#!/usr/bin/env python3
"""Report which of step 1's fields are still empty, and who can fill them.

Scope is step 1's own output contract (pipeline/1-extract/output.json). `answer`
is not checked here -- it belongs to nobody until step 4.

  parser    a question the parse damaged: options dropped, stem cut, stem never
            found. The text is in the PDF, so a code fix repairs every paper
            with the same defect at once.
  research  which exam the paper is -- bank, role, year, exam_type. Not in
            the PDF or its filename, so a web search is the only source.
            Findings go in the .meta.json sidecar, which load_meta() prefers.

Either may be filled from the web, but only with an anchor: enough of the
question left to confirm the match. A stem cut mid-sentence still has its
options to match on; a stem that is only "Question 66." does not.

    python3 pipeline/1-extract/check_gaps.py
    python3 pipeline/1-extract/check_gaps.py --fail-on-parser
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
SKIP = {"parse_report.json", "index.json", "index.jsonl",
        "gap_report.json", "review_queue.json"}

# A trailing comma is deliberately NOT a signal: para-jumble stems end on a
# fragment ("(E) on agri-business scenarios,") and flagging those buried the
# real truncations under false positives.
TRUNCATED_RE = re.compile(r"[(\[{+\-×÷=∶/]\s*$")
PLACEHOLDER_RE = re.compile(r"^(?:Question|Q)\s*\.?\s*\d+\s*[.):]?\s*$", re.IGNORECASE)

# The paper-identity fields step 1 must fill, all copied onto every question.
META_FIELDS = ("bank", "role", "year", "exam_type")
PARSER_CLASS = {"no_options", "empty_stem", "placeholder_stem",
                "truncated_stem", "duplicate_q_num"}
MIN_ANCHOR_CHARS = 25


def latest_batch(data_root: Path) -> Path | None:
    """The newest data/batch{n}, or None when nothing has been parsed.

    There is no fixed default to point at: parser.py writes data/batch{n}, and a
    default of data/papers -- which nothing creates -- made a no-argument run
    scan an empty directory and report zero gaps as though all were clean.
    """
    batches = [(int(p.name[5:]), p) for p in data_root.glob("batch*")
               if p.is_dir() and p.name[5:].isdigit()]
    return max(batches)[1] if batches else None


def rel(path: Path) -> str:
    """Repo-relative inside the repo, absolute when run against a temp dir."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def is_anchored(q: dict) -> bool:
    """Enough of the question survived to confirm a web result is the right one.

    Two independent handles are needed, because either alone matches too much:
    a distinctive run of stem text, and the option set.
    """
    stem = (q.get("stem") or "").strip()
    return (len(stem) >= MIN_ANCHOR_CHARS
            and not PLACEHOLDER_RE.match(stem)
            and len(q.get("options") or {}) >= 2)


def question_gaps(q: dict) -> list[str]:
    found = []
    stem = (q.get("stem") or "").strip()
    if not q.get("options"):
        found.append("no_options")
    # An error-spotting set states its task in the direction and prints nothing
    # but the five candidate sentences, so a blank stem there is the paper's
    # shape, not a gap. parse() keeps those questions on the same test; without
    # it this report contradicts the batch it just scored.
    if not stem and not (q.get("direction_text") or "").strip():
        found.append("empty_stem")
    elif PLACEHOLDER_RE.match(stem):
        found.append("placeholder_stem")
    elif TRUNCATED_RE.search(stem) or stem.count("(") > stem.count(")"):
        found.append("truncated_stem")
    return found


def paper_gaps(paper: dict) -> list[str]:
    found = [f"no_{f}" for f in META_FIELDS if not paper.get(f)]
    nums = [q.get("q_num") for q in paper.get("questions") or []]
    if len(nums) != len(set(nums)):
        found.append("duplicate_q_num")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=None,
                    help="a data/batch{n} folder (default: the newest)")
    ap.add_argument("--fail-on-parser", action="store_true",
                    help="exit 1 if any parser-class gap remains")
    args = ap.parse_args(argv)
    if args.root is None:
        args.root = latest_batch(DATA)
        if args.root is None:
            print(f"  no batches under {DATA} -- run parser.py first", file=sys.stderr)
            return 1

    tally: Counter[str] = Counter()
    anchoring: Counter[str] = Counter()
    papers: list[dict] = []
    total_q = total_papers = 0

    for path in sorted(args.root.rglob("*.json")):
        if path.name in SKIP:
            continue
        try:
            paper = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  skip {path.name}: {exc}", file=sys.stderr)
            continue
        # A report or index file sitting in the same folder is not a paper.
        if not isinstance(paper, dict):
            continue
        qs = paper.get("questions") or []
        if not qs:
            continue
        total_papers += 1
        total_q += len(qs)

        per_q: dict[str, list[int]] = {}
        unanchored: list[int] = []
        for q in qs:
            gaps = question_gaps(q)
            if not gaps:
                continue
            for gap in gaps:
                per_q.setdefault(gap, []).append(q.get("q_num"))
                tally[gap] += 1
            if is_anchored(q):
                anchoring["anchored"] += 1
            else:
                unanchored.append(q.get("q_num"))
                anchoring["unanchored"] += 1

        meta = paper_gaps(paper)
        for gap in meta:
            tally[gap] += 1
        if per_q or meta:
            papers.append({
                "paper_id": paper.get("paper_id"),
                "path": rel(path),
                "source_pdf": paper.get("source_pdf"),
                "paper_gaps": meta,
                "question_gaps": {k: sorted(v) for k, v in per_q.items()},
                "unanchored_q_nums": sorted(unanchored),
            })

    # Zero papers is a broken path, not a clean bill of health. Without this a
    # root that does not exist writes a report full of zeros, prints
    # "0 questions in 0 papers" and exits 0 -- and --fail-on-parser reports green
    # having checked nothing.
    if total_papers == 0:
        print(f"  no papers under {rel(args.root)} -- nothing was checked", file=sys.stderr)
        return 1

    parser_total = sum(n for gap, n in tally.items() if gap in PARSER_CLASS)
    research_total = sum(n for gap, n in tally.items() if gap not in PARSER_CLASS)

    report = {
        "papers_scanned": total_papers,
        "questions_scanned": total_q,
        "totals": dict(tally.most_common()),
        "parser_gaps": parser_total,
        "research_gaps": research_total,
        "web_fillable": anchoring["anchored"],
        "needs_parser_fix": anchoring["unanchored"],
        "papers": papers,
    }
    out = args.root / "gap_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"  {total_q} questions in {total_papers} papers\n")
    print(f"  parser gaps    {parser_total:6d}   in the PDF, parsed wrong")
    for gap in sorted(PARSER_CLASS):
        if tally[gap]:
            print(f"      {gap:20} {tally[gap]:6d}")
    print(f"\n  research gaps  {research_total:6d}   not in the PDF -- web search")
    for gap, n in sorted(tally.items()):
        if gap not in PARSER_CLASS:
            print(f"      {gap:20} {n:6d}")
    print("\n  of the damaged questions:")
    print(f"      {anchoring['anchored']:6d} anchored     enough left to match a web result against")
    print(f"      {anchoring['unanchored']:6d} unanchored   nothing to match on -- fix the parser")
    print(f"\n  wrote {rel(out)}")

    if args.fail_on_parser and parser_total:
        print(f"\n::error::{parser_total} parser-class gaps remain", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

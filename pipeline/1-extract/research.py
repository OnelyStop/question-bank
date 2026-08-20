#!/usr/bin/env python3
"""Fill the gaps a PDF cannot answer, by searching the web.

Reads `gap_report.json`, searches for each paper that is missing bank / role /
year / stage / shift, and writes what it finds into that PDF's `.meta.json`
sidecar. Step 1 already prefers the sidecar over anything derived from the path,
so re-running the extract picks the values up.

Paper metadata is filled automatically: it is a short list of known values, and
a wrong one is visible immediately. Damaged *questions* are only ever written to
a review file -- a search result that looks right is not proof it is the same
question, and a wrong stem is invisible once it ships.

Needs a Serper key (serper.dev, free tier):

    export SERPER_API_KEY=...
    python3 pipeline/1-extract/research.py
    python3 pipeline/1-extract/research.py --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parser import meta_from_text

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / "data" / "papers"
CORPUS = REPO / "corpus" / "pdf"
SERPER_URL = "https://google.serper.dev/search"
# What the parser records. No shift: it is not part of the output.
FIELDS = ("bank", "role", "year", "exam_type")

# Search the QUESTIONS, not the filename. A filename like
# "IBPS_Clerk_Prelims_Memory_Based_Quant" returns pages about the exam series
# and answers with whatever year is currently popular -- it gave 2020 and then
# 2025 for the same PDF. A quoted 12-word question stem is unique to one sitting:
# it returned "SBI PO Prelims 2025 4th Aug 2nd Shift - Question Paper", which is
# exactly right. 12 words, not 22: longer phrases stop matching once extraction
# differs by a character.
PROBE_WORDS = 12
PROBES_PER_PAPER = 5
MIN_AGREEMENT = 3
# The winner must also beat the runner-up 2:1. On a paper whose true year is
# 2019 the vote was 2021:4 vs 2019:3 -- a plain "most votes" rule would have
# written the wrong year; the margin rejects it and leaves the field null.
MIN_MARGIN = 2.0


def search(query: str, key: str, timeout: float = 20.0) -> list[dict]:
    body = json.dumps({"q": query, "num": 10}).encode()
    req = urllib.request.Request(
        SERPER_URL, data=body,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (json.loads(r.read()) or {}).get("organic") or []
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"      search failed: {exc}", file=sys.stderr)
        return []


def probe_stems(paper: dict, n: int = PROBES_PER_PAPER) -> list[str]:
    """Question stems distinctive enough to identify the sitting they came from.

    Mid-length only: a short stem ("Find the value of x") is shared by a hundred
    papers, and a long one is usually the passage every question in the set
    repeats. Spread across the paper so one mis-parsed question cannot decide it.
    """
    good = []
    for q in paper.get("questions") or []:
        s = " ".join((q.get("stem") or "").split())
        if 70 <= len(s) <= 220 and len(s.split()) >= PROBE_WORDS:
            good.append(" ".join(s.split()[:PROBE_WORDS]))
    if not good:
        return []
    step = max(1, len(good) // n)
    return good[::step][:n]


def identify(paper: dict, want: set[str], key: str) -> tuple[dict, dict]:
    """Search this paper's own questions and vote on what exam they came from."""
    votes: dict[str, Counter] = {f: Counter() for f in want}
    for stem in probe_stems(paper):
        for r in search(f'"{stem}"', key)[:8]:
            parsed = meta_from_text(f"{r.get('title', '')} {r.get('snippet', '')}")
            for f in want:
                if parsed.get(f):
                    votes[f][str(parsed[f])] += 1
        time.sleep(0.6)

    found, tally = {}, {}
    for f, counts in votes.items():
        if not counts:
            continue
        ranked = counts.most_common()
        tally[f] = dict(ranked[:3])
        (value, n) = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        if n >= MIN_AGREEMENT and n >= MIN_MARGIN * max(runner_up, 1):
            found[f] = value
    return found, tally


def sidecar_for(pdf_rel: str) -> Path | None:
    p = Path(pdf_rel)
    pdf = p if p.exists() else CORPUS / Path(*p.parts[1:]) if p.parts else None
    return pdf.with_suffix(pdf.suffix + ".meta.json") if pdf and pdf.exists() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    report_path = args.root / "gap_report.json"
    if not report_path.is_file():
        print(f"  no {report_path} -- run check_gaps.py first", file=sys.stderr)
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))

    key = os.environ.get("SERPER_API_KEY", "")
    if not key and not args.dry_run:
        print("  SERPER_API_KEY not set. Export it, or pass --dry-run to see the queue.",
              file=sys.stderr)
        return 1

    todo = [p for p in report.get("papers") or [] if p.get("paper_gaps")]
    if args.limit:
        todo = todo[: args.limit]
    print(f"  {len(todo)} papers with metadata gaps\n")

    filled = skipped = 0
    review: list[dict] = []

    for p in todo:
        want = {g[3:] for g in p["paper_gaps"] if g.startswith("no_")}
        want = set(want) & set(FIELDS)
        pdf_rel = p.get("source_pdf") or ""
        name = Path(pdf_rel).stem
        if not want or not name:
            continue

        print(f"    {name[:56]}")
        print(f"      want {sorted(want)}")
        if args.dry_run:
            skipped += 1
            continue

        try:
            paper = json.loads(Path(p["path"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue

        found, tally = identify(paper, want, key)
        for f in sorted(want - set(found)):
            review.append({"paper_id": p["paper_id"], "field": f, "votes": tally.get(f, {})})
        if not found:
            print(f"      undecided {tally or '(no results)'}")
            skipped += 1
            continue

        side = sidecar_for(pdf_rel)
        if not side:
            print("      no sidecar (PDF missing)")
            skipped += 1
            continue

        data = json.loads(side.read_text(encoding="utf-8")) if side.is_file() else {}
        wrote = {k: v for k, v in found.items() if not data.get(k)}
        if not wrote:
            skipped += 1
            continue
        data.update(wrote)
        data.setdefault("research", {})["method"] = "question-search"
        data["research"]["filled"] = sorted(wrote)
        data["research"]["votes"] = tally
        if not args.dry_run:
            side.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"      filled {wrote}")
        filled += 1

    # Damaged questions are queued for a person, never auto-written: a search
    # result that looks right is not proof it is the same question.
    questions = []
    for p in report.get("papers") or []:
        anchored = (set(sum((p.get("question_gaps") or {}).values(), []))
                    - set(p.get("unanchored_q_nums") or []))
        if anchored:
            questions.append({"paper_id": p["paper_id"], "q_nums": sorted(anchored)})

    out = args.root / "review_queue.json"
    out.write_text(json.dumps({"metadata": review, "questions": questions}, indent=2),
                   encoding="utf-8")
    n_q = sum(len(r["q_nums"]) for r in questions)
    print(f"\n  review queue -> {out.name}")
    print(f"      {len(review):5d} year/shift suggestions to confirm by hand")
    print(f"      {n_q:5d} damaged questions to check against the PDF")

    print(f"\n  filled {filled} papers, skipped {skipped}")
    print("  re-run parser.py to pick up the sidecars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

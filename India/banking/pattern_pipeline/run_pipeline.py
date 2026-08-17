#!/usr/bin/env python3
"""
Run the banking question pattern extraction pipeline.

Reads papers from India/banking/papers and/or papers-deduped,
classifies each question with pattern skills, and writes uniform
Supabase-ready JSONL (+ summary report).

Examples:
  python run_pipeline.py
  python run_pipeline.py --source papers-deduped
  python run_pipeline.py --limit-papers 5 --out-dir out/sample
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BANKING = ROOT.parent
REPO = BANKING.parent.parent

# Allow `python run_pipeline.py` from this directory
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extract import extract_paper  # noqa: E402
from quality import audit, is_serveable  # noqa: E402


SKIP_NAMES = {
    "parse_report.json",
    "question_bank.schema.json",
    "index.json",
}


def iter_paper_files(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for fp in sorted(source_dir.rglob("*.json")):
        if fp.name in SKIP_NAMES or "schema" in fp.name.lower():
            continue
        files.append(fp)
    return files


def load_paper(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or "questions" not in data:
        return None
    return data


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract uniform patterned questions for Supabase")
    parser.add_argument(
        "--source",
        choices=["papers", "papers-deduped", "both"],
        default="both",
        help="Which paper collection to read",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "out",
        help="Output directory for questions.jsonl and report.json",
    )
    parser.add_argument("--limit-papers", type=int, default=0, help="Optional cap for smoke tests")
    parser.add_argument(
        "--prefer",
        choices=["papers-deduped", "papers"],
        default="papers-deduped",
        help="When both sources have the same paper_id, keep this collection",
    )
    parser.add_argument(
        "--no-quarantine",
        action="store_true",
        help="Keep every row in questions.jsonl instead of splitting out flagged.jsonl",
    )
    args = parser.parse_args()

    sources: list[tuple[str, Path]] = []
    if args.source in ("papers", "both"):
        sources.append(("papers", BANKING / "papers"))
    if args.source in ("papers-deduped", "both"):
        sources.append(("papers-deduped", BANKING / "papers-deduped"))

    by_qid: dict[str, dict[str, Any]] = {}
    qid_collection: dict[str, str] = {}
    pattern_counts: Counter[str] = Counter()
    secondary_counts: Counter[str] = Counter()
    papers_seen = 0
    papers_used = 0
    questions_seen = 0
    skipped_files = 0

    for collection, source_dir in sources:
        if not source_dir.exists():
            print(f"skip missing source: {source_dir}", file=sys.stderr)
            continue
        files = iter_paper_files(source_dir)
        for fp in files:
            if args.limit_papers and papers_seen >= args.limit_papers:
                break
            paper = load_paper(fp)
            papers_seen += 1
            if paper is None:
                skipped_files += 1
                continue
            rows = extract_paper(paper, source_collection=collection)
            papers_used += 1
            questions_seen += len(rows)
            for row in rows:
                qid = row["q_id"]
                existing = by_qid.get(qid)
                if existing is None:
                    by_qid[qid] = row
                    qid_collection[qid] = collection
                    continue
                # Prefer configured collection on duplicates
                if qid_collection.get(qid) != args.prefer and collection == args.prefer:
                    by_qid[qid] = row
                    qid_collection[qid] = collection

    rows = list(by_qid.values())
    rows.sort(key=lambda r: r.get("q_id") or "")

    for row in rows:
        pattern_counts[row["question_pattern"]] += 1
        for sec in row.get("secondary_patterns") or []:
            secondary_counts[sec] += 1

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "questions.jsonl"
    flagged_path = out_dir / "flagged.jsonl"
    report_path = out_dir / "report.json"
    by_pattern_dir = out_dir / "by_pattern"
    by_pattern_dir.mkdir(parents=True, exist_ok=True)

    # Quality pass. Blocking rows are held back rather than shipped, the same way
    # sets/usable + sets/flagged already split that lane.
    defects_by_qid = audit(rows)
    flagged_counts: Counter[str] = Counter()
    clean: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    for row in rows:
        defects = defects_by_qid.get(row.get("q_id")) or []
        if args.no_quarantine or is_serveable(defects):
            clean.append(row)
        else:
            reasons = sorted({d.reason for d in defects if d.tier in ("fatal", "blocking")})
            for reason in reasons:
                flagged_counts[reason] += 1
            flagged.append({**row, "flagged_reasons": reasons})

    write_jsonl(jsonl_path, clean)
    if not args.no_quarantine:
        write_jsonl(flagged_path, flagged)

    # Also split by pattern for easier QA / staged uploads.
    # Seeded with every pattern seen, so a pattern whose rows were all quarantined
    # gets truncated to empty rather than leaving the previous run's file on disk
    # -- otherwise by_pattern/ still serves exactly the rows we just held back.
    grouped: dict[str, list[dict[str, Any]]] = {p: [] for p in pattern_counts}
    for row in clean:
        grouped.setdefault(row["question_pattern"], []).append(row)
    for pattern, group in grouped.items():
        write_jsonl(by_pattern_dir / f"{pattern}.jsonl", group)

    report = {
        "papers_seen": papers_seen,
        "papers_used": papers_used,
        "skipped_files": skipped_files,
        "questions_seen_before_dedupe": questions_seen,
        "questions_unique": len(rows),
        "questions_clean": len(clean),
        "questions_flagged": len(flagged),
        "source": args.source,
        "prefer": args.prefer,
        "quarantine": not args.no_quarantine,
        "pattern_counts": dict(pattern_counts.most_common()),
        "secondary_counts": dict(secondary_counts.most_common()),
        "flagged_counts": dict(flagged_counts.most_common()),
        "outputs": {
            "questions_jsonl": str(jsonl_path.as_posix()),
            "flagged_jsonl": None if args.no_quarantine else str(flagged_path.as_posix()),
            "report_json": str(report_path.as_posix()),
            "by_pattern_dir": str(by_pattern_dir.as_posix()),
        },
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"papers_used={papers_used} unique_questions={len(rows)}")
    print(f"  clean={len(clean)}  flagged={len(flagged)}")
    print(f"wrote {jsonl_path}")
    if not args.no_quarantine:
        print(f"wrote {flagged_path}")
    print(f"wrote {report_path}")
    for pattern, count in pattern_counts.most_common():
        print(f"  {count:6d}  {pattern}")
    if flagged_counts:
        print("held back:")
        for reason, count in flagged_counts.most_common():
            print(f"  {count:6d}  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

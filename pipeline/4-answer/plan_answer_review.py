"""Create a deterministic, read-only plan for answering the remaining questions.

The plan intentionally never writes the question-bank JSON.  It is useful before
exporting work to a subscription-agent/human review workflow: every handoff is
kept within one source batch and uses a stable q_id ordering.

Usage:
  python pipeline/4-answer/plan_answer_review.py
  python pipeline/4-answer/plan_answer_review.py --handoff-size 25 --report data/answer_review_plan.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper


def batch_name_for(path: Path, out_root: Path) -> str:
    """Return the top-level data batch; tolerate a paper directly under --out."""
    try:
        rel = path.relative_to(out_root)
    except ValueError:
        return "unknown"
    return rel.parts[0] if len(rel.parts) > 1 else "unknown"


def chunked(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def plan(out_root: Path, handoff_size: int) -> dict[str, Any]:
    if handoff_size < 1:
        raise ValueError("--handoff-size must be at least 1")

    unanswered_by_batch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    totals = Counter()
    answered_by_batch = Counter()
    invalid_unanswered = Counter()

    for path in sorted(iter_paper_jsons(out_root), key=lambda p: str(p).replace("\\", "/")):
        paper = load_paper(path)
        if not paper:
            continue
        batch = batch_name_for(path, out_root)
        for question in paper.get("questions") or []:
            totals[batch] += 1
            if question.get("answer"):
                answered_by_batch[batch] += 1
                continue
            options = question.get("options") or {}
            stem = str(question.get("stem") or "").strip()
            safe_for_review = bool(question.get("q_id") and stem and len(options) >= 2)
            if not safe_for_review:
                invalid_unanswered[batch] += 1
            unanswered_by_batch[batch].append(
                {
                    "q_id": str(question.get("q_id") or ""),
                    "paper_id": str(paper.get("paper_id") or ""),
                    "q_num": question.get("q_num"),
                    "section": str(question.get("section") or "Unclassified"),
                    "topic": str(question.get("topic") or "Unclassified"),
                    "question_pattern": str(question.get("question_pattern") or "unknown"),
                    "safe_for_review": safe_for_review,
                }
            )

    batch_reports: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []
    for batch in sorted(totals, key=lambda name: (int(name[5:]) if name.startswith("batch") and name[5:].isdigit() else 10**9, name)):
        pending = sorted(
            unanswered_by_batch[batch],
            key=lambda row: (row["paper_id"], int(row["q_num"] or 0), row["q_id"]),
        )
        safe = [row for row in pending if row["safe_for_review"]]
        for index, group in enumerate(chunked(safe, handoff_size), start=1):
            handoffs.append(
                {
                    "handoff_id": f"{batch}-answers-{index:03d}",
                    "batch": batch,
                    "question_count": len(group),
                    "first_q_id": group[0]["q_id"],
                    "last_q_id": group[-1]["q_id"],
                    "paper_ids": sorted({row["paper_id"] for row in group}),
                }
            )
        batch_reports.append(
            {
                "batch": batch,
                "questions": totals[batch],
                "answered": answered_by_batch[batch],
                "unanswered": len(pending),
                "coverage_pct": round(100 * answered_by_batch[batch] / totals[batch], 2) if totals[batch] else 0.0,
                "safe_for_subscription_review": len(safe),
                "needs_data_repair_before_review": invalid_unanswered[batch],
                "section_counts": dict(sorted(Counter(row["section"] for row in pending).items())),
                "topic_counts": dict(sorted(Counter(row["topic"] for row in pending).items())),
                "pattern_counts": dict(sorted(Counter(row["question_pattern"] for row in pending).items())),
            }
        )

    questions = sum(totals.values())
    answered = sum(answered_by_batch.values())
    return {
        "schema_version": 1,
        "planning_rules": {
            "ordering": "batch number, paper_id, q_num, q_id",
            "handoff_boundary": "Never mixes source batches.",
            "safe_for_subscription_review": "q_id, non-empty stem, and at least two options are required.",
        },
        "summary": {
            "questions": questions,
            "answered": answered,
            "unanswered": questions - answered,
            "answer_coverage_pct": round(100 * answered / questions, 2) if questions else 0.0,
            "safe_for_subscription_review": sum(item["question_count"] for item in handoffs),
            "needs_data_repair_before_review": sum(invalid_unanswered.values()),
            "handoff_size": handoff_size,
            "handoff_count": len(handoffs),
        },
        "batches": batch_reports,
        "handoffs": handoffs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan safe, deterministic answer-review handoffs")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Question-bank data directory")
    parser.add_argument("--handoff-size", type=int, default=25)
    parser.add_argument("--report", help="Optional JSON output path; does not alter question data")
    args = parser.parse_args(argv)
    result = plan(Path(args.out), args.handoff_size)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

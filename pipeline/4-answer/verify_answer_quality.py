"""Read-only quality audit for extracted answers and explanations.

This tool never changes a paper.  It checks mechanical invariants that can be
verified offline and creates a bounded queue for human/subscription-agent
review.  It deliberately does not judge whether an explanation is *correct*:
that requires reading the source question or an independent reviewer.

Usage:
  python verify_answer_quality.py
  python verify_answer_quality.py --out data --sample-size 250
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper


MOJIBAKE_RE = re.compile(r"(?:\ufffd|â€¦|â€|Ã.|à¤|à¥)")
WHITESPACE_RE = re.compile(r"\s+")


def compact(value: Any, limit: int) -> str:
    """Normalise and bound text kept in a review queue."""
    text = WHITESPACE_RE.sub(" ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def question_row(paper: dict[str, Any], question: dict[str, Any], flags: list[str]) -> dict[str, Any]:
    """Expose only fields a reviewer needs; no source corpus data is mutated."""
    return {
        "q_id": question.get("q_id"),
        "paper_id": paper.get("paper_id"),
        "q_num": question.get("q_num"),
        "bank": paper.get("bank"),
        "role": paper.get("role"),
        "year": paper.get("year"),
        "section": question.get("section"),
        "topic": question.get("topic"),
        "answer": question.get("answer"),
        "options": question.get("options") or {},
        "answer_source": question.get("answer_source"),
        "answer_confidence": question.get("answer_confidence"),
        "stem": compact(question.get("stem"), 500),
        "explanation": compact(question.get("explanation"), 1_000),
        "flags": flags,
        "review_instruction": "Verify the selected option and explanation against the source PDF; do not infer an answer from this queue alone.",
    }


def flags_for(question: dict[str, Any]) -> list[str]:
    """Return deterministic, mechanical review flags for one question."""
    flags: list[str] = []
    answer = question.get("answer")
    options = question.get("options") or {}
    explanation = question.get("explanation")
    confidence = question.get("answer_confidence")

    if answer:
        if not isinstance(options, dict) or answer not in options:
            flags.append("answer_not_in_options")
        if not question.get("answer_source"):
            flags.append("answer_source_missing")
        if confidence is None:
            flags.append("answer_confidence_missing")
        elif not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            flags.append("answer_confidence_invalid")
        elif confidence < 0.8:
            flags.append("answer_low_confidence")
    elif explanation:
        flags.append("explanation_without_answer")

    if explanation is not None:
        if not isinstance(explanation, str):
            flags.append("explanation_not_string")
        else:
            stripped = explanation.strip()
            if not stripped:
                flags.append("explanation_blank")
            elif len(stripped) < 20:
                flags.append("explanation_too_short")
            elif len(stripped) > 8_000:
                flags.append("explanation_too_long")
            if MOJIBAKE_RE.search(explanation):
                flags.append("explanation_possible_mojibake")
    elif answer:
        flags.append("answer_without_explanation")
    return flags


def audit(out_root: Path, *, sample_size: int, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Audit the corpus and return a summary plus a priority review queue."""
    paths = iter_paper_jsons(out_root)
    if not paths:
        raise ValueError(f"No paper JSON files found below {out_root}")

    total = answered = explained = valid_answer = 0
    flag_counts: Counter[str] = Counter()
    per_batch: dict[str, Counter[str]] = {}
    flagged: list[dict[str, Any]] = []
    clean_answered: list[dict[str, Any]] = []

    for path in paths:
        paper = load_paper(path)
        if not paper:
            continue
        batch = path.parent.name
        batch_counts = per_batch.setdefault(batch, Counter())
        for question in paper.get("questions") or []:
            total += 1
            batch_counts["questions"] += 1
            answer = question.get("answer")
            explanation = question.get("explanation")
            if answer:
                answered += 1
                batch_counts["answered"] += 1
            if explanation:
                explained += 1
                batch_counts["explained"] += 1

            flags = flags_for(question)
            if answer and answer in (question.get("options") or {}):
                valid_answer += 1
            for flag in flags:
                flag_counts[flag] += 1
                batch_counts[flag] += 1
            row = question_row(paper, question, flags)
            if flags:
                flagged.append(row)
            elif answer:
                clean_answered.append(row)

    if not total:
        raise ValueError(f"Paper JSON files below {out_root} contain no questions")

    # Prioritise objective invalidity and encoding corruption, then a stable
    # random sample of otherwise mechanically clean answers for correctness QA.
    priority = {
        "answer_not_in_options": 0,
        "explanation_possible_mojibake": 1,
        "answer_confidence_invalid": 2,
        "explanation_without_answer": 3,
        "answer_low_confidence": 4,
        "answer_without_explanation": 5,
    }
    flagged.sort(key=lambda row: (min(priority.get(flag, 9) for flag in row["flags"]), str(row["q_id"])))
    rng = random.Random(seed)
    rng.shuffle(clean_answered)
    queue = flagged[:sample_size]
    if len(queue) < sample_size:
        queue.extend(clean_answered[: sample_size - len(queue)])

    batches: dict[str, dict[str, Any]] = {}
    for batch, counts in sorted(per_batch.items()):
        questions = counts["questions"]
        batches[batch] = {
            "questions": questions,
            "answered": counts["answered"],
            "explained": counts["explained"],
            "answer_coverage_pct": round(100 * counts["answered"] / questions, 2),
            "explanation_coverage_pct": round(100 * counts["explained"] / questions, 2),
            "flags": {key: value for key, value in counts.items() if key not in {"questions", "answered", "explained"}},
        }

    report = {
        "summary": {
            "questions": total,
            "answered": answered,
            "explained": explained,
            "valid_answer_keys": valid_answer,
            "answer_coverage_pct": round(100 * answered / total, 2),
            "explanation_coverage_pct": round(100 * explained / total, 2),
            "valid_answer_key_pct": round(100 * valid_answer / answered, 2) if answered else 0,
            "flagged_questions": len(flagged),
            "review_queue_size": len(queue),
            "read_only": True,
        },
        "flag_counts": dict(sorted(flag_counts.items())),
        "batches": batches,
        "flagged_examples": flagged[:200],
        "review_notes": (
            "This report checks data shape and text health only. A reviewer must compare each queued answer and explanation with its source PDF before accepting it."
        ),
    }
    return report, queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only answer/explanation quality audit")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Question-bank data directory")
    parser.add_argument("--report", help="Report output path (default: <out>/answer_quality_report.json)")
    parser.add_argument("--review-queue", help="Queue output path (default: <out>/answer_quality_review_queue.jsonl)")
    parser.add_argument("--sample-size", type=int, default=250, help="Maximum review records to export")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed for clean-answer sampling")
    args = parser.parse_args(argv)
    if args.sample_size < 0:
        parser.error("--sample-size must be non-negative")

    out_root = Path(args.out)
    report_path = Path(args.report) if args.report else out_root / "answer_quality_report.json"
    queue_path = Path(args.review_queue) if args.review_queue else out_root / "answer_quality_review_queue.jsonl"
    try:
        report, queue = audit(out_root, sample_size=args.sample_size, seed=args.seed)
    except ValueError as exc:
        parser.error(str(exc))

    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with queue_path.open("w", encoding="utf-8") as handle:
        for row in queue:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"Wrote {report_path}")
    print(f"Wrote {queue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

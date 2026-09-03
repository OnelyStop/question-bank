#!/usr/bin/env python3
"""Remove unusable question records from an extracted corpus.

The corpus stores Hindi correctly as UTF-8, though some terminals render it as
mojibake. The optional sparse-fragment pass keeps self-contained arithmetic and
number-series questions while removing incomplete extraction remnants.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEVANAGARI_START = "\u0900"
DEVANAGARI_END = "\u097f"


def question_text(question: dict[str, Any]) -> str:
    options = question.get("options") or {}
    option_values = options.values() if isinstance(options, dict) else []
    return " ".join(
        str(value) for value in [question.get("direction_text"), question.get("stem"), *option_values]
        if value
    )


def is_corrupted(question: dict[str, Any]) -> bool:
    text = question_text(question)
    return any(DEVANAGARI_START <= char <= DEVANAGARI_END for char in text)


def is_self_contained_math(question: dict[str, Any]) -> bool:
    stem = str(question.get("stem") or "")
    digit_count = sum(char.isdigit() for char in stem)
    has_operator = any(char in stem for char in "+-=*/%^×÷")
    is_long_series = stem.count(",") >= 4
    return digit_count >= 3 and (has_operator or is_long_series)


def is_sparse_fragment(question: dict[str, Any]) -> bool:
    direction = str(question.get("direction_text") or "")
    text = question_text(question)
    direction_letters = sum(char.isascii() and char.isalpha() for char in direction)
    total_letters = sum(char.isascii() and char.isalpha() for char in text)
    return direction_letters < 20 and total_letters < 20 and not is_self_contained_math(question)


def clean(papers_dir: Path, *, dry_run: bool, remove_sparse: bool) -> dict[str, Any]:
    removed: list[dict[str, Any]] = []
    touched = 0
    for path in sorted(papers_dir.glob("*.json")):
        if path.name.endswith("_report.json"):
            continue
        paper = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(paper, dict) or not isinstance(paper.get("questions"), list):
            continue
        questions = paper.get("questions") or []
        retained = []
        for question in questions:
            reason = "hindi_devanagari" if is_corrupted(question) else None
            if remove_sparse and not reason and is_sparse_fragment(question):
                reason = "sparse_fragment"
            if reason:
                removed.append({"paper": path.name, "q_id": question.get("q_id"), "q_num": question.get("q_num"), "reason": reason})
            else:
                retained.append(question)
        if len(retained) != len(questions):
            touched += 1
            paper["questions"] = retained
            paper["question_count"] = len(retained)
            if not dry_run:
                path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"papers_dir": str(papers_dir), "dry_run": dry_run, "papers_touched": touched, "questions_removed": len(removed), "removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-sparse", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = clean(args.papers_dir, dry_run=args.dry_run, remove_sparse=args.remove_sparse)
    if not args.dry_run:
        report_path = args.report or args.papers_dir.parent / f"{args.papers_dir.name}-cleanup-report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({key: value for key, value in report.items() if key != "removed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

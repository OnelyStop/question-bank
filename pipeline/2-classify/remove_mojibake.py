#!/usr/bin/env python3
"""Preview or remove unusable Hindi-only / sparse extraction records.

This tool fails closed: it previews by default, requires ``--apply`` to write,
and refuses empty or no-op inputs. Bilingual questions are retained so step 2
can strip their appended Hindi while preserving the English content.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
NON_LATIN = re.compile(r"[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0600-\u06FF]")
LATIN = re.compile(r"[A-Za-z]")


def question_values(question: dict[str, Any]) -> list[str]:
    options = question.get("options") or {}
    option_values = options.values() if isinstance(options, dict) else []
    return [str(value) for value in [question.get("direction_text"), question.get("stem"), *option_values] if value]


def question_text(question: dict[str, Any]) -> str:
    return " ".join(question_values(question))


def is_hindi_only(question: dict[str, Any]) -> bool:
    """Return true only when Devanagari exists and no Latin survives stripping."""
    values = question_values(question)
    return bool(DEVANAGARI.search(" ".join(values))) and not any(
        LATIN.search(NON_LATIN.sub(" ", value)) for value in values
    )


def is_self_contained_math(question: dict[str, Any]) -> bool:
    stem = str(question.get("stem") or "")
    digit_count = sum(char.isdigit() for char in stem)
    has_operator = any(char in stem for char in "+-=*/%^×÷")
    return digit_count >= 3 and (has_operator or stem.count(",") >= 4)


def is_sparse_fragment(question: dict[str, Any]) -> bool:
    direction = str(question.get("direction_text") or "")
    text = question_text(question)
    direction_letters = sum(char.isascii() and char.isalpha() for char in direction)
    total_letters = sum(char.isascii() and char.isalpha() for char in text)
    return direction_letters < 20 and total_letters < 20 and not is_self_contained_math(question)


def clean(papers_dir: Path, *, dry_run: bool = True, remove_sparse: bool = False) -> dict[str, Any]:
    if not papers_dir.is_dir():
        raise ValueError(f"papers directory does not exist: {papers_dir}")
    paths = [p for p in sorted(papers_dir.glob("*.json")) if not p.name.endswith("_report.json")]
    if not paths:
        raise ValueError(f"no JSON files found in {papers_dir}")

    removed: list[dict[str, Any]] = []
    touched = valid_papers = 0
    for path in paths:
        paper = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(paper, dict) or not isinstance(paper.get("questions"), list):
            continue
        valid_papers += 1
        questions = paper["questions"]
        retained = []
        for question in questions:
            reason = "hindi_only" if is_hindi_only(question) else None
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

    if not valid_papers:
        raise ValueError(f"no valid paper JSON files found in {papers_dir}")
    if not removed:
        raise ValueError("cleanup found no removable records; refusing a no-op success")
    return {"papers_dir": str(papers_dir), "dry_run": dry_run, "papers_touched": touched, "questions_removed": len(removed), "removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="write removals; default is a dry-run preview")
    parser.add_argument("--remove-sparse", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = clean(args.papers_dir, dry_run=not args.apply, remove_sparse=args.remove_sparse)
    except ValueError as exc:
        parser.error(str(exc))
    if args.apply:
        report_path = args.report or args.papers_dir.parent / f"{args.papers_dir.name}-cleanup-report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "removed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

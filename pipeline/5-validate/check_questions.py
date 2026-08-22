#!/usr/bin/env python3
"""Reject a batch whose questions carry a defect we have shipped before.

check_gaps.py reports what is missing; this rejects what is present but wrong.
Every rule is a real bug from batch 1 -- if one of these patterns reappears,
the parse regressed and the JSON must not merge.

    python3 pipeline/5-validate/check_questions.py            # all data/batch*/
    python3 pipeline/5-validate/check_questions.py data/batch1
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKIP = {"parse_report.json", "index.json", "index.jsonl",
        "gap_report.json", "review_queue.json"}

REQUIRED = ("q_id", "paper_id", "q_num", "stem", "options", "direction_id",
            "direction_text", "direction_has_image", "direction_image_refs",
            "bank", "role", "exam_type", "year", "memory_based",
            "has_image", "image_refs")


def schema_fields() -> set[str]:
    """Every field schema.json declares.

    schema.json is `additionalProperties: false`, so a field the parser writes
    and the schema does not declare is a contract break -- it will be rejected
    at import, after the batch has merged. Nothing caught that before: REQUIRED
    above is a hardcoded list that only asks what must be PRESENT, and
    check_examples.py validates the per-step output.json examples rather than
    the committed data. `corrected` reached 18 questions across 10 files that
    way.
    """
    schema = json.loads((REPO / "schema" / "schema.json").read_text(encoding="utf-8"))
    return set(schema["properties"])

RULES = [
    # (name, field-selector, pattern) -- pattern hit == defect
    ("answer_key_bleed", "options",
     re.compile(r"(?i)\bans\s*\.\s*\(?\s*[a-e]\s*\)?\s*$|\bans\s*\.\s*$")),
    ("direction_bleed", "options",
     re.compile(r"(?i)Directions?\s*[\(\d]|Q\s*\d+\s*\.")),
    ("boilerplate", "any",
     re.compile(r"(?i)adda247|bankersadda|careerpower|www\.[a-z0-9-]+\.")),
    # superscript garbling: a raised operator never appears in real content
    ("raised_operator", "any", re.compile("[⁺⁻⁼⁽⁾]")),
    # "28^(th) June" -- a date's suffix is set raised and small, so it reads as
    # an exponent. It is prose, and 141 dates across two batches came out this
    # way before the parser stopped raising it.
    ("raised_ordinal", "any", re.compile(r"(?i)\d\s*\^\(\s*(?:st|nd|rd|th)\s*\)")),
    # a stem that is only its own number is a parse failure, not a question
    ("placeholder_stem", "stem",
     re.compile(r"^(?:Question|Q)\s*\.?\s*\d+\s*[.):]?\s*$", re.I)),
    ("solution_bleed", "any", re.compile(r"(?i)\bsol\s*\.\s|\bsolution\s*:")),
    # "…topmost position? ?" -- a bilingual paper prints the question twice and
    # the Hindi sentence's ASCII "?" outlives the Devanagari run it sat in. Only
    # at the END: 97 maths stems legitimately hold two ("What should come in
    # place of (?) …? 150%"), and none of 4,778 merged questions ends in a run
    # of them for a good reason.
    ("doubled_question_mark", "stem", re.compile(r"\?(?:\s*\?)+\s*$")),
]


def texts(q: dict, selector: str):
    if selector in ("stem", "any"):
        yield "stem", q.get("stem") or ""
    if selector in ("options", "any"):
        for k, v in (q.get("options") or {}).items():
            yield f"option {k}", v
    if selector == "any":
        yield "direction", q.get("direction_text") or ""


def check_paper(path: Path, paper: dict, declared: set[str] | None = None) -> list[str]:
    errs: list[str] = []
    qs = paper.get("questions") or []
    nums = [q.get("q_num") for q in qs]
    if len(nums) != len(set(nums)):
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        errs.append(f"duplicate q_num {dupes}")

    for q in qs:
        missing = [f for f in REQUIRED if f not in q]
        if missing:
            errs.append(f"q{q.get('q_num')}: missing fields {missing}")
        if declared:
            undeclared = sorted(set(q) - declared)
            if undeclared:
                errs.append(f"q{q.get('q_num')}: fields not in schema.json "
                            f"{undeclared} (additionalProperties is false)")
        for k, v in (q.get("options") or {}).items():
            if k not in "abcde":
                errs.append(f"q{q.get('q_num')}: option key {k!r}")
            if not str(v).strip():
                errs.append(f"q{q.get('q_num')}: empty option ({k})")
        # unbalanced LaTeX braces render as garbage downstream
        stem = q.get("stem") or ""
        if stem.count("{") != stem.count("}"):
            errs.append(f"q{q.get('q_num')}: unbalanced braces in stem")
        for name, selector, pat in RULES:
            for where, text in texts(q, selector):
                if pat.search(text):
                    errs.append(f"q{q.get('q_num')}: {name} in {where}: {text[:60]!r}")
    return errs


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    roots = [Path(a) for a in args] or sorted((REPO / "data").glob("batch*"))
    declared = schema_fields()
    papers = 0
    questions = 0
    failures: list[str] = []

    for root in roots:
        for path in sorted(root.rglob("*.json")):
            if path.name in SKIP:
                continue
            try:
                paper = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                failures.append(f"{path}: unreadable ({exc})")
                continue
            if not isinstance(paper, dict) or "questions" not in paper:
                continue
            papers += 1
            questions += len(paper["questions"])
            for err in check_paper(path, paper, declared):
                failures.append(f"{path.relative_to(REPO) if path.is_relative_to(REPO) else path}: {err}")

    # Scanning nothing is a broken path, not a clean bill of health.
    if papers == 0:
        print(f"::error::no papers found under {[str(r) for r in roots]}", file=sys.stderr)
        return 1

    if failures:
        print(f"{len(failures)} defect(s) across {papers} papers:\n", file=sys.stderr)
        for f in failures[:50]:
            print(f"  {f}", file=sys.stderr)
        if len(failures) > 50:
            print(f"  ... and {len(failures) - 50} more", file=sys.stderr)
        return 1

    print(f"  OK — {questions} questions in {papers} papers, no known defect "
          f"patterns, no field outside schema.json's {len(declared)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared helpers for the test suite.

Deliberately not named `test_*`: the runner and pytest both collect modules by
that prefix, and this one holds no cases.

Pipeline step folders are named `1-extract`, `5-validate` and so on -- not valid
Python identifiers, so they cannot be imported as packages. Each has to go on
sys.path directly, which is what `step()` does.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def step(folder: str, module: str):
    """Import `module` out of pipeline/<folder>/."""
    path = str(REPO / "pipeline" / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module(module)


def check(name: str, got, want) -> None:
    assert got == want, f"{name}\n    got : {got!r}\n    want: {want!r}"


def check_in(name: str, needle: str, haystack) -> None:
    joined = " | ".join(haystack) if isinstance(haystack, list) else str(haystack)
    assert needle in joined, f"{name}\n    {needle!r} not found in: {joined!r}"


def check_not_in(name: str, needle: str, haystack) -> None:
    joined = " | ".join(haystack) if isinstance(haystack, list) else str(haystack)
    assert needle not in joined, f"{name}\n    {needle!r} unexpectedly in: {joined!r}"


def line(*spans):
    """A PyMuPDF text line: (text, size, flags) per span.

    flags bit 0 is the superscript bit, so 5 is superscript and 4 is not.
    """
    return {"spans": [{"text": t, "size": s, "flags": f} for t, s, f in spans]}


# The 16 fields step 1 puts on every question -- see pipeline/1-extract/output.json.
QUESTION_FIELDS = (
    "q_id", "paper_id", "q_num", "stem", "options", "direction_id",
    "direction_text", "direction_has_image", "direction_image_refs",
    "bank", "role", "exam_type", "year", "memory_based",
    "has_image", "image_refs",
)


def question(**overrides) -> dict:
    """A complete, defect-free question. Override one field to make it bad."""
    q = {
        "q_id": "ibps-po-mains-2022-q1", "paper_id": "ibps-po-mains-2022",
        "q_num": 1, "stem": "What is the value of 12 + 13?",
        "options": {"a": "24", "b": "25", "c": "26", "d": "27", "e": "28"},
        "direction_id": "d001", "direction_text": "Solve the following.",
        "direction_has_image": False, "direction_image_refs": [],
        "bank": "IBPS", "role": "PO", "exam_type": "Mains", "year": 2022,
        "memory_based": True, "has_image": False, "image_refs": [],
    }
    q.update(overrides)
    return q


def paper(*questions_, **overrides) -> dict:
    p = {
        "source": "paper.pdf", "source_pdf": "corpus/done/paper.pdf",
        "paper_id": "ibps-po-mains-2022", "bank": "IBPS", "role": "PO",
        "exam_type": "Mains", "year": 2022, "memory_based": True,
        "question_count": len(questions_), "image_only_q_nums": [],
        "questions": list(questions_) or [question()],
    }
    p.update(overrides)
    return p

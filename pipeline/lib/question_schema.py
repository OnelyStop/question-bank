"""JSON schemas / builders for the bank-exam question bank.

Question.to_dict() writes the step-1 slice of schema/schema.json (17 of 28
fields) directly -- see pipeline/1-extract/README.md. There is one shape, not
four: every field name here is a schema field, and steps 2-4 add more of the
same object rather than translating between formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from context_completeness import needs_figure_stimulus


SECTION_HEADERS: list[tuple[str, re.Pattern[str]]] = [
    ("Reasoning", re.compile(r"\bREASONING(?:\s+ABILITY)?\b", re.I)),
    ("Quantitative", re.compile(r"\bQUANTITATIVE(?:\s+APTITUDE)?\b|\bNUMERICAL\s+ABILITY\b|\bQUANT\b", re.I)),
    ("English", re.compile(r"\bENGLISH(?:\s+LANGUAGE)?\b", re.I)),
    ("GA", re.compile(r"\bGENERAL\s+AWARENESS\b|\bGA\b|\bBANKING\s+AWARENESS\b|\bCURRENT\s+AFFAIRS\b", re.I)),
    ("Computer", re.compile(r"\bCOMPUTER(?:\s+APTITUDE|\s+KNOWLEDGE)?\b", re.I)),
]


@dataclass
class Question:
    q_id: str
    q_num: int
    direction_id: str | None
    direction_text: str | None
    stem: str
    options: dict[str, str]
    # Internal working state -- direction/figure blocks used to derive
    # direction_image_refs below. Never serialized: it isn't a schema field.
    context: list[dict[str, Any]] = field(default_factory=list)
    # Paper-level fields, copied on so a question filters without a join.
    # Filled in by convert_pdf() once paper metadata is known.
    paper_id: str | None = None
    bank: str | None = None
    role: str | None = None
    exam_type: str | None = None
    year: int | None = None
    shift: str | None = None
    memory_based: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        direction_image_refs: list[str] = []
        for block in self.context:
            if block.get("type") == "image" and block.get("role") == "figure":
                asset = block.get("asset")
                if asset and asset not in direction_image_refs:
                    direction_image_refs.append(asset)

        # A figure crop only ever gets attempted for a question covered by an
        # active direction (see layout_parse.py) -- a standalone question that
        # needs one is flagged here with no file behind it, same as the
        # existing direction case; nothing here builds a new crop path.
        # A crop that actually exists outranks the wording test: the regex can
        # only guess from prose, while an exported file is proof there was a
        # figure on the page.
        wants_figure = bool(direction_image_refs) or needs_figure_stimulus(
            self.direction_text, self.stem, self.options
        )

        return {
            "q_id": self.q_id,
            "paper_id": self.paper_id,
            "q_num": self.q_num,
            "stem": self.stem,
            "options": self.options,
            "direction_id": self.direction_id,
            "direction_text": self.direction_text,
            "direction_has_image": bool(self.direction_id) and wants_figure,
            "direction_image_refs": direction_image_refs,
            "bank": self.bank,
            "role": self.role,
            "exam_type": self.exam_type,
            "year": self.year,
            "shift": self.shift,
            "memory_based": self.memory_based,
            "has_image": (not self.direction_id) and wants_figure,
            "image_refs": [],
        }


@dataclass
class Paper:
    paper_id: str
    source: dict[str, Any]
    bank: str | None
    role: str | None
    exam_type: str | None
    year: int | None
    shift: str | None
    memory_based: bool
    language: str | None
    parse_status: str
    questions: list[Question] = field(default_factory=list)
    parse_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "source": self.source,
            "bank": self.bank,
            "role": self.role,
            "exam_type": self.exam_type,
            "year": self.year,
            "shift": self.shift,
            "memory_based": self.memory_based,
            "language": self.language,
            "parse_status": self.parse_status,
            "parse_notes": self.parse_notes,
            "question_count": len(self.questions),
            "questions": [q.to_dict() for q in self.questions],
        }


def slug_part(value: str | None, fallback: str = "unknown") -> str:
    if not value:
        return fallback
    s = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return s or fallback


def make_paper_id(
    bank: str | None,
    role: str | None,
    year: int | None,
    exam_type: str | None,
    shift: str | None,
    sha256: str | None,
) -> str:
    sha8 = (sha256 or "nosha")[:8]
    return "_".join(
        [
            slug_part(bank),
            slug_part(role),
            str(year) if year is not None else "noyear",
            slug_part(exam_type),
            slug_part(shift, "unknown_shift"),
            sha8,
        ]
    )


def make_q_id(paper_id: str, q_num: int) -> str:
    return f"{paper_id}::q{q_num:03d}"


def make_direction_id(seq: int) -> str:
    return f"d{seq:03d}"


def detect_section(text: str) -> str | None:
    for label, pat in SECTION_HEADERS:
        if pat.search(text):
            return label
    return None

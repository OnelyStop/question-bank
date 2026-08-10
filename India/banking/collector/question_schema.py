"""JSON schemas / builders for the bank-exam question bank."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


SECTION_HEADERS: list[tuple[str, re.Pattern[str]]] = [
    ("Reasoning", re.compile(r"\bREASONING(?:\s+ABILITY)?\b", re.I)),
    ("Quantitative", re.compile(r"\bQUANTITATIVE(?:\s+APTITUDE)?\b|\bNUMERICAL\s+ABILITY\b|\bQUANT\b", re.I)),
    ("English", re.compile(r"\bENGLISH(?:\s+LANGUAGE)?\b", re.I)),
    ("GA", re.compile(r"\bGENERAL\s+AWARENESS\b|\bGA\b|\bBANKING\s+AWARENESS\b|\bCURRENT\s+AFFAIRS\b", re.I)),
    ("Computer", re.compile(r"\bCOMPUTER(?:\s+APTITUDE|\s+KNOWLEDGE)?\b", re.I)),
]


@dataclass
class QuestionMetrics:
    has_passage: bool
    option_count: int
    stem_char_len: int
    page_start: int | None = None
    page_end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Question:
    q_id: str
    q_num: int
    section: str | None
    topic: str | None
    topic_confidence: float | None
    topic_source: str | None
    direction_id: str | None
    direction_text: str | None
    stem: str
    options: dict[str, str]
    answer: str | None
    explanation: str | None
    metrics: QuestionMetrics

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_index_row(self, paper: "Paper") -> dict[str, Any]:
        """Flat row for index.jsonl (filter-friendly)."""
        return {
            "q_id": self.q_id,
            "paper_id": paper.paper_id,
            "bank": paper.bank,
            "role": paper.role,
            "exam_type": paper.exam_type,
            "year": paper.year,
            "shift": paper.shift,
            "memory_based": paper.memory_based,
            "language": paper.language,
            "q_num": self.q_num,
            "section": self.section,
            "topic": self.topic,
            "direction_id": self.direction_id,
            "has_passage": self.metrics.has_passage,
            "option_count": self.metrics.option_count,
            "stem": self.stem,
            "options": self.options,
            "answer": self.answer,
            "pdf_path": paper.source.get("pdf_path"),
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

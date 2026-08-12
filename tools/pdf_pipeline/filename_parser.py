"""Parse bank exam PDF filenames into corpus path segments."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

YEAR_RE = re.compile(r"\b(20(?:1[0-9]|2[0-9]))\b")
SHIFT_RE = re.compile(
    r"(?:shift|sft)\s*([1-4])|(?:(1st|2nd|3rd|4th)\s*shift)",
    re.IGNORECASE,
)
ORDINAL_SHIFT = {"1st": "1", "2nd": "2", "3rd": "3", "4th": "4"}

BANK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("NABARD", re.compile(r"\bnabard\b", re.I)),
    ("SIDBI", re.compile(r"\bsidbi\b", re.I)),
    ("IBPS", re.compile(r"\bibps\b", re.I)),
    ("SBI", re.compile(r"\bsbi\b", re.I)),
    ("RBI", re.compile(r"\brbi\b", re.I)),
]

ROLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Grade_B", re.compile(r"\bgrade[\s._-]*b\b", re.I)),
    ("Assistant", re.compile(r"\bassistant\b", re.I)),
    ("RRB", re.compile(r"\brrb\b", re.I)),
    ("Clerk", re.compile(r"\bclerk\b", re.I)),
    ("SO", re.compile(r"\b(?:so|specialist)\b", re.I)),
    ("PO", re.compile(r"\b(?:po|probationary)\b", re.I)),
]

STAGE_PRELIMS = re.compile(r"\b(?:prelims?|pre)\b", re.I)
STAGE_MAINS = re.compile(r"\b(?:mains?|main)\b", re.I)
MEMORY_RE = re.compile(r"\bmemory[\s._-]*based\b|\bmemory\b", re.I)
LANG_EN = re.compile(r"\b(?:english|eng|en)\b", re.I)
LANG_HI = re.compile(r"\b(?:hindi|hin|hi)\b", re.I)

WINDOWS_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class ParsedName:
    year: str | None
    bank: str | None
    role: str | None
    stage: str | None
    shift: str | None
    memory_based: bool
    language: str | None
    skip_reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_for_match(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"[\s._\-]+", " ", stem).strip()


def parse_filename(filename: str, extra_text: str = "") -> ParsedName:
    """Extract year/bank/role/stage/shift from a PDF filename (+ optional URL/title)."""
    combined = f"{filename} {extra_text}".strip()
    text = _normalize_for_match(combined)
    lower = text.lower()

    year_match = YEAR_RE.search(text)
    if not year_match:
        # Also accept years glued like 2024Shift
        loose = re.search(r"(20(?:1[0-9]|2[0-9]))", text)
        if not loose:
            # Keep yearless papers — route to _unsorted/no_year later
            year = None
        else:
            year = loose.group(1)
    else:
        year = year_match.group(1)

    bank: str | None = None
    for label, pat in BANK_PATTERNS:
        if pat.search(lower):
            bank = label
            break

    role: str | None = None
    # IBPS + RRB → ROLE=RRB (plan rule)
    if bank == "IBPS" and re.search(r"\brrb\b", lower):
        role = "RRB"
    else:
        for label, pat in ROLE_PATTERNS:
            if pat.search(lower):
                role = label
                break

    stage: str | None = None
    if STAGE_PRELIMS.search(lower):
        stage = "Prelims"
    elif STAGE_MAINS.search(lower):
        stage = "Mains"

    shift: str | None = None
    sm = SHIFT_RE.search(lower)
    if sm:
        num = sm.group(1) or ORDINAL_SHIFT.get((sm.group(2) or "").lower())
        if num:
            shift = f"Shift_{num}"

    language: str | None = None
    if LANG_HI.search(lower):
        language = "hindi"
    elif LANG_EN.search(lower):
        language = "english"

    return ParsedName(
        year=year,
        bank=bank,
        role=role,
        stage=stage,
        shift=shift,
        memory_based=bool(MEMORY_RE.search(lower)),
        language=language,
        skip_reason=None,
    )


def sanitize_filename(filename: str) -> str:
    name = WINDOWS_BAD.sub("_", filename).strip(" .")
    return name or "unnamed.pdf"


def build_corpus_path(corpus_root: Path, parsed: ParsedName, filename: str) -> Path | None:
    """
    Return destination path for the PDF, or None if the file should be skipped.
    Yearless files go under _unsorted/no_year (or bank tree with no_year).
    """
    if parsed.skip_reason:
        return None

    safe_name = sanitize_filename(filename)
    year = parsed.year or "no_year"

    if not parsed.bank:
        return corpus_root / "_unsorted" / year / safe_name

    role = parsed.role or "_unknown_role"
    stage = parsed.stage or "_unknown_stage"
    shift = parsed.shift or "_unknown_shift"
    return (
        corpus_root
        / parsed.bank
        / role
        / year
        / stage
        / shift
        / safe_name
    )


def write_sidecar(pdf_path: Path, parsed: ParsedName, extra: dict | None = None) -> None:
    """Write optional metadata JSON next to the PDF."""
    data = parsed.to_dict()
    if extra:
        data.update(extra)
    sidecar = pdf_path.with_suffix(pdf_path.suffix + ".meta.json")
    sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")

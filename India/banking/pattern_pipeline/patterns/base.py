"""Shared helpers for pattern classifier skills."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # avoids a runtime dependency from patterns/ onto checks/
    from checks.base import Defect


NON_LATIN = re.compile(
    r"[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0600-\u06FF\u4E00-\u9FFF]"
)


@dataclass
class MatchResult:
    matched: bool
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


def combined_text(question: dict[str, Any]) -> str:
    dt = question.get("direction_text") or ""
    stem = question.get("stem") or ""
    return f"{dt}\n{stem}".strip()


def direction_text(question: dict[str, Any]) -> str:
    return (question.get("direction_text") or "").strip()


def stem_text(question: dict[str, Any]) -> str:
    return (question.get("stem") or "").strip()


def normalize_options(options: Any) -> dict[str, str]:
    """Raw `options` -> the exact dict the uniform row will carry.

    Single source of truth: `extract.py` writes this onto the row and
    `option_count()` counts it, so a skill can never gate on a different number
    from the one that ships.
    """
    if not isinstance(options, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("a", "b", "c", "d", "e"):
        if options.get(key) is not None:
            out[key] = str(options[key])
    for key in ("A", "B", "C", "D", "E"):  # also accept uppercase keys
        low = key.lower()
        if low not in out and options.get(key) is not None:
            out[low] = str(options[key])
    return out


def option_count(question: dict[str, Any]) -> int:
    """How many options this question really has.

    Counts the normalized dict -- the exact options the uniform row will carry --
    and deliberately ignores `metrics.option_count`. That metric is the upstream
    parser's claim about the PDF, and it disagrees with reality: 115 rows claim 5
    while the dict is empty, which let them slip past the `< 4` guard in
    `partial_or_missing_options` and land in `shared_directions_set` /
    `standalone_mcq` as if they were complete.

    Every caller that gates on option count (`partial_or_missing_options`,
    `shared_directions_set`, `standalone_mcq`, and the fallbacks in
    `classify.py`) routes through here, so fixing it once fixes all of them.
    """
    return len(normalize_options(question.get("options")))


def has_shared_directions(question: dict[str, Any]) -> bool:
    metrics = question.get("metrics") or {}
    if "has_passage" in metrics:
        return bool(metrics["has_passage"])
    return bool(direction_text(question) or question.get("direction_id"))


def is_bilingual_text(text: str) -> bool:
    if not text:
        return False
    return bool(NON_LATIN.search(text)) and bool(re.search(r"[A-Za-z]{3,}", text))


def image_blocks(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Image refs carried by the question, if any.

    NOTE: papers under `India/banking/papers/` carry no `context[]` at all (see
    `papers/SCHEMA.md`) -- only the newer `tools/pdf_pipeline/` emits it. Against
    the current corpus this returns [] for every question, which is why
    `chart_missing` fires on all figure-pattern rows. Kept as-is so the pipeline
    starts attaching refs for free once papers are rebuilt.
    """
    refs: list[dict[str, Any]] = []
    for block in question.get("context") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "image" or block.get("role") in {"figure", "chart", "diagram"}:
            refs.append(block)
    return refs


class PatternSkill:
    """Base class for one question-pattern skill."""

    id: str = ""
    name: str = ""
    priority: int = 100  # lower = earlier

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        raise NotImplementedError

    def extract_fields(self, question: dict[str, Any], match: MatchResult) -> dict[str, Any]:
        """Optional pattern-specific fields merged into uniform row."""
        return {}

    def validate(self, row: dict[str, Any]) -> Iterable["Defect"]:
        """What 'complete' means for THIS pattern. Default: nothing to say.

        The classifier has already decided the row is, say, a table DI set --
        so this skill is the right place to know that a table DI set without a
        table is not serveable. Cross-pattern rules live in `checks/` instead.
        """
        return ()

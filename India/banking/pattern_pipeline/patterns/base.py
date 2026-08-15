"""Shared helpers for pattern classifier skills."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


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


def option_count(question: dict[str, Any]) -> int:
    metrics = question.get("metrics") or {}
    if "option_count" in metrics:
        return int(metrics["option_count"] or 0)
    return len(question.get("options") or {})


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

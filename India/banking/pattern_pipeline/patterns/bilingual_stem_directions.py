from __future__ import annotations

from typing import Any

from .base import MatchResult, PatternSkill, combined_text, is_bilingual_text


class BilingualStemDirectionsSkill(PatternSkill):
    """Secondary pattern — stored in secondary_patterns + is_bilingual flag."""

    id = "bilingual_stem_directions"
    name = "Bilingual stem / directions"
    priority = 5

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        if is_bilingual_text(text):
            return MatchResult(matched=True, confidence=0.95, signals=["non-Latin + English text"])
        return MatchResult(matched=False)

    def extract_fields(self, question: dict[str, Any], match: MatchResult) -> dict[str, Any]:
        return {"is_bilingual": True}

from __future__ import annotations

from typing import Any

from .base import MatchResult, PatternSkill, has_shared_directions, option_count


class StandaloneMcqSkill(PatternSkill):
    id = "standalone_mcq"
    name = "Standalone MCQ"
    priority = 190

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        if has_shared_directions(question):
            return MatchResult(matched=False)
        if option_count(question) < 4:
            return MatchResult(matched=False)
        return MatchResult(
            matched=True,
            confidence=0.7,
            signals=["no shared directions", "option_count>=4", "fallback standalone MCQ"],
        )

from __future__ import annotations

from typing import Any

from .base import MatchResult, PatternSkill, has_shared_directions, option_count


class SharedDirectionsSetSkill(PatternSkill):
    id = "shared_directions_set"
    name = "Shared-directions / set-based MCQ"
    priority = 180

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        if not has_shared_directions(question):
            return MatchResult(matched=False)
        if option_count(question) < 4:
            return MatchResult(matched=False)
        return MatchResult(
            matched=True,
            confidence=0.7,
            signals=["has direction_text/direction_id", "fallback shared-directions set"],
        )

from __future__ import annotations

from typing import Any

from .base import MatchResult, PatternSkill, has_shared_directions, option_count


class PartialOrMissingOptionsSkill(PatternSkill):
    id = "partial_or_missing_options"
    name = "Partial / missing options"
    priority = 10

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        oc = option_count(question)
        if oc < 4:
            return MatchResult(
                matched=True,
                confidence=0.95,
                signals=[f"option_count={oc}"],
            )
        return MatchResult(matched=False)

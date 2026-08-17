from __future__ import annotations

from typing import Any, Iterable

from checks.base import Defect

from .base import MatchResult, PatternSkill, option_count


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

    def validate(self, row: dict[str, Any]) -> Iterable[Defect]:
        # This pattern IS the defect -- a question classified here is by
        # definition missing options. Say so once, here, rather than leaving it
        # to a generic check to rediscover.
        count = len(row.get("options") or {})
        yield Defect(reason="option_partial", tier="blocking",
                     detail=f"only {count} options parsed")

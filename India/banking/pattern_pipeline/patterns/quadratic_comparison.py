from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text


QUAD_RX = re.compile(
    r"(?i)("
    r"two\s+equations?|"
    r"quadratic\s+equations?|"
    r"equations?\s*\(\s*I\s*\)\s*and\s*\(\s*II\s*\)|"
    r"solve\s+(both|the\s+given)\s+(the\s+)?equations?"
    r")"
)


class QuadraticComparisonSkill(PatternSkill):
    id = "quadratic_comparison"
    name = "Quadratic / two-equation comparison"
    priority = 90

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = QUAD_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.88, signals=[f"quadratic cue: {m.group(0)[:60]}"])

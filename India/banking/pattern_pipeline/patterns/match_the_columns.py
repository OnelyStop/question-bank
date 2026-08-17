from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text


# A bare `Column I` is NOT enough: it is an ordinary DI table header, and matched
# 67 of the 89 rows this skill claimed. Require either an explicit instruction to
# match, or both columns named -- which is what a real match-the-columns item has.
MATCH_RX = re.compile(
    r"(?i)("
    r"match\s+the\s+(following|column|list)|"
    r"column\s*(?:I|1)\b.{0,200}?column\s*(?:II|2)\b|"
    r"list\s*(?:I|1)\b.{0,200}?list\s*(?:II|2)\b"
    r")",
    re.S,
)


class MatchTheColumnsSkill(PatternSkill):
    id = "match_the_columns"
    name = "Match the columns / lists"
    priority = 100

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = MATCH_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.9, signals=[f"match columns cue: {m.group(0)[:60]}"])

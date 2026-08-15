from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text


MATCH_RX = re.compile(
    r"(?i)("
    r"match\s+the\s+(following|column|list)|"
    r"column\s*[iI1]\b|"
    r"column\s*[iI1].{0,40}column\s*[iI2]"
    r")"
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

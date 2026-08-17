from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text


DS_RX = re.compile(
    r"(?i)("
    r"data\s+sufficiency|"
    r"question\s+and\s+(two|three)\s+statements|"
    r"statements?\s+numbered\s+I|"
    r"accompanied\s+by\s+(two|three)\s+statements|"
    r"which\s+of\s+the\s+(following\s+)?statements?\s*(is|are)\s*(/are)?\s*sufficient|"
    r"the\s+data\s+in\s+statement"
    r")"
)


class DataSufficiencySkill(PatternSkill):
    id = "data_sufficiency"
    name = "Data sufficiency"
    priority = 70

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = DS_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.9, signals=[f"DS cue: {m.group(0)[:60]}"])

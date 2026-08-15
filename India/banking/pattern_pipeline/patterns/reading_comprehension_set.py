from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text, direction_text


RC_RX = re.compile(
    r"(?i)("
    r"read\s+the\s+(following\s+|given\s+)?passage|"
    r"passage\s+(carefully\s+)?and\s+answer|"
    r"according\s+to\s+the\s+passage|"
    r"based\s+on\s+the\s+(given\s+)?passage|"
    r"with\s+reference\s+to\s+the\s+passage"
    r")"
)


class ReadingComprehensionSetSkill(PatternSkill):
    id = "reading_comprehension_set"
    name = "Reading comprehension (passage) set"
    priority = 60

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        dt = direction_text(question)
        text = combined_text(question)
        m = RC_RX.search(dt[:300] if dt else text[:300])
        if not m:
            return MatchResult(matched=False)
        # Avoid classifying short instruction-only blocks as RC
        if dt and len(dt) < 120 and "passage" not in dt.lower():
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.9, signals=[f"RC cue: {m.group(0)[:60]}"])

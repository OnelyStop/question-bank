from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text


TABLE_RX = re.compile(
    r"(?i)("
    r"following\s+table|table\s+(given|shows|carefully|below)|"
    r"tabulat|read\s+the\s+following\s+table|given\s+table\s+shows"
    r")"
)


class TableDiSetSkill(PatternSkill):
    id = "table_di_set"
    name = "Table DI set"
    priority = 40

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = TABLE_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.9, signals=[f"table DI cue: {m.group(0)[:60]}"])

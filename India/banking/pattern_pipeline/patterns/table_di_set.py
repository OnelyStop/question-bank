from __future__ import annotations

import re
from typing import Any, Iterable

from checks.base import Defect

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

    def validate(self, row: dict[str, Any]) -> Iterable[Defect]:
        direction = (row.get("direction_text") or "").strip()
        if not direction:
            yield Defect(reason="context_missing", tier="blocking",
                         detail="table DI question with no table")
        elif len(re.findall(r"\d", direction)) < 5:
            yield Defect(reason="context_unusable", tier="blocking",
                         detail="table announced but its numbers were only in the image")

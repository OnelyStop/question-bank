from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text


QTY_RX = re.compile(
    r"(?i)("
    r"quantity\s*[iI1]\b.{0,120}quantity\s*[iI2]\b|"
    r"two\s+quantities|"
    r"compare\s+the\s+(two\s+)?quantit"
    r")"
)


class QuantityComparisonSkill(PatternSkill):
    id = "quantity_comparison"
    name = "Quantity comparison"
    priority = 80

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = QTY_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.9, signals=[f"quantity cue: {m.group(0)[:60]}"])

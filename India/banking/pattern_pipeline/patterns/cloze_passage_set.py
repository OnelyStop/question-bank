from __future__ import annotations

import re
from typing import Any, Iterable

from checks.base import Defect

from .base import MatchResult, PatternSkill, combined_text, direction_text


CLOZE_RX = re.compile(
    r"(?i)("
    r"following\s+passage\s+there\s+are\s+blanks|"
    r"blanks?.{0,40}(numbered|denoted)|"
    r"fill\s+in\s+the\s+blanks?\s+in\s+the\s+following\s+passage|"
    r"select\s+the\s+word\s+that\s+fits\s+blank|"
    r"fits?\s+blank\s*\(\s*\d+\s*\)|"
    r"clo[sz]e\s+test"
    r")"
)


class ClozePassageSetSkill(PatternSkill):
    id = "cloze_passage_set"
    name = "Cloze / fill-in-the-blank passage"
    priority = 50

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = CLOZE_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        # Prefer true shared passage cloze over single-sentence blanks
        if not direction_text(question) and "blank" in (question.get("stem") or "").lower():
            return MatchResult(matched=False)
        return MatchResult(matched=True, confidence=0.92, signals=[f"cloze cue: {m.group(0)[:60]}"])

    def validate(self, row: dict[str, Any]) -> Iterable[Defect]:
        # The stem is usually synthetic ("Select the word that fits blank (79)."),
        # so the passage in direction_text is the entire question.
        if not (row.get("direction_text") or "").strip():
            yield Defect(reason="context_missing", tier="blocking",
                         detail="cloze blank with no passage to fill it in")

from __future__ import annotations

import re
from typing import Any, Iterable

from checks.base import Defect

from .base import MatchResult, PatternSkill, direction_text, has_shared_directions


CASELET_RX = re.compile(
    r"(?i)("
    r"answer\s+the\s+questions?\s+based\s+on\s+the\s+information|"
    r"caselet|"
    r"based\s+on\s+the\s+information\s+given\s+below|"
    r"read\s+the\s+(given\s+)?data\s+carefully|"
    r"following\s+information\s+(carefully\s+)?and\s+answer"
    r")"
)

NUMERIC_RX = re.compile(
    r"(?i)("
    r"%|\bpercent\b|\brs\.?\b|\brupees?\b|\blitres?\b|\bliters?\b|"
    r"\bpopulation\b|\bstudents?\b|\bsold\b|\bbought\b|\bratio\b|\baverage\b|"
    r"\bprofit\b|\bloss\b|\bincome\b|\bexpense\b|\bkm\b|\bmetres?\b|\bmeters?\b|"
    r"\bcrore\b|\blakh\b|\bmillion\b"
    r")"
)

# Word-only numeric cues, for deciding whether a caselet's *figures* are missing.
# Deliberately excludes punctuation like `%` and `Rs` symbols -- see validate().
NUMERIC_WORDS = re.compile(
    r"(?i)\b("
    r"rs\.?|rupees?|percent|per\s+cent|total|average|ratio|sold|bought|"
    r"income|expenditure|profit|loss|population|students?|litres?|liters?|"
    r"crore|lakh|million|thousand"
    r")\b"
)

PUZZLE_RX = re.compile(
    r"(?i)(sits?|sitting|circular|row\s+facing|floors?|boxes?|months?|days?|scheduled|lives\s+on|who\s+among)"
)


class CaseletDiSetSkill(PatternSkill):
    id = "caselet_di_set"
    name = "Caselet DI set"
    priority = 110

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        if not has_shared_directions(question):
            return MatchResult(matched=False)
        dt = direction_text(question)
        if not dt or len(dt) < 80:
            return MatchResult(matched=False)
        # Prefer quantitative caselets; skip obvious puzzle sets
        if PUZZLE_RX.search(dt):
            return MatchResult(matched=False)
        if CASELET_RX.search(dt[:350]) and NUMERIC_RX.search(dt):
            return MatchResult(matched=True, confidence=0.82, signals=["caselet DI + numeric cues"])
        # Numeric paragraph without chart/table words
        if NUMERIC_RX.search(dt) and not re.search(r"(?i)\b(table|pie|bar\s+graph|line\s+graph)\b", dt):
            # Require instruction-like opener or dense numbers
            if CASELET_RX.search(dt[:350]) or len(re.findall(r"\d+", dt)) >= 6:
                return MatchResult(matched=True, confidence=0.75, signals=["numeric paragraph caselet"])
        return MatchResult(matched=False)

    def validate(self, row: dict[str, Any]) -> Iterable[Defect]:
        # A *numeric* caselet is answerable only if its figures are in the prose.
        #
        # Gated on NUMERIC_WORDS, not NUMERIC_RX: the latter counts a bare `%` as
        # a numeric cue, and `%` is a defined operator in symbol-notation
        # reasoning ("A%B means A is the child of B") and a code glyph in
        # coding-decoding sets. Both carry their whole premise in the text and
        # are perfectly answerable; gating on `%` quarantines 98 of them.
        direction = (row.get("direction_text") or "").strip()
        if not direction or not NUMERIC_WORDS.search(direction):
            return
        if len(re.findall(r"\d", direction)) < 5:
            yield Defect(reason="context_unusable", tier="blocking",
                         detail="numeric caselet whose figures did not survive extraction")

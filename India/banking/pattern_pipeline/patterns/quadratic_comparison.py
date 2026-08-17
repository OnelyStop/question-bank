from __future__ import annotations

import re
from typing import Any, Iterable

from checks.base import Defect

from .base import MatchResult, PatternSkill, combined_text


# A cue that this is the two-equations-compare-x-and-y format.
# `two equations` on its own is NOT enough: 206 of 250 rows it matched contained
# no equation at all -- it fires on caselet prose like "two equations of the same
# line". An equation must actually be present, so CUE and EQUATION both have to hit.
QUAD_RX = re.compile(
    r"(?i)("
    r"quadratic\s+equations?|"
    r"two\s+equations?|"
    r"equations?\s*\(?\s*I\s*\)?\s*and\s*\(?\s*II\s*\)?|"
    r"solve\s+(both|the\s+given)\s+(the\s+)?equations?"
    r")"
)

# Something equation-shaped: a squared term, or an `= 0` / `= number` right-hand side.
EQUATION_RX = re.compile(
    r"(x|y)\s*(\^?\s*2|²|\*\*\s*2)"      # x², y^2, y**2
    r"|[a-z0-9)\s]=\s*-?\d"               # ... = 0
    r"|\b[IV]+\.\s*\d*\s*[xy]\b",         # "I. 7x - 54x + 99 = 0"
    re.I,
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
        eq = EQUATION_RX.search(text)
        if not eq:
            # Says "two equations" but shows none -- not this pattern.
            return MatchResult(matched=False)
        return MatchResult(
            matched=True,
            confidence=0.88,
            signals=[f"quadratic cue: {m.group(0)[:60]}", f"equation: {eq.group(0)[:30]}"],
        )

    def validate(self, row: dict[str, Any]) -> Iterable[Defect]:
        text = f"{row.get('direction_text') or ''}\n{row.get('stem') or ''}"
        if not EQUATION_RX.search(text):
            yield Defect(reason="equation_degraded", tier="blocking",
                         detail="two-equation question whose equations did not survive extraction")

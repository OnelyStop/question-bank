from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, option_values, stem_of

# A stacked fraction or a decimal point that collapsed into loose digits:
# `30 10/13 %` arrived as `30 10 13 %`, and `25.7%` as `25 7 %`.
# The trailing % is what makes this safe to assert — bare "25 7" is too common
# in prose ("25 7-day periods") to flag on its own.
SPLIT_PERCENT = re.compile(r"\b\d+\s+\d+(?:\s+\d+)?\s*%")

# Same damage inside a currency amount: `Rs 21 083` for `Rs 21,083`.
SPLIT_CURRENCY = re.compile(r"(?i)\brs\.?\s*\d{1,3}(?:\s+\d{3})+\b")


class FractionFlattenedCheck(CheckSkill):
    """A stacked fraction or decimal collapsed into loose digits."""

    id = "fraction_flattened"
    name = "Fraction / decimal flattened"
    tier = "suspect"
    reason = "fraction_flattened"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        for where, text in [("stem", stem_of(row))] + [
            ("option", v) for v in option_values(row)
        ]:
            m = SPLIT_PERCENT.search(text) or SPLIT_CURRENCY.search(text)
            if m:
                yield self.defect(f"{where}: {m.group(0)!r} lost its separator")
                return

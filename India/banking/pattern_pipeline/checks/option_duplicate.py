from __future__ import annotations

from typing import Any, Iterable

from .base import CheckSkill, Defect, norm, option_values


class OptionDuplicateCheck(CheckSkill):
    """Two options identical once whitespace is normalised.

    Usually a parse artifact rather than a real exam question — the source had
    `25.7%` and `28.7%` and the decimal points were lost, collapsing them.
    """

    id = "option_duplicate"
    name = "Duplicate option text"
    tier = "blocking"
    reason = "option_duplicate"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        vals = [norm(v) for v in option_values(row)]
        vals = [v for v in vals if v]
        if len(vals) != len(set(vals)):
            dupes = {v for v in vals if vals.count(v) > 1}
            yield self.defect(f"repeated: {sorted(dupes)[:3]}")

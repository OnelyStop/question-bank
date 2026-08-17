from __future__ import annotations

from typing import Any, Iterable

from .base import CheckSkill, Defect, options_of


class OptionEmptyCheck(CheckSkill):
    """An option that cleaned away to nothing, or to pure punctuation."""

    id = "option_empty"
    name = "Empty option text"
    tier = "blocking"
    reason = "option_empty"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        for key, val in sorted(options_of(row).items()):
            if not isinstance(val, str):
                continue
            if not val.strip():
                yield self.defect(f"option ({key}) is blank")
            elif not any(ch.isalnum() for ch in val):
                yield self.defect(f"option ({key}) has no alphanumeric content: {val[:30]!r}")

from __future__ import annotations

from typing import Any, Iterable

from .base import CheckSkill, Defect, options_of


class OptionPartialCheck(CheckSkill):
    """Fewer than four options, or a gap in the a-e run.

    The gap case is the dangerous one: keys `(a, b, d, e)` mean one option was
    dropped during parsing, so every answer key on that row is off by one once
    answers get attached.
    """

    id = "option_partial"
    name = "Partial / missing options"
    tier = "blocking"
    reason = "option_partial"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        opts = options_of(row)
        if len(opts) < 4:
            yield self.defect(f"only {len(opts)} options")
            return
        expected = set("abcde"[: len(opts)])
        if set(opts) != expected:
            yield self.defect(f"keys {''.join(sorted(opts))} are not a run from 'a'")

from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, option_values, stem_of

# A full (a)...(b)...(c) run still sitting inside one field means the option
# splitter never fired for this question.
#
# Case-sensitive on purpose. Only lowercase (a) marks an MCQ option; uppercase
# (A) labels a stimulus or rearrangement fragment and is legitimate inside a
# stem. Adding re.I here flags 1,387 rows instead of 300, nearly all of them
# ordinary para-jumble questions.
INLINE_RUN = re.compile(r"\(\s*a\s*\).{1,200}\(\s*b\s*\).{1,200}\(\s*c\s*\)", re.S)

# The next question welded onto the end of an option.
NEXT_Q = re.compile(r"\n\s*\d{1,3}\s*\.\s+\S")

# An option that swallowed a paragraph of solution working.
TOO_LONG = 400


class OptionBleedCheck(CheckSkill):
    """The next question, or a block of prose, is still welded to the stem or an option."""

    id = "option_bleed"
    name = "Option bleed"
    tier = "blocking"
    reason = "option_bleed"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        stem = stem_of(row)
        if INLINE_RUN.search(stem):
            yield self.defect(f"options still inline in stem: {stem[:80]!r}")
        for val in option_values(row):
            if NEXT_Q.search(val):
                yield self.defect(f"next question welded to an option: {val[-60:]!r}")
                break
        long_opts = [v for v in option_values(row) if len(v) > TOO_LONG]
        if long_opts:
            yield Defect(
                reason=self.reason,
                tier="suspect",
                detail=f"option of {len(long_opts[0])} chars — likely swallowed prose",
            )

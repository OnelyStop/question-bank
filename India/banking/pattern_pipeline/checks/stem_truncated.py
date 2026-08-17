from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, stem_of

# Ends on a lowercase letter, comma, semicolon or an open bracket — the sentence
# was still going when the block boundary cut it.
UNTERMINATED = re.compile(r"[a-z,;(]\s*$")

# Starts mid-word: the opening of the stem was eaten by the previous block.
HEAD_LOST = re.compile(r"^\s*[a-z]{2,}\b")


class StemTruncatedCheck(CheckSkill):
    """The stem stops (or starts) mid-sentence."""

    id = "stem_truncated"
    name = "Stem truncated"
    tier = "suspect"
    reason = "stem_truncated"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        stem = stem_of(row).strip()
        if not stem:
            return  # stem_too_short owns this
        if UNTERMINATED.search(stem):
            yield self.defect(f"ends mid-clause: ...{stem[-50:]!r}")
        elif HEAD_LOST.match(stem) and len(stem) > 20:
            yield self.defect(f"starts mid-word: {stem[:50]!r}...")

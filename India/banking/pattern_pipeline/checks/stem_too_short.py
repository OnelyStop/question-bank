from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, stem_of

# `36.` / `Q36.` / `Question 131.` — the parser found the anchor but no text.
# These come from stems printed as vector glyphs, which extract as nothing.
PLACEHOLDER = re.compile(r"^\s*(q(uestion)?\s*)?\d{1,3}\s*[.)]?\s*$", re.I)

MIN_CHARS = 12


class StemTooShortCheck(CheckSkill):
    """Nothing survived that reads as a question."""

    id = "stem_too_short"
    name = "Stem empty or too short"
    tier = "blocking"
    reason = "stem_too_short"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        stem = stem_of(row).strip()
        if not stem:
            yield self.defect("stem is empty")
        elif PLACEHOLDER.match(stem):
            yield self.defect(f"stem is a bare question number: {stem[:40]!r}")
        elif len(stem) < MIN_CHARS:
            # Short but real happens in quant ("? = 73 + 33"), so this is suspect,
            # not blocking — a human decides.
            yield Defect(reason=self.reason, tier="suspect",
                         detail=f"{len(stem)} chars: {stem[:40]!r}")

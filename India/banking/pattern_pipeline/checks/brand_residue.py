"""Coaching-brand / URL / promo residue.

Regexes lifted from `tools/verify.py`, which already uses them to keep the
`sets/` lane clean. Two notes carried over from there, both load-bearing:

- `\\b` matters on the book titles: "Facebook" contains "ebook", and one book's
  questions are genuinely about Facebook user counts.
- Platform names alone are legitimate question content; only the call-to-action
  phrasing is a leak.

Its "broken font mapping" class is deliberately NOT copied — that range matches
genuine Bengali, which is language, not damage. See `language_script.py`.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, all_text

LEAKS = {
    "coaching brand": re.compile(
        r"adda\s?247|bankersadda|sscadda|careerpower|ibps\s?guide|oliveboard"
        r"|testbook|gradeup|smartkeeda|practicemock", re.I),
    "url or email": re.compile(
        r"www\.|https?://|\b[a-z0-9-]+\.(?:com|in|org|net)\b|\S+@\S+\.\w+", re.I),
    "source book title": re.compile(
        r"200 Questions of Quant|Complete Pack of Banking|Ace (?:English|reasoning|quant)"
        r"|3rd edition|Maha Pack|\bCRACKER\b|\beBooks?\b", re.I),
    "promo": re.compile(
        r"mail us at|whatsapp\s*@?\s*\d|telegram\s+channel|click\s+here"
        r"|subscribe\s+(?:our|to)|download\s+\w*\s*app\b|follow\s+(?:us|\d*\s*\w+\s+sir)"
        r"|mock test series|facebook\s+page", re.I),
    "section label": re.compile(r"\b(?:Answers|Solutions)\s*:", re.I),
}


class BrandResidueCheck(CheckSkill):
    """A coaching brand, URL, book title or promo survived cleaning."""

    id = "brand_residue"
    name = "Brand / promo residue"
    tier = "suspect"
    reason = "brand_residue"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        text = all_text(row)
        for label, rx in LEAKS.items():
            m = rx.search(text)
            if m:
                yield self.defect(f"{label}: {m.group(0)[:40]!r}")
                return

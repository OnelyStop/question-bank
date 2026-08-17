from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, all_text

# Indic scripts that legitimately appear in these papers. These are LANGUAGE,
# not damage — `tools/verify.py` lumps Bengali in with its "broken font mapping"
# class, which mislabels 247 genuine Bengali rows. Kept separate here.
SCRIPTS = {
    "hindi": re.compile(r"[ऀ-ॿ]"),
    "bengali": re.compile(r"[ঀ-৿]"),
    "gujarati": re.compile(r"[઀-૿]"),
    "tamil": re.compile(r"[஀-௿]"),
    "telugu": re.compile(r"[ఀ-౿]"),
    "kannada": re.compile(r"[ಀ-೿]"),
    "malayalam": re.compile(r"[ഀ-ൿ]"),
}

# Enough Latin to carry a question on its own.
ENGLISH_HALF = re.compile(r"[A-Za-z]{3,}(?:\s+[A-Za-z]{3,}){2,}")


class LanguageScriptCheck(CheckSkill):
    """Non-Latin script present: either a language the row does not declare, or
    a question asked *only* in that language.

    A bilingual question keeps its English half and is fine to serve, so it is
    reported at `info`. One with no English half cannot be served from this
    English-only bank, so it blocks — the same rule `sets/` applies.
    """

    id = "language_script"
    name = "Script / language disagreement"
    tier = "blocking"
    reason = "language_only_non_english"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        text = all_text(row)
        found = [name for name, rx in SCRIPTS.items() if rx.search(text)]
        if not found:
            return
        label = ",".join(found)
        if not ENGLISH_HALF.search(text):
            yield Defect(reason=f"language_{found[0]}", tier="blocking",
                         detail=f"asked only in {label}")
            return
        # Bilingual and serveable — but the metadata should say so.
        declared = (row.get("language") or "").lower()
        if declared in ("english", "en", ""):
            yield Defect(reason="language_metadata_wrong", tier="info",
                         detail=f"contains {label} but language={declared!r}")
        if not row.get("is_bilingual"):
            yield Defect(reason="bilingual_flag_missing", tier="info",
                         detail=f"contains {label} but is_bilingual=false")

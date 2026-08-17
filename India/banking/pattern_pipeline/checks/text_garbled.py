from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, all_text

# Private use area (U+E000-U+F8FF): Wingdings/Symbol arrows that survived a broken
# font mapping. "Village  A B C Year " is a real table header from this corpus.
# Deliberately NOT the Indic script ranges -- those are language, see language_script.py.
# Escapes, not literals: these characters do not survive being pasted around.
PRIVATE_USE = re.compile("[-]")

# The unicode replacement char, and runs of the box glyph the PDFs fall back to
# for a character the font could not map.
REPLACEMENT = re.compile("�|[▫□]{3,}")

# Control characters that should never survive text extraction.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class TextGarbledCheck(CheckSkill):
    """Characters survive from a broken font mapping."""

    id = "text_garbled"
    name = "Text garbled"
    tier = "blocking"
    reason = "text_garbled"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        text = all_text(row)
        for label, rx in (("private-use glyph", PRIVATE_USE),
                          ("replacement char", REPLACEMENT),
                          ("control char", CONTROL)):
            m = rx.search(text)
            if m:
                yield self.defect(f"{label} at offset {m.start()}: {m.group(0)!r}")
                return

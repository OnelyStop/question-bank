"""Strip Devanagari (and other non-Latin) translations appended to English text."""

from __future__ import annotations

import re
from typing import Any

# Devanagari block (Hindi) — primary case in this corpus
DEVANAGARI = re.compile(r"[\u0900-\u097F]+")
# Other scripts sometimes mixed in (Tamil etc.)
NON_LATIN = re.compile(
    r"[\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0600-\u06FF]"
)
HAS_ENGLISH = re.compile(r"[A-Za-z]{3,}")


def is_bilingual(text: str | None) -> bool:
    if not text:
        return False
    return bool(NON_LATIN.search(text)) and bool(HAS_ENGLISH.search(text))


def strip_non_latin(text: str | None) -> tuple[str, bool]:
    """
    Return (cleaned_text, changed).

    Strategy: drop runs of non-Latin script and tidy leftover whitespace / separators.
    Keeps Latin letters, digits, and common punctuation used in stems/options.
    """
    if not text:
        return text or "", False
    if not NON_LATIN.search(text):
        return text, False

    cleaned = NON_LATIN.sub(" ", text)
    # Collapse whitespace and orphaned separators left by stripping
    cleaned = re.sub(r"[ \t\f\v]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r" ?/ ?", "/", cleaned)
    cleaned = cleaned.strip(" \t\n/|-")
    cleaned = cleaned.strip()
    return cleaned, cleaned != text.strip()


def strip_question_fields(question: dict[str, Any]) -> dict[str, int]:
    """
    Strip bilingual pollution from stem, options, direction_text in place.

    Returns counts: {stem, options, direction_text, fields_changed}.
    """
    counts = {"stem": 0, "options": 0, "direction_text": 0, "fields_changed": 0}

    stem, changed = strip_non_latin(question.get("stem"))
    if changed:
        question["stem"] = stem
        counts["stem"] = 1
        counts["fields_changed"] += 1

    dt, changed = strip_non_latin(question.get("direction_text"))
    if changed:
        question["direction_text"] = dt or None
        counts["direction_text"] = 1
        counts["fields_changed"] += 1

    opts = question.get("options")
    if isinstance(opts, dict):
        opt_changed = 0
        new_opts: dict[str, str] = {}
        for k, v in opts.items():
            nv, ch = strip_non_latin(v if isinstance(v, str) else str(v) if v is not None else "")
            new_opts[k] = nv
            if ch:
                opt_changed += 1
        if opt_changed:
            question["options"] = new_opts
            counts["options"] = opt_changed
            counts["fields_changed"] += opt_changed

    return counts

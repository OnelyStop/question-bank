from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, direction_of, stem_of

# Patterns whose whole premise is a shared block. Without it the question is
# a dangling reference: "How many persons sit between B and E?" with no seating.
SET_PATTERNS = {
    "reading_comprehension_set",
    "cloze_passage_set",
    "table_di_set",
    "caselet_di_set",
    "shared_directions_set",
}

# A stem that points BACK at context it does not have.
#
# Backward references only. "the following information" is the direction's own
# opener -- when it appears in a stem it means the direction was welded into the
# stem, so the context is present, just misplaced. Treating that as missing
# quarantines 605 perfectly answerable coding-decoding questions.
DANGLING = re.compile(
    r"(?i)\b(the above (table|passage|graph|chart|information|arrangement)"
    r"|according to the passage|based on the (given )?passage"
    r"|with reference to the passage)\b"
)


class ContextMissingCheck(CheckSkill):
    """A set-pattern question whose shared directions were never attached."""

    id = "context_missing"
    name = "Context missing"
    tier = "blocking"
    reason = "context_missing"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        has_ctx = bool(direction_of(row).strip() or row.get("direction_id"))
        pattern = row.get("question_pattern")
        if pattern in SET_PATTERNS and not has_ctx:
            yield self.defect(f"{pattern} with no direction_text or direction_id")
        elif not has_ctx and DANGLING.search(stem_of(row)):
            yield self.defect("stem refers to context the row does not carry")

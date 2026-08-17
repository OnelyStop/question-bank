from __future__ import annotations

import re
from typing import Any, Iterable

from .base import CheckSkill, Defect, direction_of

# Shared directions that survived only as a dump of the whole page.
OVERSIZED = 6000

# A direction that announces data it does not contain. "The pie chart shows the
# percentage distribution..." followed by no numbers means the numbers were only
# ever in the image.
ANNOUNCES_DATA = re.compile(
    r"(?i)\b(pie chart|bar graph|line graph|radar (chart|graph)|following table|given table"
    r"|table (shows|given))\b"
)
MIN_NUMBERS = 5


class ContextUnusableCheck(CheckSkill):
    """Shared directions present, but not usable as given."""

    id = "context_unusable"
    name = "Context unusable"
    tier = "blocking"
    reason = "context_unusable"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        direction = direction_of(row)
        if not direction.strip():
            return  # context_missing owns this
        if len(direction) > OVERSIZED:
            yield Defect(reason=self.reason, tier="suspect",
                         detail=f"{len(direction)} chars — likely a whole-page dump")
            return
        if ANNOUNCES_DATA.search(direction) and len(re.findall(r"\d+", direction)) < MIN_NUMBERS:
            yield self.defect(
                "announces a chart/table but carries no numbers — the data was only in the image"
            )

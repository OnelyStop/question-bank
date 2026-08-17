from __future__ import annotations

import re
from typing import Any, Iterable

from checks.base import Defect

from .base import MatchResult, PatternSkill, combined_text


VISUAL_RX = re.compile(
    r"(?i)("
    r"pie\s+chart|bar\s+graph|line\s+graph|radar\s+chart|radar\s+graph|"
    r"mixed\s+graph|candlestick|"
    r"the\s+bar\s+shows|the\s+pie\s+(chart\s+)?(given|shows)|"
    r"following\s+(pie|bar|line)\s+(chart|graph)|"
    r"study\s+the\s+following\s+(pie|bar|line|radar)"
    r")"
)


class VisualChartGraphDiSkill(PatternSkill):
    id = "visual_chart_graph_di"
    name = "Visual chart / graph DI"
    priority = 30

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        m = VISUAL_RX.search(text)
        if not m:
            return MatchResult(matched=False)
        return MatchResult(
            matched=True,
            confidence=0.9,
            signals=[f"visual DI cue: {m.group(0)[:60]}"],
            extras={"has_image": True},
        )

    def extract_fields(self, question: dict[str, Any], match: MatchResult) -> dict[str, Any]:
        # Deliberately does NOT assert has_image. The text said "pie chart"; that
        # is evidence a chart existed in the PDF, not that one was extracted.
        # `extract.py` derives has_image from real refs, and validate() below
        # flags the row when there are none.
        return {}

    def validate(self, row: dict[str, Any]) -> Iterable[Defect]:
        if not (row.get("image_refs") or []):
            yield Defect(
                reason="chart_missing",
                tier="blocking",
                detail="chart/graph DI with no image attached - the data was only in the figure",
            )

from __future__ import annotations

import re
from typing import Any

from .base import MatchResult, PatternSkill, combined_text, image_blocks


IMG_RX = re.compile(
    r"(?i)("
    r"following\s+(figure|diagram|picture|image)|"
    r"(figure|diagram)\s+(given|shown|below|above)|"
    r"as\s+shown\s+in\s+the\s+(figure|diagram|image)|"
    r"study\s+the\s+following\s+(diagram|figure)|"
    r"refer\s+to\s+the\s+(figure|diagram)|"
    r"\[image\]|<<image>>|<image>|"
    r"the\s+(given\s+)?(figure|diagram)\s+(shows|represents)"
    r")"
)


class ImageFigureBasedSkill(PatternSkill):
    id = "image_figure_based"
    name = "Image / figure / diagram based"
    priority = 20

    def match(self, question: dict[str, Any], paper: dict[str, Any] | None = None) -> MatchResult:
        text = combined_text(question)
        refs = image_blocks(question)
        signals: list[str] = []
        conf = 0.0
        if IMG_RX.search(text):
            signals.append("figure/diagram cue in text")
            conf = 0.9
        if refs:
            signals.append(f"context image blocks={len(refs)}")
            conf = max(conf, 0.95)
        if conf > 0:
            return MatchResult(matched=True, confidence=conf, signals=signals, extras={"image_refs": refs})
        return MatchResult(matched=False)

    def extract_fields(self, question: dict[str, Any], match: MatchResult) -> dict[str, Any]:
        return {
            "has_image": True,
            "image_refs": match.extras.get("image_refs") or image_blocks(question),
        }

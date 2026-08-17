"""Shared helpers for quality-check skills.

Same shape as `patterns/base.py`: one skill per file, registered in `__init__.py`.
A pattern skill answers *what* a question is; a check skill answers *whether it is
serveable*. Reason codes are the ones already in use by `India/banking/sets/`
(see its README) so both lanes speak one vocabulary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

# Worst first. `validate.py --tier X` fails the build on X and anything worse.
TIERS = ["fatal", "blocking", "suspect", "info"]


@dataclass
class Defect:
    reason: str            # taxonomy code, e.g. "chart_missing"
    tier: str = "blocking"
    detail: str = ""


class CheckSkill:
    """Base class for one quality check."""

    id: str = ""
    name: str = ""
    tier: str = "blocking"
    reason: str = ""

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        raise NotImplementedError

    def defect(self, detail: Any = "") -> Defect:
        return Defect(reason=self.reason or self.id, tier=self.tier, detail=str(detail)[:300])


class CorpusCheckSkill:
    """A check that needs every row at once (duplicates, direction sets)."""

    id: str = ""
    name: str = ""
    tier: str = "suspect"
    reason: str = ""

    def check_corpus(self, rows: list[dict[str, Any]]) -> Iterable[tuple[str, Defect]]:
        raise NotImplementedError

    def defect(self, detail: Any = "") -> Defect:
        return Defect(reason=self.reason or self.id, tier=self.tier, detail=str(detail)[:300])


# --- shared accessors (row-shaped, unlike patterns/base.py which is question-shaped) ---

def options_of(row: dict[str, Any]) -> dict[str, str]:
    opts = row.get("options")
    return opts if isinstance(opts, dict) else {}


def option_values(row: dict[str, Any]) -> list[str]:
    return [v for v in options_of(row).values() if isinstance(v, str)]


def stem_of(row: dict[str, Any]) -> str:
    stem = row.get("stem")
    return stem if isinstance(stem, str) else ""


def direction_of(row: dict[str, Any]) -> str:
    dt = row.get("direction_text")
    return dt if isinstance(dt, str) else ""


def all_text(row: dict[str, Any]) -> str:
    return "\n".join([direction_of(row), stem_of(row)] + option_values(row))


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()

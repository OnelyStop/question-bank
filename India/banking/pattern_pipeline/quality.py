"""Runs the check skills over uniform rows.

Sits above both registries so neither has to import the other: pattern skills
contribute their own `validate()`, `checks/` contributes the cross-pattern rules,
and this module is the only place that knows about both.

Used by `validate.py` (report + CI gate) and `run_pipeline.py` (quarantine).
"""

from __future__ import annotations

from typing import Any, Iterable

from checks import CORPUS_CHECKS, ROW_CHECKS, TIERS, Defect
from patterns import PRIMARY_SKILLS, SECONDARY_SKILLS

_SKILL_BY_ID = {s.id: s for s in PRIMARY_SKILLS + SECONDARY_SKILLS}

# Worst tier first, so `worst_tier` and sorting agree with checks.base.TIERS.
_TIER_RANK = {tier: i for i, tier in enumerate(TIERS)}


def row_defects(row: dict[str, Any]) -> list[Defect]:
    """Every defect on one row: the pattern's own rules, then the shared checks.

    Deduplicated by (reason, tier) -- a pattern skill and a generic check often
    reach the same conclusion (`partial_or_missing_options.validate()` and
    `OptionPartialCheck` both say `option_partial`), and the row has that defect
    once, not twice. The pattern's version wins because it runs first and carries
    the more specific detail.
    """
    found: list[Defect] = []
    seen: set[tuple[str, str]] = set()

    def add(defects: Iterable[Defect]) -> None:
        for defect in defects:
            key = (defect.reason, defect.tier)
            if key not in seen:
                seen.add(key)
                found.append(defect)

    skill = _SKILL_BY_ID.get(row.get("question_pattern"))
    if skill is not None:
        add(skill.validate(row))
    for check in ROW_CHECKS:
        add(check.check(row))
    return found


def corpus_defects(rows: list[dict[str, Any]]) -> dict[str, list[Defect]]:
    """Defects that only exist across rows, keyed by q_id."""
    out: dict[str, list[Defect]] = {}
    for check in CORPUS_CHECKS:
        for qid, defect in check.check_corpus(rows):
            out.setdefault(qid, []).append(defect)
    return out


def audit(rows: list[dict[str, Any]]) -> dict[str, list[Defect]]:
    """All defects for a whole corpus, keyed by q_id. Rows with none are absent."""
    by_qid = corpus_defects(rows)
    for row in rows:
        defects = row_defects(row)
        if defects:
            by_qid.setdefault(row.get("q_id"), []).extend(defects)
    return by_qid


def worst_tier(defects: Iterable[Defect]) -> str | None:
    """The most severe tier present, or None for a clean row."""
    ranks = [_TIER_RANK.get(d.tier, len(TIERS)) for d in defects]
    return TIERS[min(ranks)] if ranks else None


def is_serveable(defects: Iterable[Defect]) -> bool:
    """True if nothing worse than `suspect` was found."""
    tier = worst_tier(defects)
    return tier is None or _TIER_RANK[tier] > _TIER_RANK["blocking"]

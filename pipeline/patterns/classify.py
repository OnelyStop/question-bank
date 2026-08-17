"""Classify a raw paper question into one primary pattern (+ optional secondary)."""

from __future__ import annotations

from typing import Any

from patterns import PRIMARY_SKILLS, SECONDARY_SKILLS
from patterns.base import MatchResult, PatternSkill, has_shared_directions, option_count


def classify_question(
    question: dict[str, Any],
    paper: dict[str, Any] | None = None,
) -> tuple[PatternSkill, MatchResult, list[tuple[PatternSkill, MatchResult]]]:
    """
    Return (primary_skill, primary_match, secondary_matches).

    Primary skills are evaluated in priority order; first match wins.
    Secondary skills (e.g. bilingual) can all match.
    """
    primary_sorted = sorted(PRIMARY_SKILLS, key=lambda s: s.priority)
    primary: PatternSkill | None = None
    primary_match: MatchResult | None = None

    for skill in primary_sorted:
        result = skill.match(question, paper)
        if result.matched:
            primary = skill
            primary_match = result
            break

    if primary is None or primary_match is None:
        # Absolute fallback — should be rare
        if has_shared_directions(question):
            from patterns.shared_directions_set import SharedDirectionsSetSkill

            primary = SharedDirectionsSetSkill()
            primary_match = MatchResult(
                matched=True,
                confidence=0.4,
                signals=["emergency fallback shared_directions_set"],
            )
        elif option_count(question) < 4:
            from patterns.partial_or_missing_options import PartialOrMissingOptionsSkill

            primary = PartialOrMissingOptionsSkill()
            primary_match = MatchResult(
                matched=True,
                confidence=0.4,
                signals=["emergency fallback partial_or_missing_options"],
            )
        else:
            from patterns.standalone_mcq import StandaloneMcqSkill

            primary = StandaloneMcqSkill()
            primary_match = MatchResult(
                matched=True,
                confidence=0.4,
                signals=["emergency fallback standalone_mcq"],
            )

    secondary: list[tuple[PatternSkill, MatchResult]] = []
    for skill in SECONDARY_SKILLS:
        # Don't duplicate primary id in secondary
        if skill.id == primary.id:
            continue
        result = skill.match(question, paper)
        if result.matched:
            secondary.append((skill, result))

    return primary, primary_match, secondary

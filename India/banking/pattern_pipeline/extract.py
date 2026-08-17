"""Normalize classified questions into uniform Supabase-ready rows."""

from __future__ import annotations

from typing import Any

from classify import classify_question
from patterns.base import has_shared_directions, image_blocks, normalize_options, option_count


def extract_uniform_question(
    question: dict[str, Any],
    paper: dict[str, Any],
    *,
    source_collection: str,
) -> dict[str, Any]:
    primary, primary_match, secondary = classify_question(question, paper)

    opts = normalize_options(question.get("options"))
    oc = option_count(question)

    secondary_ids: list[str] = []
    is_bilingual = False
    image_refs = image_blocks(question)

    extras: dict[str, Any] = {}
    extras.update(primary.extract_fields(question, primary_match))

    for skill, match in secondary:
        secondary_ids.append(skill.id)
        extras.update(skill.extract_fields(question, match))

    if extras.get("is_bilingual"):
        is_bilingual = True
    if extras.get("image_refs"):
        image_refs = extras["image_refs"]
    # has_image follows the refs and nothing else. It used to be forced true for
    # the two figure patterns, which claimed an image on 1,012 rows that carry
    # none -- a flag the UI cannot honour. A row that needs a figure and has none
    # is now reported by that pattern's validate() as `chart_missing`.
    has_image = bool(image_refs)

    # bilingual can also be primary only if somehow selected — keep flag true
    if primary.id == "bilingual_stem_directions":
        is_bilingual = True

    row: dict[str, Any] = {
        "q_id": question.get("q_id") or f"{paper.get('paper_id')}::q{int(question.get('q_num') or 0):03d}",
        "bank": paper.get("bank"),
        "role": paper.get("role"),
        "exam_type": paper.get("exam_type"),
        "year": paper.get("year"),
        "shift": paper.get("shift"),
        "memory_based": paper.get("memory_based"),
        "language": paper.get("language"),
        "section": question.get("section") or paper.get("subject"),
        "subject": paper.get("subject") or question.get("section"),
        "topic": question.get("topic"),
        "question_pattern": primary.id,
        "secondary_patterns": secondary_ids,
        "direction_id": question.get("direction_id"),
        "direction_text": question.get("direction_text"),
        "stem": question.get("stem") or "",
        "options": opts,
        "option_count": oc,
        "answer": question.get("answer"),
        "explanation": question.get("explanation"),
        "has_shared_directions": has_shared_directions(question),
        "is_bilingual": is_bilingual,
        "has_image": has_image,
        "image_refs": image_refs,
    }
    return row


def extract_paper(
    paper: dict[str, Any],
    *,
    source_collection: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for q in paper.get("questions") or []:
        rows.append(extract_uniform_question(q, paper, source_collection=source_collection))
    return rows

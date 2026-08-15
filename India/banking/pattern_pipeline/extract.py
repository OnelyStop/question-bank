"""Normalize classified questions into uniform Supabase-ready rows."""

from __future__ import annotations

from typing import Any

from classify import classify_question
from patterns.base import MatchResult, PatternSkill, has_shared_directions, image_blocks, option_count


def _normalize_options(options: Any) -> dict[str, str]:
    if not isinstance(options, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("a", "b", "c", "d", "e"):
        if key in options and options[key] is not None:
            out[key] = str(options[key])
    # also accept uppercase keys
    for key in ("A", "B", "C", "D", "E"):
        low = key.lower()
        if low not in out and key in options and options[key] is not None:
            out[low] = str(options[key])
    return out


def extract_uniform_question(
    question: dict[str, Any],
    paper: dict[str, Any],
    *,
    source_collection: str,
) -> dict[str, Any]:
    primary, primary_match, secondary = classify_question(question, paper)

    opts = _normalize_options(question.get("options"))
    oc = option_count(question)
    if oc == 0:
        oc = len(opts)

    metrics = question.get("metrics") or {}
    signals = list(primary_match.signals)
    secondary_ids: list[str] = []
    is_bilingual = False
    has_image = False
    image_refs = image_blocks(question)

    extras: dict[str, Any] = {}
    extras.update(primary.extract_fields(question, primary_match))

    for skill, match in secondary:
        secondary_ids.append(skill.id)
        signals.extend(match.signals)
        extras.update(skill.extract_fields(question, match))

    if extras.get("is_bilingual"):
        is_bilingual = True
    if extras.get("has_image") or image_refs or primary.id in {"image_figure_based", "visual_chart_graph_di"}:
        has_image = True
    if extras.get("image_refs"):
        image_refs = extras["image_refs"]

    # bilingual can also be primary only if somehow selected — keep flag true
    if primary.id == "bilingual_stem_directions":
        is_bilingual = True

    source = paper.get("source") or {}

    row: dict[str, Any] = {
        "q_id": question.get("q_id") or f"{paper.get('paper_id')}::q{int(question.get('q_num') or 0):03d}",
        "paper_id": paper.get("paper_id"),
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
        "q_num": question.get("q_num"),
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
        "source_pdf_path": source.get("pdf_path"),
        "source_collection": source_collection,
        "classification_confidence": primary_match.confidence,
        "classification_signals": signals,
        "page_start": metrics.get("page_start"),
        "page_end": metrics.get("page_end"),
        "raw_metrics": metrics or None,
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

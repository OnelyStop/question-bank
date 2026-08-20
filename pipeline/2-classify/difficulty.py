"""v1 difficulty scorer (1 easiest … 5 hardest)."""

from __future__ import annotations

from typing import Any


PATTERN_BASE: dict[str, int] = {
    "standalone_mcq": 2,
    "shared_directions_set": 3,
    "reading_comprehension_set": 3,
    "cloze_passage_set": 2,
    "image_figure_based": 4,
    "visual_chart_graph_di": 4,
    "table_di_set": 3,
    "caselet_di_set": 4,
    "data_sufficiency": 4,
    "quantity_comparison": 3,
    "quadratic_comparison": 2,
    "match_the_columns": 2,
    "partial_or_missing_options": 1,
    "bilingual_stem_directions": 2,
}

TOPIC_BUMP: dict[str, int] = {
    "Data_Interpretation": 1,
    "Puzzle": 1,
    "Seating_Arrangement": 1,
    "Input_Output": 1,
    "Critical_Reasoning": 1,
    "Reading_Comprehension": 0,
    "Number_Series": -1,
    "Simplification": -1,
    "Approximation": -1,
    "Vocabulary": -1,
    "Error_Spotting": 0,
}


def infer_difficulty(
    question: dict[str, Any],
    paper: dict[str, Any] | None = None,
) -> int:
    pattern = question.get("question_pattern") or "standalone_mcq"
    topic = question.get("topic") or ""
    exam_type = (paper or {}).get("exam_type") or question.get("exam_type")

    score = PATTERN_BASE.get(pattern, 3)
    score += TOPIC_BUMP.get(topic, 0)

    if exam_type and str(exam_type).lower() == "mains":
        score += 1
    elif exam_type and str(exam_type).lower() == "prelims":
        score -= 0

    # Long shared directions tend to be heavier
    dt = question.get("direction_text") or ""
    if len(dt) > 800:
        score += 1

    return max(1, min(5, int(score)))

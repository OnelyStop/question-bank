#!/usr/bin/env python3
"""Regression cases for the rule-based section and topic classifier."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import check, step  # noqa: E402

topics = step("2-classify", "label_topics")
sections = step("2-classify", "label_sections")


def label(stem: str):
    return topics.infer_labels(None, None, stem, None)[:2]


def test_common_puzzle_wording_is_reasoning():
    check(
        "birth-month ordering is a puzzle",
        label("Eight persons were born in different months. Who was born before P?"),
        ("Reasoning", "Puzzle"),
    )


def test_rrb_prelims_numbering_has_documented_sections():
    paper = {"bank": "IBPS", "role": "RRB", "exam_type": "Prelims", "questions": [None] * 80}
    check("RRB q40 is reasoning", sections.section_from_prelims_qnum(paper, 40), ("Reasoning", "prelims_qnum_range"))
    check("RRB q41 is quantitative", sections.section_from_prelims_qnum(paper, 41), ("Quantitative", "prelims_qnum_range"))
    partial = {**paper, "questions": [None] * 20}
    check("partial cleaned RRB paper retains q_num layout", sections.section_from_prelims_qnum(partial, 41), ("Quantitative", "prelims_qnum_range"))


def test_nearby_section_fill_requires_matching_enclosing_sections():
    paper = {"questions": [{"section": "Reasoning"}, {}, {}, {"section": "Reasoning"}]}
    check("fills a short internal gap", sections.fill_nearby_sections(paper), 2)
    check("gap inherits the enclosing section", [q.get("section") for q in paper["questions"]], ["Reasoning"] * 4)
    boundary = {"questions": [{"section": "English"}, {}, {"section": "Quantitative"}]}
    check("does not cross a section boundary", sections.fill_nearby_sections(boundary), 0)


def test_sparse_market_puzzle_wording_is_reasoning():
    check(
        "market-order question from weak batch",
        label("How many persons go market after H?"),
        ("Reasoning", "Puzzle"),
    )


def test_underscore_blank_is_english():
    check(
        "extracted blank question",
        label("Choose the word: the report has ______________ errors."),
        ("English", "Fill_in_the_Blanks"),
    )


def test_symbolic_conclusion_is_inequality():
    check(
        "statement and conclusion relation is inequality",
        label("Statements: P > Q, Q = R. Conclusions: P > R."),
        ("Reasoning", "Inequality"),
    )


def test_math_comparison_is_not_stolen_by_inequality_rule():
    check(
        "numeric comparison remains unlabelled without a quantitative cue",
        label("Which value is greater: 12 or 9?"),
        (None, None),
    )


def test_direction_question_is_reasoning():
    check(
        "relative direction question",
        label("In which direction is P from Q after walking 5 km north?"),
        ("Reasoning", "Direction_Sense"),
    )


def test_letter_arrangement_is_alphanumeric():
    check(
        "letter transformation question",
        label("If the letters in the word BANK are arranged alphabetically, which is second?"),
        ("Reasoning", "Alphanumeric"),
    )


def test_reviewed_weak_batch_alphanumeric_cases():
    # Manually reviewed examples from PR #47's weak batches. The paper/q ids
    # make these regression labels traceable back to the corpus rather than
    # examples invented for the classifier.
    check(
        "batch11 ibps_rrb_2024_prelims_33292564 q20",
        label("Find how many meaningful words will be formed by using letters only once."),
        ("Reasoning", "Alphanumeric"),
    )
    check(
        "batch9 ibps_rrb_2019_prelims_c0605d17 q12",
        label("How many numbers are in the series immediately preceded by a symbol and followed by a letter?"),
        ("Reasoning", "Alphanumeric"),
    )


def test_remaining_weak_batch_patterns():
    check(
        "height-ranking set is a puzzle",
        label("Seven persons are of different heights. Who is the second tallest?"),
        ("Reasoning", "Puzzle"),
    )
    check(
        "literal numeric run is a number series",
        label("1, 2, 5, 16, 65, 328, 1957"),
        ("Quantitative", "Number_Series"),
    )
    check(
        "series ending in a missing value",
        label("2, 4, 7, 12, 19, ?"),
        ("Quantitative", "Number_Series"),
    )
    check(
        "question-mark arithmetic is simplification",
        label("What value should come in place of (?) in the following question?"),
        ("Quantitative", "Simplification"),
    )
    check(
        "salary problem is arithmetic",
        label("Anil spends 25% of his monthly salary and saves the rest."),
        ("Quantitative", "Arithmetic"),
    )
    check(
        "shared-order set is a puzzle",
        label("Seven persons purchased books, but not necessarily in the same order."),
        ("Reasoning", "Puzzle"),
    )
    check(
        "hyphenated line graph is data interpretation",
        label("Study the line-graph carefully and answer the question."),
        ("Quantitative", "Data_Interpretation"),
    )
    check(
        "computer hardware question is computer basics",
        label("Which port connects an internal hard disk drive to a motherboard?"),
        ("Computer", "Computer_Basics"),
    )
    check(
        "variable series is number series",
        label("Find the pattern of the series. Series I: 8, 9, 17, 52, A, B."),
        ("Quantitative", "Number_Series"),
    )
    check(
        "time slot ordering is a puzzle",
        label("Each subject has a time slot. Which class is scheduled after English?"),
        ("Reasoning", "Puzzle"),
    )
    check(
        "reasoning inference uses the miscellaneous taxonomy bucket",
        label("Which conclusion can be inferred from the given information?"),
        ("Reasoning", "Miscellaneous_Reasoning"),
    )


def test_geometry_is_quantitative_arithmetic():
    check(
        "geometry question",
        label("Find the area of a triangle with base 10 cm and height 4 cm."),
        ("Quantitative", "Arithmetic"),
    )

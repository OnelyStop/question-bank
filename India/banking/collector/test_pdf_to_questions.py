"""Tests for PDF text → question parsing (no PDF I/O required for core cases)."""

from __future__ import annotations

from pdf_to_questions import parse_options, parse_questions_from_text
from question_schema import make_paper_id, make_q_id


SAMPLE = """
IBPS Clerk Prelims 2019 | Memory Based Paper

Direction (1-5): Study the following information carefully
and answer the questions given below:

Eight persons A, B, C, D, E F, G and H are going to watch
movie in different months.

1. How many persons sit between B and E?

(a) One
(b) Two
(c) Three
(d) Four
(e) More than four

2. Who among the following sits third to the right of H?

(a) F
(b) E
(c) D
(d) G
(e) A

Direction (6-7): In each of the questions below. Some
statements are given followed by conclusions:
(a) If only conclusion I follows.
(b) If only conclusion II follows.
(c) If either conclusion I or II follows.
(d) If neither conclusion I nor II follows.
(e) If both conclusions I and II follow.

6. Statements: Only a few paint is color. No color is fabric.
Conclusions: I. Some fabric is paint
II. All color can be paint

7. Statements: Only a few brush is paint.
Conclusions: I. Some brush is color
II. No fabric is brush

Directions (8-9): In the following passage there are blanks.
Some text ________ (8) and more ________ (9).

8. (a) One
(b) Two
(c) Three
(d) Four
(e) Five

9. (a) Red
(b) Blue
(c) Green
(d) Yellow
(e) Black

REASONING ABILITY

11. In the word CHLORINE, how many pairs?

(a) Four
(b) Two
(c) One
(d) Three
(e) More than four
"""


def test_parse_options_basic():
    stem, opts = parse_options(
        "How many?\n(a) One\n(b) Two\n(c) Three\n(d) Four\n(e) Five"
    )
    assert "How many" in stem
    assert opts["a"] == "One"
    assert opts["e"] == "Five"
    assert len(opts) == 5


def test_parse_options_letter_paren():
    stem, opts = parse_options(
        "Find the number.\nA) 315\nB) 325\nC) 295\nD) 335\nE) None of these"
    )
    assert "Find the number" in stem
    assert opts["a"] == "315"
    assert opts["e"] == "None of these"


def test_parse_q_prefix_style():
    text = """
Directions (1-2): Read the passage.

Q1. What is the main idea?

(a) One
(b) Two
(c) Three
(d) Four
(e) Five

Q2. Which is true?

(a) A
(b) B
(c) C
(d) D
(e) E
"""
    qs, _notes = parse_questions_from_text(text, [(1, 0, len(text))], "qstyle")
    assert [q.q_num for q in qs] == [1, 2]
    assert qs[0].options["a"] == "One"


def test_parse_question_word_style():
    text = """
Directions: Answer based on the info.

Question 1: Find the value.
A) 10
B) 20
C) 30
D) 40
E) 50

Question 2: Find the ratio.
A) 1:2
B) 2:3
C) 3:4
D) 4:5
E) 5:6
"""
    qs, _notes = parse_questions_from_text(text, [(1, 0, len(text))], "pmock")
    assert len(qs) == 2
    assert qs[0].options["a"] == "10"
    assert qs[0].direction_text and "Answer based" in qs[0].direction_text


def test_parse_sample_paper():
    qs, notes = parse_questions_from_text(SAMPLE, [(1, 0, len(SAMPLE))], "test_paper")
    nums = [q.q_num for q in qs]
    assert 1 in nums and 2 in nums and 6 in nums and 7 in nums and 11 in nums
    assert 8 in nums and 9 in nums
    q1 = next(q for q in qs if q.q_num == 1)
    assert q1.direction_id == "d001"
    assert q1.direction_text and "Eight persons" in q1.direction_text
    assert q1.options["a"] == "One"
    assert q1.metrics.has_passage is True
    q6 = next(q for q in qs if q.q_num == 6)
    assert q6.options.get("a", "").startswith("If only conclusion")
    q8 = next(q for q in qs if q.q_num == 8)
    assert "blank" in q8.stem.lower()
    assert q8.options["a"] == "One"
    q11 = next(q for q in qs if q.q_num == 11)
    assert q11.section == "Reasoning"
    assert not notes or "no_questions_parsed" not in notes


def test_ids():
    pid = make_paper_id("IBPS", "Clerk", 2019, "Prelims", None, "abcdefghij")
    assert pid.startswith("ibps_clerk_2019_prelims_unknown_shift_abcdefgh")
    assert make_q_id(pid, 3).endswith("::q003")


if __name__ == "__main__":
    test_parse_options_basic()
    test_parse_options_letter_paren()
    test_parse_q_prefix_style()
    test_parse_question_word_style()
    test_parse_sample_paper()
    test_ids()
    print("ok")

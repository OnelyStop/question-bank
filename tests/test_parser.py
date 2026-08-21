#!/usr/bin/env python3
"""Page structure: where a question starts, and what a line of it says.

Every case is a real failure. Option splitting lives in test_options.py and
number formatting in test_maths.py; this file covers the geometry underneath
both -- anchors, raised spans, stacked fractions, bilingual text.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import check, line, step  # noqa: E402

parser = step("1-extract", "parser")
QUESTION_RE = parser.QUESTION_RE
line_text, join_fractions = parser.line_text, parser.join_fractions
question_anchors, strip_hindi = parser.question_anchors, parser.strip_hindi


# --- what counts as a question number ---------------------------------------
def anchor(text):
    m = QUESTION_RE.match(text)
    return int(m.group(1) or m.group(2)) if m else None


def test_question_number_shapes():
    # "Q130.1: 23x+y" is a real question whose stem opens with a digit.
    check("Q-prefixed with a decimal stem", anchor("Q130.1: 23x+y = 32"), 130)
    check("bare decimal is an option value", anchor("30.2"), None)
    check("bare number with a space", anchor("52. 27"), 52)
    check("zero is a list marker", anchor("0. junk"), None)


def anchors_for(text: str) -> list[int]:
    found = list(QUESTION_RE.finditer(text))
    prefixed = sum(1 for m in found if m.group(1))
    q_style = prefixed >= 0.6 * len(found) if found else False
    return [n for n, _, _ in question_anchors(found, q_style)]


def test_para_jumble_labels_are_not_questions():
    # These sets print the already-placed sentences by their position in the
    # paragraph. "2." read as question 2, so 104's block ended there and its
    # options -- (a) P (b) Q (c) R (d) S (e) T -- were never reached. The real
    # questions 2 and 5 have to lead: what marks the labels as labels is that
    # those numbers are already spent, and a para-jumble always sits far enough
    # into a paper (q100+ here) for that to hold.
    jumble = (
        "".join(f"{n}. Real question text.\n" for n in range(1, 6)) +
        "104. P. Above 500 falls in the 'severe-plus emergency' category.\n"
        "2. An AQI between 0-50 is considered 'good'.\n"
        "Q. The air quality index touched dangerous levels of 625.\n"
        "5. There was some relief after sporadic rains on Saturday.\n"
        "(a) P\n(b) Q\n(c) R\n(d) S\n(e) T\n"
        "105. P. According to its developers, the key is labeling the nodes.\n"
    )
    check("sentence labels dropped", anchors_for(jumble), [1, 2, 3, 4, 5, 104, 105])


def test_column_interleave_is_kept_whole():
    # Two columns read out of order all by themselves. Every one of these is a
    # real question, and rejecting backward numbers cost all four of them.
    text = "".join(f"{n}. Which of the following is true?\n"
                   for n in (41, 44, 45, 42, 43, 46))
    check("interleaved order preserved", anchors_for(text), [41, 44, 45, 42, 43, 46])


def test_section_restart_is_kept():
    # 1-35 Reasoning then 1-35 English reuses every number legitimately. It
    # differs from a label by continuing to count.
    text = "".join(f"{n}. Question text here.\n" for n in (1, 2, 3, 4, 1, 2, 3, 4))
    check("restart kept", anchors_for(text), [1, 2, 3, 4, 1, 2, 3, 4])


# --- raised spans -----------------------------------------------------------
# A real exponent prints small AND carries the flag. PyMuPDF also flags whole
# full-size runs on stacked-fraction lines, and raising those garbled 14 stems
# into "⁺ ? ⁼ ³⁵".
def test_real_exponent_is_raised():
    check("exponent becomes a glyph",
          line_text(line((" 2x", 12.0, 4), ("2", 8.0, 5), (" – 3x", 12.0, 4))),
          " 2x² – 3x")


def test_full_size_run_is_not_raised():
    check("full-size run left alone",
          line_text(line(("2", 7.9, 4), (" × 4 + ? = 35 ", 11.0, 5))),
          "2 × 4 + ? = 35 ")


def test_long_exponent_keeps_its_expression():
    # Translating "(4×16÷32+1)" character by character emits mixed garbage.
    check("expression exponent stays whole",
          line_text(line(("(? )", 12.0, 4), ("(4 ×16 ÷32+1)", 8.5, 5))),
          "(? )^(4 ×16 ÷32+1)")


def test_adjacent_raised_spans_merge():
    # "2x+3y" arrives as five spans; judged one at a time each was short enough
    # for the glyph path, giving "^{2}x⁺^{3}y".
    check("run merged before choosing a form",
          line_text(line(("2", 12, 4), ("2", 8, 5), ("x", 8, 5),
                         ("+", 8, 5), ("3", 8, 5), ("y", 8, 5))),
          "2^(2x+3y)")


def test_radicand_is_not_an_exponent():
    # A radicand prints small and carries the flag too: "√16" became "^{1}⁶".
    check("radical span never raised",
          line_text(line(("value of ", 12.0, 4), ("√16", 8.0, 5))),
          "value of √16")


def test_ordinal_suffix_stays_prose():
    # A date sets its suffix raised and small, so it passes both signals:
    # "born on 28^(th) June". 141 dates across two batches, against 2 real
    # exponents.
    check("date suffix",
          line_text(line(("born on 28", 12.0, 4), ("th", 8.0, 5), (" June", 12.0, 4))),
          "born on 28th June")
    check("roman numeral suffix",
          line_text(line(("find IV", 12.0, 4), ("th", 8.0, 5), (" term", 12.0, 4))),
          "find IVth term")
    # It has to follow a number: a raised run after an ordinary word is not an
    # ordinal, and treating one as prose would hide a real exponent.
    check("needs a number before it",
          line_text(line(("the ", 12.0, 4), ("th", 8.0, 5))),
          "the ^(th)")


# --- stacked fractions ------------------------------------------------------
# The numerator merges only across a drawn bar. Without that rule the question
# number "54." sitting above a maths line merged into it and the question
# disappeared.
def test_fraction_merges_over_a_bar():
    num = ((10, 100, 20, 108), "1")
    den = ((10, 110, 30, 124), "3 %")
    merged, _ = join_fractions([num, den], bars=[(109, 8, 32)])
    check("joined over a bar", [t for _, t in merged], ["1/3 %"])


def test_no_bar_no_merge():
    num = ((10, 100, 20, 108), "1")
    den = ((10, 110, 30, 124), "3 %")
    merged, _ = join_fractions([num, den], bars=[])
    check("left apart without a bar", [t for _, t in merged], ["1", "3 %"])


# --- bilingual papers -------------------------------------------------------
# Removing Devanagari runs (not truncating at the first one) keeps the Latin
# labels inside a Hindi direction; truncation wiped them to "".
def test_hindi_run_removal():
    check("labels survive",
          strip_hindi("दिए गए (a) यदि x >y (b) यदि x <y"),
          "(a) x >y (b) x <y")
    check("appended translation cut",
          strip_hindi("14 years 14 वर्त"), "14 years 14")


if __name__ == "__main__":
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))

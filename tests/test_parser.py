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
DIRECTION_RE = parser.DIRECTION_RE
UNNUMBERED_DIRECTION_RE = parser.UNNUMBERED_DIRECTION_RE


# --- Q-prefixed direction ranges ---------------------------------------------
# "Directions (Q131-135)", "(Q.13-20)" -- three real papers carry a filename
# numbering habit ("Q41.") into their direction headers too, on top of the
# plain "(101-105)" style. Missing this drops the whole direction (a
# para-jumble's task, a cloze passage's blanks) for every question it covers.
def direction_range(text):
    m = DIRECTION_RE.search(text)
    return m.groups() if m else None


def test_answer_the_questions_opens_a_di_set():
    # sbi-po-pre-2021.pdf: "Answer the questions based on the information
    # given below" opens a DI table, but only "Answer the following" was
    # recognized -- the table glued onto the previous question's stem
    # instead of becoming its own direction.
    check("recognized as a direction header",
          bool(UNNUMBERED_DIRECTION_RE.match(
              "Answer the questions based on the information given below.")),
          True)
    check("existing 'Answer the following' still works (regression)",
          bool(UNNUMBERED_DIRECTION_RE.match("Answer the following questions.")),
          True)
    check("plain prose containing neither phrase is not a direction",
          bool(UNNUMBERED_DIRECTION_RE.match("Answer wisely and carefully.")),
          False)


def test_q_prefixed_range_is_read_same_as_bare():
    check("Q-prefixed with a period and space",
          direction_range("Directions (Q. 101-105) : Read the following passage"),
          ("101", "105"))
    check("Q-prefixed with no space, no period",
          direction_range("Directions (Q131-135) Five statements are given below"),
          ("131", "135"))
    check("Q-prefixed with period, no space",
          direction_range("Directions (Q.13-20): In the following passage"),
          ("13", "20"))
    check("bare numbers still work (regression)",
          direction_range("Directions (116-120):"), ("116", "120"))
    check("singular 'Direction', no colon (regression)",
          direction_range("Direction (126-130)"), ("126", "130"))


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


def test_math_alphanumerics_are_folded():
    # Equation-set papers use "𝑥" and "𝟏" — U+1D465 and U+1D7CF. The bold digit
    # is not matched by \d, so to_latex silently declined to convert anything
    # containing one, and 49 questions across three batches carried them into
    # the JSON. Folding belongs at extraction, not only in the review PDF.
    check("italic x folded",
          line_text(line(("I. 4/\U0001d465 = 3", 12.0, 4))), "I. 4/x = 3")
    check("bold digit folded",
          line_text(line(("\U0001d7cf\U0001d7d0 apples", 12.0, 4))), "12 apples")
    check("ordinary text untouched",
          line_text(line(("Find the value of x.", 12.0, 4))), "Find the value of x.")


# --- scripts ----------------------------------------------------------------
def test_bengali_only_question_is_dropped():
    # One SBI paper prints 31 of 98 questions in Bengali only, in a font whose
    # text layer decodes wrongly -- "যদি" comes out "যশি". 29 of them carry a
    # full option set, so every gate passes them.
    check("bengali stem", parser.unreadable("শব্ব্তশি: শকেু আযপল্", {"a": "1"}), True)
    check("bengali options", parser.unreadable("Which follows?", {"a": "যশি"}), True)


def test_hindi_only_question_is_kept():
    # A Hindi stem with English options is a question this bank keeps. Treating
    # the two scripts alike took 40 questions out of batch 1.
    check("hindi stem stays",
          parser.unreadable("C से ठीक भारी कौि है?", {"a": "B", "b": "D"}), False)


def test_strip_leftovers_only_in_a_bengali_paper():
    # ": : I. , II." is the whole of one syllogism stem after its Bengali was
    # removed -- short, wordless, numberless.
    check("residue in a bengali paper", parser.unreadable(": : I. , II.", {}, True), True)
    check("same stem elsewhere is left alone",
          parser.unreadable(": : I. , II.", {}, False), False)
    check("a blank stem is not unreadable", parser.unreadable("", {"a": "1"}, True), False)
    check("a real short stem survives",
          parser.unreadable("Find the value of 2 + 2", {"a": "4"}, True), False)


# --- picture, or parse failure? ---------------------------------------------
# Per question the two look identical: no stem, five options, a direction. What
# separates them is how much of the SET sits on an image.
def stemless(n, on_image, direction="d1", options=None):
    return {"q_num": n, "stem": "", "direction_id": direction,
            "options": options if options is not None else {"a": "1", "b": "2"},
            "on_image": on_image}


def test_stemless_set_mostly_on_images_is_a_picture():
    # A symbol set prints its statements as graphics: every question is on one.
    qs = [stemless(n, True) for n in (43, 44, 45)]
    parser.resolve_image_bodied(qs)
    check("whole set marked", [q["has_image"] for q in qs], [True, True, True])


def test_stemless_set_with_one_stray_image_is_not():
    # An error-spotting set states the task in its direction and prints only the
    # five candidate sentences. One chart elsewhere on a page is not the
    # question -- dropping q93 on that evidence lost five good options.
    qs = [stemless(n, n == 93) for n in range(89, 96)]
    parser.resolve_image_bodied(qs)
    check("none marked", [q["has_image"] for q in qs], [False] * 7)


def test_missing_options_is_always_a_picture():
    # "(a) (b) (c) (d) (e)" with nothing after them: the values were drawn.
    qs = [{"q_num": 63, "stem": "In tank R, pipe A was opened for 9 hours.",
           "options": {}, "direction_id": "d2", "on_image": True}]
    parser.resolve_image_bodied(qs)
    check("no options and on an image", qs[0]["has_image"], True)


def test_complete_question_is_never_a_picture():
    qs = [{"q_num": 1, "stem": "What is 2 + 2?", "options": {"a": "3", "b": "4"},
           "direction_id": None, "on_image": True}]
    parser.resolve_image_bodied(qs)
    check("stem and options present", qs[0]["has_image"], False)


# --- bilingual papers -------------------------------------------------------
# Removing Devanagari runs (not truncating at the first one) keeps the Latin
# labels inside a Hindi direction; truncation wiped them to "".
def test_orphaned_question_mark_collapses():
    # The Hindi sentence ends in an ASCII "?" that the Devanagari run does not
    # cover, so removing the Hindi strands it after the English one.
    check("hindi's question mark does not survive",
          strip_hindi("Which box is at the topmost position? "
                      "निम्ननिनित में से कौि सा है?"),
          "Which box is at the topmost position?")
    check("no space between them either",
          strip_hindi("…the passage given??"), "…the passage given?")
    # Only at the end. A maths stem carries "(?)" mid-sentence and must not be
    # touched -- 97 of them do.
    check("mid-stem question marks kept",
          strip_hindi("What should come in place of (?) in the questions? 150"),
          "What should come in place of (?) in the questions? 150")


def test_hindi_run_removal():
    check("labels survive",
          strip_hindi("दिए गए (a) यदि x >y (b) यदि x <y"),
          "(a) x >y (b) x <y")
    check("appended translation cut",
          strip_hindi("14 years 14 वर्त"), "14 years 14")


if __name__ == "__main__":
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))

#!/usr/bin/env python3
"""Splitting a question block into a stem and its options.

The recurring failure is not a missing option -- it is an option that captured
text belonging to something else. "155.56% Ans." and "Only (ii) is filled u"
both read as real answers, so nothing downstream flags them.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import check  # noqa: E402
from harness import step  # noqa: E402

parser = step("1-extract", "parser")
split_options = parser.split_options
options_from_direction = parser.options_from_direction


def test_plain_five_options():
    stem, opts = split_options("Find the value.\n(a) 10\n(b) 20\n(c) 30\n(d) 40\n(e) 50")
    check("stem kept", stem, "Find the value.")
    check("five options", list(opts), ["a", "b", "c", "d", "e"])
    check("values kept", list(opts.values()), ["10", "20", "30", "40", "50"])


def test_no_options_leaves_stem_whole():
    stem, opts = split_options("No options here at all.")
    check("stem survives", stem, "No options here at all.")
    check("no options invented", opts, {})


def test_answer_key_bleed():
    # The inline key rode along on option (e) of all 100 questions in one paper.
    _, opts = split_options("What? (a) 1 (b) 2 (c) 3 (d) 4 (e) 155.56%\nAns.(b)")
    check("Ans.(x) cut from last option", opts.get("e"), "155.56%")


def test_direction_bleed():
    _, opts = split_options(
        "Pick. (a) A (b) B (c) C (d) D (e) No combination fits\n"
        "Directions 32-34: Given below")
    check("unparenthesised Directions cut", opts.get("e"), "No combination fits")


def test_bleed_needs_a_word_boundary():
    # "plans. (a)" is not an answer key. Without \b it cut a stem at
    # "improvement pl" and took the options with it.
    _, opts = split_options(
        "It contributes to improvement plans.\n(a) Only (iii)\n(b) Only (ii)\n"
        "(c) Only (i)\n(d) Both\n(e) All of these")
    check("plans. is not Ans.", len(opts), 5)


def test_uppercase_starters():
    # Connector questions print three UPPERCASE options and no lowercase set.
    stem, opts = split_options(
        "Select the connector.\n(A) Because the bank issued\n"
        "(B) Considering the bank issued\n(C) Even though the bank issued")
    check("three uppercase options", list(opts), ["a", "b", "c"])
    check("stem kept", stem, "Select the connector.")


def test_lowercase_wins_over_uppercase():
    # A para-jumble has both: (A)-(D) sentence parts and (a)-(e) real options.
    _, opts = split_options(
        "(A) part one (B) part two (C) part three\n"
        "(a) ABCD\n(b) BACD\n(c) CABD\n(d) DACB\n(e) No change")
    check("lowercase set chosen", list(opts.values())[0], "ABCD")


def test_error_spotting_segments():
    _, opts = split_options(
        "Why we do not (a)/ meet to discuss (b)/ this matter (c)/ "
        "on Friday? (d)/ No error. (e)")
    check("segments split on the marker", list(opts.values()),
          ["Why we do not", "meet to discuss", "this matter", "on Friday?", "No error."])


def test_bare_uppercase_adda247():
    # SBI PO Pre 2019/2020 print "A) 12" with no opening paren.
    stem, opts = split_options(
        "Find D.\nA) 180 B) 320 C) 260 D) 240 E) 300")
    check("stem kept", stem, "Find D.")
    check("five bare options", list(opts), ["a", "b", "c", "d", "e"])
    check("values kept", list(opts.values()),
          ["180", "320", "260", "240", "300"])


def test_bare_uppercase_beats_stray_paren_e():
    # "choose option (e)" is an instruction, not option e of a five-set.
    stem, opts = split_options(
        "If already correct, choose option (e) i.e. No correction required "
        "as your answer. The ban has been a failure as there has been no "
        "reducing in usage.\nA) is no reduce B) has been no reduction "
        "C) have been no reduced D) is not any reduced E) No correction required")
    check("sentence stayed in the stem", "failure" in stem, True)
    check("real A)-E) list", list(opts.values())[1], "has been no reduction")
    check("five options", len(opts), 5)


def test_cloze_blank_then_bare_options():
    stem, opts = split_options(
        "(A) A) Traded B) Invaded C) Segregated D) Daunted E) Halted")
    check("blank is the stem", stem, "(A)")
    check("options from A)", list(opts), ["a", "b", "c", "d", "e"])
    check("first option", opts["a"], "Traded")


def test_options_stated_once_in_the_direction():
    # Quadratic-comparison sets print the five choices in the direction and then
    # only the equations under each number, so the questions carry no options.
    d = ("give answer (a) if x > y (b) if x < y (c) if x >= y (d) if x <= y "
         "(e) if x = y or no relation can be established")
    opts = options_from_direction(d)
    check("five options recovered", list(opts), ["a", "b", "c", "d", "e"])
    check("first option", opts["a"], "if x > y")
    check("no direction, no options", options_from_direction(""), {})


if __name__ == "__main__":
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))

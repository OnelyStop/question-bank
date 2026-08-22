#!/usr/bin/env python3
"""Regression tests for the parser, one per bug that actually shipped.

Every case here is a real failure from batch 1 -- not hypothetical coverage.
Plain asserts, no test framework: run it, exit 0 or die on the first failure.

    python3 pipeline/1-extract/test_parser.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "1-extract"))
from parser import (  # noqa: E402
    AD_CREDIT_RE,
    QUESTION_RE,
    display,
    join_fractions,
    line_text,
    split_options,
    strip_hindi,
    to_latex,
)

def check(name: str, got, want) -> None:
    assert got == want, f"{name}\n    got : {got!r}\n    want: {want!r}"


# --- question anchors -------------------------------------------------------
# "Q130.1: 23x+y" is a real question whose stem starts with a digit; a bare
# "30.2" is an option value; "0." is a list marker.
def anchor(text):
    m = QUESTION_RE.match(text)
    return int(m.group(1) or m.group(2)) if m else None


def test_question_anchors():
    check("anchor Q130.1", anchor("Q130.1: 23x+y = 32"), 130)
    check("anchor bare decimal rejected", anchor("30.2"), None)
    check("anchor bare with space", anchor("52. 27"), 52)
    check("anchor zero rejected", anchor("0. junk"), None)

# --- superscripts -----------------------------------------------------------
# A real exponent prints small; PyMuPDF also flags whole full-size runs as
# superscript on stacked-fraction lines, and raising those garbled 14 stems.
def line(*spans):
    return {"spans": [{"text": t, "size": s, "flags": f} for t, s, f in spans]}


def test_superscripts():
    check("superscript real exponent",
          line_text(line((" 2x", 12.0, 4), ("2", 8.0, 5), (" – 3x", 12.0, 4))),
          " 2x² – 3x")
    check("superscript full-size run NOT raised",
          line_text(line(("2", 7.9, 4), (" × 4 + ? = 35 ", 11.0, 5))),
          "2 × 4 + ? = 35 ")
    check("superscript expression -> ^(...)",
          line_text(line(("(? )", 12.0, 4), ("(4 ×16 ÷32+1)", 8.5, 5))),
          "(? )^(4 ×16 ÷32+1)")

# --- stacked fractions ------------------------------------------------------
# The numerator merges only across a drawn fraction bar; without that rule the
# question number "54." above a maths line merged into it and the question
# disappeared.
def test_stacked_fractions():
    num = ((10, 100, 20, 108), "1")
    den = ((10, 110, 30, 124), "3 %")
    merged, _ = join_fractions([num, den], bars=[(109, 8, 32)])
    check("fraction joined over a bar", [t for _, t in merged], ["1/3 %"])
    merged, _ = join_fractions([num, den], bars=[])
    check("no bar, no merge", [t for _, t in merged], ["1", "3 %"])

# --- option bleed -----------------------------------------------------------
# The inline answer key rode along on option (e) of all 100 questions in one
# paper: "155.56% Ans." is a wrong option that looks real.
def test_option_bleed():
    _, opts = split_options("What? (a) 1 (b) 2 (c) 3 (d) 4 (e) 155.56%\nAns.(b)")
    check("Ans.(x) cut from last option", opts.get("e"), "155.56%")
    _, opts = split_options("Pick. (a) A (b) B (c) C (d) D (e) No combination fits\nDirections 32-34: Given below")
    check("unparenthesised Directions cut", opts.get("e"), "No combination fits")


# "Visit: adda247.com" has no "www." so it slipped past the option-bleed cut,
# and it isn't always trailing -- it showed up stitched into the MIDDLE of a
# passage in one 2019 IBPS PO Mains paper: "...equal in each city. Visit:
# adda247.com Note- Married couples...". Cutting-to-end-of-string (BLEED_RE's
# approach) would have deleted "Note- Married couples..." along with it, so
# this is a plain removal instead, applied to the whole document text before
# anchors are found.
def test_ad_credit_removed_inline():
    check("trailing credit, no www.",
          AD_CREDIT_RE.sub(" ", "4080 Visit: adda247.com").strip(), "4080")
    check("mid-passage credit leaves what follows",
          " ".join(AD_CREDIT_RE.sub(
              " ", "equal in each city. Visit: adda247.com Note- Married couples."
          ).split()),
          "equal in each city. Note- Married couples.")


def test_error_spotting_segments():
    _, opts = split_options("Why we do not (a)/ meet to discuss (b)/ this matter (c)/ on Friday? (d)/ No error. (e)")
    check("error-spotting segments", list(opts.values()),
          ["Why we do not", "meet to discuss", "this matter", "on Friday?", "No error."])

# --- Hindi ------------------------------------------------------------------
# Removing runs (not truncating at the first Devanagari char) keeps Latin
# labels inside a Hindi direction; truncation wiped them to "".
def test_hindi_stripping():
    check("hindi run removal keeps labels",
          strip_hindi("दिए गए (a) यदि x >y (b) यदि x <y"),
          "(a) x >y (b) x <y")
    check("english + appended hindi",
          strip_hindi("14 years 14 वर्त"),
          "14 years 14")

# --- latex round trip -------------------------------------------------------
def test_latex_round_trip():
    check("to_latex fraction",
          to_latex("15/100 × 200/700 × ? = 240"),
          r"\frac{15}{100} \times \frac{200}{700} \times ? = 240")
    check("to_latex leaves prose alone", to_latex("Choose the correct word."), None)
    check("display fraction", display(r"\frac{15}{100} \times ? = 240"), "15/100 × ? = 240")
    check("display exponent", display(r"2x^{2} – 3x"), "2x² – 3x")
    check("display inequality", display(r"K \geq T \leq B"), "K ≥ T ≤ B")


if __name__ == "__main__":
    # No framework needed: run every test_* in this file, die on the first
    # failure. pytest discovers the same functions when it is available.
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL {name}: {exc}", file=sys.stderr)
    if failures:
        sys.exit(1)
    print("  OK — all parser regression cases pass")

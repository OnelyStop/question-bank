#!/usr/bin/env python3
"""Maths formatting: every case here changed the value of a question.

A wrong option that looks plausible is worse than a missing one -- nobody
reviews "4.49" and thinks to check it was "4.49" in the paper too. These lock
down the conversions where a small slip silently means different arithmetic.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import check, step  # noqa: E402

parser = step("1-extract", "parser")
to_latex, display = parser.to_latex, parser.display


def test_fractions():
    check("plain fraction",
          to_latex("15/100 × 200/700 × ? = 240"),
          r"\frac{15}{100} \times \frac{200}{700} \times ? = 240")
    # 2/33 and 8/9 have no Unicode vulgar glyph; the LaTeX still has to be right.
    check("fraction with no unicode glyph", to_latex("2/33 × 99"),
          r"\frac{2}{33} \times 99")


def test_roots_convert_before_fractions():
    # "√16/2" is √16 over 2 = 2. Converting the fraction first gives
    # \sqrt{\frac{16}{2}} = √8 = 2.83 -- a different number, and nothing in the
    # output looks wrong.
    check("root binds to its radicand only",
          to_latex("√16/2 = ?"), r"\frac{\sqrt{16}}{2} = ?")
    check("cube root", to_latex("∛1331 + 4 = ?"), r"\sqrt[3]{1331} + 4 = ?")
    check("fourth root", to_latex("∜16"), r"\sqrt[4]{16}")
    check("root left alone beside an operator",
          to_latex("√1225 ÷ 5"), r"\sqrt{1225} \div 5")


def test_mixed_numbers():
    # "87 1/3 %" is eighty-seven and a third percent, one quantity. A space
    # between the integer and the fraction reads as 87 × 1/3.
    check("mixed number has no space",
          to_latex("87 1/3 % of 900"), r"87\frac{1}{3} \% of 900")
    check("mixed number renders as one value",
          display(r"87\frac{1}{3} \%"), "87⅓ %")


def test_percent_is_escaped():
    # A bare % opens a comment in LaTeX: everything after it on the line
    # disappears when rendered. 55 option values were affected.
    check("percent escaped", to_latex("50% of 200 = ?"), r"50\% of 200 = ?")
    check("percent survives the round trip", display(r"50\% of 200 = ?"),
          "50% of 200 = ?")


def test_operators():
    check("times and div", to_latex("144 ÷ 12 × 3"), r"144 \div 12 \times 3")
    check("inequalities", to_latex("12 ≥ x ≤ 20"), r"12 \geq x \leq 20")


def test_prose_is_not_latex():
    # Only mathy strings convert. Wrapping prose would put backslashes through
    # every English question in the bank.
    check("prose returns None", to_latex("Choose the correct word."), None)
    check("prose with a year returns None",
          to_latex("Which bank was founded in 1955?"), None)


def test_display_round_trip():
    for latex, want in (
        (r"\frac{15}{100} \times ? = 240", "15/100 × ? = 240"),
        (r"2x^{2} – 3x", "2x² – 3x"),
        (r"K \geq T \leq B", "K ≥ T ≤ B"),
        (r"\sqrt[3]{1331}", "∛1331"),
    ):
        check(f"display {latex}", display(latex), want)


def test_latex_braces_balance():
    # An unbalanced brace renders as garbage downstream, so check_questions
    # rejects it -- the parser must never emit one.
    for src in ("15/100 × 200/700", "√16/2", "∛1331 + 4", "87 1/3 %", "√1225 ÷ 5"):
        out = to_latex(src)
        assert out is not None, f"expected latex for {src!r}"
        assert out.count("{") == out.count("}"), f"unbalanced braces from {src!r}: {out!r}"


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))

#!/usr/bin/env python3
"""The validators themselves.

check_questions.py and check_layout.py are what stops a bad batch merging, and
until now nothing checked them. A rule whose regex quietly stops matching still
prints "OK" -- the gate reports success having caught nothing, which is the
same failure that let a papers=0 scan pass as clean.

Each rule is asserted twice: it fires on the defect it was written for, and it
stays quiet on a clean question. The second half matters more -- a rule that
flags everything gets switched off.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import QUESTION_FIELDS, check, check_in, check_not_in, paper, question, step  # noqa: E402

gate = step("5-validate", "check_questions")
layout = step("5-validate", "check_layout")
gaps = step("1-extract", "check_gaps")

HERE = Path("data/batch5/1.json")


def defects(*questions_) -> list[str]:
    return gate.check_paper(HERE, paper(*questions_))


def test_clean_question_passes():
    check("no defect in a clean question", defects(question()), [])


def test_required_fields():
    check("contract is 16 fields", len(QUESTION_FIELDS), 16)
    check("gate requires exactly the contract",
          sorted(gate.REQUIRED), sorted(QUESTION_FIELDS))
    q = question()
    del q["year"]
    check_in("missing field caught", "missing fields", defects(q))


def test_schema_drift():
    # schema.json is additionalProperties:false, so a field the parser writes
    # and the schema does not declare is rejected at import -- after the batch
    # has merged. `corrected` reached 18 questions across 10 files that way:
    # REQUIRED only asks what must be PRESENT, and check_examples validates the
    # per-step examples rather than the committed data.
    declared = gate.schema_fields()
    check_in("undeclared field caught", "not in schema.json",
             gate.check_paper(HERE, paper(question(confidence=0.97)), declared))
    check("a clean question passes",
          gate.check_paper(HERE, paper(question()), declared), [])
    # The field this PR adds has to be declared, or every corrected question
    # trips the rule above.
    check("corrected is declared", "corrected" in declared, True)
    check("the step-1 contract is a subset of the schema",
          sorted(set(QUESTION_FIELDS) - declared), [])


def test_answer_key_bleed():
    q = question(options={"a": "1", "b": "2", "c": "3", "d": "4", "e": "155.56% Ans.(b)"})
    check_in("Ans.(b) caught", "answer_key_bleed", defects(q))


def test_direction_bleed():
    q = question(options={"a": "A", "b": "B", "c": "C", "d": "D",
                          "e": "No combination fits Directions (32-34):"})
    check_in("direction in an option caught", "direction_bleed", defects(q))


def test_raised_operator():
    # Superscript garbling: "⁺ ? ⁼ ³⁵" is never real content.
    check_in("raised operator caught", "raised_operator",
             defects(question(stem="2 ⁺ 4 ⁼ ³⁵")))


def test_raised_ordinal():
    # "28^(th) June" -- a date read as an exponent. 141 of these shipped.
    check_in("date suffix caught", "raised_ordinal",
             defects(question(stem="Who was born on 28^(th) June?")))
    check_in("in a direction too", "raised_ordinal",
             defects(question(direction_text="F was born on 16^(th) June.")))
    # A real exponent must still pass, or the rule would reject correct maths.
    check_not_in("real exponent not flagged", "raised_ordinal",
                 defects(question(stem=r"Find (?)^(4 \times 16 \div 32 + 1)")))
    check_not_in("prose ordinal not flagged", "raised_ordinal",
                 defects(question(stem="Who was born on 28th June?")))


def test_placeholder_stem():
    check_in("stem that is only its number", "placeholder_stem",
             defects(question(stem="Question 66.")))


def test_boilerplate():
    check_in("coaching-house footer", "boilerplate",
             defects(question(stem="Visit www.bankersadda.com for more")))


def test_solution_bleed():
    check_in("worked solution", "solution_bleed",
             defects(question(stem="Find x. Sol. x = 4 because")))


def test_empty_and_misnamed_options():
    check_in("empty option value", "empty option",
             defects(question(options={"a": "1", "b": "  ", "c": "3"})))
    check_in("option key outside a-e", "option key",
             defects(question(options={"a": "1", "f": "2"})))


def test_unbalanced_braces():
    check_in("unbalanced latex", "unbalanced braces",
             defects(question(stem=r"\frac{15}{100")))
    check_not_in("balanced latex passes", "unbalanced braces",
                 defects(question(stem=r"\frac{15}{100} \times ?")))


def test_duplicate_q_num():
    check_in("same number twice", "duplicate q_num",
             defects(question(q_num=7), question(q_num=7)))


def test_empty_scan_is_a_failure():
    # A root that does not exist wrote a report full of zeros and exited 0.
    # Scanning nothing is a broken path, not a clean bill of health.
    # stderr is captured: the gate prints "::error::", which GitHub would turn
    # into a CI annotation on a run where nothing is actually wrong.
    noise = io.StringIO()
    with contextlib.redirect_stderr(noise):
        code = gate.main(["data/does-not-exist"])
    check("no papers -> exit 1", code, 1)
    check_in("says why", "no papers found", noise.getvalue())


# --- what is missing --------------------------------------------------------
def test_gap_classes():
    # A question with no options is unanswerable however it got that way.
    check_in("no options is a gap", "no_options",
             gaps.question_gaps({"stem": "What is 2 + 2?", "options": {}}))
    # An error-spotting set puts its task in the direction and prints only the
    # five candidates, so a blank stem there is the paper's shape, not a gap.
    check("direction-supplied stem is not a gap",
          gaps.question_gaps({"stem": "", "options": {"a": "1", "b": "2"},
                              "direction_text": "Choose the sentence with an error."}),
          [])
    check_in("blank stem with no direction is a gap", "empty_stem",
             gaps.question_gaps({"stem": "", "options": {"a": "1"}, "direction_text": ""}))
    check_in("a stem that is only its number", "placeholder_stem",
             gaps.question_gaps({"stem": "Question 66.", "options": {"a": "1"}}))
    # Which exam a paper is cannot be read off the page -- that is research.
    check_in("missing exam_type is a paper gap", "no_exam_type",
             gaps.paper_gaps({"bank": "IBPS", "role": "RRB", "year": 2021,
                              "exam_type": None, "questions": []}))
    check("a complete paper has no gaps",
          gaps.paper_gaps({"bank": "IBPS", "role": "RRB", "year": 2021,
                           "exam_type": "Prelims", "questions": []}), [])


# --- folder ownership -------------------------------------------------------
def test_layout_allows_what_belongs():
    for path in ("tests/test_parser.py", "tests/harness.py",
                 "data/batch5/1.json", "data/batch5/1.pdf",
                 "data/batch5/index.json", "data/batch5/gap_report.json",
                 "corpus/remaining/IBPS/PO/2022/Mains/_unknown_shift/a.pdf",
                 "corpus/done/IBPS/PO/2022/Mains/_unknown_shift/a.pdf.meta.json",
                 "pipeline/1-extract/parser.py", "README.md"):
        check(f"allowed: {path}", layout.violation(path), None)


def test_layout_rejects_old_and_stray_paths():
    for path, reason in (
        ("data/papers/x.json", "old layout"),
        ("corpus/pdf/x.pdf", "old corpus layout"),
        ("data/batch5/notes.txt", "stray file in a batch"),
        ("pipeline/9-nope/x.py", "not a pipeline step"),
        ("tests/notes.md", "not a Python module"),
        ("tests/fixtures.py", "support module not on the allowed list"),
        ("scratch.py", "unknown top-level entry"),
    ):
        assert layout.violation(path) is not None, f"should be rejected ({reason}): {path}"


if __name__ == "__main__":
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))


# --- can the review PDF be read? --------------------------------------------
# The JSON gates say nothing about the PDFs, and the PDF is what a person opens
# to decide whether a parse is right. A batch reached review with 43 "<U+20B9>"
# escapes in one paper and correct JSON underneath, with every check green.
def test_render_escape_detection():
    render = step("5-validate", "check_render")
    check("plain text is fine", render.ESCAPE_RE.findall("Rs 10,000 for UPI Lite"), [])
    check("an escape is caught",
          render.ESCAPE_RE.findall("<U+20B9>10,000 and <U+2192> x"),
          ["<U+20B9>", "<U+2192>"])
    # Lower case too: the escape is written upper case, but a check that only
    # matched one case would pass a file it should reject.
    check("case does not matter", render.ESCAPE_RE.findall("<U+20b9>"), ["<U+20b9>"])
    check("a lone angle bracket is not an escape",
          render.ESCAPE_RE.findall("x < U + 1 > y"), [])


def test_render_gate_fails_on_a_missing_pdf(tmp_path=None):
    import json as _json
    import tempfile
    from pathlib import Path as _Path

    render = step("5-validate", "check_render")
    with tempfile.TemporaryDirectory() as d:
        root = _Path(d) / "batch99"
        root.mkdir()
        (root / "1.json").write_text(_json.dumps(paper(question())))
        noise = io.StringIO()
        with contextlib.redirect_stderr(noise):
            code = render.main([str(root)])
        check("a paper with no PDF fails", code, 1)
        check_in("says which", "no review PDF", noise.getvalue())


def test_render_gate_empty_scan_is_a_failure():
    render = step("5-validate", "check_render")
    noise = io.StringIO()
    with contextlib.redirect_stderr(noise):
        code = render.main(["data/does-not-exist"])
    check("nothing scanned -> exit 1", code, 1)
    check_in("says why", "no review PDFs found", noise.getvalue())

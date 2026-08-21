#!/usr/bin/env python3
"""Which ten PDFs a batch gets, and that it's the same ten on every machine.

The batch issues list an exact ten filenames computed once, on Linux. If
`collect_pdfs` ever orders `corpus/remaining/` differently on Windows, a
contributor running there parses the wrong ten PDFs into a batch number that
means nothing.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import check, step  # noqa: E402

parser = step("1-extract", "parser")
collect_pdfs = parser.collect_pdfs
SKIP_NAME_RE = parser.SKIP_NAME_RE
pdf_source_ref = parser.pdf_source_ref


def test_order_is_case_sensitive_posix_not_native_path_sort():
    # "_unknown_bank" vs "IBPS": Path's native comparison sorts these
    # case-insensitively on Windows (`_` < `i`) and case-sensitively on Linux
    # (`I` < `_`) -- different platforms, different "first ten". POSIX-string,
    # case-sensitive sorting is the one order that matches on both, and it's
    # the one the batch issues were written against.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel in (
            "_unknown_bank/x.pdf",
            "IBPS/Clerk/a.pdf",
            "IBPS/PO/b.pdf",
        ):
            f = root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"")

        got = [p.relative_to(root).as_posix() for p in collect_pdfs(root)]
        check(
            "IBPS/ sorts before _unknown_bank/ (case-sensitive POSIX order)",
            got,
            ["IBPS/Clerk/a.pdf", "IBPS/PO/b.pdf", "_unknown_bank/x.pdf"],
        )


def test_answers_pdf_without_the_word_key_is_skipped():
    # A real one from corpus/remaining/: "IBPS-PO-2016-English-Answers-1.pdf"
    # is a solutions PDF ("S101. (c); Sol. ...") same as any "...Answer-Key.pdf",
    # but the old pattern required a literal "key" and let this one through --
    # it parsed to a correct-but-useless 0 questions, burning a batch slot.
    check(
        "bare 'Answers' is a solutions filename",
        bool(SKIP_NAME_RE.search("IBPS-PO-2016-English-Answers-1")),
        True,
    )


def test_existing_answer_key_naming_still_skips():
    check(
        "'Answer-Key' still skips (regression)",
        bool(SKIP_NAME_RE.search("SBI-Clerk-MBT-22nd-Feb-Tamil-File-with-answer-key")),
        True,
    )


def test_a_real_paper_named_answer_is_not_skipped():
    # The heuristic is a filename token, not a substring: a paper about
    # "General Awareness" must not be caught by "answer".
    check(
        "'Awareness' does not contain the 'answer' token",
        bool(SKIP_NAME_RE.search("IBPS-Clerk-General-Awareness-2023")),
        False,
    )


def test_single_file_is_returned_as_is():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "one.pdf"
        f.write_bytes(b"")
        check("a single PDF path passes through unchanged", collect_pdfs(f), [f])


def test_source_ref_uses_forward_slashes_on_any_os():
    # str(Path) serializes with the native separator. On Windows that wrote
    # "corpus\done\..." into a committed JSON while every batch generated on
    # Linux has "corpus/done/..." -- the same field, two different values
    # depending on who ran the parser.
    check(
        "repo-relative path uses forward slashes",
        pdf_source_ref(parser.REPO / "corpus" / "done" / "IBPS" / "a.pdf"),
        "corpus/done/IBPS/a.pdf",
    )


def test_source_ref_outside_repo_falls_back_to_posix_too():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "sub" / "b.pdf"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"")
        check(
            "path outside REPO also comes back forward-slashed",
            pdf_source_ref(f),
            f.as_posix(),
        )


if __name__ == "__main__":
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))

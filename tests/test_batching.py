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


def test_single_file_is_returned_as_is():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "one.pdf"
        f.write_bytes(b"")
        check("a single PDF path passes through unchanged", collect_pdfs(f), [f])


if __name__ == "__main__":
    from run_tests import run_module  # noqa: E402

    sys.exit(run_module(sys.modules[__name__]))

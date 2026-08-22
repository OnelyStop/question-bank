#!/usr/bin/env python3
"""Reject a review PDF that cannot be read.

check_questions.py reads the JSON. Nothing read the PDFs, and they are the
artifact a human actually opens to decide whether a parse is right -- so a
batch could be reviewed, approved and merged with a PDF full of "<U+20B9>"
while every gate stayed green. That is what happened: 43 escapes in one paper,
34 of them the rupee sign, with correct JSON underneath.

The cause is worth knowing, because the check alone does not fix it. render()
draws with Arial Unicode and falls back to Latin-1 when it is missing, turning
every unmapped character into "<U+XXXX>". Both paths it looks in are macOS-only,
so the PDF you get depends on the machine that ran the parser, and it degrades
without saying anything.

    python3 pipeline/5-validate/check_render.py            # all data/batch*/
    python3 pipeline/5-validate/check_render.py data/batch7
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parents[2]

# What flatten() emits for a character the font could not draw.
ESCAPE_RE = re.compile(r"<U\+[0-9A-Fa-f]{4,6}>")

# A page of a review PDF is mostly text. Far less than this means the render
# produced a document that looks fine in a file listing and is blank to read.
MIN_CHARS_PER_PAGE = 40


def check_pdf(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        doc = fitz.open(path)
    except Exception as exc:
        return [f"unreadable ({exc})"]

    with doc:
        pages = len(doc)
        if pages == 0:
            return ["no pages"]
        text = "\n".join(p.get_text() for p in doc)

    escapes = ESCAPE_RE.findall(text)
    if escapes:
        counts: dict[str, int] = {}
        for e in escapes:
            counts[e] = counts.get(e, 0) + 1
        shown = ", ".join(f"{k} x{n}" for k, n in
                          sorted(counts.items(), key=lambda kv: -kv[1])[:5])
        errs.append(
            f"{len(escapes)} unrenderable character(s): {shown} — "
            "the Unicode font was missing when this was rendered"
        )

    if len(text.strip()) < MIN_CHARS_PER_PAGE * pages:
        errs.append(f"only {len(text.strip())} characters over {pages} pages — near-empty render")

    return errs


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    roots = [Path(a) for a in args] or sorted((REPO / "data").glob("batch*"))

    papers = 0
    checked = 0
    failures: list[str] = []

    for root in roots:
        for jsonp in sorted(root.glob("[0-9]*.json")):
            papers += 1
            pdf = jsonp.with_suffix(".pdf")
            rel = pdf.relative_to(REPO) if pdf.is_relative_to(REPO) else pdf

            # A paper with no PDF beside it is a paper nobody can review.
            if not pdf.is_file():
                failures.append(f"{rel}: missing — {jsonp.name} has no review PDF")
                continue

            checked += 1
            for err in check_pdf(pdf):
                failures.append(f"{rel}: {err}")

    # Scanning nothing is a broken path, not a clean bill of health -- the same
    # failure this repo has shipped twice. Counted on the JSONs, not the PDFs:
    # keyed on PDFs, a batch whose papers ALL lack one reported "no review PDFs
    # found", which reads as a bad path rather than as ten missing files.
    if papers == 0:
        print(f"::error::no papers found under {[str(r) for r in roots]}",
              file=sys.stderr)
        return 1

    if failures:
        print(f"{len(failures)} problem(s) across {checked} review PDFs:\n", file=sys.stderr)
        for f in failures[:40]:
            print(f"  {f}", file=sys.stderr)
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more", file=sys.stderr)
        print("\n  A '<U+XXXX>' means the renderer could not draw that character.",
              file=sys.stderr)
        print("  Install Arial Unicode and re-render with rerender.py — the JSON",
              file=sys.stderr)
        print("  is usually fine, so the batch does not need parsing again.",
              file=sys.stderr)
        return 1

    print(f"  OK — {checked} review PDFs, all readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The one PDF reader shared by more than one step.

Kept out of `corpus.py` on purpose: that module must stay importable without
PyMuPDF, because 2-classify depends on it and has no reason to read a PDF.

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    from pdf import extract_pages
"""

from __future__ import annotations

from pathlib import Path

import fitz


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    doc = fitz.open(pdf_path)
    pages: list[tuple[int, str]] = []
    try:
        for i, page in enumerate(doc, start=1):
            pages.append((i, page.get_text() or ""))
    finally:
        doc.close()
    return pages

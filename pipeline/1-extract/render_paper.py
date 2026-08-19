#!/usr/bin/env python3
"""Render a paper's JSON back to a readable PDF, for checking it by eye.

Extraction defects are obvious on a page and invisible in JSON — a stem that
lost its middle, options that ran together, a direction attached to the wrong
questions. This writes <paper>.pdf beside <paper>.json so a person can flip
through and see them.

    python3 pipeline/1-extract/render_paper.py                    # every paper
    python3 pipeline/1-extract/render_paper.py --paper data/papers/.../x.json
    python3 pipeline/1-extract/render_paper.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / "data" / "papers"

PAGE = fitz.paper_rect("a4")
MARGIN = 48.0
BODY = 9.5
LEAD = 1.35

SKIP = {"parse_report.json", "index.jsonl", "question_bank.schema.json"}


class Sheet:
    """A PDF being written top-down, breaking pages when it runs out of room."""

    def __init__(self, title: str) -> None:
        self.doc = fitz.open()
        self.title = title
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE.width, height=PAGE.height)
        self.y = MARGIN
        n = self.doc.page_count
        self.page.insert_text(
            (MARGIN, PAGE.height - 28), f"{self.title}  ·  page {n}",
            fontsize=7.5, color=(0.45, 0.45, 0.45),
        )

    def write(self, text: str, *, size: float = BODY, bold: bool = False,
              indent: float = 0.0, gap: float = 3.0, colour=(0, 0, 0)) -> None:
        if not text:
            return
        font = "hebo" if bold else "helv"
        width = PAGE.width - 2 * MARGIN - indent
        # measure first: insert_textbox returns <0 when the text will not fit
        need = fitz.get_text_length(text, fontname=font, fontsize=size)
        lines = max(1, int(need / max(width, 1)) + 1)
        height = lines * size * LEAD + gap

        if self.y + height > PAGE.height - MARGIN:
            self._new_page()

        box = fitz.Rect(MARGIN + indent, self.y, PAGE.width - MARGIN, PAGE.height - MARGIN)
        used = self.page.insert_textbox(
            box, text, fontname=font, fontsize=size, color=colour, lineheight=LEAD,
        )
        if used < 0:                      # did not fit: start a page and retry once
            self._new_page()
            box = fitz.Rect(MARGIN + indent, self.y, PAGE.width - MARGIN, PAGE.height - MARGIN)
            used = self.page.insert_textbox(
                box, text, fontname=font, fontsize=size, color=colour, lineheight=LEAD,
            )
        self.y += height

    def rule(self) -> None:
        if self.y + 10 > PAGE.height - MARGIN:
            self._new_page()
            return
        self.page.draw_line(
            fitz.Point(MARGIN, self.y), fitz.Point(PAGE.width - MARGIN, self.y),
            color=(0.85, 0.85, 0.85), width=0.5,
        )
        self.y += 8


def render(paper: dict, out: Path) -> int:
    pid = paper.get("paper_id") or out.stem
    sheet = Sheet(pid)

    bits = [paper.get("bank"), paper.get("role"), paper.get("exam_type"),
            str(paper.get("year") or ""), paper.get("shift")]
    sheet.write(pid, size=12, bold=True, gap=2)
    sheet.write("  ".join(b for b in bits if b), size=9, colour=(0.4, 0.4, 0.4))
    qs = paper.get("questions") or []
    sheet.write(f"{len(qs)} questions", size=9, colour=(0.4, 0.4, 0.4), gap=8)
    sheet.rule()

    seen_direction: str | None = None
    for q in qs:
        d_id = q.get("direction_id")
        d_text = q.get("direction_text")
        if d_text and d_id != seen_direction:
            sheet.write(d_text, size=9, bold=True, colour=(0.15, 0.15, 0.45), gap=6)
            if q.get("direction_has_image") or q.get("direction_image_refs"):
                sheet.write("[figure referenced by this direction]", size=8,
                            colour=(0.6, 0.3, 0.1), gap=4)
            seen_direction = d_id

        sheet.write(f"{q.get('q_num')}. {q.get('stem') or '(no stem)'}", gap=2)
        opts = q.get("options") or {}
        if not opts:
            sheet.write("(no options)", size=8.5, indent=14, colour=(0.7, 0.2, 0.2))
        for k in sorted(opts):
            sheet.write(f"({k}) {opts[k]}", size=9, indent=14, gap=1.5)

        extras = []
        if q.get("answer"):
            extras.append(f"answer: {q['answer']}")
        if q.get("has_image"):
            extras.append("needs a figure")
        if extras:
            sheet.write("   ".join(extras), size=8, indent=14,
                        colour=(0.2, 0.5, 0.2), gap=2)
        sheet.rule()

    sheet.doc.save(str(out), deflate=True)
    pages = sheet.doc.page_count
    sheet.doc.close()
    return pages


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--paper", type=Path, help="render one paper only")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    if args.paper:
        files = [args.paper]
    else:
        files = sorted(p for p in args.root.rglob("*.json") if p.name not in SKIP)
    if args.limit:
        files = files[: args.limit]

    made = 0
    for path in files:
        try:
            paper = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  skip {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(paper, dict) or not paper.get("questions"):
            continue
        out = path.with_suffix(".pdf")
        pages = render(paper, out)
        made += 1
        print(f"  {out.relative_to(REPO)}  {len(paper['questions'])} questions, {pages} pages")

    print(f"\n  rendered {made} papers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Redraw one paper's review PDF from its JSON, without parsing anything.

Some defects are not worth a parser change: a stacked fraction whose numerator
is an expression, a layout one paper uses once. The JSON is the product, so fix
it there -- but re-running the batch to redraw one page is ten PDFs of work for
one line, and it re-derives nine papers that were already right.

    python3 pipeline/1-extract/rerender.py data/batch9/1.json
    python3 pipeline/1-extract/rerender.py --fix data/batch9/1.json
    python3 pipeline/1-extract/rerender.py data/batch9/*.json

`--fix` re-applies corrections.json to the questions before drawing, so a
hand-written fix lands in the JSON the same way a parsed one does and survives
the next full run of the batch. Without it the JSON is only redrawn.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parser import apply_correction, load_corrections, render  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("papers", type=Path, nargs="+", help="one or more <n>.json")
    ap.add_argument("--fix", action="store_true",
                    help="apply corrections.json to the JSON before drawing")
    args = ap.parse_args(argv)

    fixes = load_corrections() if args.fix else {}
    if args.fix and not fixes:
        print("  --fix given but corrections.json is empty", file=sys.stderr)
        return 1

    for path in args.papers:
        if not path.is_file():
            print(f"  no such paper: {path}", file=sys.stderr)
            return 1
        paper = json.loads(path.read_text(encoding="utf-8"))
        if "questions" not in paper:
            print(f"  not a paper: {path}", file=sys.stderr)
            return 1

        touched = []
        if fixes:
            fixed = []
            for q in paper["questions"]:
                out = apply_correction(q, fixes)
                if out is not q:
                    touched.append(out["q_num"])
                fixed.append(out)
            paper["questions"] = fixed
            if touched:
                path.write_text(json.dumps(paper, indent=2, ensure_ascii=False),
                                encoding="utf-8")

        pages = render(paper, path.with_suffix(".pdf"))
        note = f"  corrected q{touched}" if touched else ""
        print(f"  {path.name} -> {path.with_suffix('.pdf').name}"
              f"  {len(paper['questions'])} questions, {pages} pages{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

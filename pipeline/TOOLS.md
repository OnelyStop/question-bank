# tools

## pdf_pipeline/

Builds (or rebuilds) `India/banking/papers/` from PDFs.

```bash
python tools/pdf_pipeline/pdf_question_pipeline.py --pdf path/to/paper.pdf --force --skip-answers
```

See `pdf_pipeline/README.md`. Needs `pymupdf`.

## beautify.py

Turns a slice of `India/banking/sets/extracted.json` into a publishable set.

```bash
python3 tools/beautify.py 1        # builds set 1
python3 tools/beautify.py 1 2 3    # several at once
```

Writes four files per set into `sets/` — `usable/N.pdf`, `usable/N.json`,
`flagged/N.pdf`, `flagged/N.csv`. Runs from any working directory; paths resolve against the repo.

Needs `fpdf2` and `pillow`, and reads `Arial Unicode.ttf` / `Arial Bold.ttf` from
`/System/Library/Fonts/Supplemental/` — change `FONT_REG` / `FONT_BOLD` at the top
of the script to run it off macOS. The font matters: the base-14 PDF fonts have no
glyph for `≤ ≥ √ ² ⅔`, which is why the earlier review PDFs rendered `if x ≥ y` as
`if x ? y`.

It does two separate things and does not mix them. **Repair** handles damage with
exactly one correct answer — a footer welded to an option, a URL, a publisher's
name inside the narrative. **Flag** refuses to guess: a question whose seating
arrangement was never extracted, or whose stacked fraction collapsed into loose
digits, cannot be reconstructed, so it goes to `flagged/` with a reason instead of
shipping as though it were fine.

## assets_classified.json

`filename -> chart | solution | ad` for every image the extractor pulled out
alongside a question.

This has to be done by eye, and it is not optional. Most of what the extractor
attached to a question is **not** the question's chart — it is a coaching-house
advert, or a working diagram from the answer key. Set 1 had 42 unique images: 8
real charts, 20 solution diagrams, 14 adverts.

An image missing from this file is treated as not-a-chart, so every question in
its set lands in `flagged/` as `chart_missing`. The script prints a warning when a
slice references unclassified images — heed it, or the output will look like a
data problem when it is really an unfinished classification pass.

**All ten sets are built.** Classification covers every image that could change
an outcome: 173 of the 917 the extractor attached. The other 744 hang off
questions that never mention a chart, so they are dropped either way and
reviewing them would change nothing. The warning only fires for the ones that
matter.

## verify.py

```bash
python3 tools/verify.py
```

Re-reads the published sets and scans them for what cleaning was supposed to
remove — brands, URLs, source-book titles, characters from the broken font
mappings — and reconciles clean + flagged against the input. A cleaner made of
regexes fails silently when a regex stops matching; this is what makes that loud.
Exits non-zero on any leak.

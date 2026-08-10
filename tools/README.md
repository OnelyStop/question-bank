# tools

## beautify.py

Turns a slice of `India/banking/raw/ready.json` into a publishable set.

```bash
python3 tools/beautify.py 1        # builds set 1
python3 tools/beautify.py 1 2 3    # several at once
```

Writes four files per set — `cleaned/N.pdf`, `cleaned/N.json`, `flagged/N.pdf`,
`flagged/N.csv`. Runs from any working directory; paths resolve against the repo.

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

**Only set 1 is classified.** Sets 2-10 need their images reviewed before they
can be built, and set 2 also carries footer patterns the cleaner has not seen yet
(62 questions trip `brand_residue` on a trial run).

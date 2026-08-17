# 1 — extract

PDFs in, one JSON file per paper out.

**Reads** `corpus/pdf/{bank}/{role}/{year}/{stage}/*.pdf`
**Writes** `corpus/papers/{bank}/{role}/{year}/{stage}/{shift}/{paper_id}.json`

This is the hardest step and everything downstream inherits its mistakes.

## What it has to do

**Read layout, not text.** Exam PDFs are two-column with options in a grid.
Flat text extraction interleaves the columns and scrambles option order. Work
from character positions.

**OCR only where needed.** Some pages have no text layer, or a broken one. Detect
that per page rather than OCR-ing everything — OCR is slow and worse than a good
text layer.

**Find direction blocks.** "Directions (11–15): Study the following…" applies to
questions 11 through 15. Emit one `direction_id` per block and attach every
question in its range. 71% of questions belong to one, so getting the ranges
wrong breaks most of the bank.

**Drop the Hindi.** Bilingual papers put the Devanagari immediately after the
English, in the same block. The first attempt appended it to the English stem —
1,350 questions came out that way, and **95 of the 134 PDFs that produced nothing
were Hindi editions.** The export is English-only, so detect the Devanagari and
cut it rather than concatenating it into `stem`.

**Options as an object**, keyed `a`–`e`, not an array. Watch for stacked
fractions: `87 3/7 %` arriving as `87 3 %` is a question that no longer means
what it meant. Better to flag it than to emit it looking fine.

**Crop the figures.** Set `has_image`, and write the image to a file that
`image_refs` or `direction_image_refs` can point at. **This was never done** —
986 questions are flagged as needing a figure with no file behind it, which makes
them unanswerable. For a passage set the chart belongs to the passage
(`direction_image_refs`), not to each question.

**Derive the metadata** — `bank`, `role`, `exam_type`, `year`, `shift` — from the
path and filename. Anything you can't determine becomes `_unknown_*` rather than
a guess.

## Output

[`output.json`](output.json) — one question, **17 of the 28 fields** in
[`schema/schema.json`](../../schema/README.md).

Every field name here is a schema field. There is no separate paper shape and no
intermediate format: each step fills more of the same object.

The passage travels on the question — `direction_text`, `direction_has_image`,
`direction_image_refs` — so a question is self-contained from the start. Note the
chart belongs to the **passage**, not the question: 902 of 986 figure questions
are in a passage set.

`answer`, `section`, `topic`, `difficulty`, `question_pattern`, `content_hash`,
`direction_hash` and `is_active` are absent on purpose. Later steps add them.

Also write `parse_report.json`: per-PDF status, question count, and what couldn't
be read. The previous run's report is what told us 134 of 379 PDFs produced
nothing, so make this honest.

## Done when

- Every PDF in the manifest either produces a paper or appears in the report
  with a reason.
- Question counts are plausible — a prelims paper is 100 questions, mains 155.
- Spot-check ten papers against the PDF by eye. Option order and direction ranges
  are what break silently.

## What's here

| | |
|---|---|
| `pdf_to_questions.py` | 939 lines, the main pass |
| `layout_parse.py` | 578 lines, column and block geometry |
| `page_stream.py` | 291 lines, character positions from PyMuPDF |
| `ocr_supplement.py` | the OCR fallback |
| `filename_parser.py` | filename → exam metadata |

Needs `pip install pymupdf`. The previous run produced 243 papers and 21,044
questions from 379 PDFs — recover it with
`git checkout c73426f -- corpus/papers` to compare against.

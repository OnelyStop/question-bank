Questions held back from the cleaned sets, with the reason on each.

`N.pdf` shows the question as it survived cleaning with its flag underneath.
`N.csv` is the same list as `question_id, reasons, stem` for triage.

1,255 of 4,851 are held back. What they are:

| count | reason | what happened |
|---|---|---|
| 705 | **chart_missing** | The question asks about a graph or table, and the image extracted alongside it was an advert or a solution diagram — so the data it needs is nowhere on the page. 419 of these are set 5 alone. |
| 327 | **fraction_flattened** | A stacked fraction collapsed into loose digits: `30 10/13 %` arrived as `30 10 13 %`. The intended value is not recoverable. |
| 319 | **option_bleed** | The next question, or a block of solution working, is still welded onto an option and could not be cut cleanly. |
| 60 | **stem_too_short** | Nothing survived cleaning that reads as a question. |
| 58 | **context_missing** | A puzzle question whose seating plan or arrangement was never extracted. Unanswerable by anyone, not just by us. |
| 56 | **language_hindi** | Asked only in Hindi, with no English half to keep. Bilingual questions are *not* here — those are cleaned and kept. |
| 45 | **text_garbled** | Characters survive from a broken font mapping that had no digit to recover. Shown as ▫ in the PDF. |
| 41 | **context_unusable** | The shared directions survived only as a dump of the whole page. |
| 37 | **stem_truncated** | The stem stops mid-sentence. |
| 22 | **option_duplicate** | Two options are identical once cleaned — the extractor copied one over another. |
| 20 | **option_empty** | An option cleaned away to nothing. |
| 8 | **brand_residue** | A coaching brand or URL survived cleaning and would otherwise have shipped. |
| 4 | **equation_degraded** | An equation lost its exponent, so it no longer matches the answer key it was given. |

Most are fixable by going back to the source PDF for that one question — they are
all in `products/corpus/`. `chart_missing` needs the right image cropped out of
the source page; `context_missing` needs the arrangement re-extracted for the
whole set at once; `fraction_flattened` needs the stacked fraction read by eye.

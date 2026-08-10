Questions held back from the cleaned sets, with the reason on each.

`N.pdf` shows the question as it survived cleaning with its flag underneath.
`N.csv` is the same list as `question_id, reasons, stem` for triage.

The flags, and what each one means:

| reason | what happened |
|---|---|
| **chart_missing** | The question asks about a graph or table, and the image extracted alongside it was an advert or a solution diagram — so the data it needs is nowhere on the page. |
| **context_missing** | A puzzle question whose seating plan or arrangement was never extracted. Unanswerable by anyone, not just by us. |
| **fraction_flattened** | A stacked fraction collapsed into loose digits: `30 10/13 %` arrived as `30 10 13 %`. The intended value is not recoverable. |
| **option_bleed** | The next question's text is still welded onto an option and could not be cut cleanly. |
| **option_duplicate** | Two options are identical once cleaned, which means the extractor copied one over another. |
| **equation_degraded** | An equation lost its exponent, so it no longer matches the answer key it was given. |
| **stem_truncated** | The stem stops mid-sentence. |
| **brand_residue** | A coaching brand or URL survived cleaning and would otherwise have shipped. |

Most of these are fixable by going back to the source PDF for that one question.
`chart_missing` needs the right image cropped out of the source page;
`context_missing` needs the arrangement re-extracted for the whole set at once.

# sets

4,851 questions pooled from 58 source PDFs, deduped, and split into ten sets of
500. **3,596 are usable and 1,255 are held back**, each with a reason.

```
extracted.json   what came out of the source PDFs, damage and all
usable/          N.pdf + N.json  - 3,596 questions, ready to use
flagged/         N.pdf + N.csv   - 1,255 held back, with a reason each
charts/          the 50 images a question genuinely needs
```

`usable/N.json` and `usable/N.pdf` hold the same questions in the same order, so
"question 198 in set 4" means one thing in either. Chart paths in the JSON are
relative to this folder (`charts/…`).

Built by `tools/beautify.py`, checked by `tools/verify.py`.

## Where these came from

Roughly half are real exam questions, half are from coaching books:

| | source PDFs | questions |
|---|---|---|
| Previous-year and memory-based papers | 30 | 2,246 |
| Coaching books and practice compilations | 28 | 2,605 |

The exam papers include IBPS Clerk Mains 2022-2024, SBI Clerk Mains 2021-2025,
the SBI 8th March shifts, and an RBI Assistant computer capsule. The books
include a large data-interpretation compilation, and the Ace and QUANTS series.

**This is not a separate universe from `../papers/`.** Six PDFs feed both, so
those questions exist twice in the repo, parsed two different ways:

```
IBPS-Clerk-Mains-2023-Memory-Based-1-1.pdf
IBPS-Clerk-Mains-Memory-Based-Paper-2024.pdf
IBPS-Clerk-Pre-Memory-Based-Paper-Mock-01-26.-Aug.2023.pdf
SBI-Clerk-Mains-Memory-Based-2023-2024.pdf
SBI_Clerk_Mains_2024_25_Memory_Based_Paper_10_04_2025_1st_shift.pdf
SBI_Clerk_Pre_2024_25_Memory_Based_Paper_22_Feb_2025_1st_shift_English.pdf
```

The difference is what each keeps. `../papers/` keeps a question with its paper —
which bank, which year, which shift. Here the questions are pooled and deduped
across every source, so provenance is dropped and what you get instead is a
usable/held-back judgement on each one.

## Usable

| set | usable | held | | set | usable | held |
|---|---|---|---|---|---|---|
| 1 | 392 | 108 | | 6 | 407 | 93 |
| 2 | 399 | 101 | | 7 | 296 | 204 |
| 3 | 457 | 43 | | 8 | 391 | 109 |
| 4 | 417 | 83 | | 9 | 421 | 79 |
| 5 | **81** | **419** | | 10 | 335 | 16 |

Directions shared by a set are printed once above the set, with the set's chart
under them, rather than repeated under every question.

**Set 5 is the outlier, and it is not a bug.** 479 of its 500 questions come from
one data-interpretation book, and only 40 have any image attached at all — the
graphs were never extracted, so those questions ask about data that is nowhere on
the page.

## Flagged

| count | reason | what happened |
|---|---|---|
| 705 | **chart_missing** | Asks about a graph or table whose image turned out to be an advert or a solution diagram. 419 are set 5. |
| 327 | **fraction_flattened** | A stacked fraction collapsed into loose digits: `30 10/13 %` arrived as `30 10 13 %`. |
| 319 | **option_bleed** | The next question, or a block of solution working, is still welded to an option. |
| 60 | **stem_too_short** | Nothing survived cleaning that reads as a question. |
| 58 | **context_missing** | A puzzle whose seating plan was never extracted. |
| 56 | **language_hindi** | Asked only in Hindi. Bilingual questions are *not* here — those keep their English half. |
| 45 | **text_garbled** | Characters survive from a broken font mapping. Shown as ▫ in the PDF. |
| 41 | **context_unusable** | Shared directions survived only as a dump of the whole page. |
| 37 | **stem_truncated** | The stem stops mid-sentence. |
| 22 | **option_duplicate** | Two options identical once cleaned. |
| 20 | **option_empty** | An option cleaned away to nothing. |
| 8 | **brand_residue** | A coaching brand or URL survived cleaning. |
| 4 | **equation_degraded** | An equation lost its exponent and no longer matches its key. |

Most are fixable one question at a time from the source PDFs in
`products/corpus/`. `chart_missing` needs the right image cropped from the source
page; `context_missing` needs the arrangement re-extracted for a whole set at
once; `fraction_flattened` needs the fraction read by eye.

## Bilingual questions

Some sources print each question in English and then again in Hindi, with options
like `Rs.21,083 crore / Rs.21,083 करोड़`. The English half is complete on its own,
so it is kept and the Hindi dropped. Only questions asked *solely* in Hindi are
held back.

Questions that are ready to use.

Two collections live here, from two different sources.

## question_bank/

Previous-year papers parsed from the source PDFs, organised
`{bank}/{role}/{year}/{stage}/{shift}/`, with `index.jsonl` for filtering and
`SCHEMA.md` describing the format. This is the primary bank.

## 1-10.pdf / 1-10.json

The coaching-book corpus in `../raw/ready.json`, built by `tools/beautify.py`:
**3,596 usable questions out of 4,851**, with 238 charts embedded. Same questions
in the PDF and the JSON, in the same order, so "question 198 in set 4" means one
thing in either.

| set | usable | held back | | set | usable | held back |
|---|---|---|---|---|---|---|
| 1 | 392 | 108 | | 6 | 407 | 93 |
| 2 | 399 | 101 | | 7 | 296 | 204 |
| 3 | 457 | 43 | | 8 | 391 | 109 |
| 4 | 417 | 83 | | 9 | 421 | 79 |
| 5 | **81** | **419** | | 10 | 335 | 16 |

A question in here carries only the question, its options, the answer, and — when
the question genuinely needs one — the chart or table. No source book, no
internal id, no publisher's name or URL. Directions shared by a set are printed
once above the set, with the set's chart under them, rather than repeated per
question. `tools/verify.py` re-reads the published output and fails if anything
cleaning was meant to remove survives.

**Set 5 is the outlier and it is not a bug.** 479 of its 500 questions come from
one data-interpretation book, and only 40 of them have any image attached at all
— the extractor never captured the graphs. Those questions ask about data that is
nowhere on the page, so they are held back. Recovering set 5 means going back to
`products/corpus/` and re-cropping the graphs from the source PDF.

The 1,255 held back are in `../flagged/` with a reason each, not silently dropped
and not silently included.

## Bilingual questions

Some papers print each question in English and then again in Hindi, with options
like `Rs.21,083 crore / Rs.21,083 करोड़`. The English half is complete on its own,
so it is kept and the Hindi half dropped. Only the 56 questions asked *only* in
Hindi are held back.

## The two collections are not reconciled

`question_bank/` is the better source — real papers rather than coaching reprints
— and its schema already carries the shared-directions grouping (`direction_id` /
`direction_text`) that these sets needed. What it has no equivalent for is the
quality gate in `../flagged/`: nothing in that schema decides whether a question
is answerable at all.

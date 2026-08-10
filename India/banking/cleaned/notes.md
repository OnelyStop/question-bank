Questions that are ready to use.

Two collections live here, from two different sources.

## question_bank/

Previous-year papers parsed from the source PDFs, organised
`{bank}/{role}/{year}/{stage}/{shift}/`, with `index.jsonl` for filtering and
`SCHEMA.md` describing the format. This is the primary bank.

## 1.pdf / 1.json

Set 1 of the coaching-book corpus in `../raw/ready.json` — 394 questions out of
the first 500, built by `tools/beautify.py`. Same questions in both files, same
order, so "question 198 in set 1" means one thing in either.

A question in here carries only the question, its options, the answer, and — when
the question genuinely needs one — the chart or table. No source book, no internal
id, no publisher's name or URL. Directions shared by a set are printed once above
the set, with the set's chart under them, rather than repeated per question.

The 106 that could not be made usable are in `../flagged/` with a reason each,
not silently dropped and not silently included.

Sets 2-10 are not built. The image classification in
`tools/assets_classified.json` only covers set 1, and running the pipeline over a
later set without extending it drops every chart in that set; the script warns
when that happens. Set 2 also carries footer patterns the cleaner has not been
taught yet.

The two collections have not been reconciled. `question_bank/` is the better
source — real papers rather than coaching reprints — and its schema already
carries the shared-directions grouping (`direction_id` / `direction_text`) that
set 1 needed. What it has no equivalent for is the quality gate in `../flagged/`:
nothing in the schema decides whether a question is answerable at all.

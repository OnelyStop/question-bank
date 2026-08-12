# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
India/banking/
  papers/    previous-year papers, kept whole and organised by exam
  sets/      questions pooled from many sources, cleaned and typeset
  corpus/    source PDFs for the papers pipeline (local; not in git)
tools/       scripts — pdf_pipeline/ builds papers/; beautify/verify handle sets/
```

Both hold real exam questions. They differ in what they keep.

## papers/

246 previous-year papers laid out by `{bank}/{role}/{year}/{stage}/{shift}/`,
plus `index.jsonl` for filtering without opening every file. A question here
stays attached to its paper: which bank, which year, which shift.

`papers/SCHEMA.md` has the format. Questions carry `direction_id` /
`direction_text` so a puzzle or DI set stays linked to its shared passage, and
`metrics` records what the parser could and could not see.

## sets/

4,851 questions pooled from 58 PDFs — about half previous-year and memory-based
papers, half coaching books — deduped across all of them and split into ten sets
of 500. Provenance is dropped; what you get instead is a judgement on each
question. **3,596 are usable, 1,255 are held back with a reason.**

That distinction is the point. A question whose seating arrangement was never
extracted cannot be answered by anyone, and a question whose stacked fraction
collapsed into loose digits no longer means what it meant. Those are quarantined
rather than shipped looking sound.

Six PDFs feed both collections, so some questions appear in each, parsed two
different ways. `sets/README.md` lists them.

## What a question looks like

Only the question, its options, the answer, and — where the question genuinely
needs one — the chart or table. No source book, no internal id, no coaching
brand, no URL. `tools/verify.py` re-reads the published output and fails if any
of that survives.

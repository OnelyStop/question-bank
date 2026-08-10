# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
India/banking/
  papers/          previous-year papers, parsed from the official PDFs
  practice-sets/   questions from coaching books, cleaned and typeset
tools/             the scripts that build and check practice-sets/
```

## papers/

The primary collection: 246 previous-year papers laid out by
`{bank}/{role}/{year}/{stage}/{shift}/`, plus `index.jsonl` for filtering without
opening every file. `papers/SCHEMA.md` describes the format — questions carry
`direction_id` / `direction_text` so a puzzle or DI set stays linked to its shared
passage, and `metrics` records what the parser could and could not see.

## practice-sets/

4,851 questions extracted from coaching books, split into ten sets of 500.
**3,596 are usable and 1,255 are held back**, each with a reason.

The distinction is the point. A question whose seating arrangement was never
extracted cannot be answered by anyone, and a question whose stacked fraction
collapsed into loose digits no longer means what it meant. Those are quarantined
rather than shipped looking sound. See `practice-sets/README.md`.

## What a question looks like

Only the question, its options, the answer, and — where the question genuinely
needs one — the chart or table. No source book, no internal id, no coaching
brand, no URL. `tools/verify.py` re-reads the published output and fails if any
of that survives.

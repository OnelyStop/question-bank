# 3 — answer

Fill in `answer`, and later `explanation`.

**Reads** `corpus/papers/` and any answered source in `corpus/`
**Writes** the same files, with `answer` and `explanation` added

**Right now the export has 0 answers out of 18,651.** Nothing works without this
step — no practice, no scoring, no marking, no progress tracking. It is the single
most valuable thing in the pipeline.

## Two sources

**1. Answer keys in the PDFs.** Most papers carry a key at the back, sometimes as
a grid, sometimes as a table of `q_num → option`. Map it onto the questions.
`attach_answers.py` (771 lines) was written for this and never successfully ran —
it now has the 375 PDFs in `corpus/pdf/` to run against, so this is the primary
path rather than the blocked one.

**2. Stem match against an answered collection.** The `sets/` collection in git
history has 3,596 questions answered under `correct_option`, and **1,126 of them
matched a paper question by stem**:

```bash
git checkout ce4d92f -- corpus/sets
```

That's about 6% of the bank, and it needs no PDFs. Worth doing if answers become
urgent before the corpus is recovered.

## The rule that matters

**A wrong answer is worse than no answer.** A blank question is visibly
incomplete; a wrong one teaches the wrong thing and users won't report it, they'll
just stop trusting the app.

So gate every match:

- The **numeric tuple must be identical.** Two questions can share every word and
  differ only in a number — 105 such pairs exist in a 3,596-question sample, with
  different answers. Never carry an answer across one of those.
- The **option set must agree.** Same stem with different options is a different
  question.
- Write every match *and* every near-miss to `answer_report.json`, with both
  stems, so a human can audit the borderline ones.

When two sources disagree on the same question, record both and pick neither.
There were 25 such conflicts inside `sets/` alone.

## explanation

Generated, not extracted — the PDFs don't contain worked solutions. That's a
separate pass once answers exist, and the answer has to be right before an
explanation of it is worth anything.

Budget note: ~600 characters each across 20,000 questions is about 12 MB in
Postgres and a few dollars of tokens for one pass. Generate once and store it;
regenerating per view costs more than storing it for years.

## Output

[`output.json`](output.json) — step 2's 21 fields plus two:

```
answer   explanation
```

23 of 28. `answer` is the option **key** (`"a"`), not an index.

Record which source produced each answer in `answer_report.json`, not on the
question. `pdf_key` and `stem_match` have very different reliability, and when a
wrong answer surfaces you need to trace it — but that belongs in the report, not
the export.

## Done when

- Answer coverage is reported honestly, per source, in `answer_report.json`.
- Every answer is a key that exists in that question's `options`.
- A sample of 100 answers is checked by hand against the source PDF. This is the
  one step where sampling by eye is not optional.

## What's here

| | |
|---|---|
| `attach_answers.py` | 771 lines, answer-key extraction from PDFs. Unproven |
| `validate_answers.py` | 314 lines, sanity checks on extracted answers |

Treat both as a starting point. Neither has ever produced a single answer that
reached the export.

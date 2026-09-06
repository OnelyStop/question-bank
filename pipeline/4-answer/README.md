# 4 — answer

Fill in `answer`, and later `explanation`.

**Reads** step 3's deduped questions + `dedupe_report.json` · **Writes** the same,
with `answer` and `explanation` added

Running after dedupe means answering **19,443 unique questions instead of
21,044** — 1,601 lookups saved, and they come off the most expensive path.

**Right now the export has 0 answers.** Nothing works without this
step — no practice, no scoring, no marking, no progress tracking. It is the single
most valuable thing in the pipeline.

## Subscription-agent handoff (no API)

Use this when answers are reviewed by a ChatGPT/Codex subscription agent rather
than an API. Export is read-only and splits unanswered questions into small JSONL
batches. Give an agent one batch at a time and require one JSONL response per
line in this exact shape:

```json
{"q_id":"exact exported id","answer":"a","explanation":"optional concise reasoning"}
```

The importer is dry-run by default. It rejects unknown IDs, answers not present
in a question's options, malformed records, duplicates that disagree, and any
attempt to overwrite a different existing answer. Review the report before
writing; subscription-agent answers are recorded as low-confidence review data,
not as PDF-derived keys.

```bash
python pipeline/4-answer/export_agent_batches.py --out data --export-dir data/agent_answer_batches --batch-size 25
python pipeline/4-answer/export_agent_batches.py --out data --export-dir data/agent_explanation_batches --mode explanations --batch-size 25
python pipeline/4-answer/import_agent_answers.py --out data --responses data/agent_answer_responses
python pipeline/4-answer/import_agent_answers.py --out data --responses data/agent_answer_responses --require-explanation --apply
```

For an explanation task, the export includes the existing validated answer.
The response must repeat that option key and add `explanation`; the importer
rejects any changed answer key and never replaces an existing explanation.

Plan the handoffs and independently audit all already-attached answers before
any import. Both commands are read-only with respect to question JSON:

```bash
python pipeline/4-answer/plan_answer_review.py --out data --handoff-size 25 --report data/answer_review_plan.json
python pipeline/4-answer/verify_answer_quality.py --out data --sample-size 250
```

## Where the answers are

I scanned all 375 PDFs. **69% carry a machine-readable answer key:**

| Format | PDFs | |
|---|---|---|
| `S{n}. Ans.(x)` + `Sol.` | **218** | 58% |
| grid — `1. (c); 2. (b);` | 34 | 9% |
| `Ans.` with no solutions | 7 | 2% |
| **nothing** | **116** | **31%** |

**23,630 answer markers** in total, and **15,926 `Sol.` blocks** — worked
solutions, not just keys.

**1. `S{n}. Ans.(x)` + `Sol.` — build this first.** 58% of PDFs, one regex pair,
and `{n}` joins straight to `q_num`:

```
Solutions
S1. Ans.(c)
Sol. The correct choice is option (c) which can be inferred from the first
     paragraph which mentions, "The rise in smartphone use…"
S2. Ans.(d)
```

Capture the solution up to the next `S{n}. Ans.` marker — GA and DI solutions run
several paragraphs with sub-headings, RC ones are a single sentence.

**2. Grid format** — 34 PDFs, `1. (c); 2. (b); 3. (c);` interleaved with prose.

**3. Separate solution PDFs** — `*-Solutions.pdf`, `*_SOL.pdf`, `*-Answers-1.pdf`
hold answers with no questions. Pair them to their question paper by exam, year
before the `q_num` join works.

**4. Use the provenance map.** A merged question lists every `(paper_id, q_num)`
it came from. If the first paper has no key, try the others — that's what
`dedupe_report.json` is for.

**5. Web search, last.** For the ~31% with no key anywhere. Expensive and
unverifiable, so it runs on the smallest possible set — which is why this step
comes after dedupe.

**6. Stem match** against the old `sets/` collection in git history
(`git checkout ce4d92f -- corpus/sets`) — 3,596 answered questions, 1,126 of
which matched a paper question.

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

**Extracted, not generated.** The `Sol.` blocks are worked solutions — 15,926 of
them across the corpus. Take those verbatim rather than asking an LLM: they're
the publisher's own working, they cost nothing, and they can't hallucinate a
wrong method for a right answer.

Only generate for questions where no `Sol.` block exists, and only after the
answer is confirmed.

## Output

[`output.json`](output.json) — step 3's 24 fields plus two:

```
answer   explanation
```

26 of 28. `answer` is the option **key** (`"a"`), not an index. The last two are
`marks` and `negative_marks`, absent while they equal their defaults.

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
| `export_agent_batches.py` | Read-only JSONL export of unanswered questions for subscription-agent review |
| `import_agent_answers.py` | Dry-run-by-default validation and import of agent answer JSONL |
| `plan_answer_review.py` | Read-only per-source-batch queue and coverage plan |
| `verify_answer_quality.py` | Read-only answer/explanation audit and independent review queue |
| `export_agent_batches.py` | read-only unanswered-question batches for subscription agents |
| `import_agent_answers.py` | strict validation and opt-in application of agent responses |

Treat both as a starting point. Neither has ever produced a single answer that
reached the export.

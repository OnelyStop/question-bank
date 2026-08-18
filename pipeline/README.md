# pipeline

Five steps. One folder each, one owner each.

```
corpus/  ->  1-extract  ->  2-classify  ->  3-dedupe  ->  4-answer  ->  data/
                                                              |
                                                          5-validate
```

| Step | Does | Blocked by |
|---|---|---|
| [1-extract](1-extract/) | PDFs → one JSON per paper | nothing — the PDFs are here |
| [2-classify](2-classify/) | adds `section`, `topic`, `question_pattern` | nothing |
| [3-dedupe](3-dedupe/) | keeps one copy of each question | nothing |
| [4-answer](4-answer/) | adds `answer`, `explanation`, writes the export | nothing |
| [5-validate](5-validate/) | refuses to ship a broken export | nothing |
| [lib](lib/) | shared helpers | — |

Each step reads the previous step's output and writes the same shape back, so a
step can be re-run on its own without re-running the ones before it. Only step 4
changes the shape, into the flat export.

## What each step adds

Every folder has an `output.json` — the exact shape that step must produce. The
same question runs through all five, so you can diff one against the next.

| After | Fields | Gains |
|---|---|---|
| [1-extract](1-extract/output.json) | 17 / 28 | `stem` `options` `direction_text` + the exam metadata |
| [2-classify](2-classify/output.json) | 21 / 28 | `section` `topic` `difficulty` `question_pattern` |
| [3-dedupe](3-dedupe/output.json) | 24 / 28 | `content_hash` `direction_hash` `is_active` |
| [4-answer](4-answer/output.json) | 26 / 28 | `answer` `explanation` |
| [5-validate](5-validate/output.json) | — | a report, not questions |

**There is one shape, not four.** Every field in every `output.json` is a field in
[`schema/schema.json`](../schema/README.md); each step fills more of the same
question object. No paper wrapper, no intermediate format, nothing to translate
between steps.

The last two of the 28 are `marks` and `negative_marks`, which stay absent while
they equal their defaults (`1`, `-0.25`).

Anything a step needs for its own auditing — label confidence, which source an
answer came from, what merged with what — goes in that step's report file, not on
the question.

## Working on one step

Each folder's README says what its step reads, what it must write, and how to
tell it worked. You shouldn't need to read another step's code to do yours — if
you do, that's a bug in the interface between them, worth raising.

The contract between steps is the paper JSON. Its final shape, after step 4, is
[`schema/schema.json`](../schema/README.md); steps 1–3 work with the same fields
nested inside a paper file rather than flattened.

## State of the code

The files in each folder are from the first attempt at this. **They are a
starting point, not a working pipeline** — they were written as one tangled run
with three overlapping entry points, and the entry points have been deleted.
What's left is the parts with real logic in them:

| | |
|---|---|
| 1-extract | 2,039 lines — layout parsing, OCR fallback, filename/path parsing |
| 2-classify | the topic taxonomy and 14 pattern detectors; **this one works** |
| 3-dedupe | nothing yet |
| 4-answer | 1,085 lines of answer-key extraction, never successfully run |
| 5-validate | two narrow checks |

Expect to rewrite the orchestration. Expect the parsing details to be worth
keeping.

## The PDFs are here

375 of the 379 source PDFs are committed under `corpus/pdf/`, each with a
`.meta.json` sidecar, at the path step 1 reads. **Nothing is blocked any more** —
step 1 can run, and everything downstream follows from it.

Two things came with them:

- **414 MB in git history.** Removing it later needs a rewrite, so if more
  batches are coming, decide on Git LFS before they land rather than after.
- **RRB papers are filed two ways** — 52 as `bank=IBPS, role=RRB` and 28 as
  `bank=null, role=RRB`. Same exam family, two buckets. Step 1 will emit
  `_unknown_bank` for the second set until that's reconciled.

# pipeline

Five steps. One folder each, one owner each.

```
corpus/  ->  1-extract  ->  2-classify  ->  3-answer  ->  4-dedupe  ->  data/
                                                              |
                                                          5-validate
```

| Step | Does | Blocked by |
|---|---|---|
| [1-extract](1-extract/) | PDFs → one JSON per paper | needs the source PDFs |
| [2-classify](2-classify/) | adds `section`, `topic`, `question_pattern` | nothing |
| [3-answer](3-answer/) | adds `answer`, `explanation` | needs PDFs or an answered source |
| [4-dedupe](4-dedupe/) | keeps one copy of each question, writes the export | nothing |
| [5-validate](5-validate/) | refuses to ship a broken export | nothing |
| [lib](lib/) | shared helpers | — |

Each step reads the previous step's output and writes the same shape back, so a
step can be re-run on its own without re-running the ones before it. Only step 4
changes the shape, into the flat export.

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
| 3-answer | 1,085 lines of answer-key extraction, never successfully run |
| 4-dedupe | nothing yet |
| 5-validate | two narrow checks |

Expect to rewrite the orchestration. Expect the parsing details to be worth
keeping.

## The one thing blocking everything

The source PDFs were never committed to this repo. 379 of them, listed at
`git checkout 6da6705 -- corpus/PDF-MANIFEST.md`. Without them steps 1 and 3
can't run, and 2, 4 and 5 have nothing to read.

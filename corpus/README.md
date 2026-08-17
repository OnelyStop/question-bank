# corpus

Everything the pipeline reads. Two sources, both raw:

```
papers/    243 papers, 21,044 questions          extracted from the source PDFs
sets/      4,851 questions from 58 other PDFs    3,596 of them answered
```

Nothing here is cleaned — that's the point. Cleaning is what the pipeline does,
and its output goes to [`data/`](../data/README.md).

## The source PDFs are not here

Tens of gigabytes of exam papers, never committed to this repo. Without them:

| | |
|---|---|
| `answer` | only 1,126 questions can be answered, by matching `sets/` |
| `image_refs` | 986 questions need a figure that was never extracted |
| re-extraction | a parser fix can't be re-run over the papers |

If they're recovered, they go in `corpus/pdf/` (gitignored), and layout matters —
the pipeline reads the path to work out which exam a PDF is:

```
corpus/pdf/{bank}/{role}/{year}/{stage}/ibps_clerk_2019_mains.pdf
```

A PDF that doesn't match lands in an `_unknown_*` bucket. The `_unknown` folders
in `papers/` are the ones that didn't match.

## papers/ — the extraction, as it came out

243 papers, 21,044 questions, one file per paper, laid out
`{bank}/{role}/{year}/{stage}/{shift}/`. A question stays attached to its paper,
so you always know which exam it came from.

**It is raw, and it needs work the pipeline hasn't done yet:**

- **1,350 questions (6%) are bilingual** — the Hindi is appended to the English
  stem and options, across 35 papers. Stripping it is step 2's job.
- **No answers.** Not one.
- **986 questions flagged `has_image` with no figure**, because the extraction
  never cropped them.
- Duplicates across papers, since memory-based papers repeat questions.

There was a second folder, `papers-deduped/`, holding a cleaned pass — Hindi
stripped, deduped, split by subject. It's deleted. It was pipeline output living
in the source tree, it held 2,393 fewer questions than `papers/`, and keeping
both meant every script had to pick one. The cleaning it did belongs in the
pipeline, where it can be re-run.

`papers/` is now the single source. Until the PDFs come back it is also the only
copy of that extraction — treat it as irreplaceable.

## sets/ — the only answers in the repo

4,851 questions pooled from 58 PDFs, deduped and split into ten sets of 500.
Provenance is dropped; each question carries a judgement instead.

```
usable/          3,596 questions, all answered
flagged/         1,255 held back, each with a reason
charts/          the 50 images a question genuinely needs
extracted.json   what came out of the PDFs, damage and all
```

**All 3,596 usable questions have an answer**, under `correct_option` — the only
answer data anywhere here. **1,126 of them match a question in `papers/` by
stem**, which is how step 3 fills answers without the PDFs.

The 1,255 flagged ones are held back for real reasons: a seating arrangement that
was never extracted can't be answered by anyone, and a stacked fraction that
collapsed into loose digits no longer means what it meant. Quarantined rather
than shipped looking fine.

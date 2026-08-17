# corpus

Everything the pipeline reads. Nothing here is clean — that's the point. The
clean output goes to [`data/`](../data/README.md).

```
pdf/              the source PDFs                        (gitignored, EMPTY)
papers/           243 papers, 21,106 questions           extracted from those PDFs
papers-deduped/   235 papers, 18,651 questions           a second, lossy pass
sets/             4,851 questions pooled from 58 PDFs    3,596 of them answered
```

## pdf/ — empty, and it's the main problem

Tens of gigabytes of exam PDFs, never committed. Without them:

| | |
|---|---|
| `answer` | only 1,126 questions can be answered, by matching `sets/` |
| `image_refs` | 986 questions need a figure that was never extracted |
| re-extraction | a parser fix can't be re-run over the papers |

Layout matters — `pipeline` reads the path to work out which exam a PDF is:

```
pdf/{bank}/{role}/{year}/{stage}/ibps_clerk_2019_mains.pdf
```

A PDF that doesn't match lands in an `_unknown_*` bucket. The `_unknown` folders
in `papers/` are the ones that didn't match.

## papers/ vs papers-deduped/ — neither is complete

This is the thing to know before building anything. They were produced by
separate runs and **each holds questions the other doesn't**:

| | Distinct stems |
|---|---|
| `papers/` | 17,227 |
| `papers-deduped/` | 16,710 |
| only in `papers/` | **1,408** |
| only in `papers-deduped/` | **891** |
| **union** | **18,118** |

`papers-deduped/` calls itself "a strict subset that adds nothing". That is
wrong — it adds 891 stems `papers/` doesn't have.

So neither folder is the source of truth. **Step 4 builds from the union of
both** and dedupes there, which recovers 1,408 questions the current export is
missing. Dedup is a pipeline step, not a folder.

Both are also irreplaceable while `pdf/` is empty — this JSON is the only copy of
that extraction.

## sets/ — the only answers in the repo

4,851 questions pooled from 58 PDFs, deduped and split into ten sets of 500.
Provenance is dropped; each question carries a judgement instead.

```
usable/    3,596 questions, all answered
flagged/   1,255 held back, each with a reason
charts/    the 50 images a question genuinely needs
extracted.json   what came out of the PDFs, damage and all
```

**All 3,596 usable questions have an answer**, under `correct_option`. That's the
only answer data anywhere in this repo, and 1,126 of them match a question in
`papers/` by stem — which is how step 3 fills answers without the PDFs.

The 1,255 flagged ones are held back for real reasons: a seating arrangement
that was never extracted can't be answered by anyone, and a stacked fraction
that collapsed into loose digits no longer means what it meant. Quarantined
rather than shipped looking fine.

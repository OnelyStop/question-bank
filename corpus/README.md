# corpus

Everything the pipeline reads. **Empty right now.**

```
PDF-MANIFEST.md    the 379 source PDFs to recover
```

Drop source material in here — PDFs under `pdf/`, or extracted JSON in its own
folder per batch. Overlap is expected and fine: step 4 dedupes, and it's built on
the assumption that the same question arrives many times from many sources.

Nothing in here is ever cleaned in place. Cleaning is what the pipeline does, and
its output goes to [`data/`](../data/README.md).

## The source PDFs

Tens of gigabytes of exam papers, **never committed to this repo**. In all of git
history the only PDFs are 20 typeset files that `beautify.py` generated. The
originals are on the machine that ran the first extraction.

[`PDF-MANIFEST.md`](PDF-MANIFEST.md) lists all 379 by name — 245 that produced a
paper and 134 that produced nothing, **95 of those Hindi editions** of papers
whose English version parsed fine. That's the list to ask for, and the retry list
once step 1 handles Devanagari properly instead of appending it to the English.

Restore them under `corpus/pdf/` (gitignored), keeping the manifest's relative
paths. Layout matters — the pipeline reads the path to work out which exam a PDF
is:

```
corpus/pdf/{bank}/{role}/{year}/{stage}/ibps_clerk_2019_mains.pdf
```

## What used to be here

Both were the old pipeline's output, and output doesn't belong in the source
tree. Both are in git history:

```bash
git checkout c73426f -- corpus/papers   # 243 papers, 21,044 questions, no answers
git checkout ce4d92f -- corpus/sets     # 4,851 questions, 3,596 of them answered
```

`sets/` is worth knowing about if answers become urgent — it's the only answered
question data that has ever existed here, and 1,126 of those answers matched a
paper question by stem.

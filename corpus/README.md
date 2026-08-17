# corpus

Everything the pipeline reads.

```
sets/              4,851 questions from 58 PDFs, 3,596 answered
PDF-MANIFEST.md    the 379 source PDFs to recover
```

Nothing here is cleaned — that's the point. Cleaning is what the pipeline does,
and its output goes to [`data/`](../data/README.md).

## The source PDFs are missing

Tens of gigabytes of exam papers. **They were never committed to this repo** — in
all of git history the only PDFs are the 20 typeset files under `sets/`. The
originals are on the machine that ran the first extraction.

[`PDF-MANIFEST.md`](PDF-MANIFEST.md) lists all 379 of them by name: 245 that
produced a paper and 134 that produced nothing. It's the list to ask for.

Restore them under `corpus/pdf/` (gitignored), keeping the manifest's relative
paths. Layout matters — the pipeline reads the path to work out which exam a PDF
is:

```
corpus/pdf/{bank}/{role}/{year}/{stage}/ibps_clerk_2019_mains.pdf
```

A PDF that doesn't match lands in an `_unknown_*` bucket.

**95 of the 134 failures are Hindi editions** of papers whose English version
parsed fine — worth retrying once step 1 handles Devanagari properly rather than
appending it to the English text.

Until the PDFs are back, step 1 can't run and there are no papers. What was
previously extracted from them lived in `corpus/papers/` and has been deleted, on
the grounds that pipeline output does not belong in the source tree. It is still
in git history:

```bash
git checkout c73426f -- corpus/papers    # 243 papers, 21,044 questions
```

## sets/ — the only questions and the only answers right now

4,851 questions pooled from 58 PDFs, deduped and split into ten sets of 500.
Provenance is dropped; each question carries a judgement instead.

```
usable/          3,596 questions, all answered
flagged/         1,255 held back, each with a reason
charts/          the 50 images a question genuinely needs
extracted.json   what came out of the PDFs, damage and all
```

**All 3,596 usable questions have an answer**, under `correct_option`. That makes
this the only usable question data in the repo today.

The 1,255 flagged ones are held back for real reasons: a seating arrangement that
was never extracted can't be answered by anyone, and a stacked fraction that
collapsed into loose digits no longer means what it meant. Quarantined rather
than shipped looking fine.

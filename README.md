# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
data/       the questions themselves — hand-checked, not regenerable
pipeline/   the code that produced them
schema/     what every file is shaped like
scripts/    typesetting and the publish-time checks
```

Everything under `data/` is a source. Everything a pipeline writes is ignored by
git and rebuilt on demand, so nothing in here is both large and derivable.

## data/

| | Papers | Questions | Answers |
|---|---|---|---|
| **`papers/`** | 243 | 21,106 | — |
| **`papers-deduped/`** | 235 | 18,651 | — |
| **`sets/usable/`** | — | 3,596 | **all** |

`papers/` and `papers-deduped/` are previous-year papers laid out as
`{bank}/{role}/{year}/{stage}/{shift}/`, with an `index.jsonl` for filtering
without opening every file. A question here stays attached to its paper: which
bank, which year, which shift. The deduped pass drops 8 papers the full set
keeps, which is the only reason both are here — `papers/` is the superset and
the one to reach for if a paper seems to be missing.

`sets/` pools questions from 58 PDFs — about half previous-year and
memory-based papers, half coaching books — deduped across all of them and split
into ten sets of 500. Provenance is dropped; what you get instead is a
judgement on each question. 3,596 are usable, 1,255 are held back with a
reason.

That distinction is the point. A question whose seating arrangement was never
extracted cannot be answered by anyone, and a question whose stacked fraction
collapsed into loose digits no longer means what it meant. Those are
quarantined rather than shipped looking sound.

**`sets/usable/` is the only place answers currently live**, under
`correct_option`. The papers pipeline carries none — see below.

Six PDFs feed both collections, so some questions appear in each, parsed two
different ways. `data/sets/README.md` lists them.

## pipeline/

```
pdf/             source PDFs → data/papers/           (needs the corpus)
patterns/        classifies each question into 14 patterns
feature_tables/  → the six tables the app imports
```

Run them from the repo root; the defaults resolve to `data/`.

```bash
python3 pipeline/patterns/run_pipeline.py                  # → pipeline/patterns/out/
python3 pipeline/feature_tables/build_feature_tables.py    # → pipeline/feature_tables/out/
```

`build_feature_tables.py` emits `papers`, `directions`, `questions` and three
empty per-user tables (`attempts`, `attempt_answers`, `user_topic_stats`) that
the app fills at runtime. Current output: 235 papers, 3,039 directions, 18,651
questions, 121 canonical.

## Two things to know before relying on this

**The source PDFs are not in git.** `data/corpus/` is gitignored and absent, so
`pipeline/pdf/` cannot run and the JSON under `data/` is the only copy of that
extraction. Treat it as irreplaceable.

**The papers pipeline has no answers — 0 of 18,651.** The 3,596 answered
questions in `data/sets/usable/` are not wired into it; the two collections were
built by separate paths and never joined. Answering the papers set means either
running `pipeline/pdf/attach_answers.py` against a restored corpus, or matching
`sets/` questions back onto their papers by stem.

## What a question looks like

Only the question, its options, the answer, and — where the question genuinely
needs one — the chart or table. No source book, no internal id, no coaching
brand, no URL. `scripts/verify.py` re-reads the published output and fails if
any of that survives.

Formats are in `schema/schema.json` — one file, covering the paper files, the
index rows, and the 14 question patterns. The app's database tables are defined
in the frontend repo, not here.

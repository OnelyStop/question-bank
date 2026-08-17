# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
data/       the questions — the only copy, not regenerable
pipeline/   the code that produced them
schema/     what one exported question looks like
scripts/    typesetting and publish-time checks
```

Anything a pipeline writes is gitignored and rebuilt on demand, so nothing here
is both large and derivable.

## The data

| | Papers | Questions | Answers |
|---|---|---|---|
| `data/papers/` | 243 | 21,106 | none |
| `data/papers-deduped/` | 235 | 18,651 | none |
| `data/sets/usable/` | — | 3,596 | **all** |

**Papers** are laid out as `{bank}/{role}/{year}/{stage}/{shift}/`. A question
stays attached to its paper, so you always know which exam it came from.
`papers/` is the superset — the deduped pass drops 8 papers it keeps.

**Sets** pool questions from 58 PDFs, deduped and split into ten sets of 500.
Provenance is dropped; instead each question gets a judgement. 3,596 are usable,
1,255 are held back with a reason — a question whose seating arrangement was
never extracted can't be answered by anyone, so it's quarantined rather than
shipped looking fine.

## The pipeline

Five steps, one file each.

| Step | In → out | Needs | Status |
|---|---|---|---|
| **1. extract** | PDFs → paper JSON | the corpus | **blocked** — corpus is gone |
| **2. classify** | + `section`, `topic`, `question_pattern` | nothing | **works, not wired in** |
| **3. answer** | + `answer`, `explanation` | corpus, or a match against `sets/` | **blocked** |
| **4. build** | → `questions.jsonl.gz` | nothing | works |
| **5. validate** | checks the export against `schema/schema.json` | nothing | works |

Steps 2, 4 and 5 need only the JSON in `data/`, so they run today. Only 1 and 3
depend on the missing PDFs.

### What runs right now

```bash
python3 pipeline/patterns/run_pipeline.py                 # classify patterns
python3 pipeline/feature_tables/build_feature_tables.py   # build the export
python3 pipeline/patterns/validate.py pipeline/patterns/out/questions.jsonl
```

Output today: **235 papers, 3,039 directions, 18,651 questions.**

### Step 2 is the one worth doing next

The section and topic classifier already exists — `pipeline/pdf/label_sections.py`
and `label_topics.py`, with a taxonomy in `topic_taxonomy.json`. It reads the
paper JSON, not the PDFs, and run against `data/papers-deduped` today it labels
**13,569 of 18,651 questions (73%)**:

| | Now | After step 2 |
|---|---|---|
| `section` | 17% | **73%** |
| `topic` | 0% | **73%** |

Subtopics it produces: Data_Interpretation (1,606), Seating_Arrangement (1,377),
Error_Spotting (1,359), Arithmetic (1,220), Reading_Comprehension (987).

It has never been wired into the export, and it currently won't even import —
it sits in `pipeline/pdf/` and inherits an `import fitz` from `pdf_to_questions`
that it doesn't need. Splitting the steps apart fixes that.

## What gets exported

One flat file. Each question carries everything needed to filter it (bank, role,
year, section, pattern) and render it — no second file, no join.

```json
{
  "q_id": "ibps_clerk_2019_mains_781623cd::q095",
  "stem": "What is the ratio of marked price to selling price of article C?",
  "options": { "a": "4 : 3", "b": "3 : 4", "c": "4 : 7", "d": "7 : 4", "e": "4 : 5" },
  "answer": "b",
  "direction_hash": "9f3c1ab77e40d215",
  "direction_text": "Line chart given below shows markup percent...",
  "bank": "IBPS", "role": "Clerk", "year": 2019,
  "section": "Quantitative", "question_pattern": "shared_directions_set"
}
```

Full field list in [`schema/`](schema/README.md). Two things worth knowing:

- **The file and your database are different shapes.** In the file, all 6
  questions of a passage set carry the passage text. In the database that column
  doesn't exist — the text lives once in a `passages` table and each question
  keeps the 16-character `direction_hash`.
- **Ship it gzipped.** 23 MB becomes 3 MB, because the repeated passages
  compress away.

In Postgres the whole bank is about **18 MB**, or **30 MB** once explanations
are written.

## Status

| Step | | |
|---|---|---|
| 1. Extract | done | `stem` 99%, `options` 98% |
| 2. Classify patterns | done | `question_pattern` 100% |
| 2. Classify section/topic | **built, never run** | would go 17% → 73% and 0% → 73% |
| **3. Answers** | **not done** | **0 of 18,651** |
| 4. Build | done | 235 papers, 18,651 questions |
| 5. Validate | done | 21,044 rows, 0 errors |

## Two things to know first

**The source PDFs are gone.** `data/corpus/` is gitignored and absent, so
`pipeline/pdf/` can't run and the JSON under `data/` is the only copy of that
extraction. Treat it as irreplaceable.

**Nothing has answers except `data/sets/usable/`.** Those 3,596 answered
questions were built by a separate path and never joined to the papers. Fixing
this means either restoring the corpus and running
`pipeline/pdf/attach_answers.py`, or matching `sets/` questions back onto their
papers by stem — step 3 above. The second needs no missing files.

Until that's done the export can't drive practice, scoring or marking.

**986 questions need a figure that doesn't exist.** They carry
`has_image: true` and no file reference; the extraction never produced the
images. Recovering them needs the corpus too.

## What a question contains

Only the question, its options, the answer, and — where it genuinely needs one —
the chart or table. No source book, no internal id, no coaching brand, no URL.
`scripts/verify.py` re-reads the published output and fails if any of that
survives.

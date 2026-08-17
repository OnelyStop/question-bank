# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
corpus/     everything the pipeline reads — PDFs and the raw extraction
data/       the clean output, one gzipped file
pipeline/   the five steps
schema/     what one exported question looks like
scripts/    typesetting and publish-time checks
```

`corpus/` is raw and messy by design; `data/` is generated and disposable.
Delete `data/`, re-run step 4, get it back.

Anything a pipeline writes is gitignored and rebuilt on demand, so nothing here
is both large and derivable.

## The data

| | Papers | Questions | Answers |
|---|---|---|---|
| `corpus/papers/` | 243 | 21,106 | none |
| `corpus/papers-deduped/` | 235 | 18,651 | none |
| `corpus/sets/usable/` | — | 3,596 | **all** |

**Papers** are laid out as `{bank}/{role}/{year}/{stage}/{shift}/`. A question
stays attached to its paper, so you always know which exam it came from.
**Neither folder is complete** — 1,408 distinct stems exist only in `papers/`
and 891 only in `papers-deduped/`, so step 4 builds from the union of both.

**Sets** pool questions from 58 PDFs, deduped and split into ten sets of 500.
Provenance is dropped; instead each question gets a judgement. 3,596 are usable,
1,255 are held back with a reason — a question whose seating arrangement was
never extracted can't be answered by anyone, so it's quarantined rather than
shipped looking fine.

## The pipeline

Not built yet. What exists in `pipeline/` is the old code — three overlapping
entry points, 37 files, and a classifier shelved inside the PDF folder where it
can't run. This is what replaces it: five steps, one file each.

```
corpus/  ->  1_extract  ->  2_classify  ->  3_answer  ->  4_build  ->  data/
                                                              |
                                                          5_validate
```

```
pipeline/
  1_extract.py    2_classify.py    3_answer.py    4_build.py    5_validate.py
  lib/            shared modules the steps import
```

| Step | Needs the PDFs? |
|---|---|
| 1. extract | **yes** — blocked |
| 2. classify | no |
| 3. answer | partly — 1,126 without them |
| 4. build | no |
| 5. validate | no |

Steps 2, 4 and 5 run on the JSON already in `corpus/`. That's the boundary the
old layout hid.

---

### 1. `1_extract.py` — PDFs to questions

**In** `corpus/pdf/**/*.pdf` · **Out** `corpus/papers/{bank}/{role}/{year}/{stage}/{paper_id}.json`

- Read each PDF page as a layout stream, not flat text — column order and
  option alignment both come from geometry.
- OCR only the pages where the text layer is missing or garbage.
- Detect direction blocks ("Directions (11–15): …") and attach every question in
  the range to one `direction_id`.
- Parse options into `{a: …, b: …}`, keyed not indexed.
- Flag figures: set `has_image`, and crop the chart to a file that
  `image_refs` / `direction_image_refs` can point at. **This is the part that
  was never done** — 986 questions are flagged with no file.
- Derive `bank`, `role`, `year`, `stage`, `shift` from the path and filename.
- Write `parse_report.json`: per-PDF status, question counts, what it couldn't
  read.

Needs PyMuPDF and a populated `corpus/pdf/`. Both missing today.

---

### 2. `2_classify.py` — label what each question is

**In** `corpus/papers/` · **Out** the same JSON, with labels added

- `section` — Quantitative, Reasoning, English, GA, Computer.
- `topic` — from `lib/topic_taxonomy.json`: Data_Interpretation,
  Seating_Arrangement, Error_Spotting, Arithmetic, Reading_Comprehension…
- `difficulty` — integer.
- `question_pattern` — one of the 14 structural patterns, validated against the
  enum in `schema.json`.
- Propagate `section` across a direction set: if four of five questions under one
  passage are Reasoning, the fifth is too.

**This step's logic already exists** and is worth running first. Measured against
`corpus/papers-deduped/` today it labels 13,569 of 18,651 questions:

| | Now | After |
|---|---|---|
| `section` | 17% | **73%** |
| `topic` | 0% | **73%** |

It needs nothing but the JSON. What stops it running today is an `import fitz`
inherited from the PDF module — moving it to `lib/classify/` fixes that.

---

### 3. `3_answer.py` — fill in the answers

**In** `corpus/papers/` + `corpus/sets/usable/` · **Out** the same JSON, with
`answer` and `explanation`

Two sources, in order:

1. **Answer keys from the PDFs** — the back-of-paper key, mapped to question
   numbers. Needs `corpus/pdf/`, so blocked.
2. **Stem match against `corpus/sets/usable/`** — 3,596 questions there are
   answered under `correct_option`, and **1,126 of them match a paper question**.
   Needs no missing files. Do this one now.

Match on a normalised stem, not an exact string: strip whitespace and case, and
require the option set to agree before accepting an answer. Log every match and
every near-miss to `answer_report.json` — a wrong answer is worse than none.

`explanation` is generated, not extracted. That's a separate pass, once answers
exist.

Ceiling without the PDFs: **1,126 of 18,651, about 6%.**

---

### 4. `4_build.py` — the export

**In** `corpus/papers/` **and** `corpus/papers-deduped/` · **Out**
`data/questions.jsonl.gz`

- **Build from the union of both folders.** Neither is complete: 1,408 distinct
  stems exist only in `papers/`, 891 only in `papers-deduped/`. The current
  export uses deduped alone and loses 1,408 questions.
- **Dedupe here**, on `content_hash`, keeping the copy with more filled fields.
  Dedup is a step, not a pre-baked folder.
- Flatten the paper's identity onto every question — `bank`, `role`,
  `exam_type`, `year`, `shift`, `memory_based`.
- Compute `direction_hash` from the passage text, and inline `direction_text`
  and `direction_image_refs`.
- Omit nulls, and omit `marks` / `negative_marks` when they equal the default.
- Truncate `content_hash` to 16 chars.
- Gzip. 23 MB becomes 3 MB, because the repeated passages compress away.
- Write `build_report.json` with the fill rate of every field.

Union target: **18,118 distinct questions**, up from 16,710.

---

### 5. `5_validate.py` — refuse to ship it broken

**In** `data/questions.jsonl.gz` · **Out** exit 0, or a list of failures

- Every row against `schema/schema.json` — types, required fields, and the
  `question_pattern` enum.
- Referential integrity: every `direction_hash` groups questions that really do
  share a passage; every `direction_id` resolves within its paper.
- No leaked provenance — no source book, coaching brand, internal id or URL.
  This is what `scripts/verify.py` does today.
- Fill rates, compared against the last run: **fail if a field went
  backwards.** A parser change that silently drops `options` on 2,000 questions
  should stop the build, not ship.
- No duplicate `q_id`, no duplicate `content_hash`.

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

| Step | State | |
|---|---|---|
| 1. extract | ran once, can't re-run | gave `stem` 99%, `options` 98%; no figures |
| 2. classify | logic exists, never wired in | would take `section` 17%→73%, `topic` 0%→73% |
| 3. answer | not written | 1,126 reachable now, rest needs the PDFs |
| 4. build | old version only | builds from deduped alone, loses 1,408 questions |
| 5. validate | partial | pattern enum only; no schema or fill-rate checks |

Nothing in `pipeline/` matches the five steps yet — that code is the old
three-entry-point version.

## Two things to know first

**The source PDFs are gone.** [`corpus/pdf/`](corpus/README.md) is gitignored
and empty, so step 1 can't run and the JSON in `corpus/papers*` is the only copy
of that extraction. Treat it as irreplaceable until the PDFs are restored.

**Nothing has answers except `corpus/sets/usable/`.** Those 3,596 answered
questions were built by a separate path and never joined to the papers. Fixing
this means either restoring the corpus and running
the PDF answer keys, or matching `sets/` questions back onto their papers by
stem — step 3 above. The second needs no missing files and reaches 1,126.

Until that's done the export can't drive practice, scoring or marking.

**986 questions need a figure that doesn't exist.** They carry
`has_image: true` and no file reference; the extraction never produced the
images. Recovering them needs the corpus too.

## What a question contains

Only the question, its options, the answer, and — where it genuinely needs one —
the chart or table. No source book, no internal id, no coaching brand, no URL.
`scripts/verify.py` re-reads the published output and fails if any of that
survives.

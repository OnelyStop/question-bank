# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
corpus/     everything the pipeline reads — the raw extraction
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

| | Questions | Answers |
|---|---|---|
| `corpus/sets/usable/` | 3,596 | **all** |
| `corpus/sets/flagged/` | 1,255 | held back |

That's it. The 243 extracted papers that used to sit in `corpus/papers/` are
deleted — they were the old pipeline's output, and output doesn't belong in the
source tree. They're in git history (`git checkout c73426f -- corpus/papers`).

**The source PDFs were never in this repo.** All 379 of them are listed in
[`corpus/PDF-MANIFEST.md`](corpus/PDF-MANIFEST.md); they live on the machine that
ran the first extraction. Nothing upstream of step 2 can run until they're back.

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

**In** the source PDFs · **Out** `corpus/papers/{bank}/{role}/{year}/{stage}/{paper_id}.json`

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

Needs PyMuPDF and the source PDFs, which aren't in this repo. Restore them to
`corpus/pdf/` and this step runs again.

---

### 2. `2_classify.py` — label what each question is

**In** `corpus/papers/` (once step 1 has written it) · **Out** the same JSON, with
labels added

- **Strip the Hindi.** 1,350 questions across 35 papers carry the Devanagari
  translation appended to the English stem and options. Do this first — every
  label below is computed from the text.
- `section` — Quantitative, Reasoning, English, GA, Computer.
- `topic` — from `lib/topic_taxonomy.json`: Data_Interpretation,
  Seating_Arrangement, Error_Spotting, Arithmetic, Reading_Comprehension…
- `difficulty` — integer.
- `question_pattern` — one of the 14 structural patterns, validated against the
  enum in `schema.json`.
- Propagate `section` across a direction set: if four of five questions under one
  passage are Reasoning, the fifth is too.

**This step's logic already exists** and is worth running first. Measured today it labels
13,569 of 18,651 questions:

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
   numbers. Needs the source PDFs, so blocked.
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

**In** `corpus/papers/` · **Out** `data/questions.jsonl.gz`

- **Dedupe here**, on `content_hash`, keeping the copy with more filled fields.
  Memory-based papers repeat questions, so this is real work — but it belongs in
  the pipeline, where it can be re-run, not baked into a second folder.
- Flatten the paper's identity onto every question — `bank`, `role`,
  `exam_type`, `year`, `shift`, `memory_based`.
- Compute `direction_hash` from the passage text, and inline `direction_text`
  and `direction_image_refs`.
- Omit nulls, and omit `marks` / `negative_marks` when they equal the default.
- Truncate `content_hash` to 16 chars.
- Gzip. 23 MB becomes 3 MB, because the repeated passages compress away.
- Write `build_report.json` with the fill rate of every field.

Input is 21,044 questions across 243 papers. How many survive dedup is the
thing to measure once it runs — the old export got 18,651 from a smaller input.

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

| Step | State |
|---|---|
| 1. extract | **blocked** — needs the 379 PDFs in `PDF-MANIFEST.md` |
| 2. classify | logic exists; nothing to run it on until step 1 does |
| 3. answer | not written |
| 4. build | old version only, and it now outputs 0 papers |
| 5. validate | partial — pattern enum only, no schema or fill-rate checks |

Nothing in `pipeline/` matches the five steps yet; that code is the old
three-entry-point version, and with `corpus/papers/` gone it has no input.
**Recovering the PDFs is the one thing that unblocks all of it.**

## Two things to know first

**The source PDFs were never committed.** Step 1 can't run without them, and
every step after it has nothing to read. [`corpus/PDF-MANIFEST.md`](corpus/PDF-MANIFEST.md)
lists all 379 — 245 that parsed and 134 that didn't, 95 of those Hindi editions.
Getting them back is the unblock for everything else.

**`corpus/sets/usable/` is the only question data left in the repo.** 3,596
questions, all answered under `correct_option`. It's a separate source from the
papers and survives independently of them.

**986 questions need a figure that doesn't exist.** They carry
`has_image: true` and no file reference; the extraction never produced the
images. Recovering them needs the corpus too.

## What a question contains

Only the question, its options, the answer, and — where it genuinely needs one —
the chart or table. No source book, no internal id, no coaching brand, no URL.
`scripts/verify.py` re-reads the published output and fails if any of that
survives.

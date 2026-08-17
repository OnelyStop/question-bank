# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
corpus/     everything the pipeline reads — empty, put source material here
data/       the clean output, one gzipped file
pipeline/   the five steps, one folder each
schema/     what one exported question looks like
```

`corpus/` is raw and messy by design; `data/` is generated and disposable.
Delete `data/`, re-run step 4, get it back.

Anything a pipeline writes is gitignored and rebuilt on demand, so nothing here
is both large and derivable.

## The data

`corpus/` is **empty** — drop source material in there and run the pipeline.
Overlap between folders is expected; step 4 dedupes.

Everything that used to be in it was the old pipeline's output. It's in git
history if needed:

```bash
git checkout c73426f -- corpus/papers        # 243 papers, 21,044 questions, no answers
git checkout ce4d92f -- corpus/sets          # 4,851 questions, 3,596 answered
git checkout 6da6705 -- corpus/PDF-MANIFEST.md   # the 379 source PDFs by name
```

**The source PDFs were never committed here.** 379 of them, on the machine that
ran the first extraction — 245 parsed, 134 didn't, 95 of those Hindi editions.
Recovering them unblocks everything.

## The pipeline

Five steps, [one folder each](pipeline/README.md). The old code's three
overlapping entry points and its six-table export are deleted; what survived is
the parts with real logic, filed under the step they belong to.

```
corpus/  ->  1_extract  ->  2_classify  ->  3_answer  ->  4_build  ->  data/
                                                              |
                                                          5_validate
```

```
pipeline/
  1-extract/   2-classify/   3-answer/   4-dedupe/   5-validate/   lib/
```

One folder per step, one owner per step, and a README in each saying what it
reads, what it must write, and how to tell it worked. Steps 1–3 each read the
previous step's output and write the same shape back, so any one of them can be
re-run alone.

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

### 1. `1-extract/` — PDFs to questions

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

### 2. `2-classify/` — label what each question is

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

It needs nothing but the JSON. The `import fitz` that used to stop it running is
gone now that it lives in `2-classify/`.

---

### 3. `3-answer/` — fill in the answers

**In** `corpus/papers/` + any answered source in `corpus/` · **Out** the same
JSON, with `answer` and `explanation`

Two sources, in order:

1. **Answer keys from the PDFs** — the back-of-paper key, mapped to question
   numbers. Needs the source PDFs, so blocked.
2. **Stem match against an answered source.** The `sets/` collection in git
   history (`ce4d92f`) has 3,596 answered questions, and **1,126 of them matched a
   paper question by stem** — a fallback that needs no PDFs if answers get
   urgent before the corpus is recovered.

Match on a normalised stem, not an exact string: strip whitespace and case, and
require the option set to agree before accepting an answer. Log every match and
every near-miss to `answer_report.json` — a wrong answer is worse than none.

`explanation` is generated, not extracted. That's a separate pass, once answers
exist.

Gate every match the same way step 4 does: the numeric tuple must be identical
and the options must agree. A near-match with different numbers is a different
question, and copying its answer over is the worst outcome available here.

---

### 4. `4-dedupe/` — dedupe and export

**In** `corpus/` · **Out** `data/questions.jsonl.gz`

Many overlapping folders will land in `corpus/` — memory-based papers repeat
questions and the same paper arrives from several sources. This step keeps one
copy of each.

#### Exact duplicates only

Only questions that are **character-for-character the same** are merged. Nothing
based on similarity scores, because the measurement below shows why that would be
dangerous here.

```python
def key(q):
    return sha256(
        norm(q["stem"]) + "\x00" +
        "\x00".join(f"{k}={norm(v)}" for k, v in sorted(q["options"].items()))
    ).hexdigest()

def norm(s):
    s = unicodedata.normalize("NFKC", s)   # ² and 2 settled the same way
    s = re.sub(r"\s+", " ", s).strip()     # whitespace and line breaks
    return s.casefold()                    # "Who" == "who"
```

One dict, one pass, O(n). First copy wins.

Digits are **never** touched. That is the whole safety property: two questions
that differ only in a number produce different keys and stay separate.

#### Why nothing fuzzier

Grouping the 3,596 answered questions by their text with the digits stripped out:

| | |
|---|---|
| true duplicates — same words **and** numbers | 182 |
| **same words, different numbers** | **105** |

**37% of look-alike pairs are not duplicates.** These two are identical strings
once digits are removed, and have different answers:

```
I. 35x2 – 34x – 21 = 0  /  II. 63y² + 55y + 12 = 0     answer: c
I. 3x2 – 5x – 12 = 0    /  II. 2y² + 15y + 25 = 0      answer: a
```

Any similarity threshold that catches the 182 also merges some of the 105 and
deletes real questions. Exact matching catches fewer duplicates and never makes
that mistake — the right trade when the source folders may be gone afterwards.

If near-duplicates become a problem later, the shape to add is MinHash + LSH
**gated on the numeric tuple matching exactly**, writing candidates to a review
file rather than merging them.

#### Two things to record while merging

**Where the copies came from.** When N collapse into one:

```json
"seen_in": ["ibps_clerk_2019_mains_…", "ibps_clerk_2021_prelims_…"],
"seen_count": 6
```

A question that appeared in six exams is high-yield, and this is the only place
that fact exists. Dedup usually discards it.

**Answer conflicts.** Same key, different `answer` — one source is wrong. Write
both to a review file and pick neither. There were 25 such cases in 3,596
questions. Silently choosing one ships a wrong answer.

Otherwise the surviving record takes the copy with the most filled fields,
prefers one that has an `answer`, unions the `image_refs`, and keeps the earliest
`year`.

#### Then the export

- Flatten the paper's identity onto every question — `bank`, `role`,
  `exam_type`, `year`, `shift`, `memory_based`.
- Compute `direction_hash`; inline `direction_text` and `direction_image_refs`.
- Omit nulls, and omit `marks` / `negative_marks` when they equal the default.
- Truncate `content_hash` to 16 chars.
- Gzip — repeated passages compress to almost nothing.
- Write `build_report.json`: fill rate per field, how many duplicates were
  merged, how many conflicts went to review.

### 5. `5-validate/` — refuse to ship it broken

**In** `data/questions.jsonl.gz` · **Out** exit 0, or a list of failures

- Every row against `schema/schema.json` — types, required fields, and the
  `question_pattern` enum.
- Referential integrity: every `direction_hash` groups questions that really do
  share a passage; every `direction_id` resolves within its paper.
- No leaked provenance — no source book, coaching brand, internal id or URL.
  This is what `pipeline/5-validate/check_no_provenance.py` does today.
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
| 1-extract | **blocked** — needs the 379 source PDFs |
| 2-classify | works; takes `section` to 73% and `topic` to 73% once there's input |
| 3-answer | 1,085 lines that have never produced an answer |
| 4-dedupe | not written |
| 5-validate | two narrow checks |

**Recovering the PDFs unblocks all of it.** They're the input to step 1, and every
step after it reads step 1's output.

## What blocks everything

**The source PDFs were never committed.** Step 1 can't run without them, and
every step after it has nothing to read. The manifest naming all 379 is at
`git checkout 6da6705 -- corpus/PDF-MANIFEST.md`. Getting the PDFs back is the
unblock for everything else.

**There is no question data in the repo at all right now.** The pipeline is a
specification; `corpus/` is where the source material goes.

**986 questions need a figure that doesn't exist.** They carry
`has_image: true` and no file reference; the extraction never produced the
images. Recovering them needs the corpus too.

## What a question contains

Only the question, its options, the answer, and — where it genuinely needs one —
the chart or table. No source book, no internal id, no coaching brand, no URL.
`pipeline/5-validate/check_no_provenance.py` re-reads the export and fails if any of that
survives.

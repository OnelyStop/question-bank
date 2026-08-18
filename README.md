# question-bank

Exam questions for Indian competitive exams, cleaned up and made usable.

Right now that means **banking** — IBPS, SBI and RRB.

```
corpus/     the source PDFs — 375 of them, 414 MB
data/       the clean output, one gzipped file
pipeline/   the five steps, one folder each
schema/     what one exported question looks like
```

`corpus/` is raw and messy by design; `data/` is generated and disposable.
Delete `data/`, re-run the pipeline, get it back.

Anything a pipeline writes is gitignored and rebuilt on demand, so nothing here
is both large and derivable.

## The data

`corpus/pdf/` holds **375 of the 379 source PDFs**, each with a `.meta.json`
sidecar, laid out `{bank}/{role}/{year}/{stage}/`. That's the input to step 1, so
**nothing is blocked** — the whole pipeline can run.

Earlier extractions are in git history if you want to compare against them:

```bash
git checkout c73426f -- corpus/papers   # 243 papers, 21,044 questions, no answers
git checkout ce4d92f -- corpus/sets     # 4,851 questions, 3,596 answered
```

## The pipeline

Five steps, [one folder each](pipeline/README.md). The old code's three
overlapping entry points and its six-table export are deleted; what survived is
the parts with real logic, filed under the step they belong to.

```
corpus/  ->  1-extract  ->  2-classify  ->  3-dedupe  ->  4-answer  ->  data/
                                                              |
                                                          5-validate
```

```
pipeline/
  1-extract/   2-classify/   3-dedupe/   4-answer/   5-validate/   lib/
```

One folder per step, one owner per step, and a README in each saying what it
reads, what it must write, and how to tell it worked. Steps 1–3 each read the
previous step's output and write the same shape back, so any one of them can be
re-run alone.

| Step | Needs the PDFs? |
|---|---|
| 1. extract | yes |
| 2. classify | no |
| 3. dedupe | no |
| 4. answer | yes, for the answer keys |
| 5. validate | no |

The PDFs are in `corpus/pdf/`, so all five can run. Steps 2, 4 and 5 need only
step 1's JSON, which means they can be developed against the previous
extraction (`git checkout c73426f -- corpus/papers`) without waiting for a step 1
rewrite.

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

Needs `pip install pymupdf`. The 375 source PDFs are in `corpus/pdf/`, so this
step can run.

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

### 3. `3-dedupe/` — keep one copy of each question

**In** step 2's classified questions · **Out** the same, deduped, plus
`dedupe_report.json`

Memory-based papers repeat questions and the same paper arrives from several
sources. **The last extraction was 7.6% duplicates — 1,601 copies of 21,044.**

#### Exact duplicates only

```python
def key(q):
    return sha256(
        norm(q["stem"]) + "\x00" +
        "\x00".join(f"{k}={norm(v)}" for k, v in sorted(q["options"].items()))
    ).hexdigest()

def norm(s):
    s = unicodedata.normalize("NFKC", s)   # settles ² vs 2
    s = re.sub(r"\s+", " ", s).strip()     # whitespace, line breaks
    return s.casefold()                    # "Who" == "who"
```

One dict, one pass, O(n). First copy wins. **Digits are never normalised** — that
is the whole safety property.

#### Why nothing fuzzier

Two independent measurements say the same thing:

- Grouping 3,596 answered questions by text with digits stripped: 182 are true
  duplicates, **105 share every word but differ in their numbers**. 37% of
  look-alikes aren't duplicates.
- At file level, a "share the first 3000 characters" heuristic flagged 47 PDF
  pairs. **46 were false positives** — different papers sharing a cover page.
  Exact text hashing found the one real duplicate and nothing else.

A reasonable-sounding similarity heuristic was 46/47 wrong. Exact hashing was
right both times.

```
I. 35x2 – 34x – 21 = 0  /  II. 63y² + 55y + 12 = 0     answer: c
I. 3x2 – 5x – 12 = 0    /  II. 2y² + 15y + 25 = 0      answer: a
```

Identical strings once digits are removed; different answers.

#### Keep the provenance — step 4 needs it

```json
{ "d758775a0377eafe": [
    { "paper_id": "ibps_clerk_2019_mains_…", "q_num": 95 },
    { "paper_id": "ibps_clerk_2021_prelims_…", "q_num": 42 } ] }
```

This is why dedupe runs before answers. Keys are found by `(paper_id, q_num)`, so
a merged question needs every place it appeared — if the 2019 paper has no key
but the 2021 one does, step 4 finds it here. It's also the high-yield signal: a
question in six exams is worth ranking practice by.

---

### 4. `4-answer/` — fill in the answers

**In** step 3's deduped questions + `dedupe_report.json` · **Out** the same, with
`answer` and `explanation`

Running after dedupe means answering **19,443 unique questions instead of
21,044**, and those 1,601 saved lookups come off the most expensive path.

I scanned all 375 PDFs — **69% carry a machine-readable answer key**:

| Format | PDFs | |
|---|---|---|
| `S{n}. Ans.(x)` + `Sol.` | **218** | 58% |
| grid — `1. (c); 2. (b);` | 34 | 9% |
| `Ans.` only | 7 | 2% |
| **nothing** | **116** | **31%** |

23,630 answer markers, and **15,926 `Sol.` blocks** — worked solutions, so
`explanation` is *extracted*, not generated.

Sources in order of reliability:

1. **`S{n}. Ans.(x)` + `Sol.`** — 58% of PDFs, and `{n}` joins straight to
   `q_num`. Build this first.
2. **Grid keys** — 34 PDFs.
3. **Separate solution PDFs** (`*-Solutions.pdf`, `*_SOL.pdf`) — pair to their
   question paper first.
4. **Other papers the question appeared in** — `dedupe_report.json` lists every
   `(paper_id, q_num)`. If one paper has no key, try the rest.
5. **Web search** — for the ~31% with no key anywhere. Expensive and
   unverifiable, which is exactly why it runs on the smallest possible set.
6. **Stem match** against `sets/` in git history — 1,126 matched.

Validate every key against that question's `options` before accepting it, and log
matched *and* unmatched counts on both sides. 100 questions and 100 answers off
by one look perfect in aggregate and are entirely wrong.

---

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
| 1-extract | code exists, never cropped a figure; PDFs now available |
| 2-classify | works; takes `section` to 73% and `topic` to 73% |
| 3-dedupe | not written |
| 4-answer | 1,085 lines that have never produced an answer |
| 5-validate | two narrow checks, plus CI on the step examples |

Nothing is blocked. Step 1 is the one to run first, since everything reads its
output — and its two known gaps are figures (986 questions flagged with no file)
and the Devanagari it appends to English stems.

## Two things to know

**414 MB of PDFs are in git history.** Removing them later needs a history
rewrite, so if more batches are coming, decide on Git LFS before they land.

**4 of the 379 PDFs are still missing**, and 35 have metadata that files them
under `_unknown_bank` — RRB papers recorded two different ways. See
[1-extract](pipeline/1-extract/README.md).

**There is no extracted question data yet** — `data/` is empty until step 4 runs.
The source PDFs are in place; the pipeline that turns them into questions is
specified but not built.

**986 questions need a figure that doesn't exist.** They carry
`has_image: true` and no file reference; the extraction never produced the
images. Recovering them needs the corpus too.

## What a question contains

Only the question, its options, the answer, and — where it genuinely needs one —
the chart or table. No source book, no internal id, no coaching brand, no URL.
`pipeline/5-validate/check_no_provenance.py` re-reads the export and fails if any of that
survives.

# schema

One file — [`schema.json`](schema.json) — one question, flat. 26 fields, no
joins.

## One question, every field filled

A real row from IBPS Clerk 2019 Mains, shown as it will look once the answer
and classifier stages have run:

```json
{
  "q_id": "ibps_clerk_2019_mains_unknown_shift_781623cd::q095",
  "paper_id": "ibps_clerk_2019_mains_unknown_shift_781623cd",
  "q_num": 95,
  "content_hash": "d758775a0377eafe",

  "stem": "What is the ratio of marked price to selling price of article C?",
  "options": { "a": "4 : 3", "b": "3 : 4", "c": "4 : 7", "d": "7 : 4", "e": "4 : 5" },
  "answer": "b",
  "explanation": "MRP = CP x 1.4, SP = MRP x 0.75, so MRP : SP = 1 : 0.75 = 4 : 3...",

  "direction_id": "d019",
  "direction_hash": "9f3c1ab77e40d215",
  "direction_text": "Line chart given below shows markup percent more than CP and discount percent given on MRP of seven different articles sold by a shopkeeper. Study the data carefully and answer the following questions.",

  "bank": "IBPS",
  "role": "Clerk",
  "exam_type": "Mains",
  "year": 2019,
  "shift": null,
  "memory_based": true,

  "section": "Quantitative",
  "topic": "Profit and Loss",
  "difficulty": "medium",
  "question_pattern": "shared_directions_set",

  "has_image": true,
  "image_refs": ["ibps_clerk_2019_mains_781623cd_p07_chart1.png"],
  "is_active": true
}
```

Everything except `answer`, `explanation`, `topic`, `difficulty`,
`image_refs` and `direction_hash` is real, exported data — those are empty or
not yet emitted today, and shown filled to make the shape clear.

Four things to read off it:

- **`marks` and `negative_marks` are absent** because this question uses the
  defaults (`1` and `-0.25`). They appear only where a paper differs.
- **`options` is an object keyed `a`–`e`, not an array.** So `answer` is the
  key `"b"`, not an index. `option_count` was dropped because it's just
  `Object.keys(options).length`.
- **`direction_text` repeats on every question in the set.** All seven articles
  in that line chart share this passage — that's the 4.4× duplication, and it's
  what lets you import one file.
- **`has_image` is true here and `image_refs` is empty in the real data.** 986
  questions are flagged as needing a figure and not one of them carries a
  reference to it. This question cannot actually be answered without the chart.

## What was dropped, and why

Four fields carried no information. A field with one value everywhere cannot
filter anything:

| Dropped | Reason |
|---|---|
| `language` | constant `"english"` — add back when Hindi papers land |
| `option_count` | `len(options)` — derivable |
| `topic_source` | provenance for a field that doesn't exist yet |
| `page_start` | which PDF page it came from; no product use |

## Grouping questions by passage

**Never group by `direction_id`.** It is paper-scoped — 30 distinct values
(`d001`…`d030`) reused across all 235 papers. Grouping by it alone merges
questions from unrelated exams into one "passage".

Group by **`direction_hash`** — 16 hex chars of the passage text:

```sql
select direction_hash, min(direction_text) as passage,
       array_agg(q_id order by q_num) as questions
from questions
where direction_hash is not null and is_active
group by direction_hash;
```

That gives **2,744 groups** rather than 3,039, because 148 passages are reused
across papers — one appears in 11 — and hashing the text collapses them
automatically. A paper-scoped key can't do that.

Order inside a set is `q_num`. Typical set is 5 questions (median 5, max 32,
68 passages have only one).

If you need the group scoped to a single paper instead — showing a paper
exactly as it was sat — use `(paper_id, direction_id)`. Both columns are
already on the row, so that costs nothing.

`direction_hash` costs +0.51 MB and is what makes the passage a first-class
thing you can index, cache and render once.

## marks and negative_marks

Both are back, with defaults:

| | Default |
|---|---|
| `marks` | `1` |
| `negative_marks` | `-0.25` |

They're **omitted from the export when they equal the default**, so today they
cost nothing — all 18,651 questions are standard — and a paper that scores
differently just writes the field. You get per-question customisation without
paying 0.45 MB to repeat the same two numbers 18,651 times.

Note `negative_marks` is stored **negative** (`-0.25`). The old export had it
positive, which meant every consumer had to know whether to add or subtract.

## Two changes that cost nothing

**Null fields are omitted, not written.** `answer` and four others are empty on
every row; writing `"answer": null` 18,651 times cost 2.5 MB. They stay declared
in the schema — they're coming — but absent from the data until filled.

**`content_hash` is 16 hex chars, not 64.** It exists to make re-import
idempotent; 16 chars is collision-safe at this scale and the full hash was 5% of
the whole file.

Together with the four dropped fields, and after adding `direction_hash`:
**29.3 MB → 24.2 MB, 17% smaller.**

## Where the bytes actually are

| | | |
|---|---|---|
| `direction_text` | 10.1 MB | **34%** — the inlining cost |
| `stem` | 4.6 MB | 16% |
| `options` | 2.4 MB | 8% |

`direction_text` is one third of the file because 3,039 passages are shared by
13,292 questions — inlining duplicates each ~4.4×. That is the price of a
single-file import with no join, and it's the right trade at this size. If the
corpus grows 10×, revisit it.

## File size is not the real efficiency question

This file is imported into Postgres once. 24.2 MB costs nothing at import and
the app never ships it to a browser. What matters is how the filters run:

- The filter columns are **low cardinality** — `bank` 2 distinct, `exam_type` 2,
  `role` 3, `section` 3, `year` 10, `question_pattern` 13. A btree index on any
  one alone is close to useless; Postgres will just seq-scan. Index the
  combinations you actually query, e.g. `(bank, role, year)`.
- **`is_active` belongs in every filter**, and 854 questions are already false.
  A partial index — `where is_active` — keeps the dead rows out of the index
  entirely.
- Searching `stem` is a full-text problem, not a `LIKE` one. That needs a GIN
  index on a `tsvector`, and it's the only field where the index will approach
  the size of the data.

## x-fill: read before you build

Every field carries `x-fill`, measured across all 18,651 rows.

**Empty (0%)** — `answer`, `explanation`, `topic`, `difficulty`, `image_refs`.

**Partial** — `section` 17%, `shift` 20%, `bank` 92%, `exam_type` 93%,
`year` 96%, `role` 97%.

Two that will bite:

- **`answer` at 0% blocks practice, scoring and marking entirely.**
- **`section` 17% and `shift` 20% are filter fields.** As facets they'd hide 83%
  and 80% of the bank respectively — they read as broken UI, not missing data.
  Hold them back until the classifier fills them.

## Not here

`attempts`, `attempt_answers` and `user_topic_stats` are written by the app at
runtime and defined in the frontend repo (`src/db/schema.ts`) with their RLS
policies. This repo produces no rows for them.

# schema

One file — [`schema.json`](schema.json). One question, flat, 28 fields.

Import it and you can filter by bank, role, year, exam type, section or pattern,
and render the question — without touching a second file.

> **This describes the file, not your database tables.** They are deliberately
> different shapes. In the file every question carries `direction_text`; in the
> database that column does not exist. See [Storage](#storage).

## A question

Real row from IBPS Clerk 2019 Mains, with the empty fields filled in so you can
see the whole shape:

```json
{
  "q_id": "ibps_clerk_2019_mains_unknown_shift_781623cd::q095",
  "paper_id": "ibps_clerk_2019_mains_unknown_shift_781623cd",
  "q_num": 95,
  "content_hash": "d758775a0377eafe",

  "stem": "What is the ratio of marked price to selling price of article C?",
  "options": { "a": "4 : 3", "b": "3 : 4", "c": "4 : 7", "d": "7 : 4", "e": "4 : 5" },
  "answer": "b",
  "explanation": "MRP = CP x 1.4, SP = MRP x 0.75, so MRP : SP = 4 : 3",

  "direction_id": "d019",
  "direction_hash": "9f3c1ab77e40d215",
  "direction_text": "Line chart given below shows markup percent more than CP and discount percent given on MRP of seven different articles sold by a shopkeeper.",
  "direction_has_image": true,
  "direction_image_refs": ["ibps_clerk_2019_mains_781623cd_p07_chart1.png"],

  "bank": "IBPS",
  "role": "Clerk",
  "exam_type": "Mains",
  "year": 2019,
  "shift": null,
  "memory_based": true,

  "section": "Quantitative",
  "topic": "Profit and Loss",
  "difficulty": 3,
  "question_pattern": "shared_directions_set",

  "has_image": true,
  "image_refs": [],
  "is_active": true
}
```

- `options` is an **object keyed `a`–`e`**, not an array — so `answer` is the key
  `"b"`, not an index `1`.
- `marks` and `negative_marks` are **absent because they're default**. Only a
  paper that scores differently writes them.

## Every field

**Fill** is how much of the real data has the field today, measured across all
18,651 questions.

**Identity**

| Field | Type | Fill | |
|---|---|---|---|
| `q_id` | string | 100% | Unique — `{paper_id}::q{num}` |
| `paper_id` | string | 100% | Which paper it came from |
| `q_num` | integer | 100% | Position in the paper; orders a passage set |
| `content_hash` | string | 100% | 16 hex chars of the stem — makes re-import idempotent |

**The question**

| Field | Type | Fill | |
|---|---|---|---|
| `stem` | string | 99% | The question text |
| `options` | object | 98% | `{ "a": "…", "b": "…" }`, up to `e` |
| `answer` | string | **—** | The correct key, e.g. `"b"` |
| `explanation` | string | **—** | Worked solution |

**The passage** — for questions that share a passage, DI table or seating grid

| Field | Type | Fill | |
|---|---|---|---|
| `direction_id` | string | 71% | The block within its paper — `d001`…`d030` |
| `direction_hash` | string | 71% | 16 hex chars of the passage text — **group by this** |
| `direction_text` | string | 71% | The passage itself (file only — see Storage) |
| `direction_has_image` | boolean | **—** | The passage needs a figure |
| `direction_image_refs` | array | **—** | Figures belonging to the **passage** — the DI chart, table or grid |

**Filter by exam** — copied from the paper so you don't need a join

| Field | Type | Fill | |
|---|---|---|---|
| `bank` | string | 92% | `IBPS`, `SBI` |
| `role` | string | 97% | `Clerk`, `PO`, `SO` |
| `exam_type` | string | 93% | `Prelims`, `Mains` |
| `year` | integer | 96% | 2015–2024 |
| `shift` | string | 20% | Which shift of the day |
| `memory_based` | boolean | 100% | Recalled by candidates, not an official paper |

**Filter by content**

| Field | Type | Fill | |
|---|---|---|---|
| `section` | string | 17% | `Quantitative`, `Reasoning`, `English` |
| `topic` | string | **—** | e.g. `Profit and Loss` |
| `difficulty` | integer | **—** | 1 = easiest |
| `question_pattern` | string | 100% | One of 14 — enum in the schema |

**Figures**

| Field | Type | Fill | |
|---|---|---|---|
| `has_image` | boolean | 100% | True on 986 questions |
| `image_refs` | array | **—** | Figures for **this question alone** |

For a passage set the chart almost always belongs to the passage, not the
question — **902 of the 986 flagged questions are in a set**, and in 175 of 176
sets every question is flagged. So the chart goes in `direction_image_refs` and
ends up on the `passages` row, not repeated on all 6 questions. Only the 84
standalone figure questions use `image_refs`.

**Scoring**

| Field | Type | Fill | |
|---|---|---|---|
| `marks` | number | default `1` | Omitted when default |
| `negative_marks` | number | default `-0.25` | Stored negative. Omitted when default |
| `is_active` | boolean | 100% | False on 854 — exclude these from practice |

## Storage

### The passage is written many times in the file, stored once in the DB

Say 6 questions share one passage.

**In the file**, all 6 carry the full text:

| `q_id` | `stem` | `direction_text` |
|---|---|---|
| q011 | What is the ratio…? | Line chart given below shows… |
| q012 | What is the profit…? | Line chart given below shows… |
| q013 | What is the discount…? | Line chart given below shows… |

**In the database they don't.** The `questions` table has **no `direction_text`
column at all** — the import drops it. The text goes into its own table:

`passages` — **1 row**, and this is where the chart lives too

| `direction_hash` | `body` | `image_refs` |
|---|---|---|
| `9f3c1ab7` | Line chart given below shows… | `["…_p07_chart1.png"]` |

`questions` — **6 rows**, holding a 16-character code

| `q_id` | `stem` | `direction_hash` |
|---|---|---|
| q011 | What is the ratio…? | `9f3c1ab7` |
| q012 | What is the profit…? | `9f3c1ab7` |
| q013 | What is the discount…? | `9f3c1ab7` |

Across the bank: **13,292 copies become 2,744 rows.**

### How the import does it

```sql
-- 1. load the file as-is, into a scratch table
copy questions_import from 'questions.jsonl';

-- 2. the text goes to passages, questions keep only the code
insert into passages (direction_hash, body, image_refs)
select distinct direction_hash, direction_text, direction_image_refs
from questions_import;

insert into questions (q_id, stem, options, direction_hash, ...)
select q_id, stem, options, direction_hash, ... from questions_import;

drop table questions_import;
```

The copies only ever exist inside `questions_import`, which is deleted at the
end.

### Why the file keeps the copies

So it stays **one file**, where every line stands alone. No second file, no
"load this one first", no ordering rules — one `copy` and you have everything.

And gzip makes the repeats nearly free:

| | Size | Gzipped |
|---|---|---|
| passage on every question | 23.2 MB | **2.98 MB** |
| passage on first of each set only | 15.9 MB | 2.84 MB |

Repeated text is what gzip is best at. Ship `questions.jsonl.gz` and import it
directly:

```bash
zcat questions.jsonl.gz | psql -c "copy questions_import from stdin"
```

Restructuring the file to write the passage only once saves 7.3 MB uncompressed
but only **0.14 MB** gzipped — and costs you a file whose lines aren't
self-contained. Not worth it.

### How much space it all takes

| | Today | With explanations |
|---|---|---|
| `questions` | 11.2 MB | 23.9 MB |
| `passages` | 1.8 MB | 1.8 MB |
| Indexes | 4.8 MB | 4.8 MB |
| **Total** | **~18 MB** | **~30 MB** |

For 20,000 questions. That's **6% of the Supabase free tier**.

`explanation` is the whole growth — 12 of the 12.7 MB added. Everything else is
rounding error.

### What was optimised, and what wasn't

| Change | Saved |
|---|---|
| Passage into its own table | ~8 MB in the DB |
| Gzip the export | 20 MB in transit |
| Dropped 4 fields with one value each | 2.2 MB |
| Omit null fields instead of writing them | 2.5 MB |
| `content_hash` 16 chars instead of 64 | 0.9 MB |

Deliberately **not** optimised:

- **The passage text itself.** Deduped it's 1.58 MB — mean 575 characters, and
  only 135 of 2,744 are over 2 KB, which is where Postgres would compress
  anyway. Nothing to squeeze.
- **`stem` (4.6 MB) and `options` (2.4 MB).** That's the actual content.
- **`explanation` in a separate table.** It's only read after someone answers,
  so splitting it would keep the hot table smaller — but at 30 MB the whole
  database fits in memory. Revisit at 500k questions.
- **Generating explanations on demand instead of storing them.** One pass costs
  $2–45 in tokens; storing 12 MB costs $0.0015/month. Generate once, store
  forever.

### Why a passages table and not just duplication

Not for space — 10 MB is nothing to Postgres. **For editing.** These passages
came out of PDFs and some are wrong: 6 are cut off mid-sentence, stacked
fractions arrive mangled. Fixing one should change **1 row, not 6**, with no way
to half-fix it.

It also means a 5-question set sent to a phone is **4.5 KB instead of 7.0 KB**,
since the passage goes over once.

**Don't** store the text on only the first question of a set instead. Same
space, but reading it needs a self-join, and deactivating that one question
strips the passage from the whole set.

## Grouping questions by passage

**Never group by `direction_id`.** It has only 30 distinct values (`d001`…
`d030`) and they repeat in every paper — grouping by it merges unrelated exams
into one "passage".

Group by **`direction_hash`**:

```sql
select p.direction_hash, p.body as passage,
       array_agg(q.q_id order by q.q_num) as questions
from questions q
join passages p using (direction_hash)
where q.is_active
group by p.direction_hash, p.body;
```

- Order inside a set is `q_num`. Median set is **5** questions, max 32.
- Hashing the text also merges the **148 passages reused across papers** (one
  appears in 11), which a per-paper key can't do.
- Want a passage scoped to one paper, exactly as it was sat? Use
  `(paper_id, direction_id)`. Keep `direction_id` for this — 10 papers contain
  two separate blocks whose text is identical, and hashing merges them.

## What's empty — read before building

| | Fill |
|---|---|
| `answer` `explanation` `topic` `difficulty` `image_refs` | **0%** |
| `section` | 17% |
| `shift` | 20% |
| `bank` · `exam_type` · `year` · `role` | 92–97% |

Three that will bite:

- **`answer` is 0%.** No practice, scoring or marking works until it's filled.
- **`section` 17% and `shift` 20% are filter fields.** As facets they'd hide 83%
  and 80% of the bank — that reads as broken UI, not missing data. Hold them
  back until the classifier runs — it exists and would take `section` to 73%,
  see the [pipeline steps](../README.md#the-pipeline).
- **No figures exist at all.** 986 questions are flagged `has_image`, and not one
  carries a file reference — the extraction never produced the images. Those
  questions can't be answered from what we have, whichever field they'd sit in.

## Query speed

File size barely matters — it imports once. Query speed does, and the filter
columns are all low cardinality: `bank` 2 distinct values, `exam_type` 2, `role`
3, `section` 3, `year` 10, `question_pattern` 13.

- Single-column indexes on those are near useless — Postgres will seq-scan.
  Index the combinations you actually query, like `(bank, role, year)`.
- `is_active` is in every query and 854 rows are already false, so use a partial
  index: `where is_active`.
- Searching `stem` needs full-text — a GIN index on a `tsvector`, not `LIKE`.

## Not here

`attempts`, `attempt_answers` and `user_topic_stats` are written by the app at
runtime, and defined in the frontend repo (`src/db/schema.ts`) with their RLS
policies. This repo produces no rows for them.

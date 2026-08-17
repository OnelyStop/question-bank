# schema

One file — [`schema.json`](schema.json). One question, flat, 26 fields.

Import it and you can filter by bank, role, year, exam type, section or pattern,
and render the question — without touching a second file.

## A question

Real row from IBPS Clerk 2019 Mains, shown with the empty fields filled in so
you can see the whole shape:

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

- `options` is an **object keyed `a`–`e`**, not an array — so `answer` is the
  key `"b"`, not an index `1`.
- `marks` and `negative_marks` are **missing because they're default** (`1` and
  `-0.25`). A paper that scores differently writes them; everything else doesn't.
- `answer`, `explanation`, `topic`, `difficulty` and `image_refs` are **empty in
  the real data today.**

## The passage: written 6 times, stored once

Say a passage has 6 questions. In the file, each of the 6 carries the full
`direction_text`:

```jsonc
{ "q_id": "...q011", "direction_hash": "9f3c1ab7", "direction_text": "Line chart given below shows..." }
{ "q_id": "...q012", "direction_hash": "9f3c1ab7", "direction_text": "Line chart given below shows..." }
{ "q_id": "...q013", "direction_hash": "9f3c1ab7", "direction_text": "Line chart given below shows..." }
// ...6 identical passages
```

That looks wasteful, and it would be — if it went into the database that way.
It doesn't. **Importing is two steps, and the copies only exist in the first
one.**

**Step 1** — load the file into a scratch table, copies and all:

```sql
copy questions_import from 'questions.jsonl';   -- 6 rows, 6 copies of the passage
```

**Step 2** — split it, then throw the scratch table away:

```sql
insert into passages (direction_hash, body)
select distinct direction_hash, direction_text from questions_import;   -- 1 row

insert into questions (q_id, stem, options, direction_hash, ...)
select q_id, stem, options, direction_hash, ... from questions_import;  -- 6 rows, no passage text

drop table questions_import;
```

What you end up with:

| Table | Rows | Passage text |
|---|---|---|
| `passages` | **1** | the full text, once |
| `questions` | **6** | just `"9f3c1ab7"` — 16 characters each |

So the passage lives in exactly one place. The 6 questions point at it with a
16-character key, and you get it back with a join.

**Why keep the copies in the file at all?** Because it makes the file one file.
No second file, no "load this before that", no ordering rules — one `copy` and
you have everything. The duplication is 9.7 MB that exists for about a minute
during import and then is gone.

**Why it matters that it doesn't reach the database:**

- Fix a typo in a passage → **1 row updated, not 6.** No risk of the same
  passage rendering two different ways.
- Serving a 5-question set → **4.5 KB instead of 7.0 KB**, because the passage
  goes over the wire once. Worst set in the corpus is 22 questions on a 4,275
  character passage — that's 92 KB of repeats saved.

Across the whole bank: **13,292 inlined copies become 2,744 passage rows.**

## Grouping questions by passage

**Never group by `direction_id`.** It only has 30 distinct values (`d001`…
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
  `(paper_id, direction_id)` — both columns are already there.

## What's empty — read before building

| | Fill |
|---|---|
| `answer` `explanation` `topic` `difficulty` `image_refs` | **0%** |
| `section` | 17% |
| `shift` | 20% |
| `bank` · `exam_type` · `year` · `role` | 92–97% |

Two that will bite:

- **`answer` is 0%.** No practice, scoring or marking works until it's filled.
- **`section` 17% and `shift` 20% are filter fields.** As facets they'd hide 83%
  and 80% of the bank — that reads as broken UI, not missing data. Hold them
  back until the classifier fills them.

Every field carries `x-fill` in the schema, measured across all 18,651 rows.

## Size and speed

**24.2 MB**, down from 29.3 MB. Four fields were dropped for having one value
everywhere — `language`, `option_count`, `topic_source`, `page_start` — nulls
are omitted rather than written, and `content_hash` is 16 chars instead of 64.

File size barely matters; it imports once. **Query speed does**, and the filter
columns are all low cardinality — `bank` 2 distinct values, `exam_type` 2,
`role` 3, `section` 3, `year` 10, `question_pattern` 13:

- Single-column indexes on those are near useless — Postgres will seq-scan.
  Index the combinations you query, like `(bank, role, year)`.
- `is_active` is in every query and 854 rows are already false, so use a partial
  index: `where is_active`.
- Searching `stem` needs full-text — a GIN index on a `tsvector`, not `LIKE`.

## Not here

`attempts`, `attempt_answers` and `user_topic_stats` are written by the app at
runtime, and defined in the frontend repo (`src/db/schema.ts`) with their RLS
policies. This repo produces no rows for them.

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

Say 6 questions share one passage.

**In the file**, all 6 carry the full passage text:

| `q_id` | `stem` | `direction_text` |
|---|---|---|
| q011 | What is the ratio…? | Line chart given below shows… |
| q012 | What is the profit…? | Line chart given below shows… |
| q013 | What is the discount…? | Line chart given below shows… |
| …6 rows, same text 6 times | | |

**In the database, after import, they do not.** The text moves into its own
table, and each question keeps only a short code:

`passages` — **1 row**

| `direction_hash` | `body` |
|---|---|
| `9f3c1ab7` | Line chart given below shows… |

`questions` — **6 rows**

| `q_id` | `stem` | `direction_hash` |
|---|---|---|
| q011 | What is the ratio…? | `9f3c1ab7` |
| q012 | What is the profit…? | `9f3c1ab7` |
| q013 | What is the discount…? | `9f3c1ab7` |

So the answer to "do the 6 questions still hold the text?" is **no**. They hold
a 16-character code. The text sits in one row, and a join brings it back.

### How the text gets out

The importer does it in two steps:

```sql
-- 1. load the file as-is, into a scratch table
copy questions_import from 'questions.jsonl';

-- 2. text goes to passages, questions keep only the code
insert into passages (direction_hash, body)
select distinct direction_hash, direction_text from questions_import;

insert into questions (q_id, stem, options, direction_hash, ...)
select q_id, stem, options, direction_hash, ... from questions_import;

drop table questions_import;
```

The 6 copies exist only inside `questions_import`, which is deleted at the end.

### Why the file has copies at all

Because it keeps it **one file**. No second file, no "load this one first", no
ordering rules — one `copy` and you have everything. The extra 9.7 MB lives for
about a minute during import, then it's gone.

### What you get from this

- Fix a typo in a passage → **1 row changes, not 6.** The passage can never show
  up two different ways.
- Send a 5-question set to a phone → **4.5 KB instead of 7.0 KB.** The passage
  goes over once, not five times.
- Whole bank: **13,292 copies become 2,744 passage rows.**

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

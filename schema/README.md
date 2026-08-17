# schema

One file — [`schema.json`](schema.json) — describing what this repo hands to
the app.

A **question** is the unit. It points at two other rows, and both are in the
schema because a question is not usable without them:

| `$def` | | Why it's here |
|---|---|---|
| `question` | 21 fields | the thing you import |
| `direction` | 3 fields | **71% of questions are unreadable without it** |
| `paper` | 16 fields | where the question came from |

## Why direction is not optional

13,292 of 18,651 questions carry a `direction_id` and nothing else — the shared
passage, the DI table, the seating arrangement all live in the `direction` row.
A reading-comprehension question imported on its own is five options and no
passage.

`paper` matters less at read time but every question has a `paper_id`, and it's
what "IBPS Clerk 2023 Mains" is attached to.

## The fields tell you what's actually filled

Every field in `question` carries `x-fill` — the percentage non-null across all
18,651 exported questions, measured from the data, not asserted.

Five are at **0%**:

```
answer        explanation    topic    topic_source    difficulty
```

`answer` is the blocker — the export cannot be used for practice until it's
filled. `topic` and `difficulty` are empty because the classifier stage was
never built; `section` is at 17% for the same reason. See the root
[README](../README.md).

`image_refs` is also 0%, on the 986 questions where `has_image` is true.

## question_pattern

An enum on the question itself, not a separate concern — one of 14 values,
enforced at runtime by `pipeline/patterns/validate.py`. The write-up of each
pattern lives in `.cursor/skills/banking-question-pattern-pipeline/`.

## Not here

**The app's tables.** `attempts`, `attempt_answers` and `user_topic_stats` are
written by the app at runtime; this repo produces no rows for them. All the
tables — including the three above — are defined in the frontend repo as
Drizzle schema (`src/db/schema.ts`) with their RLS policies beside them.

**The source paper files** under `data/papers/`. Those are the pipeline's input,
not its output. Their shape is whatever `pipeline/pdf/` writes.

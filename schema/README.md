# schema

One file — [`schema.json`](schema.json) — one question, flat. 29 fields, and
everything is on the row: no joins, no lookup tables.

```jsonc
{
  "q_id": "...", "paper_id": "...", "q_num": 12,
  "stem": "...", "options": [...], "answer": null,
  "direction_text": "Directions (11-15): Study the following...",
  "bank": "IBPS", "role": "Clerk", "year": 2023, "shift": null,
  "section": "Reasoning", "question_pattern": "shared_directions_set",
  "marks": 1, "is_active": true
}
```

Import this one file and you can filter by bank, role, year, exam type,
section or pattern, and render the question without fetching anything else.

## What each group is for

| Group | Fields |
|---|---|
| **Identity** | `q_id` `paper_id` `q_num` `content_hash` |
| **Content** | `stem` `options` `answer` `explanation` `direction_id` `direction_text` |
| **Filter** | `bank` `role` `exam_type` `year` `shift` `memory_based` `language` `section` `topic` `topic_source` `difficulty` `question_pattern` |
| **Render** | `has_image` `image_refs` `page_start` |
| **Scoring** | `marks` `negative_marks` `option_count` `is_active` |

`direction_text` is the shared passage, DI table or seating arrangement,
**inlined** rather than referenced. 71% of questions have one, and 3,039
passages are shared by 13,292 questions, so inlining duplicates each about 4.4×
— roughly **+9.7 MB on a 16.8 MB file**. That's the price of not needing a
second table, and at this size it's the right trade.

`direction_id` stays alongside it so questions sharing a passage can still be
grouped and shown together.

## x-fill: what is actually populated

Every field carries `x-fill`, measured across all 18,651 questions rather than
asserted. Read it before building on a field.

**Empty (0%)** — `answer`, `explanation`, `topic`, `topic_source`,
`difficulty`, `image_refs`.

**Partial** — `shift` 20%, `section` 17%, `page_start` 87%, `bank` 92%,
`exam_type` 93%, `year` 96%, `role` 97%.

Two consequences worth knowing before wiring the UI:

- **`answer` at 0% means no practice, scoring or marking works yet.** This is
  the blocker.
- **`shift` at 20% and `section` at 17% are filter fields.** A shift filter
  hides 80% of the bank; a section filter hides 83%. Ship those two as facets
  only once they're filled, or they'll look broken.

`topic`, `topic_source`, `difficulty` and most of `section` are empty because
the classifier stage was never built. See the root [README](../README.md).

## Not here

The app's own tables — `attempts`, `attempt_answers`, `user_topic_stats` — are
written at runtime and defined in the frontend repo (`src/db/schema.ts`) with
their RLS policies. This repo produces no rows for them.

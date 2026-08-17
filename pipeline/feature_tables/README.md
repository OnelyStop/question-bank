# Feature tables (question-features-spec)

Six tables for Question Bank / PYQ Mix / Past Papers.

| Table | Kind | Source |
|-------|------|--------|
| `papers` | content | `papers-deduped` + exam pattern lookup |
| `directions` | content | unique `(paper_id, direction_id)` bodies |
| `questions` | content | per-question rows (+ `content_hash`, marks, `is_active`) |
| `attempts` | runtime | empty until product use |
| `attempt_answers` | runtime | empty until product use |
| `user_topic_stats` | runtime | empty until product use |

## Build

```bash
python India/banking/feature_tables/build_feature_tables.py
```

Outputs land in `out/`:

- `papers.jsonl`, `directions.jsonl`, `questions.jsonl`
- `attempts.jsonl`, `attempt_answers.jsonl`, `user_topic_stats.jsonl` (empty)
- `tables_catalog.json`, `report.json`

Schemas: `schemas/*.schema.json`

Exam duration / marks / sectional timing: `exam_patterns.json`

## Notes from the spec

- Always join directions as `paper_id + direction_id` (ids repeat across papers).
- Never drop `paper_id` from questions.
- `exam_key` groups recalls of the same real exam; `is_canonical` picks the best file.
- `answer` / `explanation` / `topic` / `difficulty` are still mostly empty — import is ready for them.

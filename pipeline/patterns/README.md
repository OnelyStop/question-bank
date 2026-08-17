# Pattern extraction pipeline

Turns raw paper JSON under `India/banking/papers` and `papers-deduped` into a
**uniform question JSONL** ready for Supabase, with one `question_pattern` per row.

Each of the 14 patterns is implemented as a **pattern skill** under
`patterns/` (classifier + optional field extraction). Cursor agent skills live
under `.cursor/skills/banking-question-pattern-pipeline/`.

## Quick start

```bash
# from repo root
python India/banking/pattern_pipeline/run_pipeline.py

# smoke test
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 10 --out-dir India/banking/pattern_pipeline/out/sample

# validate
python India/banking/pattern_pipeline/validate.py India/banking/pattern_pipeline/out/questions.jsonl
```

## Outputs

| File | Purpose |
|------|---------|
| `out/questions.jsonl` | One uniform question object per line (Supabase load) |
| `out/by_pattern/*.jsonl` | Same rows split by `question_pattern` |
| `out/report.json` | Counts + paths |

Duplicate `q_id`s across `papers` and `papers-deduped` are collapsed; default prefer is `papers-deduped`.

## Uniform row fields

See `schema/uniform_question.schema.json`. Key fields:

- `question_pattern` — primary pattern id from `../question_patterns.json`
- `secondary_patterns` — e.g. `bilingual_stem_directions`
- `stem`, `options`, `direction_text`, `direction_id`
- `has_shared_directions`, `is_bilingual`, `has_image`
- paper metadata: `bank`, `role`, `year`, `exam_type`, …

## Supabase

1. Create the tables from the frontend repo (`bun run db:migrate`); shapes are in `schema/feature_tables/`.
2. Bulk-upsert `out/questions.jsonl` (e.g. via script, Edge function, or `COPY` after converting to CSV/NDJSON import).

## Pattern skill priority (first match wins)

1. `partial_or_missing_options`
2. `image_figure_based`
3. `visual_chart_graph_di`
4. `table_di_set`
5. `cloze_passage_set`
6. `reading_comprehension_set`
7. `data_sufficiency`
8. `quantity_comparison`
9. `quadratic_comparison`
10. `match_the_columns`
11. `caselet_di_set`
12. `shared_directions_set` (fallback for shared directions)
13. `standalone_mcq` (fallback for no directions)

Secondary (can co-occur):

- `bilingual_stem_directions` → sets `is_bilingual` + `secondary_patterns`

## Agent usage

Use the project skill `banking-question-pattern-pipeline` when adjusting
classifiers, re-running extraction, or mapping rows into Supabase.

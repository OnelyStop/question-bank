---
name: banking-question-pattern-pipeline
description: >-
  Extracts banking PYQ papers into uniform Supabase-ready JSON using 14
  question-pattern skills. Use when classifying question patterns, running
  India/banking/pattern_pipeline, building questions.jsonl, or loading
  banking_questions into Supabase.
---

# Banking question pattern pipeline

## Goal

Normalize ~39k paper questions into one uniform JSON shape with
`question_pattern` set from the canonical 14 patterns in
`India/banking/question_patterns.json`.

## Run (bulk)

```bash
python India/banking/pattern_pipeline/run_pipeline.py
python India/banking/pattern_pipeline/validate.py India/banking/pattern_pipeline/out/questions.jsonl
```

Outputs:

- `India/banking/pattern_pipeline/out/questions.jsonl`
- `India/banking/pattern_pipeline/out/by_pattern/<pattern>.jsonl`
- `India/banking/pattern_pipeline/out/report.json`

Supabase DDL: `India/banking/pattern_pipeline/schema/supabase_questions.sql`

## Architecture

| Layer | Path |
|-------|------|
| Pattern catalog | `India/banking/question_patterns.json` |
| Pattern skills (code) | `India/banking/pattern_pipeline/patterns/*.py` |
| Classifier | `India/banking/pattern_pipeline/classify.py` |
| Uniform extractor | `India/banking/pattern_pipeline/extract.py` |
| CLI | `India/banking/pattern_pipeline/run_pipeline.py` |
| Pattern skill docs | [patterns/](patterns/) |

## Workflow

1. Confirm pattern ids still match `question_patterns.json` `allowed_ids`.
2. Adjust the relevant pattern skill under `pattern_pipeline/patterns/`.
3. Re-run pipeline (optionally `--limit-papers` first).
4. Check `report.json` pattern counts.
5. Validate JSONL.
6. Load into `public.banking_questions`.

## Adding / changing a pattern

1. Add/update entry in `India/banking/question_patterns.json`.
2. Add/update `pattern_pipeline/patterns/<id>.py` implementing `PatternSkill`.
3. Register in `pattern_pipeline/patterns/__init__.py` (`PRIMARY_SKILLS` or `SECONDARY_SKILLS`).
4. Update schema enum + SQL check if needed.
5. Add/update doc in [patterns/](patterns/).
6. Smoke-test with `--limit-papers 20`.

## Classification rules

- **One primary pattern** per question (priority order; first match wins).
- **Secondary patterns** may co-occur (`bilingual_stem_directions`).
- Prefer specific formats (RC, cloze, DI, DS, …) over generic
  `shared_directions_set` / `standalone_mcq`.
- `partial_or_missing_options` wins when `option_count < 4`.

## Pattern docs

- [standalone_mcq](patterns/standalone_mcq.md)
- [shared_directions_set](patterns/shared_directions_set.md)
- [reading_comprehension_set](patterns/reading_comprehension_set.md)
- [cloze_passage_set](patterns/cloze_passage_set.md)
- [image_figure_based](patterns/image_figure_based.md)
- [visual_chart_graph_di](patterns/visual_chart_graph_di.md)
- [table_di_set](patterns/table_di_set.md)
- [caselet_di_set](patterns/caselet_di_set.md)
- [data_sufficiency](patterns/data_sufficiency.md)
- [quantity_comparison](patterns/quantity_comparison.md)
- [quadratic_comparison](patterns/quadratic_comparison.md)
- [match_the_columns](patterns/match_the_columns.md)
- [partial_or_missing_options](patterns/partial_or_missing_options.md)
- [bilingual_stem_directions](patterns/bilingual_stem_directions.md)

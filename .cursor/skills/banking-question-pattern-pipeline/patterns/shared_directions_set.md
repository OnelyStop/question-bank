# Shared-directions set

**Pattern id:** `shared_directions_set`

## When to apply
Has direction_text/direction_id but no more specific pattern matched

## Code skill
`pipeline/patterns/patterns/shared_directions_set.py`

## Uniform output
Sets `question_pattern` to `shared_directions_set` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python pipeline/patterns/run_pipeline.py --limit-papers 20 --out-dir pipeline/patterns/out/sample
```

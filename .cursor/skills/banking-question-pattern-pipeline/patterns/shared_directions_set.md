# Shared-directions set

**Pattern id:** `shared_directions_set`

## When to apply
Has direction_text/direction_id but no more specific pattern matched

## Code skill
`India/banking/pattern_pipeline/patterns/shared_directions_set.py`

## Uniform output
Sets `question_pattern` to `shared_directions_set` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 20 --out-dir India/banking/pattern_pipeline/out/sample
```

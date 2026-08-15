# Quadratic comparison

**Pattern id:** `quadratic_comparison`

## When to apply
Two equations (I) and (II)

## Code skill
`India/banking/pattern_pipeline/patterns/quadratic_comparison.py`

## Uniform output
Sets `question_pattern` to `quadratic_comparison` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 20 --out-dir India/banking/pattern_pipeline/out/sample
```

# Partial / missing options

**Pattern id:** `partial_or_missing_options`

## When to apply
option_count < 4

## Code skill
`India/banking/pattern_pipeline/patterns/partial_or_missing_options.py`

## Uniform output
Sets `question_pattern` to `partial_or_missing_options` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 20 --out-dir India/banking/pattern_pipeline/out/sample
```

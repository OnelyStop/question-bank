# Match the columns

**Pattern id:** `match_the_columns`

## When to apply
Column I / Column II matching

## Code skill
`India/banking/pattern_pipeline/patterns/match_the_columns.py`

## Uniform output
Sets `question_pattern` to `match_the_columns` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 20 --out-dir India/banking/pattern_pipeline/out/sample
```

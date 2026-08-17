# Table DI set

**Pattern id:** `table_di_set`

## When to apply
Following/given table shows...

## Code skill
`pipeline/patterns/patterns/table_di_set.py`

## Uniform output
Sets `question_pattern` to `table_di_set` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python pipeline/patterns/run_pipeline.py --limit-papers 20 --out-dir pipeline/patterns/out/sample
```

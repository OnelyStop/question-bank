# Data sufficiency

**Pattern id:** `data_sufficiency`

## When to apply
Statements I/II/(III) sufficiency format

## Code skill
`pipeline/patterns/patterns/data_sufficiency.py`

## Uniform output
Sets `question_pattern` to `data_sufficiency` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python pipeline/patterns/run_pipeline.py --limit-papers 20 --out-dir pipeline/patterns/out/sample
```

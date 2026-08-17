# Reading comprehension set

**Pattern id:** `reading_comprehension_set`

## When to apply
Directions say read the passage / according to the passage

## Code skill
`pipeline/patterns/patterns/reading_comprehension_set.py`

## Uniform output
Sets `question_pattern` to `reading_comprehension_set` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python pipeline/patterns/run_pipeline.py --limit-papers 20 --out-dir pipeline/patterns/out/sample
```

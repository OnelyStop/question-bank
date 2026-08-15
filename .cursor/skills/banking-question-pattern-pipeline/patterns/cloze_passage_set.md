# Cloze passage set

**Pattern id:** `cloze_passage_set`

## When to apply
Passage blanks numbered/denoted; fit blank (N)

## Code skill
`India/banking/pattern_pipeline/patterns/cloze_passage_set.py`

## Uniform output
Sets `question_pattern` to `cloze_passage_set` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 20 --out-dir India/banking/pattern_pipeline/out/sample
```

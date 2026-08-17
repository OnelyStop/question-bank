# Image / figure based

**Pattern id:** `image_figure_based`

## When to apply
Figure/diagram cues or context image blocks

## Code skill
`pipeline/patterns/patterns/image_figure_based.py`

## Uniform output
Sets `question_pattern` to `image_figure_based` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python pipeline/patterns/run_pipeline.py --limit-papers 20 --out-dir pipeline/patterns/out/sample
```

# Bilingual stem/directions

**Pattern id:** `bilingual_stem_directions`

## When to apply
Non-Latin script + English co-occur (secondary)


**Secondary pattern:** sets `is_bilingual` and is listed in `secondary_patterns`; does not replace primary.
## Code skill
`pipeline/patterns/patterns/bilingual_stem_directions.py`

## Uniform output
Sets `question_pattern` to `bilingual_stem_directions` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python pipeline/patterns/run_pipeline.py --limit-papers 20 --out-dir pipeline/patterns/out/sample
```

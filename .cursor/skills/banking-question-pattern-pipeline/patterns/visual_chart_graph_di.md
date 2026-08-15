# Visual chart/graph DI

**Pattern id:** `visual_chart_graph_di`

## When to apply
Pie/bar/line/radar chart language

## Code skill
`India/banking/pattern_pipeline/patterns/visual_chart_graph_di.py`

## Uniform output
Sets `question_pattern` to `visual_chart_graph_di` (unless secondary-only). Keep `stem`, `options`, `direction_text`, and paper metadata unchanged aside from classification fields.

## Tuning
Edit the regex/signals in the Python skill, then re-run:

```bash
python India/banking/pattern_pipeline/run_pipeline.py --limit-papers 20 --out-dir India/banking/pattern_pipeline/out/sample
```

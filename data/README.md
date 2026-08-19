# data

Everything the pipeline produces. `corpus/` is the input; nothing here is edited
by hand.

```
papers/              step 1's output — one JSON per paper, committed
questions.jsonl.gz   the final export — derived, not committed
build_report.json    counts and fill rates from the run that produced it
```

## Why papers/ is committed but the export isn't

`papers/` costs something real to regenerate: PyMuPDF, 414 MB of PDFs, and a
full extraction run. Committing it means whoever owns steps 2–5 can work
immediately.

`questions.jsonl.gz` is one command away from `papers/`, so it stays out. Delete
it, re-run step 4, get it back.

## Shape

Each line of the export is [`schema/schema.json`](../schema/README.md) — 28
fields, flat, with the paper's identity copied onto every question so the app can
filter without a join.

The per-paper files in `papers/` carry the same fields, nested inside the paper
they came from, and gain more of them at each step. See
[the pipeline](../pipeline/README.md).

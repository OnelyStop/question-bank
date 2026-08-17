# data

The clean output. One file, written by step 4 of the pipeline:

```
questions.jsonl.gz    one question per line, gzipped
build_report.json     counts and fill rates from the run that produced it
```

**Empty right now** — the pipeline that writes it hasn't been built yet. See
[the pipeline steps](../README.md#the-pipeline).

Nothing here is edited by hand and nothing here is a source. Delete it, re-run
step 4, and you get it back. Everything it's derived from lives in
[`corpus/`](../corpus/README.md).

The shape of each line is [`schema/schema.json`](../schema/README.md) — 28
fields, flat, with the paper's identity copied onto every question so you can
filter without a join.

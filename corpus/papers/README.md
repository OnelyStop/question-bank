# papers

Previous-year banking papers, parsed from the official PDFs.

```
{bank}/{role}/{year}/{stage}/{shift}/{paper_id}.json   one file per paper
puzzles/                                               reasoning puzzle sets
index.jsonl                                            one row per question, for filtering
parse_report.json                                      per-PDF conversion status
SCHEMA.md                                              the format, in full
```

Unknown metadata uses `_unknown_*` path segments, so a paper whose shift was
never recorded still lands somewhere predictable.

Start with `index.jsonl` if you want to filter by bank, role or year without
opening 246 files. Read `SCHEMA.md` before relying on any field — several
(`topic`, `topic_confidence`, `topic_source`) are reserved and still null.

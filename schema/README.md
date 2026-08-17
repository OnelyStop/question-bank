# schema

One file — [`schema.json`](schema.json) — covering everything this repo
produces. Four definitions under `$defs`:

| `$def` | Describes |
|---|---|
| `paper_file` | a paper under `data/papers/`, questions nested inside |
| `index_row` | one flat row per question in `data/papers/index.jsonl` |
| `parse_report` | the per-run summary written beside the papers |
| `question_pattern` | the closed list of 14 patterns |

## The app's tables are not here

This repo extracts and validates. It does not own the database.

`papers`, `directions`, `questions`, `attempts`, `attempt_answers` and
`user_topic_stats` are defined in the **frontend repo** as Drizzle schema
(`src/db/schema.ts`), created by `bun run db:migrate`, with their RLS policies
beside them. Three of those six this repo never writes a single row for — they
are filled by the app at runtime.

`build_feature_tables.py` exports JSONL for the importer to read. The shape of
that export is whatever the build script writes; the app validates it on the
way in. A schema here would be a second definition of someone else's tables,
kept in sync by hand.

## paper_file

A paper is one file, so `bank`, `role`, `year` and `shift` are stored once at
the top and every question inherits them. `paper_id` is
`{bank}_{role}_{year}_{stage}_{shift}_{hash8}`.

Questions carry `direction_id` so a puzzle or DI set stays linked to the passage
it shares, and `metrics` records what the parser could and could not see.

## index_row

The same questions flattened, one row each, so a filter over 21,044 questions
doesn't have to open 243 files. Every field carries `x-fill` — the percentage of
rows where it is non-null, measured from the data rather than asserted.

Two are worth knowing before you build on it: **`answer` is 0%** and **`topic`
is 0%**. `section` is partial. The pipeline that fills them is described in the
root [README](../README.md).

## question_pattern

The only thing here enforced at runtime: `pipeline/patterns/validate.py` fails
any row whose `question_pattern` is outside the 14. Each entry keeps its
description and detection signals under `x-patterns`, and the human-readable
write-up of each lives in `.cursor/skills/banking-question-pattern-pipeline/`.

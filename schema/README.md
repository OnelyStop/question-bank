# schema

Nine files. Two describe data that is committed to this repo, six describe the
tables the app imports, and one is a controlled vocabulary.

```
papers.schema.json     the paper files in data/papers/
papers.SCHEMA.md       the same format, in prose — read this one first
feature_tables/        the six tables build_feature_tables.py exports
question_patterns.json the 14 patterns a question may be classified as
```

## One question schema

`feature_tables/questions.schema.json` is it. A question is exported once, with
a `paper_id` pointing at its paper.

The pipeline does flatten questions into an intermediate on the way there —
`extract.py` copies the paper's `bank`, `year`, `shift` and so on onto every
row so patterns can be classified across the whole corpus at once. That
intermediate has no schema file, and shouldn't: it is written and consumed by
`pipeline/patterns/` within a single run, its output is gitignored, and the
function in `extract.py` is the only contract anything checks against. A JSON
Schema sitting beside it would have been a second definition that no code
reads and nothing keeps in sync.

## papers.schema.json · papers.SCHEMA.md

The source shape — what `pipeline/pdf/` wrote into `data/papers/`. A paper is
one file with its questions nested inside, so bank, year and shift are stored
once at the top rather than on every question.

This one earns a committed schema because the data it describes is committed,
and the PDFs it came from are gone.

## feature_tables/

| Table | Rows | Filled by |
|---|---|---|
| `papers` | 235 | the pipeline |
| `directions` | 3,039 | the pipeline |
| `questions` | 18,651 | the pipeline |
| `attempts` | 0 | the app, at runtime |
| `attempt_answers` | 0 | the app, at runtime |
| `user_topic_stats` | 0 | the app, at runtime |

The three empty ones ship as schemas with no rows on purpose — they define what
the app writes, not what the pipeline produces.

## question_patterns.json

Not a schema — the closed list of 14 patterns. `pipeline/patterns/validate.py`
fails any row whose `question_pattern` is not in it. This is the only file here
that is enforced at runtime.

## No DDL here

There is no `CREATE TABLE` in this repo. The tables are defined in the frontend
repo as Drizzle schema (`src/db/schema.ts`) and created by `bun run db:migrate`,
so migrations stay in one place with RLS policies beside them. The JSON Schema
files here describe the *export* — the contract an importer checks against, not
the database definition.

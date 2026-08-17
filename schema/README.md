# schema

Ten files, because a question changes shape three times on its way from a PDF
to the app. Each stage needs its own contract.

```
papers.schema.json     ①  a paper file, questions nested inside it
uniform_question.*     ②  one flat question, paper metadata copied onto it
feature_tables/        ③  the six normalized tables the app imports
```

## ① papers.schema.json · papers.SCHEMA.md

The source shape — what `pipeline/pdf/` writes into `data/papers/`. A paper is
one file and its questions live inside it, so the bank, year and shift are
stored once at the top.

`papers.SCHEMA.md` is the same format written out in prose, and is the one to
read first.

## ② uniform_question.schema.json

The intermediate, written by `pipeline/patterns/extract.py`. Questions are
pulled out of their papers into one flat list so patterns can be classified
across the whole corpus at once.

Nothing links back to a paper at this stage, so the paper's identity is copied
onto every question — `bank`, `role`, `exam_type`, `year`, `shift`, `subject`,
`language`. That duplication is the point of the stage, not an oversight.

## ③ feature_tables/

The six tables `build_feature_tables.py` exports.

| Table | Rows | Filled by |
|---|---|---|
| `papers` | 235 | the pipeline |
| `directions` | 3,039 | the pipeline |
| `questions` | 18,651 | the pipeline |
| `attempts` | 0 | the app, at runtime |
| `attempt_answers` | 0 | the app, at runtime |
| `user_topic_stats` | 0 | the app, at runtime |

Here the twelve copied fields from ② collapse back into a single `paper_id`,
and the columns the app needs appear: `is_active`, `difficulty`, `marks`,
`negative_marks`, `content_hash`.

The three empty tables ship as schemas with no rows on purpose — they define
what the app writes, not what the pipeline produces.

## question_patterns.json

Not a schema — the closed list of 14 patterns a question can be classified as.
`pipeline/patterns/validate.py` fails any row whose `question_pattern` is not
in it.

## No DDL here

There is no `CREATE TABLE` in this repo. The tables are defined in the frontend
repo as Drizzle schema (`src/db/schema.ts`) and created by `bun run db:migrate`,
so migrations stay in one place with RLS policies beside them. The JSON Schema
files here describe the *export* — treat them as the contract the importer
checks against, not as the database definition.

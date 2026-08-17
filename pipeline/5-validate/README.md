# 5 — validate

Refuse to ship a broken export.

**Reads** `data/questions.jsonl.gz` · **Writes** exit 0, or a list of failures

This step's job is to fail. If it never fails, it isn't checking anything.

## What it has to check

**Every row against the schema.** Types, required fields, and the
`question_pattern` enum from [`schema/schema.json`](../../schema/README.md).
`check_schema.py` does the enum today and nothing else.

**Answers are answerable.** Every `answer` is a key that actually exists in that
question's `options`. An answer of `"e"` on a four-option question is a bug that
reaches the user as an unwinnable question.

**Passage integrity.** Every `direction_hash` groups questions that genuinely
share a passage; every `direction_id` resolves within its own paper. Remember
`direction_id` is paper-scoped — only 30 distinct values across every paper — so
grouping by it alone merges unrelated exams.

**No leaked provenance.** No source book, coaching brand, internal id or URL.
`check_no_provenance.py` does this.

**No duplicate `q_id` and no duplicate `content_hash`.** If step 4 worked there
are none; this is how you find out it didn't.

**Fill rates against the previous run — and fail if a field went backwards.**
This is the most valuable check here and it doesn't exist yet. A parser change
that silently drops `options` on 2,000 questions should stop the build. Keep the
last run's `build_report.json` and compare.

## Known-bad states it should catch today

These are all real, from the last export:

| | |
|---|---|
| `answer` 0% | should fail the build outright — the export is unusable |
| `image_refs` empty on 986 questions flagged `has_image` | unanswerable questions |
| `section` 17%, `shift` 20% | too sparse to expose as a filter |

Decide which of these are hard failures and which are warnings, and write the
threshold down. A check whose threshold lives in someone's head gets argued with
instead of fixed.

## Output

[`output.json`](output.json) — a report, not a pass/fail line.

`passed` is the gate. `checks[]` records every check that ran, including the ones
that passed, so an absent check is visible rather than silently skipped.
`failures[]` names the field, the count, and a sample of `q_id`s so the fix
doesn't need a grep. `fill{}` is kept so the next run can compare against it and
fail on a regression.

The committed example is the **current real state** of the last export: `answer`
0%, 986 questions flagged for a figure that doesn't exist, `section` at 17%. It
should fail today, and it does.

## Done when

- It fails on a deliberately corrupted export — try it: flip an `answer` to a
  key that doesn't exist, duplicate a `q_id`, drop a required field.
- It runs in CI on every export, not by hand.
- Its output names the `q_id` and the field for every failure, so the fix is
  obvious without opening the file.

## What's here

| | |
|---|---|
| `check_schema.py` | validates `question_pattern` against the enum. That's all it does |
| `check_no_provenance.py` | 104 lines, greps the output for source books, brands, URLs |

Both are narrow. The schema check should validate the whole row, not one field.

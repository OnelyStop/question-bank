# 2 — classify

Label what each question is. **Nothing here needs the PDFs**, so this step can be
worked on and tested today.

**Reads** `corpus/papers/` · **Writes** the same files, with labels added

## What it has to do

**Strip the Devanagari first.** 1,350 questions carry the Hindi appended to the
English stem and options. Every label below is computed from the text, so
leftover Hindi poisons all of them. If step 1 has been fixed this is already done
— until then, do it here.

**`section`** — Quantitative, Reasoning, English, GA, Computer.

**`topic`** — from `topic_taxonomy.json`. Real values it produces:
Data_Interpretation, Seating_Arrangement, Error_Spotting, Arithmetic,
Reading_Comprehension, Vocabulary, Puzzle, Inequality, Syllogism, Number_Series,
Para_Jumble.

**`difficulty`** — integer, 1 easiest. Nothing computes this yet.

**`question_pattern`** — one of 14 structural patterns, from `patterns/`. Must be
in the enum in [`schema/schema.json`](../../schema/README.md); step 5 fails the
build otherwise.

**Propagate `section` across a direction set.** If four of five questions under
one passage are Reasoning, the fifth is too. This is the cheapest accuracy win
available — 71% of questions belong to a set.

## This step already mostly works

Run against the previous extraction, `label_topics.infer_labels()` labels
**13,569 of 18,651 questions (73%)**:

| | Before | After |
|---|---|---|
| `section` | 17% | **73%** |
| `topic` | 0% | **73%** |

Label sources came out as: 12,211 from rules, 1,010 from a section fallback, 348
cross-section, 5,082 unlabelled.

So the job here is less "write a classifier" than "wire up the one that exists and
push 73% higher". Two known problems to fix:

- It was importable only through the PDF module, which pulled in PyMuPDF for no
  reason. That coupling is now gone — don't reintroduce it.
- Some existing `section` values are wrong. A percentage/DI question was labelled
  Reasoning. Don't trust the 17% that's already populated; recompute it.

## Output

[`output.json`](output.json) — step 1's 17 fields plus four:

```
section   topic   difficulty   question_pattern
```

21 of 28. Nothing else changes.

Keep `label_source` and `label_confidence` in your own run report, not on the
question — a label from a rule and a label from a section fallback are worth very
different amounts, and you'll want to trace a bad batch. They're deliberately not
schema fields; the app has no use for them.

## Done when

- `section` and `topic` are above 90%.
- No `question_pattern` outside the 14-value enum.
- Every question in a direction set has the same `section` as its siblings.
- Spot-check: pull 20 questions per topic and read them. A misfiled topic is
  invisible in aggregate and obvious on the page.

## What's here

| | |
|---|---|
| `label_topics.py` | 439 lines — `infer_labels(section, direction, stem, options)` |
| `label_sections.py` | 444 lines, plus `propagate_direction_sections()` |
| `topic_taxonomy.json` | the topic vocabulary |
| `patterns/` | 14 detectors + `base.py`, one file per pattern |
| `classify.py` | dispatches a question through the detectors |

Each pattern has a written spec in
`.cursor/skills/banking-question-pattern-pipeline/patterns/` — read the one for a
pattern before changing its detector.

# papers-deduped

A deduplicated pass over the same papers as `../papers/`, uploaded as received.

305 files, 235 unique `paper_id`s, 18,651 questions. Same schema as `../papers/`
plus a `subject` field (198 of 235 papers are `Unclassified`).

`../papers/` is unchanged and remains the reference copy.

## Read before relying on this

It is a strict subset of `../papers/` — it adds nothing and removes 2,393
questions. **1,459 of those are genuine duplicates. The other 934 exist nowhere
else in this folder.**

The dedupe matched on stem text alone, and banking papers reuse stems heavily:

```
DROPPED  Select the word that fits blank (78).     options: 81, 9, 1
KEPT     Select the word that fits blank (78).     options: 248, 348, 358
```

Different papers, different cloze passages, different questions. 381 were lost to
that collision; another ~500 are sentence-rearrangement items
(`Which of the following would be the THIRD sentence after rearrangement?`),
which every English paper carries with a different set of sentences.

Deduping on **stem + options** instead yields 19,354 questions — it collapses
1,690 true duplicates, more than this pass found, while keeping the 703 it
discarded.

Two other things to know:

- 29 `paper_id`s appear in more than one file here (up to 4 copies each), so
  reading the tree naively double-counts questions.
- No `index.jsonl`, `SCHEMA.md`, `parse_report.json` or `puzzles/`. Use
  `../papers/SCHEMA.md` for the field definitions.

## What it gets right

- 1,459 real content duplicates removed.
- Two PDFs that `../papers/` files twice under different paths, same content
  hash: `…3d393f68` (Prelims and `_unknown_stage`) and `…da38d550`.
- Four empty papers whose parse had failed.

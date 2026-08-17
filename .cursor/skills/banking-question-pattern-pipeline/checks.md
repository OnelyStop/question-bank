# Quality check skills

**Code:** `India/banking/pattern_pipeline/checks/*.py`
**Driver:** `India/banking/pattern_pipeline/quality.py`
**CLI:** `India/banking/pattern_pipeline/validate.py`

Pattern skills say *what* a question is. Check skills say *whether it is
serveable*. Same architecture: one skill per file, registered in
`checks/__init__.py` as `ROW_CHECKS` / `CORPUS_CHECKS`.

Reason codes are the ones `India/banking/sets/` already uses (see its README), so
both lanes speak one vocabulary.

## Tiers

| Tier | Meaning | Effect |
|------|---------|--------|
| `fatal` | Violates `schema/uniform_question.schema.json` or the Supabase DDL | The load breaks. Must be zero. |
| `blocking` | Loads fine, but cannot be shown to a candidate | Held back into `out/flagged.jsonl` |
| `suspect` | Probably an extraction artifact | Ships, but listed for review |
| `info` | Known coverage gap | Counted only, never fails |

`validate.py --tier X` exits non-zero on X or worse. Default `blocking`.

## Where a rule belongs

- **Pattern-specific** ("a table DI set with no table") → `PatternSkill.validate()`
  on that pattern. The classifier already decided the pattern, so the pattern is
  the thing that knows what completeness means for itself.
- **Cross-pattern** ("an option cleaned away to nothing") → a check skill here.

Five patterns implement `validate()`: `visual_chart_graph_di`,
`image_figure_based`, `table_di_set`, `reading_comprehension_set`,
`cloze_passage_set`, `caselet_di_set`, `quadratic_comparison`,
`partial_or_missing_options`.

## Row checks

| Skill | Reason | Tier | Fires when |
|-------|--------|------|-----------|
| `schema_conformance` | `schema_violation` | fatal | Missing/unknown key, bad enum, wrong type. Reads the schema file itself, so it cannot drift. |
| `stem_too_short` | `stem_too_short` | blocking | Empty stem, or a bare `Question 131.` placeholder. Short-but-real is `suspect`. |
| `option_partial` | `option_partial` | blocking | Fewer than 4 options, or a gap in the a–e run (`a,b,d,e` means one was dropped and every answer key shifts). |
| `option_empty` | `option_empty` | blocking | An option cleaned away to nothing. |
| `option_duplicate` | `option_duplicate` | blocking | Two options identical once normalised. |
| `option_bleed` | `option_bleed` | blocking | A full `(a)…(b)…(c)` run still inside the stem, or the next question welded to an option. |
| `context_missing` | `context_missing` | blocking | A set-pattern with no directions, or a stem referring back to context it lacks. |
| `context_unusable` | `context_unusable` | blocking | Directions that announce a chart/table but carry no numbers — the data was only in the image. |
| `text_garbled` | `text_garbled` | blocking | Private-use glyphs, replacement chars, control chars. |
| `language_script` | `language_<script>` | blocking | Asked *only* in a non-Latin script. Bilingual rows keep their English half and pass at `info`. |
| `fraction_flattened` | `fraction_flattened` | suspect | `30 10/13 %` arrived as `30 10 13 %`. |
| `stem_truncated` | `stem_truncated` | suspect | Stem stops mid-clause or starts mid-word. |
| `brand_residue` | `brand_residue` | suspect | Coaching brand, URL, book title or promo survived. Regexes shared with `tools/verify.py`. |

## Corpus checks

| Skill | Reason | Tier | Fires when |
|-------|--------|------|-----------|
| `duplicate_content` | `duplicate_q_id` | fatal | Same `q_id` twice — `banking_questions.q_id` is `unique`. |
| `duplicate_content` | `duplicate_content` | suspect | Same stem + options under a different `q_id`; dedupe is keyed on `q_id` alone. |
| `direction_set_integrity` | `direction_id_conflict` | blocking | One `(paper_id, direction_id)` mapping to two different bodies. |
| `direction_set_integrity` | `direction_set_broken` | suspect | A direction covering more than 12 questions. |

`direction_id` is only unique **within a paper** — always scope it by
`paper_id + direction_id`.

## Adding a check

1. Add `checks/<id>.py` implementing `CheckSkill` (or `CorpusCheckSkill`).
2. Register it in `checks/__init__.py`.
3. Add a row to the table above.
4. Add an assertion to `validate.py --selftest`.
5. Re-run and compare `flagged_counts` in `out/report.json`.

## Two traps worth knowing

- **Case matters on `(a)`.** Only lowercase `(a)` marks an MCQ option; uppercase
  `(A)` labels a stimulus or rearrangement fragment. Making `option_bleed`
  case-insensitive flags 1,387 rows instead of 300.
- **`%` is not always a percent sign.** It is a defined operator in
  symbol-notation reasoning (`A%B means A is the child of B`) and a code glyph in
  coding-decoding sets. Treating it as a numeric cue quarantines ~100 answerable
  questions.

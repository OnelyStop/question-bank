# 1 — extract

PDFs in, questions out.

**Reads** `corpus/remaining/` · **Writes** `data/batch{n}/{1..10}.json` + a
matching `.pdf` of each paper, and `index.json` mapping the numbers to sources.
Parsed PDFs move to `corpus/done/`, so `remaining/` is always the work left.

## Running it

Ten papers at a time, so a batch can be read before the next one starts. No
arguments — it takes the next ten from `corpus/remaining/`:

```bash
python3 pipeline/1-extract/parser.py                          # next 10
python3 pipeline/1-extract/check_gaps.py --root data/batch1   # what is missing
python3 pipeline/1-extract/research.py  --root data/batch1    # search for it
```

Only what parsed is moved — a PDF that raised stays in `remaining/` for the next
run rather than being quietly filed as done. `--keep` parses without moving
anything, for re-running a batch.

Solutions-only PDFs and Hindi editions of papers already held in English are
moved straight to `done/` without parsing: they yield 0-1 questions and would
otherwise burn a slot in every batch. 136 of the 365 files were these.

Every paper is also rendered back to a readable PDF beside its JSON. Extraction
defects are obvious on a page and invisible in JSON — a stem that lost its
middle, options that ran together, a passage glued to the wrong question.

## What the parser handles

Each rule below is here because a real paper needed it. They are not
hypothetical, and removing one costs the questions named.

**Two-column pages.** The gutter is found from **text blocks only**: a centred
watermark straddling it makes it undetectable, and with no gutter the page falls
back to top-to-bottom order, which interleaves the columns and severs stems from
their options.

**Stacked fractions.** `15/100 × 200/700 × ? = 240` prints as separate boxes —
numerators at half height, denominators below, often in different blocks. They
are rejoined using the **fraction bar**, an actual vector line in the PDF. That
signal is what distinguishes a numerator from a question number sitting above a
maths stem; without it, `Q54.` merges into the line below and the question
disappears.

**Directions, in three layouts.** Numbered (`Directions (11–15):`), unnumbered
(`Read the given passage…`, covering questions by position), and — in two of ten
papers — printed *after* their question and repeated for every question in the
set. That last one is why directions are taken from inside the question's own
block where one appears there: matched by document position they land one
question late, and the passage stays glued to the previous stem.

**Options in four shapes.** The usual `(a) … (e)` list; `A.` line-start; error
spotting, where the options are the sentence's own `(a)/ (b)/` segments; and
sets that state the five choices **once in the direction** (`give answer (a) if
x > y`) and print only equations under each number.

**Cloze blanks.** The stem is a blank inside the passage — `____(18)___` or a
bare `(15)` — so it is taken as the sentence containing that blank.

**Bilingual papers.** The Devanagari is removed run by run, keeping the English
wherever it sits. Cutting at the first Devanagari character instead wiped
directions whose prose is Hindi but whose `(a)…(e)` labels are Latin. Where a
question is Hindi-only, the Hindi is kept — it is still the question.

**Numbering style per paper.** Where `Q41.` is the house style, a bare `1.` is a
list item inside a stem or a table row, not a question. Requiring the dominant
style only where one clearly dominates leaves bare-numbered papers alone.

## Output

```json
{
  "q_num": 78,
  "stem": "\\frac{32}{35} \\div \\frac{1}{5} \\times \\frac{7}{8} \\div \\frac{2}{35} = ?",
  "options": {"a": "60", "b": "80", "c": "75", "d": "90", "e": "70"},
  "direction_text": "What should come in place of the question mark?"
}
```

Four fields, no more. Maths goes into `stem` as LaTeX in place -- a parallel
`stem_latex` would be a second version to keep in step. Prose stems are
untouched; the conversion only fires on text that is actually maths. The LaTeX
carries no `$...$` delimiters, so a maths stem is entirely LaTeX and a prose
stem entirely plain.

Paper-level: `bank`, `role`, `exam_type`, `year`, `memory_based`,
`question_count`. There is no `shift` — it is unknowable for most of these
papers, which are practice compilations rather than one sitting, and an
`unknown_shift` placeholder was only ever noise.

## Where it stands

| Batch | Questions | Complete |
|---|---|---|
| 1 — the ten easiest IBPS papers | 928 | 924 (99.6%) |
| 2 | 1,222 | 1,169 (95.7%) |

156 PDFs in `corpus/done/`, 219 left in `corpus/remaining/`.

What is not complete has no text to extract: options rendered as images, so the
PDF holds `(a) (b) (c) (d) (e)` with nothing behind them, and Hindi-only stems.

## Not handled

- **Scanned pages.** No text layer, no OCR. One paper in the corpus is affected.
- **Section-split PDFs.** `… – Quantitative` / `… – Reasoning` are fragments of
  one sitting; each parses as a whole paper of 10–24 questions.
- **Superscripts.** `2x2` in the JSON is 2x² in the paper. Recoverable from span
  baseline-shift the same way fractions were, if it turns out to matter.
- **Intentional line breaks inside a passage.** Every join site (`split_options`,
  direction-body extraction, stem cleanup) ends in `" ".join(text.split())`,
  which collapses all whitespace to single spaces -- including line breaks that
  were meaningful, like one-statement-per-line coding/seating passages
  ("P@Q means P is East of Q...", one rule per line). Nothing is lost -- every
  word survives -- but the passage reads as a flattened wall of text instead of
  its original layout. A real fix exists (PyMuPDF gives each line's bounding
  box, so a line ending well short of the column's right margin plus extra
  vertical leading before the next line is a decent signal for "this break was
  intentional," the same kind of geometric signal the gutter and fraction-bar
  detection already use) but it touches every join site in the parser, and this
  codebase has a history of "should be safe" general changes regressing a
  specific paper. Not attempted. Flag questions like this for manual review
  rather than guessing.

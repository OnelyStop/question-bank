# 1 — extract

PDFs in, questions out.

**Reads** `corpus/pdf/{bank}/…/*.pdf` · **Writes** `data/batch{n}/{1..10}.json` + a
matching `.pdf` of each paper, and `index.json` mapping the numbers to sources.

## Running it

Ten PDFs at a time, so a batch can be read before the next one starts:

```bash
python3 pipeline/1-extract/parser.py corpus/pdf/IBPS               # batch 1
python3 pipeline/1-extract/parser.py corpus/pdf/IBPS --batch 2     # the next 10
python3 pipeline/1-extract/check_gaps.py --root data/batch1        # what is missing
python3 pipeline/1-extract/research.py  --root data/batch1         # search for it
```

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
  "stem": "32/35 ÷ 1/5 × 7/8 ÷ 2/35 = ?",
  "stem_latex": "\\frac{32}{35} \\div \\frac{1}{5} \\times \\frac{7}{8} = ?",
  "options": {"a": "60", "b": "80", "c": "75", "d": "90", "e": "70"},
  "direction_text": "What should come in place of the question mark?"
}
```

`stem_latex` and `options_latex` appear **only** where the text is genuinely
maths, so a reader can tell which questions need a maths renderer. The plain
text is always present and always readable.

Paper-level: `bank`, `role`, `exam_type`, `year`, `memory_based`,
`question_count`. There is no `shift` — it is unknowable for most of these
papers, which are practice compilations rather than one sitting, and an
`unknown_shift` placeholder was only ever noise.

## Where it stands

Batch 1, the ten easiest IBPS papers: **928 questions, 924 complete (99.6%)**.

The four that are not complete have no text to extract — their options are
rendered as images, so the PDF holds `(a) (b) (c) (d) (e)` with nothing behind
them.

## Not handled

- **Scanned pages.** No text layer, no OCR. One paper in the corpus is affected.
- **Section-split PDFs.** `… – Quantitative` / `… – Reasoning` are fragments of
  one sitting; each parses as a whole paper of 10–24 questions.
- **Superscripts.** `2x2` in the JSON is 2x² in the paper. Recoverable from span
  baseline-shift the same way fractions were, if it turns out to matter.

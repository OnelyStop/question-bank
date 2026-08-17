# Question bank file schema

Structured output from `pdf_to_questions.py`. Source PDFs live under `corpus/`; converted data lives under `question_bank/`.

## Directory layout

```text
question_bank/
  SCHEMA.md                 ← this file
  index.jsonl               ← one JSON object per question (flat, filter-friendly)
  parse_report.json         ← conversion run summary + per-PDF status
  {bank}/{role}/{year}/{exam_type}/{shift}/{paper_id}.json
```

Path mirrors `corpus/` when metadata is known:

```text
question_bank/IBPS/Clerk/2019/Prelims/_unknown_shift/ibps_clerk_2019_prelims_unknown_shift_237fb266.json
```

Unknown metadata uses `_unknown_*` segments (same as corpus).

| File type | Format | Purpose |
|-----------|--------|---------|
| Paper JSON | `.json` | Full paper: metadata + all questions + passages |
| Index | `index.jsonl` | Fast filter by bank / year / exam without loading papers |
| Report | `parse_report.json` | QA: ok / skipped / failed counts per source PDF |

---

## 1. Paper JSON (`*.json`)

One file per successfully parsed (or failed-empty) PDF.

### Root object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `paper_id` | string | yes | Stable id: `{bank}_{role}_{year}_{exam_type}_{shift}_{sha8}` |
| `source` | object | yes | Provenance (see below) |
| `bank` | string \| null | yes | e.g. `IBPS`, `SBI`, `RBI` |
| `role` | string \| null | yes | e.g. `PO`, `Clerk`, `RRB` |
| `exam_type` | string \| null | yes | `Prelims` or `Mains` (from corpus `stage`) |
| `year` | integer \| null | yes | Exam year, e.g. `2019` |
| `shift` | string \| null | yes | e.g. `Shift_1`, or null if unknown |
| `memory_based` | boolean | yes | From filename / meta sidecar |
| `language` | string \| null | yes | Usually `english`; Hindi PDFs are skipped |
| `parse_status` | string | yes | `ok`, `partial`, `failed` |
| `parse_notes` | string[] | yes | Parser warnings (empty if clean) |
| `question_count` | integer | yes | Length of `questions` |
| `questions` | array | yes | Question objects (see below) |

### `source` object

| Field | Type | Description |
|-------|------|-------------|
| `pdf_path` | string | Relative path under repo, e.g. `corpus/IBPS/Clerk/2019/...pdf` |
| `sha256` | string \| null | Content hash from `*.pdf.meta.json` |
| `source_url` | string \| null | Original download URL if known |
| `source_filename` | string | Original PDF filename |

### `paper_id` format

```text
{bank}_{role}_{year|noyear}_{exam_type}_{shift|unknown_shift}_{sha256[:8]}
```

Example: `ibps_clerk_2019_prelims_unknown_shift_237fb266`

---

## 2. Question object (inside `questions[]`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `q_id` | string | yes | `{paper_id}::q{num:03d}` e.g. `...::q001` |
| `q_num` | integer | yes | Question number in the paper |
| `section` | string \| null | yes | `Reasoning`, `Quantitative`, `English`, `GA`, `Computer`, or null |
| `topic` | string \| null | yes | **Reserved** — null until topic labelling |
| `topic_confidence` | number \| null | yes | **Reserved** — null until labelling |
| `topic_source` | string \| null | yes | **Reserved** — e.g. `rules`, `llm`, `manual` |
| `direction_id` | string \| null | yes | Links questions sharing a passage, e.g. `d001` |
| `direction_text` | string \| null | yes | Shared Directions / passage / DI table context |
| `stem` | string | yes | Question text (without options) |
| `options` | object | yes | Keys `a`–`e` → option text (may be partial) |
| `answer` | string \| null | yes | Correct option key; null unless present in PDF |
| `explanation` | string \| null | yes | Solution text; null unless present in PDF |
| `metrics` | object | yes | Parse QA metrics (see below) |

### `options` object

```json
{
  "a": "One",
  "b": "Two",
  "c": "Three",
  "d": "Four",
  "e": "More than four"
}
```

Options are normalized to lowercase keys. Missing options are omitted (not empty strings).

### `metrics` object

| Field | Type | Description |
|-------|------|-------------|
| `has_passage` | boolean | `direction_text` is set for this question |
| `option_count` | integer | Number of options parsed (`0`–`5`) |
| `stem_char_len` | integer | Character length of `stem` |
| `page_start` | integer \| null | First PDF page (1-based) |
| `page_end` | integer \| null | Last PDF page for this question block |

### Direction groups

Puzzle / RC / DI sets share one `direction_id` and `direction_text`:

```json
{
  "q_num": 1,
  "direction_id": "d001",
  "direction_text": "Eight persons A, B, C... sit in a row...",
  "stem": "How many persons sit between B and E?",
  "options": { "a": "One", "b": "Two", ... }
}
```

Cloze blanks may use a synthetic stem: `Select the word that fits blank (79).`

---

## 3. Index row (`index.jsonl`)

One JSON object per line — same questions as paper files, flattened for filtering.

| Field | Type | Description |
|-------|------|-------------|
| `q_id` | string | Same as in paper JSON |
| `paper_id` | string | Parent paper |
| `bank` | string \| null | |
| `role` | string \| null | |
| `exam_type` | string \| null | |
| `year` | integer \| null | |
| `shift` | string \| null | |
| `memory_based` | boolean | |
| `language` | string \| null | |
| `q_num` | integer | |
| `section` | string \| null | |
| `topic` | string \| null | |
| `direction_id` | string \| null | |
| `has_passage` | boolean | |
| `option_count` | integer | |
| `stem` | string | |
| `options` | object | |
| `answer` | string \| null | |
| `pdf_path` | string | From parent `source.pdf_path` |

**Does not include:** `direction_text`, `explanation`, `metrics`, `topic_confidence`, `topic_source` (load paper JSON when needed).

Example filter (Python):

```python
import json
rows = []
with open("question_bank/index.jsonl") as f:
    for line in f:
        r = json.loads(line)
        if r.get("bank") == "IBPS" and r.get("role") == "Clerk" and r.get("year") in (2019, 2020):
            rows.append(r)
```

---

## 4. Parse report (`parse_report.json`)

| Field | Type | Description |
|-------|------|-------------|
| `papers_seen` | integer | PDFs processed in this run |
| `status_counts` | object | Counts by `ok`, `partial`, `failed`, `skipped`, `cached` |
| `total_questions_indexed_approx` | integer | Sum of question counts |
| `papers_with_questions` | integer | Papers with `question_count > 0` |
| `avg_questions_per_parsed_paper` | number | Average over papers with questions |
| `index_rows` | integer | Lines in `index.jsonl` |
| `papers` | array | Per-PDF summary (see below) |

### `papers[]` entry

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `ok`, `partial`, `failed`, `skipped`, `cached` |
| `pdf` | string | Relative path under `corpus/` |
| `paper_id` | string | |
| `question_count` | integer | |
| `with_options` | integer \| null | Questions with ≥4 options |
| `out_path` | string \| null | Relative path under `question_bank/` |
| `reason` | string \| null | Skip reason: `hindi`, `solutions_pdf` |
| `notes` | string[] \| null | Parser notes |

---

## Enumerations

### `parse_status` / paper `status`

| Value | Meaning |
|-------|---------|
| `ok` | Parsed with reasonable option coverage |
| `partial` | Parsed but many questions missing options |
| `failed` | No questions extracted |
| `skipped` | Not converted (Hindi or solutions PDF) |
| `cached` | Skipped re-parse (sha256 unchanged) |

### `section` (when detected)

`Reasoning`, `Quantitative`, `English`, `GA`, `Computer`, or `null`

### `bank` / `role` (from corpus meta)

Common values: `IBPS`, `SBI`, `RBI`, `NABARD`, `SIDBI`; `PO`, `Clerk`, `RRB`, `SO`, `Assistant`, `Grade_B`

---

## Example: minimal paper JSON

```json
{
  "paper_id": "ibps_clerk_2019_prelims_unknown_shift_237fb266",
  "source": {
    "pdf_path": "corpus/IBPS/Clerk/2019/Prelims/_unknown_shift/IBPS_Clerk_Prelims_2019_Memory_Based_Paper_For_Practice.pdf",
    "sha256": "237fb266...",
    "source_url": "https://...",
    "source_filename": "IBPS_Clerk_Prelims_2019_Memory_Based_Paper_For_Practice.pdf"
  },
  "bank": "IBPS",
  "role": "Clerk",
  "exam_type": "Prelims",
  "year": 2019,
  "shift": null,
  "memory_based": true,
  "language": "english",
  "parse_status": "ok",
  "parse_notes": [],
  "question_count": 100,
  "questions": [
    {
      "q_id": "ibps_clerk_2019_prelims_unknown_shift_237fb266::q001",
      "q_num": 1,
      "section": null,
      "topic": null,
      "topic_confidence": null,
      "topic_source": null,
      "direction_id": "d001",
      "direction_text": "Eight persons A, B, C, D, E F, G and H are going to watch movie...",
      "stem": "If E is related to F and H is related to C then...",
      "options": {
        "a": "H",
        "b": "F",
        "c": "C",
        "d": "B",
        "e": "A"
      },
      "answer": null,
      "explanation": null,
      "metrics": {
        "has_passage": true,
        "option_count": 5,
        "stem_char_len": 72,
        "page_start": 1,
        "page_end": 1
      }
    }
  ]
}
```

---

## Current corpus stats (reference)

From last full conversion run:

- **379** PDFs seen → **241** ok, **134** skipped, **4** failed  
- **21,044** questions in `index.jsonl`  
- **243** paper JSON files on disk  

Regenerate with:

```powershell
python pdf_to_questions.py
```

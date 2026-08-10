# Bank exam Telegram PDF collector

Collects PDFs from Telegram channels and sorts them by filename clues (bank, role, year, stage, shift). Keeps **2023+** only.

## Setup

**No my.telegram.org needed.** Uses Telegram Desktop API keys + phone login.

```powershell
cd C:\Users\satin\OneDrive\Desktop\bank_exam
python -m pip install -r requirements.txt
```

## Run (your own PowerShell window)

```powershell
cd C:\Users\satin\OneDrive\Desktop\bank_exam
python collect.py --limit 300
```

1. Enter phone with country code, e.g. `+9198xxxxxxxx`
2. Enter the login **code** Telegram sends you
3. If you use 2FA, enter that password too
4. Downloads go into `corpus/`

## Alternative: web collector (no Telegram login)

If Telegram API keeps failing, collect from coaching sites:

```powershell
python web_collect.py
python web_collect.py --telegram-web   # also scan public t.me/s previews
```

Same `corpus/` folder layout.

## Output layout

```
corpus/
  IBPS/PO/2024/Prelims/Shift_1/....pdf
  SBI/Clerk/2023/Mains/_unknown_shift/....pdf
  _unsorted/2024/....pdf
  _skipped_log.txt
```

Missing stage/shift/role become `_unknown_*`. Yearless or pre-2023 files are skipped and logged.

Each saved PDF gets a sibling `*.pdf.meta.json` with parsed fields + sha256.

## Convert PDFs → question JSON

```powershell
cd C:\Users\satin\OneDrive\Desktop\bank_exam
python pdf_to_questions.py
python pdf_to_questions.py --force   # re-parse everything
python test_pdf_to_questions.py
```

Writes `question_bank/` (per-paper JSON + `index.jsonl` + `parse_report.json`). Hindi / solutions PDFs are skipped.

See [`question_bank/SCHEMA.md`](question_bank/SCHEMA.md) for the full file layout and field definitions. JSON Schema: [`question_bank/question_bank.schema.json`](question_bank/question_bank.schema.json).

## Resume / dedupe

`state.json` stores seen `channel:message_id` keys and content hashes so re-runs skip duplicates.

## Tests

```powershell
python test_filename_parser.py
```

# India — Banking PYQ

## Layout

```text
India/banking/
  raw/notes.md              Placeholder for raw ingest notes
  cleaned/
    notes.md
    question_bank/          Structured JSON from corpus PDFs (see SCHEMA.md)
  collector/                PDF download + PDF→JSON tooling
```

## Regenerate question bank

```powershell
cd India/banking/collector
python -m pip install -r requirements.txt
# Place PDFs under collector/corpus/ (not in git — too large)
python pdf_to_questions.py --corpus corpus --out ../cleaned/question_bank
```

Schema: [`cleaned/question_bank/SCHEMA.md`](cleaned/question_bank/SCHEMA.md)

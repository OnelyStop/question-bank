# pdf_pipeline

Turns a memory-based / previous-year PDF into the same paper JSON shape that
lives under `India/banking/papers/`.

```bash
# from repo root
python tools/pdf_pipeline/pdf_question_pipeline.py --pdf path/to/paper.pdf --force --skip-answers

# or drop PDFs in India/banking/corpus/ (same bank/role/year layout as papers)
python tools/pdf_pipeline/pdf_question_pipeline.py --force --skip-answers
```

Defaults: corpus = `India/banking/corpus`, out = `India/banking/papers`.
Needs `pymupdf`. OCR is optional and skipped if tesseract isn't around.

What it does, roughly: read the page as layout boxes, split into question units,
keep figures only when the question actually needs one (DI / puzzle), label
section/topic, write the paper JSON and rebuild `papers/index.jsonl`.

This is how the `papers/` tree gets (re)built. It is not the sets/ beautify path —
that starts from a pooled extract and ships usable vs flagged slices.

# corpus

The source PDFs. **Not in git** — everything in this folder except this file is
gitignored, because it's tens of gigabytes of third-party exam papers.

**It is currently empty, and that is the repo's biggest problem.** Three things
can't be done without it:

| | |
|---|---|
| `answer` | 0 of 18,651 questions have one |
| `image_refs` | 986 questions need a figure that was never extracted |
| re-extraction | any parser fix can't be re-run over the papers |

## Layout

`pipeline/pdf/` reads the path to work out which exam a PDF belongs to, so the
folder names matter:

```
corpus/
  {bank}/{role}/{year}/{stage}/
    IBPS/Clerk/2019/Mains/ibps_clerk_2019_mains.pdf
    SBI/PO/2023/Prelims/sbi_po_2023_prelims_shift1.pdf
```

`pipeline/pdf/filename_parser.py` handles the filename; `meta_from_path()` in
`pdf_to_questions.py` handles the directory. A PDF that doesn't match lands under
`_unknown_bank` in the output — 235 papers made it through, and the `_unknown`
buckets in `data/papers/` are the ones that didn't.

## Getting it back

Whoever ran the original extraction has these files locally. They were never
committed, so git can't help. Put them back in the layout above and step 1 of
[the pipeline](../README.md#the-pipeline) runs again.

Needs PyMuPDF:

```bash
pip install pymupdf
python3 pipeline/pdf/pdf_to_questions.py --corpus corpus --out data/papers
```

## Why it's separate from data/

`corpus/` is input, `data/` is output. Everything in `data/` was derived from
these PDFs — and since the PDFs are gone, that derived JSON is currently the
only copy. Treat `data/` as irreplaceable until this folder is restored.

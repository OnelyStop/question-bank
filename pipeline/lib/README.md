# lib

Shared by more than one step. Nothing here runs on its own.

| | |
|---|---|
| `corpus.py` | paths, paper loading, boilerplate stripping, `rebuild_index` |
| `context_completeness.py` | decides whether a question has enough context to be answerable |
| `pdf.py` | the one PyMuPDF reader more than one step needs |

The question shape is **not** defined here. `pipeline/1-extract/parser.py` is the
only thing that writes it, and `pipeline/1-extract/output.json` is the contract.
A second, unused copy of that shape lived here and drifted: it went on emitting
`shift` after the field was dropped, and built paper ids as
`ibps_clerk_2020_prelims_unknown_shift_<sha>` where the real writer produces
`ibps_clerk_2020_prelims_<sha>`. `paper_id` is the answer join key, so anything
written against the copy would have produced ids that never join.

`context_completeness.py` is the more interesting one. It's what distinguishes a
question that's merely hard from one that is impossible because its seating
arrangement or chart never made it out of the PDF. That judgement is why the old
`sets/` collection held back 1,255 of 4,851 questions instead of shipping them
looking fine, and it's worth keeping that standard.

Put something here only when a second step needs it. A helper used by one step
belongs in that step's folder, where its owner can change it without coordinating.

# lib

Shared by more than one step. Nothing here runs on its own.

| | |
|---|---|
| `question_schema.py` | 162 lines — the paper JSON shape steps 1–3 read and write |
| `context_completeness.py` | 318 lines — decides whether a question has enough context to be answerable |

`context_completeness.py` is the more interesting one. It's what distinguishes a
question that's merely hard from one that is impossible because its seating
arrangement or chart never made it out of the PDF. That judgement is why the old
`sets/` collection held back 1,255 of 4,851 questions instead of shipping them
looking fine, and it's worth keeping that standard.

Put something here only when a second step needs it. A helper used by one step
belongs in that step's folder, where its owner can change it without coordinating.

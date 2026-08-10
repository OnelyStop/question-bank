Questions before they are cleaned and made ready to use.

`ready.json` — 4,850 questions extracted from the source books, deduped, with an
answer key and five options each. This is what `tools/beautify.py` reads. It is
split into sets of 500, so set N is questions `[(N-1)*500 : N*500]` and that split
is stable: regenerating after a cleaning change must not move a question from one
set to another, or "question 198 in set 1" stops meaning anything.

The text in here is raw and still carries its damage — footers welded to options,
Symbol-font characters as private-use codepoints, running headers, publisher names.
Read `../cleaned/` for the usable version and `../flagged/` for what could not be
salvaged.

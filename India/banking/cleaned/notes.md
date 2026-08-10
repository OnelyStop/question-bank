Questions that are ready to use.

Each set is `N.pdf` (for reading) and `N.json` (for loading). Same questions, same
order, so "question 198 in set 1" means one thing in both.

A question in here carries only the question, its options, the answer, and — when
the question genuinely needs one — the chart or table. No source book, no internal
id, no publisher's name or URL. Directions shared by a set are printed once above
the set, with the set's chart under them, rather than repeated per question.

Anything that could not be made usable is in `../flagged/` with the reason, not
silently dropped and not silently included.

Built by `products/beautify.py`, which reads `products/dataset/ready.json`. Set 1
is done. Sets 2-10 are still the old review PDFs: the image classification in
`products/dataset/assets_classified.json` only covers set 1's images, and running
the pipeline over a later set without extending it drops every chart in that set.
The script warns when this happens.

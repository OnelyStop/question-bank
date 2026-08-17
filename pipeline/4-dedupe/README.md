# 4 — dedupe

Keep one copy of each question, then write the export.

**Reads** `corpus/papers/` · **Writes** `data/questions.jsonl.gz`

Nothing here is written yet. Many overlapping folders will land in `corpus/` —
memory-based papers repeat questions, and the same paper arrives from several
sources.

## Exact duplicates only

Merge only questions that are **character-for-character identical**. No similarity
scores, no thresholds.

```python
def key(q):
    return sha256(
        norm(q["stem"]) + "\x00" +
        "\x00".join(f"{k}={norm(v)}" for k, v in sorted(q["options"].items()))
    ).hexdigest()

def norm(s):
    s = unicodedata.normalize("NFKC", s)   # settles ² vs 2
    s = re.sub(r"\s+", " ", s).strip()     # whitespace, line breaks
    return s.casefold()                    # "Who" == "who"
```

One dict, one pass, O(n). First copy wins.

**Digits are never normalised.** That is the whole safety property.

## Why not something fuzzier

Grouping 3,596 answered questions by their text with the digits stripped out:

| | |
|---|---|
| true duplicates — same words **and** numbers | 182 |
| **same words, different numbers** | **105** |
| same text and numbers, answers disagree | 25 |

**37% of look-alike pairs are not duplicates.** These two are identical strings
once digits are removed, and have different answers:

```
I. 35x2 – 34x – 21 = 0  /  II. 63y² + 55y + 12 = 0     answer: c
I. 3x2 – 5x – 12 = 0    /  II. 2y² + 15y + 25 = 0      answer: a
```

Any threshold that catches the 182 also merges some of the 105 and deletes real
questions — unrecoverable once the source folders are cleared. Exact matching
finds fewer duplicates and never makes that mistake.

If near-duplicates become a real problem later, the shape to add is MinHash + LSH
**gated on the numeric tuple matching exactly**, writing candidates to a review
file rather than merging them. Don't add it speculatively.

## Two things to record while merging

**Where the copies came from.** When N collapse into one:

```json
"seen_in": ["ibps_clerk_2019_mains_…", "ibps_clerk_2021_prelims_…"],
"seen_count": 6
```

A question that appeared in six exams is high-yield, and this is the only place
that fact exists. Dedup normally throws it away.

**Answer conflicts.** Same key, different `answer` — one source is wrong. Write
both to a review file and pick neither.

The surviving record otherwise takes the copy with the most filled fields, prefers
one that has an `answer`, unions the `image_refs`, and keeps the earliest `year`.

## Then the export

Flatten to one line per question, per
[`schema/schema.json`](../../schema/README.md):

- Copy the paper's identity onto every question — `bank`, `role`, `exam_type`,
  `year`, `shift`, `memory_based` — so the app filters without a join.
- Compute `direction_hash` from the passage text; inline `direction_text` and
  `direction_image_refs`.
- Omit nulls. Omit `marks` / `negative_marks` when they equal the default
  (`1`, `-0.25`).
- Truncate `content_hash` to 16 chars.
- Gzip. Repeated passages compress to almost nothing — 23 MB becomes about 3 MB.

## Output

[`output.json`](output.json) is one line of `data/questions.jsonl.gz` — the shape
changes here, from nested paper files to one flat question per line.

What's different from step 3:

| | |
|---|---|
| added | `q_id`, `content_hash`, `direction_hash`, `seen_in`, `seen_count` |
| flattened in | `bank`, `role`, `exam_type`, `year`, `shift`, `memory_based` |
| inlined | `direction_text`, `direction_has_image`, `direction_image_refs` |
| dropped | `stem_hi`, `options_hi`, `body_hi`, `label_source`, `answer_source`, `page_start`, `context_complete` |

The `_hi` fields are dropped because the export is English-only. The audit fields
(`label_source`, `answer_source`) are dropped because they exist to debug steps
2 and 3, not to serve the app — but keep them in the paper JSON, don't discard
them at the source.

Every field must validate against
[`schema/schema.json`](../../schema/README.md), which is the authority. 30 fields
declared; `marks` and `negative_marks` are absent when they equal their defaults.

## Done when

- `build_report.json` gives the fill rate of every field, how many duplicates
  merged, and how many conflicts went to review.
- Re-running on unchanged input produces a byte-identical file.
- Step 5 passes.
- Nothing was dropped silently — every question that went in is either in the
  output, merged into a row whose `seen_in` names its paper, or in the review file.

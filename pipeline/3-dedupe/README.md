# 3 — dedupe

Keep one copy of each question, then write the export.

**Reads** `data/papers/` · **Writes** `data/questions.jsonl.gz`

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

## While merging

**Write the provenance to `dedupe_report.json`. Step 4 depends on it.**

```json
{ "d758775a0377eafe": [
    { "paper_id": "ibps_clerk_2019_mains_…", "q_num": 95 },
    { "paper_id": "ibps_clerk_2021_prelims_…", "q_num": 42 } ] }
```

This is the reason dedupe runs before answers rather than after. Answer keys are
found by `(paper_id, q_num)`, so a merged question needs every place it appeared:
if the 2019 paper has no answer key but the 2021 one does, step 4 finds it
through this map. Drop the provenance and you throw away a second and third
chance at an answer.

It's also the high-yield signal — a question that appeared in six exams is worth
ranking practice sets by, and nowhere else records that.

**Answer conflicts move to step 4.** When two source papers give different
answers for the same merged question, step 4 is where that surfaces — it has the
provenance map and can see both keys at once. There were 25 such cases in a
3,596-question sample, so this will happen.

The surviving record takes the copy with the most filled fields, unions the
`image_refs`, and keeps the earliest `year`. It can't prefer "the copy with an
answer" any more — no answers exist yet at this point — which is fine, because
step 4 looks the answer up across every paper in the provenance map regardless of
which copy survived.

## Then the export

Flatten to one line per question, per
[`schema/schema.json`](../../schema/README.md):

- Copy the paper's identity onto every question — `bank`, `role`, `exam_type`,
  `year`, `memory_based` — so the app filters without a join.
- Compute `direction_hash` from the passage text; inline `direction_text` and
  `direction_image_refs`.
- Omit nulls. Omit `marks` / `negative_marks` when they equal the default
  (`1`, `-0.25`).
- Truncate `content_hash` to 16 chars.
- Gzip. Repeated passages compress to almost nothing — 23 MB becomes about 3 MB.

## Output

[`output.json`](output.json) — step 2's 21 fields plus three derived ones:

```
content_hash   direction_hash   is_active
```

24 of 28. `answer` and `explanation` come in step 4; `marks` and
`negative_marks` stay absent while they equal their defaults (`1`, `-0.25`).

`content_hash` is the dedup key, truncated to 16 chars. `direction_hash` is
computed from the passage text and is what groups a passage set — never group by
`direction_id`, which is paper-scoped.

Every field must validate against
[`schema/schema.json`](../../schema/README.md), which is the authority.

## Done when

- `dedupe_report.json` maps every surviving `content_hash` to all the
  `(paper_id, q_num)` pairs it absorbed. Step 4 can't work without it.
- Re-running on unchanged input produces byte-identical output.
- Nothing was dropped silently — every question that went in is either in the
  output or named in the provenance of one that is.
- The duplicate rate is reported. It was **7.6%** on the last extraction —
  1,601 copies of 21,044 — so a wildly different number means step 1 changed.

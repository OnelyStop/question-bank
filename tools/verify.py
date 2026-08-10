#!/usr/bin/env python3
"""
Check that what was published is actually publishable.

The cleaner is a pile of regexes, and a regex that stops matching is silent. So
the shipped output is re-read here and scanned for the very things cleaning was
supposed to remove — a brand name, a URL, a source book's title, a character
from the broken font mapping. Anything found is a leak, not a warning.

Also reconciles the counts: clean + flagged must equal the slice that went in,
or a question was lost between the two.

Usage: python3 tools/verify.py
"""

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "India" / "banking"

LEAKS = {
    "coaching brand": re.compile(
        r"adda\s?247|bankersadda|sscadda|careerpower|ibps\s?guide|oliveboard"
        r"|testbook|gradeup|smartkeeda|practicemock", re.I),
    "url or email": re.compile(
        r"www\.|https?://|\b[a-z0-9-]+\.(?:com|in|org|net)\b|\S+@\S+\.\w+", re.I),
    # \b matters: "Facebook" contains "ebook", and one book's questions are
    # genuinely about Facebook user counts.
    "source book title": re.compile(
        r"200 Questions of Quant|Complete Pack of Banking|Ace (?:English|reasoning|quant)"
        r"|3rd edition|Maha Pack|\bCRACKER\b|\beBooks?\b", re.I),
    # Likewise the platform names alone are legitimate question content; only
    # the call-to-action phrasing is a leak.
    "promo": re.compile(
        r"mail us at|whatsapp\s*@?\s*\d|telegram\s+channel|click\s+here"
        r"|subscribe\s+(?:our|to)|download\s+\w*\s*app\b|follow\s+(?:us|\d*\s*\w+\s+sir)"
        r"|mock test series|facebook\s+page", re.I),
    "broken font mapping": re.compile(r"[ঀ-෿ሀ-፿]"),
    "hindi": re.compile(r"[ऀ-ॿ]"),
    "private use area": re.compile(r"[-]"),
    "section label": re.compile(r"\b(?:Answers|Solutions)\s*:", re.I),
}


def main():
    ready = json.loads((BANK / "raw" / "ready.json").read_text())
    problems = Counter()
    examples = {}
    total_clean = total_flagged = 0

    for n in range(1, 11):
        cj = BANK / "cleaned" / f"{n}.json"
        fc = BANK / "flagged" / f"{n}.csv"
        if not cj.exists():
            print(f"set {n}: NOT BUILT")
            continue
        clean = json.loads(cj.read_text())
        flagged = list(csv.DictReader(fc.open()))
        expected = len(ready[(n - 1) * 500: n * 500])
        total_clean += len(clean)
        total_flagged += len(flagged)

        note = "" if len(clean) + len(flagged) == expected else \
            f"  <-- LOST {expected - len(clean) - len(flagged)}"
        print(f"set {n:2d}: {len(clean):4d} clean + {len(flagged):4d} flagged "
              f"= {len(clean) + len(flagged):4d} of {expected}{note}")

        for q in clean:
            fields = [q["stem"], q["context"]] + [o["text"] for o in q["options"]]
            for label, pat in LEAKS.items():
                for f in fields:
                    m = pat.search(f)
                    if m:
                        problems[label] += 1
                        examples.setdefault(label, f"set {n}: ...{f[max(0, m.start()-60):m.start()+60]}...")
            if len(q["options"]) != 5 or {o["key"] for o in q["options"]} != set("abcde"):
                problems["malformed options"] += 1
            if q["correct_option"] not in "abcde":
                problems["bad answer key"] += 1
            for c in q["charts"]:
                if not (BANK / c).exists():
                    problems["missing chart file"] += 1

    print(f"\ntotal: {total_clean} clean, {total_flagged} flagged, "
          f"{total_clean + total_flagged} of {len(ready)}")

    if problems:
        print("\nLEAKS IN PUBLISHED OUTPUT:")
        for label, count in problems.most_common():
            print(f"  {count:5d}  {label}")
            if label in examples:
                print(f"         {examples[label]}")
        return 1
    print("\nno leaks: nothing in the published sets matches what cleaning removes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

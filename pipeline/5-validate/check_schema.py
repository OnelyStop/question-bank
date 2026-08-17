#!/usr/bin/env python3
"""Validate uniform question JSONL against allowed patterns + required fields."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA_FILE = ROOT.parent.parent / "schema" / "schema.json"

REQUIRED = [
    "q_id",
    "question_pattern",
    "stem",
    "options",
    "option_count",
    "has_shared_directions",
    "is_bilingual",
    "has_image",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path, nargs="?", default=ROOT.parent.parent / "data" / "questions.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    allowed = set(json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["properties"]["question_pattern"]["enum"])
    errors = 0
    rows = 0
    with args.jsonl.open(encoding="utf-8") as f:
        for line in f:
            if args.limit and rows >= args.limit:
                break
            rows += 1
            row = json.loads(line)
            for key in REQUIRED:
                if key not in row:
                    print(f"missing {key} in {row.get('q_id')}")
                    errors += 1
            pattern = row.get("question_pattern")
            if pattern not in allowed:
                print(f"bad pattern {pattern!r} in {row.get('q_id')}")
                errors += 1
            if not isinstance(row.get("options"), dict):
                print(f"options not object in {row.get('q_id')}")
                errors += 1

    print(f"validated_rows={rows} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

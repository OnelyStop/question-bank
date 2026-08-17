#!/usr/bin/env python3
"""Check the per-step output.json examples against schema/schema.json.

These examples are the contract between pipeline steps, so they are worth
enforcing: a field renamed in the schema and not in the examples sends whoever
owns the next step down the wrong path.

    python3 pipeline/5-validate/check_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "schema" / "schema.json"
STEPS = ["1-extract", "2-classify", "3-answer", "4-dedupe"]

JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def type_ok(value: object, declared: object) -> bool:
    names = [declared] if isinstance(declared, str) else list(declared)
    # bool is a subclass of int, so an integer field must not accept True
    if isinstance(value, bool) and "boolean" not in names:
        return False
    return any(isinstance(value, JSON_TYPES[n]) for n in names if n in JSON_TYPES)


def main() -> int:
    failures: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]

    previous: set[str] = set()
    previous_step = ""
    for step in STEPS:
        path = REPO / "pipeline" / step / "output.json"
        if not path.exists():
            failures.append(f"{step}: output.json is missing")
            continue

        try:
            example = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{step}: output.json is not valid JSON — {exc}")
            continue

        for key, value in example.items():
            if key not in props:
                failures.append(f"{step}: '{key}' is not a field in schema.json")
                continue
            if not type_ok(value, props[key].get("type")):
                failures.append(
                    f"{step}: '{key}' is {type(value).__name__}, "
                    f"schema says {props[key].get('type')}"
                )

        # each step must be a superset of the one before it — a step that drops a
        # field silently breaks everything downstream of it
        lost = previous - set(example)
        if lost:
            failures.append(f"{step}: drops {sorted(lost)} that {previous_step} had")

        enum = props.get("question_pattern", {}).get("enum", [])
        pattern = example.get("question_pattern")
        if pattern is not None and pattern not in enum:
            failures.append(f"{step}: question_pattern '{pattern}' is not in the enum")

        print(f"  {step:<12} {len(example):>2}/{len(props)} fields")
        previous, previous_step = set(example), step

    # the last step should account for every schema field, filled or deliberately absent
    unused = sorted(set(props) - previous)
    expected_absent = {"marks", "negative_marks"}
    if set(unused) - expected_absent:
        failures.append(
            f"4-dedupe: schema fields never shown in any example: "
            f"{sorted(set(unused) - expected_absent)}"
        )

    if failures:
        print("\nFAILED", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print(f"\n  OK — {len(STEPS)} examples match schema.json ({len(props)} fields)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

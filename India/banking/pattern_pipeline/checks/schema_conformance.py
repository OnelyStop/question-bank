"""Schema / DB contract conformance.

Everything here is `fatal`: it breaks either `schema/uniform_question.schema.json`
(`additionalProperties: false`) or the `create table` in
`schema/supabase_questions.sql`. The load fails, so these must be zero.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .base import CheckSkill, Defect, options_of

_SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "uniform_question.schema.json"


def _load_schema() -> tuple[set[str], set[str], set[str]]:
    """(required, allowed_properties, allowed_patterns) straight from the schema file."""
    doc = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    props = doc.get("properties", {})
    patterns = set(props.get("question_pattern", {}).get("enum", []))
    return set(doc.get("required", [])), set(props), patterns


REQUIRED, ALLOWED_KEYS, ALLOWED_PATTERNS = _load_schema()
ANSWER_KEYS = {"a", "b", "c", "d", "e"}


class SchemaConformanceCheck(CheckSkill):
    """Row violates the JSON schema or the Supabase column contract."""

    id = "schema_conformance"
    name = "Schema conformance"
    tier = "fatal"
    reason = "schema_violation"

    def check(self, row: dict[str, Any]) -> Iterable[Defect]:
        for key in sorted(REQUIRED - set(row)):
            yield self.defect(f"missing required key {key!r}")
        for key in sorted(set(row) - ALLOWED_KEYS):
            yield self.defect(f"key {key!r} not in schema (additionalProperties is false)")

        if not isinstance(row.get("q_id"), str) or not row.get("q_id"):
            yield self.defect(f"q_id must be a non-empty string, got {row.get('q_id')!r}")
        if row.get("question_pattern") not in ALLOWED_PATTERNS:
            yield self.defect(f"question_pattern {row.get('question_pattern')!r} not in enum")
        if not isinstance(row.get("stem"), str):
            yield self.defect("stem must be a string")

        if not isinstance(row.get("options"), dict):
            yield self.defect("options must be an object")
        else:
            for key, val in sorted(options_of(row).items()):
                if key not in ANSWER_KEYS:
                    yield self.defect(f"option key {key!r} outside a-e")
                if not isinstance(val, str):
                    yield self.defect(f"option {key!r} is {type(val).__name__}, not string")

        count = row.get("option_count")
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 5:
            yield self.defect(f"option_count must be an integer 0-5, got {count!r}")

        answer = row.get("answer")
        if answer is not None and answer not in ANSWER_KEYS:
            # The SQL has a matching check constraint, so this aborts the insert.
            yield self.defect(f"answer {answer!r} outside a-e (papers using 1-5 need mapping)")

        year = row.get("year")
        if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
            yield self.defect(f"year must be integer or null, got {year!r}")

        for flag in ("has_shared_directions", "is_bilingual", "has_image"):
            if flag in row and not isinstance(row[flag], bool):
                yield self.defect(f"{flag} must be boolean, got {row[flag]!r}")

        if "secondary_patterns" in row:
            sec = row["secondary_patterns"]
            if not isinstance(sec, list) or any(not isinstance(s, str) for s in sec):
                yield self.defect("secondary_patterns must be a list of strings")
        if "image_refs" in row and not isinstance(row["image_refs"], list):
            yield self.defect("image_refs must be an array")

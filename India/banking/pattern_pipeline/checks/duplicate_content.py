from __future__ import annotations

from typing import Any, Iterable

from .base import CorpusCheckSkill, Defect, norm, options_of


class DuplicateQIdCheck(CorpusCheckSkill):
    """The same q_id twice. `banking_questions.q_id` is `unique` — the load aborts."""

    id = "duplicate_q_id"
    name = "Duplicate q_id"
    tier = "fatal"
    reason = "duplicate_q_id"

    def check_corpus(self, rows: list[dict[str, Any]]) -> Iterable[tuple[str, Defect]]:
        seen: set[str] = set()
        for row in rows:
            qid = row.get("q_id")
            if qid in seen:
                yield qid, self.defect("q_id already used by an earlier row")
            seen.add(qid)


class DuplicateContentCheck(CorpusCheckSkill):
    """Same stem and same options under a different q_id.

    Dedupe in `run_pipeline.py` is keyed on `q_id` alone, so the same question
    recalled into two papers survives twice.
    """

    id = "duplicate_content"
    name = "Duplicate content"
    tier = "suspect"
    reason = "duplicate_content"

    def check_corpus(self, rows: list[dict[str, Any]]) -> Iterable[tuple[str, Defect]]:
        first_seen: dict[tuple, str] = {}
        for row in rows:
            stem = norm(row.get("stem") or "")
            if not stem:
                continue  # stem_too_short owns empty rows; they'd all collide here
            key = (stem, tuple(sorted((k, norm(v)) for k, v in options_of(row).items())))
            original = first_seen.get(key)
            if original is None:
                first_seen[key] = row.get("q_id")
            else:
                yield row.get("q_id"), self.defect(f"identical to {original}")

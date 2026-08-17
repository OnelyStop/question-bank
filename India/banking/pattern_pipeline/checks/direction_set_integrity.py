from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .base import CorpusCheckSkill, Defect, direction_of

# A real IBPS/SBI set runs 3-8 questions. Much more than that and one direction
# has swallowed the questions belonging to the next one.
MAX_SET = 12


def _paper_of(row: dict[str, Any]) -> str:
    return (row.get("q_id") or "").split("::")[0]


class DirectionSetIntegrityCheck(CorpusCheckSkill):
    """Direction groups that do not hold together.

    `direction_id` is only unique within a paper (`feature_tables/README.md`:
    "Always join directions as `paper_id + direction_id`; ids repeat across
    papers"), so everything here is scoped per paper.
    """

    id = "direction_set_integrity"
    name = "Direction set integrity"
    tier = "suspect"
    reason = "direction_set_broken"

    def check_corpus(self, rows: list[dict[str, Any]]) -> Iterable[tuple[str, Defect]]:
        members: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            did = row.get("direction_id")
            if did:
                members[(_paper_of(row), did)].append(row)

        for (paper, did), group in members.items():
            texts = {direction_of(r).strip() for r in group}
            if len(texts) > 1:
                # Same set, two different bodies: one of them is wrong.
                for row in group:
                    yield row.get("q_id"), Defect(
                        reason="direction_id_conflict", tier="blocking",
                        detail=f"{did} in {paper} maps to {len(texts)} different bodies")
            if len(group) > MAX_SET:
                for row in group:
                    yield row.get("q_id"), self.defect(
                        f"{did} covers {len(group)} questions (max expected {MAX_SET})")

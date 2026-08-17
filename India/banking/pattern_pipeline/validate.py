#!/usr/bin/env python3
"""Validate uniform question JSONL.

Checks that a row is actually *serveable*, not just that the expected keys exist.
Every rule is a check skill under `checks/`, plus each pattern skill's own
`validate()` -- see `quality.py`.

  python validate.py out/questions.jsonl
  python validate.py out/questions.jsonl --tier blocking   # CI gate
  python validate.py out/questions.jsonl --defects out/defects.jsonl
  python validate.py --selftest

Tiers, worst first:
  fatal    violates the JSON schema / Supabase DDL -- the load breaks
  blocking loads fine, but cannot be shown to a candidate
  suspect  probably an extraction artifact; needs a human
  info     known coverage gaps; counted, never fatal
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from checks import TIERS  # noqa: E402
from quality import audit, worst_tier  # noqa: E402

# Fields that are simply not populated yet. Reported so the gap stays visible,
# never as a defect: `papers/SCHEMA.md` marks topic "Reserved", and answers only
# exist for papers that shipped a solution PDF.
COVERAGE_FIELDS = ["answer", "explanation", "topic", "direction_id", "shift", "bank", "year"]


def load_rows(path: Path, limit: int = 0) -> tuple[list[dict], int]:
    rows: list[dict] = []
    bad = 0
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            if limit and len(rows) >= limit:
                break
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                bad += 1
                print(f"fatal  unparseable_line  line={lineno}  {exc}")
    return rows, bad


def report(rows: list[dict], defects_by_qid: dict[str, list]) -> Counter:
    counts: Counter = Counter()
    rows_by_tier: dict[str, set] = defaultdict(set)
    for qid, defects in defects_by_qid.items():
        for defect in defects:
            counts[(defect.tier, defect.reason)] += 1
            rows_by_tier[defect.tier].add(qid)

    total = len(rows) or 1
    for tier in TIERS:
        items = sorted(((c, reason) for (t, reason), c in counts.items() if t == tier),
                       reverse=True)
        if not items:
            continue
        hit = len(rows_by_tier[tier])
        print(f"\n[{tier}] {sum(c for c, _ in items)} defects across "
              f"{hit} rows ({100 * hit / total:.1f}%)")
        for count, reason in items:
            print(f"  {count:7d}  {reason}")
    return counts


def coverage(rows: list[dict]) -> None:
    total = len(rows) or 1
    lines = []
    for field in COVERAGE_FIELDS:
        missing = sum(1 for r in rows if r.get(field) in (None, "", []))
        if missing:
            lines.append(f"  {missing:7d}  {field}_missing  ({100 * missing / total:.0f}%)")
    if lines:
        print("\n[coverage] not populated yet -- never fails the build")
        print("\n".join(lines))


def selftest() -> int:
    good = {
        "q_id": "p::q001", "question_pattern": "standalone_mcq", "stem": "What is 2 + 2?",
        "options": {"a": "3", "b": "4", "c": "5", "d": "6", "e": "None of these"},
        "option_count": 5, "has_shared_directions": False, "is_bilingual": False,
        "has_image": False, "image_refs": [], "answer": "b", "language": "english",
    }
    from quality import corpus_defects, row_defects

    assert not row_defects(good), row_defects(good)

    def reasons(**over):
        return {d.reason for d in row_defects(dict(good, **over))}

    # blocking
    assert "option_partial" in reasons(options={"a": "1", "b": "2"}, option_count=2)
    assert "option_partial" in reasons(
        options={"a": "1", "b": "2", "d": "3", "e": "4"}, option_count=4, answer=None)
    assert "option_duplicate" in reasons(
        options={"a": "3", "b": "3", "c": "5", "d": "6", "e": "7"})
    assert "option_empty" in reasons(
        options={"a": " ", "b": "2", "c": "3", "d": "4", "e": "5"})
    assert "stem_too_short" in reasons(stem="   ")
    assert "stem_too_short" in reasons(stem="Question 131.")
    assert "option_bleed" in reasons(stem="Find x. (a) 1 (b) 2 (c) 3 (d) 4")
    assert "chart_missing" in reasons(question_pattern="visual_chart_graph_di")
    assert "context_missing" in reasons(question_pattern="table_di_set")
    assert "text_garbled" in reasons(stem="Village  A B C total")
    assert "language_hindi" in reasons(stem="कितने लोग?")
    # fatal
    assert "schema_violation" in reasons(answer="A")
    assert "schema_violation" in reasons(option_count=9)
    assert "schema_violation" in reasons(surprise=1)
    # suspect
    assert "fraction_flattened" in reasons(
        options={"a": "25 7 %", "b": "1", "c": "2", "d": "3", "e": "4"})
    assert "stem_truncated" in reasons(stem="The value of the first term is,")
    assert "brand_residue" in reasons(stem="What is 2 + 2? Visit adda247.com")
    # bilingual keeps its English half -> serveable, but metadata is flagged
    bi = reasons(stem="How many people? कितने लोग हैं?")
    assert "language_metadata_wrong" in bi and "language_hindi" not in bi, bi
    # corpus
    dup = {d.reason for _, d in [(q, d) for q, ds in
           corpus_defects([dict(good), dict(good, q_id="p::q002")]).items() for d in ds]}
    assert "duplicate_content" in dup, dup
    same = {d.reason for _, ds in corpus_defects([dict(good), dict(good)]).items() for d in ds}
    assert "duplicate_q_id" in same, same

    print("selftest ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path, nargs="?", default=ROOT / "out" / "questions.jsonl")
    parser.add_argument("--tier", choices=TIERS, default="blocking",
                        help="exit non-zero if any defect at this tier or worse is found")
    parser.add_argument("--defects", type=Path, help="write one JSON object per defect here")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--selftest", action="store_true", help="run built-in assertions and exit")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    rows, bad_json = load_rows(args.jsonl, args.limit)
    defects_by_qid = audit(rows)

    print(f"rows={len(rows)}  unparseable_lines={bad_json}")
    counts = report(rows, defects_by_qid)
    coverage(rows)

    if args.defects:
        args.defects.parent.mkdir(parents=True, exist_ok=True)
        with args.defects.open("w", encoding="utf-8") as handle:
            for qid, defects in sorted(defects_by_qid.items(), key=lambda kv: kv[0] or ""):
                for defect in defects:
                    handle.write(json.dumps({
                        "q_id": qid, "tier": defect.tier,
                        "reason": defect.reason, "detail": defect.detail,
                    }, ensure_ascii=False) + "\n")
        print(f"\nwrote {args.defects}")

    gate = TIERS.index(args.tier)
    failing = sum(c for (tier, _), c in counts.items() if TIERS.index(tier) <= gate) + bad_json
    clean = sum(1 for r in rows if not defects_by_qid.get(r.get("q_id")))
    serveable = sum(
        1 for r in rows
        if TIERS.index(worst_tier(defects_by_qid.get(r.get("q_id")) or []) or "info") > gate
    )
    print(f"\nclean_rows={clean}  serveable_at_{args.tier}={serveable}  of {len(rows)}")
    print(f"exit_gate={args.tier}  failing_defects={failing}")
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())

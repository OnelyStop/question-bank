"""
Validate attached answers and quarantine invalid ones.

Usage:
  python validate_answers.py
  python validate_answers.py --audit-size 80 --no-quarantine
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from pdf_to_questions import DEFAULT_OUT, rebuild_index

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("validate_answers")

SKIP_JSON = {
    "parse_report.json",
    "answer_attach_report.json",
    "answer_validation_report.json",
    "question_bank.schema.json",
    "section_label_report.json",
    "topic_label_report.json",
}


def iter_paper_jsons(out_root: Path) -> list[Path]:
    return sorted(
        p
        for p in out_root.rglob("*.json")
        if p.name not in SKIP_JSON and not p.name.endswith(".meta.json")
    )


def load_paper(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if "questions" not in data or "paper_id" not in data:
        return None
    return data


def option_count(q: dict[str, Any]) -> int:
    metrics = q.get("metrics") or {}
    if "option_count" in metrics:
        return int(metrics["option_count"] or 0)
    return len(q.get("options") or {})


def validate_and_quarantine(
    out_root: Path,
    *,
    quarantine: bool,
    audit_size: int,
    seed: int,
) -> dict[str, Any]:
    answer_not_in_options: list[dict[str, Any]] = []
    weak_options: list[dict[str, Any]] = []
    short_stems: list[dict[str, Any]] = []
    empty_stems: list[dict[str, Any]] = []
    letter_dist: Counter[str] = Counter()

    total_q = 0
    with_answer = 0
    quarantined = 0
    papers_full = papers_partial = papers_none = 0

    audit_pool: list[dict[str, Any]] = []

    attach_conflicts: list[dict[str, Any]] = []
    attach_path = out_root / "answer_attach_report.json"
    if attach_path.is_file():
        try:
            ar = json.loads(attach_path.read_text(encoding="utf-8"))
            attach_conflicts = list((ar.get("solutions_pdfs") or {}).get("conflicts") or [])
            attach_conflicts += list((ar.get("same_pdf") or {}).get("conflicts") or [])
        except json.JSONDecodeError:
            pass

    no_answers_same_pdf: list[dict[str, Any]] = []
    if attach_path.is_file():
        try:
            ar = json.loads(attach_path.read_text(encoding="utf-8"))
            no_answers_same_pdf = list((ar.get("same_pdf") or {}).get("no_answers_found") or [])
        except json.JSONDecodeError:
            pass

    # Papers that had no same-PDF answers but may have answers from sol PDFs
    no_same_pdf_but_filled: list[dict[str, Any]] = []
    no_same_pdf_still_empty: list[dict[str, Any]] = []

    papers_by_id: dict[str, dict[str, Any]] = {}

    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        papers_by_id[paper["paper_id"]] = paper
        qs = paper.get("questions") or []
        filled_before = sum(1 for q in qs if q.get("answer"))
        dirty = False

        for q in qs:
            total_q += 1
            stem = (q.get("stem") or "").strip()
            oc = option_count(q)
            opts = q.get("options") or {}
            ans = q.get("answer")

            if not stem:
                empty_stems.append(
                    {
                        "q_id": q.get("q_id"),
                        "paper_id": paper["paper_id"],
                        "q_num": q.get("q_num"),
                    }
                )
            stem_len = (q.get("metrics") or {}).get("stem_char_len")
            if stem_len is None:
                stem_len = len(stem)
            if stem and stem_len < 15:
                short_stems.append(
                    {
                        "q_id": q.get("q_id"),
                        "paper_id": paper["paper_id"],
                        "q_num": q.get("q_num"),
                        "stem": stem[:80],
                        "stem_char_len": stem_len,
                    }
                )

            if oc < 4:
                weak_options.append(
                    {
                        "q_id": q.get("q_id"),
                        "paper_id": paper["paper_id"],
                        "q_num": q.get("q_num"),
                        "option_count": oc,
                        "has_answer": bool(ans),
                    }
                )

            if ans:
                letter_dist[str(ans)] += 1
                if ans not in opts:
                    answer_not_in_options.append(
                        {
                            "q_id": q.get("q_id"),
                            "paper_id": paper["paper_id"],
                            "q_num": q.get("q_num"),
                            "answer": ans,
                            "option_keys": sorted(opts.keys()),
                            "pdf_path": (paper.get("source") or {}).get("pdf_path"),
                        }
                    )
                    if quarantine:
                        q["answer"] = None
                        q["_quarantined_answer"] = ans
                        q["_quarantine_reason"] = "answer_not_in_options"
                        quarantined += 1
                        dirty = True
                else:
                    with_answer += 1
                    audit_pool.append(
                        {
                            "paper_id": paper["paper_id"],
                            "q_id": q.get("q_id"),
                            "q_num": q.get("q_num"),
                            "bank": paper.get("bank"),
                            "role": paper.get("role"),
                            "year": paper.get("year"),
                            "exam_type": paper.get("exam_type"),
                            "section": q.get("section"),
                            "stem": stem[:200],
                            "answer": ans,
                            "options": json.dumps(opts, ensure_ascii=False),
                            "pdf_path": (paper.get("source") or {}).get("pdf_path"),
                            "human_ok": "",  # fill: y/n
                        }
                    )

        if dirty:
            path.write_text(json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")

        filled_after = sum(1 for q in qs if q.get("answer"))
        if not qs:
            continue
        if filled_after == len(qs):
            papers_full += 1
        elif filled_after:
            papers_partial += 1
        else:
            papers_none += 1

        _ = filled_before  # silence lint

    for entry in no_answers_same_pdf:
        pid = entry.get("paper_id")
        paper = papers_by_id.get(pid or "")
        if not paper:
            no_same_pdf_still_empty.append({**entry, "note": "paper_missing"})
            continue
        n_ans = sum(1 for q in paper.get("questions") or [] if q.get("answer"))
        row = {**entry, "answers_after_sol_merge": n_ans}
        if n_ans:
            no_same_pdf_but_filled.append(row)
        else:
            no_same_pdf_still_empty.append(row)

    rng = random.Random(seed)
    audit_sample = audit_pool[:]
    rng.shuffle(audit_sample)
    audit_sample = audit_sample[: max(0, audit_size)]

    audit_csv = out_root / "answer_audit_sample.csv"
    if audit_sample:
        with audit_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(audit_sample[0].keys()))
            writer.writeheader()
            writer.writerows(audit_sample)

    # Recount after quarantine
    with_answer_final = 0
    total_final = 0
    still_bad = 0
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        for q in paper.get("questions") or []:
            total_final += 1
            ans = q.get("answer")
            if not ans:
                continue
            with_answer_final += 1
            if ans not in (q.get("options") or {}):
                still_bad += 1

    report = {
        "summary": {
            "questions": total_final,
            "with_answer": with_answer_final,
            "answer_coverage_pct": round(100.0 * with_answer_final / total_final, 2) if total_final else 0,
            "quarantined_answers": quarantined,
            "answer_not_in_options_remaining": still_bad,
            "papers_full": papers_full,
            "papers_partial": papers_partial,
            "papers_none": papers_none,
            "letter_distribution": dict(letter_dist),
            "weak_options_count": len(weak_options),
            "short_stems_count": len(short_stems),
            "empty_stems_count": len(empty_stems),
            "attach_conflicts_count": len(attach_conflicts),
            "no_same_pdf_but_filled_count": len(no_same_pdf_but_filled),
            "no_same_pdf_still_empty_count": len(no_same_pdf_still_empty),
            "audit_sample_size": len(audit_sample),
            "audit_csv": str(audit_csv.name) if audit_sample else None,
        },
        "answer_not_in_options": answer_not_in_options[:200],
        "answer_not_in_options_total": len(answer_not_in_options),
        "weak_options": weak_options[:100],
        "short_stems": short_stems[:100],
        "empty_stems": empty_stems[:50],
        "attach_conflicts": attach_conflicts[:100],
        "no_same_pdf_but_filled": no_same_pdf_but_filled[:50],
        "no_same_pdf_still_empty": no_same_pdf_still_empty[:50],
        "audit_instructions": (
            "Open answer_audit_sample.csv. For each row, open pdf_path and verify "
            "the answer letter for q_num. Set human_ok to y or n. Target: >=95% y."
        ),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Validate and quarantine bad answers")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--audit-size", type=int, default=80)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-quarantine", action="store_true", help="Report only; do not null bad answers")
    args = p.parse_args(argv)

    out_root = Path(args.out)
    report = validate_and_quarantine(
        out_root,
        quarantine=not args.no_quarantine,
        audit_size=args.audit_size,
        seed=args.seed,
    )
    if not args.no_quarantine and report["summary"]["quarantined_answers"]:
        n = rebuild_index(out_root)
        report["summary"]["index_rows"] = n
        log.info("Rebuilt index.jsonl (%s rows)", n)

    report_path = out_root / "answer_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", report_path)
    log.info("Summary: %s", json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

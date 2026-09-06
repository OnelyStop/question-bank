"""Recover missing explanations from a question paper's own PDF solution blocks.

This is deliberately narrower than answer attachment: it only writes an
explanation when the paper already has an answer and that answer agrees with the
answer printed beside the source PDF's ``Sol.`` block.  It never generates or
guesses an explanation.

The command is dry-run by default.  Pass ``--apply`` only after reviewing its
JSON report.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "lib"))
from corpus import DEFAULT_CORPUS, DEFAULT_OUT, iter_paper_jsons, load_paper  # noqa: E402
from pdf import extract_pages  # noqa: E402
from corpus import build_full_text  # noqa: E402


def load_attach_helpers() -> Any:
    """Load the established PDF resolver/parser without duplicating its rules."""
    spec = importlib.util.spec_from_file_location("attach_answers", ROOT / "attach_answers.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load attach_answers.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_useful_explanation(value: object) -> bool:
    """Reject empty parser artefacts while retaining concise publisher solutions."""
    if not isinstance(value, str):
        return False
    return len(value.strip()) >= 12


def recover(
    out_root: Path,
    corpus: Path,
    *,
    apply: bool,
    limit: int,
    skip: int,
) -> dict[str, Any]:
    attach = load_attach_helpers()
    report: dict[str, Any] = {
        "dry_run": not apply,
        "papers_seen": 0,
        "papers_with_source_pdf": 0,
        "papers_touched": 0,
        "questions_total": 0,
        "with_answer": 0,
        "with_explanation_before": 0,
        "eligible_missing_explanation": 0,
        "recovered": 0,
        "answer_mismatches": 0,
        "missing_pdf": [],
        "no_solution_map": [],
        "details": [],
    }
    for source_index, paper_path in enumerate(iter_paper_jsons(out_root)):
        if source_index < skip:
            continue
        if limit and report["papers_seen"] >= limit:
            break
        paper = load_paper(paper_path)
        if not paper:
            continue
        report["papers_seen"] += 1
        questions = paper.get("questions") or []
        report["questions_total"] += len(questions)
        report["with_answer"] += sum(bool(q.get("answer")) for q in questions)
        report["with_explanation_before"] += sum(is_useful_explanation(q.get("explanation")) for q in questions)

        eligible = [q for q in questions if q.get("answer") and not is_useful_explanation(q.get("explanation"))]
        report["eligible_missing_explanation"] += len(eligible)
        if not eligible:
            continue
        pdf_path = attach.resolve_pdf_path(paper, corpus)
        if not pdf_path:
            report["missing_pdf"].append(str(paper.get("paper_id") or paper_path))
            continue
        report["papers_with_source_pdf"] += 1
        try:
            pages = extract_pages(pdf_path)
            text, _spans = build_full_text(pages)
            answer_map = attach.extract_answer_map(text)
        except Exception as exc:  # noqa: BLE001
            report["missing_pdf"].append(f"{paper.get('paper_id')}: {exc}")
            continue
        if not answer_map:
            report["no_solution_map"].append(str(paper.get("paper_id") or paper_path))
            continue

        recovered_for_paper = 0
        mismatches_for_paper = 0
        for question in eligible:
            try:
                q_num = int(question.get("q_num"))
            except (TypeError, ValueError):
                continue
            source = answer_map.get(q_num)
            if not source or not is_useful_explanation(source.get("explanation")):
                continue
            # A question number alone is insufficient evidence.  The existing
            # answer must exactly match the answer printed with this solution.
            if str(question.get("answer")).lower() != str(source.get("answer")).lower():
                mismatches_for_paper += 1
                continue
            recovered_for_paper += 1
            if apply:
                question["explanation"] = str(source["explanation"]).strip()
                question["explanation_source"] = "source_pdf_solution"

        report["answer_mismatches"] += mismatches_for_paper
        report["recovered"] += recovered_for_paper
        if recovered_for_paper:
            report["details"].append(
                {
                    "paper_id": paper.get("paper_id"),
                    "paper_path": str(paper_path.relative_to(out_root)).replace("\\", "/"),
                    "source_pdf": str(pdf_path.relative_to(corpus)).replace("\\", "/"),
                    "recovered": recovered_for_paper,
                    "answer_mismatches": mismatches_for_paper,
                }
            )
            if apply:
                paper_path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                report["papers_touched"] += 1

    before = report["with_explanation_before"]
    total = report["questions_total"]
    after = before + report["recovered"]
    report["with_explanation_after"] = after
    report["coverage_before_pct"] = round((100 * before / total) if total else 0, 2)
    report["coverage_after_pct"] = round((100 * after / total) if total else 0, 2)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--report", type=Path, default=DEFAULT_OUT / "pdf_explanation_recovery_report.json")
    parser.add_argument("--limit", type=int, default=0, help="Maximum papers to inspect (0 = all).")
    parser.add_argument("--skip", type=int, default=0, help="Number of paper JSON files to skip before inspection.")
    parser.add_argument("--apply", action="store_true", help="Write recovered explanations; otherwise only report.")
    args = parser.parse_args(argv)
    report = recover(args.out, args.corpus, apply=args.apply, limit=args.limit, skip=args.skip)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dry_run", "recovered", "coverage_before_pct", "coverage_after_pct", "papers_touched")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

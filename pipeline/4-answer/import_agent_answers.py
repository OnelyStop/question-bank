"""Validate and optionally apply subscription-agent answers.

Responses must be JSONL records containing exactly a known ``q_id`` and an
``answer`` key that exists in that question's options.  ``explanation`` is
optional and is retained only when a response is accepted.  This command is a
dry run by default; pass --apply only after reviewing its report.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper, rebuild_index


def read_responses(source: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load JSONL from one file or recursively from a response directory."""
    files = [source] if source.is_file() else sorted(source.rglob("*.jsonl"))
    if not files:
        return [], [{"reason": "no_response_files", "source": str(source)}]
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for path in files:
        for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                rejected.append({"reason": "invalid_json", "file": str(path), "line": line_no})
                continue
            if not isinstance(row, dict):
                rejected.append({"reason": "not_an_object", "file": str(path), "line": line_no})
                continue
            row["_file"] = str(path)
            row["_line"] = line_no
            rows.append(row)
    return rows, rejected


def index_questions(out_root: Path) -> tuple[dict[str, tuple[Path, dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    indexed: dict[str, tuple[Path, dict[str, Any], dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        for question in paper.get("questions") or []:
            q_id = question.get("q_id")
            if not isinstance(q_id, str) or not q_id:
                errors.append({"reason": "missing_question_id", "file": str(path)})
            elif q_id in indexed:
                errors.append({"reason": "duplicate_question_id", "q_id": q_id, "file": str(path)})
            else:
                indexed[q_id] = (path, paper, question)
    return indexed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/import subscription-agent answer responses")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--responses", type=Path, required=True, help="JSONL file or directory of JSONL files")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--source", default="subscription_agent_review", help="Provenance label stored on accepted entries")
    parser.add_argument("--apply", action="store_true", help="write accepted answers (default: dry run)")
    parser.add_argument(
        "--require-explanation",
        action="store_true",
        help="reject answers without a non-empty explanation (use for full review handoffs)",
    )
    args = parser.parse_args()
    report_path = args.report or (args.out / "agent_answer_import_report.json")
    rows, rejected = read_responses(args.responses)
    index, index_errors = index_questions(args.out)
    rejected.extend(index_errors)
    if not rows:
        report_path.write_text(json.dumps({"applied": False, "accepted": [], "rejected": rejected}, indent=2) + "\n", encoding="utf-8")
        print("No usable response records; nothing applied.", file=sys.stderr)
        return 1

    by_qid: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        q_id, answer = row.get("q_id"), row.get("answer")
        if not isinstance(q_id, str) or not q_id or not isinstance(answer, str) or not answer.strip():
            rejected.append({"reason": "requires_q_id_and_answer", "file": row["_file"], "line": row["_line"]})
            continue
        by_qid.setdefault(q_id, []).append(row)

    accepted: list[tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any]]] = []
    conflicts: list[dict[str, Any]] = []
    for q_id, candidates in by_qid.items():
        answers = {str(row["answer"]).strip().lower() for row in candidates}
        if len(answers) != 1:
            conflicts.append({"q_id": q_id, "answers": sorted(answers), "reason": "agent_responses_disagree"})
            continue
        entry = index.get(q_id)
        if not entry:
            rejected.append({"q_id": q_id, "reason": "unknown_q_id"})
            continue
        path, paper, question = entry
        answer = next(iter(answers))
        explanation = candidates[0].get("explanation")
        if args.require_explanation and (not isinstance(explanation, str) or not explanation.strip()):
            rejected.append({"q_id": q_id, "reason": "explanation_required"})
            continue
        options = {str(key).lower() for key in (question.get("options") or {})}
        if answer not in options:
            rejected.append({"q_id": q_id, "answer": answer, "reason": "answer_not_in_options", "valid_options": sorted(options)})
            continue
        current = question.get("answer")
        has_explanation = isinstance(explanation, str) and explanation.strip()
        if current and str(current).lower() != answer:
            conflicts.append({"q_id": q_id, "existing_answer": current, "agent_answer": answer, "reason": "conflicts_with_existing_answer"})
            continue
        if current:
            if not has_explanation:
                rejected.append({"q_id": q_id, "reason": "already_answered_same_key"})
                continue
            if isinstance(question.get("explanation"), str) and question["explanation"].strip():
                rejected.append({"q_id": q_id, "reason": "already_explained"})
                continue
        accepted.append((candidates[0], path, paper, question))

    dirty: dict[Path, dict[str, Any]] = {}
    if args.apply:
        for row, path, paper, question in accepted:
            if not question.get("answer"):
                question["answer"] = str(row["answer"]).strip().lower()
                question["answer_source"] = args.source
                question["answer_confidence"] = 0.5
            explanation = row.get("explanation")
            if isinstance(explanation, str) and explanation.strip():
                question["explanation"] = explanation.strip()
                question["explanation_source"] = args.source
            dirty[path] = paper
        for path, paper in dirty.items():
            path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if dirty:
            rebuild_index(args.out)

    summary = {
        "format": "question-bank-agent-answer-import/v1",
        "dry_run": not args.apply,
        "response_rows": len(rows),
        "accepted": len(accepted),
        "applied": len(accepted) if args.apply else 0,
        "papers_touched": len(dirty),
        "rejected": rejected,
        "conflicts": conflicts,
        "rejection_counts": dict(Counter(item["reason"] for item in rejected)),
    }
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{'Applied' if args.apply else 'Validated'} {len(accepted)} answer(s); {len(rejected)} rejected; {len(conflicts)} conflict(s). Report: {report_path}")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())

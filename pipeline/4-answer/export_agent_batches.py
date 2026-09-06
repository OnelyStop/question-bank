"""Export answer or explanation review tasks for subscription-agent handoff.

The export is deliberately data-only: an agent receives the question identity,
its options, and the relevant direction text.  It must return a JSONL response
with the matching ``q_id`` and one of that question's option keys.  No answers
are changed by this script.

Usage:
  python export_agent_batches.py --out data --export-dir data/agent_answer_batches
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper


def canonical_question(question: dict[str, Any], paper: dict[str, Any]) -> dict[str, Any]:
    """Return the only fields an answer agent needs, in a stable order."""
    options = question.get("options") or {}
    return {
        "q_id": question.get("q_id"),
        "paper_id": paper.get("paper_id"),
        "q_num": question.get("q_num"),
        "direction_text": question.get("direction_text") or "",
        "stem": question.get("stem") or "",
        "options": {str(key): value for key, value in sorted(options.items())},
    }


def fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_batch(path: Path, out_root: Path) -> str:
    """Return the owning data batch, never mixing it with another handoff."""
    try:
        relative = path.relative_to(out_root)
    except ValueError:
        return "unknown"
    return relative.parts[0] if len(relative.parts) > 1 else "unknown"


def queued_questions(out_root: Path, mode: str) -> tuple[dict[str, list[dict[str, Any]]], int]:
    rows: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    pending: dict[str, tuple[str, dict[str, Any]]] = {}
    skipped_unsafe = 0
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        for question in paper.get("questions") or []:
            answer = question.get("answer")
            explanation = question.get("explanation")
            if mode == "answers" and answer:
                continue
            if mode == "explanations" and (not answer or (isinstance(explanation, str) and explanation.strip())):
                continue
            payload = canonical_question(question, paper)
            q_id = payload["q_id"]
            if (
                not isinstance(q_id, str)
                or not q_id
                or not str(payload["stem"]).strip()
                or len(payload["options"]) < 2
            ):
                skipped_unsafe += 1
                continue
            if q_id in seen:
                duplicate_ids.add(q_id)
                continue
            seen.add(q_id)
            if mode == "explanations":
                payload["existing_answer"] = str(answer).lower()
                payload["review_instruction"] = (
                    "Verify the existing answer against the question, then provide a concise explanation "
                    "for that same answer. Return the existing answer key and an explanation."
                )
            payload["question_fingerprint"] = fingerprint(payload)
            pending[q_id] = (source_batch(path, out_root), payload)
    # A response cannot be imported safely when one q_id names more than one
    # record. Keep every such record out of the external review queue.
    skipped_unsafe += len(duplicate_ids)
    for q_id, (batch, payload) in pending.items():
        if q_id not in duplicate_ids:
            rows.setdefault(batch, []).append(payload)
    return {
        batch: sorted(batch_rows, key=lambda row: (str(row["paper_id"]), int(row["q_num"] or 0), row["q_id"]))
        for batch, batch_rows in sorted(rows.items())
    }, skipped_unsafe


def main() -> int:
    parser = argparse.ArgumentParser(description="Export answer or explanation tasks for agent review")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--mode", choices=("answers", "explanations"), default="answers")
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 200:
        parser.error("--batch-size must be between 1 and 200")
    rows_by_batch, skipped_unsafe = queued_questions(args.out, args.mode)
    total_rows = sum(len(rows) for rows in rows_by_batch.values())
    if not total_rows:
        print(f"No {args.mode} tasks found; no batches exported.", file=sys.stderr)
        return 1
    args.export_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "format": "question-bank-agent-review-batches/v1",
        "mode": args.mode,
        "response_format": {"q_id": "exact q_id from export", "answer": "one option key", "explanation": "required for explanation tasks"},
        "batch_size": args.batch_size,
        "skipped_unsafe_questions": skipped_unsafe,
        "batches": [],
    }
    for source, source_rows in rows_by_batch.items():
        for index, start in enumerate(range(0, len(source_rows), args.batch_size), start=1):
            batch_rows = source_rows[start : start + args.batch_size]
            name = f"{source}-{args.mode}-{index:03d}.jsonl"
            target = args.export_dir / name
            with target.open("w", encoding="utf-8", newline="\n") as fh:
                for row in batch_rows:
                    fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            manifest["batches"].append({"file": name, "source_batch": source, "questions": len(batch_rows)})
    (args.export_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Exported {total_rows} safe {args.mode} tasks in {len(manifest['batches'])} batch(es) "
        f"to {args.export_dir}; skipped {skipped_unsafe} that need source/data repair."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

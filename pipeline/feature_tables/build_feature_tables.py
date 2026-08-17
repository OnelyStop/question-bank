#!/usr/bin/env python3
"""
Build the six OnelyStopp feature tables from papers-deduped (+ cleaned pattern JSONL).

Content tables (populated):
  papers, directions, questions

Runtime tables (empty JSONL, schema only for now):
  attempts, attempt_answers, user_topic_stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DEFAULT_PAPERS = REPO / "corpus/papers-deduped"
DEFAULT_CLEANED = REPO / "pipeline" / "patterns" / "out" / "questions.jsonl"
DEFAULT_PATTERNS = ROOT / "exam_patterns.json"
DEFAULT_OUT = ROOT / "out"

SKIP_NAMES = {"parse_report.json", "question_bank.schema.json", "index.json"}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def slug(value: Any, fallback: str = "unknown") -> str:
    if value is None or value == "":
        return fallback
    return str(value).strip().replace(" ", "_")


def make_exam_key(bank: Any, role: Any, exam_type: Any, year: Any, shift: Any) -> str:
    shift_part = slug(shift, "unknown_shift")
    year_part = str(year) if year is not None else "noyear"
    return "|".join(
        [
            slug(bank).upper() if bank else "UNKNOWN_BANK",
            slug(role).upper() if role else "UNKNOWN_ROLE",
            slug(exam_type).upper() if exam_type else "UNKNOWN_STAGE",
            year_part,
            shift_part,
        ]
    )


def pattern_key(bank: Any, role: Any, exam_type: Any) -> str:
    return "|".join(
        [
            str(bank or "").strip().upper() or "UNKNOWN",
            str(role or "").strip().upper() or "UNKNOWN",
            str(exam_type or "").strip() or "Unknown",
        ]
    )


def lookup_pattern(patterns: dict[str, Any], bank: Any, role: Any, exam_type: Any) -> dict[str, Any]:
    table = patterns.get("patterns") or {}
    key = pattern_key(bank, role, exam_type)
    # Try exact, then RRB under IBPS if role is RRB
    if key in table:
        return {**(patterns.get("default") or {}), **table[key]}
    # Normalize Quantitative naming etc. already in keys
    # Fallback: try without case issues on exam_type
    for k, v in table.items():
        if k.upper() == key.upper():
            return {**(patterns.get("default") or {}), **v}
    return dict(patterns.get("default") or {})


def normalize_options(options: Any) -> dict[str, str]:
    if not isinstance(options, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("a", "b", "c", "d", "e", "A", "B", "C", "D", "E"):
        low = key.lower()
        if low in out:
            continue
        if key in options and options[key] is not None and str(options[key]).strip() != "":
            out[low] = str(options[key])
    return out


def content_hash(stem: str, options: dict[str, str]) -> str:
    payload = {
        "stem": (stem or "").strip(),
        "options": {k: options[k] for k in sorted(options)},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def iter_paper_files(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for fp in sorted(source_dir.rglob("*.json")):
        if fp.name in SKIP_NAMES or "schema" in fp.name.lower():
            continue
        files.append(fp)
    return files


def load_cleaned_by_qid(path: Path) -> dict[str, dict[str, Any]]:
    """Map q_id -> useful fields from cleaned pattern JSONL."""
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            qid = row.get("q_id")
            if not qid:
                continue
            out[qid] = {
                "question_pattern": row.get("question_pattern"),
                "has_image": row.get("has_image"),
                "image_refs": row.get("image_refs"),
                "section": row.get("section"),
                "topic": row.get("topic"),
            }
    return out


def extract_image_refs(question: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for block in question.get("context") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "image" or block.get("role") in {"figure", "chart", "diagram"}:
            refs.append(block)
    return refs


def detect_has_image(
    question: dict[str, Any],
    refs: list[dict[str, Any]],
    cleaned: dict[str, Any] | None,
    question_pattern: str | None,
) -> bool:
    if refs:
        return True
    if cleaned and cleaned.get("has_image"):
        return True
    if question_pattern in {"image_figure_based", "visual_chart_graph_di"}:
        return True
    text = f"{question.get('direction_text') or ''}\n{question.get('stem') or ''}".lower()
    cues = (
        "pie chart",
        "bar graph",
        "line graph",
        "radar chart",
        "following diagram",
        "following figure",
        "study the following diagram",
        "as shown in the figure",
    )
    return any(c in text for c in cues)


def paper_completeness(paper: dict[str, Any]) -> tuple[int, int, int]:
    """Higher is better for is_canonical: (with_options, question_count, has_meta)."""
    qs = paper.get("questions") or []
    with_opts = 0
    for q in qs:
        opts = normalize_options(q.get("options"))
        if len(opts) >= 4:
            with_opts += 1
    meta = 0
    for field in ("bank", "role", "exam_type", "year"):
        if paper.get(field) not in (None, ""):
            meta += 1
    return (with_opts, len(qs), meta)


def merge_subject_splits(loaded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    papers-deduped stores one physical paper as multiple subject JSON files
    that share the same paper_id. Merge them into one paper with combined questions.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for paper in loaded:
        pid = paper["paper_id"]
        if pid not in by_id:
            by_id[pid] = dict(paper)
            by_id[pid]["questions"] = list(paper.get("questions") or [])
            continue
        existing = by_id[pid]
        # Prefer non-null metadata
        for field in ("bank", "role", "exam_type", "year", "shift", "memory_based", "language"):
            if existing.get(field) in (None, "") and paper.get(field) not in (None, ""):
                existing[field] = paper.get(field)
        if not (existing.get("source") or {}).get("pdf_path"):
            existing["source"] = paper.get("source") or existing.get("source")
        # Merge questions by q_id
        by_qid = {q.get("q_id"): q for q in existing["questions"]}
        for q in paper.get("questions") or []:
            q = dict(q)
            if not q.get("section") and paper.get("subject") not in (None, "", "Unclassified"):
                q["section"] = paper.get("subject")
            qid = q.get("q_id")
            if qid not in by_qid:
                by_qid[qid] = q
                continue
            prev = by_qid[qid]
            # Prefer filled section / richer options
            if not prev.get("section") and q.get("section"):
                prev["section"] = q.get("section")
            prev_opts = len(normalize_options(prev.get("options")))
            new_opts = len(normalize_options(q.get("options")))
            if new_opts > prev_opts:
                keep_section = prev.get("section") or q.get("section")
                by_qid[qid] = q
                if keep_section and not by_qid[qid].get("section"):
                    by_qid[qid]["section"] = keep_section
            elif not prev.get("direction_text") and q.get("direction_text"):
                prev["direction_text"] = q.get("direction_text")
                prev["direction_id"] = q.get("direction_id") or prev.get("direction_id")
        existing["questions"] = list(by_qid.values())

    merged = list(by_id.values())
    for paper in merged:
        paper["questions"].sort(key=lambda q: int(q.get("q_num") or 0))
        paper["question_count"] = len(paper["questions"])
    return merged


def build(
    *,
    papers_dir: Path,
    cleaned_jsonl: Path,
    patterns_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    patterns = json.loads(patterns_path.read_text(encoding="utf-8"))
    cleaned_by_qid = load_cleaned_by_qid(cleaned_jsonl)

    paper_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []
    question_rows: list[dict[str, Any]] = []

    # Collect papers first for canonical selection
    loaded_raw: list[dict[str, Any]] = []
    for fp in iter_paper_files(papers_dir):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "paper_id" not in data or "questions" not in data:
            continue
        loaded_raw.append(data)

    files_seen = len(loaded_raw)
    loaded = merge_subject_splits(loaded_raw)

    by_exam_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for paper in loaded:
        key = make_exam_key(
            paper.get("bank"),
            paper.get("role"),
            paper.get("exam_type"),
            paper.get("year"),
            paper.get("shift"),
        )
        by_exam_key[key].append(paper)

    canonical_ids: set[str] = set()
    for key, group in by_exam_key.items():
        best = max(group, key=paper_completeness)
        canonical_ids.add(best["paper_id"])

    active_papers = 0
    inactive_questions = 0
    missing_answer = 0
    with_direction = 0

    for paper in loaded:
        paper_id = paper["paper_id"]
        bank = paper.get("bank")
        role = paper.get("role")
        exam_type = paper.get("exam_type")
        year = paper.get("year")
        shift = paper.get("shift")
        exam_key = make_exam_key(bank, role, exam_type, year, shift)
        pat = lookup_pattern(patterns, bank, role, exam_type)
        source = paper.get("source") or {}
        questions = paper.get("questions") or []

        # Paper active if it has at least one usable question
        usable = sum(1 for q in questions if len(normalize_options(q.get("options"))) >= 4)
        is_active = usable > 0
        if is_active:
            active_papers += 1

        paper_rows.append(
            {
                "paper_id": paper_id,
                "bank": bank,
                "role": role,
                "exam_type": exam_type,
                "year": year,
                "shift": shift,
                "memory_based": paper.get("memory_based"),
                "exam_key": exam_key,
                "is_canonical": paper_id in canonical_ids,
                "duration_min": pat.get("duration_min"),
                "total_marks": pat.get("total_marks"),
                "section_timing": pat.get("section_timing"),
                "source_pdf": source.get("pdf_path"),
                "is_active": is_active,
                "question_count": len(questions),
                "language": paper.get("language"),
            }
        )

        # Directions: unique by (paper_id, direction_id)
        seen_dirs: set[str] = set()
        for q in questions:
            did = q.get("direction_id")
            body = (q.get("direction_text") or "").strip()
            if not did or not body:
                continue
            if did in seen_dirs:
                continue
            seen_dirs.add(did)
            direction_rows.append(
                {
                    "paper_id": paper_id,
                    "direction_id": did,
                    "body": body,
                }
            )

        for q in questions:
            opts = normalize_options(q.get("options"))
            stem = q.get("stem") or ""
            q_id = q.get("q_id") or f"{paper_id}::q{int(q.get('q_num') or 0):03d}"
            q_num = int(q.get("q_num") or 0)
            option_count = len(opts)
            is_q_active = option_count >= 4 and bool(stem.strip())
            if not is_q_active:
                inactive_questions += 1
            if not q.get("answer"):
                missing_answer += 1
            if q.get("direction_id"):
                with_direction += 1

            cleaned = cleaned_by_qid.get(q_id) or {}
            question_pattern = cleaned.get("question_pattern")

            # Prefer section from paper subject folder when question section empty
            section = q.get("section") or paper.get("subject") or cleaned.get("section")
            if section in ("Unclassified", ""):
                section = q.get("section") or cleaned.get("section") or None

            metrics = q.get("metrics") or {}
            image_refs = extract_image_refs(q)
            if not image_refs and isinstance(cleaned.get("image_refs"), list):
                image_refs = cleaned.get("image_refs") or []
            has_image = detect_has_image(q, image_refs, cleaned, question_pattern)

            question_rows.append(
                {
                    # Stage 1 — parser
                    "q_id": q_id,
                    "paper_id": paper_id,
                    "q_num": q_num,
                    "stem": stem,
                    "options": opts,
                    "answer": q.get("answer"),
                    "explanation": q.get("explanation"),
                    "direction_id": q.get("direction_id"),
                    "has_image": has_image,
                    "image_refs": image_refs,
                    "page_start": metrics.get("page_start"),
                    # Stage 2 — classifier
                    "section": section if section not in ("Unclassified",) else None,
                    "topic": q.get("topic") or cleaned.get("topic"),
                    "topic_source": q.get("topic_source"),
                    "difficulty": q.get("difficulty"),
                    # Stage 3 — import script
                    "content_hash": content_hash(stem, opts),
                    "marks": pat.get("marks_per_question"),
                    "negative_marks": pat.get("negative_marks"),
                    "option_count": option_count,
                    "is_active": is_q_active,
                    # Extra from pattern pipeline
                    "question_pattern": question_pattern,
                }
            )

    # Dedupe questions by content_hash keeping first active, else first
    hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in question_rows:
        hash_groups[row["content_hash"]].append(row)
    duplicate_hashes = sum(1 for rows in hash_groups.values() if len(rows) > 1)

    paper_rows.sort(key=lambda r: r["paper_id"])
    direction_rows.sort(key=lambda r: (r["paper_id"], r["direction_id"]))
    question_rows.sort(key=lambda r: (r["paper_id"], r["q_num"], r["q_id"]))

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "papers.jsonl", paper_rows)
    write_jsonl(out_dir / "directions.jsonl", direction_rows)
    write_jsonl(out_dir / "questions.jsonl", question_rows)
    # Runtime tables — empty until product traffic
    write_jsonl(out_dir / "attempts.jsonl", [])
    write_jsonl(out_dir / "attempt_answers.jsonl", [])
    write_jsonl(out_dir / "user_topic_stats.jsonl", [])

    # Also dump schemas catalog
    schemas_dir = ROOT / "schemas"
    catalog = {
        "tables": [
            {"name": "papers", "rows": len(paper_rows), "populated": True},
            {"name": "directions", "rows": len(direction_rows), "populated": True},
            {"name": "questions", "rows": len(question_rows), "populated": True},
            {"name": "attempts", "rows": 0, "populated": False},
            {"name": "attempt_answers", "rows": 0, "populated": False},
            {"name": "user_topic_stats", "rows": 0, "populated": False},
        ]
    }
    (out_dir / "tables_catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "source_papers_dir": str(papers_dir.as_posix()),
        "cleaned_jsonl": str(cleaned_jsonl.as_posix()),
        "paper_files_seen": files_seen,
        "papers": len(paper_rows),
        "papers_active": active_papers,
        "papers_canonical": sum(1 for r in paper_rows if r["is_canonical"]),
        "unique_exam_keys": len(by_exam_key),
        "directions": len(direction_rows),
        "questions": len(question_rows),
        "questions_active": sum(1 for r in question_rows if r["is_active"]),
        "questions_inactive": inactive_questions,
        "questions_missing_answer": missing_answer,
        "questions_with_direction": with_direction,
        "questions_with_pattern": sum(1 for r in question_rows if r.get("question_pattern")),
        "duplicate_content_hash_groups": duplicate_hashes,
        "bank_counts": dict(Counter(r.get("bank") for r in paper_rows).most_common()),
        "outputs": {
            "papers": str((out_dir / "papers.jsonl").as_posix()),
            "directions": str((out_dir / "directions.jsonl").as_posix()),
            "questions": str((out_dir / "questions.jsonl").as_posix()),
            "attempts": str((out_dir / "attempts.jsonl").as_posix()),
            "attempt_answers": str((out_dir / "attempt_answers.jsonl").as_posix()),
            "user_topic_stats": str((out_dir / "user_topic_stats.jsonl").as_posix()),
            "tables_catalog": str((out_dir / "tables_catalog.json").as_posix()),
        },
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build 6 feature tables from papers-deduped")
    parser.add_argument("--papers-dir", type=Path, default=DEFAULT_PAPERS)
    parser.add_argument("--cleaned-jsonl", type=Path, default=DEFAULT_CLEANED)
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build(
        papers_dir=args.papers_dir,
        cleaned_jsonl=args.cleaned_jsonl,
        patterns_path=args.patterns,
        out_dir=args.out_dir,
    )
    print(
        f"papers={report['papers']} directions={report['directions']} "
        f"questions={report['questions']} canonical={report['papers_canonical']}"
    )
    print(f"wrote {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

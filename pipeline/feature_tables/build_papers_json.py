#!/usr/bin/env python3
"""
Split feature_tables/out/questions.jsonl into a papers_json/ tree:

  papers_json/{bank}/{role}/{year}/{exam_type}/{paper_id}.json

Mirrors the papers/ layout (bank → role → year → exam). Unknowns use
_unknown_bank / _unknown_role / no_year / _unknown_stage.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DEFAULT_QUESTIONS = ROOT / "out" / "questions.jsonl"
DEFAULT_PAPERS = ROOT / "out" / "papers.jsonl"
DEFAULT_OUT = REPO / "corpus/papers_json"


def slug_bank(value: Any) -> str:
    if value in (None, ""):
        return "_unknown_bank"
    return str(value).strip()


def slug_role(value: Any) -> str:
    if value in (None, ""):
        return "_unknown_role"
    return str(value).strip()


def slug_year(value: Any) -> str:
    if value in (None, ""):
        return "no_year"
    return str(int(value)) if isinstance(value, int) else str(value).strip() or "no_year"


def slug_exam(value: Any) -> str:
    if value in (None, ""):
        return "_unknown_stage"
    return str(value).strip()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build(
    *,
    questions_path: Path,
    papers_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    papers = {p["paper_id"]: p for p in load_jsonl(papers_path)}
    questions = load_jsonl(questions_path)

    by_paper: dict[str, list[dict[str, Any]]] = defaultdict(list)
    orphan_questions = 0
    for q in questions:
        pid = q.get("paper_id")
        if not pid:
            orphan_questions += 1
            continue
        by_paper[pid].append(q)

    # Clear previous tree if present
    if out_dir.exists():
        # only remove contents under papers_json, keep folder
        for child in sorted(out_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    pass
    out_dir.mkdir(parents=True, exist_ok=True)

    files_written = 0
    questions_written = 0
    bank_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    exam_counts: Counter[str] = Counter()
    path_counts: Counter[str] = Counter()
    missing_paper_meta = 0
    tree: dict[str, Any] = {}

    for paper_id, qs in sorted(by_paper.items()):
        meta = papers.get(paper_id)
        if meta is None:
            missing_paper_meta += 1
            # derive what we can from paper_id slug
            meta = {
                "paper_id": paper_id,
                "bank": None,
                "role": None,
                "exam_type": None,
                "year": None,
                "shift": None,
            }

        bank = slug_bank(meta.get("bank"))
        role = slug_role(meta.get("role"))
        year = slug_year(meta.get("year"))
        exam = slug_exam(meta.get("exam_type"))

        rel_dir = Path(bank) / role / year / exam
        abs_dir = out_dir / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        qs_sorted = sorted(qs, key=lambda r: (r.get("q_num") or 0, r.get("q_id") or ""))
        payload = {
            "paper_id": paper_id,
            "bank": meta.get("bank"),
            "role": meta.get("role"),
            "exam_type": meta.get("exam_type"),
            "year": meta.get("year"),
            "shift": meta.get("shift"),
            "memory_based": meta.get("memory_based"),
            "exam_key": meta.get("exam_key"),
            "is_canonical": meta.get("is_canonical"),
            "duration_min": meta.get("duration_min"),
            "total_marks": meta.get("total_marks"),
            "section_timing": meta.get("section_timing"),
            "source_pdf": meta.get("source_pdf"),
            "is_active": meta.get("is_active"),
            "language": meta.get("language"),
            "question_count": len(qs_sorted),
            "questions": qs_sorted,
        }

        out_path = abs_dir / f"{paper_id}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        files_written += 1
        questions_written += len(qs_sorted)
        bank_counts[bank] += 1
        role_counts[f"{bank}/{role}"] += 1
        year_counts[f"{bank}/{role}/{year}"] += 1
        exam_counts[f"{bank}/{role}/{year}/{exam}"] += 1
        path_counts[str(rel_dir).replace("\\", "/")] += 1

        # nested tree summary
        tree.setdefault(bank, {}).setdefault(role, {}).setdefault(year, {}).setdefault(exam, {
            "files": 0,
            "questions": 0,
            "paper_ids": [],
        })
        node = tree[bank][role][year][exam]
        node["files"] += 1
        node["questions"] += len(qs_sorted)
        node["paper_ids"].append(paper_id)

    report = {
        "source_questions": str(questions_path.as_posix()),
        "source_papers": str(papers_path.as_posix()),
        "out_dir": str(out_dir.as_posix()),
        "layout": "corpus/papers_json/{bank}/{role}/{year}/{exam_type}/{paper_id}.json",
        "totals": {
            "input_questions": len(questions),
            "unique_papers_in_questions": len(by_paper),
            "papers_meta_available": len(papers),
            "files_written": files_written,
            "questions_written": questions_written,
            "orphan_questions_no_paper_id": orphan_questions,
            "papers_missing_meta": missing_paper_meta,
        },
        "by_bank": dict(bank_counts.most_common()),
        "by_bank_role": dict(role_counts.most_common()),
        "by_bank_role_year": dict(sorted(year_counts.items())),
        "by_bank_role_year_exam": dict(sorted(exam_counts.items())),
        "tree": tree,
    }

    report_path = out_dir / "separation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Also a short markdown report
    md_lines = [
        "# papers_json separation report",
        "",
        f"- Layout: `{report['layout']}`",
        f"- Files written: **{files_written}**",
        f"- Questions written: **{questions_written}**",
        f"- Papers missing meta: {missing_paper_meta}",
        "",
        "## By bank",
        "",
    ]
    for bank, n in bank_counts.most_common():
        md_lines.append(f"- `{bank}`: {n} papers")
    md_lines.extend(["", "## By bank / role / year / exam", ""])
    for key, n in sorted(exam_counts.items()):
        qs = tree
        parts = key.split("/")
        # key is bank/role/year/exam
        try:
            qn = tree[parts[0]][parts[1]][parts[2]][parts[3]]["questions"]
        except Exception:
            qn = "?"
        md_lines.append(f"- `{key}`: {n} papers, {qn} questions")
    md_path = out_dir / "separation_report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    report["outputs"] = {
        "separation_report_json": str(report_path.as_posix()),
        "separation_report_md": str(md_path.as_posix()),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Split questions.jsonl into papers_json tree")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--papers", type=Path, default=DEFAULT_PAPERS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = build(
        questions_path=args.questions,
        papers_path=args.papers,
        out_dir=args.out_dir,
    )
    t = report["totals"]
    print(
        f"files={t['files_written']} questions={t['questions_written']} "
        f"out={args.out_dir}"
    )
    print(f"report={report['outputs']['separation_report_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

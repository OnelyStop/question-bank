"""Paths and paper helpers shared by more than one step.

These live here because the step folders are named `1-extract`, `2-classify` and
so on — not valid Python identifiers, so no step can import another. Anything two
steps both need has to come through `lib/`.

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper

`iter_paper_jsons` and `load_paper` were duplicated in two steps before this.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "corpus" / "pdf"
DEFAULT_OUT = REPO_ROOT / "corpus" / "papers"

SKIP_JSON = {
    "parse_report.json",
    "answer_attach_report.json",
    "answer_validation_report.json",
    "question_bank.schema.json",
    "section_label_report.json",
    "topic_label_report.json",
}

def rebuild_index(out_root: Path) -> int:
    index_path = out_root / "index.jsonl"
    count = 0
    with index_path.open("w", encoding="utf-8") as fh:
        for path in sorted(out_root.rglob("*.json")):
            if path.name in {"parse_report.json", "index.json"}:
                continue
            if path.name.endswith(".meta.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if "questions" not in data or "paper_id" not in data:
                continue
            # Rebuild Paper-like index rows without full dataclass
            for q in data.get("questions") or []:
                row = {
                    "q_id": q.get("q_id"),
                    "paper_id": data.get("paper_id"),
                    "bank": data.get("bank"),
                    "role": data.get("role"),
                    "exam_type": data.get("exam_type"),
                    "year": data.get("year"),
                    "shift": data.get("shift"),
                    "memory_based": data.get("memory_based"),
                    "language": data.get("language"),
                    "q_num": q.get("q_num"),
                    "section": q.get("section"),
                    "topic": q.get("topic"),
                    "direction_id": q.get("direction_id"),
                    "has_passage": (q.get("metrics") or {}).get("has_passage"),
                    "option_count": (q.get("metrics") or {}).get("option_count"),
                    "stem": q.get("stem"),
                    "options": q.get("options"),
                    "answer": q.get("answer"),
                    "answer_confidence": q.get("answer_confidence"),
                    "answer_source": q.get("answer_source"),
                    "pdf_path": (data.get("source") or {}).get("pdf_path"),
                    "context_status": q.get("context_status"),
                    "context_issues": q.get("context_issues"),
                    "has_context_images": any(
                        b.get("type") == "image"
                        and b.get("asset")
                        and b.get("role") == "figure"
                        for b in (q.get("context") or [])
                    ),
                }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    return count

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

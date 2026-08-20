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
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("corpus")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "corpus" / "pdf"
DEFAULT_OUT = REPO_ROOT / "data" / "papers"

# What step 1 writes on every question -- see pipeline/1-extract/output.json.
INDEX_FIELDS = (
    "q_id", "paper_id", "q_num", "stem", "options",
    "direction_id", "direction_has_image",
    "bank", "role", "exam_type", "year", "memory_based", "has_image",
)

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
            if not isinstance(data, dict):
                continue
            if "questions" not in data or "paper_id" not in data:
                continue
            # One row per question, flat. Fields come off the question itself:
            # step 1 copies the paper's identity onto every question, so a row
            # needs no join. Reading `metrics`, `context`, `context_status` and
            # `shift` off it silently produced a column of nulls once those left
            # the question shape.
            for q in data.get("questions") or []:
                row = {k: q.get(k) for k in INDEX_FIELDS}
                row["topic"] = q.get("topic")          # added by 2-classify
                row["section"] = q.get("section")      # added by 2-classify
                row["answer"] = q.get("answer")        # added by 4-answer
                row["pdf_path"] = data.get("source_pdf")
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


HINDI_NAME_RE = re.compile(r"(?:[\-_ ]|^)(?:hindi|hin)(?:[\-_ .]|$)", re.I)


SOLUTION_NAME_RE = re.compile(r"solution", re.I)


def build_full_text(pages: list[tuple[int, str]]) -> tuple[str, list[tuple[int, int, int]]]:
    chunks: list[str] = []
    spans: list[tuple[int, int, int]] = []
    pos = 0
    for page_num, raw in pages:
        cleaned = clean_lines(raw)
        if not cleaned:
            continue
        if chunks:
            chunks.append("\n\n")
            pos += 2
        start = pos
        chunks.append(cleaned)
        pos += len(cleaned)
        spans.append((page_num, start, pos))
    return "".join(chunks), spans


def load_meta(pdf_path: Path) -> dict[str, Any]:
    sidecar = pdf_path.with_suffix(pdf_path.suffix + ".meta.json")
    if sidecar.is_file():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Bad meta JSON: %s", sidecar)
    return {}


def meta_from_path(pdf_path: Path, corpus: Path) -> dict[str, Any]:
    try:
        rel = pdf_path.relative_to(corpus)
    except ValueError:
        return {}
    parts = rel.parts
    out: dict[str, Any] = {"source_filename": pdf_path.name}
    if len(parts) >= 6:
        out["bank"] = None if parts[0].startswith("_") else parts[0]
        out["role"] = None if parts[1].startswith("_") else parts[1]
        out["year"] = None if parts[2] in {"no_year"} else parts[2]
        out["stage"] = None if parts[3].startswith("_") else parts[3]
        out["shift"] = None if parts[4].startswith("_") else parts[4]
    return out


DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


def strip_devanagari(text: str | None) -> str | None:
    """Cut the Hindi translation these papers append to the English.

    Bilingual papers print the English question, then the same question in
    Devanagari, in one block -- "…difference between present age of A & B?
    यदि A और B की…" -- and options as "14 years 14 वर्त". The English never
    resumes afterwards, checked across the bilingual papers here, so cutting at
    the first Devanagari character is enough.

    A Hindi-first paper would be left almost empty by this; that is the right
    outcome for an English-only bank, and check_gaps reports the empty stems.
    """
    if not text:
        return text
    m = DEVANAGARI_RE.search(text)
    if not m:
        return text
    return text[: m.start()].strip(" \t\n-/|,;")


def clean_lines(text: str, drop_bare_numbers: bool = True) -> str:
    """Strip coaching-house boilerplate lines.

    Pass `drop_bare_numbers=False` when working from page geometry. A stacked
    fraction prints its numerator on a line of its own, and the page-number rule
    ate it: "33 1/3 %" came out as "33 3 %" -- a wrong option that looks real.
    Those callers drop page numbers by header/footer band instead.
    """
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            kept.append("")
            continue
        if not drop_bare_numbers and line.isdigit():
            kept.append(line)
            continue
        if NOISE_LINE_RE.match(line):
            continue
        kept.append(line)
    out: list[str] = []
    blanks = 0
    for line in kept:
        if line == "":
            blanks += 1
            if blanks <= 1:
                out.append("")
        else:
            blanks = 0
            out.append(line)
    return "\n".join(out).strip()


NOISE_LINE_RE = re.compile(
    r"(?i)^("
    r"adda247.*|"
    r"www\.[a-z0-9.\-]+.*|"
    r"website:.*|"
    r"email:.*|"
    r"info@[a-z0-9.\-]+.*|"
    r"store\.adda247\.com.*|"
    r"bankersadda\.com.*|"
    r"sscadda\.com.*|"
    r"careerpower\.in.*|"
    r"practicemock\.com.*|"
    r"page\s*\d+.*|"
    r"\d+\s*$|"
    r".*info@practicemock\.com.*"
    r")$"
)

# Directions (1-5): …  OR  Direction (1-5): …

"""
Convert bank exam PYQ PDFs in corpus/ into structured JSON under corpus/papers/.

Usually just run:
  python pdf_question_pipeline.py --force --skip-answers

This file still works on its own if you want:
  python pdf_to_questions.py --limit 20
  python pdf_to_questions.py --force
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

import fitz

from context_completeness import (
    assess_context,
    is_decorative_image_block,
    should_synthesize_cloze_stem,
)
from ocr_supplement import supplement_context_ocr
from page_stream import (
    extract_page_stream,
    flatten_context_text,
    items_for_char_range,
)
from question_schema import (
    Paper,
    Question,
    QuestionMetrics,
    detect_section,
    make_direction_id,
    make_paper_id,
    make_q_id,
)

# tools/pdf_pipeline/ → repo root is two levels up
ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DEFAULT_CORPUS = REPO_ROOT / "corpus"
DEFAULT_OUT = REPO_ROOT / "corpus" / "papers"

log = logging.getLogger("pdf_to_questions")

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
DIRECTION_RANGE_RE = re.compile(
    r"(?is)Directions?\s*\(\s*(\d+)\s*[-–—to]+\s*(\d+)\s*\)\s*:?\s*"
)
# Bare "Directions:" / "Directions : Answer the questions…"
DIRECTION_BARE_RE = re.compile(r"(?im)^\s*Directions?\s*:\s+")

# 1.  | 1)  | Q1.  | Q.1  | Q 1.  | Question 1:  | Question 1.
QUESTION_START_RE = re.compile(
    r"(?im)^\s*(?:Question\s+|Q\s*\.?\s*)?(\d{1,3})\s*(?:[.):]|[\u0964])\s+"
)

# Lowercase only — uppercase (A) is stimulus, not MCQ option
OPTION_SPLIT_RE = re.compile(r"(?:\(\s*([a-e])\s*\)|(?<![A-Za-z])([a-e])\s*\))\s+")
# A) or A. style (some papers)
ALT_OPTION_SPLIT_RE = re.compile(r"(?m)^\s*([A-E])[\.\)]\s+")

SOLUTIONS_CUT_RE = re.compile(
    r"(?im)^\s*(?:SOLUTIONS?(?:\s+AND\s+EXPLANATIONS?)?|ANSWER\s+KEY|"
    r"DETAILED\s+SOLUTIONS?)\s*$"
)
STIMULUS_LABEL_RE = re.compile(r"\([A-F]\)\s+\S{10,}")
OPTION_BLEED_CUT_RE = re.compile(
    r"(?i)\s*(?:Directions?\s*\(|Question\s+\d+|Q\s*\d+\.|"
    r"Copyright\s*©|www\.[a-z0-9.\-]+).*$"
)

# Keep old name as alias used in find_events
DIRECTION_RE = DIRECTION_RANGE_RE

SOLUTION_NAME_RE = re.compile(r"solution", re.I)
HINDI_NAME_RE = re.compile(r"(?:[\-_ ]|^)(?:hindi|hin)(?:[\-_ .]|$)", re.I)

SECTION_LINE_RE = re.compile(
    r"(?im)^\s*(REASONING(?:\s+ABILITY)?|QUANTITATIVE(?:\s+APTITUDE)?|"
    r"NUMERICAL\s+ABILITY|ENGLISH(?:\s+LANGUAGE)?|GENERAL\s+AWARENESS|"
    r"BANKING\s+AWARENESS|COMPUTER(?:\s+APTITUDE|\s+KNOWLEDGE)?)\s*$"
)


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


def should_skip(pdf_path: Path, meta: dict[str, Any]) -> str | None:
    name = pdf_path.name
    lang = (meta.get("language") or "").lower()
    if lang == "hindi" or HINDI_NAME_RE.search(name):
        return "hindi"
    if SOLUTION_NAME_RE.search(name):
        return "solutions_pdf"
    return None


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    doc = fitz.open(pdf_path)
    pages: list[tuple[int, str]] = []
    try:
        for i, page in enumerate(doc, start=1):
            pages.append((i, page.get_text() or ""))
    finally:
        doc.close()
    return pages


def clean_lines(text: str) -> str:
    kept: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            kept.append("")
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


def page_at(char_index: int, spans: list[tuple[int, int, int]]) -> int | None:
    for page_num, start, end in spans:
        if start <= char_index < end:
            return page_num
    if spans and char_index >= spans[-1][1]:
        return spans[-1][0]
    return None


def cut_solutions_section(text: str) -> str:
    m = SOLUTIONS_CUT_RE.search(text)
    if m:
        return text[: m.start()].strip()
    return text


def direction_has_stimulus_labels(raw_body: str) -> bool:
    return bool(STIMULUS_LABEL_RE.search(raw_body))


def truncate_option_text(text: str) -> str:
    m = OPTION_BLEED_CUT_RE.search(text)
    if m:
        return text[: m.start()].strip()
    return text.strip()


def parse_options_alt_dot(block: str) -> tuple[str, dict[str, str]]:
    """Parse A. / B. line-start options."""
    matches = list(ALT_OPTION_SPLIT_RE.finditer(block))
    if not matches:
        return block.strip(), {}
    start_m = matches[0]
    stem = block[: start_m.start()].strip()
    options: dict[str, str] = {}
    for idx, m in enumerate(matches):
        label = m.group(1).lower()
        if label not in "abcde":
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        text = truncate_option_text(block[m.end() : end])
        text = re.sub(r"\s+", " ", text).strip(" \t\n;-")
        if text:
            options[label] = text
    return stem, options


def parse_options(block: str) -> tuple[str, dict[str, str]]:
    """Split block into text-before-options and options a–e (last full set wins)."""
    block = truncate_option_text(block)
    matches = list(OPTION_SPLIT_RE.finditer(block))
    if not matches:
        stem, opts = parse_options_alt_dot(block)
        if opts:
            return stem, opts
        return block.strip(), {}

    def label_of(m: re.Match[str]) -> str:
        return (m.group(1) or m.group(2) or "").lower()

    best_start = None
    for i, _m in enumerate(matches):
        labels: list[str] = []
        j = i
        expected = "a"
        while j < len(matches) and label_of(matches[j]) == expected:
            labels.append(expected)
            expected = chr(ord(expected) + 1)
            j += 1
            if expected > "e":
                break
        if labels in (list("abcde"), list("abcd")):
            best_start = i
    if best_start is None:
        best_start = 0

    start_m = matches[best_start]
    stem = block[: start_m.start()].strip()
    options: dict[str, str] = {}
    run = matches[best_start:]
    for idx, m in enumerate(run):
        label = label_of(m)
        if label not in "abcde":
            continue
        if label == "a" and options:
            break
        end = run[idx + 1].start() if idx + 1 < len(run) else len(block)
        text = truncate_option_text(block[m.end() : end])
        text = re.sub(r"\s+", " ", text).strip(" \t\n;-")
        if text:
            options[label] = text
        if label == "e":
            break
    if not options:
        return parse_options_alt_dot(block)
    return stem, options


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def section_map_from_text(text: str) -> list[tuple[int, str]]:
    """Char offsets where a section header appears."""
    found: list[tuple[int, str]] = []
    for m in SECTION_LINE_RE.finditer(text):
        label = detect_section(m.group(1)) or m.group(1).title()
        found.append((m.start(), label))
    return found


def section_at(pos: int, section_spans: list[tuple[int, str]]) -> str | None:
    current = None
    for start, label in section_spans:
        if start <= pos:
            current = label
        else:
            break
    return current


def direction_covers(active_dir: dict[str, Any] | None, q_num: int) -> bool:
    if not active_dir:
        return False
    q_lo, q_hi = active_dir.get("q_start"), active_dir.get("q_end")
    if q_lo is None or q_hi is None:
        # Bare direction applies until replaced by a later direction event
        return True
    return q_lo <= q_num <= q_hi


def find_events(text: str) -> list[dict[str, Any]]:
    """Ordered direction + question anchors."""
    events: list[dict[str, Any]] = []
    for m in DIRECTION_RANGE_RE.finditer(text):
        events.append(
            {
                "kind": "direction",
                "start": m.start(),
                "end": m.end(),
                "q_start": int(m.group(1)),
                "q_end": int(m.group(2)),
                "match": m,
            }
        )
    for m in DIRECTION_BARE_RE.finditer(text):
        # Skip if this position already covered by a ranged direction
        if any(e["kind"] == "direction" and e["start"] == m.start() for e in events):
            continue
        # Avoid double-hit when "Directions (1-5):" also matched bare somehow
        if DIRECTION_RANGE_RE.match(text[m.start() : m.start() + 40]):
            continue
        events.append(
            {
                "kind": "direction",
                "start": m.start(),
                "end": m.end(),
                "q_start": None,
                "q_end": None,
                "match": m,
            }
        )
    for m in QUESTION_START_RE.finditer(text):
        events.append(
            {
                "kind": "question",
                "start": m.start(),
                "end": m.end(),
                "q_num": int(m.group(1)),
                "match": m,
            }
        )
    events.sort(key=lambda e: (e["start"], 0 if e["kind"] == "direction" else 1))
    return events


def parse_questions_from_text(
    text: str,
    page_spans: list[tuple[int, int, int]],
    paper_id: str,
    stream_items: list[Any] | None = None,
) -> tuple[list[Question], list[str]]:
    notes: list[str] = []
    text = cut_solutions_section(text)
    if not text.strip():
        return [], ["empty_text"]

    events = find_events(text)
    section_spans = section_map_from_text(text)
    questions: list[Question] = []
    seen_nums: set[int] = set()

    directions: list[dict[str, Any]] = []
    active_bare_dir: dict[str, Any] | None = None
    direction_seq = 0

    i = 0
    while i < len(events):
        ev = events[i]
        if ev["kind"] == "direction":
            direction_seq += 1
            dir_id = make_direction_id(direction_seq)
            q_lo, q_hi = ev["q_start"], ev["q_end"]
            body_end = len(text)
            for j in range(i + 1, len(events)):
                nxt = events[j]
                if nxt["kind"] == "direction":
                    body_end = nxt["start"]
                    break
                if nxt["kind"] == "question":
                    if q_lo is None or q_lo <= nxt["q_num"] <= q_hi:
                        body_end = nxt["start"]
                        break
            raw_body = text[ev["end"] : body_end]
            direction_text = normalize_ws(raw_body)
            shared_opts: dict[str, str] = {}
            if not direction_has_stimulus_labels(raw_body):
                _pre, shared_opts = parse_options(raw_body)
                if shared_opts and len(_pre) > len(direction_text) * 0.5:
                    direction_text = normalize_ws(_pre) or direction_text

            dir_page_lo = page_at(ev["start"], page_spans)
            dir_page_hi = page_at(max(ev["end"], body_end - 1), page_spans)
            pages = (dir_page_lo or 1, dir_page_hi or dir_page_lo or 1)
            dir_context_blocks: list[dict[str, Any]] = []
            if stream_items is not None:
                dir_context_blocks = items_for_char_range(
                    stream_items, ev["start"], body_end, pages=pages
                )
            if not dir_context_blocks and direction_text:
                dir_context_blocks = [{"type": "text", "text": direction_text}]

            dir_record = {
                "id": dir_id,
                "q_start": q_lo,
                "q_end": q_hi,
                "text": direction_text or None,
                "shared_options": shared_opts,
                "body_start": ev["start"],
                "body_end": body_end,
                "pages": pages,
                "context": dir_context_blocks,
                "event_start": ev["start"],
            }
            directions.append(dir_record)
            if q_lo is None:
                active_bare_dir = dir_record
            i += 1
            continue

        # question
        q_num = ev["q_num"]
        if q_num > 200:
            i += 1
            continue
        if q_num in seen_nums:
            i += 1
            continue

        active_dir: dict[str, Any] | None = None
        for d in reversed(directions):
            if direction_covers(d, q_num):
                active_dir = d
                break
        if active_dir is None and active_bare_dir and direction_covers(active_bare_dir, q_num):
            active_dir = active_bare_dir

        block_end = len(text)
        for j in range(i + 1, len(events)):
            nxt = events[j]
            if nxt["kind"] == "direction":
                block_end = nxt["start"]
                break
            if nxt["kind"] == "question":
                if nxt["q_num"] != q_num:
                    block_end = nxt["start"]
                    break

        raw_q = text[ev["end"] : block_end]
        stem, options = parse_options(raw_q)
        stem = normalize_ws(stem)

        if not options and active_dir and active_dir.get("shared_options"):
            if direction_covers(active_dir, q_num):
                options = dict(active_dir["shared_options"])

        if not stem and options:
            if direction_covers(active_dir, q_num) and should_synthesize_cloze_stem(
                active_dir.get("text") if active_dir else None, raw_q
            ):
                stem = f"Select the word that fits blank ({q_num})."
            elif options:
                stem = f"Question {q_num}."
            else:
                stem = f"Question {q_num}."

        if not stem:
            notes.append(f"empty_stem_q{q_num}")
            i += 1
            continue

        if len(stem) < 8 and not options:
            i += 1
            continue

        p_start = page_at(ev["start"], page_spans)
        p_end = page_at(max(ev["start"], block_end - 1), page_spans)
        section = section_at(ev["start"], section_spans)
        dir_id = None
        dir_text = None
        q_context: list[dict[str, Any]] = []
        if direction_covers(active_dir, q_num):
            dir_id = active_dir["id"]  # type: ignore[index]
            dir_text = active_dir["text"]  # type: ignore[index]
            if dir_text:
                q_context.append({"type": "text", "text": dir_text, "role": "direction"})
            if stream_items is not None:
                q_pages = (p_start or 1, p_end or p_start or 1)
                q_imgs = items_for_char_range(
                    stream_items,
                    ev["start"],
                    block_end,
                    pages=None,
                )
                seen_assets: set[str] = set()
                for b in q_imgs:
                    if b.get("type") != "image" or not b.get("asset"):
                        continue
                    if b["asset"] in seen_assets or is_decorative_image_block(b):
                        continue
                    seen_assets.add(b["asset"])
                    q_context.append(b)
            if stem:
                q_context.append({"type": "text", "text": stem, "role": "stem"})

        if not dir_text and q_context:
            dir_text = flatten_context_text(
                [b for b in q_context if b.get("role") != "stem"]
            ) or None

        status, issues = assess_context(
            stem=stem,
            options=options,
            direction_text=dir_text,
            context=q_context,
            q_num=q_num,
        )

        q = Question(
            q_id=make_q_id(paper_id, q_num),
            q_num=q_num,
            section=section,
            topic=None,
            topic_confidence=None,
            topic_source=None,
            direction_id=dir_id,
            direction_text=dir_text,
            stem=stem,
            options=options,
            answer=None,
            explanation=None,
            metrics=QuestionMetrics(
                has_passage=bool(dir_text or q_context),
                option_count=len(options),
                stem_char_len=len(stem),
                page_start=p_start,
                page_end=p_end,
            ),
            context=q_context,
            context_status=status,
            context_issues=issues,
        )
        questions.append(q)
        seen_nums.add(q_num)
        i += 1

    if not questions:
        notes.append("no_questions_parsed")
    return questions, notes


def coerce_year(value: Any) -> int | None:
    if value is None:
        return None
    try:
        y = int(str(value).strip())
    except ValueError:
        return None
    if 2000 <= y <= 2099:
        return y
    return None


def coerce_shift(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if s.startswith("_"):
        return None
    return s


def paper_out_path(out_root: Path, paper: Paper) -> Path:
    bank = paper.bank or "_unknown_bank"
    role = paper.role or "_unknown_role"
    year = str(paper.year) if paper.year is not None else "no_year"
    stage = paper.exam_type or "_unknown_stage"
    shift = paper.shift or "_unknown_shift"
    return out_root / bank / role / year / stage / shift / f"{paper.paper_id}.json"


def convert_pdf(
    pdf_path: Path,
    corpus: Path,
    out_root: Path,
    force: bool = False,
    *,
    taxonomy: dict[str, Any] | None = None,
    label_questions: bool = True,
) -> dict[str, Any]:
    meta = load_meta(pdf_path)
    if not meta:
        meta = meta_from_path(pdf_path, corpus)

    skip = should_skip(pdf_path, meta)
    rel_pdf = str(pdf_path.relative_to(corpus)).replace("\\", "/") if pdf_path.is_relative_to(corpus) else str(pdf_path)

    bank = meta.get("bank")
    role = meta.get("role")
    exam_type = meta.get("stage")
    year = coerce_year(meta.get("year"))
    shift = coerce_shift(meta.get("shift"))
    memory_based = bool(meta.get("memory_based"))
    language = meta.get("language") or "english"
    sha256 = meta.get("sha256")

    paper_id = make_paper_id(bank, role, year, exam_type, shift, sha256)
    out_path = paper_out_path(
        out_root,
        Paper(
            paper_id=paper_id,
            source={},
            bank=bank,
            role=role,
            exam_type=exam_type,
            year=year,
            shift=shift,
            memory_based=memory_based,
            language=language,
            parse_status="pending",
        ),
    )

    if skip:
        return {
            "status": "skipped",
            "reason": skip,
            "pdf": rel_pdf,
            "paper_id": paper_id,
            "question_count": 0,
        }

    if out_path.is_file() and not force:
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if existing.get("source", {}).get("sha256") and sha256 and existing["source"]["sha256"] == sha256:
                return {
                    "status": "cached",
                    "pdf": rel_pdf,
                    "paper_id": paper_id,
                    "question_count": existing.get("question_count")
                    or len(existing.get("questions") or []),
                    "out_path": str(out_path.relative_to(out_root)).replace("\\", "/"),
                }
        except (json.JSONDecodeError, OSError):
            pass

    try:
        from layout_parse import parse_pdf_layout

        layout = parse_pdf_layout(pdf_path, paper_id, out_root)
        questions = layout.questions
        notes = list(layout.notes)
        if layout.assets_exported:
            notes.append(f"assets_exported:{layout.assets_exported}")
    except Exception as exc:  # noqa: BLE001 — collect per-file failures
        log.exception("Failed parsing %s", pdf_path)
        paper = Paper(
            paper_id=paper_id,
            source={
                "pdf_path": f"corpus/{rel_pdf}" if not rel_pdf.startswith("corpus/") else rel_pdf,
                "sha256": sha256,
                "source_url": meta.get("source_url"),
                "source_filename": meta.get("source_filename") or pdf_path.name,
            },
            bank=bank,
            role=role,
            exam_type=exam_type,
            year=year,
            shift=shift,
            memory_based=memory_based,
            language=language,
            parse_status="failed",
            questions=[],
            parse_notes=[f"exception:{type(exc).__name__}:{exc}"],
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(paper.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "status": "failed",
            "pdf": rel_pdf,
            "paper_id": paper_id,
            "question_count": 0,
            "out_path": str(out_path.relative_to(out_root)).replace("\\", "/"),
            "notes": paper.parse_notes,
        }

    with_opts = sum(1 for q in questions if q.metrics.option_count >= 4)
    if not questions:
        status = "failed"
    elif with_opts < max(1, len(questions) // 3):
        status = "partial"
        notes.append(f"low_option_coverage:{with_opts}/{len(questions)}")
    else:
        status = "ok"

    paper = Paper(
        paper_id=paper_id,
        source={
            "pdf_path": f"corpus/{rel_pdf}",
            "sha256": sha256,
            "source_url": meta.get("source_url"),
            "source_filename": meta.get("source_filename") or pdf_path.name,
        },
        bank=bank,
        role=role,
        exam_type=exam_type,
        year=year,
        shift=shift,
        memory_based=memory_based,
        language=language,
        parse_status=status,
        questions=questions,
        parse_notes=notes,
    )

    paper_dict = paper.to_dict()
    from question_pipeline import load_taxonomy_cached, post_process_paper

    post_process_paper(
        paper_dict,
        taxonomy=taxonomy or load_taxonomy_cached(),
        label=label_questions,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(paper_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": status,
        "pdf": rel_pdf,
        "paper_id": paper_id,
        "question_count": len(questions),
        "with_options": with_opts,
        "out_path": str(out_path.relative_to(out_root)).replace("\\", "/"),
        "notes": notes,
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


def write_report(out_root: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    total_q = 0
    papers_with_q = 0
    for r in results:
        st = r.get("status") or "unknown"
        status_counts[st] = status_counts.get(st, 0) + 1
        qc = int(r.get("question_count") or 0)
        total_q += qc
        if qc > 0:
            papers_with_q += 1

    converted = [r for r in results if r.get("status") in {"ok", "partial", "failed", "cached"}]
    avg_q = (total_q / papers_with_q) if papers_with_q else 0.0

    report = {
        "papers_seen": len(results),
        "status_counts": status_counts,
        "total_questions_indexed_approx": total_q,
        "papers_with_questions": papers_with_q,
        "avg_questions_per_parsed_paper": round(avg_q, 2),
        "papers": [
            {
                "status": r.get("status"),
                "pdf": r.get("pdf"),
                "paper_id": r.get("paper_id"),
                "question_count": r.get("question_count"),
                "with_options": r.get("with_options"),
                "out_path": r.get("out_path"),
                "reason": r.get("reason"),
                "notes": r.get("notes"),
            }
            for r in results
        ],
    }
    (out_root / "parse_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def iter_pdfs(corpus: Path) -> list[Path]:
    return sorted(p for p in corpus.rglob("*.pdf") if p.is_file())


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="Convert corpus PDFs to enriched question JSON (parse + label + optional answers)"
    )
    p.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--limit", type=int, default=0, help="Max PDFs to process (0 = all)")
    p.add_argument("--force", action="store_true", help="Re-parse even if sha256 matches")
    p.add_argument("--pdf", action="append", default=[], help="Specific PDF path(s)")
    p.add_argument("--skip-labels", action="store_true", help="Skip section/topic labeling")
    p.add_argument("--skip-answers", action="store_true", help="Skip answer attachment after parse")
    args = p.parse_args(argv)

    corpus = Path(args.corpus)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    taxonomy = None
    if not args.skip_labels:
        from question_pipeline import load_taxonomy_cached

        taxonomy = load_taxonomy_cached()
    label_questions = not args.skip_labels

    if args.pdf:
        pdfs = [Path(x) for x in args.pdf]
    else:
        pdfs = iter_pdfs(corpus)
    if args.limit and args.limit > 0:
        pdfs = pdfs[: args.limit]

    log.info("Processing %s PDFs from %s", len(pdfs), corpus)
    results: list[dict[str, Any]] = []
    for idx, pdf in enumerate(pdfs, start=1):
        log.info("[%s/%s] %s", idx, len(pdfs), pdf.name)
        result = convert_pdf(
            pdf,
            corpus,
            out_root,
            force=args.force,
            taxonomy=taxonomy,
            label_questions=label_questions,
        )
        results.append(result)

    answer_report: dict[str, Any] | None = None
    if not args.skip_answers:
        from question_pipeline import attach_answers_to_bank

        log.info("Attaching answers…")
        answer_report = attach_answers_to_bank(out_root, corpus, limit=args.limit or 0)

    index_count = rebuild_index(out_root)
    report = write_report(out_root, results)
    report["index_rows"] = index_count
    if answer_report:
        report["answer_attachment"] = answer_report
    (out_root / "parse_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info(
        "Done. status=%s questions~=%s index_rows=%s",
        report["status_counts"],
        report["total_questions_indexed_approx"],
        index_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

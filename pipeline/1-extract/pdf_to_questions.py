"""
Convert bank exam PYQ PDFs in corpus/ into structured JSON under data/papers/.

Usually just run:

This file still works on its own if you want:
  python pdf_to_questions.py --limit 20
  python pdf_to_questions.py --force
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any


# step folders ("1-extract") are not valid module names, so shared code
# comes through lib/ rather than from another step
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import (  # noqa: F401  (re-exported for callers)
    HINDI_NAME_RE,
    SOLUTION_NAME_RE,
    build_full_text,
    clean_lines,
    load_meta,
    meta_from_path,
    rebuild_index,
)
from pdf import extract_pages  # noqa: F401
from context_completeness import (
    is_decorative_image_block,
    sanitize_question_context,
    should_synthesize_cloze_stem,
)
from page_stream import (
    flatten_context_text,
    items_for_char_range,
)
from question_schema import (
    Paper,
    Question,
    detect_section,
    make_direction_id,
    make_paper_id,
    make_q_id,
)

# tools/pdf_pipeline/ → repo root is two levels up
ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
DEFAULT_CORPUS = REPO_ROOT / "corpus" / "pdf"
DEFAULT_OUT = REPO_ROOT / "data" / "papers"

log = logging.getLogger("pdf_to_questions")

DIRECTION_RANGE_RE = re.compile(
    r"(?is)Directions?\s*\(\s*(\d+)\s*[-–—to]+\s*(\d+)\s*\)\s*:?\s*"
)
# Bare "Directions:" / "Directions : Answer the questions…"
DIRECTION_BARE_RE = re.compile(r"(?im)^\s*Directions?\s*:\s+")

# 1.  | 1)  | Q1.  | Q.1  | Q 1.  | Question 1:  | Question 1.  | Q32.<text-with-no-space>
#
# Trailing separator is `\s*`, not `\s+`: Indic-script typesetting (and some
# plain-English papers too) runs the stem straight on with no space after the
# period -- "Q32.\u0b92\u0bb0\u0bc1..." -- and requiring a space made every such question
# invisible. Measured: 115 questions recovered across 46 papers, 0 lost.
#
# First digit is `[1-9]`, not `\d`: once the space is no longer required, a
# bare "0." (a list marker, a footnote) would otherwise register as question 0.
#
# `(?!\d)` after the separator: without it, `\s*` matching zero spaces makes
# any decimal number at a line start read as a question anchor -- "30.2" on its
# own extracted line (a stacked-option value, one number per line, is normal
# layout in these PDFs) matches as "30." + digit "2", and the real question was
# cut into by that fake anchor. Caught in testing: q52 of one paper vanished
# because its own option list (27, 30.2, 23.8, 33.4, 20.6) tripped this. The
# lookahead rejects a digit right after the separator, so "30.2" is rejected
# while "Q32.\u0b92\u0bb0\u0bc1" (a letter follows) and "52. 27" (a space follows) still match.
QUESTION_START_RE = re.compile(
    r"(?im)^\s*(?:Question\s+|Q\s*\.?\s*)?([1-9]\d{0,2})\s*(?:[.):]|[\u0964])(?!\d)\s*"
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
    r"Copyright\s*©|www\.[a-z0-9.\-]+|"
    # Papers that print the answer inline right after a question's own options
    # ("Answer: D) \nSolution: \nN is the Admiral. \nHence, option d.") rather
    # than in a separate solutions section -- SOLUTIONS_CUT_RE only strips a
    # dedicated section, so this text has nowhere else to be caught and lands
    # inside the last option. Measured: option (e) carried the full explanation
    # as part of its text.
    r"Answer\s*:\s*[A-Ea-e]\)|Solution\s*:).*$",
    # DOTALL: the bleed text above is multi-line (a real newline after every
    # sentence), and without this flag `.` cannot cross those newlines, so
    # `.*$` could never reach the true end of the string -- the whole
    # alternation silently failed to match on any multi-line trailing text,
    # including the pre-existing Directions?/Question/Q\d+ cases, not just
    # this one. Caught because this fix's own regex tested correct in
    # isolation on single-line input but did nothing on the real multi-line
    # capture from the PDF.
    re.DOTALL,
)

# Keep old name as alias used in find_events
DIRECTION_RE = DIRECTION_RANGE_RE


SECTION_LINE_RE = re.compile(
    r"(?im)^\s*(REASONING(?:\s+ABILITY)?|QUANTITATIVE(?:\s+APTITUDE)?|"
    r"NUMERICAL\s+ABILITY|ENGLISH(?:\s+LANGUAGE)?|GENERAL\s+AWARENESS|"
    r"BANKING\s+AWARENESS|COMPUTER(?:\s+APTITUDE|\s+KNOWLEDGE)?)\s*$"
)






def should_skip(pdf_path: Path, meta: dict[str, Any]) -> str | None:
    name = pdf_path.name
    lang = (meta.get("language") or "").lower()
    if lang == "hindi" or HINDI_NAME_RE.search(name):
        return "hindi"
    if SOLUTION_NAME_RE.search(name):
        return "solutions_pdf"
    return None








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
        # NOTE: section_at() reads real headings out of the PDF, which beats
        # step 2's keyword guess. Question has no section field today, so this
        # is computed and dropped — wire it through when step 2 is ready.
        _section = section_at(ev["start"], section_spans)  # noqa: F841
        dir_id = None
        dir_text = None
        q_context: list[dict[str, Any]] = []
        if direction_covers(active_dir, q_num):
            dir_id = active_dir["id"]  # type: ignore[index]
            dir_text = active_dir["text"]  # type: ignore[index]
            if dir_text:
                q_context.append({"type": "text", "text": dir_text, "role": "direction"})
            if stream_items is not None:
                # FIXME(1-extract): computed then discarded — the call below
                # passes pages=None, so figure lookup is not scoped to this
                # question's pages. Possibly why 986 questions carry
                # has_image with no image_refs. Verify before deleting.
                q_pages = (p_start or 1, p_end or p_start or 1)  # noqa: F841
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

        # section/topic are step 2's, answer/explanation are step 4's, and the
        # schema has no metrics — Question carries only what step 1 can know.
        q = Question(
            q_id=make_q_id(paper_id, q_num),
            q_num=q_num,
            direction_id=dir_id,
            direction_text=dir_text,
            stem=stem,
            options=options,
            context=q_context,
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

        # Strip bleed/logos now, before Question.to_dict() reads context[] to
        # derive direction_image_refs, and copy the paper-level fields the
        # schema wants duplicated onto every question so it filters without a
        # join (see schema/schema.json).
        for q in questions:
            q.context = sanitize_question_context(
                direction_text=q.direction_text,
                stem=q.stem,
                context=q.context,
                q_num=q.q_num,
            )
            q.paper_id = paper_id
            q.bank = bank
            q.role = role
            q.exam_type = exam_type
            q.year = year
            q.shift = shift
            q.memory_based = memory_based
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

    with_opts = sum(1 for q in questions if len(q.options) >= 4)
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
    p.add_argument("--skip-answers", action="store_true", help="Skip answer attachment after parse")
    args = p.parse_args(argv)

    corpus = Path(args.corpus)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

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
        )
        results.append(result)

    index_count = rebuild_index(out_root)
    report = write_report(out_root, results)
    report["index_rows"] = index_count
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

"""
Infer and backfill question section labels.

Usage:
  python label_sections.py
  python label_sections.py --force   # overwrite existing sections
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
import sys
from pathlib import Path
from typing import Any

# step folders ("1-extract") are not valid module names, so shared code
# comes through lib/ rather than from another step
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import (
    DEFAULT_OUT,
    iter_paper_jsons,
    load_paper,
)

try:
    from label_topics import topic_implied_section
except ImportError:
    topic_implied_section = None  # type: ignore[assignment,misc]

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("label_sections")


def save_paper(path: Path, paper: dict[str, Any]) -> None:
    path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

PATH_CUES: list[tuple[str, re.Pattern[str]]] = [
    ("Quantitative", re.compile(r"\b(?:quant|quantitative|numerical|maths?|di)\b", re.I)),
    ("Reasoning", re.compile(r"\b(?:reasoning|puzzle)\b", re.I)),
    (
        "English",
        re.compile(
            r"\benglish[\s_\-]*(?:language|section|comprehension)\b|"
            r"(?:^|[/\\])english(?:[/\\]|$)",
            re.I,
        ),
    ),
    ("GA", re.compile(r"\b(?:ga|general[\s_\-]*awareness|banking[\s_\-]*awareness|current[\s_\-]*affairs)\b", re.I)),
    ("Computer", re.compile(r"\bcomputer\b", re.I)),
]

# Language-medium tags in filenames are not exam sections.
LANGUAGE_TAG_RE = re.compile(
    r"[-_/](?:english|eng|hindi|bengali)(?:[-_/]|\.pdf)|"
    r"\b(?:english|hindi)[\s_\-]*(?:memory|paper|mock|shift)\b",
    re.I,
)

# Known Prelims section order by bank/role (only used when layout is documented).
PRELIMS_BANDS: dict[str, list[tuple[int, int, str]]] = {
    "IBPS::PO::Prelims": [
        (1, 30, "English"),
        (31, 65, "Quantitative"),
        (66, 100, "Reasoning"),
    ],
    "IBPS::Clerk::Prelims": [
        (1, 30, "English"),
        (31, 65, "Quantitative"),
        (66, 100, "Reasoning"),
    ],
    "SBI::Clerk::Prelims": [
        (1, 30, "English"),
        (31, 65, "Quantitative"),
        (66, 100, "Reasoning"),
    ],
}

# SBI PO: 40/30/30 from 2024 onward; older papers use 30/35/35
SBI_PO_PRELIMS_LEGACY = [
    (1, 30, "English"),
    (31, 65, "Quantitative"),
    (66, 100, "Reasoning"),
]
SBI_PO_PRELIMS_2024 = [
    (1, 40, "English"),
    (41, 70, "Quantitative"),
    (71, 100, "Reasoning"),
]

# Keyword rules on direction_text + stem (order matters: first match wins within section groups)
TEXT_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "Reasoning",
        re.compile(
            r"(?i)\b("
            r"puzzle|seating|sitting|floor|box|stack|schedule|blood\s*relation|"
            r"syllogism|inequality|coding[\s\-]*decoding|input[\s\-]*output|"
            r"direction\s+(?:sense|test)|order\s+and\s+ranking|critical\s+reasoning|"
            r"statement\s+and\s+(?:assumption|conclusion|argument)|"
            r"eight\s+persons|certain\s+number\s+of\s+persons|"
            r"facing\s+(?:north|south|east|west)|circular\s+(?:row|table)"
            r")\b",
        ),
    ),
    (
        "Quantitative",
        re.compile(
            r"(?i)\b("
            r"pie\s+chart|bar\s+graph|line\s+graph|table\s+(?:shows|given)|"
            r"data\s+interpretation|simplification|approximation|"
            r"quadratic|number\s+series|wrong\s+number|"
            r"profit\s+and\s+loss|simple\s+interest|compound\s+interest|"
            r"time\s+and\s+work|time\s+(?:and|&)\s+distance|boat|"
            r"mixture|allegation|percentage|ratio\s+(?:and|&)\s+proportion|"
            r"average|mensuration|probability|permutation|"
            r"what\s+(?:approximate\s+)?value\s+will\s+come|"
            r"find\s+the\s+(?:total\s+)?(?:number|value|ratio|percentage)"
            r")\b",
        ),
    ),
    (
        "English",
        re.compile(
            r"(?i)\b("
            r"passage|reading\s+comprehension|cloze|"
            r"error\s+(?:spot|detection)|spot\s+the\s+error|"
            r"fill\s+in\s+the\s+blank|sentence\s+(?:improvement|rearrangement|correction)|"
            r"para\s*jumble|phrase\s+replacement|word\s+swap|"
            r"synonym|antonym|highlighted|"
            r"grammatically|contextually\s+correct"
            r")\b",
        ),
    ),
    (
        "GA",
        re.compile(
            r"(?i)\b("
            r"current\s+affairs|banking\s+awareness|who\s+is\s+the|"
            r"headquarters|RBI|SEBI|NABARD|monetary\s+policy|"
            r"budget|GDP|which\s+(?:bank|scheme|ministry)"
            r")\b",
        ),
    ),
    (
        "Computer",
        re.compile(
            r"(?i)\b("
            r"operating\s+system|MS[\s\-]?Excel|MS[\s\-]?Word|hardware|"
            r"software|network(ing)?|CPU|RAM|binary|protocol|HTML|"
            r"computer\s+(?:memory|virus|network)"
            r")\b",
        ),
    ),
]


def cue_from_text(text: str) -> str | None:
    cleaned = LANGUAGE_TAG_RE.sub(" ", text)
    for label, pat in PATH_CUES:
        if pat.search(cleaned):
            return label
    return None


def prelims_layout_key(paper: dict[str, Any]) -> str | None:
    bank = paper.get("bank")
    role = paper.get("role")
    exam_type = paper.get("exam_type")
    if not bank or not role or exam_type != "Prelims":
        return None
    return f"{bank}::{role}::Prelims"


def _prelims_bands_for_paper(paper: dict[str, Any]) -> list[tuple[int, int, str]] | None:
    key = prelims_layout_key(paper)
    if not key:
        return None
    if key == "SBI::PO::Prelims":
        year = paper.get("year")
        if year is not None and int(year) >= 2024:
            return SBI_PO_PRELIMS_2024
        return SBI_PO_PRELIMS_LEGACY
    return PRELIMS_BANDS.get(key)


def _topic_section_override(
    direction_text: str | None,
    stem: str | None,
    candidate_section: str | None,
    options: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """Prefer topic-implied section when q_num/keywords disagree with content."""
    if not topic_implied_section or not candidate_section:
        return candidate_section, None
    implied_sec, implied_topic = topic_implied_section(direction_text, stem, options)
    if not implied_sec or not implied_topic:
        return candidate_section, None
    if implied_sec == candidate_section:
        return candidate_section, None
    # Quant/Reas content should not stay in English bucket from q_num alone
    if candidate_section == "English" and implied_sec in ("Quantitative", "Reasoning"):
        return implied_sec, "topic_cross_section"
    # English error-spotting/cloze under wrong q_num band
    if candidate_section in ("Quantitative", "Reasoning") and implied_sec == "English":
        return implied_sec, "topic_cross_section"
    return candidate_section, None


def section_from_prelims_qnum(
    paper: dict[str, Any],
    q_num: int,
) -> tuple[str | None, str | None]:
    """Return section from known Prelims numbering when layout is documented."""
    if paper.get("exam_type") != "Prelims" or not isinstance(q_num, int):
        return None, None
    nqs = len(paper.get("questions") or [])
    if not (80 <= nqs <= 120):
        return None, None
    bands = _prelims_bands_for_paper(paper)
    if not bands:
        return None, None
    for lo, hi, sec in bands:
        if lo <= q_num <= hi:
            return sec, "prelims_qnum_range"
    return None, None


def infer_section_for_row(
    row: dict[str, Any],
    *,
    direction_text: str | None = None,
    question_count: int | None = None,
) -> tuple[str | None, str | None]:
    """Infer section from index-row fields (mock pool enrichment)."""
    if row.get("section"):
        return row["section"], "existing"

    blob = " ".join(
        filter(
            None,
            [row.get("pdf_path"), row.get("paper_id"), row.get("stem")],
        )
    )
    path_sec = cue_from_text(blob)
    if path_sec:
        return path_sec, "path_filename"

    text = " ".join(filter(None, [direction_text, row.get("stem")]))
    implied_sec, implied_topic = topic_implied_section(
        direction_text, row.get("stem"), row.get("options")
    ) if topic_implied_section else (None, None)
    if implied_sec and implied_topic:
        return implied_sec, "topic_keywords"

    kw = section_from_keywords(text)
    if kw:
        sec, src = _topic_section_override(direction_text, row.get("stem"), kw, row.get("options"))
        return sec or kw, src or "keywords"

    if row.get("exam_type") == "Prelims" and isinstance(row.get("q_num"), int):
        paper_stub = {
            "bank": row.get("bank"),
            "role": row.get("role"),
            "exam_type": row.get("exam_type"),
            "year": row.get("year"),
            "questions": [None] * (question_count or 100),
        }
        sec, src = section_from_prelims_qnum(paper_stub, int(row["q_num"]))
        if sec:
            final, osrc = _topic_section_override(
                direction_text, row.get("stem"), sec, row.get("options")
            )
            return final or sec, osrc or src

    return None, None


def section_from_keywords(text: str) -> str | None:
    for label, pat in TEXT_RULES:
        if pat.search(text):
            return label
    return None


def infer_section(paper: dict[str, Any], q: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (section, source)."""
    # 1) Already set
    if q.get("section"):
        return q["section"], "existing"

    # 2) Filename / path cues
    src = paper.get("source") or {}
    blob = " ".join(
        filter(
            None,
            [
                src.get("source_filename"),
                src.get("pdf_path"),
                paper.get("paper_id"),
            ],
        )
    )
    path_sec = cue_from_text(blob)
    if path_sec:
        return path_sec, "path_filename"

    # 3) Topic-implied section from content
    implied_sec, implied_topic = topic_implied_section(
        q.get("direction_text"), q.get("stem"), q.get("options")
    ) if topic_implied_section else (None, None)
    if implied_sec and implied_topic:
        return implied_sec, "topic_keywords"

    # 4) Keywords on direction + stem
    text = " ".join(filter(None, [q.get("direction_text"), q.get("stem")]))
    kw = section_from_keywords(text)
    if kw:
        sec, osrc = _topic_section_override(
            q.get("direction_text"), q.get("stem"), kw, q.get("options")
        )
        return sec or kw, osrc or "keywords"

    # 5) Prelims numbering only for documented layouts
    q_num = q.get("q_num")
    if isinstance(q_num, int):
        sec, src = section_from_prelims_qnum(paper, q_num)
        if sec:
            final, osrc = _topic_section_override(
                q.get("direction_text"), q.get("stem"), sec, q.get("options")
            )
            return final or sec, osrc or src

    return None, None


def propagate_direction_sections(paper: dict[str, Any], *, unify: bool = False) -> int:
    """
    Copy section across a direction group.

    Default: fill siblings that are missing a section.
    unify=True: force every sibling to the majority section (fixes mixed sets).
    """
    by_dir: dict[str, list[dict[str, Any]]] = {}
    for q in paper.get("questions") or []:
        did = q.get("direction_id")
        if did:
            by_dir.setdefault(did, []).append(q)
    filled = 0
    for _did, group in by_dir.items():
        secs = [q.get("section") for q in group if q.get("section")]
        if not secs:
            continue
        # majority section
        sec = Counter(secs).most_common(1)[0][0]
        for q in group:
            if not q.get("section"):
                q["section"] = sec
                q["section_source"] = "direction_propagate"
                filled += 1
            elif unify and q.get("section") != sec:
                q["section"] = sec
                q["section_source"] = "direction_unify"
                filled += 1
    return filled


def fill_neighbour_sections(paper: dict[str, Any]) -> int:
    """
    Fill missing section when both immediate neighbours agree.

    Banking papers run in section blocks (e.g. Q1–30 English). If Q45 is
    unlabelled and Q44/Q46 both say Reasoning, Q45 is Reasoning. Boundary
    questions (neighbours disagree or only one side labelled) stay empty.
    """
    qs = paper.get("questions") or []
    filled = 0
    for i, q in enumerate(qs):
        if q.get("section"):
            continue
        left = qs[i - 1] if i > 0 else None
        right = qs[i + 1] if i + 1 < len(qs) else None
        if not left or not right:
            continue
        left_sec = left.get("section")
        right_sec = right.get("section")
        if left_sec and right_sec and left_sec == right_sec:
            q["section"] = left_sec
            q["section_source"] = "neighbour"
            filled += 1
    return filled


def fill_neighbour_topics(paper: dict[str, Any], allowed_topics: set[str] | None = None) -> int:
    """Fill missing topic when both immediate neighbours share the same topic id."""
    qs = paper.get("questions") or []
    filled = 0
    for i, q in enumerate(qs):
        if q.get("topic"):
            continue
        left = qs[i - 1] if i > 0 else None
        right = qs[i + 1] if i + 1 < len(qs) else None
        if not left or not right:
            continue
        left_topic = left.get("topic")
        right_topic = right.get("topic")
        if not left_topic or left_topic != right_topic:
            continue
        if allowed_topics is not None and left_topic not in allowed_topics:
            continue
        # Prefer not to cross a section boundary even if topics match oddly
        left_sec = left.get("section")
        right_sec = right.get("section")
        if left_sec and right_sec and left_sec != right_sec:
            continue
        q["topic"] = left_topic
        q["topic_source"] = "neighbour"
        if not q.get("section") and left_sec and left_sec == right_sec:
            q["section"] = left_sec
            q["section_source"] = "neighbour"
        filled += 1
    return filled


def label_sections(out_root: Path, *, force: bool = False) -> dict[str, Any]:
    sources: Counter[str] = Counter()
    sections: Counter[str] = Counter()
    total = 0
    labelled = 0
    papers_touched = 0

    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        dirty = False
        for q in paper.get("questions") or []:
            total += 1
            if q.get("section") and not force:
                sources["existing"] += 1
                sections[str(q["section"])] += 1
                labelled += 1
                continue
            if force:
                q.pop("section", None)
                q.pop("section_source", None)

            sec, src = infer_section(paper, q)
            if sec:
                q["section"] = sec
                if src != "existing":
                    q["section_source"] = src
                sources[src or "unknown"] += 1
                sections[sec] += 1
                labelled += 1
                dirty = True
            else:
                sources["unlabelled"] += 1

        prop = propagate_direction_sections(paper)
        if prop:
            dirty = True
            sources["direction_propagate"] += prop
            labelled += prop
            # unlabelled was overcounted for those — adjust roughly
            sources["unlabelled"] = max(0, sources["unlabelled"] - prop)
            for q in paper.get("questions") or []:
                if q.get("section_source") == "direction_propagate":
                    sections[str(q["section"])] += 1

        n_sec = fill_neighbour_sections(paper)
        if n_sec:
            dirty = True
            sources["neighbour"] += n_sec
            labelled += n_sec
            sources["unlabelled"] = max(0, sources["unlabelled"] - n_sec)
            for q in paper.get("questions") or []:
                if q.get("section_source") == "neighbour":
                    sections[str(q["section"])] += 1

        if dirty:
            papers_touched += 1
            save_paper(path, paper)

    # Recount labelled accurately
    labelled = 0
    total = 0
    sections = Counter()
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        for q in paper.get("questions") or []:
            total += 1
            if q.get("section"):
                labelled += 1
                sections[str(q["section"])] += 1

    return {
        "questions": total,
        "labelled": labelled,
        "coverage_pct": round(100.0 * labelled / total, 2) if total else 0,
        "papers_touched": papers_touched,
        "by_source": dict(sources),
        "by_section": dict(sections),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Backfill section labels on question bank")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--force", action="store_true")
    p.add_argument("--all", action="store_true", help="Label entire bank (default: all papers)")
    args = p.parse_args(argv)

    out_root = Path(args.out)
    report = label_sections(out_root, force=args.force)
    report_path = out_root / "section_label_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", report_path)
    log.info("Coverage %s%% (%s/%s)", report["coverage_pct"], report["labelled"], report["questions"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Step 2 — classify.

Input:  step 1 output — corpus/papers/**/*.json
Output: the same files, with section / topic / difficulty / question_pattern filled.

Flow:
  corpus/pdf  ->  1-extract  ->  corpus/papers  ->  2-classify  ->  corpus/papers (labelled)

Also strips bilingual (Devanagari) text before labelling.
Audit fields stay in classify_report.json, not on the question.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
DEFAULT_SCHEMA = REPO / "schema" / "schema.json"
DEFAULT_TAXONOMY = ROOT / "topic_taxonomy.json"

# Allow running as `python run_classify.py` from this folder
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "lib"))

from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper  # noqa: E402

from classify import classify_question  # noqa: E402
from difficulty import infer_difficulty  # noqa: E402
from label_sections import infer_section, propagate_direction_sections  # noqa: E402
from label_topics import infer_labels, load_taxonomy  # noqa: E402
from strip_bilingual import strip_question_fields  # noqa: E402


def save_paper(path: Path, paper: dict[str, Any]) -> None:
    path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

log = logging.getLogger("run_classify")

# Pattern → topic hint when rules leave topic empty
PATTERN_TOPIC_HINT: dict[str, tuple[str, str]] = {
    "reading_comprehension_set": ("English", "Reading_Comprehension"),
    "cloze_passage_set": ("English", "Cloze_Test"),
    "table_di_set": ("Quantitative", "Data_Interpretation"),
    "visual_chart_graph_di": ("Quantitative", "Data_Interpretation"),
    "caselet_di_set": ("Quantitative", "Data_Interpretation"),
    "data_sufficiency": ("Quantitative", "Data_Sufficiency_Quant"),
    "quantity_comparison": ("Quantitative", "Arithmetic"),
    "quadratic_comparison": ("Quantitative", "Quadratic_Equation"),
    "match_the_columns": ("English", "Miscellaneous_English"),
}

AUDIT_KEYS = (
    "section_source",
    "topic_source",
    "topic_confidence",
)


def load_pattern_enum(schema_path: Path) -> set[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    props = schema.get("properties") or {}
    qp = props.get("question_pattern") or {}
    return set(qp.get("enum") or [])


def scrub_audit_fields(question: dict[str, Any]) -> None:
    for key in AUDIT_KEYS:
        question.pop(key, None)


def classify_paper(
    paper: dict[str, Any],
    *,
    force: bool,
    allowed_topics: set[str],
    pattern_enum: set[str],
) -> dict[str, Any]:
    """Mutate paper questions in place. Return per-paper audit stats."""
    stats: dict[str, Any] = {
        "questions": 0,
        "stripped_fields": 0,
        "section_sources": Counter(),
        "topic_sources": Counter(),
        "patterns": Counter(),
        "pattern_invalid": 0,
        "section_filled": 0,
        "topic_filled": 0,
        "difficulty_filled": 0,
    }

    for q in paper.get("questions") or []:
        stats["questions"] += 1

        # 1) Strip bilingual text first
        strip_counts = strip_question_fields(q)
        stats["stripped_fields"] += strip_counts["fields_changed"]

        # 2) Section (recompute when force)
        if force:
            q.pop("section", None)
            q.pop("section_source", None)
        if force or not q.get("section"):
            # clear so infer_section doesn't short-circuit on stale value
            q.pop("section", None)
            sec, src = infer_section(paper, q)
            if sec:
                q["section"] = sec
                stats["section_sources"][src or "unknown"] += 1
            else:
                stats["section_sources"]["unlabelled"] += 1
        else:
            stats["section_sources"]["existing"] += 1

        # 3) Topic
        if force:
            q.pop("topic", None)
            q.pop("topic_source", None)
            q.pop("topic_confidence", None)
        if force or not q.get("topic"):
            sec2, topic, conf, tsrc = infer_labels(
                q.get("section"),
                q.get("direction_text"),
                q.get("stem"),
                q.get("options"),
            )
            if sec2 and (force or not q.get("section") or tsrc in ("rules", "rules_cross_section")):
                q["section"] = sec2
            if topic and (not allowed_topics or topic in allowed_topics or topic.endswith("_Misc")):
                q["topic"] = topic
                stats["topic_sources"][tsrc] += 1
            else:
                stats["topic_sources"]["unlabelled"] += 1
        else:
            stats["topic_sources"]["existing"] += 1

    # 4) Propagate / unify section across direction sets
    propagate_direction_sections(paper, unify=True)

    # 5) Pattern + difficulty + pattern→topic hints
    for q in paper.get("questions") or []:
        primary, match, _secondary = classify_question(q, paper)
        pattern = primary.id
        if pattern_enum and pattern not in pattern_enum:
            stats["pattern_invalid"] += 1
            # fall back to safe enum member
            pattern = "shared_directions_set" if q.get("direction_id") else "standalone_mcq"
        q["question_pattern"] = pattern
        stats["patterns"][pattern] += 1

        # Topic hint from pattern if still missing
        if not q.get("topic") and pattern in PATTERN_TOPIC_HINT:
            sec_hint, topic_hint = PATTERN_TOPIC_HINT[pattern]
            if not allowed_topics or topic_hint in allowed_topics:
                q["topic"] = topic_hint
                if not q.get("section"):
                    q["section"] = sec_hint
                stats["topic_sources"]["pattern_hint"] += 1

        q["difficulty"] = infer_difficulty(q, paper)

        if q.get("section"):
            stats["section_filled"] += 1
        if q.get("topic"):
            stats["topic_filled"] += 1
        if q.get("difficulty") is not None:
            stats["difficulty_filled"] += 1

        # Schema: audit fields stay in the report only
        scrub_audit_fields(q)

    return stats


def direction_section_conflicts(paper: dict[str, Any]) -> int:
    groups: dict[str, set[str]] = defaultdict(set)
    for q in paper.get("questions") or []:
        did = q.get("direction_id")
        sec = q.get("section")
        if did and sec:
            groups[did].add(sec)
    return sum(1 for secs in groups.values() if len(secs) > 1)


def run(
    *,
    papers_dir: Path,
    taxonomy_path: Path,
    schema_path: Path,
    force: bool,
    limit_papers: int,
    dry_run: bool,
) -> dict[str, Any]:
    taxonomy = load_taxonomy(taxonomy_path)
    allowed_topics = {t for topics in (taxonomy.get("sections") or {}).values() for t in topics}
    pattern_enum = load_pattern_enum(schema_path)

    files = iter_paper_jsons(papers_dir)
    if limit_papers > 0:
        files = files[:limit_papers]

    totals = {
        "papers": 0,
        "papers_written": 0,
        "questions": 0,
        "stripped_fields": 0,
        "section_filled": 0,
        "topic_filled": 0,
        "difficulty_filled": 0,
        "pattern_invalid": 0,
        "direction_section_conflicts": 0,
    }
    section_sources: Counter[str] = Counter()
    topic_sources: Counter[str] = Counter()
    patterns: Counter[str] = Counter()
    sections: Counter[str] = Counter()
    topics: Counter[str] = Counter()

    for path in files:
        paper = load_paper(path)
        if not paper:
            continue
        totals["papers"] += 1
        stats = classify_paper(
            paper,
            force=force,
            allowed_topics=allowed_topics,
            pattern_enum=pattern_enum,
        )
        totals["questions"] += stats["questions"]
        totals["stripped_fields"] += stats["stripped_fields"]
        totals["section_filled"] += stats["section_filled"]
        totals["topic_filled"] += stats["topic_filled"]
        totals["difficulty_filled"] += stats["difficulty_filled"]
        totals["pattern_invalid"] += stats["pattern_invalid"]
        totals["direction_section_conflicts"] += direction_section_conflicts(paper)
        section_sources.update(stats["section_sources"])
        topic_sources.update(stats["topic_sources"])
        patterns.update(stats["patterns"])
        for q in paper.get("questions") or []:
            if q.get("section"):
                sections[str(q["section"])] += 1
            if q.get("topic"):
                topics[str(q["topic"])] += 1

        if not dry_run:
            save_paper(path, paper)
            totals["papers_written"] += 1

    qn = totals["questions"] or 1
    report = {
        "papers_dir": str(papers_dir.as_posix()),
        "force": force,
        "dry_run": dry_run,
        "totals": totals,
        "coverage": {
            "section_pct": round(100.0 * totals["section_filled"] / qn, 2),
            "topic_pct": round(100.0 * totals["topic_filled"] / qn, 2),
            "difficulty_pct": round(100.0 * totals["difficulty_filled"] / qn, 2),
            "pattern_pct": 100.0 if qn else 0.0,
        },
        "section_sources": dict(section_sources.most_common()),
        "topic_sources": dict(topic_sources.most_common()),
        "patterns": dict(patterns.most_common()),
        "sections": dict(sections.most_common()),
        "topics": dict(topics.most_common()),
        "pattern_enum_size": len(pattern_enum),
        "done_when": {
            "section_topic_above_90": totals["section_filled"] / qn >= 0.9
            and totals["topic_filled"] / qn >= 0.9,
            "no_invalid_patterns": totals["pattern_invalid"] == 0,
            "no_direction_section_conflicts": totals["direction_section_conflicts"] == 0,
        },
    }
    return report


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Step 2 classify: section/topic/difficulty/pattern")
    p.add_argument(
        "--papers-dir",
        type=Path,
        default=DEFAULT_OUT,
        help="Step 1 output directory (default: corpus/papers)",
    )
    p.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    p.add_argument("--force", action="store_true", help="Recompute labels even if already set")
    p.add_argument("--limit-papers", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Where to write classify_report.json (default: <papers-dir>/classify_report.json)",
    )
    args = p.parse_args(argv)

    if not args.papers_dir.exists():
        log.error("papers dir missing: %s", args.papers_dir)
        log.error("This is step 1's output. Run 1-extract first, or restore:")
        log.error("  git checkout ae12d7b -- corpus/papers")
        return 1

    paper_files = iter_paper_jsons(args.papers_dir)
    if not paper_files:
        log.error("No paper JSON under %s — step 1 has not produced input yet.", args.papers_dir)
        return 1

    report = run(
        papers_dir=args.papers_dir,
        taxonomy_path=args.taxonomy,
        schema_path=args.schema,
        force=args.force,
        limit_papers=args.limit_papers,
        dry_run=args.dry_run,
    )
    report_path = args.report or (args.papers_dir / "classify_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cov = report["coverage"]
    tot = report["totals"]
    log.info(
        "papers=%s questions=%s section=%.1f%% topic=%.1f%% difficulty=%.1f%%",
        tot["papers"],
        tot["questions"],
        cov["section_pct"],
        cov["topic_pct"],
        cov["difficulty_pct"],
    )
    log.info("wrote %s", report_path)
    log.info("done_when %s", report["done_when"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

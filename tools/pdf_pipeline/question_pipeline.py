"""Post-parse enrichment: context sanitize, completeness, section/topic labels."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from context_completeness import assess_context, is_decorative_image_block, sanitize_question_context
from label_topics import infer_labels, load_taxonomy

ROOT = Path(__file__).resolve().parent
DEFAULT_TAXONOMY = ROOT / "topic_taxonomy.json"
log = logging.getLogger("question_pipeline")


def finalize_question(q: dict[str, Any]) -> None:
    """Sanitize context blocks and re-assess completeness for one question."""
    q["context"] = sanitize_question_context(
        direction_text=q.get("direction_text"),
        stem=q.get("stem") or "",
        context=q.get("context"),
        q_num=q.get("q_num"),
    )
    status, issues = assess_context(
        stem=q.get("stem") or "",
        options=q.get("options") or {},
        direction_text=q.get("direction_text"),
        context=q.get("context"),
        q_num=q.get("q_num"),
    )
    q["context_status"] = status
    q["context_issues"] = issues


def label_paper_questions(paper: dict[str, Any], *, taxonomy: dict[str, Any] | None = None) -> None:
    """Infer section + topic for every question in a paper."""
    from label_sections import infer_section, propagate_direction_sections

    propagate_direction_sections(paper)

    allowed: set[str] = set()
    if taxonomy:
        allowed = {t for topics in (taxonomy.get("sections") or {}).values() for t in topics}

    for q in paper.get("questions") or []:
        sec, src = infer_section(paper, q)
        if sec:
            q["section"] = sec
            q["section_source"] = src

        sec2, topic, conf, tsrc = infer_labels(
            q.get("section"),
            q.get("direction_text"),
            q.get("stem"),
            q.get("options"),
        )
        if sec2 and tsrc in ("rules", "rules_cross_section"):
            q["section"] = sec2
            if tsrc == "rules_cross_section":
                q["section_source"] = "topic_cross_section"
        if topic:
            if topic not in allowed and allowed:
                tsrc = f"{tsrc}_off_taxonomy"
            q["topic"] = topic
            q["topic_confidence"] = conf
            q["topic_source"] = tsrc


def post_process_paper(
    paper: dict[str, Any],
    *,
    taxonomy: dict[str, Any] | None = None,
    label: bool = True,
) -> dict[str, Any]:
    """Run all enrichment steps on a parsed paper dict (in place)."""
    for q in paper.get("questions") or []:
        finalize_question(q)
    if label:
        label_paper_questions(paper, taxonomy=taxonomy)
    return paper


def load_taxonomy_cached(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_TAXONOMY
    return load_taxonomy(path)


def attach_answers_to_bank(
    out_root: Path,
    corpus: Path,
    *,
    limit: int = 0,
    skip_same_pdf: bool = False,
    skip_solutions: bool = False,
) -> dict[str, Any]:
    """Attach answers from question + solutions PDFs, then backfill confidence."""
    from attach_answers import (
        attach_from_same_pdfs,
        attach_from_solutions_pdfs,
        backfill_answer_confidence,
        count_answers,
    )

    before = count_answers(out_root)
    same_stats: dict[str, Any] = {}
    sol_stats: dict[str, Any] = {}

    if not skip_same_pdf:
        log.info("Attaching answers from same PDFs…")
        same_stats = attach_from_same_pdfs(out_root, corpus, limit=limit)

    if not skip_solutions:
        log.info("Attaching answers from solutions PDFs…")
        sol_stats = attach_from_solutions_pdfs(out_root, corpus, limit=limit)

    conf_stats = backfill_answer_confidence(out_root)
    after = count_answers(out_root)

    return {
        "before": before,
        "after": after,
        "same_pdf": same_stats,
        "solutions": sol_stats,
        "confidence": conf_stats,
    }

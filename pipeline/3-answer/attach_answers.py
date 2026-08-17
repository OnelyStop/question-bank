"""
Attach answers/explanations to question_bank JSON by question number.

Sources:
  1. Same PDF as the questions (embedded S#. Ans.(x) / N. (x); blocks)
  2. Separate solutions PDFs (filename contains 'solution'), paired to papers

Usage:
  python attach_answers.py
  python attach_answers.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

from pdf_to_questions import (
    DEFAULT_CORPUS,
    DEFAULT_OUT,
    SOLUTION_NAME_RE,
    HINDI_NAME_RE,
    build_full_text,
    extract_pages,
    load_meta,
    meta_from_path,
    rebuild_index,
)

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("attach_answers")

# S1. Ans.(a)  |  S48. Ans. (e)  |  S1.Ans.(a)
ANS_S_RE = re.compile(
    r"(?is)(?<!\w)S\s*(\d{1,3})\s*\.\s*Ans\s*\.\s*\(?\s*([a-eA-E])\s*\)?"
)

# 56. (e);  |  1. (d);
ANS_N_SEMI_RE = re.compile(
    r"(?m)^\s*(\d{1,3})\s*[\.\)]\s*\(\s*([a-eA-E])\s*\)\s*;"
)

SOL_STRIP_RE = re.compile(
    r"(?i)[\s_\-]*(?:solutions?|sol|answer[\s_\-]*key|with[\s_\-]*answers?)[\s_\-]*"
)

SECTION_CUES: list[tuple[str, re.Pattern[str]]] = [
    ("Quantitative", re.compile(r"\b(?:quant|quantitative|numerical|maths?|di)\b", re.I)),
    ("Reasoning", re.compile(r"\b(?:reasoning|puzzle)\b", re.I)),
    ("English", re.compile(r"\b(?:english|eng)\b", re.I)),
    ("GA", re.compile(r"\b(?:ga|general[\s_\-]*awareness|banking[\s_\-]*awareness|current)\b", re.I)),
    ("Computer", re.compile(r"\bcomputer\b", re.I)),
]


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_answer_map(text: str) -> dict[int, dict[str, Any]]:
    """
    Build {q_num: {"answer", "explanation", "pattern"}} from PDF text.

    Prefer S#. Ans.(x) when both patterns hit the same number (later wins by position).
    """
    # start, end, letter, q_num, pattern
    anchors: list[tuple[int, int, str, int, str]] = []

    for m in ANS_S_RE.finditer(text):
        q_num = int(m.group(1))
        letter = m.group(2).lower()
        if 1 <= q_num <= 200 and letter in "abcde":
            anchors.append((m.start(), m.end(), letter, q_num, "s_ans"))

    for m in ANS_N_SEMI_RE.finditer(text):
        q_num = int(m.group(1))
        letter = m.group(2).lower()
        if 1 <= q_num <= 200 and letter in "abcde":
            anchors.append((m.start(), m.end(), letter, q_num, "n_semi"))

    if not anchors:
        return {}

    anchors.sort(key=lambda a: a[0])

    by_num: dict[int, dict[str, Any]] = {}
    for i, (start, end, letter, q_num, pattern) in enumerate(anchors):
        next_start = anchors[i + 1][0] if i + 1 < len(anchors) else len(text)
        body = text[end:next_start]
        body = re.sub(r"(?is)^\s*Sol\s*\.?\s*", "", body)
        explanation = normalize_ws(body) or None
        if explanation and len(explanation) > 4000:
            explanation = explanation[:4000].rstrip() + "…"
        by_num[q_num] = {
            "answer": letter,
            "explanation": explanation,
            "pattern": pattern,
        }

    return by_num


def score_answer_confidence(
    *,
    source_label: str,
    pattern: str | None,
    has_explanation: bool,
    answer_in_options: bool,
    had_conflict: bool = False,
) -> float:
    """0–1 confidence that the attached answer key is correct for this q_num."""
    if not answer_in_options:
        return 0.2
    if had_conflict:
        return 0.55

    if source_label.startswith("solutions_pdf"):
        base = 0.85
    elif pattern == "s_ans":
        base = 0.95
    elif pattern == "n_semi":
        base = 0.90
    else:
        base = 0.85

    if has_explanation:
        base = min(0.98, base + 0.02)
    return round(base, 2)


def resolve_pdf_path(paper: dict[str, Any], corpus: Path) -> Path | None:
    src = (paper.get("source") or {}).get("pdf_path") or ""
    rel = src
    if rel.startswith("corpus/") or rel.startswith("corpus\\"):
        rel = rel[7:]
    path = corpus / rel
    if path.is_file():
        return path
    return None


def apply_map_to_paper(
    paper: dict[str, Any],
    answer_map: dict[int, dict[str, Any]],
    *,
    source_label: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fill answer/explanation/confidence on questions. Returns stats + conflicts."""
    filled = 0
    explanations = 0
    conflicts: list[dict[str, Any]] = []
    for q in paper.get("questions") or []:
        q_num = q.get("q_num")
        if q_num not in answer_map:
            continue
        info = answer_map[q_num]
        new_ans = info.get("answer")
        new_exp = info.get("explanation")
        pattern = info.get("pattern")
        old_ans = q.get("answer")
        opts = q.get("options") or {}

        if old_ans and new_ans and old_ans != new_ans and not overwrite:
            conflicts.append(
                {
                    "q_num": q_num,
                    "kept": old_ans,
                    "rejected": new_ans,
                    "source": source_label,
                }
            )
            # Keep old answer but lower confidence due to conflict
            if old_ans in opts:
                q["answer_confidence"] = score_answer_confidence(
                    source_label=str(q.get("answer_source") or "same_pdf"),
                    pattern=None,
                    has_explanation=bool(q.get("explanation") or new_exp),
                    answer_in_options=True,
                    had_conflict=True,
                )
            if not q.get("explanation") and new_exp:
                q["explanation"] = new_exp
                explanations += 1
            continue

        if overwrite or not old_ans:
            if new_ans:
                q["answer"] = new_ans
                q["answer_source"] = source_label
                q["answer_confidence"] = score_answer_confidence(
                    source_label=source_label,
                    pattern=pattern if isinstance(pattern, str) else None,
                    has_explanation=bool(new_exp or q.get("explanation")),
                    answer_in_options=new_ans in opts,
                )
                filled += 1
        elif old_ans and q.get("answer_confidence") is None:
            # Refresh confidence metadata if missing
            q["answer_source"] = q.get("answer_source") or source_label
            q["answer_confidence"] = score_answer_confidence(
                source_label=str(q.get("answer_source") or source_label),
                pattern=pattern if isinstance(pattern, str) else None,
                has_explanation=bool(q.get("explanation") or new_exp),
                answer_in_options=old_ans in opts,
            )

        if (overwrite or not q.get("explanation")) and new_exp:
            q["explanation"] = new_exp
            explanations += 1
            # bump confidence slightly if we just added explanation
            if q.get("answer") and q.get("answer") in opts and not (
                old_ans and new_ans and old_ans != new_ans
            ):
                q["answer_confidence"] = score_answer_confidence(
                    source_label=str(q.get("answer_source") or source_label),
                    pattern=pattern if isinstance(pattern, str) else None,
                    has_explanation=True,
                    answer_in_options=True,
                )
    return {"filled": filled, "explanations": explanations, "conflicts": conflicts}


def iter_paper_jsons(out_root: Path) -> list[Path]:
    skip = {"parse_report.json", "answer_attach_report.json", "question_bank.schema.json"}
    paths = []
    for path in sorted(out_root.rglob("*.json")):
        if path.name in skip or path.name.endswith(".meta.json"):
            continue
        if path.name == "SCHEMA.md":
            continue
        paths.append(path)
    return paths


def load_paper(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if "questions" not in data or "paper_id" not in data:
        return None
    return data


def section_cue_from_name(name: str) -> str | None:
    for label, pat in SECTION_CUES:
        if pat.search(name):
            return label
    return None


def normalize_stem_for_pair(filename: str) -> str:
    stem = Path(filename).stem
    stem = SOL_STRIP_RE.sub(" ", stem)
    stem = re.sub(r"[\s_\-]+", " ", stem).strip().lower()
    return stem


def list_solutions_pdfs(corpus: Path) -> list[Path]:
    out = []
    for pdf in sorted(corpus.rglob("*.pdf")):
        if HINDI_NAME_RE.search(pdf.name):
            continue
        if SOLUTION_NAME_RE.search(pdf.name):
            out.append(pdf)
    return out


def build_paper_index(papers: list[tuple[Path, dict[str, Any]]]) -> dict[str, list[tuple[Path, dict[str, Any]]]]:
    """Index papers by bank|role|year|exam_type for fallback pairing."""
    idx: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for path, paper in papers:
        key = "|".join(
            [
                str(paper.get("bank") or ""),
                str(paper.get("role") or ""),
                str(paper.get("year") or ""),
                str(paper.get("exam_type") or ""),
            ]
        )
        idx.setdefault(key, []).append((path, paper))
    return idx


def find_sibling_question_pdf(sol_pdf: Path, corpus: Path) -> Path | None:
    """Prefer a non-solution PDF in the same folder with similar stem."""
    sol_norm = normalize_stem_for_pair(sol_pdf.name)
    candidates = []
    for sib in sol_pdf.parent.iterdir():
        if not sib.is_file() or sib.suffix.lower() != ".pdf":
            continue
        if SOLUTION_NAME_RE.search(sib.name):
            continue
        if HINDI_NAME_RE.search(sib.name):
            continue
        sib_norm = normalize_stem_for_pair(sib.name)
        # Exact after strip, or one contains the other
        if sol_norm and sib_norm and (sol_norm == sib_norm or sol_norm in sib_norm or sib_norm in sol_norm):
            candidates.append((0, sib))
            continue
        # Token overlap
        sol_toks = set(sol_norm.split())
        sib_toks = set(sib_norm.split())
        if not sol_toks or not sib_toks:
            continue
        overlap = len(sol_toks & sib_toks) / max(len(sol_toks), len(sib_toks))
        if overlap >= 0.5:
            candidates.append((1 - overlap, sib))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def paper_path_for_pdf(
    pdf_path: Path,
    corpus: Path,
    papers_by_source: dict[str, tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]] | None:
    try:
        rel = str(pdf_path.relative_to(corpus)).replace("\\", "/")
    except ValueError:
        rel = pdf_path.name
    key = f"corpus/{rel}"
    if key in papers_by_source:
        return papers_by_source[key]
    # Also try bare relative
    if rel in papers_by_source:
        return papers_by_source[rel]
    # Match by source_filename
    name = pdf_path.name
    for _k, (ppath, paper) in papers_by_source.items():
        src_name = (paper.get("source") or {}).get("source_filename")
        if src_name == name:
            return ppath, paper
    return None


def pair_solutions_to_paper(
    sol_pdf: Path,
    corpus: Path,
    papers_by_source: dict[str, tuple[Path, dict[str, Any]]],
    papers_by_meta: dict[str, list[tuple[Path, dict[str, Any]]]],
) -> tuple[Path, dict[str, Any]] | None:
    sibling = find_sibling_question_pdf(sol_pdf, corpus)
    if sibling:
        hit = paper_path_for_pdf(sibling, corpus, papers_by_source)
        if hit:
            return hit

    meta = load_meta(sol_pdf) or meta_from_path(sol_pdf, corpus)
    bank = meta.get("bank")
    role = meta.get("role")
    year = meta.get("year")
    stage = meta.get("stage")
    key = "|".join([str(bank or ""), str(role or ""), str(year or ""), str(stage or "")])
    candidates = papers_by_meta.get(key) or []
    if not candidates:
        # Try without stage
        key2 = "|".join([str(bank or ""), str(role or ""), str(year or ""), ""])
        for k, lst in papers_by_meta.items():
            if k.startswith(key2.rstrip("|")) or k.rsplit("|", 1)[0] == key2.rstrip("|"):
                # weaker: bank|role|year match
                parts = k.split("|")
                if parts[0] == str(bank or "") and parts[1] == str(role or "") and parts[2] == str(year or ""):
                    candidates.extend(lst)

    if not candidates:
        return None

    cue = section_cue_from_name(sol_pdf.name)
    if cue:
        sectioned = []
        for ppath, paper in candidates:
            qs = paper.get("questions") or []
            if any(q.get("section") == cue for q in qs):
                sectioned.append((ppath, paper))
            # Also prefer papers whose source filename has same section cue
            src_name = (paper.get("source") or {}).get("source_filename") or ""
            if section_cue_from_name(src_name) == cue:
                return ppath, paper
        if sectioned:
            return sectioned[0]

    # Prefer paper with most questions missing answers that this sol could fill
    return candidates[0]


def attach_from_same_pdfs(
    out_root: Path,
    corpus: Path,
    limit: int = 0,
) -> dict[str, Any]:
    results = {
        "papers_touched": 0,
        "answers_filled": 0,
        "explanations_filled": 0,
        "conflicts": [],
        "missing_pdf": [],
        "no_answers_found": [],
        "details": [],
    }
    paths = iter_paper_jsons(out_root)
    count = 0
    for path in paths:
        paper = load_paper(path)
        if not paper:
            continue
        if paper.get("parse_status") not in {"ok", "partial"}:
            continue
        count += 1
        if limit and count > limit:
            break
        pdf = resolve_pdf_path(paper, corpus)
        if not pdf:
            results["missing_pdf"].append(paper.get("paper_id"))
            continue
        try:
            pages = extract_pages(pdf)
            text, _spans = build_full_text(pages)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed reading %s: %s", pdf, exc)
            results["missing_pdf"].append(paper.get("paper_id"))
            continue
        amap = extract_answer_map(text)
        if not amap:
            results["no_answers_found"].append(
                {"paper_id": paper.get("paper_id"), "pdf": str(pdf.relative_to(corpus)).replace("\\", "/")}
            )
            continue
        stats = apply_map_to_paper(paper, amap, source_label="same_pdf", overwrite=False)
        if stats["filled"] or stats["explanations"]:
            path.write_text(json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")
            results["papers_touched"] += 1
            results["answers_filled"] += stats["filled"]
            results["explanations_filled"] += stats["explanations"]
            results["details"].append(
                {
                    "paper_id": paper.get("paper_id"),
                    "source": "same_pdf",
                    "map_size": len(amap),
                    "filled": stats["filled"],
                    "explanations": stats["explanations"],
                }
            )
        if stats["conflicts"]:
            results["conflicts"].extend(
                [{"paper_id": paper.get("paper_id"), **c} for c in stats["conflicts"]]
            )
    return results


def attach_from_solutions_pdfs(
    out_root: Path,
    corpus: Path,
    limit: int = 0,
) -> dict[str, Any]:
    results: dict[str, Any] = {
        "solutions_seen": 0,
        "matched": [],
        "unmatched": [],
        "answers_filled": 0,
        "explanations_filled": 0,
        "conflicts": [],
    }

    # Load all papers into memory for pairing
    papers: list[tuple[Path, dict[str, Any]]] = []
    papers_by_source: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        if paper.get("parse_status") not in {"ok", "partial", "failed"}:
            continue
        papers.append((path, paper))
        src = (paper.get("source") or {}).get("pdf_path") or ""
        if src:
            papers_by_source[src.replace("\\", "/")] = (path, paper)

    papers_by_meta = build_paper_index(papers)
    sols = list_solutions_pdfs(corpus)
    if limit:
        sols = sols[:limit]

    # Keep mutable paper objects keyed by paper_id so multiple sol PDFs can merge
    paper_objs: dict[str, tuple[Path, dict[str, Any]]] = {
        p["paper_id"]: (path, p) for path, p in papers if p.get("paper_id")
    }

    for sol in sols:
        results["solutions_seen"] += 1
        try:
            pages = extract_pages(sol)
            text, _ = build_full_text(pages)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed reading sol %s: %s", sol, exc)
            results["unmatched"].append(
                {
                    "pdf": str(sol.relative_to(corpus)).replace("\\", "/"),
                    "reason": f"read_error:{exc}",
                }
            )
            continue
        amap = extract_answer_map(text)
        if not amap:
            results["unmatched"].append(
                {
                    "pdf": str(sol.relative_to(corpus)).replace("\\", "/"),
                    "reason": "no_answers_parsed",
                }
            )
            continue

        pair = pair_solutions_to_paper(sol, corpus, papers_by_source, papers_by_meta)
        if not pair:
            results["unmatched"].append(
                {
                    "pdf": str(sol.relative_to(corpus)).replace("\\", "/"),
                    "reason": "no_paper_match",
                    "map_size": len(amap),
                }
            )
            continue

        ppath, paper = pair
        pid = paper.get("paper_id")
        # Use live object if we already mutated it
        if pid in paper_objs:
            ppath, paper = paper_objs[pid]

        stats = apply_map_to_paper(
            paper,
            amap,
            source_label=f"solutions_pdf:{sol.name}",
            overwrite=False,  # keep same-PDF answers on conflict
        )
        paper_objs[pid] = (ppath, paper)
        ppath.write_text(json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")
        results["answers_filled"] += stats["filled"]
        results["explanations_filled"] += stats["explanations"]
        results["matched"].append(
            {
                "solutions_pdf": str(sol.relative_to(corpus)).replace("\\", "/"),
                "paper_id": pid,
                "paper_path": str(ppath.relative_to(out_root)).replace("\\", "/"),
                "map_size": len(amap),
                "filled": stats["filled"],
                "explanations": stats["explanations"],
            }
        )
        if stats["conflicts"]:
            results["conflicts"].extend(
                [
                    {
                        "paper_id": pid,
                        "solutions_pdf": sol.name,
                        **c,
                    }
                    for c in stats["conflicts"]
                ]
            )

    return results


def count_answers(out_root: Path) -> dict[str, Any]:
    total = 0
    with_ans = 0
    with_exp = 0
    conf_sum = 0.0
    conf_n = 0
    buckets = {"ge_0.9": 0, "ge_0.8": 0, "ge_0.5": 0, "lt_0.5": 0, "missing": 0}
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        for q in paper.get("questions") or []:
            total += 1
            if q.get("explanation"):
                with_exp += 1
            if not q.get("answer"):
                continue
            with_ans += 1
            conf = q.get("answer_confidence")
            if conf is None:
                buckets["missing"] += 1
                continue
            conf_sum += float(conf)
            conf_n += 1
            if conf >= 0.9:
                buckets["ge_0.9"] += 1
            elif conf >= 0.8:
                buckets["ge_0.8"] += 1
            elif conf >= 0.5:
                buckets["ge_0.5"] += 1
            else:
                buckets["lt_0.5"] += 1
    return {
        "questions": total,
        "with_answer": with_ans,
        "with_explanation": with_exp,
        "answer_coverage_pct": round(100.0 * with_ans / total, 2) if total else 0,
        "avg_answer_confidence": round(conf_sum / conf_n, 3) if conf_n else None,
        "confidence_buckets": buckets,
    }


def backfill_answer_confidence(out_root: Path) -> dict[str, Any]:
    """Set answer_confidence / answer_source on existing answers that lack them."""
    conflict_keys: set[tuple[str, int]] = set()
    attach_path = out_root / "answer_attach_report.json"
    if attach_path.is_file():
        try:
            ar = json.loads(attach_path.read_text(encoding="utf-8"))
            for c in (ar.get("solutions_pdfs") or {}).get("conflicts") or []:
                pid = c.get("paper_id")
                qn = c.get("q_num")
                if pid is not None and qn is not None:
                    conflict_keys.add((str(pid), int(qn)))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    updated = 0
    papers_touched = 0
    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        dirty = False
        pid = str(paper.get("paper_id") or "")
        for q in paper.get("questions") or []:
            ans = q.get("answer")
            if not ans:
                q.pop("answer_confidence", None)
                continue
            if q.get("answer_confidence") is not None and q.get("answer_source"):
                continue
            opts = q.get("options") or {}
            in_opts = ans in opts
            src = q.get("answer_source") or "legacy_attach"
            had_conflict = (pid, int(q.get("q_num") or -1)) in conflict_keys
            # Infer pattern for scoring when we only have legacy metadata
            pattern = None
            if src == "same_pdf" or src == "legacy_attach":
                pattern = "s_ans" if q.get("explanation") else "n_semi"
            elif src.startswith("solutions_pdf"):
                pattern = "s_ans" if q.get("explanation") else None
            q["answer_source"] = src
            q["answer_confidence"] = score_answer_confidence(
                source_label=src if src.startswith("solutions_pdf") else ("same_pdf" if src in {"same_pdf", "legacy_attach"} else src),
                pattern=pattern,
                has_explanation=bool(q.get("explanation")),
                answer_in_options=in_opts,
                had_conflict=had_conflict,
            )
            updated += 1
            dirty = True
        if dirty:
            papers_touched += 1
            path.write_text(json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")

    index_rows = rebuild_index(out_root)
    return {
        "questions_updated": updated,
        "papers_touched": papers_touched,
        "index_rows": index_rows,
        "stats": count_answers(out_root),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Attach answers to question bank by q_num")
    p.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--limit", type=int, default=0, help="Limit papers / sol PDFs for smoke tests")
    p.add_argument("--skip-same-pdf", action="store_true")
    p.add_argument("--skip-solutions", action="store_true")
    p.add_argument(
        "--backfill-confidence-only",
        action="store_true",
        help="Only set answer_confidence on existing answers; do not re-parse PDFs",
    )
    args = p.parse_args(argv)

    corpus = Path(args.corpus)
    out_root = Path(args.out)

    if args.backfill_confidence_only:
        result = backfill_answer_confidence(out_root)
        report_path = out_root / "answer_confidence_report.json"
        report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Backfilled confidence: %s", result["stats"])
        log.info("Wrote %s", report_path)
        return 0

    before = count_answers(out_root)
    log.info("Before: %s", before)

    same_stats: dict[str, Any] = {}
    sol_stats: dict[str, Any] = {}

    if not args.skip_same_pdf:
        log.info("Attaching answers from same PDFs…")
        same_stats = attach_from_same_pdfs(out_root, corpus, limit=args.limit)
        log.info(
            "Same-PDF: papers=%s answers=%s explanations=%s",
            same_stats["papers_touched"],
            same_stats["answers_filled"],
            same_stats["explanations_filled"],
        )

    if not args.skip_solutions:
        log.info("Attaching answers from solutions PDFs…")
        sol_stats = attach_from_solutions_pdfs(out_root, corpus, limit=args.limit)
        log.info(
            "Solutions: matched=%s unmatched=%s answers=%s",
            len(sol_stats.get("matched") or []),
            len(sol_stats.get("unmatched") or []),
            sol_stats.get("answers_filled"),
        )

    # Ensure every attached answer has confidence
    backfill = backfill_answer_confidence(out_root)

    index_rows = rebuild_index(out_root)
    after = count_answers(out_root)

    report = {
        "before": before,
        "after": after,
        "index_rows": index_rows,
        "confidence_backfill": backfill,
        "same_pdf": {
            "papers_touched": same_stats.get("papers_touched"),
            "answers_filled": same_stats.get("answers_filled"),
            "explanations_filled": same_stats.get("explanations_filled"),
            "missing_pdf_count": len(same_stats.get("missing_pdf") or []),
            "no_answers_found_count": len(same_stats.get("no_answers_found") or []),
            "conflict_count": len(same_stats.get("conflicts") or []),
            "no_answers_found": (same_stats.get("no_answers_found") or [])[:50],
            "conflicts": (same_stats.get("conflicts") or [])[:50],
            "details": same_stats.get("details") or [],
        },
        "solutions_pdfs": {
            "solutions_seen": sol_stats.get("solutions_seen"),
            "matched_count": len(sol_stats.get("matched") or []),
            "unmatched_count": len(sol_stats.get("unmatched") or []),
            "answers_filled": sol_stats.get("answers_filled"),
            "explanations_filled": sol_stats.get("explanations_filled"),
            "conflict_count": len(sol_stats.get("conflicts") or []),
            "matched": sol_stats.get("matched") or [],
            "unmatched": sol_stats.get("unmatched") or [],
            "conflicts": (sol_stats.get("conflicts") or [])[:50],
        },
    }
    report_path = out_root / "answer_attach_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", report_path)
    log.info("After: %s", after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

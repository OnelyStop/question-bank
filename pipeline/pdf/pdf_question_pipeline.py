"""
PDF → question_bank in one go.

  python pdf_question_pipeline.py
  python pdf_question_pipeline.py --force --skip-answers
  python pdf_question_pipeline.py --pdf some.pdf --force
  python pdf_question_pipeline.py --limit 5 --force --skip-answers

Per PDF: read meta, layout-parse, label/clean, write JSON.
Then rebuild index.jsonl. Answers optional.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from pdf_to_questions import (
    DEFAULT_CORPUS,
    DEFAULT_OUT,
    convert_pdf,
    iter_pdfs,
    rebuild_index,
    write_report,
)

log = logging.getLogger("pdf_question_pipeline")

STAGES = ("meta", "layout", "enrich", "write", "index", "answers")


def process_one_pdf(
    pdf: Path,
    *,
    corpus: Path,
    out_root: Path,
    force: bool = False,
    taxonomy: dict[str, Any] | None = None,
    label_questions: bool = True,
) -> dict[str, Any]:
    """Parse one PDF into question_bank JSON."""
    log.info("parsing %s", pdf.name)
    return convert_pdf(
        pdf,
        corpus,
        out_root,
        force=force,
        taxonomy=taxonomy,
        label_questions=label_questions,
    )


def run_pipeline(
    *,
    corpus: Path | None = None,
    out_root: Path | None = None,
    force: bool = False,
    limit: int = 0,
    pdfs: list[Path] | None = None,
    skip_labels: bool = False,
    skip_answers: bool = False,
) -> dict[str, Any]:
    """Batch-convert PDFs; return the parse report."""
    corpus = corpus or DEFAULT_CORPUS
    out_root = out_root or DEFAULT_OUT
    out_root.mkdir(parents=True, exist_ok=True)

    taxonomy = None
    if not skip_labels:
        from question_pipeline import load_taxonomy_cached

        taxonomy = load_taxonomy_cached()

    if pdfs:
        paths = list(pdfs)
    else:
        paths = iter_pdfs(corpus)
    if limit and limit > 0:
        paths = paths[:limit]

    log.info("%s pdf(s)  %s -> %s", len(paths), corpus, out_root)

    results: list[dict[str, Any]] = []
    for idx, pdf in enumerate(paths, start=1):
        log.info("[%s/%s] %s", idx, len(paths), pdf.name)
        results.append(
            process_one_pdf(
                pdf,
                corpus=corpus,
                out_root=out_root,
                force=force,
                taxonomy=taxonomy,
                label_questions=not skip_labels,
            )
        )

    answer_report: dict[str, Any] | None = None
    if not skip_answers:
        from question_pipeline import attach_answers_to_bank

        log.info("attaching answers")
        answer_report = attach_answers_to_bank(out_root, corpus, limit=limit or 0)

    log.info("rebuilding index")
    index_count = rebuild_index(out_root)

    report = write_report(out_root, results)
    report["index_rows"] = index_count
    if answer_report:
        report["answer_attachment"] = answer_report
    report["pipeline"] = "pdf_question_pipeline"
    report["stages"] = list(STAGES if not skip_answers else STAGES[:-1])

    (out_root / "parse_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info(
        "done — %s papers, ~%s questions, %s index rows",
        report.get("papers_seen"),
        report.get("total_questions_indexed_approx"),
        index_count,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Convert corpus PDFs into question_bank JSON")
    p.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--limit", type=int, default=0, help="Max PDFs (0 = all)")
    p.add_argument("--force", action="store_true", help="Re-parse even if cached")
    p.add_argument("--pdf", action="append", default=[], help="Specific PDF path(s)")
    p.add_argument("--skip-labels", action="store_true")
    p.add_argument("--skip-answers", action="store_true")
    args = p.parse_args(argv)

    report = run_pipeline(
        corpus=Path(args.corpus),
        out_root=Path(args.out),
        force=args.force,
        limit=args.limit,
        pdfs=[Path(x) for x in args.pdf] or None,
        skip_labels=args.skip_labels,
        skip_answers=args.skip_answers,
    )
    status = report.get("status_counts") or {}
    if status.get("failed") and not status.get("ok") and not status.get("partial"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

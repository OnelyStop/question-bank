#!/usr/bin/env python3
"""Recover answer data only from exact, non-conflicting provenance matches.

This deliberately does not try to solve a question.  It considers two sources:

* an identical question already answered elsewhere in the current corpus; and
* the historical ``corpus/sets`` answer collection at a pinned git revision.

The question stem and the complete keyed option set must match after Unicode
normalisation.  A fingerprint with more than one answer is excluded.  The
default is a dry run; ``--apply`` is required before any question JSON changes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper, rebuild_index


DEFAULT_REVISION = "ce4d92f"
SET_FILES = ["corpus/sets/extracted.json"] + [f"corpus/sets/usable/{n}.json" for n in range(1, 11)]


def normalise(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def fingerprint(question: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    stem = normalise(question.get("stem"))
    options = question.get("options")
    if not stem or not isinstance(options, dict) or not options:
        return None
    return stem, tuple(sorted((str(key), normalise(value)) for key, value in options.items()))


def add_evidence(
    evidence: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, set[str]]],
    key: tuple[str, tuple[tuple[str, str], ...]] | None,
    answer: object,
    options: dict[str, Any],
    explanation: object = None,
) -> None:
    answer = str(answer or "").lower()
    if not key or answer not in options:
        return
    evidence[key].setdefault(answer, set())
    if isinstance(explanation, str) and explanation.strip():
        evidence[key][answer].add(explanation.strip())


def git_json(repo: Path, revision: str, path: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", "show", f"{revision}:{path}"],
        cwd=repo,
        capture_output=True,
        encoding="utf-8",
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    return payload if isinstance(payload, list) else []


def collect_legacy(repo: Path, revision: str, evidence: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, set[str]]]) -> int:
    records = 0
    for path in SET_FILES:
        for item in git_json(repo, revision, path):
            options = item.get("options")
            if not isinstance(options, list):
                continue
            keyed = {str(o.get("key")): o.get("text") or "" for o in options if isinstance(o, dict) and o.get("key")}
            key = fingerprint({"stem": item.get("stem"), "options": keyed})
            add_evidence(evidence, key, item.get("correct_option"), keyed, item.get("explanation"))
            records += 1
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover answers from exact, validated provenance only")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--apply", action="store_true", help="write validated, non-conflicting recoveries")
    parser.add_argument("--report", type=Path, help="optional JSON report path")
    args = parser.parse_args()

    papers: list[tuple[Path, dict[str, Any]]] = []
    evidence: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, set[str]]] = defaultdict(dict)
    for path in iter_paper_jsons(args.out):
        paper = load_paper(path)
        if not paper:
            continue
        papers.append((path, paper))
        for question in paper.get("questions") or []:
            options = question.get("options") or {}
            add_evidence(evidence, fingerprint(question), question.get("answer"), options, question.get("explanation"))

    legacy_records = collect_legacy(Path(__file__).resolve().parents[2], args.revision, evidence)
    unambiguous = {key: next(iter(values.items())) for key, values in evidence.items() if len(values) == 1}
    conflicts = sum(1 for values in evidence.values() if len(values) > 1)
    recovered = explanations = candidates = papers_touched = 0

    for path, paper in papers:
        dirty = False
        for question in paper.get("questions") or []:
            if question.get("answer"):
                continue
            hit = unambiguous.get(fingerprint(question))
            if not hit:
                continue
            answer, explanation_set = hit
            options = question.get("options") or {}
            if answer not in options:
                continue
            candidates += 1
            if not args.apply:
                continue
            question["answer"] = answer
            question["answer_source"] = "exact_provenance"
            question["answer_confidence"] = 0.9
            # Explanations are copied only if provenance supplies exactly one
            # non-empty version, avoiding arbitrary selection between variants.
            if len(explanation_set) == 1:
                question["explanation"] = next(iter(explanation_set))
                explanations += 1
            dirty = True
            recovered += 1
        if dirty:
            path.write_text(json.dumps(paper, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            papers_touched += 1

    if args.apply and papers_touched:
        rebuild_index(args.out)
    report = {
        "dry_run": not args.apply,
        "papers_scanned": len(papers),
        "legacy_records_scanned": legacy_records,
        "unambiguous_provenance_fingerprints": len(unambiguous),
        "conflicting_provenance_fingerprints_skipped": conflicts,
        "candidate_answers": candidates,
        "answers_filled": recovered,
        "explanations_filled": explanations,
        "papers_touched": papers_touched,
    }
    rendered = json.dumps(report, indent=2)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

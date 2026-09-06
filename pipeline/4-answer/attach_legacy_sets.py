#!/usr/bin/env python3
"""Attach answers from the historical corpus/sets collection by exact content.

The legacy sets are read directly from a pinned git revision. A match requires
the NFKC/casefolded stem *and every keyed option* to agree, deliberately keeping
numeric text intact. Conflicting legacy answers are reported and never applied.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from corpus import DEFAULT_OUT, iter_paper_jsons, load_paper, rebuild_index


DEFAULT_REVISION = "ce4d92f"
SET_FILES = ["corpus/sets/extracted.json"] + [f"corpus/sets/usable/{n}.json" for n in range(1, 11)]


def normalise(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def fingerprint(stem: str | None, options: dict[str, str]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return normalise(stem), tuple(sorted((str(key), normalise(value)) for key, value in options.items()))


def git_json(repo: Path, revision: str, name: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", "show", f"{revision}:{name}"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    payload = json.loads(result.stdout)
    return payload if isinstance(payload, list) else []


def legacy_answers(repo: Path, revision: str) -> tuple[dict[tuple[str, tuple[tuple[str, str], ...]], str], int]:
    answers: dict[tuple[str, tuple[tuple[str, str], ...]], set[str]] = defaultdict(set)
    for name in SET_FILES:
        for item in git_json(repo, revision, name):
            answer = item.get("correct_option")
            options = item.get("options") or []
            if answer not in {"a", "b", "c", "d", "e"} or not isinstance(options, list):
                continue
            keyed = {str(option.get("key")): str(option.get("text") or "") for option in options if option.get("key")}
            if not keyed:
                continue
            answers[fingerprint(item.get("stem"), keyed)].add(answer)
    conflicts = sum(1 for values in answers.values() if len(values) > 1)
    return {key: next(iter(values)) for key, values in answers.items() if len(values) == 1}, conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach exact answers from historical corpus sets")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    known, legacy_conflicts = legacy_answers(repo, args.revision)
    filled = papers = 0
    for path in iter_paper_jsons(args.out):
        paper = load_paper(path)
        if not paper:
            continue
        dirty = False
        for question in paper.get("questions") or []:
            if question.get("answer"):
                continue
            options = question.get("options") or {}
            answer = known.get(fingerprint(question.get("stem"), options))
            if answer and answer in options:
                question["answer"] = answer
                question["answer_source"] = f"legacy_sets:{args.revision}"
                question["answer_confidence"] = 0.9
                filled += 1
                dirty = True
        if dirty:
            path.write_text(json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            papers += 1

    rebuild_index(args.out)
    report = {
        "revision": args.revision,
        "unique_legacy_fingerprints": len(known),
        "legacy_conflicting_fingerprints": legacy_conflicts,
        "answers_filled": filled,
        "papers_touched": papers,
    }
    (args.out / "answer_legacy_sets_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

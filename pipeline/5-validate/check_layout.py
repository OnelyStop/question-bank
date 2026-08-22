#!/usr/bin/env python3
"""Reject files that sit outside the folder that owns them.

Path drift is a proven failure mode here: references to old layouts twice made
a script resolve to a deleted directory and return zero results as success, and
the corpus moved (pdf/ -> done/ + remaining/) in a way that would let a new PDF
land in the dead location without anything noticing.

Checked against what a commit would contain: tracked files plus untracked
non-ignored ones -- the same lesson as check_imports, where a broken new file
was invisible until committed.

    python3 pipeline/5-validate/check_layout.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ROOT_ALLOWED = {
    ".githooks", ".github", ".gitignore", "CONTRIBUTING.md", "LICENSE",
    "README.md", "corpus", "data", "pipeline", "schema", "tests",
}
STEP_DIRS = {"1-extract", "2-classify", "3-dedupe", "4-answer", "5-validate", "lib"}
BATCH_RE = re.compile(r"^batch\d+$")
BATCH_FILES = re.compile(r"^(?:\d+\.(?:json|pdf)|index\.json|gap_report\.json|review_queue\.json)$")


def repo_files() -> list[str]:
    out = []
    for flags in (["--cached"], ["--others", "--exclude-standard"]):
        raw = subprocess.run(["git", "ls-files", "-z", *flags],
                             cwd=REPO, capture_output=True, check=True).stdout
        out.extend(p.decode("utf-8", "replace") for p in raw.split(b"\0") if p)
    return sorted(set(out))


def violation(path: str) -> str | None:
    parts = path.split("/")
    top = parts[0]

    if top not in ROOT_ALLOWED:
        return "unknown top-level entry"

    if top == "corpus":
        # only the split corpus, one source format, nothing in the old pdf/
        if len(parts) == 2:
            return None if parts[1] in {"manifest.json", ".gitkeep"} else \
                "corpus/ holds only manifest.json — PDFs go under done/ or remaining/"
        if parts[1] not in {"done", "remaining"}:
            return "corpus subtree must be done/ or remaining/ (corpus/pdf/ is the old layout)"
        if not (path.endswith(".pdf") or path.endswith(".pdf.meta.json")):
            return "corpus holds only *.pdf and *.pdf.meta.json"

    elif top == "data":
        if len(parts) == 2:
            return None if parts[1] == "README.md" else \
                "data/ holds only README.md and batch folders"
        if parts[1] == "papers":
            return "data/papers/ is the old layout — output goes to data/batch{n}/"
        if not BATCH_RE.match(parts[1]):
            return "data subtree must be a batch{n} folder"
        if len(parts) != 3 or not BATCH_FILES.match(parts[2]):
            return "unexpected file inside a batch folder"

    elif top == "pipeline":
        if len(parts) == 2:
            return None if parts[1] == "README.md" else \
                "pipeline/ holds only README.md and the step folders"
        if parts[1] not in STEP_DIRS:
            return f"not a pipeline step ({', '.join(sorted(STEP_DIRS))})"

    elif top == "tests":
        # Cases plus the two modules they share: harness.py (fixtures and the
        # step importer) and run_tests.py (the single entry point CI calls).
        # Python only -- fixtures belong in the case that uses them, not in
        # loose data files nothing points at.
        if len(parts) != 2 or not parts[1].endswith(".py"):
            return "tests/ holds only Python modules"
        if not (parts[1].startswith("test_") or parts[1] in {"harness.py", "run_tests.py"}):
            return "a test module is named test_*.py"

    return None


def main() -> int:
    files = repo_files()
    if len(files) < 50:
        print(f"::error::only {len(files)} files listed — the git call is broken",
              file=sys.stderr)
        return 1

    failures = [(p, v) for p in files if (v := violation(p))]
    if failures:
        print(f"{len(failures)} file(s) outside the folder that owns them:\n",
              file=sys.stderr)
        for p, v in failures[:40]:
            print(f"  {p}\n      {v}", file=sys.stderr)
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more", file=sys.stderr)
        return 1

    print(f"  OK — {len(files)} files, all where they belong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

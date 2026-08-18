#!/usr/bin/env python3
"""Check that every pipeline module can actually be imported.

`python -m py_compile` only parses. It passes a file with a missing import or an
undefined name at module scope — which is how an `import fitz` inherited from the
PDF module left the classifier unrunnable without anything noticing.

Each module is imported in its **own subprocess**. An earlier version imported
them all in one process and passed `4-answer/attach_answers.py`, which does not
import at all: loading step 1 first left `pdf_to_questions` in `sys.modules`, so
step 4's cross-step import silently resolved. Order-dependent false passes are
the exact failure this check exists to catch.

    python3 pipeline/5-validate/check_imports.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# A run that finds nothing must fail, not pass quietly. 31 modules today.
MIN_MODULES = 25

# Known broken, with a reason. The check fails if anything on it starts
# importing, so the list cannot rot.
KNOWN_BROKEN: set[str] = set()

CHILD = """
import importlib, importlib.util, sys
from pathlib import Path
path = Path(sys.argv[1])
pkg = path.parent
if (pkg / "__init__.py").exists():
    sys.path.insert(0, str(pkg.parent))
    name = path.stem
    importlib.import_module(f"{pkg.name}.{name}" if name != "__init__" else pkg.name)
else:
    sys.path.insert(0, str(pkg))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
"""


def tracked_modules() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "pipeline/**/*.py"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split()
    return [REPO / p for p in out]


def imports_ok(path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-c", CHILD, str(path)],
        cwd=REPO, capture_output=True, text=True,
    )
    if proc.returncode == 0:
        return True, ""
    last = [ln for ln in proc.stderr.strip().splitlines() if ln.strip()]
    return False, last[-1] if last else f"exit {proc.returncode}"


def main() -> int:
    files = tracked_modules()

    if len(files) < MIN_MODULES:
        print(f"::error::found only {len(files)} modules, expected at least "
              f"{MIN_MODULES} — the glob is probably broken", file=sys.stderr)
        return 1

    failures: list[tuple[str, str]] = []
    skipped: list[str] = []

    for path in files:
        rel = str(path.relative_to(REPO))
        if rel in KNOWN_BROKEN:
            skipped.append(rel)
            continue
        ok, err = imports_ok(path)
        if not ok:
            failures.append((rel, err))

    fixed = [rel for rel in KNOWN_BROKEN if imports_ok(REPO / rel)[0]]
    if fixed:
        print(f"\n  These now import — remove them from KNOWN_BROKEN: {fixed}",
              file=sys.stderr)
        return 1

    if failures:
        print(f"\n{len(failures)} of {len(files)} modules fail to import\n", file=sys.stderr)
        for rel, err in failures:
            print(f"::error file={rel}::{err}", file=sys.stderr)
            print(f"  {rel}\n      {err}", file=sys.stderr)
        return 1

    print(f"  OK — {len(files) - len(skipped)} modules import"
          + (f", {len(skipped)} known broken: {', '.join(skipped)}" if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

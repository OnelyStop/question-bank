#!/usr/bin/env python3
"""Check that every pipeline module can actually be imported.

`python -m py_compile` only parses. It passes a file with a missing import or an
undefined name at module scope — which is how an `import fitz` inherited from the
PDF module left the classifier unrunnable without anything noticing.

    python3 pipeline/5-validate/check_imports.py
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Known broken, with a reason. This list must only ever shrink: the check fails
# if something on it starts importing, so it can't rot. Currently empty.
KNOWN_BROKEN: set[str] = set()


def tracked_modules() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "pipeline/**/*.py"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split()
    return [REPO / p for p in out]


def load(path: Path) -> None:
    """Import one file. Packages go through their parent so relative imports work."""
    pkg_root = path.parent
    if (pkg_root / "__init__.py").exists():
        # part of a package — import it as package.module, from the parent dir
        sys.path.insert(0, str(pkg_root.parent))
        try:
            name = path.stem if path.stem != "__init__" else ""
            target = f"{pkg_root.name}.{name}" if name else pkg_root.name
            importlib.import_module(target)
        finally:
            sys.path.pop(0)
        return

    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ImportError("no import spec")
        module = importlib.util.module_from_spec(spec)
        # register before exec: dataclasses and typing resolve names via sys.modules
        sys.modules[path.stem] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(path.stem, None)
    finally:
        sys.path.pop(0)


def main() -> int:
    files = tracked_modules()
    failures: list[tuple[str, str]] = []

    skipped = []
    for path in files:
        rel = str(path.relative_to(REPO))
        if rel in KNOWN_BROKEN:
            skipped.append(rel)
            continue
        try:
            load(path)
        except Exception as exc:
            failures.append((rel, f"{type(exc).__name__}: {exc}"))

    # a file that starts importing should leave the list, or it rots
    fixed = []
    for rel in list(KNOWN_BROKEN):
        try:
            load(REPO / rel)
            fixed.append(rel)
        except Exception:
            pass
    if fixed:
        print(f"\n  These now import — remove them from KNOWN_BROKEN: {fixed}", file=sys.stderr)
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

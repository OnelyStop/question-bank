#!/usr/bin/env python3
"""Run every test in this folder.

One entry point so CI cannot drift from what is here: adding a tests/test_*.py
is enough, no workflow edit. Nothing outside tests/ holds test cases.

    python3 tests/run_tests.py            # everything
    python3 tests/run_tests.py maths      # only modules matching "maths"

No framework required -- plain asserts, run in file order. pytest discovers the
same functions if it is installed.
"""

from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_module(module) -> int:
    """Run every test_* function in `module`. Returns the failure count."""
    failures = 0
    names = [n for n in vars(module) if n.startswith("test_") and callable(getattr(module, n))]
    for name in sorted(names):
        try:
            getattr(module, name)()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {module.__name__}.{name}\n    {exc}", file=sys.stderr)
        except Exception:  # a broken test is a failure, not a crash of the run
            failures += 1
            print(f"  ERROR {module.__name__}.{name}", file=sys.stderr)
            traceback.print_exc()
    return failures


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(HERE))
    pattern = argv[0] if argv else ""
    modules = sorted(p.stem for p in HERE.glob("test_*.py") if pattern in p.stem)
    if not modules:
        # An empty run is a broken path, not a pass -- the same failure mode as
        # a gap report over zero papers printing "no gaps".
        print(f"::error::no test modules matched {pattern!r} in {HERE}", file=sys.stderr)
        return 1

    total = failures = 0
    for name in modules:
        module = importlib.import_module(name)
        cases = [n for n in vars(module) if n.startswith("test_")
                 and callable(getattr(module, n))]
        total += len(cases)
        bad = run_module(module)
        failures += bad
        mark = "FAIL" if bad else "ok  "
        print(f"  {mark}  {name:22} {len(cases):3d} cases"
              + (f"  {bad} failed" if bad else ""))

    print(f"\n  {total} cases in {len(modules)} modules, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

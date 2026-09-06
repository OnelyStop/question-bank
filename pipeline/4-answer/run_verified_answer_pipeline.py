"""Run every non-LLM, source-backed answer pass until it reaches a fixed point.

This controller deliberately does not invent answers.  It repeats PDF-key,
solutions-PDF, legacy exact-match, and validation passes while any verified
answer is added, then exports the remaining well-formed questions in batches
of 25 for human or subscription-model review.

It cannot call the chat model that is running this conversation. Doing that
would require a separate API integration and credentials.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(ROOT / script), *args], check=True)


def answer_count(out: Path) -> int:
    report = json.loads((out / "answer_quality_report.json").read_text(encoding="utf-8"))
    return int(report["summary"]["answered"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--max-passes", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--queue-dir", type=Path, default=Path("data/agent_answer_batches_current"))
    args = parser.parse_args()
    if args.max_passes < 1:
        parser.error("--max-passes must be at least 1")

    run("verify_answer_quality.py", "--out", str(args.out))
    initial = answer_count(args.out)
    history: list[dict[str, int]] = []
    for pass_no in range(1, args.max_passes + 1):
        before = answer_count(args.out)
        run("attach_answers.py", "--out", str(args.out), "--corpus", str(args.corpus))
        run("attach_legacy_sets.py", "--out", str(args.out))
        run("validate_answers.py", "--out", str(args.out))
        run("verify_answer_quality.py", "--out", str(args.out))
        after = answer_count(args.out)
        history.append({"pass": pass_no, "before": before, "after": after, "added": after - before})
        if after == before:
            break

    run(
        "export_agent_batches.py",
        "--out", str(args.out),
        "--export-dir", str(args.queue_dir),
        "--mode", "answers",
        "--batch-size", str(args.batch_size),
    )
    final = answer_count(args.out)
    report = {"initial_answered": initial, "final_answered": final, "verified_passes": history, "queue_dir": str(args.queue_dir)}
    (args.out / "verified_answer_pipeline_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Copy pre-2023 (+ no_year / untracked) PDFs into corpus_pre_2023/ with same structure."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "corpus"
DST = ROOT / "corpus_pre_2023"

PRE_YEAR = re.compile(r"^(20(?:1[0-9]|2[0-2]))$")  # 2010–2022
POST_YEAR = re.compile(r"^202[3-9]$")
ANY_YEAR = re.compile(r"(20(?:1[0-9]|2[0-9]))")


def should_copy(pdf: Path, rel_parts: tuple[str, ...]) -> bool:
    if "no_year" in rel_parts:
        return True
    if any(PRE_YEAR.match(p) for p in rel_parts):
        return True
    if any(POST_YEAR.match(p) for p in rel_parts):
        return False
    name_years = ANY_YEAR.findall(pdf.name)
    if name_years and all(int(y) < 2023 for y in name_years):
        return True
    return False


def main() -> None:
    DST.mkdir(exist_ok=True)
    copied = 0
    for pdf in SRC.rglob("*.pdf"):
        rel = pdf.relative_to(SRC)
        if not should_copy(pdf, rel.parts):
            continue
        target = DST / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != pdf.stat().st_size:
            shutil.copy2(pdf, target)
            meta = pdf.with_suffix(pdf.suffix + ".meta.json")
            if meta.exists():
                shutil.copy2(meta, target.with_suffix(target.suffix + ".meta.json"))
        copied += 1
    print(f"corpus_pre_2023 PDFs: {len(list(DST.rglob('*.pdf')))} (processed {copied})")


if __name__ == "__main__":
    main()

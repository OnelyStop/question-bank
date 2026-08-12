"""Optional OCR supplement for image context blocks (never replaces images)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("ocr_supplement")

_tesseract = None


def _get_tesseract():
    global _tesseract
    if _tesseract is not None:
        return _tesseract
    try:
        import pytesseract  # type: ignore

        _tesseract = pytesseract
        return pytesseract
    except ImportError:
        _tesseract = False
        return False


def ocr_image_file(image_path: Path) -> str:
    """Return OCR text for an image file, or empty string if unavailable."""
    tess = _get_tesseract()
    if not tess:
        return ""
    try:
        from PIL import Image  # type: ignore

        with Image.open(image_path) as img:
            return tess.image_to_string(img).strip()
    except Exception as exc:  # noqa: BLE001
        log.debug("OCR failed for %s: %s", image_path, exc)
        return ""


def supplement_context_ocr(
    context: list[dict[str, Any]] | None,
    bank_root: Path,
) -> list[dict[str, Any]]:
    """Add ocr_text to image blocks when Tesseract is available."""
    if not context:
        return []
    out: list[dict[str, Any]] = []
    for block in context:
        b = dict(block)
        if b.get("type") == "image" and b.get("asset") and not b.get("ocr_text"):
            rel = str(b["asset"]).lstrip("/")
            if rel.startswith("_assets/"):
                img_path = bank_root / rel
            else:
                img_path = bank_root / rel
            if img_path.is_file():
                text = ocr_image_file(img_path)
                if text:
                    b["ocr_text"] = text
        out.append(b)
    return out

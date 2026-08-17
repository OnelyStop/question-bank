"""Extract ordered page streams (text + images) from exam PDFs."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

log = logging.getLogger("page_stream")


@dataclass
class StreamItem:
    kind: str  # text | image | table
    page: int
    bbox: tuple[float, float, float, float]
    text: str | None = None
    asset: str | None = None
    xref: int | None = None
    ocr_text: str | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass
class PageStreamResult:
    full_text: str
    page_spans: list[tuple[int, int, int]]
    items: list[StreamItem] = field(default_factory=list)
    assets_exported: int = 0


def _is_decorative(bbox: tuple[float, float, float, float], page_rect: fitz.Rect) -> bool:
    """Legacy helper — prefer layout_parse crops. Header 12% / footer 8% are decorative."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    if w < 35 or h < 35:
        return True
    page_h = page_rect.height
    page_w = page_rect.width
    header_y = page_rect.y0 + 0.12 * page_h
    footer_y = page_rect.y1 - 0.08 * page_h
    if y1 <= header_y + 5:
        return True
    if y0 < header_y and h < 0.22 * page_h:
        return True
    if y0 >= footer_y - 5:
        return True
    if w * h < 0.002 * page_w * page_h:
        return True
    return False


def crop_page_region(
    page: fitz.Page,
    clip: tuple[float, float, float, float],
    out_path: Path,
    *,
    scale: float = 1.5,
) -> bool:
    """Render a clipped page region to PNG. Returns False on failure."""
    try:
        rect = fitz.Rect(clip)
        if rect.width < 20 or rect.height < 20:
            return False
        pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(scale, scale), alpha=False)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_path))
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("crop_page_region failed: %s", exc)
        return False


def _export_image(
    doc: fitz.Document,
    page: fitz.Page,
    xref: int,
    bbox: tuple[float, float, float, float],
    paper_id: str,
    assets_dir: Path,
    page_num: int,
    img_index: int,
) -> str | None:
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        assets_dir.mkdir(parents=True, exist_ok=True)
        name = f"p{page_num}_{img_index}.png"
        out_path = assets_dir / name
        pix.save(str(out_path))
        rel = f"_assets/{paper_id}/{name}"
        return rel.replace("\\", "/")
    except Exception as exc:  # noqa: BLE001
        log.debug("image export failed p%s xref=%s: %s", page_num, xref, exc)
        return None


def _sort_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(blocks, key=lambda b: (round(b["bbox"][1], 1), round(b["bbox"][0], 1)))


def extract_page_stream(
    pdf_path: Path,
    paper_id: str,
    assets_root: Path,
    *,
    clean_line_fn: Any | None = None,
) -> PageStreamResult:
    """Build text + image stream; export content images to assets_root/_assets/{paper_id}/."""
    doc = fitz.open(pdf_path)
    assets_dir = assets_root / "_assets" / paper_id
    items: list[StreamItem] = []
    text_chunks: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    pos = 0
    xref_page_counts: dict[int, int] = {}
    exported = 0

    try:
        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict").get("blocks") or []
            img_idx = 0
            page_items: list[StreamItem] = []

            seen_xrefs: set[int] = set()
            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    rects = []
                if not rects:
                    continue
                for rect in rects:
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                    if _is_decorative(bbox, page.rect):
                        continue
                    asset = _export_image(
                        doc, page, xref, bbox, paper_id, assets_dir, page_num, img_idx
                    )
                    img_idx += 1
                    if asset:
                        exported += 1
                        page_items.append(
                            StreamItem(
                                kind="image",
                                page=page_num,
                                bbox=bbox,
                                asset=asset,
                                xref=xref,
                            )
                        )

            for block in _sort_blocks(blocks):
                if block.get("type") != 0:
                    continue
                bbox = tuple(block.get("bbox") or (0, 0, 0, 0))
                lines: list[str] = []
                for line in block.get("lines") or []:
                    spans = "".join(s.get("text", "") for s in line.get("spans") or [])
                    if spans.strip():
                        lines.append(spans)
                text = "\n".join(lines).strip()
                if not text:
                    continue
                if clean_line_fn:
                    text = clean_line_fn(text)
                if not text:
                    continue
                page_items.append(
                    StreamItem(kind="text", page=page_num, bbox=bbox, text=text)
                )

            # Tables as text supplement
            try:
                tabs = page.find_tables()
                for ti, tab in enumerate(tabs.tables or []):
                    try:
                        md = tab.to_markdown()
                    except Exception:
                        md = ""
                    if md and len(md) > 20:
                        page_items.append(
                            StreamItem(
                                kind="table",
                                page=page_num,
                                bbox=tuple(tab.bbox) if hasattr(tab, "bbox") else (0, 0, 0, 0),
                                text=md,
                            )
                        )
            except Exception:
                pass

            if not page_items:
                continue

            if text_chunks:
                text_chunks.append("\n\n")
                pos += 2

            page_start = pos
            first = True
            for it in page_items:
                if it.kind == "text":
                    if not first:
                        text_chunks.append("\n")
                        pos += 1
                    it.char_start = pos
                    text_chunks.append(it.text or "")
                    pos += len(it.text or "")
                    it.char_end = pos
                    first = False
                elif it.kind in ("image", "table"):
                    it.char_start = pos
                    it.char_end = pos
            page_spans.append((page_num, page_start, pos))
            items.extend(page_items)

        full_text = "".join(text_chunks)
    finally:
        doc.close()

    return PageStreamResult(
        full_text=full_text,
        page_spans=page_spans,
        items=items,
        assets_exported=exported,
    )


def items_for_char_range(
    items: list[StreamItem],
    start: int,
    end: int,
    pages: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    """Collect stream items overlapping [start, end) or page range."""
    out: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    for it in items:
        include = False
        if it.char_start is not None and it.char_end is not None:
            if it.kind == "text" and it.char_start < end and it.char_end > start:
                include = True
            elif it.kind in ("image", "table") and pages:
                lo, hi = pages
                include = lo <= it.page <= hi
            elif it.kind in ("image", "table") and it.char_start >= start and it.char_start < end:
                include = True
        elif pages and it.kind in ("image", "table"):
            lo, hi = pages
            include = lo <= it.page <= hi

        if not include:
            continue

        if it.kind == "text":
            out.append({"type": "text", "text": it.text, "page": it.page, "bbox": list(it.bbox)})
        elif it.kind == "table":
            out.append({"type": "table", "text": it.text, "page": it.page, "bbox": list(it.bbox)})
        elif it.kind == "image" and it.asset and it.asset not in seen_assets:
            seen_assets.add(it.asset)
            block: dict[str, Any] = {
                "type": "image",
                "asset": it.asset,
                "page": it.page,
                "bbox": list(it.bbox),
            }
            if it.ocr_text:
                block["ocr_text"] = it.ocr_text
            out.append(block)
    return out


def flatten_context_text(blocks: list[dict[str, Any]] | None) -> str:
    if not blocks:
        return ""
    parts = []
    for b in blocks:
        if b.get("type") in ("text", "table") and b.get("text"):
            parts.append(str(b["text"]))
    return " ".join(parts).strip()

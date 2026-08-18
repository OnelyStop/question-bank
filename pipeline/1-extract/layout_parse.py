"""Geometry-first PDF question parsing: layout boxes → question units → allowlisted figures."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from context_completeness import needs_figure_stimulus
from question_schema import Question, make_direction_id, make_q_id

log = logging.getLogger("layout_parse")

HEADER_FRAC = 0.12
FOOTER_FRAC = 0.08
MIN_FIGURE_INK = 0.04
MAX_WATERMARK_INK = 0.12
MIN_CROP_AREA = 8000

# A CID font with no ToUnicode CMap makes PyMuPDF hand back raw glyph IDs, which
# land in the C0 control range instead of readable text -- the stem comes out as
# "\x01 A\x10 6 D\x03 \x0f\x10 E F". Measured over all 375 corpus PDFs: the one
# broken paper scores 0.7086 and every other PDF scores exactly 0.0000, so this
# threshold sits an order of magnitude clear of both sides.
CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MAX_CTRL_CHAR_RATIO = 0.10


@dataclass
class TextBox:
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    char_start: int = 0
    char_end: int = 0


@dataclass
class LayoutResult:
    questions: list[Question]
    notes: list[str] = field(default_factory=list)
    assets_exported: int = 0


def _helpers():
    """Lazy import to avoid circular import with pdf_to_questions."""
    from pdf_to_questions import (
        clean_lines,
        cut_solutions_section,
        direction_covers,
        find_events,
        normalize_ws,
        parse_options,
        section_at,
        section_map_from_text,
        should_synthesize_cloze_stem,
    )

    return {
        "clean_lines": clean_lines,
        "cut_solutions_section": cut_solutions_section,
        "direction_covers": direction_covers,
        "find_events": find_events,
        "normalize_ws": normalize_ws,
        "parse_options": parse_options,
        "section_at": section_at,
        "section_map_from_text": section_map_from_text,
        "should_synthesize_cloze_stem": should_synthesize_cloze_stem,
    }


def _union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float] | None:
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return (x0, y0, x1, y1)


# Same header line pdf_to_questions.SOLUTIONS_CUT_RE looks for, kept as a local
# copy rather than threaded through the cross-module lazy-import shim in
# _helpers() -- this only needs a one-line per-block text match, not the
# multi-line cut semantics the original does on the whole concatenated string.
_SOLUTIONS_HEADER_RE = re.compile(
    r"(?im)^\s*(?:SOLUTIONS?(?:\s+AND\s+EXPLANATIONS?)?|ANSWER\s+KEY|DETAILED\s+SOLUTIONS?)\s*$"
)


def _has_solutions_header(blocks: list[dict[str, Any]]) -> bool:
    for b in blocks:
        for line in b.get("lines") or []:
            text = "".join(s.get("text", "") for s in line.get("spans") or [])
            if _SOLUTIONS_HEADER_RE.match(text.strip()):
                return True
    return False


def find_gutter(blocks: list[dict[str, Any]], page_width: float) -> float | None:
    """x of the column gutter on this page, or None for single-column.

    A real two-column layout has a vertical band that (almost) nothing crosses,
    with real content on both sides. Scanned in the middle 20% of the page width
    rather than fixed at the midpoint, because gutters drift a little per paper.
    A few full-width crossers (a wide direction, a table header) are tolerated —
    demanding zero broke on pages that are two-column apart from one wide block.

    Conservative on purpose: no gutter found -> caller keeps today's plain
    top-to-bottom order, so single-column pages are never touched by this.
    """
    n = len(blocks)
    if n < 4:
        return None

    def _area(b: dict[str, Any]) -> float:
        x0, y0, x1, y1 = b["bbox"]
        return max(0.0, x1 - x0) * max(0.0, y1 - y0)

    total_area = sum(_area(b) for b in blocks)
    if total_area <= 0:
        return None

    best: tuple[tuple[int, float], float] | None = None
    lo, hi = int(page_width * 0.40), int(page_width * 0.60)
    for cut in range(lo, hi, 3):
        crossing = sum(1 for b in blocks if b["bbox"][0] < cut - 2 and b["bbox"][2] > cut + 2)
        # Area-weighted, not block-count-based: a passage that wraps into many
        # small paragraph blocks on one side and lands as one or two tall
        # blocks on the other (e.g. a cloze passage's tail continuing at the
        # top of the next column) used to fail a >=25%-of-block-count check on
        # the sparse side even though that side plainly has real content.
        # Measured case: 9 small left-column blocks vs. 2 blocks spanning most
        # of the right column's height -- right was 2/14 blocks (14%) but
        # ~35% of page area, and the direction+passage for q79-84 silently
        # lost its whole body because no gutter was ever found on that page.
        left_area = sum(_area(b) for b in blocks if b["bbox"][2] <= cut + 2)
        right_area = sum(_area(b) for b in blocks if b["bbox"][0] >= cut - 2)
        if (
            crossing <= max(1, int(0.15 * n))
            and left_area >= 0.15 * total_area
            and right_area >= 0.15 * total_area
        ):
            score = (-crossing, min(left_area, right_area))
            if best is None or score > best[0]:
                best = (score, cut)
    return best[1] if best else None


def _sort_blocks(blocks: list[dict[str, Any]], page_width: float | None = None) -> list[dict[str, Any]]:
    """Reading order for one page's blocks.

    Plain top-to-bottom (y0, then x0 as a sub-point tiebreak) is wrong on a
    two-column page: a left-column block and a right-column block a few points
    apart in y0 emit in y-order, which stitches the end of one column's sentence
    onto the start of the other's. When `find_gutter` locates a real gutter, sort
    by column bucket first so the whole left column is emitted before the right
    column starts. `page_width=None` (page_stream.py's copy of this function,
    dead code in step 1) keeps the old behaviour untouched.

    Skipped on any page carrying a "Solutions" / "Answer Key" header: that
    header can land in either column bucket depending on its x0, and if it
    lands in the left bucket, column-bucketing puts the ENTIRE left column --
    header included -- ahead of the right column, even when the right column's
    real questions print visually above the header. `cut_solutions_section`
    then truncates from the header's position in the reordered string and
    takes those real questions with it. Measured: this silently deleted the
    last 2-3 questions on several papers before the guard was added. Plain
    y0 sort already handles these pages correctly -- that is why the original
    unfixed extractor never hit this -- so just fall back to it here.
    """
    if page_width is not None and not _has_solutions_header(blocks):
        gutter = find_gutter(blocks, page_width)
        if gutter is not None:
            return sorted(
                blocks,
                key=lambda b: (0 if b["bbox"][0] < gutter else 1, round(b["bbox"][1], 1), round(b["bbox"][0], 1)),
            )
    return sorted(blocks, key=lambda b: (round(b["bbox"][1], 1), round(b["bbox"][0], 1)))


def extract_text_boxes(pdf_path: Path) -> tuple[str, list[tuple[int, int, int]], list[TextBox], dict[int, fitz.Rect]]:
    """Text-only layout stream (no image xref export)."""
    h = _helpers()
    clean_lines = h["clean_lines"]
    cut_solutions_section = h["cut_solutions_section"]
    doc = fitz.open(pdf_path)
    boxes: list[TextBox] = []
    chunks: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    page_rects: dict[int, fitz.Rect] = {}
    pos = 0
    try:
        for page_num, page in enumerate(doc, start=1):
            page_rects[page_num] = page.rect
            blocks = page.get_text("dict").get("blocks") or []
            page_boxes: list[TextBox] = []
            for block in _sort_blocks(blocks, page.rect.width):
                if block.get("type") != 0:
                    continue
                raw_bbox = block.get("bbox") or (0, 0, 0, 0)
                bbox = (float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
                lines: list[str] = []
                for line in block.get("lines") or []:
                    spans = "".join(s.get("text", "") for s in line.get("spans") or [])
                    if spans.strip():
                        lines.append(spans)
                text = "\n".join(lines).strip()
                if not text:
                    continue
                text = clean_lines(text)
                if not text:
                    continue
                page_boxes.append(TextBox(page=page_num, bbox=bbox, text=text))

            if not page_boxes:
                continue
            if chunks:
                chunks.append("\n\n")
                pos += 2
            page_start = pos
            first = True
            for tb in page_boxes:
                if not first:
                    chunks.append("\n")
                    pos += 1
                tb.char_start = pos
                chunks.append(tb.text)
                pos += len(tb.text)
                tb.char_end = pos
                first = False
            page_spans.append((page_num, page_start, pos))
            boxes.extend(page_boxes)
    finally:
        doc.close()

    full = cut_solutions_section("".join(chunks))
    return full, page_spans, boxes, page_rects


def boxes_for_range(boxes: list[TextBox], start: int, end: int) -> list[TextBox]:
    return [b for b in boxes if b.char_start < end and b.char_end > start]


def content_bbox_for_boxes(
    boxes: list[TextBox],
    page_rect: fitz.Rect,
) -> tuple[float, float, float, float] | None:
    if not boxes:
        return None
    ub = _union_bbox([b.bbox for b in boxes])
    if not ub:
        return None
    header_y = page_rect.y0 + HEADER_FRAC * page_rect.height
    footer_y = page_rect.y1 - FOOTER_FRAC * page_rect.height
    x0, y0, x1, y1 = ub
    y0 = max(y0, header_y)
    y1 = min(y1, footer_y)
    if y1 <= y0 + 8:
        return None
    pad = 4.0
    return (
        max(page_rect.x0, x0 - pad),
        y0,
        min(page_rect.x1, x1 + pad),
        y1,
    )


def _ink_density(pix: fitz.Pixmap) -> float:
    """Fraction of pixels that are not near-white."""
    try:
        samples = pix.samples
        n = pix.n
        total = pix.width * pix.height
        if total <= 0 or not samples:
            return 0.0
        dark = 0
        step = max(1, total // 5000)  # subsample for speed
        for i in range(0, total, step):
            off = i * n
            if n >= 3:
                r, g, b = samples[off], samples[off + 1], samples[off + 2]
                if r < 245 or g < 245 or b < 245:
                    dark += 1
            else:
                if samples[off] < 245:
                    dark += 1
        return dark / max(1, (total + step - 1) // step)
    except Exception:
        return 0.0


def is_header_footer_band(bbox: tuple[float, float, float, float], page_rect: fitz.Rect) -> bool:
    x0, y0, x1, y1 = bbox
    h = y1 - y0
    header_y = page_rect.y0 + HEADER_FRAC * page_rect.height
    footer_y = page_rect.y1 - FOOTER_FRAC * page_rect.height
    if y1 <= header_y + 5:
        return True
    if y0 >= footer_y - 5:
        return True
    # Tall header logo straddling band
    if y0 < header_y and h < page_rect.height * 0.2:
        return True
    return False


def bbox_overlap_ratio(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> float:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    x0 = max(ix0, ox0)
    y0 = max(iy0, oy0)
    x1 = min(ix1, ox1)
    y1 = min(iy1, oy1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area = max(1.0, (ix1 - ix0) * (iy1 - iy0))
    return inter / area


def find_figure_gap(
    page: fitz.Page,
    page_rect: fitz.Rect,
    direction_boxes: list[TextBox],
    question_boxes: list[TextBox],
) -> tuple[float, float, float, float] | None:
    """Find vertical gap between direction text and question text that may hold a figure."""
    if not direction_boxes or not question_boxes:
        return None
    dir_ub = _union_bbox([b.bbox for b in direction_boxes if b.page == page.number + 1])
    q_ub = _union_bbox([b.bbox for b in question_boxes if b.page == page.number + 1])
    if not dir_ub or not q_ub:
        return None
    gap_top = dir_ub[3]
    gap_bot = q_ub[1]
    if gap_bot - gap_top < 40:
        return None
    header_y = page_rect.y0 + HEADER_FRAC * page_rect.height
    footer_y = page_rect.y1 - FOOTER_FRAC * page_rect.height
    y0 = max(gap_top, header_y)
    y1 = min(gap_bot, footer_y)
    if y1 - y0 < 40:
        return None
    # Width was previously the full page minus a 20pt margin -- on a two-column
    # page that crop spans both columns and swallows the neighbouring column's
    # text (measured: a 40-question-shared "figure" that turned out to be a
    # screenshot of an unrelated seating puzzle in the other column).
    #
    # Clamp to the direction's own COLUMN, not to the tight bbox of its text: a
    # pie chart routinely draws wider than its caption/direction text (measured
    # on a real chart here -- labels span x=378-510, legend to x=501, well past
    # the direction line's own extent), so clamping to text bbox would crop the
    # chart itself. Clamping to the column is wide enough for the chart and
    # still excludes the other column.
    x0, x1 = page_rect.x0 + 20, page_rect.x1 - 20
    gutter = find_gutter(page.get_text("dict").get("blocks") or [], page_rect.width)
    if gutter is not None:
        dir_x0 = dir_ub[0]
        if dir_x0 < gutter:
            x1 = min(x1, gutter)
        else:
            x0 = max(x0, gutter)
    return (x0, y0, x1, y1)


def embedded_images_in_zone(
    page: fitz.Page,
    zone: tuple[float, float, float, float],
    page_rect: fitz.Rect,
) -> list[tuple[float, float, float, float]]:
    """Return bboxes of embedded images mostly inside the content zone (not header/footer)."""
    out: list[tuple[float, float, float, float]] = []
    seen: set[int] = set()
    for img in page.get_images(full=True):
        xref = int(img[0])
        if xref in seen:
            continue
        seen.add(xref)
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        for rect in rects:
            bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
            if is_header_footer_band(bbox, page_rect):
                continue
            if bbox_overlap_ratio(bbox, zone) < 0.7:
                continue
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if w < 40 or h < 40:
                continue
            if w * h < MIN_CROP_AREA:
                continue
            out.append(bbox)
    return out


def _render_crop_candidate(
    page: fitz.Page,
    clip: tuple[float, float, float, float],
) -> tuple[fitz.Pixmap | None, float]:
    """Render one crop candidate; return (pixmap, ink_density). Reject empty/watermark crops.

    Rendering is separate from saving so a caller comparing several candidates
    (attach_figure_for_direction tries up to three per direction) can pick the
    winner before anything touches disk -- export_crop used to save every
    candidate and only keep the best one's *path*, leaking the losers as
    orphan PNGs (698 of 1,626 files on a full corpus run, 73 MB).
    """
    rect = fitz.Rect(clip)
    if rect.width < 30 or rect.height < 30:
        return None, 0.0
    try:
        pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    except Exception as exc:
        log.debug("crop failed: %s", exc)
        return None, 0.0
    ink = _ink_density(pix)
    # Reject blank or watermark-like (very sparse ink on large area)
    area = rect.width * rect.height
    if ink < MIN_FIGURE_INK:
        return None, ink
    if ink < MAX_WATERMARK_INK and area > 0.25 * page.rect.width * page.rect.height:
        # Large sparse region ≈ watermark
        return None, ink
    return pix, ink


def _save_crop(pix: fitz.Pixmap, paper_id: str, assets_dir: Path, page_num: int, tag: str) -> str:
    assets_dir.mkdir(parents=True, exist_ok=True)
    name = f"p{page_num}_{tag}.png"
    pix.save(str(assets_dir / name))
    return f"_assets/{paper_id}/{name}".replace("\\", "/")


def export_crop(
    page: fitz.Page,
    clip: tuple[float, float, float, float],
    paper_id: str,
    assets_dir: Path,
    page_num: int,
    tag: str,
) -> tuple[str | None, float]:
    """Render a page crop and save it; return (asset_path, ink_density)."""
    pix, ink = _render_crop_candidate(page, clip)
    if pix is None:
        return None, ink
    return _save_crop(pix, paper_id, assets_dir, page_num, tag), ink


def attach_figure_for_direction(
    doc: fitz.Document,
    *,
    paper_id: str,
    assets_dir: Path,
    page_num: int,
    direction_boxes: list[TextBox],
    unit_boxes: list[TextBox],
    page_rect: fitz.Rect,
    dir_tag: str,
    cache: dict[str, str | None],
) -> str | None:
    """At most one figure crop per direction set."""
    if dir_tag in cache:
        return cache[dir_tag]
    page = doc[page_num - 1]
    zone = content_bbox_for_boxes(direction_boxes + unit_boxes, page_rect)
    if not zone:
        cache[dir_tag] = None
        return None

    # Prefer gap between direction and questions (classic DI layout)
    gap = find_figure_gap(page, page_rect, direction_boxes, unit_boxes)
    candidates: list[tuple[float, float, float, float]] = []
    if gap:
        candidates.append(gap)
    # Embedded images inside zone
    candidates.extend(embedded_images_in_zone(page, zone, page_rect))
    # Fallback: direction-only expanded zone (excluding question stem text height somewhat)
    if direction_boxes:
        dir_zone = content_bbox_for_boxes(direction_boxes, page_rect)
        if dir_zone and dir_zone[3] - dir_zone[1] > 60:
            candidates.append(dir_zone)

    best_pix: fitz.Pixmap | None = None
    best_ink = 0.0
    best_tag = ""
    for i, clip in enumerate(candidates):
        if is_header_footer_band(clip, page_rect):
            continue
        pix, ink = _render_crop_candidate(page, clip)
        if pix is not None and ink > best_ink:
            best_pix, best_ink, best_tag = pix, ink, f"{dir_tag}_{i}"

    # Only the winner ever gets written -- the runner-up candidates rendered
    # above are discarded in memory, never touching disk.
    best_asset = (
        _save_crop(best_pix, paper_id, assets_dir, page_num, best_tag) if best_pix is not None else None
    )

    cache[dir_tag] = best_asset
    return best_asset


def ctrl_char_ratio(text: str) -> float:
    """Fraction of non-whitespace chars that are C0 control chars.

    A healthy PDF's text layer scores 0.0 -- verified across all 375 corpus
    PDFs. Only a broken CID font (glyph IDs standing in for text) produces a
    non-trivial ratio.
    """
    non_ws = re.sub(r"\s", "", text)
    if not non_ws:
        return 0.0
    return len(CTRL_CHAR_RE.findall(non_ws)) / len(non_ws)


def parse_pdf_layout(
    pdf_path: Path,
    paper_id: str,
    assets_root: Path,
) -> LayoutResult:
    """Parse PDF into Question objects with geometry-first context (default: no images)."""
    h = _helpers()
    find_events = h["find_events"]
    direction_covers = h["direction_covers"]
    parse_options = h["parse_options"]
    normalize_ws = h["normalize_ws"]
    should_synthesize_cloze_stem = h["should_synthesize_cloze_stem"]

    text, page_spans, boxes, page_rects = extract_text_boxes(pdf_path)
    notes: list[str] = []
    if not text.strip():
        return LayoutResult(questions=[], notes=["empty_text"])
    if ctrl_char_ratio(text) > MAX_CTRL_CHAR_RATIO:
        # Glyph IDs, not text. Emitting these produces questions whose stem is
        # control characters, so refuse the paper and let it show up in
        # parse_report.json with a reason instead.
        return LayoutResult(questions=[], notes=["unusable_text_layer"])

    events = find_events(text)
    assets_dir = assets_root / "_assets" / paper_id
    assets_exported = 0
    figure_cache: dict[str, str | None] = {}

    directions: list[dict[str, Any]] = []
    active_bare_dir: dict[str, Any] | None = None
    direction_seq = 0
    questions: list[Question] = []
    seen_nums: set[int] = set()

    doc = fitz.open(pdf_path)
    try:
        i = 0
        while i < len(events):
            ev = events[i]
            if ev["kind"] == "direction":
                direction_seq += 1
                dir_id = make_direction_id(direction_seq)
                q_lo, q_hi = ev["q_start"], ev["q_end"]
                body_end = len(text)
                for j in range(i + 1, len(events)):
                    nxt = events[j]
                    if nxt["kind"] == "direction":
                        body_end = nxt["start"]
                        break
                    if nxt["kind"] == "question":
                        if q_lo is None or q_lo <= nxt["q_num"] <= (q_hi or nxt["q_num"]):
                            body_end = nxt["start"]
                            break
                raw_body = text[ev["end"] : body_end]
                direction_text = normalize_ws(raw_body)
                shared_opts: dict[str, str] = {}
                _pre, shared_opts = parse_options(raw_body)
                if shared_opts and len(_pre) > len(direction_text) * 0.5:
                    direction_text = normalize_ws(_pre) or direction_text

                dir_boxes = boxes_for_range(boxes, ev["start"], body_end)
                dir_record = {
                    "id": dir_id,
                    "q_start": q_lo,
                    "q_end": q_hi,
                    "text": direction_text or None,
                    "shared_options": shared_opts,
                    "body_start": ev["start"],
                    "body_end": body_end,
                    "boxes": dir_boxes,
                    "event_start": ev["start"],
                }
                directions.append(dir_record)
                if q_lo is None:
                    active_bare_dir = dir_record
                i += 1
                continue

            q_num = ev["q_num"]
            if q_num > 200 or q_num in seen_nums:
                i += 1
                continue

            active_dir: dict[str, Any] | None = None
            for d in reversed(directions):
                if direction_covers(d, q_num):
                    active_dir = d
                    break
            if active_dir is None and active_bare_dir and direction_covers(active_bare_dir, q_num):
                active_dir = active_bare_dir

            block_end = len(text)
            for j in range(i + 1, len(events)):
                nxt = events[j]
                if nxt["kind"] == "direction":
                    block_end = nxt["start"]
                    break
                if nxt["kind"] == "question" and nxt["q_num"] != q_num:
                    block_end = nxt["start"]
                    break

            raw_q = text[ev["end"] : block_end]
            stem, options = parse_options(raw_q)
            stem = normalize_ws(stem)

            if not options and active_dir and active_dir.get("shared_options"):
                if direction_covers(active_dir, q_num):
                    options = dict(active_dir["shared_options"])

            if not stem and options:
                if direction_covers(active_dir, q_num) and should_synthesize_cloze_stem(
                    active_dir.get("text") if active_dir else None, raw_q
                ):
                    stem = f"Select the word that fits blank ({q_num})."
                else:
                    stem = f"Question {q_num}."

            if not stem or (len(stem) < 8 and not options):
                notes.append(f"skip_empty_q{q_num}")
                i += 1
                continue

            q_boxes = boxes_for_range(boxes, ev["start"], block_end)
            p_start = q_boxes[0].page if q_boxes else None
            if p_start is None:
                for pn, a, b in page_spans:
                    if a <= ev["start"] < b:
                        p_start = pn
                        break
            p_start = p_start or 1
            p_end = q_boxes[-1].page if q_boxes else p_start
            page_rect = page_rects.get(p_start) or fitz.Rect(0, 0, 595, 842)

            dir_id = active_dir["id"] if active_dir and direction_covers(active_dir, q_num) else None
            dir_text = active_dir["text"] if active_dir and direction_covers(active_dir, q_num) else None
            dir_boxes = list(active_dir.get("boxes") or []) if active_dir and dir_id else []

            context: list[dict[str, Any]] = []
            if dir_text:
                context.append({"type": "text", "text": dir_text, "role": "direction"})

            want_figure = needs_figure_stimulus(dir_text, stem, options)
            figure_asset: str | None = None
            if want_figure and dir_id:
                before = figure_cache.get(dir_id)
                figure_asset = attach_figure_for_direction(
                    doc,
                    paper_id=paper_id,
                    assets_dir=assets_dir,
                    page_num=p_start,
                    direction_boxes=dir_boxes,
                    unit_boxes=q_boxes,
                    page_rect=page_rect,
                    dir_tag=dir_id,
                    cache=figure_cache,
                )
                if figure_asset and before is None:
                    assets_exported += 1
                if figure_asset:
                    zone = content_bbox_for_boxes(dir_boxes + q_boxes, page_rect)
                    context.append(
                        {
                            "type": "image",
                            "asset": figure_asset,
                            "page": p_start,
                            "bbox": list(zone) if zone else None,
                            "role": "figure",
                        }
                    )

            if stem:
                context.append({"type": "text", "text": stem, "role": "stem"})

            q = Question(
                q_id=make_q_id(paper_id, q_num),
                q_num=q_num,
                direction_id=dir_id,
                direction_text=dir_text,
                stem=stem,
                options=options,
                context=context,
            )
            questions.append(q)
            seen_nums.add(q_num)
            i += 1
    finally:
        doc.close()

    if not questions:
        notes.append("no_questions_parsed")
    if assets_exported:
        notes.append(f"figure_crops:{assets_exported}")
    return LayoutResult(questions=questions, notes=notes, assets_exported=assets_exported)

"""Assess whether a question has recoverable full context (geometry-first)."""

from __future__ import annotations

import re
from typing import Any

LETTER_ONLY_OPT = re.compile(r"^[A-F]$", re.I)
UPPER_STIMULUS = re.compile(r"\([A-E]\)\s+\S{4,}")
BLANK_MARKER = re.compile(r"_{2,}|\(\s*\d+\s*\)|blank\s*\(\s*\d+\s*\)", re.I)
SOLUTIONS_MARKERS = re.compile(
    r"\b(?:Sol\.|Solutions?\s|S\d+\.\s*Ans\.|Final Answer:)\b", re.I
)
OPTION_BLEED = re.compile(r"Directions?\s*\(|\bQ\d+\.|Copyright\s*©", re.I)
MATH_BROKEN = re.compile(r"^[√×÷+\-=\s\d.?]+$|√\s*\+\s*\d+\s*=\s*√")
MULTI_Q_MARKER = re.compile(r"\bQ(\d+)\b", re.I)
PERM_OPTION_RE = re.compile(r"^[A-E]{3,5}$", re.I)
NO_REARRANGEMENT_RE = re.compile(r"(?i)no\s+rearrangement\s+required")
SLASH_PARTS_RE = re.compile(r"\([A-E]\)\s*/.*\([B-E]\)\s*/")

# Directions that require a visual figure / table crop
NEEDS_FIGURE_RE = re.compile(
    r"(?i)\bstudy\s+the\s+(?:following\s+)?(?:table|chart|graph|figure|diagram|bar|pie)|"
    r"\bpie\s+chart|\bbar\s+(?:graph|diagram)|\bline\s+graph|"
    r"\bdata\s+interpretation|\bfollowing\s+(?:table|chart|graph|figure)|"
    r"\barrangement\s+carefully|\bpuzzle\b|"
    r"\bwho\s+among\s+the\s+following\s+(?:persons?|people)|"
    r"\bfollowing\s+information\s+carefully"
)

# Text-only English patterns that must NOT require images
TEXT_ONLY_ENGLISH_RE = re.compile(
    r"(?i)grammatical|idiomatic\s+err|error\s+(?:spot|detection)|"
    r"no\s+rearrangement\s+required|divided\s+into\s+.*phrases?|"
    r"correct\s+sequence\s+of\s+(?:these\s+)?phrases?|"
    r"para\s*jumble|sentence\s+improvement|cloze|"
    r"read\s+each\s+sentence|find\s+out\s+(?:whether|if).*(?:error|correct)"
)

HEADER_FRAC = 0.12


def is_decorative_image_block(block: dict[str, Any], page_height: float | None = None) -> bool:
    """Header/footer/watermark images are never question figures."""
    if block.get("type") != "image":
        return False
    if block.get("role") == "figure":
        return False  # explicitly allowlisted crop
    bbox = block.get("bbox")
    if not bbox or len(bbox) < 4:
        return True  # unknown geometry → treat as decorative
    x0, y0, x1, y1 = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    w, h = x1 - x0, y1 - y0
    ph = page_height or 842.0
    header_y = HEADER_FRAC * ph
    footer_y = ph * (1.0 - 0.08)
    if w < 35 or h < 35:
        return True
    if y1 <= header_y + 10:
        return True
    if y0 < header_y and h < ph * 0.22:
        return True
    if y0 >= footer_y - 10:
        return True
    if y1 > footer_y and h < ph * 0.15:
        return True
    if w * h < 5000:
        return True
    # Centered Adda-style watermark splash
    if 0.15 * ph < y0 < 0.45 * ph and h > 0.25 * ph and w > 0.4 * (x1 - x0 + w):
        if w > 250 and h > 200:
            return True
    return False


def has_allowlisted_figure(blocks: list[dict[str, Any]] | None) -> bool:
    if not blocks:
        return False
    for b in blocks:
        if b.get("type") != "image" or not b.get("asset"):
            continue
        if b.get("role") == "figure":
            return True
        if not is_decorative_image_block(b):
            return True
    return False


def has_substantive_images(blocks: list[dict[str, Any]] | None) -> bool:
    return has_allowlisted_figure(blocks)


def has_header_band_image(blocks: list[dict[str, Any]] | None, page_height: float = 842.0) -> bool:
    if not blocks:
        return False
    header_y = HEADER_FRAC * page_height
    for b in blocks:
        if b.get("type") != "image" or not b.get("asset"):
            continue
        if b.get("role") == "figure":
            continue
        bbox = b.get("bbox") or []
        if len(bbox) >= 4 and float(bbox[1]) < header_y:
            return True
    return False


def multi_question_bleed(text: str, q_num: int | None) -> bool:
    if not text or q_num is None:
        return False
    nums = {int(m) for m in MULTI_Q_MARKER.findall(text)}
    if q_num not in nums:
        return False
    return len(nums - {q_num}) >= 1


def looks_like_rearrangement_options(options: dict[str, str] | None) -> bool:
    if not options:
        return False
    vals = [str(v).strip() for v in options.values() if v]
    if any(NO_REARRANGEMENT_RE.search(v) for v in vals):
        return True
    return sum(1 for v in vals if PERM_OPTION_RE.match(v)) >= 2


def is_text_only_english(direction_text: str | None, stem: str, options: dict[str, str] | None) -> bool:
    blob = f"{direction_text or ''}\n{stem}"
    if TEXT_ONLY_ENGLISH_RE.search(blob):
        return True
    if looks_like_rearrangement_options(options):
        return True
    if SLASH_PARTS_RE.search(stem or "") and options:
        # Error spotting style letter opts
        vals = [str(v).strip() for v in options.values()]
        if vals and all(LETTER_ONLY_OPT.match(v) or v.lower().startswith("no error") for v in vals):
            return True
    return False


def needs_figure_stimulus(
    direction_text: str | None,
    stem: str,
    options: dict[str, str] | None = None,
) -> bool:
    """True only when a visual figure/table is required for the question to be solvable."""
    if is_text_only_english(direction_text, stem, options):
        return False
    blob = f"{direction_text or ''}\n{stem or ''}"
    if NEEDS_FIGURE_RE.search(blob):
        return True
    if MATH_BROKEN.match((stem or "").strip()):
        return True
    # Letter-only options for para jumble sentences in direction (stimulus is text, not figure)
    opt_vals = list((options or {}).values())
    if opt_vals and len(opt_vals) >= 4 and all(LETTER_ONLY_OPT.match(str(v).strip()) for v in opt_vals):
        if UPPER_STIMULUS.search(blob):
            return False  # textual (A)(B)(C) stimulus
        if NEEDS_FIGURE_RE.search(blob):
            return True
    return False


def sanitize_question_context(
    *,
    direction_text: str | None,
    stem: str,
    context: list[dict[str, Any]] | None,
    q_num: int | None = None,
) -> list[dict[str, Any]]:
    """Thin safety net: keep direction, allowlisted figures, drop logos and bleed."""
    out: list[dict[str, Any]] = []
    if direction_text:
        out.append({"type": "text", "text": direction_text.strip(), "role": "direction"})
    for block in context or []:
        if block.get("role") == "stem":
            continue
        if block.get("type") == "image":
            if is_decorative_image_block(block):
                continue
            if block.get("role") != "figure" and is_decorative_image_block(block):
                continue
            # Drop non-figure images unless they look non-decorative (legacy)
            if block.get("role") != "figure":
                continue
            if block.get("asset") and not any(b.get("asset") == block.get("asset") for b in out):
                out.append(dict(block))
            continue
        if block.get("type") in ("text", "table") and block.get("text"):
            txt = str(block["text"])
            if multi_question_bleed(txt, q_num):
                continue
            if direction_text and txt.strip() == direction_text.strip():
                continue
            if stem and txt.strip() == stem.strip():
                continue
            # Drop raw PDF page dumps that contain many Q markers
            if len(MULTI_Q_MARKER.findall(txt)) >= 2:
                continue
            out.append(dict(block))
    if stem and not any(b.get("role") == "stem" for b in out):
        out.append({"type": "text", "text": stem, "role": "stem"})
    return out


def context_blocks_to_text(blocks: list[dict[str, Any]] | None) -> str:
    if not blocks:
        return ""
    parts: list[str] = []
    for b in blocks:
        if b.get("type") == "text" and b.get("text"):
            parts.append(str(b["text"]))
        elif b.get("type") == "table" and b.get("text"):
            parts.append(str(b["text"]))
        elif b.get("type") == "image" and b.get("ocr_text"):
            parts.append(str(b["ocr_text"]))
    return " ".join(parts).strip()


def has_image_blocks(blocks: list[dict[str, Any]] | None) -> bool:
    return has_allowlisted_figure(blocks)


def assess_context(
    *,
    stem: str,
    options: dict[str, str],
    direction_text: str | None,
    context: list[dict[str, Any]] | None = None,
    q_num: int | None = None,
) -> tuple[str, list[str]]:
    """Return (context_status, context_issues). Logos never make a question complete."""
    issues: list[str] = []
    dtext = (direction_text or "").strip()
    # Ignore decorative images when judging
    clean_ctx = [
        b
        for b in (context or [])
        if not (b.get("type") == "image" and is_decorative_image_block(b))
    ]
    ctx_text = context_blocks_to_text(clean_ctx)
    combined = f"{dtext}\n{ctx_text}\n{stem}"
    opt_vals = list((options or {}).values())
    has_figure = has_allowlisted_figure(clean_ctx)
    text_only = is_text_only_english(direction_text, stem or "", options)
    wants_figure = needs_figure_stimulus(direction_text, stem or "", options)

    if has_header_band_image(context):
        issues.append("header_logo_image")

    if q_num is not None and multi_question_bleed(ctx_text, q_num):
        issues.append("multi_question_bleed")

    if SOLUTIONS_MARKERS.search(stem or "") or any(SOLUTIONS_MARKERS.search(str(v)) for v in opt_vals):
        issues.append("solutions_bleed")

    if opt_vals and any(OPTION_BLEED.search(str(v)) for v in opt_vals):
        issues.append("option_bleed")

    if len(options or {}) < 3 and stem and not has_figure:
        issues.append("option_structure")

    if opt_vals and len(opt_vals) >= 4 and all(LETTER_ONLY_OPT.match(str(v).strip()) for v in opt_vals):
        stimulus = dtext + ctx_text + (stem or "")
        if not UPPER_STIMULUS.search(stimulus) and not has_figure and not text_only:
            issues.append("letter_opts_no_stimulus")

    if wants_figure and not has_figure:
        issues.append("missing_figure")

    if MATH_BROKEN.match((stem or "").strip()) and not has_figure:
        issues.append("broken_math_text")

    if not stem or len(stem.strip()) < 8:
        if not has_figure:
            issues.append("tiny_stem")

    # Logos must never clear other issues
    hard = {
        "multi_question_bleed",
        "solutions_bleed",
        "missing_figure",
        "header_logo_image",
        "tiny_stem",
        "broken_math_text",
        "letter_opts_no_stimulus",
    }
    hard_hit = [i for i in issues if i in hard]

    if not issues:
        return "complete", []

    # Text-only English with intact stem/options is complete even without images
    if text_only and not hard_hit and "option_structure" not in issues:
        soft = [i for i in issues if i not in ("short_shared_context",)]
        if not soft or soft == ["option_bleed"]:
            return "complete", issues if soft else []

    if hard_hit:
        return "missing_context", issues

    if has_figure and set(issues) <= {"option_bleed", "option_structure"}:
        return "partial", issues

    if issues:
        return "partial" if has_figure else "missing_context", issues
    return "complete", []


def should_synthesize_cloze_stem(direction_text: str | None, raw_q: str) -> bool:
    """Only invent blank stem when direction clearly has cloze markers."""
    if not direction_text:
        return False
    if not BLANK_MARKER.search(direction_text):
        return False
    if re.search(r"\([a-e]\)\s", raw_q, re.I):
        return True
    stem_part = raw_q.strip()
    return not stem_part or len(stem_part) < 15

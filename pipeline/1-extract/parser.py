#!/usr/bin/env python3
"""Parse the well-formed exam PDFs into questions.

Scoped to the `easy` bucket: two-column Adda247 layouts with a clean text layer.
Everything here is a rule that a paper in that bucket actually needs -- the
awkward cases live in `medium`/`hard` and are deliberately out of scope.

    python3 pipeline/1-extract/parser.py corpus/pdf/IBPS
    python3 pipeline/1-extract/parser.py corpus/pdf/IBPS --batch 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parents[2]
REMAINING = REPO / "corpus" / "remaining"
DONE = REPO / "corpus" / "done"

HEADER_FRAC = 0.12
FOOTER_FRAC = 0.08

# Bengali only. Devanagari is deliberately NOT here: a Hindi-only stem with
# English options is a question this bank keeps, and treating the two scripts
# alike dropped 40 of batch 1.
BENGALI_RE = re.compile(r"[ঀ-৿]")
NOISE_RE = re.compile(
    # The page number often shares the footer line -- "11 Visit: adda247.com" --
    # so anchoring on the domain alone left the whole footer in the text, where
    # it ran on into a passage's direction and into option (e).
    r"(?i)^(?:\d{1,3}\s+)?"
    r"(?:adda247.*|www\.[a-z0-9.\-]+.*|bankersadda\.com.*|sscadda\.com.*|"
    r"careerpower\.in.*|store\.adda247\.com.*|(?:web)?site\s*:.*|visit\s*:.*|"
    r"email:.*|info@[a-z0-9.\-]+.*|page\s*\d+.*|"
    r"sbi po pre \d{4} question paper.*)$"
)

# The `(?!\d)` guard applies only to the bare form -- with an explicit "Q" there
# is no ambiguity, and "Q130.1: 23x+y" is a real question whose stem starts with
# a digit, while a bare "30.2" is an option value.
QUESTION_RE = re.compile(
    r"(?im)^\s*(?:(?:Question\s+|Q\s*\.?\s*)([1-9]\d{0,2})\s*[.):]"
    r"|([1-9]\d{0,2})\s*[.):](?!\d))\s*"
)
DIRECTION_RE = re.compile(r"(?is)Directions?\s*\(\s*(\d+)\s*[-–—to]+\s*(\d+)\s*\)\s*:?\s*")
# Some papers never number their directions -- one paper writes 50 of these and
# not a single "Directions (111-115):" -- so the questions they cover have to be
# taken from position instead of from a stated range.
UNNUMBERED_DIRECTION_RE = re.compile(
    r"(?im)^\s*(?:Directions?\s*:|"
    r"Read the (?:given|following)|Study the following|"
    r"In (?:the|each of the) following|What should come|"
    r"Find the wrong|Answer the following|Solve the following)"
)
OPTION_RE = re.compile(r"\(\s*([a-e])\s*\)\s*")
UPPER_OPTION_RE = re.compile(r"\(\s*([A-E])\s*\)\s*")
# Adda247 SBI PO memory papers print "A) 12  B) 15" -- letter + close paren,
# no open paren. `(?<!\()` keeps cloze blanks "(A)" and roman "(I)" from being
# read as the option list; `(?<![A-Za-z])` keeps "area)" out.
BARE_UPPER_OPTION_RE = re.compile(r"(?<!\()(?<![A-Za-z])([A-E])\)\s+")
# Watermark that lands in the body, not on its own footer line.
PAPER_MARK_RE = re.compile(r"\bSBI PO PRE \d{4} QUESTION PAPER\b", re.I)
# "(a)/ segment" -- error spotting, where the options are the sentence's parts
SEGMENT_RE = re.compile(r"\(\s*([a-e])\s*\)\s*[.,;]?\s*(?:/|(?=\s*$))")
BLEED_RE = re.compile(
    # "Directions (32-34):" and "Directions 32-34:" are the same header;
    # requiring the paren let the unparenthesised form bleed into option (e).
    r"(?is)\s*(?:Directions?\s*[\(\d]|Q\s*\d+\.|Question\s+\d+|www\.[a-z0-9.\-]+|"
    # "Ans.(b)" printed after each question's options is an inline answer key,
    # not part of option (e). It bled into the last option of all 100 questions
    # in one paper -- "155.56% Ans." -- which is a wrong option that looks real.
    # \b matters: case-insensitive "ans." also matched inside "plans. (a)",
    # cutting a stem at "improvement pl" and dropping all five options.
    r"\bAns\s*\.\s*\(?\s*[a-e]\s*\)?|"
    r"Answer\s*:|Solution\s*:).*$"
)
SOLUTIONS_RE = re.compile(r"(?im)^\s*(?:SOLUTIONS?|ANSWER\s+KEY|DETAILED\s+SOLUTIONS?)\s*$")
# Files with no questions to take: a solutions-only PDF, or the Hindi edition of
# a paper already held in English. Parsed anyway they yield 0-1 questions and
# burn a slot in the batch.
SKIP_NAME_RE = re.compile(r"(?i)(?:^|[-_ ])(?:solutions?|sol|answer[-_ ]?key|hindi|hn)(?:[-_ .]|$)")

# PyMuPDF sets bit 0 of a span's flags for superscript text. Without this an
# exponent arrives flat -- "2x2 - 3x + 1 = 0" -- where the trailing 2 reads as
# multiplication rather than a square, and nothing downstream can tell them
# apart.
SUPERSCRIPT_FLAG = 1
# What may sit above a fraction bar: a number, or a radical like "√16".
NUMERATOR_RE = re.compile(r"[√∛]?\s*\d{1,4}\s*%?")
SUPERSCRIPT_MAP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
ORDINAL_RE = re.compile(r"(?i)st|nd|rd|th")
# Mathematical alphanumerics: "𝑥", and "𝟏" which is a digit no \d matches. They
# arrive from equation-set papers, so fold them before anything reads the text
# -- to_latex works in \d, and a bold 1 left it silently declining to convert.
MATH_ALNUM = re.compile(r"[\U0001D400-\U0001D7FF]")


def normalise(text: str) -> str:
    return MATH_ALNUM.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), text)
# What an ordinal suffix may follow: "28th June", and "IVth term of the series".
ORDINAL_STEM_RE = re.compile(r"(?:\d|\b[IVXLCDM]+)$")


def line_text(line: dict) -> str:
    """A line's text, with superscript spans raised.

    The flag alone is not trusted: on stacked-fraction lines PyMuPDF marks the
    WHOLE following run (" × 4 + ? = 35", full body size) as superscript, and
    raising it garbled ~14 stems into "⁺ ? ⁼ ³⁵". A real exponent also prints
    small -- measured 8pt against 11-12pt body -- so both signals are required,
    plus a length cap: an exponent is a couple of characters, not a clause.
    """
    spans = line.get("spans") or []
    body = max((s.get("size", 0) for s in spans), default=0)

    def is_sup(span):
        text = span.get("text", "")
        # A radicand prints small and carries the superscript flag too --
        # "√16" became "^{1}⁶" and "√1331" became "^(\sqrt{1331})". A span
        # holding a radical sign is never an exponent.
        if "√" in text or "∛" in text:
            return False
        return (text.strip()
                and span.get("flags", 0) & SUPERSCRIPT_FLAG
                and span.get("size", body) <= 0.85 * body)

    # Adjacent superscript spans are ONE exponent. "2x+3y" arrives as four
    # spans, and judged one at a time each is short enough for the glyph path,
    # giving "^{2}x⁺^{3}y". Merge the run first, then choose the form once.
    out, i = [], 0
    while i < len(spans):
        if not is_sup(spans[i]):
            out.append(spans[i].get("text", ""))
            i += 1
            continue
        j = i
        while j < len(spans) and is_sup(spans[j]):
            j += 1
        text = "".join(s.get("text", "") for s in spans[i:j]).strip()
        i = j
        # An ordinal suffix is typography, not an exponent. These papers set the
        # "th" of "28th June" raised and small, so it passed both signals and
        # came out "28^(th) June" -- 141 dates across two batches against 2 real
        # exponents. A date is prose and has to read as written.
        if ORDINAL_RE.fullmatch(text) and ORDINAL_STEM_RE.search("".join(out).rstrip()):
            out.append(text)
            continue
        # Short exponents become glyphs; anything longer becomes "^(...)"
        # whole. A real expression exponent exists -- "(?)^(4×16÷32+1)" -- and
        # translating it char-by-char would emit mixed garbage.
        raised = text.translate(SUPERSCRIPT_MAP)
        if len(text) <= 3 and raised != text:
            out.append(raised)
        else:
            out.append(f"^({text.strip('()')})")
    return normalise("".join(out))


def find_gutter(blocks: list[dict], width: float) -> float | None:
    """x of the column gutter, or None for a single-column page.

    Text blocks only. A centred watermark straddles the gutter and, counted as
    content, makes it undetectable -- and no gutter means plain top-to-bottom
    order, which interleaves the two columns and severs stems from options.
    """
    blocks = [b for b in blocks if b.get("type") == 0]
    if len(blocks) < 4:
        return None

    def area(b):
        x0, y0, x1, y1 = b["bbox"]
        return max(0.0, x1 - x0) * max(0.0, y1 - y0)

    total = sum(area(b) for b in blocks)
    if total <= 0:
        return None
    best = None
    for cut in range(int(width * 0.40), int(width * 0.60), 3):
        crossing = sum(1 for b in blocks if b["bbox"][0] < cut - 2 and b["bbox"][2] > cut + 2)
        left = sum(area(b) for b in blocks if b["bbox"][2] <= cut + 2)
        right = sum(area(b) for b in blocks if b["bbox"][0] >= cut - 2)
        if crossing <= max(1, int(0.15 * len(blocks))) and left >= 0.15 * total and right >= 0.15 * total:
            score = (-crossing, min(left, right))
            if best is None or score > best[0]:
                best = (score, cut)
    return best[1] if best else None


ROOT_INDEX = {"2": "√", "3": "∛", "4": "∜"}


def merge_span_fractions(blocks: list[dict], bars) -> None:
    """Join a stacked fraction whose numerator sits mid-line, in place.

    join_fractions works on whole lines, which covers a numerator printed on a
    line of its own. It cannot reach "50% of 128 + √16" over "2", where the
    numerator is the last SPAN of a line and the denominator the first span of
    the next -- that came out as "\\sqrt{16} 2 \\times 4", where the division
    is simply missing and the stem reads as a different sum.

    Mutates the span dicts: the numerator gains "num/den", the denominator is
    blanked. Runs before lines are built, so the line-level pass then sees an
    already-merged span and does nothing.
    """
    spans = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            for span in line.get("spans") or []:
                if span.get("text", "").strip():
                    spans.append(span)
    if not spans:
        return
    body = max(s.get("size", 0) for s in spans)

    def centre(s):
        return (s["bbox"][1] + s["bbox"][3]) / 2

    used: set[int] = set()
    for i, num in enumerate(spans):
        text = num["text"].strip()
        if id(num) in used or not NUMERATOR_RE.fullmatch(text):
            continue
        if num.get("size", body) > 0.9 * body:
            continue
        best, best_gap = None, 1e9
        for den in spans:
            if den is num or id(den) in used:
                continue
            gap = centre(den) - centre(num)
            if not (0 < gap < 20):
                continue
            nb, db = num["bbox"], den["bbox"]
            if min(nb[2], db[2]) - max(nb[0], db[0]) < 0.4 * min(nb[2] - nb[0], db[2] - db[0]):
                continue
            # A radical's overbar sits on the radicand's own top edge and is
            # not a division; without this the cube-root index "3" merges onto
            # "√1331" as "3/√1331".
            radical = "√" in den["text"] or "∛" in den["text"]
            if not any(centre(num) < by < centre(den)
                       and not (radical and abs(by - db[1]) <= 3.0)
                       and min(nb[2], bx1) - max(nb[0], bx0) > 1.0
                       for by, bx0, bx1 in bars):
                continue
            if gap < best_gap:
                best, best_gap = den, gap
        if best is None:
            continue
        used.add(id(num))
        used.add(id(best))
        # The joined fraction goes where the DENOMINATOR sits, not the
        # numerator. The numerator prints on the row above, outside the reading
        # flow: "(b) 87 1/3 %" has its 87 and % on the denominator's line, and
        # emitting at the numerator put the fraction before the previous option
        # -- "(b) 87 1/3 1/3 %" beside "(c) 83 % 2/3".
        best["text"] = f"{text}/{best['text'].strip()}"
        num["text"] = ""


def apply_root_index(blocks: list[dict], bars) -> None:
    """Fold a root index printed above the radical into one glyph.

    "∛1331" prints as a small "3" above "√1331"; left alone the 3 drifts into
    the stem as a loose number ("\\sqrt{1331} 3 11 + ...").
    """
    spans = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            for span in line.get("spans") or []:
                if span.get("text", "").strip():
                    spans.append(span)
    for idx in spans:
        text = idx["text"].strip()
        if text not in ROOT_INDEX:
            continue
        for rad in spans:
            if rad is idx or not rad["text"].lstrip().startswith("√"):
                continue
            ib, rb = idx["bbox"], rad["bbox"]
            if not (0 < (rb[1] + rb[3]) / 2 - (ib[1] + ib[3]) / 2 < 14):
                continue
            if min(ib[2], rb[2]) - max(ib[0], rb[0]) < -6:
                continue
            rad["text"] = rad["text"].replace("√", ROOT_INDEX[text], 1)
            idx["text"] = ""
            break


def page_lines(page: fitz.Page, bars=()):
    """The page's text as lines, in reading order, boilerplate removed.

    Fractions and rows are resolved per COLUMN. Doing either across the whole
    page merges a left-column line with the right-column line beside it, which
    cost 56 questions when it was applied globally.
    """
    blocks = [b for b in page.get_text("dict").get("blocks") or [] if b.get("type") == 0]
    apply_root_index(blocks, bars)
    merge_span_fractions(blocks, bars)
    gutter = find_gutter(blocks, page.rect.width)
    top = page.rect.y0 + HEADER_FRAC * page.rect.height
    bottom = page.rect.y1 - FOOTER_FRAC * page.rect.height

    blocks.sort(key=lambda b: (0 if gutter is None or b["bbox"][0] < gutter else 1,
                               round(b["bbox"][1], 1), round(b["bbox"][0], 1)))

    # Reading order comes from the blocks; fractions are then resolved across
    # the whole page, because a numerator and its denominator regularly sit in
    # different blocks.
    lines = []
    for block in blocks:
        for line in block.get("lines") or []:
            text = line_text(line).strip()
            if not text or NOISE_RE.match(text):
                continue
            bbox = tuple(float(v) for v in line["bbox"])
            # A bare number is a page number only in the header/footer. In the
            # body it is a stacked fraction's numerator, and dropping it turns
            # "33 1/3 %" into "33 3 %".
            if text.isdigit() and (bbox[3] <= top or bbox[1] >= bottom):
                continue
            lines.append((bbox, text))

    merged, flags = join_fractions(lines, bars)
    return group_rows(merged, flags)


def group_rows(lines, fraction_rows=frozenset()):
    """Pull the rest of a maths row into the line that carries its fraction.

    A maths stem prints as several boxes across one row -- "15/100 x", "Q79.",
    "200/700 x? = 240" -- often in different blocks, and the first can sit
    slightly higher than the question number, so in reading order it lands
    before the anchor and attaches to the previous question.

    Only lines that received a fraction pull their neighbours in, and every
    other line keeps its position. Re-sorting the page by y instead broke the
    ordering that keeps a question with its own options where the columns
    interleave, and cost 5 option lists; grouping every y-band cost 14 whole
    questions. An "(a) …" line is an option and is never pulled in.
    """
    if not lines or not fraction_rows:
        return lines
    heights = sorted(b[3] - b[1] for b, _ in lines)
    body = heights[len(heights) // 2]
    tol = max(3.0, 0.45 * body)

    def centre(b):
        return (b[1] + b[3]) / 2

    taken: set[int] = set()
    merged: dict[int, list] = {}
    for i in sorted(fraction_rows):
        if i in taken:
            continue
        members = [(lines[i][0], lines[i][1], i)]
        for j, (bj, tj) in enumerate(lines):
            if j == i or j in taken or j in fraction_rows or OPTION_RE.match(tj):
                continue
            if abs(centre(bj) - centre(lines[i][0])) <= tol:
                members.append((bj, tj, j))
                taken.add(j)
        if len(members) > 1:
            members.sort(key=lambda m: m[0][0])
            merged[i] = members

    out = []
    for i, (bbox, text) in enumerate(lines):
        if i in taken:
            continue
        if i in merged:
            group = merged[i]
            box = (min(m[0][0] for m in group), min(m[0][1] for m in group),
                   max(m[0][2] for m in group), max(m[0][3] for m in group))
            out.append((box, " ".join(m[1] for m in group)))
        else:
            out.append((bbox, text))
    return out


def fraction_bars(page: fitz.Page) -> list[tuple[float, float, float]]:
    """Horizontal rules on the page, as (y, x0, x1) -- the bars of fractions."""
    bars = []
    for drawing in page.get_drawings():
        for item in drawing.get("items") or []:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) <= 1.0 and abs(p2.x - p1.x) >= 4.0:
                    bars.append((p1.y, min(p1.x, p2.x), max(p1.x, p2.x)))
            elif item[0] == "re":
                r = item[1]
                if r.height <= 2.0 and r.width >= 4.0:
                    bars.append((r.y0, r.x0, r.x1))
    return bars


def join_fractions(lines, bars=()):
    """Rejoin a stacked fraction into "num/den" on the denominator's line.

        15        200                    15/100 x 200/700 x ? = 240
       --- x 100 x --- x ? = 240   ->
       100        700

    A numerator prints at roughly half body height and sits above a denominator
    it overlaps horizontally. The two boxes often overlap *vertically* too, so
    adjacency cannot be tested with "ends before the other begins" -- compare
    centres instead. Left alone the numerators drift off as loose digits and
    attach to the wrong question, and "700 x? = 240" is what reaches the JSON.
    """
    if not lines:
        return lines, set()
    heights = sorted(b[3] - b[1] for b, _ in lines)
    body = heights[len(heights) // 2]
    text = [t for _, t in lines]
    drop: set[int] = set()
    merged: set[int] = set()

    def centre(b):
        return (b[1] + b[3]) / 2

    for i, (bi, ti) in enumerate(lines):
        # A numerator is a short maths token, not only digits: "√16" over "2"
        # and "∛1331" over "11" are both real fractions in these papers.
        token = ti.strip()
        if not (NUMERATOR_RE.fullmatch(token) and (bi[3] - bi[1]) < 0.8 * body):
            continue
        best, best_gap = None, 1e9
        for j, (bj, _) in enumerate(lines):
            if j == i or j in drop or (bj[3] - bj[1]) < 0.8 * body:
                continue
            gap = centre(bj) - centre(bi)
            if not (0 < gap < 20):
                continue
            overlap = min(bi[2], bj[2]) - max(bi[0], bj[0])
            if overlap < 0.5 * min(bi[2] - bi[0], bj[2] - bj[0]):
                continue
            # A bar between the two is what makes it a fraction. Without this a
            # question number sitting above a maths line ("54." over the stem)
            # merges into it and the question disappears.
            # A radical's overbar sits ON the radicand's top edge, and would
            # otherwise read as a fraction bar -- merging a cube-root index "3"
            # onto "√1331" as "3/√1331". Only radicals draw one, so the guard
            # is scoped to them and ordinary fractions are untouched.
            radical = "√" in text[j] or "∛" in text[j]
            if not any(centre(bi) < by < centre(bj)
                       and not (radical and abs(by - bj[1]) <= 3.0)
                       and min(bi[2], bx1) - max(bi[0], bx0) > 1.0
                       for by, bx0, bx1 in bars):
                continue
            if gap < best_gap:
                best, best_gap = j, gap
        if best is not None:
            text[best] = f"{ti.strip()}/{text[best]}"
            drop.add(i)
            merged.add(best)
    kept = [(lines[i][0], text[i]) for i in range(len(lines)) if i not in drop]
    flags = {new for new, old in enumerate(
        [i for i in range(len(lines)) if i not in drop]) if old in merged}
    return kept, flags


# Devanagari and Bengali. A bilingual paper appends the translation to the
# English, and only Devanagari was cut -- an SBI Clerk paper printed its
# Bengali in ShonarBangla, a legacy font whose text layer does not even
# decode to real words, and 63 of its 98 questions carried the mojibake.
DEV_RUN_RE = re.compile(r"[ऀ-ॿঀ-৿][ऀ-ॿঀ-৿\s।]*")


OPERATOR_SPACE_RE = re.compile(r"\s*([×÷≥≤=<>+])\s*")


def space_maths(text: str) -> str:
    """One space each side of an operator.

    The PDF sets these tight -- "700 ×? = 240" -- and a reader cannot tell the
    "?" from part of the operator. Minus is left alone: it is also a hyphen.
    """
    if not text:
        return text
    return " ".join(OPERATOR_SPACE_RE.sub(r" \1 ", text).split())


MATHY_RE = re.compile(r"[=×÷√∛∜≥≤]|\d+\s*/\s*\d+|\b\d+\s*\^")
# Roots are converted BEFORE fractions, and a converted root may then be a
# numerator. Doing fractions first turned "√16/2" into "√\frac{16}{2}" -- that
# is sqrt(16/2) = 2.83, not sqrt(16)/2 = 2. A silently different sum.
ROOT_RE = re.compile(r"([√∛∜])\s*([A-Za-z0-9]+)")
ROOT_ORDER = {"√": "", "∛": "[3]", "∜": "[4]"}
MIXED_RE = re.compile(r"(\d+)\s+(\\frac\{\d+\}\{\d+\})")
FRACTION_RE = re.compile(
    r"(?<![\w/])(\\sqrt(?:\[\d\])?\{[^{}]+\}|\d+)\s*/\s*"
    r"(\\sqrt(?:\[\d\])?\{[^{}]+\}|\d+)(?![\w/])")
SUPER = {"²": "2", "³": "3", "⁴": "4", "¹": "1", "⁰": "0"}
SUPER_RE = re.compile(r"([²³⁴¹⁰])")


def to_latex(text: str) -> str | None:
    """A LaTeX form of a maths expression, or None if it isn't one.

    "15/100 x 200/700 x ? = 240" is readable but flat -- an app rendering it
    shows a slash where the paper shows a stacked fraction. The plain text stays
    in `stem`; this is the parallel form for anything that can render maths.
    """
    if not text or not MATHY_RE.search(text):
        return None
    out = ROOT_RE.sub(lambda m: f"\\sqrt{ROOT_ORDER[m.group(1)]}{{{m.group(2)}}}", text)
    out = FRACTION_RE.sub(r"\\frac{\1}{\2}", out)
    out = SUPER_RE.sub(lambda m: f"^{{{SUPER[m.group(1)]}}}", out)
    out = out.replace("×", r"\times ").replace("÷", r"\div ")
    out = out.replace("≥", r"\geq ").replace("≤", r"\leq ")
    out = " ".join(out.split())
    # "87 \frac{1}{3} %" is a MIXED number, 87 and a third, not 87 times a
    # third -- the space reads as ambiguous to anyone looking at the JSON.
    # Closing it up is the standard mixed-number form.
    out = MIXED_RE.sub(r"\1\2", out)
    # A bare % is LaTeX's comment character: everything after it on the line
    # disappears when rendered. 55 values carried one.
    out = re.sub(r"(?<!\\)%", r"\\%", out)
    return out if out != text else None


def strip_hindi(text: str) -> str:
    """Remove the Devanagari, keeping the English wherever it sits.

    Cutting at the first Devanagari character is right when the Hindi is simply
    appended, but wrong when the two interleave -- a direction whose prose is
    Hindi and whose "(a)…(e)" labels are Latin lost the labels too, and came out
    as the empty string.
    """
    if not text:
        return text
    out = DEV_RUN_RE.sub(" ", text)
    return " ".join(out.split()).strip(" \t\n-/|,;")


def image_regions(pdf: Path) -> dict[int, bool]:
    """Question numbers whose block on the page contains an embedded image.

    Simplification sets print the equation as a small inline picture beside
    "Q56." and only the options as text; some print the option VALUES as
    pictures, leaving "(a) (b) (c) (d) (e)" with nothing behind them. 45 of 54
    incomplete questions in one batch were this. There is no text to recover --
    the honest output is has_image, so the text-only filter drops them instead
    of the parse being blamed.

    A question's region runs from its anchor line to the next anchor in the
    same column. Only a region with an image qualifies, and the caller applies
    it only where text is actually missing -- a DI chart sits in the region of
    the question *before* the set, and must not flag a complete one.
    """
    found: dict[int, bool] = {}
    doc = fitz.open(pdf)
    try:
        for page in doc:
            blocks = page.get_text("dict").get("blocks") or []
            images = [b["bbox"] for b in blocks if b.get("type") == 1]
            if not images:
                continue
            gutter = find_gutter(blocks, page.rect.width)
            anchors = []
            for b in blocks:
                if b.get("type") != 0:
                    continue
                for line in b.get("lines") or []:
                    text = "".join(s.get("text", "") for s in line.get("spans") or [])
                    m = QUESTION_RE.match(text)
                    if m:
                        x0, y0, x1, y1 = line["bbox"]
                        col = 0 if gutter is None or x0 < gutter else 1
                        anchors.append((col, y0, int(m.group(1) or m.group(2))))
            anchors.sort()
            for i, (col, y0, num) in enumerate(anchors):
                nxt = next((y for c, y, _ in anchors[i + 1:] if c == col), page.rect.y1)
                for ix0, iy0, ix1, iy1 in images:
                    icol = 0 if gutter is None or ix0 < gutter else 1
                    if icol == col and y0 - 4 <= (iy0 + iy1) / 2 <= nxt:
                        found[num] = True
                        break
    finally:
        doc.close()
    return found


def read_text(pdf: Path) -> str:
    doc = fitz.open(pdf)
    try:
        chunks = []
        for page in doc:
            lines = page_lines(page, fraction_bars(page))
            if lines:
                chunks.append("\n".join(t for _, t in lines))
        body = "\n\n".join(chunks)
    finally:
        doc.close()
    m = SOLUTIONS_RE.search(body)
    return body[: m.start()] if m else body


def _complete_opts(opts: dict) -> bool:
    keys = list(opts)
    return keys == list("abcde") or keys == list("abcd")


def _extract_option_run(block: str, matches) -> tuple[str, dict[str, str]]:
    """Stem + options from a sequence of labelled matches in `block`."""
    start_at = 0
    for i in range(len(matches)):
        run, expect = [], "a"
        j = i
        while j < len(matches) and matches[j].group(1).lower() == expect:
            run.append(expect)
            expect = chr(ord(expect) + 1)
            j += 1
        if run in (list("abcde"), list("abcd")):
            start_at = i

    stem = " ".join(block[: matches[start_at].start()].split())
    opts = {}
    run = matches[start_at:]
    # Is this a run of short, single-line options? Judged from all but the
    # last, because the last is the one that collects stray text.
    heads = [block[run[i].end(): run[i + 1].start()] for i in range(len(run) - 1)]
    single_line_run = bool(heads) and all(
        h.strip() and "\n" not in h.strip() and len(h.split()) <= 6 for h in heads)

    for idx, mm in enumerate(run):
        label = mm.group(1).lower()
        if label == "a" and opts:
            break
        end = run[idx + 1].start() if idx + 1 < len(run) else len(block)
        raw = block[mm.end(): end]
        # Unrelated text can land after the LAST option when columns interleave
        # -- a DI direction's tail rode along on "(e) 9.09%" with no header for
        # BLEED_RE to match. Where every earlier option is one short line, this
        # one is too, so cut at the first break.
        if single_line_run and idx == len(run) - 1 and "\n" in raw.strip():
            raw = raw.strip().split("\n", 1)[0]
        value = " ".join(raw.split()).strip(" ;-")
        if value:
            opts[label] = value
        if label == "e":
            break
    return stem, opts


def _uppercase_starters(block: str) -> tuple[str, dict[str, str]] | None:
    # "STARTERS" connector questions print three UPPERCASE options,
    # "(A) Because… (B) Considering… (C) Even though…". Uppercase is
    # normally a stimulus label, so this runs only when no lowercase run
    # exists at all -- a para-jumble has both and keeps its (a)-(e).
    upper = list(UPPER_OPTION_RE.finditer(block))
    labels = [m.group(1) for m in upper]
    if labels[:3] != ["A", "B", "C"]:
        return None
    opts, stem = {}, " ".join(block[: upper[0].start()].split())
    run = upper[: 5 if labels[:5] == list("ABCDE") else
                  4 if labels[:4] == list("ABCD") else 3]
    for i, m in enumerate(run):
        end = run[i + 1].start() if i + 1 < len(run) else len(block)
        value = " ".join(block[m.end(): end].split()).strip(" ;-")
        if value:
            opts[m.group(1).lower()] = value
    if len(opts) == len(run):
        return stem, opts
    return None


def split_options(block: str) -> tuple[str, dict[str, str]]:
    block = PAPER_MARK_RE.sub(" ", BLEED_RE.sub("", block)).strip()

    # Error spotting first: its "(a)/ meet to discuss" has no space after the
    # label, so the ordinary option split matches nothing.
    parts = list(SEGMENT_RE.finditer(block))
    if [p.group(1).lower() for p in parts] in (list("abcde"), list("abcd")):
        opts, ok = {}, True
        for idx, mm in enumerate(parts):
            start = parts[idx - 1].end() if idx else 0
            seg = " ".join(block[start: mm.start()].split()).strip(" /;-")
            if not seg:
                ok = False
                break
            opts[mm.group(1).lower()] = seg
        if ok:
            return " ".join(block.split()), opts

    matches = list(OPTION_RE.finditer(block))
    paren_stem, paren_opts = (
        _extract_option_run(block, matches) if matches
        else (" ".join(block.split()), {}))
    # A complete (a)-(e) wins. An incomplete one -- often a stray "(e)" in
    # "choose option (e)" -- is held back so A) B) C) D) E) can be tried.
    if _complete_opts(paren_opts):
        return paren_stem, paren_opts

    # A) B) C) D) E) before "(A) Because": a cloze blank "(A)" plus a real
    # A)-E) list must keep the list, not treat the blank as a starter option.
    bare = list(BARE_UPPER_OPTION_RE.finditer(block))
    if bare:
        stem, opts = _extract_option_run(block, bare)
        if _complete_opts(opts):
            return stem, opts

    upper = _uppercase_starters(block)
    if upper:
        return upper

    if paren_opts:
        return paren_stem, paren_opts
    return " ".join(block.split()), {}


BANKS = [("NABARD", r"\bnabard\b"), ("SIDBI", r"\bsidbi\b"), ("IBPS", r"\bibps\b"),
         ("SBI", r"\bsbi\b"), ("RBI", r"\brbi\b"), ("LIC", r"\blic\b")]
ROLES = [("RRB", r"\brrb\b"), ("Clerk", r"\bclerk\b"), ("PO", r"\b(?:po|probationary)\b"),
         ("SO", r"\b(?:so|specialist)\b"), ("Assistant", r"\bassistant\b"),
         ("Grade_B", r"\bgrade[\s._-]*b\b")]
YEAR_RE = re.compile(r"\b(20(?:1\d|2\d))\b")


def meta_from_text(blob: str) -> dict:
    """Bank, role, stage and year named anywhere in `blob`.

    No `shift`: it is unknowable for most of these papers -- they are practice
    compilations rather than one sitting -- and carrying an "unknown_shift"
    placeholder around only produced noise.
    """

    def first(pairs):
        for label, pat in pairs:
            if re.search(pat, blob, re.I):
                return label
        return None

    bank = first(BANKS)
    role = "RRB" if bank == "IBPS" and re.search(r"\brrb\b", blob, re.I) else first(ROLES)
    stage = ("Mains" if re.search(r"\bmains?\b", blob, re.I)
             else "Prelims" if re.search(r"\b(?:prelims?|pre)\b", blob, re.I) else None)
    years = YEAR_RE.findall(blob)
    return {
        "bank": bank,
        "role": role,
        "exam_type": stage,
        "year": int(years[0]) if years else None,
        "memory_based": bool(re.search(r"memory[\s._-]*based", blob, re.I)),
    }


def paper_meta(pdf: Path, text: str) -> dict:
    """From the filename plus the title the PDF prints on page 1.

    A `<pdf>.meta.json` sidecar wins where it has a value: that is where
    research.py writes what it found, and without this the search results would
    have nowhere to land.
    """
    name = re.sub(r"[\s._\-]+", " ", pdf.stem)
    meta = meta_from_text(name)
    # Page 1 fills only what the filename left empty. That text is question
    # content as often as it is a title: one PO paper opens on an arrangement
    # set over "CEO, MD, DGM, AGM, Manager and Clerk", and the role came out
    # Clerk on all 115 of its questions.
    body = meta_from_text(f"{name} {text[:400]}")
    for key, value in body.items():
        if not meta.get(key):
            meta[key] = value
    side = pdf.with_suffix(pdf.suffix + ".meta.json")
    if side.is_file():
        try:
            found = json.loads(side.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return meta
        for key in ("bank", "role", "exam_type", "year"):
            value = found.get(key) or found.get("stage" if key == "exam_type" else key)
            if value and not meta.get(key):
                meta[key] = int(value) if key == "year" and str(value).isdigit() else value
    return meta


def options_from_direction(direction: str) -> dict[str, str]:
    """The five choices a whole set shares, stated once in its direction.

    Quadratic-comparison and inequality sets print "give answer (a) if x > y
    (b) if x < y …" in the direction and then only the equations under each
    number, so the questions themselves carry no options at all.
    """
    if not direction:
        return {}
    matches = list(OPTION_RE.finditer(direction))
    labels = [m.group(1).lower() for m in matches]
    if labels[:5] != list("abcde"):
        return {}
    opts = {}
    for i, m in enumerate(matches[:5]):
        end = matches[i + 1].start() if i + 1 < 5 else len(direction)
        value = " ".join(direction[m.end(): end].split()).strip(" ;-")
        if not value:
            return {}
        opts[m.group(1).lower()] = value
    return opts


def unreadable(stem: str, opts: dict | None = None,
               bengali_paper: bool = False) -> bool:
    """Left in a script this bank cannot use, after the strip already ran.

    strip_hindi takes the translation off a bilingual question and keeps the
    English. A stem still holding Devanagari or Bengali afterwards had no
    English to keep -- the fallbacks around it deliberately restore the raw text
    rather than ship an empty stem, so it arrives here intact.

    One SBI Clerk paper prints 31 of its 98 questions in Bengali only, set in
    ShonarBangla, whose text layer decodes only in part: "শুধুমাত্র" survives,
    but "যদি" comes out as "যশি" and "বিবৃতি" as "শব্ব্তশি". Those are not the
    words on the page, and 29 of the 31 carry a full option set -- so every gate
    passes them and the defect ships looking complete.

    The options count too: where stripping an option would empty it the raw text
    is kept deliberately, so a question can read as English and still offer five
    Bengali answers. And what the strip leaves behind is sometimes only
    punctuation -- ": : I. , II." is the whole of one syllogism stem -- so a
    non-empty stem with no word and no number in it is unreadable as well. A
    blank stem is not: an error-spotting set states its task in the direction.
    """
    blob = (stem or "") + " " + " ".join((opts or {}).values())
    if BENGALI_RE.search(blob):
        return True
    # What the strip leaves of a Bengali-only question is sometimes punctuation
    # alone -- ": : I. , II." is one whole syllogism stem. Short, wordless and
    # numberless together; a long stem in another script is a real question and
    # stays. A blank stem is not caught either: an error-spotting set states its
    # task in the direction and prints nothing but its five candidates.
    stem = (stem or "").strip()
    if not bengali_paper or not stem or len(stem) > 24:
        return False
    return not (re.search(r"[A-Za-z]{3,}", stem) or re.search(r"\d", stem))


def not_supplied(stem: str, opts: dict, direction: str | None) -> bool:
    """Is something missing that the paper actually printed somewhere?

    Not the same as "has an empty field". Options are never optional -- a
    question with none is unanswerable. A stem is, when a direction carries the
    task for the whole set: error-spotting sets print "choose the sentence with
    a grammatical error" once and then nothing but the five candidates under
    each number.

    Used both by resolve_image_bodied and to score a batch, so the two can
    never disagree about what "complete" means.
    """
    return not opts or not (stem or direction)


def resolve_image_bodied(questions) -> None:
    """Mark the questions that are a picture rather than a parse failure.

    No options always means the values were drawn instead of typed -- the page
    reads "(a) (b) (c) (d) (e)" with nothing after them.

    A missing stem is the ambiguous one, and the two cases look identical per
    question: both have five options and a direction. What separates them is how
    much of the SET sits on an image. Where every stem-less question in a
    direction group is on one, the stems are pictures -- symbol sets and
    "what value should come in place of (?)" print their statements as
    graphics. Where one of seven is, that image is something else on the page,
    and dropping the question throws away five good options with it: q93 of two
    RRB papers went that way, and 34 more across one batch.
    """
    groups: dict[object, list[dict]] = {}
    for q in questions:
        if not q["stem"] and q["options"]:
            groups.setdefault(q["direction_id"], []).append(q)
    # Majority, not all: one undetected image region in a set of five should not
    # hand back the whole set.
    drawn = {did: sum(1 for q in qs if q["on_image"]) * 2 > len(qs)
             for did, qs in groups.items()}

    for q in questions:
        if not q["options"]:
            q["has_image"] = q["on_image"]
        elif not q["stem"]:
            q["has_image"] = q["on_image"] and drawn.get(q["direction_id"], False)
        else:
            q["has_image"] = False
        del q["on_image"]


def stem_from_blank(direction: str, num: int) -> str:
    """For cloze sets, the sentence around this question's blank in the passage.

    The passage carries "____(18)___" where the answer goes, and the question
    itself is just an option list, so without this the stem is empty.
    """
    if not direction:
        return ""
    # Two markers in use: "____(18)___" and a bare "(15)". The bare form is only
    # trusted here because we already know the stem is empty and this direction
    # covers this number.
    m = (re.search(rf"_+\s*\(?\s*{num}\s*\)?\s*_+", direction)
         or re.search(rf"\(\s*{num}\s*\)", direction))
    if not m:
        return ""
    left = direction.rfind(".", 0, m.start())
    right = direction.find(".", m.end())
    start = left + 1 if left != -1 else max(0, m.start() - 160)
    stop = right + 1 if right != -1 else min(len(direction), m.end() + 160)
    return " ".join(direction[start:stop].split())


CORRECTIONS = Path(__file__).resolve().parent / "corrections.json"


def load_corrections() -> dict:
    """Hand-transcribed fixes, keyed by q_id.

    A question the parser mangles can be corrected by reading the PDF and
    writing the right value here -- editing the batch JSON directly does not
    survive the next run, which overwrites it.

    Transcription only. Every value must be visible in the source PDF; this is
    not a place to invent an option the paper never printed.
    """
    if not CORRECTIONS.is_file():
        return {}
    try:
        return json.loads(CORRECTIONS.read_text(encoding="utf-8")).get("questions", {})
    except (json.JSONDecodeError, OSError):
        return {}


def apply_correction(q: dict, fixes: dict) -> dict:
    fix = fixes.get(q.get("q_id"))
    if not fix:
        return q
    q = dict(q)
    q.update({k: v for k, v in fix.items() if k != "note"})
    q["corrected"] = sorted(k for k in fix if k != "note")
    return q


def make_paper_id(meta: dict, pdf: Path) -> str:
    """Stable id for the paper: what it is, plus a hash of the file it came from.

    The hash is what keeps two papers of the same exam apart -- three IBPS Clerk
    Prelims 2025 files sit in this corpus.
    """
    bits = [str(meta.get(k) or "unknown").lower().replace(" ", "_")
            for k in ("bank", "role", "year", "exam_type")]
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()[:8]
    return "_".join(bits + [digest])


def full_question(q: dict, paper_id: str, meta: dict) -> dict:
    """One question with every field step 1 owns, in contract order.

    Written out in full rather than left to the reader to join against the
    paper: a question is self-contained, so nothing downstream needs a lookup to
    filter by bank or year. `shift` is deliberately absent -- it is unknowable
    for these papers, which are practice compilations rather than one sitting.
    """
    return {
        "q_id": f"{paper_id}::q{q['q_num']:03d}",
        "paper_id": paper_id,
        "q_num": q["q_num"],
        "stem": q["stem"],
        "options": q["options"],
        "direction_id": q.get("direction_id"),
        "direction_text": q.get("direction_text"),
        "direction_has_image": False,
        "direction_image_refs": [],
        "bank": meta.get("bank"),
        "role": meta.get("role"),
        "exam_type": meta.get("exam_type"),
        "year": meta.get("year"),
        "memory_based": meta.get("memory_based", False),
        "has_image": bool(q.get("has_image")),
        "image_refs": [],
    }


def question_style(found: list) -> bool:
    """Does this paper number questions as 'Q41.' / 'Question 14:'?

    Bare '1.' is then a list item, not a question. The share of prefixed hits
    is the usual signal, but phrase-replacement lists ('1. Have grown  2. Are
    on the rise  3. …') inflate the bare count and can drop a 100-question
    'Question N:' paper under 60%. Unique prefixed numbers recover that.
    """
    if not found:
        return False
    prefixed = [m for m in found if m.group(1)]
    if len(prefixed) >= 0.6 * len(found):
        return True
    return len({int(m.group(1)) for m in prefixed}) >= 40


def question_anchors(found: list, q_style: bool) -> list[tuple[int, int, int]]:
    """Where each question starts, minus the bare numbers that only look like one.

    A para-jumble set prints two of its sentences already placed, numbered by
    their position in the paragraph: "104. P. Above 500 falls... 2. An AQI
    between 0-50... Q. The air quality index...". That "2." read as the start of
    question 2, so 104's block ended there and the options it never reached --
    (a) P (b) Q (c) R (d) S (e) T -- were dropped with the rest of the body.

    Going backwards is not the signal -- a two-column paper reads out of order
    all by itself ("41 44 45 42 43 46" is every one of those questions, once).
    Reusing a number already taken is: the paragraph's own "2." arrives long
    after question 2 was parsed. Rejecting backward numbers instead cost 4 real
    questions to that column interleave, and rejecting them outright cost 3 more
    in an earlier batch.

    Reuse is not the only tell. A section paper numbered 36-90 never uses the
    low numbers at all, so "5 : 3 respectively" inside a ratio was a free number
    and started question 5 -- cutting the real question after its first line and
    losing all five options. A bare number far below where the paper has got to
    is not a question either, whether or not it has been used.

    A section restart -- 1-35 Reasoning, then 1-35 English -- goes far backwards
    legitimately, so both rules need the same escape hatch: it keeps counting
    where a ratio or a sentence label stands alone. A rejected number that opens
    a run of three starts a new section, and the numbers seen so far are
    released.
    """
    seen = [(int(m.group(1) or m.group(2)), m.start(), m.end(), m.group(1) is None)
            for m in found if not q_style or m.group(1)]
    kept: list[tuple[int, int, int]] = []
    used: set[int] = set()
    highest = 0
    for i, (num, start, end, bare) in enumerate(seen):
        # 20 is wider than any column interleave seen here (41 44 45 42 43 46
        # is off by 3) and far below a section restart, which lands near 1.
        if bare and (num in used or num < highest - 20):
            run, prev = 1, num
            for nxt in seen[i + 1:]:
                if not 1 <= nxt[0] - prev <= 2:
                    break
                run += 1
                prev = nxt[0]
            if run < 3:
                continue
            used.clear()
            highest = num
        kept.append((num, start, end))
        used.add(num)
        highest = max(highest, num)
    return kept


def parse(pdf: Path) -> dict:
    text = read_text(pdf)
    has_image_at = image_regions(pdf)

    # A paper numbers its questions one way throughout. Where "Q41." is the
    # house style, a bare "1." is a list item inside a stem ("1. Revenue from
    # direct taxes  2. Revenue from indirect taxes") or a table row, and
    # treating it as a question start cuts the real question off from its
    # options. Requiring the dominant style only where one clearly dominates
    # leaves bare-numbered papers alone -- forcing it cost 3 real questions.
    found = list(QUESTION_RE.finditer(text))
    q_style = question_style(found)
    anchors = question_anchors(found, q_style)

    # The direction's body is everything between its header and the first
    # question it covers -- the passage, the table, the arrangement. Capturing
    # only the match span leaves "Directions (1-8):" and nothing else.
    heads = sorted(
        [(m.start(), m.end(), int(m.group(1)), int(m.group(2))) for m in DIRECTION_RE.finditer(text)]
        + [(m.start(), m.start(), None, None) for m in UNNUMBERED_DIRECTION_RE.finditer(text)
           if not DIRECTION_RE.match(text, m.start())]
    )
    directions = []
    for i, (start, end, lo, hi) in enumerate(heads):
        nxt_head = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        # Cut at the nearest anchor, not at the first question this direction
        # covers. Running to its own `lo` sounds more correct and on a
        # two-column page it swallows the questions printed beside the header --
        # 1,300 characters of questions 41-45 landed inside direction (46-50),
        # and their options stayed unrecoverable anyway because the labels
        # interleave.
        first_q = next((s for _, s, _ in anchors if s >= end), None)
        stop = min(first_q if first_q is not None else len(text), nxt_head)
        body = " ".join(text[end:stop].split())
        if lo is None:
            # Unnumbered: it covers every question between it and the next
            # direction, so the range comes from the anchors in that span.
            covered = [n for n, s, _ in anchors if end <= s < nxt_head]
            if not covered:
                continue
            lo, hi = min(covered), max(covered)
        directions.append((lo, hi, body))

    questions = []
    # One id per distinct direction, so the questions of a set can be grouped
    # without comparing passages that run to 2,000 characters.
    direction_ids: dict[str, str] = {}
    for i, (num, _start, end) in enumerate(anchors):
        stop = anchors[i + 1][1] if i + 1 < len(anchors) else len(text)
        block = text[end:stop]

        # Some papers print the question first and its whole direction after it,
        # repeating the passage for every question in the set. The direction
        # then sits inside this question's own block, so split it here -- taken
        # by global position it lands on the NEXT question while the passage
        # stays glued to this stem, which is how one paper ended up with all 115
        # stems polluted and every direction off by one. Split before
        # split_options: this pattern is line-anchored and that collapses lines.
        # A numbered "Directions (112-117):" inside this block belongs to the
        # NEXT set -- it sits before its first question's anchor, so it lands
        # at the tail of the question before it. Cut it first: otherwise the
        # "Read the following…" it opens with trips the own-direction detector
        # below, which then files this question's stem and options as a prefix
        # and returns no options at all. All five misses in one batch.
        nxt = DIRECTION_RE.search(block)
        if nxt and nxt.start() > 0:
            block = block[: nxt.start()]
        own_direction = None
        head = UNNUMBERED_DIRECTION_RE.search(block)
        prefix = block[: head.start()].strip() if head else ""
        if head and len(block) - head.start() > 80:
            if len(prefix) >= 15:
                # Question, then its direction: the stem is what came first,
                # taken whole. A para-jumble stem is itself a list of labelled
                # parts -- "(a) are more likely to be hospitalized (B) for
                # heat-related illness" -- so splitting options out of it eats
                # the stem and leaves nothing.
                raw_stem = " ".join(prefix.split())
                own_direction, raw_opts = split_options(block[head.start():])
                # The next set's "Direction:" can sit after this question's
                # A) B) C) D) E). Those labels stay in the prefix, which was
                # kept whole so a para-jumble's (a)/(B) parts are not eaten.
                # Recover only the bare A) run -- the jumble form uses parens.
                if not _complete_opts(raw_opts):
                    cleaned = PAPER_MARK_RE.sub(" ", BLEED_RE.sub("", prefix)).strip()
                    bare = list(BARE_UPPER_OPTION_RE.finditer(cleaned))
                    if bare:
                        pstem, popts = _extract_option_run(cleaned, bare)
                        if _complete_opts(popts):
                            raw_stem, raw_opts = pstem, popts
            else:
                # Direction, then the question. The instruction is one sentence,
                # ending at the colon these papers use; the rest is the stem.
                rest = block[head.start():]
                cut = rest.find(":")
                if cut == -1:
                    cut = rest.find(". ")
                if cut != -1:
                    own_direction = " ".join(rest[: cut + 1].split())
                    raw_stem, raw_opts = split_options(rest[cut + 1:])
                else:
                    raw_stem, raw_opts = split_options(block)
        else:
            raw_stem, raw_opts = split_options(block)

        raw_stem = space_maths(raw_stem)
        raw_opts = {k: space_maths(v) for k, v in raw_opts.items()}
        stem = strip_hindi(raw_stem)
        opts = {k: strip_hindi(v) or raw_opts[k] for k, v in raw_opts.items()}
        d_text = own_direction or next(
            (body for lo, hi, body in directions if lo <= num <= hi and body), None)
        d_text = strip_hindi(d_text) if d_text else None
        # Hindi-only question: stripping the Devanagari leaves "?" or "E ?", so
        # keep the original instead. A Hindi stem is still the question.
        if raw_stem and (not stem or (len(stem) < 12
                                      and not re.search(r"\d", stem)
                                      and not re.search(r"[A-Za-z]{3,}", stem))):
            stem = raw_stem
        if not opts:
            opts = options_from_direction(d_text or "")
        if not stem:
            stem = stem_from_blank(d_text or "", num)
        # Maths goes into `stem` in LaTeX, in place. One field per thing: a
        # parallel *_latex field means two versions to keep in step.
        # Options arrive by four routes -- the plain list, error-spotting
        # segments, a set's shared options, and a direction split -- and only
        # one of them passed through the block-level bleed cut. Cutting here
        # covers all of them: the next set's "Directions (76-81):" was riding
        # along on option (e), and "Ans.(b)" on 100 of 100 in another paper.
        opts = {k: BLEED_RE.sub("", v).strip() for k, v in opts.items()}
        opts = {k: v for k, v in opts.items() if v}

        stem = to_latex(stem) or stem
        opts = {k: (to_latex(v) or v) for k, v in opts.items()}
        questions.append({
            "q_num": num,
            "stem": stem,
            "options": opts,
            # Provisional: whether a picture sits where this question is.
            # Whether that picture IS the question is decided per direction set
            # once they are all built -- see resolve_image_bodied.
            "on_image": bool(has_image_at.get(num)),
            "direction_text": d_text,
            "direction_id": direction_ids.setdefault(
                d_text, f"d{len(direction_ids) + 1:03d}") if d_text else None,
        })

    # A number can be anchored more than once -- a table row reading "1. 3 60 C"
    # looks exactly like a question start. Keep the richest copy rather than the
    # first or last: the real question has options and a longer stem, and
    # position alone picks wrong in both directions.
    dedup: dict[int, dict] = {}
    for q in questions:
        prev = dedup.get(q["q_num"])
        rank = (len(q["options"]), len(q["stem"]))
        if prev is None or rank > (len(prev["options"]), len(prev["stem"])):
            dedup[q["q_num"]] = q
    meta = paper_meta(pdf, text)
    paper_id = make_paper_id(meta, pdf)
    fixes = load_corrections()
    try:
        source_pdf = str(pdf.resolve().relative_to(REPO))
    except ValueError:
        source_pdf = str(pdf)

    # A question is only marked has_image when its stem or its options are
    # missing AND the page holds an image region -- the text is a picture, so
    # there is nothing to take. Keeping it would file a stem-less, option-less
    # row in the bank; a question you cannot read is not a question.
    resolve_image_bodied([dedup[k] for k in sorted(dedup)])
    built = [apply_correction(full_question(dedup[k], paper_id, meta), fixes)
             for k in sorted(dedup)]
    bengali_paper = bool(BENGALI_RE.search(text))
    kept = [q for q in built
            if not q["has_image"] and not unreadable(q["stem"], q["options"], bengali_paper)]
    image_only = [q["q_num"] for q in built if q["has_image"]]
    script_only = [q["q_num"] for q in built if not q["has_image"]
                   and unreadable(q["stem"], q["options"], bengali_paper)]
    return {
        "source": pdf.name,
        # Repo-relative, so research.py can find the file again. The bare name
        # is not enough: the corpus is nested several folders deep.
        "source_pdf": source_pdf,
        "paper_id": paper_id,
        **meta,
        "question_count": len(kept),
        # Dropped, not lost: the numbers stay so a paper that jumps 42 -> 46
        # reads as five questions that were pictures, not five that went
        # missing. Step 4 needs to know they existed.
        "image_only_q_nums": image_only,
        "script_only_q_nums": script_only,
        "questions": kept,
    }


PAGE = fitz.paper_rect("a4")
MARGIN = 48.0
LEAD = 1.35
# Helvetica is Latin-1: it cannot draw √, ≥ or Devanagari, and PyMuPDF
# substitutes "?". Arial Unicode covers all three, so it is used when present
# and the ASCII fold below is only the fallback.
UNICODE_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]
UNI_FONT = next((f for f in UNICODE_FONTS if Path(f).is_file()), None)

ASCII_FOLD = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "--", "…": "...",
    " ": " ", "−": "-", "×": "x", "÷": "/", "≥": ">=", "≤": "<=", "≠": "!=",
    "√": "sqrt", "∛": "cbrt", "°": " deg",
})
# Mathematical alphanumerics (𝑥, 𝟔) have no glyph in any font here; NFKC maps
# them back to the plain letters they stand for. Applied only to that block, so
# it cannot also flatten x² into x2.
def flatten(text: str) -> str:
    """Latin-1 fallback. Anything unmapped becomes <U+XXXX>, not a silent "?"."""
    return "".join(c if ord(c) < 256 else f"<U+{ord(c):04X}>"
                   for c in text.translate(ASCII_FOLD))


class Sheet:
    def __init__(self, title: str) -> None:
        self.doc = fitz.open()
        self.title = title
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE.width, height=PAGE.height)
        if UNI_FONT:
            self.page.insert_font(fontname="uni", fontfile=UNI_FONT)
        self.y = MARGIN
        self.page.insert_text((MARGIN, PAGE.height - 28),
                              f"{self.title}  ·  page {self.doc.page_count}",
                              fontsize=7.5, color=(0.45, 0.45, 0.45))

    def write(self, text, *, size=9.5, bold=False, indent=0.0, gap=3.0, colour=(0, 0, 0)):
        if not text:
            return
        text = normalise(str(text))
        # Helvetica keeps a real bold face, which Arial Unicode does not, so
        # plain-Latin text stays on it and only text that needs the wider
        # coverage pays for losing bold.
        # Above ASCII, not above Latin-1: × (0xD7) and ÷ (0xF7) sit inside
        # Latin-1, so they took the fallback path and were folded to "x" and
        # "/" even with the real font available.
        if UNI_FONT and any(ord(c) > 127 for c in text):
            font = "uni"
        else:
            text = flatten(text)
            font = "hebo" if bold else "helv"
        for attempt in (0, 1):
            box = fitz.Rect(MARGIN + indent, self.y, PAGE.width - MARGIN, PAGE.height - MARGIN)
            if box.height <= size * LEAD:
                self._new_page()
                continue
            unused = self.page.insert_textbox(box, text, fontname=font, fontsize=size,
                                              color=colour, lineheight=LEAD)
            if unused >= 0:
                # insert_textbox under-reports by ~15pt on a long paragraph,
                # enough to overlap the next one. Ask the page where text ended.
                bottom = max((b[3] for b in self.page.get_text("blocks")
                              if b[3] > box.y0 - 0.5 and b[1] < box.y1 + 0.5), default=0.0)
                self.y = (bottom if bottom > box.y0 else box.y1 - unused) + gap
                return
            if attempt == 0:
                self._new_page()
        # Too tall for one page: split on words and carry the rest over.
        words = text.split()
        half = " ".join(words[: max(1, len(words) // 2)])
        self.write(half, size=size, bold=bold, indent=indent, gap=gap, colour=colour)
        self.write(" ".join(words[max(1, len(words) // 2):]),
                   size=size, bold=bold, indent=indent, gap=gap, colour=colour)

    def rule(self) -> None:
        self.y += 9
        if self.y + 9 > PAGE.height - MARGIN:
            self._new_page()
            return
        self.page.draw_line(fitz.Point(MARGIN, self.y),
                            fitz.Point(PAGE.width - MARGIN, self.y),
                            color=(0.85, 0.85, 0.85), width=0.5)
        self.y += 9


def label(paper: dict) -> str:
    """Short name: bank, role, stage, year. Unknown parts are left out."""
    bits = [paper.get("bank"), paper.get("role"), paper.get("exam_type")]
    if paper.get("year"):
        bits.append(str(paper["year"]))
    return " ".join(b for b in bits if b) or paper.get("source", "")


SUPER_BACK = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
              "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "n": "ⁿ"}
DISPLAY_MAP = [(r"\\times", "×"), (r"\\div", "÷"), (r"\\geq", "≥"), (r"\\leq", "≤")]
MIXED_DISPLAY_RE = re.compile(r"(\d+)\\frac\{(\d+)\}\{(\d+)\}")
VULGAR = {("1", "2"): "½", ("1", "3"): "⅓", ("2", "3"): "⅔", ("1", "4"): "¼",
          ("3", "4"): "¾", ("1", "5"): "⅕", ("2", "5"): "⅖", ("3", "5"): "⅗",
          ("4", "5"): "⅘", ("1", "6"): "⅙", ("5", "6"): "⅚", ("1", "8"): "⅛",
          ("3", "8"): "⅜", ("5", "8"): "⅝", ("7", "8"): "⅞", ("1", "7"): "⅐",
          ("1", "9"): "⅑", ("1", "10"): "⅒"}


ATOMIC_RE = re.compile(r"^[\w.?]+$")


def group_part(part: str) -> str:
    """Bracket a fraction half unless it is a single value already.

    "15" and "0.2" need nothing. "?-0.5" does, or the slash binds tighter than
    the minus when the page is read.
    """
    return part if ATOMIC_RE.match(part.strip()) else f"({part.strip()})"


def display(text: str) -> str:
    """LaTeX in `stem` back to readable glyphs, for the review PDF only.

    The JSON deliberately stores maths as LaTeX; printing that verbatim put
    literal "\\times" and "\\frac{15}{100}" on the page. The JSON is not
    touched -- this is display, not storage.
    """
    if "\\" not in text and "^{" not in text:
        return text
    # A mixed number shows as one glyph where Unicode has it -- "87⅓ %" is
    # unambiguous where "87 1/3 %" is not.
    out = MIXED_DISPLAY_RE.sub(
        lambda m: m.group(1) + VULGAR.get((m.group(2), m.group(3)),
                                          f" {m.group(2)}/{m.group(3)}"), text)
    # "a/b" only reads right when both halves are single values. A numerator
    # like "?-0.5" flattened to "?-0.5/0.2", which a reader takes as
    # ? - (0.5/0.2): the JSON was right and the review page said otherwise.
    out = re.sub(r"\\frac\{(.+?)\}\{([^{}]+)\}",
                 lambda m: f"{group_part(m.group(1))}/{group_part(m.group(2))}", out)
    out = out.replace("\\%", "%")
    out = re.sub(r"\\sqrt\[(\d)\]\{([^{}]+)\}",
                 lambda m: {"3": "∛", "4": "∜"}.get(m.group(1), "√") + m.group(2), out)
    out = re.sub(r"\\sqrt\{([^{}]+)\}", r"√\1", out)
    for pat, glyph in DISPLAY_MAP:
        out = re.sub(pat + r"\s*", glyph + " ", out)
    out = re.sub(r"\^\{([0-9n])\}",
                 lambda m: SUPER_BACK.get(m.group(1), "^" + m.group(1)), out)
    out = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", out)
    return " ".join(out.split())


def render(paper: dict, out: Path) -> int:
    name = label(paper)
    sheet = Sheet(name)
    sheet.write(name, size=13, bold=True, gap=3)
    sheet.write(f"{paper['question_count']} questions", size=8,
                colour=(0.55, 0.55, 0.55), gap=8)
    sheet.rule()

    seen = None
    for q in paper["questions"]:
        d = q.get("direction_text")
        if d and d != seen:
            sheet.write(display(d), size=9, bold=True, colour=(0.15, 0.15, 0.45), gap=9)
            seen = d
        sheet.write(f"{q['q_num']}. {display(q['stem']) if q['stem'] else '(no stem)'}", gap=5)
        if not q["options"]:
            sheet.write("(no options)", size=8.5, indent=16, colour=(0.7, 0.2, 0.2))
        for k in sorted(q["options"]):
            sheet.write(f"({k}) {display(q['options'][k])}", size=9, indent=16, gap=2.5)
        sheet.rule()

    # Subset before saving. Arial Unicode is a 22 MB font and PyMuPDF embeds all
    # of it, so a 38-page paper of plain text came out at 14.8 MB -- larger than
    # the source PDF it was extracted from. Only the glyphs actually used are
    # needed, and a review artefact nobody can open is no use.
    try:
        sheet.doc.subset_fonts()
    except Exception:
        pass          # older PyMuPDF: a fat file still beats no file
    sheet.doc.save(str(out), deflate=True, garbage=4)
    pages = sheet.doc.page_count
    sheet.doc.close()
    return pages


def next_batch_number(out_root: Path) -> int:
    used = [int(p.name[5:]) for p in out_root.glob("batch*") if p.name[5:].isdigit()]
    return max(used, default=0) + 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path, nargs="?", default=REMAINING,
                    help="a PDF, or a folder of them (default: corpus/remaining)")
    ap.add_argument("--out", type=Path, default=REPO / "data")
    ap.add_argument("--size", type=int, default=10)
    ap.add_argument("--batch", type=int, default=0,
                    help="output folder number (default: next unused)")
    ap.add_argument("--keep", action="store_true",
                    help="do not move the PDFs into corpus/done afterwards")
    args = ap.parse_args(argv)

    # A path that does not exist is not a PDF. Without this check `is_dir()` is
    # False for a typo, the run treats it as a single file, and it ends with a
    # new empty batch folder and a cheerful "0 questions".
    if not args.src.exists():
        print(f"  no such path: {args.src}", file=sys.stderr)
        return 1
    found = sorted(args.src.rglob("*.pdf")) if args.src.is_dir() else [args.src]
    pdfs = [p for p in found if not SKIP_NAME_RE.search(p.stem)]
    skipped = [p for p in found if SKIP_NAME_RE.search(p.stem)]
    batch = pdfs[: args.size]
    if not batch:
        print(f"  nothing to do -- {args.src} holds no PDFs")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    number = args.batch or next_batch_number(args.out)
    out = args.out / f"batch{number}"
    out.mkdir(parents=True, exist_ok=True)
    left = len(pdfs) - len(batch)
    print(f"  batch {number}: {len(batch)} PDFs, {left} left in {args.src}\n")

    total_q = clean = total_img = total_script = 0
    index = []
    parsed_pdfs = []
    for n, pdf in enumerate(batch, 1):
        try:
            paper = parse(pdf)
        except Exception as exc:
            print(f"  {n:2d}. FAIL  {pdf.name[:52]:54} {exc}")
            continue
        parsed_pdfs.append(pdf)
        qs = paper["questions"]
        # An image-bodied question is not a parse failure: there is no text to
        # take. parse() leaves those out, so they are counted from the numbers
        # it recorded and the rate below measures only the parser.
        imaged = len(paper["image_only_q_nums"])
        scripted = len(paper["script_only_q_nums"])
        no_opts = sum(1 for q in qs if not q["options"])
        # A stem the direction supplies is not missing -- same test parse() used
        # to decide the question was worth keeping.
        no_stem = sum(1 for q in qs
                      if not_supplied(q["stem"], q["options"], q["direction_text"])
                      and q["options"])
        total_q += len(qs) + imaged + scripted
        total_img += imaged
        total_script += scripted
        clean += len(qs) - sum(1 for q in qs
                               if not_supplied(q["stem"], q["options"], q["direction_text"]))

        (out / f"{n}.json").write_text(
            json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")
        render(paper, out / f"{n}.pdf")
        index.append({"n": n, "source": pdf.name, "bank": paper["bank"],
                      "role": paper["role"], "exam_type": paper["exam_type"],
                      "year": paper["year"], "questions": len(qs),
                      "image_bodied": imaged,
                      "image_only_q_nums": paper["image_only_q_nums"],
                      "script_only": scripted,
                      "script_only_q_nums": paper["script_only_q_nums"],
                      "no_options": no_opts, "no_stem": no_stem})
        label = " ".join(str(v) for v in (paper["bank"], paper["role"],
                                          paper["exam_type"], paper["year"]) if v)
        bits = []
        if imaged:
            bits.append(f"image={imaged}")
        if scripted:
            bits.append(f"script={scripted}")
        if no_opts:
            bits.append(f"no_opts={no_opts}")
        if no_stem:
            bits.append(f"no_stem={no_stem}")
        print(f"  {n:2d}. {len(qs):4d} q   {label:32}   {' '.join(bits)}")

    (out / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    text_q = total_q - total_img - total_script
    pct = 100 * clean / text_q if text_q else 0
    print(f"\n  {total_q} questions: {total_img} image-bodied, "
          f"{total_script} script-only, {text_q} text"
          f" -> {clean} complete ({pct:.1f}% of text)  ->  {out}")

    # Move only what parsed. A PDF that raised is left in remaining/ so the next
    # run picks it up again rather than it being quietly filed as done.
    if not args.keep and args.src.is_dir() and args.src.resolve() == REMAINING.resolve():
        for pdf in parsed_pdfs:
            for f in (pdf, pdf.with_suffix(pdf.suffix + ".meta.json")):
                if not f.exists():
                    continue
                dest = DONE / f.relative_to(REMAINING)
                dest.parent.mkdir(parents=True, exist_ok=True)
                f.replace(dest)
        # Skipped files are dealt with too -- leaving them in remaining/ means
        # re-examining them on every run.
        for pdf in skipped:
            for f in (pdf, pdf.with_suffix(pdf.suffix + ".meta.json")):
                if not f.exists():
                    continue
                dest = DONE / f.relative_to(REMAINING)
                dest.parent.mkdir(parents=True, exist_ok=True)
                f.replace(dest)
        for folder in sorted(REMAINING.rglob("*"), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        note = f", {len(skipped)} skipped (solutions/Hindi)" if skipped else ""
        print(f"  moved {len(parsed_pdfs)} PDFs to {DONE.relative_to(REPO)}{note}, "
              f"{left} remaining")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

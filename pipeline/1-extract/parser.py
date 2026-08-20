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
import json
import re
import unicodedata
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parents[2]
REMAINING = REPO / "corpus" / "remaining"
DONE = REPO / "corpus" / "done"

HEADER_FRAC = 0.12
FOOTER_FRAC = 0.08

DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
NOISE_RE = re.compile(
    r"(?i)^(?:adda247.*|www\.[a-z0-9.\-]+.*|bankersadda\.com.*|sscadda\.com.*|"
    r"careerpower\.in.*|store\.adda247\.com.*|website:.*|email:.*|"
    r"info@[a-z0-9.\-]+.*|page\s*\d+.*)$"
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
# "(a)/ segment" -- error spotting, where the options are the sentence's parts
SEGMENT_RE = re.compile(r"\(\s*([a-e])\s*\)\s*[.,;]?\s*(?:/|(?=\s*$))")
BLEED_RE = re.compile(
    r"(?is)\s*(?:Directions?\s*\(|Q\s*\d+\.|Question\s+\d+|www\.[a-z0-9.\-]+|"
    r"Answer\s*:|Solution\s*:).*$"
)
SOLUTIONS_RE = re.compile(r"(?im)^\s*(?:SOLUTIONS?|ANSWER\s+KEY|DETAILED\s+SOLUTIONS?)\s*$")
# Files with no questions to take: a solutions-only PDF, or the Hindi edition of
# a paper already held in English. Parsed anyway they yield 0-1 questions and
# burn a slot in the batch.
SKIP_NAME_RE = re.compile(r"(?i)(?:^|[-_ ])(?:solutions?|sol|answer[-_ ]?key|hindi|hn)(?:[-_ .]|$)")


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


def page_lines(page: fitz.Page, bars=()):
    """The page's text as lines, in reading order, boilerplate removed.

    Fractions and rows are resolved per COLUMN. Doing either across the whole
    page merges a left-column line with the right-column line beside it, which
    cost 56 questions when it was applied globally.
    """
    blocks = [b for b in page.get_text("dict").get("blocks") or [] if b.get("type") == 0]
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
            text = "".join(s.get("text", "") for s in line.get("spans") or []).strip()
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
        if not (ti.strip().isdigit() and (bi[3] - bi[1]) < 0.8 * body):
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
            if not any(centre(bi) < by < centre(bj)
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


DEV_RUN_RE = re.compile(r"[ऀ-ॿ][ऀ-ॿ\s।]*")


OPERATOR_SPACE_RE = re.compile(r"\s*([×÷≥≤=<>+])\s*")


def space_maths(text: str) -> str:
    """One space each side of an operator.

    The PDF sets these tight -- "700 ×? = 240" -- and a reader cannot tell the
    "?" from part of the operator. Minus is left alone: it is also a hyphen.
    """
    if not text:
        return text
    return " ".join(OPERATOR_SPACE_RE.sub(r" \1 ", text).split())


MATHY_RE = re.compile(r"[=×÷√≥≤]|\d+\s*/\s*\d+|\b\d+\s*\^")
FRACTION_RE = re.compile(r"(?<![\w/])(\d+)\s*/\s*(\d+)(?![\w/])")
ROOT_RE = re.compile(r"√\s*([A-Za-z0-9]+)")
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
    out = FRACTION_RE.sub(r"\\frac{\1}{\2}", text)
    out = ROOT_RE.sub(r"\\sqrt{\1}", out)
    out = SUPER_RE.sub(lambda m: f"^{{{SUPER[m.group(1)]}}}", out)
    out = out.replace("×", r"\times ").replace("÷", r"\div ")
    out = out.replace("≥", r"\geq ").replace("≤", r"\leq ")
    return " ".join(out.split()) if out != text else None


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


def split_options(block: str) -> tuple[str, dict[str, str]]:
    block = BLEED_RE.sub("", block).strip()

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
    if not matches:
        return " ".join(block.split()), {}

    # Last full a-e run wins: an earlier "(a)" may belong to the stem.
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
    for idx, mm in enumerate(run):
        label = mm.group(1).lower()
        if label == "a" and opts:
            break
        end = run[idx + 1].start() if idx + 1 < len(run) else len(block)
        value = " ".join(block[mm.end(): end].split()).strip(" ;-")
        if value:
            opts[label] = value
        if label == "e":
            break
    return stem, opts


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
    meta = meta_from_text(f'{re.sub(r"[\s._\-]+", " ", pdf.stem)} {text[:400]}')
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


def parse(pdf: Path) -> dict:
    text = read_text(pdf)

    # A paper numbers its questions one way throughout. Where "Q41." is the
    # house style, a bare "1." is a list item inside a stem ("1. Revenue from
    # direct taxes  2. Revenue from indirect taxes") or a table row, and
    # treating it as a question start cuts the real question off from its
    # options. Requiring the dominant style only where one clearly dominates
    # leaves bare-numbered papers alone -- forcing it cost 3 real questions.
    found = list(QUESTION_RE.finditer(text))
    prefixed = sum(1 for m in found if m.group(1))
    q_style = prefixed >= 0.6 * len(found) if found else False
    anchors = [(int(m.group(1) or m.group(2)), m.start(), m.end())
               for m in found if not q_style or m.group(1)]

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
        stem = to_latex(stem) or stem
        opts = {k: (to_latex(v) or v) for k, v in opts.items()}
        questions.append({
            "q_num": num,
            "stem": stem,
            "options": opts,
            "direction_text": d_text,
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
    return {
        "source": pdf.name,
        **paper_meta(pdf, text),
        "question_count": len(dedup),
        "questions": [dedup[k] for k in sorted(dedup)],
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
MATH_ALNUM = re.compile(r"[\U0001D400-\U0001D7FF]")


def normalise(text: str) -> str:
    return MATH_ALNUM.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), text)


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
        if UNI_FONT and any(ord(c) > 255 for c in text):
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
            sheet.write(d, size=9, bold=True, colour=(0.15, 0.15, 0.45), gap=9)
            seen = d
        sheet.write(f"{q['q_num']}. {q['stem'] or '(no stem)'}", gap=5)
        if not q["options"]:
            sheet.write("(no options)", size=8.5, indent=16, colour=(0.7, 0.2, 0.2))
        for k in sorted(q["options"]):
            sheet.write(f"({k}) {q['options'][k]}", size=9, indent=16, gap=2.5)
        sheet.rule()

    sheet.doc.save(str(out), deflate=True)
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

    total_q = clean = 0
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
        no_opts = sum(1 for q in qs if not q["options"])
        no_stem = sum(1 for q in qs if not q["stem"])
        total_q += len(qs)
        clean += len(qs) - no_opts - no_stem

        (out / f"{n}.json").write_text(
            json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")
        render(paper, out / f"{n}.pdf")
        index.append({"n": n, "source": pdf.name, "bank": paper["bank"],
                      "role": paper["role"], "exam_type": paper["exam_type"],
                      "year": paper["year"], "questions": len(qs),
                      "no_options": no_opts, "no_stem": no_stem})
        label = " ".join(str(v) for v in (paper["bank"], paper["role"],
                                          paper["exam_type"], paper["year"]) if v)
        flag = "" if not (no_opts or no_stem) else f"   no_opts={no_opts} no_stem={no_stem}"
        print(f"  {n:2d}. {len(qs):4d} q   {label:32}{flag}")

    (out / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    pct = 100 * clean / total_q if total_q else 0
    print(f"\n  {total_q} questions, {clean} complete ({pct:.1f}%)  ->  {out}")

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

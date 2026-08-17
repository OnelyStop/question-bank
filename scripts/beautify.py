#!/usr/bin/env python3
"""
Turn a slice of the raw question set into a publishable one.

The review PDFs this replaced were built to expose extraction damage, so they
print everything: internal ids, the coaching-book
filename each question came from, and whatever footer the extractor glued onto
option (e). That is the wrong artifact to ship. A question bank shows the
question, the options, the answer, and — only when the question genuinely needs
one — the chart or table. Nothing else.

Two things happen here, and they are deliberately separate:

  clean   repairs damage that is unambiguously repairable (a footer welded to an
          option, a source URL, a publisher's name sitting in the narrative)
  flag    refuses to guess. A puzzle question whose seating arrangement was
          never extracted cannot be answered by anyone, and no amount of string
          surgery invents the arrangement back. Those leave the set.

Reads data/raw/ready.json and writes, per slice N:
  cleaned/N.pdf    typeset, branding-free, charts embedded
  cleaned/N.json   the same questions, machine-readable
  flagged/N.pdf    the rejects, each with its reason
  flagged/N.csv    reason codes for triage

Paths resolve against the repo, so it runs from any working directory.

Usage: python3 tools/beautify.py [slice ...]   (default: 1)
"""

import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parents[1]
SETS = ROOT / "data" / "sets"
SRC = SETS / "extracted.json"
ASSET_CLASSES = ROOT / "tools" / "assets_classified.json"
OUT_CLEAN = SETS / "usable"
OUT_FLAG = SETS / "flagged"
PER_FILE = 500

FONT_REG = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


# ---------------------------------------------------------------- text repair

# Mathematical Alphanumeric Symbols and the Letterlike block: an extractor
# artefact, never an author's choice. "𝑥" and "ℎ" must read as x and h.
# NFKD is applied per-character so it cannot also flatten "x²" into "x2".
def _deitalicise(t):
    return "".join(
        unicodedata.normalize("NFKD", c)[0]
        if 0x1D400 <= ord(c) <= 0x1D7FF or 0x2100 <= ord(c) <= 0x214F
        else c
        for c in t
    )


# Arial Bold has no glyph for these, and a missing glyph prints as a blank box.
GLYPH_SUB = {"₹": "Rs.", "⇒": "=>", "∛": "cbrt", "∶": ":", " ": " "}

# The source PDFs set their maths in the Symbol font, which the extractor read
# as private-use codepoints (Symbol code + 0xF000). Left alone these render as
# empty boxes, and "if x ≥ y" becomes "if x  y" - an unanswerable option.
# 0x4F/0x50/0x59 are decorative glyphs used as symbols inside symbol-counting
# arrangement puzzles, where only "is this a symbol" matters, not which one.
GLYPH_SUB.update({
    "\uf02a": "*", "\uf02b": "+", "\uf02d": "-", "\uf03d": "=",
    "\uf0a3": "≤", "\uf0b3": "≥", "\uf0b4": "×",
    "\uf0ae": "→", "\uf0af": "↓",
    "\uf04f": "•", "\uf050": "■", "\uf059": "★",
    # Same failure, different fonts: a ring accent standing in for a degree
    # sign, a macron for the minus of "ms⁻¹", and one arrangement puzzle
    # whose symbol came through as a Portuguese letter.
    "˚": "°", "¯¹": "^-1", "ã": "★",
    "⟹": "=>",
    "⁰": "^0", "⁴": "^4", "⁵": "^5", "⁶": "^6",
    "⁷": "^7", "⁸": "^8", "⁹": "^9", "ⁿ": "^n",
})

# A second broken mapping, in the books that print stacked fractions: the digits
# 0-9 arrive as ten consecutive Odia codepoints, U+0B34 onwards. "3500 x 100/100"
# comes through as "3500 x <U+0B35><U+0B34><U+0B34>". Restoring the digits is what
# makes the surrounding damage visible to the fraction check below.
GLYPH_SUB.update({chr(0x0B34 + n): str(n) for n in range(10)})

# Whatever else that mapping produced - Ethiopic bracket pieces, stray Telugu and
# Tamil - has no digit to recover. Its presence means the text is still garbled.
GARBLED = re.compile(r"[ঀ-෿ሀ-፿]")

# The corpus carries Hindi translations of some papers. They are not damaged, but
# this is an English bank and half a question in Devanagari is not shippable.
DEVANAGARI = re.compile(r"[\u0900-\u097f]")

# Site plugs and footers the page carried, welded onto whatever text ended the
# line. "www.bankersadda.com | www.sscadda.com | ... | Adda247 App" is one run.
# Not every footer link starts with "www." — "estore.ibpsguide.com" and
# "Publications@ibpsguide.com" have to go too, and they have to go whole. Strip a
# domain only partially and the brand rewrite below turns the remainder into
# "estore.A publishing house.com".
FOOTER = re.compile(
    r"(?:\s*[|·-]?\s*(?:Visit\s*[:.]?\s*)?"
    r"(?:https?://\S+|(?:\S+@)?(?:[\w-]+\.)+(?:com|in|org|net|me|co)\b\S*))+"
    r"(?:\s*\|?\s*Adda\s?247[^|]*)?"
    r"|\s*\|\s*Adda\s?247\s*App\b.*"
    r"|\s*Visit\s*:\s*$"
    r"|\s*A Complete Guide.*$"
    r"|\s*Page\s*\d+\s*of\s*\d+.*$",
    re.I,
)

# House ads printed in the running footer, which the extractor appends to
# whatever text ended the page. Taken from what this corpus actually carries.
PROMO = re.compile(
    r"\s*(?:For any detail[s]?,?\s*mail us at\b"
    r"|Exclusively on New Pattern\b[^|]{0,60}?\beBook\b"
    r"|Cracker Book for Bank\b.*"
    r"|For any quer(?:y|ies)[^.]{0,60}?email us\b[^.]*"
    r"|(?:or\s*)?whatsapp\s*@?\s*\d[\d\s-]{7,}"
    r"|Follow\s+\w+\s+Sir\b[^.]{0,80}"
    r"|Telegram\s+Channel\b[^.]{0,60}"
    r"|Free Study Material\s*(?:&|and)\s*Quizzes\b"
    r"|Buy Now\b|Get \d+% off\b)",
    re.I,
)

# Sidebar and cross-sell copy, which lands mid-sentence rather than at the end:
# "...choosing the best possible Facebook Page Follow 102 Vishal Sir ow each
# question." Each phrase is therefore matched exactly and cut out in place, never
# to end-of-string. The bounds matter — one book's questions are genuinely about
# Facebook and Instagram user counts, and those must survive untouched.
HOUSE_ADS = re.compile(
    r"\s*(?:High\s+Quality\s+Mock\s+Test\s+Series(?:\s+for)?"
    r"(?:\s+(?:RRB|IBPS|SBI|RBI|LIC|SSC|NABARD)\b(?:\s+\w+){0,3})?"
    r"|Grand\s+Bundle\s+PDF\s+Course\s+Combo(?:\s*\([^)]*\))?(?:\s*\d{4})?"
    r"|Subscribe\s+Our\s+Yearly\s+\w+\s+Package"
    r"|TOP\s+\d+\s+Important\b[^:]{0,60}?Exams?\b"
    r"|Follow\s+us\s*:?\s*(?:(?:Telegram|Facebook|Twitter|Instagram|Youtube|G\+)\s*,?\s*)*"
    r"|Follow\s+\d*\s*\w+\s+Sir\b"
    r"|Facebook\s+Page\b|Youtube\s+Instagram\b"
    r"|(?:(?:Telegram|Facebook|Twitter|Instagram|Youtube|G\+)\s*,\s*)+"
    r"(?:Telegram|Facebook|Twitter|Instagram|Youtube|G\+)"
    r"|Click\s+Here(?:\s+(?:For|to))?\b)",
    re.I,
)

# The source exam printed after the last option and stuck to it:
# "(e) Rs.300 IBPS Clerk Prelims 2019" — the option is "Rs.300".
EXAM_TAIL = re.compile(
    r"\s*\b(?:IBPS|SBI|RRB|LIC|RBI|NABARD|SSC)\b.{0,40}?"
    r"(?:\bPrelims?\b|\bMains?\b|\bClerk\b|\bPO\b|\b20\d\d\b).*$",
    re.I,
)

# A publisher naming itself inside its own practice question. The question works
# just as well about an unnamed one, so neutralise rather than discard.
BRANDS = [
    (re.compile(r"\bAdda\s?247\s+publications?\b", re.I), "A publishing house"),
    (re.compile(r"\bBankersadda\b", re.I), "A publishing house"),
    (re.compile(r"\bIBPS\s?Guide\b", re.I), "A publishing house"),
    (re.compile(r"\bCareer\s?Power\b", re.I), "A publishing house"),
    (re.compile(r"\bSSC\s?ADDA\b", re.I), "a study channel"),
    (re.compile(r"\bAdda\s?247\b", re.I), "the publishing house"),
]
# Anything still carrying one of these after cleaning is not shippable.
BRAND_RESIDUE = re.compile(
    r"adda\s?247|bankersadda|sscadda|careerpower|ibpsguide|oliveboard|testbook"
    r"|gradeup|smartkeeda|practicemock|www\.|https?://"
    r"|\b[a-z0-9-]+\.(?:com|in|org|net)\b",
    re.I,
)

# Section labels the answer key left behind at the end of the last option. The
# colon is what makes it a heading — directions legitimately end "...and give
# answer." and that sentence must survive.
LABEL_TAIL = re.compile(r"\s*(?:Answers?|Solutions?|Explanations?)\s*:\s*$", re.I)

# Where the next question begins inside an option's text. "Palestine 17.How many
# people will sit..." — the option is "Palestine".
NEXT_Q = re.compile(
    r"\s+(?=\d{1,4}\s*[.)]\s*(?:[A-Z“‘\"(]|If\b|Which\b|How\b|What\b|Who\b|In\b))"
)
SOLUTION_NOTE = re.compile(r"\s*The logic for (?:all )?the above.*$", re.I | re.S)
# The next question's number, alone at the end of the last option: "180 sec. 11",
# "Both 22". Guarded by CURRENCY_ONLY, because in "Rs. 500" the trailing number
# is the answer and what precedes it is only a currency marker.
STRAY_NUMBER = re.compile(r"(?<=[a-zA-Z%.])\s+\d{1,3}$")
CURRENCY_ONLY = re.compile(r"^(?:rs|no|approx|about|nearly)?\W*$", re.I)

# An option marker inside shared context means the context swallowed the body of
# the questions that followed it on the page.
OPT_MARKER = re.compile(r"(?:^|\s)\(?[a-e]\)\s")
SENT_END = re.compile(r"[?.:!](?=\s)")

# Quadratic stems lose their exponent in extraction: "12y2 + 40y + 17 = 0".
# Only restore where a digit exponent cannot be anything else — a variable or a
# closing bracket immediately followed by 2 or 3 and then an operator.
EXPONENT = [
    (re.compile(r"(?<=[a-zA-Z])([23])(?=\s*[+\-×÷*/=)]|\s*$)"), None),
    (re.compile(r"(?<=\))([23])(?=\s*[+\-×÷*/=]|\s*$)"), None),
]
SUP = {"2": "²", "3": "³"}

# Sometimes the exponent was not mangled but dropped outright, and "7x² - 54x +
# 99 = 0" arrives as "7x - 54x + 99 = 0" — still parseable, now linear, and no
# longer the question the answer key was written against. Two like terms in the
# same variable with no exponent between them is not something anyone writes.
DEGRADED_EQ = re.compile(r"\d+([xy])\s*[+\-–−]\s*\d+\1\b")

# Mixed fractions are set as a stacked numerator over a denominator, and the
# extractor reads the two digits as separate numbers on the line: "30 10/13 %"
# arrives as "30 10 13 %", and sometimes the numerator lands several words
# earlier. The intended value is not recoverable, so these cannot be answered.
FLATTENED_FRACTION = re.compile(r"\d\s+\d{1,3}\s*%")

# A stem left hanging on a connector or an unfinished ratio is a severed stem,
# whatever punctuation follows it.
TRUNCATED = re.compile(
    r"(?:\d\s*[:∶]"
    r"|\b(?:the|a|an|of|to|in|and|or|by|for|with|than|then|from|between)\b"
    r"|[,;])\s*$",
    re.I,
)

# The question points at something outside itself.
REFERENTIAL = re.compile(
    r"\b(?:sits?|sitting|seated|facing|to the (?:left|right)|extreme end"
    r"|above (?:arrangement|input|step)|given arrangement|the above"
    r"|following (?:person|persons|player|combination)|belongs to"
    r"|step\s+(?:i|ii|iii|iv|v|1|2|3|4|5)\b)\b",
    re.I,
)
# The question points at a graphic. Directions name the graphic with no pointing
# word at all — "Line graph shows the quantity of 5 different products" — so the
# chart types have to be matched on their own, not only after following/given.
NEEDS_VISUAL = re.compile(
    r"\b(?:line|bar|pie|column)\s*-?\s*(?:graph|chart)\b"
    r"|\b(?:following|given|above)\s+(?:graph|chart|table|diagram|figure|histogram)"
    r"|\b(?:graph|chart|table|histogram)\s+(?:given|shown)\b"
    r"|\bstudy the (?:following |given )?(?:graph|chart|table|pie)"
    r"|\bin the (?:given |above )?figure\b|\bhistogram\b",
    re.I,
)


TITLES = None  # set per run by build(), from the corpus's own source_file names


def source_titles(questions):
    """Running headers, as a pattern built from the corpus rather than a list.

    The book's own title sits in the page header, so the extractor welds it onto
    whatever text ended the page: "None of these 200 Questions of Quantitative
    Aptitude". Every such title is already recorded as a source_file, so the set
    of strings to strip can be derived instead of guessed. Short stems
    ("QUANTS", "Quadratic") are skipped — they are ordinary words in a maths
    question and stripping them would damage real text.
    """
    seen = set()
    for q in questions:
        stem = Path(q.get("source_file") or "").stem
        stem = re.sub(r"[-_]+", " ", stem)
        stem = re.sub(r"\s*\[[^\]]*\]|\bpdf\b", " ", stem, flags=re.I)
        stem = squeeze(stem)
        if len(stem) >= 14:
            seen.add(stem)
    if not seen:
        return None
    alts = "|".join(re.escape(s).replace(r"\ ", r"\s+")
                    for s in sorted(seen, key=len, reverse=True))
    return re.compile(rf"\s*\b(?:{alts})\b.*$", re.I)


def strip_hindi(t):
    """Drop the Hindi half of a bilingual question, keep the English.

    Some papers print both languages: the stem is asked in English and then
    repeated in Devanagari, and each option reads "Rs.21,083 crore / Rs.21,083
    करोड़". The English half is complete on its own, so these are worth keeping
    rather than discarding for a language the bank does not publish in.

    Cutting at the first Devanagari character alone would leave the separator
    and the translated number behind ("December 31, 2025 /31"), so a separator
    just before it is taken as the real boundary.
    """
    m = DEVANAGARI.search(t)
    if not m:
        return t
    cut = m.start()
    window = t[max(0, cut - 40):cut]
    sep = max(window.rfind("/"), window.rfind("|"))
    if sep != -1:
        cut = max(0, cut - 40) + sep
    return t[:cut].strip(" /|-–—")


def squeeze(t):
    return re.sub(r"\s+", " ", t or "").strip()


def basic(t):
    """Repairs that apply to every field, in the only order that works.

    Branding must go before the footer sweep: "Adda247 App" is part of the
    footer run, but "Adda247 publications sold three books" is the narrative and
    the footer pattern would not touch it anyway.
    """
    t = strip_hindi(_deitalicise(t or ""))
    for a, b in GLYPH_SUB.items():
        t = t.replace(a, b)
    t = FOOTER.sub(" ", t)
    t = PROMO.sub(" ", t)
    prev = None
    while prev != t:
        prev, t = t, HOUSE_ADS.sub(" ", t)
    if TITLES:
        t = TITLES.sub("", t)
    for pat, repl in BRANDS:
        t = pat.sub(repl, t)
    return squeeze(t)


def restore_exponents(t):
    for pat, _ in EXPONENT:
        t = pat.sub(lambda m: SUP[m.group(1)], t)
    return t


def clean_stem(q):
    t = basic(q.get("stem"))
    t = EXAM_TAIL.sub("", t)
    t = LABEL_TAIL.sub("", t)
    # Two simultaneous equations printed on one line read as one broken equation.
    t = re.sub(r"\s+(?=II?\.\s)", "\n", t)
    if re.search(r"\b[xy]\s*[23]\b|\b\d+[xy][23]\b|[xy][23]\s*[+\-=]", t):
        t = restore_exponents(t)
    return t.strip()


def clean_option(t):
    t = basic(t)
    t = SOLUTION_NOTE.sub("", t)
    t = EXAM_TAIL.sub("", t)
    t = LABEL_TAIL.sub("", t)
    m = NEXT_Q.search(t)
    if m:
        t = t[: m.start()]
    shorter = STRAY_NUMBER.sub("", t)
    if not CURRENCY_ONLY.match(shorter):
        t = shorter
    return t.strip(" .,-|").strip()


def clean_context(t):
    """Keep the instruction, drop the page that came with it.

    Some contexts are a whole page of the source book: the directions line
    followed by the next six questions and their options. Cut at the first
    option marker, then back up to the last sentence boundary so the directions
    survive intact and question 1's body does not ride along.
    """
    t = basic(t)
    if not t:
        return ""
    m = OPT_MARKER.search(t)
    if m and len(OPT_MARKER.findall(t)) >= 2:
        head = t[: m.start()]
        ends = list(SENT_END.finditer(head))
        head = head[: ends[-1].end()] if ends else head
        t = head.strip()
    t = LABEL_TAIL.sub("", t)
    # Directions that stop mid-sentence ("...Read the data carefully and") are
    # cosmetic damage, not missing information — the preceding sentence already
    # says what the data is. Drop the fragment rather than print it.
    if TRUNCATED.search(t):
        ends = list(SENT_END.finditer(t + " "))
        if ends:
            t = t[: ends[-1].end()]
    return squeeze(t)


# ------------------------------------------------------------------- flagging

REASONS = {
    "context_missing": "refers to an arrangement/set that was never extracted",
    "context_unusable": "shared directions survived only as a page dump",
    "chart_missing": "asks about a graph/table that has no usable image",
    "option_bleed": "option text still carries the next question",
    "option_duplicate": "two or more options are identical after cleaning",
    "option_empty": "an option cleaned away to nothing",
    "stem_truncated": "stem ends mid-sentence",
    "equation_degraded": "an equation lost its exponent and no longer matches the key",
    "fraction_flattened": "a stacked fraction collapsed into loose digits",
    "text_garbled": "characters survive from a broken font mapping",
    "language_hindi": "asked in Hindi; no English half to keep",
    "stem_too_short": "stem is too short to be a question",
    "brand_residue": "a coaching brand or URL survived cleaning",
}


def assess(q, ctx, charts):
    """Reasons this question cannot ship. Empty list means it can."""
    bad = []
    stem, opts = q["stem"], q["options"]

    texts = [o["text"] for o in opts]
    everything = [stem, ctx] + texts

    if len(stem) < 25:
        bad.append("stem_too_short")
    elif TRUNCATED.search(stem):
        bad.append("stem_truncated")
    if DEGRADED_EQ.search(stem):
        bad.append("equation_degraded")
    if any(FLATTENED_FRACTION.search(t) for t in everything):
        bad.append("fraction_flattened")
    if any(GARBLED.search(t) for t in everything):
        bad.append("text_garbled")
    if q.get("_had_hindi") and (len(stem) < 25 or any(not t for t in texts)):
        bad.append("language_hindi")

    if any(not t for t in texts):
        bad.append("option_empty")
    elif len(set(texts)) < len(texts):
        bad.append("option_duplicate")
    if any(len(t) > 140 or NEXT_Q.search(t) or re.search(r"\d{2,4}\s*[.)]\s*[A-Z]", t)
           for t in texts):
        bad.append("option_bleed")

    if not ctx and REFERENTIAL.search(stem):
        bad.append("context_missing")
    if q.get("_ctx_was_dump") and not ctx:
        bad.append("context_unusable")

    if NEEDS_VISUAL.search(stem + " " + ctx) and not charts:
        bad.append("chart_missing")

    if any(BRAND_RESIDUE.search(t) for t in everything):
        bad.append("brand_residue")

    return bad


# ------------------------------------------------------------------ rendering

INK = (26, 26, 26)
MUTED = (110, 110, 110)
ACCENT = (12, 92, 60)
RULE = (216, 216, 216)
CTX_BG = (246, 247, 249)
FLAG_INK = (168, 42, 42)


class Book(FPDF):
    def __init__(self, title, subtitle):
        super().__init__(format="A4", unit="mm")
        self.title_text, self.subtitle = title, subtitle
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, margin=18)
        self.add_font("body", "", FONT_REG)
        self.add_font("body", "B", FONT_BOLD)
        self.set_text_color(*INK)

    def footer(self):
        self.set_y(-14)
        self.set_font("body", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, str(self.page_no()), align="C")
        self.set_text_color(*INK)

    def masthead(self):
        self.set_font("body", "B", 17)
        self.cell(0, 9, self.title_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("body", "", 9.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, self.subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)
        self.ln(4)

    def rule(self):
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(3)

    def keep_together(self, mm):
        """Start a new page rather than orphan a question across the break."""
        if self.get_y() + mm > self.h - self.b_margin:
            self.add_page()

    @staticmethod
    def drawable(text):
        """Anything still garbled would print as a blank box, which reads as a
        rendering bug rather than as the damage it is. Flagged questions are
        shown so a human can judge them, so mark the gap instead of hiding it."""
        return GARBLED.sub("\u25a1", text)

    def para(self, text, size=10.5, style="", indent=0, colour=INK, leading=4.8):
        text = self.drawable(text)
        self.set_font("body", style, size)
        self.set_text_color(*colour)
        self.set_x(self.l_margin + indent)
        self.multi_cell(self.w - self.l_margin - self.r_margin - indent, leading,
                        text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)

    def measure_context(self, text):
        """Panel height. The tint is drawn before the text it sits behind, so
        the height has to be known first — at the width the text will actually
        wrap at, or the panel stops short of its own last line."""
        if not text:
            return 0
        self.set_font("body", "", 9.5)
        w = self.w - self.l_margin - self.r_margin - 3
        return len(self.multi_cell(w, 4.4, text, dry_run=True,
                                   output="LINES")) * 4.4 + 12

    def measure_chart(self, path, max_w=95, max_h=75):
        try:
            from PIL import Image
            iw, ih = Image.open(SETS / path).size
        except Exception:
            return 0
        return ih * min(max_w / iw, max_h / ih, 0.32) + 4

    def context_block(self, label, text):
        w = self.w - self.l_margin - self.r_margin
        h = self.measure_context(text)
        self.set_fill_color(*CTX_BG)
        self.rect(self.l_margin, self.get_y(), w, h, style="F")
        self.ln(2.5)
        self.para(label, size=8.5, style="B", indent=3, colour=MUTED, leading=4.2)
        self.para(text, size=9.5, indent=3, colour=(60, 60, 60), leading=4.4)
        self.ln(3)

    def chart(self, path, max_w=95, max_h=75):
        """`path` is recorded relative to sets/ so the JSON stays portable;
        only the draw call needs it resolved."""
        try:
            from PIL import Image
            iw, ih = Image.open(SETS / path).size
        except Exception:
            return
        scale = min(max_w / iw, max_h / ih, 0.32)
        self.keep_together(ih * scale + 4)
        self.image(SETS / path, x=self.l_margin + 4, w=iw * scale, h=ih * scale)
        self.ln(2.5)

    def question(self, n, q, flags=None, charts=()):
        self.keep_together(34)
        self.set_font("body", "B", 10.5)
        num = f"{n}."
        nw = self.get_string_width(num) + 2
        self.cell(nw, 5, num)
        self.set_font("body", "", 10.5)
        self.multi_cell(self.w - self.l_margin - self.r_margin - nw, 5,
                        self.drawable(q["stem"]), new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT)
        self.ln(1)

        for path in charts:
            self.chart(path)

        for o in q["options"]:
            self.para(f"({o['key']})  {o['text']}", size=10, indent=6, leading=4.6)
        self.ln(0.8)

        if flags:
            self.para("FLAGGED  -  " + "; ".join(REASONS[f] for f in flags),
                      size=8.5, style="B", indent=6, colour=FLAG_INK, leading=4.2)
        else:
            ans = next(o for o in q["options"] if o["key"] == q["correct_option"])
            self.para(f"Answer   ({ans['key']})  {ans['text'][:90]}",
                      size=9.5, style="B", indent=6, colour=ACCENT, leading=4.4)
        self.ln(3.5)


def render(groups, path, title, subtitle, show_flags=False):
    pdf = Book(title, subtitle)
    pdf.add_page()
    pdf.masthead()
    n = 0
    for (ctx, charts), items in groups:
        header = bool(ctx) or (charts and len(items) > 1)
        if header:
            lo, hi = n + 1, n + len(items)
            span = f"Q. {lo}" if lo == hi else f"Q. {lo}-{hi}"
            # Directions and the chart they describe are one unit. Measure both
            # before drawing either, or the panel lands at the foot of a page
            # and its pie chart opens the next one.
            pdf.keep_together(pdf.measure_context(ctx) +
                              sum(pdf.measure_chart(c) for c in charts) + 20)
            if ctx:
                pdf.context_block(f"DIRECTIONS ({span})", ctx)
            for c in charts:
                pdf.chart(c)
        for q in items:
            n += 1
            pdf.question(n, q, q.get("flags") if show_flags else None,
                         charts=[] if header else charts)
        if header:
            pdf.rule()
    pdf.output(str(path))
    return n


# ----------------------------------------------------------------------- main


def build(slice_no):
    global TITLES
    everything = json.loads(SRC.read_text())
    # Built from the whole corpus, not the slice: a header bleeds across page
    # boundaries, so a title can surface in a slice that holds none of that book.
    TITLES = source_titles(everything)
    classes = json.loads(ASSET_CLASSES.read_text()) if ASSET_CLASSES.exists() else {}
    lo = (slice_no - 1) * PER_FILE
    raw = everything[lo:lo + PER_FILE]
    if not raw:
        print(f"slice {slice_no}: nothing there")
        return

    clean, flagged = [], []
    for q in raw:
        ctx_raw = q.get("shared_context") or ""
        ctx = clean_context(ctx_raw)
        # ready.json records asset paths as they sat in the extraction workspace;
        # only the images classified as charts were carried into the repo.
        charts = [f"charts/{Path(a['path']).name}"
                  for a in (q.get("assets") or [])
                  if classes.get(Path(a["path"]).name) == "chart"
                  and (SETS / "charts" / Path(a["path"]).name).exists()]
        out = {
            "question_id": q["question_id"],
            "stem": clean_stem(q),
            "options": [{"key": o["key"], "text": clean_option(o.get("text"))}
                        for o in q["options"]],
            "correct_option": q.get("correct_option"),
            "context": ctx,
            "charts": charts,
            "_ctx_was_dump": bool(ctx_raw) and not ctx,
            "_had_hindi": bool(DEVANAGARI.search(
                (q.get("stem") or "") + ctx_raw
                + "".join(o.get("text") or "" for o in q["options"]))),
        }
        out["flags"] = assess(out, ctx, charts)
        (flagged if out["flags"] else clean).append(out)

    # Consecutive questions sharing directions and a graphic are one set. Every
    # question of a DI set carries its own copy of the same pie chart; printed
    # per question that is the same image five times down five pages.
    def group(items):
        out, cur, key = [], [], object()
        for q in items:
            k = (q["context"].lower(), tuple(q["charts"]))
            if k != key:
                if cur:
                    out.append(((cur[0]["context"], cur[0]["charts"]), cur))
                cur, key = [], k
            cur.append(q)
        if cur:
            out.append(((cur[0]["context"], cur[0]["charts"]), cur))
        return out

    OUT_CLEAN.mkdir(parents=True, exist_ok=True)
    OUT_FLAG.mkdir(parents=True, exist_ok=True)

    n_clean = render(
        group(clean), OUT_CLEAN / f"{slice_no}.pdf",
        f"Banking Question Bank - Set {slice_no}",
        f"{len(clean)} questions with verified answer keys",
    )
    render(
        group(flagged), OUT_FLAG / f"{slice_no}.pdf",
        f"Flagged for repair - Set {slice_no}",
        f"{len(flagged)} questions held back from set {slice_no}",
        show_flags=True,
    )

    shipped = [{k: v for k, v in q.items() if not k.startswith("_") and k != "flags"}
               for q in clean]
    (OUT_CLEAN / f"{slice_no}.json").write_text(
        json.dumps(shipped, ensure_ascii=False, indent=1))

    with (OUT_FLAG / f"{slice_no}.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["question_id", "reasons", "stem"])
        for q in flagged:
            w.writerow([q["question_id"], "|".join(q["flags"]), q["stem"][:160]])

    # An unclassified image is treated as not-a-chart, which sends every question
    # in its set to flagged/ as chart_missing — indistinguishable in the output
    # from a set whose chart really was an advert. Only images hanging off a
    # question that asks about a visual can cause that; the rest are dropped
    # either way, so warning about them is noise. Across sets 2-10 that is the
    # difference between 917 images to review and 131.
    unseen = {Path(a["path"]).name
              for q in raw
              if NEEDS_VISUAL.search((q.get("stem") or "") + " "
                                     + (q.get("shared_context") or ""))
              for a in (q.get("assets") or [])
              if Path(a["path"]).name not in classes}
    if unseen:
        print(f"  WARNING: {len(unseen)} images on questions that ask about a "
              f"visual are unclassified and were dropped. Classify them in "
              f"{ASSET_CLASSES.name} before trusting the chart_missing count.")

    tally = Counter(f for q in flagged for f in q["flags"])
    print(f"set {slice_no}:  {n_clean} clean  /  {len(flagged)} flagged  "
          f"(of {len(raw)})")
    print(f"  charts embedded: {sum(len(q['charts']) for q in clean)}")
    for reason, c in tally.most_common():
        print(f"  {c:4d}  {reason:18s} {REASONS[reason]}")


if __name__ == "__main__":
    for arg in (sys.argv[1:] or ["1"]):
        build(int(arg))

"""
Rule-based topic labelling for the question bank.

Starts with keyword/heuristic rules (no LLM required). Focus exam: SBI PO Prelims,
but labels any question that matches.

Usage:
  python label_topics.py
  python label_topics.py --bank SBI --role PO --exam-type Prelims
  python label_topics.py --force
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pdf_to_questions import DEFAULT_OUT, rebuild_index
from validate_answers import iter_paper_jsons, load_paper

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("label_topics")

PERM_OPTION_RE = re.compile(r"^[A-E]{3,5}$", re.I)
NO_REARRANGEMENT_RE = re.compile(r"(?i)no\s+rearrangement\s+required")
PHRASE_REARRANGEMENT_DIR_RE = re.compile(
    r"(?i)divided\s+into\s+(?:four|five|\d+)?\s*phrases?|"
    r"phrases?\s+(?:aren['’]?t|are\s+not)\s+in\s+(?:their\s+)?(?:correct\s+)?position|"
    r"correct\s+sequence\s+of\s+(?:these\s+)?phrases?|"
    r"no\s+rearrangement\s+required|"
    r"rearrange\s+the\s+(?:following\s+)?(?:parts?|phrases?|fragments?)"
)
SLASH_PARTS_RE = re.compile(r"\([A-E]\)\s*/.*\([B-E]\)\s*/")
ERROR_SPOTTING_DIR_RE = re.compile(
    r"(?i)grammatical|idiomatic\s+err|read\s+each\s+sentence|"
    r"find\s+out\s+(?:whether|if).*(?:error|correct)|"
    r"which\s+(?:part|portion|segment).*(?:error|incorrect)|"
    r"spot\s+the\s+error|error\s+(?:spot|detection)|"
    r"\bno\s+error\b"
)

# (section, topic, pattern) — first match wins; English before Reasoning to avoid RC/error bleed
TOPIC_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    # English (checked first — avoids Quant/Reas keywords stealing error-spotting / cloze)
    # Phrase / sentence rearrangement BEFORE Error_Spotting (slash stems look similar)
    (
        "English",
        "Para_Jumble",
        re.compile(
            r"(?i)para\s*jumble|rearrange\s+the\s+(?:following\s+)?(?:sentences|paragraph|parts?|phrases?|fragments?)|"
            r"FIRST\s+sentence|LAST\s+sentence|meaningful\s+paragraph|"
            r"proper\s+sequence|after\s+rearrangement|"
            r"divided\s+into\s+(?:four|five|\d+)?\s*phrases?|"
            r"phrases?\s+(?:aren['’]?t|are\s+not)\s+in\s+(?:their\s+)?(?:correct\s+)?position|"
            r"correct\s+sequence\s+of\s+(?:these\s+)?phrases?|"
            r"no\s+rearrangement\s+required"
        ),
    ),
    (
        "English",
        "Error_Spotting",
        re.compile(
            r"(?i)grammatical|idiomatic\s+err|read\s+each\s+sentence|"
            r"find\s+out\s+(?:whether|if).*(?:error|correct)|"
            r"which\s+(?:part|portion|segment).*(?:error|incorrect)|"
            r"spot\s+the\s+error|error\s+(?:spot|detection)"
            # slash-parts heuristic applied separately — skipped when options are permutations
        ),
    ),
    (
        "English",
        "Cloze_Test",
        re.compile(
            r"(?i)cloze|blanks?,?\s+each\s+of\s+which\s+has\s+been\s+numbered|"
            r"blank\s*\([A-E]\)|fills?\s+blank\s*\(|which.*fills?\s+blank|"
            r"following\s+passage.*blank"
        ),
    ),
    (
        "English",
        "Vocabulary",
        re.compile(
            r"(?i)synonym|antonym|most\s+(?:similar|opposite)\s+in\s+meaning|"
            r"highlighted|four\s+words.*bold|odd\s+one\s+out|word\s+swap|"
            r"spelling|one\s+letter\s+substitution"
        ),
    ),
    (
        "English",
        "Reading_Comprehension",
        re.compile(
            r"(?i)\bpassage\b|\breading\s+comprehension|"
            r"\baccording\s+to\s+the\s+passage|\brefer\s+to\s+the\s+(?:\d+(?:st|nd|rd|th)\s+)?paragraph"
        ),
    ),
    ("English", "Sentence_Improvement", re.compile(r"(?i)\bsentence\s+improvement|\breplace\s+the\s+(?:bold|underlined)|\bphrase\s+replacement")),
    ("English", "Fill_in_the_Blanks", re.compile(r"(?i)\bfill\s+in\s+the\s+blank|\bchoose\s+the\s+word.*blank")),
    # Reasoning
    ("Reasoning", "Floor_Puzzle", re.compile(r"(?i)\bfloor\b|\blives?\s+on\b|\bstorey\b")),
    (
        "Reasoning",
        "Seating_Arrangement",
        re.compile(
            r"(?i)\b(?:circular|linear|row|square|triangular)\b.*\b(?:sit|sitting|seated)\b|"
            r"\b(?:sit|sitting|seated)\b.*\b(?:circular|linear|row|square|triangular)\b|"
            r"\bsit(?:ting|s)?\s+in\s+a\s+(?:row|circle|line|table)|"
            r"\bfacing\s+(?:north|south|east|west|centre|center)\b"
        ),
    ),
    (
        "Reasoning",
        "Puzzle",
        re.compile(
            r"(?i)\bpuzzle\b|\bschedule\b|\bbox(?:es)?\b|\bstack\b|"
            r"\beight\s+persons?\b|\bcertain\s+number\s+of\s+persons\b|"
            r"\byears?\s+(?:of\s+)?(?:experience|age)\b.*\b(?:company|department)\b"
        ),
    ),
    ("Reasoning", "Blood_Relation", re.compile(r"(?i)\bblood\s*relation|\b(?:mother|father|brother|sister|uncle|aunt)\b.*\b(?:son|daughter|nephew|niece|cousin)\b")),
    ("Reasoning", "Syllogism", re.compile(r"(?i)\bsyllogism|\bonly\s+a\s+few\b|\ball\s+\w+\s+are\b|\bno\s+\w+\s+is\b.*\bconclusion")),
    ("Reasoning", "Inequality", re.compile(r"(?i)\binequalit|\b[<>]=?|≥|≤|\bwhich\s+of\s+the\s+following\s+symbols?\b")),
    ("Reasoning", "Coding_Decoding", re.compile(r"(?i)\bcoding|decoding|\bis\s+coded\s+as\b|\bin\s+a\s+certain\s+code\b")),
    ("Reasoning", "Input_Output", re.compile(r"(?i)\binput[\s\-]*output|\bstep\s+[IVX\d]+\b.*\binput\b")),
    ("Reasoning", "Direction_Sense", re.compile(r"(?i)\bdirection\s+(?:sense|test)|\bwalks?\s+\d+\s*(?:m|km|metre)")),
    ("Reasoning", "Order_Ranking", re.compile(r"(?i)\branking|\border\s+and\s+ranking|\bleft\s+of\b.*\bright\s+of\b.*\brow\b")),
    ("Reasoning", "Alphanumeric", re.compile(r"(?i)\balphanumeric|\barrangement\s+carefully.*[A-Z]\s+\d|\bletter[- ]number")),
    # Quantitative
    (
        "Quantitative",
        "Data_Interpretation",
        re.compile(
            r"(?i)\bpie\s+chart|\bbar\s+(?:graph|diagram)|\bline\s+graph|"
            r"\btable\s+(?:shows|given|below)|\bdata\s+interpretation|\bDI\b"
        ),
    ),
    ("Quantitative", "Simplification", re.compile(r"(?i)\bsimplif|\bwhat\s+will\s+come\s+in\s+place\s+of\s+(?:the\s+)?(?:question\s+mark|\?)")),
    ("Quantitative", "Approximation", re.compile(r"(?i)\bapproximat|\bapproximate\s+value")),
    ("Quantitative", "Number_Series", re.compile(r"(?i)\bnumber\s+series|\bwrong\s+number|\bmissing\s+number\b.*\bseries")),
    ("Quantitative", "Quadratic_Equation", re.compile(r"(?i)\bquadratic|\bI\.\s*[xy]\^?2|\bcompare\s+x\s+and\s+y")),
    (
        "Quantitative",
        "Arithmetic",
        re.compile(
            r"(?i)\bprofit\s+and\s+loss|\bsimple\s+interest|\bcompound\s+interest|"
            r"\btime\s+and\s+work|\btime\s+(?:and|&)\s+distance|\bboat|"
            r"\bmixture|\ballegation|\bpercentage|\bratio\s+(?:and|&)\s+proportion|"
            r"\baverage|\bmensuration|\bprobability|\bpartnership|\bage\s+(?:of|problem)"
        ),
    ),
    # GA / Computer
    ("GA", "Current_Affairs", re.compile(r"(?i)\bcurrent\s+affairs|\brecently|\bin\s+20\d\d\b")),
    ("GA", "Banking_Awareness", re.compile(r"(?i)\bbanking\s+awareness|\bRBI\b|\bSEBI\b|\bNPA\b|\bCRR\b|\bSLR\b")),
    ("Computer", "Computer_Basics", re.compile(r"(?i)\bCPU\b|\bRAM\b|\boperating\s+system|\bMS[\s\-]?Excel|\bnetwork")),
]

FALLBACK_BY_SECTION = {
    "Reasoning": "Miscellaneous_Reasoning",
    "Quantitative": "Miscellaneous_Quant",
    "English": "Miscellaneous_English",
    "GA": "Miscellaneous_GA",
    "Computer": "Miscellaneous_Computer",
}


def options_blob(options: dict[str, str] | None) -> str:
    if not options:
        return ""
    return " ".join(str(v) for v in options.values() if v)


def looks_like_rearrangement_options(options: dict[str, str] | None) -> bool:
    """True when MCQ choices are phrase-order codes (DCBA) or 'No rearrangement required'."""
    if not options:
        return False
    vals = [str(v).strip() for v in options.values() if v]
    if not vals:
        return False
    if any(NO_REARRANGEMENT_RE.search(v) for v in vals):
        return True
    perm_hits = sum(1 for v in vals if PERM_OPTION_RE.match(v))
    return perm_hits >= 2


def looks_like_error_spotting_slash(stem: str | None, options: dict[str, str] | None) -> bool:
    """Slash (A)/(B)/(C) stems are Error Spotting only when options are not permutations."""
    if not stem or not SLASH_PARTS_RE.search(stem):
        return False
    if looks_like_rearrangement_options(options):
        return False
    return True


def topic_implied_section(
    direction: str | None,
    stem: str | None,
    options: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """Return (section, topic) from the first matching rule, ignoring stored section."""
    if looks_like_rearrangement_options(options) or (
        PHRASE_REARRANGEMENT_DIR_RE.search(direction or "") and SLASH_PARTS_RE.search(stem or "")
    ):
        return "English", "Para_Jumble"

    text = " ".join(filter(None, [direction, stem, options_blob(options)]))
    if not text.strip():
        return None, None
    for rule_section, topic, pat in TOPIC_RULES:
        if pat.search(text):
            return rule_section, topic
    if looks_like_error_spotting_slash(stem, options):
        return "English", "Error_Spotting"
    return None, None


def infer_topic(
    section: str | None,
    direction: str | None,
    stem: str | None,
    options: dict[str, str] | None = None,
) -> tuple[str | None, float, str, str | None]:
    """Return (topic, confidence, source, implied_section).

    implied_section is set when a cross-section rule matches (caller may correct section).
    """
    if looks_like_rearrangement_options(options) or (
        PHRASE_REARRANGEMENT_DIR_RE.search(direction or "") and SLASH_PARTS_RE.search(stem or "")
    ):
        if not section or section == "English":
            return "Para_Jumble", 0.85, "rules", "English"
        return "Para_Jumble", 0.6, "rules_cross_section", "English"

    text = " ".join(filter(None, [direction, stem, options_blob(options)]))
    if not text.strip() and not looks_like_error_spotting_slash(stem, options):
        return None, 0.0, "none", None

    for rule_section, topic, pat in TOPIC_RULES:
        if section and rule_section != section:
            continue
        if pat.search(text):
            return topic, 0.85, "rules", rule_section

    if looks_like_error_spotting_slash(stem, options):
        if not section or section == "English":
            return "Error_Spotting", 0.85, "rules", "English"
        return "Error_Spotting", 0.6, "rules_cross_section", "English"

    for rule_section, topic, pat in TOPIC_RULES:
        if pat.search(text):
            return topic, 0.6, "rules_cross_section", rule_section

    if section and section in FALLBACK_BY_SECTION:
        return FALLBACK_BY_SECTION[section], 0.4, "section_fallback", section

    return None, 0.0, "none", None


def infer_labels(
    section: str | None,
    direction: str | None,
    stem: str | None,
    options: dict[str, str] | None = None,
) -> tuple[str | None, str | None, float, str]:
    """Infer (section, topic, confidence, source) with topic-first section correction."""
    implied_sec, implied_topic = topic_implied_section(direction, stem, options)
    if implied_topic and implied_sec:
        if not section or section == implied_sec:
            return implied_sec, implied_topic, 0.85, "rules"
        return implied_sec, implied_topic, 0.6, "rules_cross_section"

    topic, conf, src, rule_sec = infer_topic(section, direction, stem, options)
    if topic and src == "rules_cross_section" and rule_sec:
        return rule_sec, topic, conf, src
    if topic:
        return section, topic, conf, src
    return section, None, 0.0, "none"


def load_taxonomy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def paper_matches(
    paper: dict[str, Any],
    *,
    bank: str | None,
    role: str | None,
    exam_type: str | None,
) -> bool:
    if bank and (paper.get("bank") or "").upper() != bank.upper():
        return False
    if role and (paper.get("role") or "").upper() != role.upper():
        return False
    if exam_type and (paper.get("exam_type") or "").lower() != exam_type.lower():
        return False
    return True


def label_topics(
    out_root: Path,
    taxonomy_path: Path,
    *,
    bank: str | None = None,
    role: str | None = None,
    exam_type: str | None = None,
    force: bool = False,
    use_fallback_misc: bool = True,
) -> dict[str, Any]:
    taxonomy = load_taxonomy(taxonomy_path)
    allowed = {t for topics in (taxonomy.get("sections") or {}).values() for t in topics}

    total = 0
    labelled = 0
    sources: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    papers_touched = 0
    focus_stats = {"papers": 0, "questions": 0, "labelled": 0}

    for path in iter_paper_jsons(out_root):
        paper = load_paper(path)
        if not paper:
            continue
        focus = paper_matches(paper, bank=bank, role=role, exam_type=exam_type) if (bank or role or exam_type) else True
        if bank or role or exam_type:
            if not focus:
                # Still can label all; filter only affects focus_stats reporting when --bank set
                # Plan: label one exam — when filters set, ONLY process matching papers
                continue
            focus_stats["papers"] += 1

        dirty = False
        for q in paper.get("questions") or []:
            total += 1
            if focus:
                focus_stats["questions"] += 1
            if q.get("topic") and not force:
                labelled += 1
                sources["existing"] += 1
                topics[str(q["topic"])] += 1
                if focus:
                    focus_stats["labelled"] += 1
                continue

            sec, topic, conf, src = infer_labels(
                q.get("section"),
                q.get("direction_text"),
                q.get("stem"),
                q.get("options"),
            )
            if src in ("rules_cross_section", "rules") and topic:
                if sec and sec != q.get("section"):
                    q["section"] = sec
                    q["section_source"] = "topic_cross_section" if src == "rules_cross_section" else "topic_keywords"
                    dirty = True
            if topic == FALLBACK_BY_SECTION.get(sec or q.get("section") or "") and not use_fallback_misc:
                topic, conf, src = None, 0.0, "none"

            if topic and topic not in allowed:
                # Keep anyway but mark
                src = f"{src}_off_taxonomy"

            if topic:
                q["topic"] = topic
                q["topic_confidence"] = conf
                q["topic_source"] = src
                labelled += 1
                sources[src] += 1
                topics[topic] += 1
                dirty = True
                if focus:
                    focus_stats["labelled"] += 1
            else:
                sources["unlabelled"] += 1

        if dirty:
            papers_touched += 1
            path.write_text(json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8")

    index_rows = rebuild_index(out_root)
    return {
        "filter": {"bank": bank, "role": role, "exam_type": exam_type},
        "questions_processed": total,
        "labelled": labelled,
        "coverage_pct": round(100.0 * labelled / total, 2) if total else 0,
        "papers_touched": papers_touched,
        "by_source": dict(sources),
        "by_topic": dict(topics),
        "focus": focus_stats,
        "index_rows": index_rows,
        "taxonomy": str(taxonomy_path.name),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Label topics on question bank")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--taxonomy", default=str(ROOT / "topic_taxonomy.json"))
    p.add_argument("--bank", default="SBI")
    p.add_argument("--role", default="PO")
    p.add_argument("--exam-type", default="Prelims")
    p.add_argument("--all", action="store_true", help="Label entire bank (ignore bank/role filter)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-misc-fallback", action="store_true")
    args = p.parse_args(argv)

    bank = None if args.all else args.bank
    role = None if args.all else args.role
    exam_type = None if args.all else args.exam_type

    report = label_topics(
        Path(args.out),
        Path(args.taxonomy),
        bank=bank,
        role=role,
        exam_type=exam_type,
        force=args.force,
        use_fallback_misc=not args.no_misc_fallback,
    )
    out_root = Path(args.out)
    report_path = out_root / "topic_label_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", report_path)
    log.info(
        "Labelled %s/%s (%.1f%%); focus=%s",
        report["labelled"],
        report["questions_processed"],
        report["coverage_pct"],
        report["focus"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

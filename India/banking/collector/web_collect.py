"""
Collect bank exam PDFs from public web pages (no Telegram API / login).
Sources: BankersAdda, Adda247, PracticeMock + optional t.me/s previews.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import urllib.request

from filename_parser import build_corpus_path, parse_filename, write_sidecar

ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = ROOT / "corpus"
DEFAULT_STATE = ROOT / "web_state.json"
SKIP_LOG = DEFAULT_CORPUS / "_skipped_log.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("web_collect")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

SEED_PAGES = [
    "https://www.bankersadda.com/ibps-po-memory-based-paper-2025/",
    "https://www.bankersadda.com/ibps-po-mains-memory-based-paper-2025/",
    "https://www.bankersadda.com/ibps-clerk-memory-based-mock-2024/",
    "https://www.bankersadda.com/sbi-po-memory-based-paper/",
    "https://www.bankersadda.com/sbi-clerk-memory-based-paper/",
    "https://www.bankersadda.com/ibps-rrb-po-prelims-memory-based-paper-2025-attempt-and-download-pdfs/",
    "https://www.bankersadda.com/rbi-grade-b-previous-year-question-paper/",
    "https://www.adda247.com/jobs/ibps-po-previous-year-question-paper/",
    "https://www.adda247.com/jobs/ibps-clerk-previous-year-question-paper/",
    "https://www.adda247.com/jobs/sbi-po-previous-year-question-paper/",
    "https://www.adda247.com/jobs/sbi-clerk-previous-year-question-paper/",
    "https://www.adda247.com/jobs/ibps-rrb-previous-year-question-paper/",
    "https://www.practicemock.com/blog/sbi-po-previous-year-question-paper-solution-pdf/",
    "https://www.practicemock.com/blog/ibps-po-previous-year-question-paper/",
    "https://www.practicemock.com/blog/ibps-clerk-previous-year-papers/",
]

TELEGRAM_WEB = [
    "https://t.me/s/Banking_Exams_IBPS_SBI_PO_Clerk",
    "https://t.me/s/bankingexampdfs",
    "https://t.me/s/bankpracticepdfs",
    "https://t.me/s/Banking_RBI_SEBI_NABARD_IBPS_SBI",
]

PDF_HREF_RE = re.compile(r"""href=["']([^"']+\.pdf[^"']*)["']""", re.I)
TG_DOC_RE = re.compile(
    r"""href=["'](https://cdn\d*\.telesco\.pe/file/[^"']+)["']""", re.I
)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
DIRECT_PDF_IN_QUERY = re.compile(
    r"(https?://[^\"'\s>]+\.pdf)", re.I
)


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen_urls": [], "seen_hashes": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def fetch(url: str, timeout: int = 45) -> bytes:
    # Quote non-ASCII path segments (Adda247 sometimes uses en-dash in filenames)
    parts = urlparse(url)
    path = quote(unquote(parts.path), safe="/:@&=+$,;")
    query = parts.query  # leave query as-is
    clean = parts._replace(path=path, query=query).geturl()
    req = urllib.request.Request(clean, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", errors="replace")


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unwrap_pdf_url(url: str) -> str:
    """Pull real PDF URL out of PracticeMock / login redirect wrappers."""
    if ".pdf" in url.lower() and "next=" in url.lower():
        qs = parse_qs(urlparse(url).query)
        for key in ("next", "dl", "url", "file"):
            if key in qs:
                inner = unquote(qs[key][0])
                # nested encoding
                for _ in range(3):
                    if "%2F" in inner or "%3A" in inner:
                        inner = unquote(inner)
                    else:
                        break
                m = DIRECT_PDF_IN_QUERY.search(inner)
                if m:
                    return m.group(1)
                if inner.lower().endswith(".pdf") or ".pdf?" in inner.lower():
                    return inner
    m = DIRECT_PDF_IN_QUERY.search(unquote(url))
    if m and m.group(1) != url:
        return m.group(1)
    return url


def guess_filename(url: str, page_title: str = "") -> str:
    path = urlparse(url).path
    name = Path(path).name
    if name.lower().endswith(".pdf") and len(name) > 5:
        return re.sub(r'[<>:"/\\|?*]', "_", unquote(name))
    base = re.sub(r"\s+", "_", page_title.strip())[:80] or "paper"
    base = re.sub(r'[<>:"/\\|?*]', "_", base)
    return f"{base}.pdf"


def append_skip(reason: str, name: str, url: str) -> None:
    SKIP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SKIP_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{reason}\tweb\t-\t{name}\t{url}\n")


def extract_pdf_urls(html: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for m in PDF_HREF_RE.finditer(html):
        urls.append(unwrap_pdf_url(urljoin(base_url, m.group(1))))
    if "t.me/s/" in base_url:
        for m in TG_DOC_RE.finditer(html):
            urls.append(m.group(1))
    # bare pdf urls in page text / scripts
    for m in DIRECT_PDF_IN_QUERY.finditer(html):
        urls.append(unwrap_pdf_url(m.group(1)))

    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def discover_from_page(page_url: str) -> list[tuple[str, str, str]]:
    """Return list of (pdf_url, suggested_filename, page_title)."""
    log.info("Scan %s", page_url)
    try:
        html = fetch_text(page_url)
    except Exception as e:
        log.warning("Failed page %s: %s", page_url, e)
        return []
    title_m = TITLE_RE.search(html)
    title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
    found: list[tuple[str, str, str]] = []
    for u in extract_pdf_urls(html, page_url):
        found.append((u, guess_filename(u, title), title))
    log.info("  found %s candidate links", len(found))
    return found


def save_pdf(
    url: str,
    filename: str,
    page_title: str,
    corpus: Path,
    seen_urls: set[str],
    seen_hashes: set[str],
    dry_run: bool,
) -> str:
    """Returns status: saved|skipped|error."""
    url = unwrap_pdf_url(url)
    if url in seen_urls:
        return "skipped"

    # Year/bank clues from filename + URL + page title
    parsed = parse_filename(filename, extra_text=f"{url} {page_title}")
    if parsed.skip_reason:
        append_skip(parsed.skip_reason, filename, url)
        seen_urls.add(url)
        return "skipped"

    dest = build_corpus_path(corpus, parsed, filename)
    if dest is None:
        append_skip(parsed.skip_reason or "unknown", filename, url)
        seen_urls.add(url)
        return "skipped"

    if dry_run:
        log.info("[dry-run] %s -> %s", url, dest)
        seen_urls.add(url)
        return "saved"

    try:
        data = fetch(url)
    except Exception as e:
        log.warning("Download failed %s: %s", url, e)
        return "error"

    if data[:4] != b"%PDF" and b"<html" in data[:800].lower():
        log.warning("Not a PDF (HTML): %s", url)
        seen_urls.add(url)
        append_skip("not_pdf_html", filename, url)
        return "skipped"

    digest = file_sha256(data)
    if digest in seen_hashes:
        seen_urls.add(url)
        append_skip("duplicate_hash", filename, url)
        return "skipped"

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        existing = hashlib.sha256(dest.read_bytes()).hexdigest()
        if existing == digest:
            seen_urls.add(url)
            seen_hashes.add(digest)
            return "skipped"
        dest = dest.with_name(f"{dest.stem}_{digest[:8]}{dest.suffix}")

    dest.write_bytes(data)
    write_sidecar(
        dest,
        parsed,
        extra={"source_url": url, "sha256": digest, "source_filename": filename},
    )
    seen_urls.add(url)
    seen_hashes.add(digest)
    year_label = parsed.year or "no_year"
    log.info("Saved [%s] %s", year_label, dest.relative_to(corpus))
    return "saved"


def run(args: argparse.Namespace) -> int:
    corpus = Path(args.corpus)
    corpus.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state)
    state = load_state(state_path)
    # Keep hashes (true duplicates). Clear URLs so previously no_year skips are retried.
    seen_hashes = set(state.get("seen_hashes", []))
    seen_urls: set[str] = set() if args.retry_skipped else set(state.get("seen_urls", []))

    pages = list(SEED_PAGES)
    if args.telegram_web:
        pages.extend(TELEGRAM_WEB)
    if args.page:
        pages.extend(args.page)

    candidates: list[tuple[str, str, str]] = []
    for page in pages:
        candidates.extend(discover_from_page(page))
        time.sleep(0.6)

    saved = skipped = errors = 0
    for url, name, title in candidates:
        status = save_pdf(
            url, name, title, corpus, seen_urls, seen_hashes, args.dry_run
        )
        if status == "saved":
            saved += 1
        elif status == "skipped":
            skipped += 1
        else:
            errors += 1
        if not args.dry_run:
            state["seen_urls"] = sorted(seen_urls)
            state["seen_hashes"] = sorted(seen_hashes)
            save_state(state_path, state)
        time.sleep(0.35)

    log.info("Done. saved=%s skipped=%s errors=%s", saved, skipped, errors)
    log.info("Corpus PDF total: %s", len(list(corpus.rglob("*.pdf"))))
    return 0 if errors == 0 else 2


def main() -> None:
    p = argparse.ArgumentParser(description="Collect bank exam PDFs from the web")
    p.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    p.add_argument("--state", default=str(DEFAULT_STATE))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--telegram-web", action="store_true")
    p.add_argument(
        "--retry-skipped",
        action="store_true",
        help="Retry URLs previously skipped (e.g. no_year)",
    )
    p.add_argument("--page", action="append", default=[], help="Extra page URL")
    args = p.parse_args()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()

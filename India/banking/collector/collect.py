"""
Telegram PDF collector for bank/PSU exam papers (2023+).
Downloads PDFs from seed channels and sorts by filename clues.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    SessionPasswordNeededError,
    UsernameNotOccupiedError,
)
from telethon.tl.types import DocumentAttributeFilename, MessageMediaDocument

from filename_parser import build_corpus_path, parse_filename, write_sidecar

ROOT = Path(__file__).resolve().parent
DEFAULT_CHANNELS = ROOT / "channels.txt"
DEFAULT_CORPUS = ROOT / "corpus"
DEFAULT_STATE = ROOT / "state.json"
SKIP_LOG = DEFAULT_CORPUS / "_skipped_log.txt"

# Telegram Desktop public credentials (no my.telegram.org needed).
# Official TEST credentials from Telegram Desktop docs (personal use).
DESKTOP_API_ID = 17349
DESKTOP_API_HASH = "344583e45741c457fe1862106095a5eb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("collector")


def load_channels(path: Path) -> list[str]:
    channels: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "t.me/" in line:
            line = line.rstrip("/").split("/")[-1]
        if line.startswith("@"):
            line = line[1:]
        channels.append(line)
    return channels


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen_messages": [], "seen_hashes": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def message_key(channel: str, message_id: int) -> str:
    return f"{channel}:{message_id}"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_document_filename(message) -> str | None:
    if not message.media or not isinstance(message.media, MessageMediaDocument):
        return None
    doc = message.media.document
    if not doc:
        return None
    name = None
    for attr in doc.attributes or []:
        if isinstance(attr, DocumentAttributeFilename):
            name = attr.file_name
            break
    if not name:
        return None
    if not name.lower().endswith(".pdf"):
        # Also accept application/pdf without .pdf extension
        mime = getattr(doc, "mime_type", "") or ""
        if mime != "application/pdf":
            return None
        name = name + ".pdf"
    return name


def append_skip(reason: str, filename: str, channel: str, message_id: int) -> None:
    SKIP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SKIP_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{reason}\t{channel}\t{message_id}\t{filename}\n")


async def download_with_floodwait(client: TelegramClient, message, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            await client.download_media(message, file=str(dest))
            return
        except FloodWaitError as e:
            wait = int(e.seconds) + 1
            log.warning("FloodWait %ss — sleeping", wait)
            await asyncio.sleep(wait)


async def process_channel(
    client: TelegramClient,
    channel: str,
    corpus: Path,
    state: dict,
    seen_messages: set[str],
    seen_hashes: set[str],
    limit: int,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Returns (downloaded, skipped, errors)."""
    downloaded = skipped = errors = 0
    try:
        entity = await client.get_entity(channel)
    except (UsernameNotOccupiedError, ChannelPrivateError, ValueError) as e:
        log.error("Cannot access @%s: %s", channel, e)
        return 0, 0, 1

    log.info("Scanning @%s ...", channel)
    count = 0
    async for message in client.iter_messages(entity, limit=limit or None):
        count += 1
        if count % 200 == 0:
            log.info("  @%s scanned %s messages...", channel, count)

        filename = get_document_filename(message)
        if not filename:
            continue

        key = message_key(channel, message.id)
        if key in seen_messages:
            skipped += 1
            continue

        parsed = parse_filename(filename)
        if parsed.skip_reason:
            append_skip(parsed.skip_reason, filename, channel, message.id)
            seen_messages.add(key)
            skipped += 1
            log.debug("Skip %s (%s)", filename, parsed.skip_reason)
            continue

        dest = build_corpus_path(corpus, parsed, filename)
        if dest is None:
            append_skip(parsed.skip_reason or "unknown", filename, channel, message.id)
            seen_messages.add(key)
            skipped += 1
            continue

        if dry_run:
            log.info("[dry-run] %s -> %s", filename, dest)
            seen_messages.add(key)
            downloaded += 1
            continue

        # If destination already exists with same size hint, treat as done
        if dest.exists() and dest.stat().st_size > 0:
            digest = file_sha256(dest)
            if digest in seen_hashes:
                seen_messages.add(key)
                skipped += 1
                continue
            seen_hashes.add(digest)
            seen_messages.add(key)
            skipped += 1
            continue

        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            await download_with_floodwait(client, message, tmp)
            digest = file_sha256(tmp)
            if digest in seen_hashes:
                tmp.unlink(missing_ok=True)
                append_skip("duplicate_hash", filename, channel, message.id)
                seen_messages.add(key)
                skipped += 1
                log.info("Duplicate hash, skip %s", filename)
                continue

            # Hash collision on different path: keep first path, skip writing second
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                existing = file_sha256(dest)
                if existing == digest:
                    tmp.unlink(missing_ok=True)
                else:
                    # Same name different content — add short hash suffix
                    dest = dest.with_name(f"{dest.stem}_{digest[:8]}{dest.suffix}")
                    tmp.rename(dest)
            else:
                tmp.rename(dest)

            seen_hashes.add(digest)
            seen_messages.add(key)
            write_sidecar(
                dest,
                parsed,
                extra={
                    "channel": channel,
                    "message_id": message.id,
                    "sha256": digest,
                    "source_filename": filename,
                },
            )
            downloaded += 1
            log.info("Saved %s", dest.relative_to(corpus))
        except Exception as e:
            errors += 1
            tmp.unlink(missing_ok=True)
            log.error("Failed %s from @%s: %s", filename, channel, e)

    return downloaded, skipped, errors


def resolve_api_credentials() -> tuple[int, str]:
    """Prefer .env; fall back to Telegram Desktop public API id/hash."""
    load_dotenv(ROOT / ".env")
    api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    placeholder = (
        not api_id
        or not api_hash
        or api_id == "12345678"
        or "your_api_hash" in api_hash
        or api_id.lower() == "desktop"
    )
    if placeholder:
        log.info("Using Telegram TEST API credentials (no my.telegram.org)")
        return DESKTOP_API_ID, DESKTOP_API_HASH
    return int(api_id), api_hash


async def ensure_logged_in(client: TelegramClient) -> None:
    """Login with phone number + Telegram code (more reliable than QR)."""
    await client.connect()
    if await client.is_user_authorized():
        me = await client.get_me()
        log.info("Logged in as %s", getattr(me, "username", None) or me.id)
        return

    log.info("Login required. Use the same phone number as your Telegram app.")
    phone = input("Phone (with country code, e.g. +9198xxxxxxxx): ").strip()
    if not phone.startswith("+"):
        phone = "+" + phone.lstrip("0")

    await client.send_code_request(phone)
    code = input("Code from Telegram (or SMS): ").strip().replace(" ", "")

    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        pwd = input("Two-step verification password: ").strip()
        await client.sign_in(password=pwd)

    me = await client.get_me()
    log.info("Login OK as %s", getattr(me, "username", None) or me.id)


async def run(args: argparse.Namespace) -> int:
    api_id, api_hash = resolve_api_credentials()
    session = os.getenv("TELEGRAM_SESSION", "bank_exam_session").strip()

    channels_path = Path(args.channels)
    if not channels_path.exists():
        log.error("Channels file not found: %s", channels_path)
        return 1

    channels = load_channels(channels_path)
    if not channels:
        log.error("No channels listed in %s", channels_path)
        return 1

    corpus = Path(args.corpus)
    corpus.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state)
    state = load_state(state_path)
    seen_messages = set(state.get("seen_messages", []))
    seen_hashes = set(state.get("seen_hashes", []))

    session_path = ROOT / session
    client = TelegramClient(str(session_path), api_id, api_hash)

    total_dl = total_skip = total_err = 0
    await ensure_logged_in(client)
    try:
        if args.channels_filter:
            wanted = {c.lstrip("@").lower() for c in args.channels_filter}
            channels = [c for c in channels if c.lower() in wanted]

        for channel in channels:
            dl, sk, er = await process_channel(
                client,
                channel,
                corpus,
                state,
                seen_messages,
                seen_hashes,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            total_dl += dl
            total_skip += sk
            total_err += er
            state["seen_messages"] = sorted(seen_messages)
            state["seen_hashes"] = sorted(seen_hashes)
            if not args.dry_run:
                save_state(state_path, state)
    finally:
        await client.disconnect()

    log.info(
        "Done. downloaded=%s skipped=%s errors=%s",
        total_dl,
        total_skip,
        total_err,
    )
    return 0 if total_err == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Collect bank exam PDFs from Telegram")
    p.add_argument(
        "--channels",
        default=str(DEFAULT_CHANNELS),
        help="Path to channels.txt",
    )
    p.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS),
        help="Output corpus directory",
    )
    p.add_argument(
        "--state",
        default=str(DEFAULT_STATE),
        help="Resume/dedupe state JSON",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max messages to scan per channel (0 = all)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and show destinations without downloading",
    )
    p.add_argument(
        "--only",
        dest="channels_filter",
        nargs="*",
        help="Only these channel usernames",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        code = asyncio.run(run(args))
    except KeyboardInterrupt:
        log.warning("Interrupted")
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()

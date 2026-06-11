#!/usr/bin/env python3
"""WR2 Damar publish consumer — STRATO 2 of the IG-metrics feedback loop.

Damar publishes WR2 caroselli to Instagram by hand (Law 5). To feed the IG URL
back into the queue WITHOUT a web form or a new Fly webhook, he simply sends a
WhatsApp message from his own number (+628213454726, mirrored by wa-mirror):

    PUBBLICATO WR2-A8274F https://instagram.com/p/XYZ

wa-mirror captures that message into the LOCAL Postgres table
`whatsapp_message_context` (localhost:15432/nuzantara_rag — same DB the backend
uses, NOT Fly). This consumer polls that table for new messages from Damar,
parses `ref_code + ig_url`, and calls `mark_published` (STRATO 1,
scripts/wr2_queue_writer.py) to advance the matching queue item to `published`.

Everything is Pro-local: wa-mirror (source) → local Postgres (transport) →
human-review-queue.json (sink) all live on the Pro. No PII leaves the machine
(Law 2): the consumer reads only the team-member channel and the only field it
acts on is a public IG URL.

Anti-fragility (inherited from STRATO 1): EXACT ref-code match. Any message that
does not parse, or whose ref-code does not resolve, is appended to an
"unmatched" JSONL for human disambiguation and NEVER silently dropped or
mis-applied.

Idempotency: a persistent cursor (last processed row id) + STRATO 1's own
idempotent `mark_published` (already_published no-op, conflict refusal) make
re-runs safe.

Column contract verified against the runtime reader
(app/routers/wa_mirror_messages.py:106-119): text lives in `body` with a legacy
fallback to `message_text` (COALESCE), sender is `team_member_phone`, ordering
by `id`.

CLI:
    wr2_damar_publish_consumer.py --once            # one polling pass (default)
    wr2_damar_publish_consumer.py --once --dry-run  # parse + report, write nothing
    wr2_damar_publish_consumer.py --phone +62...    # override Damar's number

The DB DSN is read from env `WA_MIRROR_DATABASE_URL` (same var wa-mirror uses).
NEVER hard-code the DSN — it carries a password (Golden Rule #6).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# ── Import STRATO 1 (sibling module in scripts/) ───────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_WRITER_PATH = _THIS_DIR / "wr2_queue_writer.py"
_spec = importlib.util.spec_from_file_location("wr2_queue_writer", _WRITER_PATH)
_qw = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _qw
_spec.loader.exec_module(_qw)

# ── Constants ──────────────────────────────────────────────────────────────

DAMAR_PHONE_DEFAULT = "+628213454726"  # roster: apps/wa-mirror/tests/phone.test.ts
DEFAULT_CURSOR_PATH = Path.home() / ".agent/state/wr2_damar_consumer.json"
DEFAULT_UNMATCHED_PATH = Path.home() / ".agent/state/wr2_damar_unmatched.jsonl"
DSN_ENV = "WA_MIRROR_DATABASE_URL"

# A publish command must carry THREE independent signals (matched separately so
# arbitrary surrounding text / word order is tolerated):
#   1. a "publish" intent word — PUBBLICATO (it, double-B), PUBLISHED, PUBLISH (en)
#   2. an instagram permalink
#   3. a ref-code — preferred `WR2-<6hex>`; fallback a bare 6-hex token
_PUB_WORD_RE = re.compile(r"\bpub\w*", re.IGNORECASE)
_IG_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?(?:\?\S*)?",
    re.IGNORECASE,
)
_REF_PREFIXED_RE = re.compile(r"\bwr2-([0-9a-f]{6})\b", re.IGNORECASE)
_REF_BARE_RE = re.compile(r"\b([0-9a-f]{6})\b", re.IGNORECASE)


# ── Pure parsing ───────────────────────────────────────────────────────────


def parse_publish_command(text: str) -> Optional[tuple[str, str]]:
    """Parse `PUBBLICATO <ref> <ig_url>` from a free-text message.

    Returns (ref_code_normalized, ig_url) or None if the message is not a
    well-formed publish command. Tolerant of word order, extra text, newlines
    and casing. The ref-code is preferred with its `WR2-` prefix; a bare 6-hex
    token is accepted as a fallback (searched AFTER excising the URL, so hex
    inside an IG shortcode is never mistaken for the ref-code). A bad ref-code
    still resolves to `not_found` downstream and writes nothing — fail-safe.
    """
    if not text:
        return None
    if not _PUB_WORD_RE.search(text):
        return None
    url_m = _IG_URL_RE.search(text)
    if not url_m:
        return None
    url = url_m.group(0).strip()
    if not _qw.validate_ig_url(url):
        return None
    ref_m = _REF_PREFIXED_RE.search(text)
    if ref_m:
        ref_hex = ref_m.group(1)
    else:
        text_wo_url = text.replace(url_m.group(0), " ")
        bare = _REF_BARE_RE.search(text_wo_url)
        if not bare:
            return None
        ref_hex = bare.group(1)
    return _qw.normalize_ref_code(ref_hex), url


# ── Result types ───────────────────────────────────────────────────────────


@dataclass
class MessageOutcome:
    """Outcome of processing one captured message."""

    row_id: int
    parsed: bool
    status: str  # not_a_command | <PublishResult.status>
    ref_code: Optional[str] = None
    ig_url: Optional[str] = None
    detail: str = ""


@dataclass
class BatchReport:
    cursor_before: int
    cursor_after: int
    outcomes: list[MessageOutcome] = field(default_factory=list)

    @property
    def published(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "published")

    @property
    def unmatched(self) -> list[MessageOutcome]:
        # Parsed-but-failed-to-apply OR not a command at all (latter is benign noise).
        return [o for o in self.outcomes if o.parsed and o.status not in ("published", "already_published")]


# ── Pure batch processing (mark_fn injected → testable without DB/queue) ───


def process_message(
    msg: dict[str, Any],
    mark_fn: Callable[[str, str, Optional[str]], Any],
) -> MessageOutcome:
    """Process one captured message dict {id, text, message_date}.

    `mark_fn(ref_code, ig_url, published_at_iso) -> PublishResult-like` is
    injected. Returns a MessageOutcome. Never raises on a malformed message.
    """
    row_id = int(msg["id"])
    text = msg.get("text") or ""
    parsed = parse_publish_command(text)
    if parsed is None:
        return MessageOutcome(row_id=row_id, parsed=False, status="not_a_command")
    ref, url = parsed
    published_at = msg.get("message_date")
    if isinstance(published_at, datetime):
        published_at = published_at.astimezone(timezone.utc).isoformat()
    result = mark_fn(ref, url, published_at)
    return MessageOutcome(
        row_id=row_id,
        parsed=True,
        status=getattr(result, "status", "unknown"),
        ref_code=ref,
        ig_url=url,
        detail=getattr(result, "detail", ""),
    )


def process_batch(
    messages: list[dict[str, Any]],
    mark_fn: Callable[[str, str, Optional[str]], Any],
    cursor_before: int,
) -> BatchReport:
    """Process a batch of messages ordered by id ascending. Cursor advances to
    the max processed id (even for non-commands, so benign noise is not
    re-scanned forever)."""
    report = BatchReport(cursor_before=cursor_before, cursor_after=cursor_before)
    for msg in messages:
        outcome = process_message(msg, mark_fn)
        report.outcomes.append(outcome)
        report.cursor_after = max(report.cursor_after, outcome.row_id)
    return report


# ── Cursor + unmatched persistence (I/O) ───────────────────────────────────


def load_cursor(path: Path) -> int:
    try:
        return int(json.loads(Path(path).read_text()).get("last_id", 0))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return 0


def save_cursor(path: Path, last_id: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_id": int(last_id), "updated_at": datetime.now(timezone.utc).isoformat()}))


def append_unmatched(path: Path, outcome: MessageOutcome) -> None:
    """Append a parsed-but-unresolved command for human disambiguation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({
            "row_id": outcome.row_id,
            "status": outcome.status,
            "ref_code": outcome.ref_code,
            "ig_url": outcome.ig_url,
            "detail": outcome.detail,
            "at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False) + "\n")


# ── DB fetch (asyncpg) ─────────────────────────────────────────────────────

_FETCH_SQL = """
    SELECT id,
           COALESCE(NULLIF(body, ''), message_text, '') AS text,
           message_date
      FROM whatsapp_message_context
     WHERE team_member_phone = $1
       AND id > $2
       AND COALESCE(NULLIF(body, ''), message_text, '') ~* 'publ'
     ORDER BY id ASC
     LIMIT 200
"""


async def fetch_new_messages(dsn: str, phone: str, after_id: int) -> list[dict[str, Any]]:
    """Fetch new wa-mirror messages from `phone` after `after_id`. Read-only."""
    import asyncpg  # local import: only needed at runtime, keeps unit tests dep-free

    conn = await asyncpg.connect(dsn.replace("?sslmode=disable", ""), timeout=10)
    try:
        rows = await conn.fetch(_FETCH_SQL, phone, after_id)
        return [{"id": r["id"], "text": r["text"], "message_date": r["message_date"]} for r in rows]
    finally:
        await conn.close()


# ── Orchestration ──────────────────────────────────────────────────────────


async def run_once(
    *,
    dsn: str,
    phone: str,
    queue_path: Path,
    cursor_path: Path,
    unmatched_path: Path,
    dry_run: bool,
    log: Callable[[str], None] = print,
) -> BatchReport:
    cursor = load_cursor(cursor_path)
    messages = await fetch_new_messages(dsn, phone, cursor)
    log(f"[wr2-damar-consumer] phone={phone} cursor={cursor} fetched={len(messages)} dry_run={dry_run}")

    def mark_fn(ref: str, url: str, published_at: Optional[str]):
        if dry_run:
            return _qw.PublishResult("dry_run", True, ref, detail="dry-run: would mark published")
        return _qw.mark_published(queue_path, ref, url, published_at=published_at)

    report = process_batch(messages, mark_fn, cursor)

    for o in report.outcomes:
        if o.parsed:
            log(f"  row={o.row_id} {o.status} ref={o.ref_code} url={o.ig_url} — {o.detail}")
        if o.parsed and o.status not in ("published", "already_published", "dry_run") and not dry_run:
            append_unmatched(unmatched_path, o)

    if not dry_run and report.cursor_after > report.cursor_before:
        save_cursor(cursor_path, report.cursor_after)

    log(f"[wr2-damar-consumer] published={report.published} unmatched={len(report.unmatched)} "
        f"cursor->{report.cursor_after}")
    return report


# ── CLI ────────────────────────────────────────────────────────────────────


def _resolve_queue_path(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("WR2_QUEUE_PATH")
    return Path(env) if env else _qw.DEFAULT_QUEUE_PATH


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="WR2 Damar publish consumer (STRATO 2)")
    p.add_argument("--once", action="store_true", help="run one polling pass (default behavior)")
    p.add_argument("--dry-run", action="store_true", help="parse + report, write nothing")
    p.add_argument("--phone", default=DAMAR_PHONE_DEFAULT, help="Damar's mirrored number")
    p.add_argument("--queue", help="queue path (default env WR2_QUEUE_PATH or standard)")
    p.add_argument("--cursor", default=str(DEFAULT_CURSOR_PATH))
    p.add_argument("--unmatched", default=str(DEFAULT_UNMATCHED_PATH))
    args = p.parse_args(argv)

    dsn = os.environ.get(DSN_ENV)
    if not dsn:
        print(f"FATAL: env {DSN_ENV} not set (the wa-mirror Postgres DSN). Refusing to run.", file=sys.stderr)
        return 2

    report = asyncio.run(run_once(
        dsn=dsn,
        phone=args.phone,
        queue_path=_resolve_queue_path(args.queue),
        cursor_path=Path(args.cursor),
        unmatched_path=Path(args.unmatched),
        dry_run=args.dry_run,
    ))
    # Non-zero exit if there are parsed-but-unresolved commands needing a human.
    return 0 if not report.unmatched else 1


if __name__ == "__main__":
    sys.exit(main())

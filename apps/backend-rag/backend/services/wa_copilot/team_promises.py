"""WA Copilot team_promises extractor + resolver (S1.8 v1).

Algorithm:
  - EXTRACT: scan whatsapp_message_context WHERE sender_role='team' with multilang
    regex (ID + EN + IT) for commitment intents. Infer promise_type
    (send/check/submit/update/process) + due_at from temporal keywords
    (today→+8h, tomorrow→+24h, next_week→+7d, asap→+12h, else NULL).
    INSERT team_promises with ON CONFLICT skip via uix_team_promises_msg_type.
  - RESOLVE: for each unresolved promise past due_at, scan next customer msg
    (sender_role != 'team') in same conversation within +24h for ack keywords
    (terima kasih/thanks/ok/grazie/ricevuto). Mark resolved + link
    resolved_by_message_id.

CLI:
    python -m backend.services.wa_copilot.team_promises \\
      extract|resolve|both \\
      [--apply | --dry-run] \\
      [--limit N] \\
      [--batch-size 200] \\
      [--metrics-json /tmp/promises.json]

PgBouncer-safe asyncpg (statement_cache_size=0). Idempotent via unique idx.
No Ollama (regex covers v1 — S1.5 LLM extraction covers semantic intent).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "v1-2026-05-25"
BATCH_SIZE_DEFAULT = 200
PROMISE_TEXT_WINDOW = 200  # max chars around regex match

# ---------------------------------------------------------------------------
# Regex catalog (multilang ID + EN + IT)
# ---------------------------------------------------------------------------

# Each entry: (promise_type, pattern). Patterns are compiled with IGNORECASE.
# Order matters: first match wins per message (one promise per type per msg
# enforced by unique idx). We allow MULTIPLE promise_types per msg (different
# rows).

_PROMISE_PATTERNS: list[tuple[str, str]] = [
    # ----- send -----
    ("send", r"\b(akan\s+(saya\s+)?kirim|saya\s+kirim|sudah\s+(saya\s+)?kirim|sudah\s+saya\s+send|kirim\s+(hari\s+ini|besok|sekarang|nanti|sore\s+ini))\b"),
    ("send", r"\b(i\s+will\s+send|i'?ll\s+send|sending\s+(now|today|tomorrow)|already\s+sent|i\s+have\s+sent|please\s+send\s+(today|asap)|will\s+send)\b"),
    ("send", r"\b(invio|invier[oò]|sto\s+inviando|gi[aà]\s+inviato|mando|mander[oò])\b"),

    # ----- check -----
    ("check", r"\b(saya\s+cek|akan\s+(saya\s+)?cek|coba\s+(saya\s+)?cek|cek\s+(dulu|nanti|besok|sekarang)|tak\s+cek)\b"),
    ("check", r"\b(i\s+will\s+check|i'?ll\s+check|let\s+me\s+check|checking\s+(now|tomorrow)|i\s+have\s+to\s+check)\b"),
    ("check", r"\b(controllo|controller[oò]|verifico|verificher[oò]|sto\s+controllando|gi[aà]\s+controllato)\b"),

    # ----- submit -----
    ("submit", r"\b(akan\s+(saya\s+)?submit|saya\s+submit|sudah\s+submit|sudah\s+saya\s+submit|submit\s+(hari\s+ini|besok|nanti|sekarang))\b"),
    ("submit", r"\b(i\s+will\s+submit|i'?ll\s+submit|submitting\s+(now|today|tomorrow)|already\s+submitted|i\s+have\s+submitted)\b"),
    ("submit", r"\b(invio\s+la\s+pratica|sottometto|sottometter[oò]|gi[aà]\s+sottomesso)\b"),

    # ----- update -----
    ("update", r"\b(akan\s+(saya\s+)?update|saya\s+update|update\s+(hari\s+ini|besok|nanti)|akan\s+kabari|saya\s+kabari|nanti\s+(saya\s+)?kabari)\b"),
    ("update", r"\b(i\s+will\s+update|i'?ll\s+update|i\s+will\s+let\s+you\s+know|i'?ll\s+let\s+you\s+know|will\s+keep\s+you\s+posted|updating\s+(soon|tomorrow))\b"),
    ("update", r"\b(aggiorno|aggiorner[oò]|ti\s+aggiorno|ti\s+(faccio\s+)?sapere|ti\s+fammo\s+sapere)\b"),

    # ----- process -----
    ("process", r"\b(akan\s+(saya\s+)?proses|saya\s+proses|proses\s+(hari\s+ini|besok|sekarang|nanti)|segera\s+(saya\s+)?proses|sudah\s+(saya\s+)?proses)\b"),
    ("process", r"\b(i\s+will\s+process|i'?ll\s+process|processing\s+(now|today|tomorrow)|already\s+processing|i\s+have\s+processed)\b"),
    ("process", r"\b(processo|elaboro|elaborer[oò]|sto\s+processando|sto\s+elaborando)\b"),
]

# Compiled
_PROMISE_PATTERNS_RE: list[tuple[str, re.Pattern[str]]] = [
    (ptype, re.compile(pat, re.IGNORECASE | re.UNICODE))
    for ptype, pat in _PROMISE_PATTERNS
]

# Temporal cue → hours offset
_TEMPORAL_CUES: list[tuple[re.Pattern[str], int]] = [
    # next week / prossima settimana / minggu depan → +7 days (168h)
    (re.compile(r"\b(next\s+week|prossima\s+settimana|minggu\s+depan)\b", re.IGNORECASE), 168),
    # tomorrow / domani / besok → +24h
    (re.compile(r"\b(tomorrow|domani|besok)\b", re.IGNORECASE), 24),
    # asap / segera → +12h
    (re.compile(r"\b(asap|as\s+soon\s+as\s+possible|segera|al\s+pi[uù]\s+presto)\b", re.IGNORECASE), 12),
    # today / oggi / hari ini / sore ini / stasera / this evening → +8h
    (re.compile(r"\b(today|oggi|hari\s+ini|sore\s+ini|stasera|this\s+evening|tonight|nanti)\b", re.IGNORECASE), 8),
]

# Ack keywords for resolver (customer side)
_ACK_PATTERN = re.compile(
    r"\b(terima\s+kasih|makasih|thanks?|thank\s+you|ty|noted|received|got\s+it|ok+|okay|"
    r"baik(?:\s+kak)?|siap|sip|grazie|ricevuto|ricevut[oa]|perfetto|ottimo)\b",
    re.IGNORECASE | re.UNICODE,
)


@dataclass(slots=True)
class PromiseCandidate:
    """One candidate promise row before insert."""

    message_id: int
    conversation_id: int | None
    client_id: int | None
    promise_text: str
    promise_type: str
    due_at: _dt.datetime | None


@dataclass
class ExtractMetrics:
    """Aggregate extract run metrics."""

    total_scanned: int = 0
    matched_messages: int = 0
    promises_created: int = 0
    promises_skipped_conflict: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    with_due_at: int = 0
    errors: int = 0
    wall_ms: int = 0


@dataclass
class ResolveMetrics:
    """Aggregate resolve run metrics."""

    total_unresolved_scanned: int = 0
    promises_resolved: int = 0
    no_ack_found: int = 0
    errors: int = 0
    wall_ms: int = 0


# ---------------------------------------------------------------------------
# Extract logic
# ---------------------------------------------------------------------------

def _infer_due_at(body: str, message_date: _dt.datetime) -> _dt.datetime | None:
    """Map temporal keywords → message_date + offset. First match wins (most
    specific patterns first)."""
    for pattern, hours in _TEMPORAL_CUES:
        if pattern.search(body):
            return message_date + _dt.timedelta(hours=hours)
    return None


def _extract_window(body: str, match: re.Match[str], window: int = PROMISE_TEXT_WINDOW) -> str:
    """Extract a window around the match (up to `window` chars total)."""
    start = max(0, match.start() - window // 2)
    end = min(len(body), match.end() + window // 2)
    snippet = body[start:end].strip()
    if len(snippet) > window:
        snippet = snippet[:window].rstrip()
    return snippet


def _find_promises_in_message(
    message_id: int,
    conversation_id: int | None,
    client_id: int | None,
    body: str,
    message_date: _dt.datetime,
) -> list[PromiseCandidate]:
    """Scan body for promise patterns; return one PromiseCandidate per unique
    promise_type matched (first occurrence wins per type)."""
    seen_types: set[str] = set()
    out: list[PromiseCandidate] = []
    for ptype, pat in _PROMISE_PATTERNS_RE:
        if ptype in seen_types:
            continue
        m = pat.search(body)
        if not m:
            continue
        seen_types.add(ptype)
        snippet = _extract_window(body, m)
        due_at = _infer_due_at(body, message_date)
        out.append(
            PromiseCandidate(
                message_id=message_id,
                conversation_id=conversation_id,
                client_id=client_id,
                promise_text=snippet,
                promise_type=ptype,
                due_at=due_at,
            )
        )
    return out


async def _scan_batch(
    pool: asyncpg.Pool,
    *,
    limit: int | None,
    batch_size: int,
    apply: bool,
    metrics: ExtractMetrics,
) -> None:
    """Iterate team messages in batches; extract + insert promises."""
    offset = 0
    unbounded = limit is None
    remaining = limit if limit is not None else 0
    while unbounded or remaining > 0:
        fetch_size = batch_size if unbounded else min(batch_size, remaining)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, conversation_id, client_id, message_date,
                       COALESCE(body, message_text) AS body
                FROM whatsapp_message_context
                WHERE sender_role = 'team'
                  AND COALESCE(body, message_text) IS NOT NULL
                  AND length(COALESCE(body, message_text)) > 3
                ORDER BY id
                OFFSET $1 LIMIT $2
                """,
                offset,
                fetch_size,
            )
        if not rows:
            return
        metrics.total_scanned += len(rows)

        # Compute candidates in Python
        candidates: list[PromiseCandidate] = []
        for r in rows:
            body = r["body"]
            promises = _find_promises_in_message(
                message_id=r["id"],
                conversation_id=r["conversation_id"],
                client_id=r["client_id"],
                body=body,
                message_date=r["message_date"],
            )
            if promises:
                metrics.matched_messages += 1
                candidates.extend(promises)

        if not candidates:
            offset += len(rows)
            if not unbounded:
                remaining -= len(rows)
            continue

        # Insert with ON CONFLICT skip
        if apply:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # INSERT ... ON CONFLICT DO NOTHING (uix_team_promises_msg_type)
                    insert_rows: list[tuple[Any, ...]] = [
                        (
                            c.message_id,
                            c.conversation_id,
                            c.client_id,
                            c.promise_text,
                            c.promise_type,
                            c.due_at,
                        )
                        for c in candidates
                    ]
                    # executemany returns None; use copy/insert per-row to count
                    inserted = 0
                    for row in insert_rows:
                        result = await conn.execute(
                            """
                            INSERT INTO team_promises
                              (message_id, conversation_id, client_id,
                               promise_text, promise_type, due_at)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (message_id, promise_type) DO NOTHING
                            """,
                            *row,
                        )
                        # result is like "INSERT 0 1" or "INSERT 0 0"
                        if result.endswith(" 1"):
                            inserted += 1
                            metrics.promises_created += 1
                            ptype = row[4]
                            metrics.by_type[ptype] = metrics.by_type.get(ptype, 0) + 1
                            if row[5] is not None:
                                metrics.with_due_at += 1
                        else:
                            metrics.promises_skipped_conflict += 1
        else:
            # Dry-run: count without inserting
            for c in candidates:
                metrics.promises_created += 1
                metrics.by_type[c.promise_type] = metrics.by_type.get(c.promise_type, 0) + 1
                if c.due_at is not None:
                    metrics.with_due_at += 1

        offset += len(rows)
        if not unbounded:
            remaining -= len(rows)


async def run_extract(
    pool: asyncpg.Pool,
    *,
    apply: bool,
    limit: int | None,
    batch_size: int,
) -> ExtractMetrics:
    """Top-level extract entrypoint."""
    t0 = time.monotonic()
    metrics = ExtractMetrics()
    try:
        await _scan_batch(
            pool,
            limit=limit,
            batch_size=batch_size,
            apply=apply,
            metrics=metrics,
        )
    except Exception:
        logger.exception("extract failed")
        metrics.errors += 1
    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# Resolve logic
# ---------------------------------------------------------------------------

async def run_resolve(
    pool: asyncpg.Pool,
    *,
    apply: bool,
    limit: int | None,
    batch_size: int,
) -> ResolveMetrics:
    """For each unresolved promise past due_at, find next customer msg in
    same conversation within +24h that contains an ack keyword."""
    t0 = time.monotonic()
    metrics = ResolveMetrics()
    try:
        async with pool.acquire() as conn:
            unresolved = await conn.fetch(
                """
                SELECT p.promise_id, p.message_id, p.conversation_id,
                       p.due_at, m.message_date AS promise_msg_date
                FROM team_promises p
                JOIN whatsapp_message_context m ON m.id = p.message_id
                WHERE p.resolved = false
                  AND p.due_at IS NOT NULL
                  AND p.due_at < NOW()
                  AND p.conversation_id IS NOT NULL
                ORDER BY p.due_at
                LIMIT $1
                """,
                limit if limit is not None else 100000,
            )
        metrics.total_unresolved_scanned = len(unresolved)
        if not unresolved:
            metrics.wall_ms = int((time.monotonic() - t0) * 1000)
            return metrics

        # Resolve in batches for transaction efficiency
        for i in range(0, len(unresolved), batch_size):
            batch = unresolved[i : i + batch_size]
            updates: list[tuple[int, _dt.datetime, int]] = []  # (promise_id, ack_date, ack_msg_id)

            async with pool.acquire() as conn:
                for p in batch:
                    promise_id = p["promise_id"]
                    conv_id = p["conversation_id"]
                    due = p["due_at"]
                    window_end = due + _dt.timedelta(hours=24)

                    rows = await conn.fetch(
                        """
                        SELECT id, message_date, COALESCE(body, message_text) AS body
                        FROM whatsapp_message_context
                        WHERE conversation_id = $1
                          AND (sender_role IS NULL OR sender_role <> 'team')
                          AND message_date BETWEEN $2 AND $3
                          AND COALESCE(body, message_text) IS NOT NULL
                        ORDER BY message_date
                        LIMIT 50
                        """,
                        conv_id,
                        due,
                        window_end,
                    )
                    found = None
                    for r in rows:
                        if _ACK_PATTERN.search(r["body"]):
                            found = r
                            break
                    if found is None:
                        metrics.no_ack_found += 1
                        continue
                    updates.append((promise_id, found["message_date"], found["id"]))

                if updates and apply:
                    async with conn.transaction():
                        for promise_id, ack_date, ack_msg_id in updates:
                            await conn.execute(
                                """
                                UPDATE team_promises
                                SET resolved = true,
                                    resolved_at = $2,
                                    resolved_by_message_id = $3
                                WHERE promise_id = $1
                                  AND resolved = false
                                """,
                                promise_id,
                                ack_date,
                                ack_msg_id,
                            )
                            metrics.promises_resolved += 1
                elif updates and not apply:
                    metrics.promises_resolved += len(updates)
    except Exception:
        logger.exception("resolve failed")
        metrics.errors += 1
    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_dsn_local() -> str:
    """Build asyncpg DSN pointing at fly-pg-proxy localhost:15432."""
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="team_promises")
    parser.add_argument(
        "subcommand",
        choices=["extract", "resolve", "both"],
        help="Operation to perform",
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="Persist writes")
    g.add_argument("--dry-run", action="store_true", help="Compute only, no DB writes")
    parser.add_argument("--limit", type=int, default=None, help="Cap rows scanned")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    parser.add_argument("--metrics-json", default=None, help="Write metrics to JSON file")
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    dsn = _build_dsn_local()
    if not dsn:
        logger.error("DATABASE_URL or DATABASE_URL_FLY required")
        return 2

    pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=5,
        statement_cache_size=0,  # PgBouncer-safe
        command_timeout=60,
    )
    try:
        combined: dict[str, Any] = {
            "version": EXTRACTOR_VERSION,
            "subcommand": args.subcommand,
            "apply": args.apply,
            "limit": args.limit,
            "batch_size": args.batch_size,
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        if args.subcommand in ("extract", "both"):
            em = await run_extract(
                pool,
                apply=args.apply,
                limit=args.limit,
                batch_size=args.batch_size,
            )
            combined["extract"] = asdict(em)
            logger.info("EXTRACT done: %s", asdict(em))
        if args.subcommand in ("resolve", "both"):
            rm = await run_resolve(
                pool,
                apply=args.apply,
                limit=args.limit,
                batch_size=args.batch_size,
            )
            combined["resolve"] = asdict(rm)
            logger.info("RESOLVE done: %s", asdict(rm))
        combined["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()

        if args.metrics_json:
            with open(args.metrics_json, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2, default=str)
            logger.info("metrics written to %s", args.metrics_json)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))

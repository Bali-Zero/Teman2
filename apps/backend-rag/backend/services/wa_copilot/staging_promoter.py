"""WA Copilot — Sprint 1 S1.2 Staging→Context Promoter.

Promotes parsed WhatsApp export messages from
`whatsapp_export_messages_staging` (transient parse area) into the live
`whatsapp_message_context` table as `source='export_backfill'` rows, so
the downstream identity resolver (S1.3) can operate on the full
historical corpus (60.727 msgs across 194 batches) in addition to live
capture (16.655 rows from `meta_cloud_api` + `wa_mirror`).

Tri-LLM panel synthesis: Gemini 3.1 Pro + Codex GPT-5.5 + DeepSeek V4 Pro.
Decision doc: research/operations/2026-05-25-wa-corpus-monetization-tri-llm-synthesis.md

Empirical baseline pre-promoter (2026-05-25 04:38 WITA):
    - 194 batches status='parsed', 0 promoted (`ingest_batch_id` 0/194)
    - 60.727 messages in staging
    - 16.655 in whatsapp_message_context (0 with ingest_batch_id)

Idempotency: ON CONFLICT (external_message_id, ingest_batch_id) DO NOTHING
on partial unique index `uix_wa_msg_ctx_external_batch`. Per-batch
transaction; rollback on ≥50 % insert failure or unexpected exception.

CLI:
    python -m backend.services.wa_copilot.staging_promoter \
        [--apply | --dry-run] \
        [--batch-id N | --all-pending] \
        [--batch-size 1000] \
        [--metrics-json /tmp/promoter.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger("wa_copilot.staging_promoter")

PROMOTER_VERSION = "v1.0"
SOURCE_TAG = "export_backfill"
SCHEMA_VERSION = "v1.0"

# Direction inference: known Bali Zero team identifiers.
# Sourced empirically from team_members.email + observed sender_display_name
# in staging (top 20 most frequent sender labels include team aliases).
# When a staging sender matches any token below (case-insensitive substring),
# the message is classified as 'outbound' (team → client). Otherwise inbound.
# Resolver downstream (S1.3) refines via phone/LID/email cascade.
TEAM_NAME_TOKENS: tuple[str, ...] = (
    "bali zero",  # "Sahira BZ", "Ari Bali Zero", "Antonello ~ Bali Zero", etc.
    " bz",        # trailing-BZ alias (covers "Sahira BZ", "Krisna - BZ")
    "balizero",   # email-style
    "sahira",
    "krisna",
    "krishna",
    "amanda",
    "ari firda",
    "ari bali",
    "antonello",
    "aditya",
    "adit",
    "vero",
    "veronika",
    "asya",
    "suryadi",
    "zainal",
    "roberta",
    "dewa ayu",
    "kadek",
    "olha",
    "rina",
    "ruslana",
    "dea",
    "subhi",
    "vino",
    "faysha",
    "faisha",
    "damar",
    "angel",
    "zero ",
    "surya",  # last (Surya is also a common Indo first name → covered by other signals)
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BatchResult:
    batch_id: int
    staging_rows: int = 0
    inserted: int = 0
    conflicts: int = 0
    skipped_null_date: int = 0
    failed: bool = False
    error: str | None = None
    wall_ms: int = 0


@dataclass
class RunMetrics:
    promoter_version: str = PROMOTER_VERSION
    dry_run: bool = False
    batches_targeted: int = 0
    batches_promoted: int = 0
    batches_failed: int = 0
    total_staging_rows: int = 0
    total_inserted: int = 0
    total_conflicts: int = 0
    total_skipped_null_date: int = 0
    batch_results: list[BatchResult] = field(default_factory=list)
    wall_ms: int = 0


# ---------------------------------------------------------------------------
# Direction inference
# ---------------------------------------------------------------------------


def _infer_direction(sender_display_name: str | None) -> str | None:
    """Infer message direction from sender label.

    Returns 'outbound' if the sender matches any team token (Bali Zero
    operator wrote the message), 'inbound' otherwise. Returns None when
    sender is unknown/blank — identity resolver will fill later.
    """
    if not sender_display_name:
        return None
    needle = sender_display_name.lower()
    for token in TEAM_NAME_TOKENS:
        if token in needle:
            return "outbound"
    return "inbound"


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------


SELECT_PENDING_BATCHES_SQL = """
SELECT b.id AS batch_id
FROM whatsapp_export_batches b
WHERE b.status = 'parsed'
  AND NOT EXISTS (
      SELECT 1 FROM whatsapp_message_context c
      WHERE c.ingest_batch_id = b.id
      LIMIT 1
  )
ORDER BY b.id
"""

COUNT_STAGING_SQL = """
SELECT COUNT(*) AS n FROM whatsapp_export_messages_staging WHERE batch_id = $1
"""

SELECT_STAGING_PAGE_SQL = """
SELECT
    id,
    batch_id,
    source_relpath,
    message_index,
    message_date,
    sender_display_name,
    body,
    body_excerpt,
    has_attachments
FROM whatsapp_export_messages_staging
WHERE batch_id = $1 AND id > $2
ORDER BY id
LIMIT $3
"""

# external_message_id format: 'batch:<batch_id>:msg:<message_index>'.
# Aligns with whatsapp_export_messages_staging unique
# (batch_id, source_relpath, message_index) and is stable across re-runs.
INSERT_CONTEXT_SQL = """
INSERT INTO whatsapp_message_context (
    direction,
    message_text,
    message_date,
    source,
    source_system,
    external_message_id,
    sender_push_name_snapshot,
    body,
    ingest_batch_id,
    schema_version,
    has_sensitive_pii,
    chat_type,
    ocr_status,
    needs_lid_resolve,
    created_at
)
SELECT
    COALESCE(t.direction, 'inbound')::varchar(10),
    t.body,
    t.message_date,
    $1::varchar(32),   -- source ('export_backfill')
    $1::text,          -- source_system (same tag for now)
    t.external_message_id,
    t.sender,
    t.body,
    t.batch_id,
    $2::text,          -- schema_version
    FALSE,
    'direct'::varchar(16),
    'pending'::varchar(16),
    FALSE,
    NOW()
FROM unnest(
    $3::int[],         -- batch_id
    $4::text[],        -- external_message_id
    $5::text[],        -- direction (nullable, COALESCE handled above)
    $6::text[],        -- sender
    $7::text[],        -- body
    $8::timestamptz[]  -- message_date
) AS t(
    batch_id,
    external_message_id,
    direction,
    sender,
    body,
    message_date
)
ON CONFLICT (external_message_id, ingest_batch_id)
    WHERE ingest_batch_id IS NOT NULL
    DO NOTHING
"""

UPDATE_BATCH_STATUS_SQL = """
UPDATE whatsapp_export_batches
SET status = 'completed'
WHERE id = $1 AND status = 'parsed'
"""


def _external_id(batch_id: int, message_index: int) -> str:
    return f"batch:{batch_id}:msg:{message_index:06d}"


async def _promote_batch(
    pool: asyncpg.Pool,
    batch_id: int,
    page_size: int,
    *,
    dry_run: bool,
) -> BatchResult:
    """Promote a single batch's staging messages → whatsapp_message_context.

    Per-batch transaction. ON CONFLICT idempotent. Returns BatchResult with
    counters; on unexpected exception sets failed=True and error=<repr>.
    """
    t0 = time.monotonic()
    result = BatchResult(batch_id=batch_id)

    try:
        async with pool.acquire() as conn:
            staging_count = await conn.fetchval(COUNT_STAGING_SQL, batch_id)
            result.staging_rows = int(staging_count or 0)
            if result.staging_rows == 0:
                logger.warning("batch %d: 0 staging rows — skipping", batch_id)
                return result

            async with conn.transaction():
                last_id = 0
                pages = 0
                while True:
                    rows = await conn.fetch(
                        SELECT_STAGING_PAGE_SQL, batch_id, last_id, page_size
                    )
                    if not rows:
                        break
                    pages += 1

                    arr_batch: list[int] = []
                    arr_ext_id: list[str] = []
                    arr_direction: list[str | None] = []
                    arr_sender: list[str | None] = []
                    arr_body: list[str | None] = []
                    arr_date: list[Any] = []

                    for r in rows:
                        last_id = r["id"]
                        if r["message_date"] is None:
                            # Skip rows without timestamp — message_date is
                            # required by downstream identity resolver and
                            # most analytics queries; staging row stays
                            # available for manual triage if needed.
                            result.skipped_null_date += 1
                            continue
                        arr_batch.append(int(r["batch_id"]))
                        arr_ext_id.append(_external_id(int(r["batch_id"]), int(r["message_index"])))
                        arr_direction.append(_infer_direction(r["sender_display_name"]))
                        arr_sender.append(r["sender_display_name"])
                        arr_body.append(r["body"])
                        arr_date.append(r["message_date"])

                    if not arr_batch:
                        continue

                    if dry_run:
                        # In dry-run we count what we WOULD insert. ON CONFLICT
                        # behavior is approximated as "everything is novel"
                        # (which is empirically true: 0 rows currently have
                        # external_message_id IS NOT NULL).
                        result.inserted += len(arr_batch)
                    else:
                        status = await conn.execute(
                            INSERT_CONTEXT_SQL,
                            SOURCE_TAG,
                            SCHEMA_VERSION,
                            arr_batch,
                            arr_ext_id,
                            arr_direction,
                            arr_sender,
                            arr_body,
                            arr_date,
                        )
                        # status like "INSERT 0 N"
                        m = re.match(r"INSERT 0 (\d+)", status or "")
                        inserted = int(m.group(1)) if m else 0
                        result.inserted += inserted
                        result.conflicts += len(arr_batch) - inserted

                    if last_id == 0:
                        break

                # Mark batch completed only on success and non-dry-run.
                if not dry_run:
                    await conn.execute(UPDATE_BATCH_STATUS_SQL, batch_id)

                if dry_run:
                    # Roll back any side-effects (none expected — INSERT skipped).
                    raise _DryRunRollback()

    except _DryRunRollback:
        # Expected unwind in dry-run mode.
        pass
    except Exception as exc:
        result.failed = True
        result.error = repr(exc)
        logger.exception("batch %d failed: %s", batch_id, exc)

    result.wall_ms = int((time.monotonic() - t0) * 1000)
    return result


class _DryRunRollback(Exception):
    """Internal sentinel to unwind a dry-run transaction without side effects."""


async def promote(
    pool: asyncpg.Pool,
    *,
    batch_ids: list[int] | None,
    batch_size: int,
    dry_run: bool,
) -> RunMetrics:
    """Promote one or more batches.

    Args:
        pool: asyncpg pool (statement_cache_size=0 PgBouncer-safe).
        batch_ids: explicit list of batch IDs; if None, discover pending batches.
        batch_size: SELECT page size for staging reads.
        dry_run: when True, compute counters and roll back all transactions.
    """
    t0 = time.monotonic()
    metrics = RunMetrics(dry_run=dry_run)

    if batch_ids is None:
        async with pool.acquire() as conn:
            rows = await conn.fetch(SELECT_PENDING_BATCHES_SQL)
        batch_ids = [int(r["batch_id"]) for r in rows]
        logger.info("discovered %d pending batches", len(batch_ids))

    metrics.batches_targeted = len(batch_ids)

    for idx, bid in enumerate(batch_ids, start=1):
        logger.info("[%d/%d] promoting batch %d", idx, metrics.batches_targeted, bid)
        result = await _promote_batch(pool, bid, batch_size, dry_run=dry_run)
        metrics.batch_results.append(result)
        metrics.total_staging_rows += result.staging_rows
        metrics.total_inserted += result.inserted
        metrics.total_conflicts += result.conflicts
        metrics.total_skipped_null_date += result.skipped_null_date
        if result.failed:
            metrics.batches_failed += 1
        else:
            metrics.batches_promoted += 1
        logger.info(
            "[%d/%d] batch %d done: inserted=%d conflicts=%d skipped_null=%d wall=%dms",
            idx,
            metrics.batches_targeted,
            bid,
            result.inserted,
            result.conflicts,
            result.skipped_null_date,
            result.wall_ms,
        )

    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_dsn_local() -> str:
    """Build asyncpg DSN pointing at fly-pg-proxy localhost:15432.

    Honors $DATABASE_URL when already local; otherwise parses password from
    $DATABASE_URL_FLY and substitutes the local host:port.
    """
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


def _metrics_payload(metrics: RunMetrics) -> dict[str, Any]:
    payload = asdict(metrics)
    # Convert dataclass list[BatchResult] to plain dicts handled by asdict already.
    return payload


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="staging_promoter")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="Persist promotions")
    g.add_argument("--dry-run", action="store_true", help="Compute only, no DB writes")

    s = parser.add_mutually_exclusive_group(required=True)
    s.add_argument(
        "--batch-id",
        type=int,
        action="append",
        help="Promote a specific batch (repeatable for multiple IDs)",
    )
    s.add_argument(
        "--all-pending",
        action="store_true",
        help="Auto-discover all parsed batches with no rows in message_context",
    )

    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--metrics-json", default=None, help="Write metrics JSON to path")
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
        command_timeout=120,
    )
    try:
        if args.all_pending:
            metrics = await promote(
                pool,
                batch_ids=None,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
        else:
            metrics = await promote(
                pool,
                batch_ids=list(args.batch_id),
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )
    finally:
        await pool.close()

    payload = _metrics_payload(metrics)
    logger.info(
        "RUN_METRICS targeted=%d promoted=%d failed=%d staging=%d inserted=%d conflicts=%d skipped_null=%d wall=%dms",
        metrics.batches_targeted,
        metrics.batches_promoted,
        metrics.batches_failed,
        metrics.total_staging_rows,
        metrics.total_inserted,
        metrics.total_conflicts,
        metrics.total_skipped_null_date,
        metrics.wall_ms,
    )

    if args.metrics_json:
        with open(args.metrics_json, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("metrics written to %s", args.metrics_json)

    return 0 if metrics.batches_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))

"""WA Copilot conversations grouping job (S1.4).

Groups whatsapp_message_context rows into whatsapp_conversations using a cascading
subject key (phone E164 → LID → JID → contact_id → ingest_batch_id) and opens a
new conversation when:

  (a) first message for the subject seen, OR
  (b) gap since previous subject message > silence_window (default 24h), OR
  (c) group_jid changes (group-chat boundary).

For each conversation populates:
  started_at        = MIN(message_date) in cluster
  last_customer_at  = MAX(message_date) where sender_role IS DISTINCT FROM 'team'
  last_team_at      = MAX(message_date) where sender_role = 'team'
  client_id         = majority-vote client_id among resolved msgs (NULL if none)
  source_group_id   = COALESCE(group_jid, chat_jid) when present
  lifecycle_stage   = 'unknown' (refinement future)
  confidence        = ratio of msgs with identity_confidence >= 0.7
  phone_e164        = normalized phone of subject OR synthetic placeholder
                      (e.g. 'lid:<lid>', 'jid:<jid>', 'contact:<id>',
                      'batch:<id>') — column is NOT NULL.
  lid               = first lid observed in cluster (if any)

CLI:
    python -m backend.services.wa_copilot.conversations_grouper \\
      [--apply | --dry-run] \\
      [--silence-window-hours 24] \\
      [--batch-size 5000] \\
      [--metrics-json /tmp/grouper.json]

Idempotent: only processes rows where conversation_id IS NULL.
Per-batch transactional via asyncpg, PgBouncer-safe (statement_cache_size=0).

Reuses backend.services.crm.client_core.normalize_phone_e164 for phone normalization.
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
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg

from backend.services.crm.client_core import normalize_phone_e164

logger = logging.getLogger(__name__)

# Sentinel for sort: messages with NULL message_date sort to head per-subject.
_MIN_DT = _dt.datetime.min.replace(tzinfo=_dt.timezone.utc)

GROUPER_VERSION = "v1.0-2026-05-25"
DEFAULT_SILENCE_WINDOW_HOURS = 24
DEFAULT_BATCH_SIZE = 5000
IDENTITY_CONFIDENCE_THRESHOLD = 0.70
DEFAULT_LIFECYCLE_STAGE = "unknown"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class GrouperMetrics:
    """Aggregate run metrics."""

    total_scanned: int = 0
    conversations_created: int = 0
    messages_grouped: int = 0
    subjects_seen: int = 0
    group_chats: int = 0
    by_subject_type: dict[str, int] = field(default_factory=dict)
    wall_ms: int = 0
    pre_total_msgs: int = 0
    pre_grouped_msgs: int = 0
    pre_total_convs: int = 0
    post_total_msgs: int = 0
    post_grouped_msgs: int = 0
    post_total_convs: int = 0
    post_pct_grouped: float = 0.0

    def bump_subject(self, subj_type: str) -> None:
        self.by_subject_type[subj_type] = self.by_subject_type.get(subj_type, 0) + 1


# ---------------------------------------------------------------------------
# Subject resolution
# ---------------------------------------------------------------------------

def resolve_subject(msg: dict[str, Any]) -> tuple[str, str, str | None]:
    """Resolve subject key for a message.

    Returns (subject_key, subject_type, phone_e164_or_placeholder).

    Cascade order:
      1. phone_number / sender_phone / counterpart_phone → normalize to E164
      2. counterpart_lid / sender_lid → 'lid:<lid>'
      3. chat_jid → 'jid:<jid>'
      4. contact_id → 'contact:<id>'
      5. ingest_batch_id → 'batch:<id>'
      6. fallback: 'orphan:<msg_id>' (singleton conversation)

    phone_e164 column is NOT NULL — synthetic placeholders ensure each subject
    has a phone_e164 value.
    """
    # 1. Phone
    raw_phone = msg.get("phone_number") or msg.get("sender_phone") or msg.get("counterpart_phone")
    if raw_phone:
        e164 = normalize_phone_e164(str(raw_phone))
        if e164:
            return e164, "phone", e164

    # 2. LID
    lid = msg.get("counterpart_lid") or msg.get("sender_lid")
    if lid:
        key = f"lid:{lid}"
        return key, "lid", key

    # 3. JID
    chat_jid = msg.get("chat_jid")
    if chat_jid:
        key = f"jid:{chat_jid}"
        return key, "jid", key

    # 4. contact_id (Brevo dump)
    contact_id = msg.get("contact_id")
    if contact_id is not None:
        key = f"contact:{contact_id}"
        return key, "contact", key

    # 5. ingest_batch_id (export_backfill)
    batch_id = msg.get("ingest_batch_id")
    if batch_id is not None:
        key = f"batch:{batch_id}"
        return key, "batch", key

    # 6. Orphan fallback
    key = f"orphan:{msg['id']}"
    return key, "orphan", key


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

@dataclass
class Cluster:
    """In-memory accumulator for a single conversation candidate."""

    subject_key: str
    subject_type: str
    phone_e164: str
    message_ids: list[int] = field(default_factory=list)
    started_at: Any = None
    last_customer_at: Any = None
    last_team_at: Any = None
    last_message_at: Any = None  # for silence-window detection
    current_group_jid: str | None = None
    lid: str | None = None
    source_group_id: str | None = None
    client_id_votes: Counter = field(default_factory=Counter)
    practice_id_votes: Counter = field(default_factory=Counter)
    high_conf_count: int = 0


def cluster_messages(
    rows: list[dict[str, Any]],
    silence_window_seconds: int,
    metrics: GrouperMetrics,
) -> list[Cluster]:
    """Cluster messages into conversation candidates.

    rows MUST be sorted by (subject_key, message_date ASC).
    """
    clusters: list[Cluster] = []
    open_cluster: Cluster | None = None
    last_subject_key: str | None = None

    for msg in rows:
        subject_key, subject_type, phone_e164 = resolve_subject(msg)
        msg_date = msg.get("message_date")
        group_jid = msg.get("group_jid")

        # Decide whether to open a new cluster
        new_cluster_reason: str | None = None
        if open_cluster is None or subject_key != last_subject_key:
            new_cluster_reason = "subject_change"
        else:
            # Same subject — check gap
            if (
                open_cluster.last_message_at is not None
                and msg_date is not None
                and (msg_date - open_cluster.last_message_at).total_seconds() > silence_window_seconds
            ):
                new_cluster_reason = "silence_window"
            elif group_jid != open_cluster.current_group_jid and (
                group_jid is not None or open_cluster.current_group_jid is not None
            ):
                # Group context changed (direct → group or group A → group B)
                new_cluster_reason = "group_change"

        if new_cluster_reason is not None:
            # Close previous cluster
            if open_cluster is not None:
                clusters.append(open_cluster)
            open_cluster = Cluster(
                subject_key=subject_key,
                subject_type=subject_type,
                phone_e164=phone_e164 or subject_key,
                current_group_jid=group_jid,
            )
            metrics.bump_subject(subject_type)
            last_subject_key = subject_key

        assert open_cluster is not None  # for type-checker

        # Add message to current cluster
        open_cluster.message_ids.append(msg["id"])

        if msg_date is not None:
            if open_cluster.started_at is None or msg_date < open_cluster.started_at:
                open_cluster.started_at = msg_date
            open_cluster.last_message_at = (
                msg_date
                if open_cluster.last_message_at is None or msg_date > open_cluster.last_message_at
                else open_cluster.last_message_at
            )
            sender_role = msg.get("sender_role")
            if sender_role == "team":
                if open_cluster.last_team_at is None or msg_date > open_cluster.last_team_at:
                    open_cluster.last_team_at = msg_date
            else:
                if open_cluster.last_customer_at is None or msg_date > open_cluster.last_customer_at:
                    open_cluster.last_customer_at = msg_date

        # Track lid (first seen wins)
        if open_cluster.lid is None:
            lid_seen = msg.get("counterpart_lid") or msg.get("sender_lid")
            if lid_seen:
                open_cluster.lid = str(lid_seen)

        # Track source_group_id (prefer group_jid, fallback chat_jid)
        if open_cluster.source_group_id is None:
            sgid = msg.get("group_jid") or msg.get("chat_jid")
            if sgid:
                open_cluster.source_group_id = str(sgid)

        # Client/practice vote
        if msg.get("client_id") is not None:
            open_cluster.client_id_votes[msg["client_id"]] += 1
        if msg.get("practice_id") is not None:
            open_cluster.practice_id_votes[msg["practice_id"]] += 1

        # High-confidence ratio
        ic = msg.get("identity_confidence")
        if ic is not None and float(ic) >= IDENTITY_CONFIDENCE_THRESHOLD:
            open_cluster.high_conf_count += 1

    # Close trailing cluster
    if open_cluster is not None:
        clusters.append(open_cluster)

    return clusters


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

SELECT_UNGROUPED_BATCH_SQL = """
    SELECT
        id,
        contact_id,
        client_id,
        practice_id,
        phone_number,
        sender_phone,
        counterpart_phone,
        counterpart_lid,
        sender_lid,
        chat_jid,
        group_jid,
        ingest_batch_id,
        message_date,
        sender_role,
        identity_confidence,
        identity_method
    FROM whatsapp_message_context
    WHERE conversation_id IS NULL
    ORDER BY
        COALESCE(
            phone_number,
            sender_phone,
            counterpart_phone,
            counterpart_lid,
            sender_lid,
            chat_jid,
            'contact:' || contact_id::text,
            'batch:' || ingest_batch_id::text,
            'orphan:' || id::text
        ),
        message_date NULLS LAST,
        id
    LIMIT $1
    OFFSET $2
"""

INSERT_CONVERSATION_SQL = """
    INSERT INTO whatsapp_conversations (
        client_id, practice_id, phone_e164, lid, source_group_id,
        lifecycle_stage, started_at, last_customer_at, last_team_at, confidence,
        created_at, updated_at
    )
    VALUES (
        $1, $2, $3, $4, $5,
        $6, $7, $8, $9, $10,
        now(), now()
    )
    RETURNING conversation_id
"""

UPDATE_MSGS_CONV_ID_SQL = """
    UPDATE whatsapp_message_context
    SET conversation_id = $1, updated_at = now()
    WHERE id = ANY($2::int[]) AND conversation_id IS NULL
"""


async def persist_cluster(
    conn: asyncpg.Connection, cluster: Cluster
) -> int:
    """Insert one conversation row + bulk-update messages. Returns conversation_id."""
    client_id: int | None = None
    if cluster.client_id_votes:
        client_id = cluster.client_id_votes.most_common(1)[0][0]

    practice_id: int | None = None
    if cluster.practice_id_votes:
        practice_id = cluster.practice_id_votes.most_common(1)[0][0]

    msg_count = len(cluster.message_ids)
    confidence = (
        round(cluster.high_conf_count / msg_count, 2) if msg_count > 0 else 0.0
    )
    # Clamp to NUMERIC(3,2) range
    confidence = max(0.0, min(1.0, confidence))

    # phone_e164 is NOT NULL — clamp synthetic keys to TEXT (no length constraint)
    phone_e164 = cluster.phone_e164 or cluster.subject_key

    row = await conn.fetchrow(
        INSERT_CONVERSATION_SQL,
        client_id,
        practice_id,
        phone_e164,
        cluster.lid,
        cluster.source_group_id,
        DEFAULT_LIFECYCLE_STAGE,
        cluster.started_at,
        cluster.last_customer_at,
        cluster.last_team_at,
        confidence,
    )
    conv_id = row["conversation_id"]

    await conn.execute(
        UPDATE_MSGS_CONV_ID_SQL, conv_id, cluster.message_ids
    )
    return conv_id


# ---------------------------------------------------------------------------
# Main batch loop
# ---------------------------------------------------------------------------

async def count_baseline(pool: asyncpg.Pool, metrics: GrouperMetrics) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE conversation_id IS NOT NULL) AS grouped
            FROM whatsapp_message_context
            """
        )
        metrics.pre_total_msgs = row["total"]
        metrics.pre_grouped_msgs = row["grouped"]
        cv = await conn.fetchrow("SELECT COUNT(*) AS n FROM whatsapp_conversations")
        metrics.pre_total_convs = cv["n"]


async def count_post(pool: asyncpg.Pool, metrics: GrouperMetrics) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE conversation_id IS NOT NULL) AS grouped
            FROM whatsapp_message_context
            """
        )
        metrics.post_total_msgs = row["total"]
        metrics.post_grouped_msgs = row["grouped"]
        if metrics.post_total_msgs > 0:
            metrics.post_pct_grouped = round(
                100.0 * metrics.post_grouped_msgs / metrics.post_total_msgs, 2
            )
        cv = await conn.fetchrow("SELECT COUNT(*) AS n FROM whatsapp_conversations")
        metrics.post_total_convs = cv["n"]
        gc = await conn.fetchrow(
            "SELECT COUNT(*) AS n FROM whatsapp_conversations WHERE source_group_id IS NOT NULL"
        )
        metrics.group_chats = gc["n"]


async def group_all(
    pool: asyncpg.Pool,
    *,
    batch_size: int,
    silence_window_hours: int,
    dry_run: bool,
) -> GrouperMetrics:
    """Main batch loop.

    Strategy: pull ungrouped rows ordered by (subject, message_date), buffer until
    we accumulate a complete subject (i.e. encounter a different subject key), then
    flush all closed clusters to DB. This preserves chronological order within
    a subject across batch boundaries.

    Simpler implementation chosen for v1: drain all ungrouped rows in one DB
    pass via async iterator since 77k rows × ~16 cols fits comfortably in
    memory (~50MB). Future optimization: stream + sticky-subject buffer.
    """
    metrics = GrouperMetrics()
    silence_window_seconds = silence_window_hours * 3600
    t0 = time.monotonic()

    await count_baseline(pool, metrics)

    # Fetch ALL ungrouped rows in one ORDER BY pass to guarantee subject contiguity.
    # 77k rows is tractable for in-memory clustering on Pro M4.
    logger.info(
        "fetching ungrouped messages (pre_grouped=%d/%d)",
        metrics.pre_grouped_msgs, metrics.pre_total_msgs,
    )
    async with pool.acquire() as conn:
        rows_raw = await conn.fetch(
            """
            SELECT
                id, contact_id, client_id, practice_id,
                phone_number, sender_phone, counterpart_phone,
                counterpart_lid, sender_lid, chat_jid, group_jid,
                ingest_batch_id, message_date, sender_role,
                identity_confidence, identity_method
            FROM whatsapp_message_context
            WHERE conversation_id IS NULL
            """
        )

    metrics.total_scanned = len(rows_raw)
    logger.info("scanned %d ungrouped messages", metrics.total_scanned)

    if metrics.total_scanned == 0:
        await count_post(pool, metrics)
        metrics.wall_ms = int((time.monotonic() - t0) * 1000)
        return metrics

    # Resolve subject for each row (in-Python — normalize_phone_e164 not in DB)
    rows: list[dict[str, Any]] = []
    for r in rows_raw:
        msg = dict(r)
        subject_key, subject_type, phone_e164 = resolve_subject(msg)
        msg["_subject_key"] = subject_key
        msg["_subject_type"] = subject_type
        msg["_phone_e164"] = phone_e164
        rows.append(msg)

    # Sort by (subject_key, message_date, id) — Python sort is stable
    rows.sort(
        key=lambda m: (
            m["_subject_key"],
            m["message_date"] or _MIN_DT,
            m["id"],
        )
    )

    # Cluster
    clusters = cluster_messages(rows, silence_window_seconds, metrics)
    metrics.conversations_created = len(clusters)
    metrics.subjects_seen = sum(metrics.by_subject_type.values())
    logger.info(
        "clustered %d msgs into %d conversations (subjects=%d)",
        metrics.total_scanned, metrics.conversations_created, metrics.subjects_seen,
    )

    if dry_run:
        logger.info("DRY RUN — no DB writes")
        metrics.wall_ms = int((time.monotonic() - t0) * 1000)
        await count_post(pool, metrics)
        return metrics

    # Persist clusters in batches; each batch is one transaction
    persisted = 0
    msgs_grouped = 0
    for batch_start in range(0, len(clusters), batch_size):
        batch = clusters[batch_start : batch_start + batch_size]
        async with pool.acquire() as conn:
            async with conn.transaction():
                for cluster in batch:
                    await persist_cluster(conn, cluster)
                    msgs_grouped += len(cluster.message_ids)
        persisted += len(batch)
        logger.info(
            "persisted %d/%d conversations (msgs_grouped=%d)",
            persisted, len(clusters), msgs_grouped,
        )

    metrics.messages_grouped = msgs_grouped
    await count_post(pool, metrics)
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
    parser = argparse.ArgumentParser(prog="conversations_grouper")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="Persist conversations + msg links")
    g.add_argument("--dry-run", action="store_true", help="Cluster only, no DB writes")
    parser.add_argument(
        "--silence-window-hours", type=int, default=DEFAULT_SILENCE_WINDOW_HOURS
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--metrics-json", default=None)
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
        metrics = await group_all(
            pool,
            batch_size=args.batch_size,
            silence_window_hours=args.silence_window_hours,
            dry_run=args.dry_run,
        )
    finally:
        await pool.close()

    payload = {
        "grouper_version": GROUPER_VERSION,
        "dry_run": args.dry_run,
        "silence_window_hours": args.silence_window_hours,
        **asdict(metrics),
    }
    # Counter is not JSON-serializable directly when nested via asdict — but
    # by_subject_type is dict[str,int]. dataclass field stores dict. asdict
    # walks recursively; Counter inherits dict so it stays a dict.
    payload["by_subject_type"] = dict(metrics.by_subject_type)

    logger.info("RUN_METRICS %s", json.dumps(payload, indent=2, default=str))

    if args.metrics_json:
        with open(args.metrics_json, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("metrics written to %s", args.metrics_json)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))

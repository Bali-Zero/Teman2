"""WA Copilot practice candidate scorer (S1.7).

Probabilistic linker between WhatsApp conversations (S1.4 grouper output) and
existing CRM practices. Emits weighted-score candidate rows into
``whatsapp_practice_candidates`` for auto-link (≥0.85) or human review
(0.60-0.85) bands.

5-signal weighted scoring (Codex round-2 design):

  Signal               Weight  Source / Logic
  -------------------- ------  ------------------------------------------------
  client_id_match      0.35    Conversation.client_id == Practice.client_id
  service_type_token   0.25    whatsapp_extractions.visa_type vs
                               practice.practice_type_code OR
                               practice_types.{code,name,category}
  attachment_match     0.15    v1 placeholder (returns 0.0 — no attachment FK)
  temporal_overlap     0.15    Conversation last_customer_at within
                               [practice_start − 30d, practice_end + 14d]
  fuzzy_name           0.10    similarity(client.full_name, practice.title)
                               (falls back to 0.5 when title is empty)

  total = 0.35*c + 0.25*s + 0.15*a + 0.15*t + 0.10*n

Decision bands:
    score >= 0.85  AND  ≥2 signals > 0.5  -> insert status='auto_linked'
    0.60 <= score < 0.85                  -> insert status='pending_review'
    score < 0.60                          -> skip (no row)

Only scores conversations with ``client_id IS NOT NULL`` (signal #1 is the
strongest weight; without it the band cannot be reached). Practice candidates
limited to ``WHERE practice.client_id = conv.client_id AND
practice.created_at < conv.last_customer_at + INTERVAL '14 days' AND
(practice.completion_date IS NULL OR practice.completion_date > conv.started_at - INTERVAL '30 days')``.

Idempotent: existing (conversation_id, practice_id) rows are skipped (INSERT
ON CONFLICT DO NOTHING relies on natural composite uniqueness via
candidate_id PK — we explicitly probe before insert to keep status stable).

CLI:
    python -m backend.services.wa_copilot.practice_scorer \\
      [--apply | --dry-run] \\
      [--batch-size 200] \\
      [--limit N] \\
      [--auto-link-threshold 0.85] \\
      [--review-threshold 0.60] \\
      [--metrics-json /tmp/scorer.json]

PgBouncer-safe asyncpg pool (statement_cache_size=0).
No Anthropic SDK; no LLM calls (pure SQL + arithmetic).
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

logger = logging.getLogger(__name__)

SCORER_VERSION = "v1.0-2026-05-25"
DEFAULT_BATCH_SIZE = 200
DEFAULT_AUTO_LINK_THRESHOLD = 0.85
DEFAULT_REVIEW_THRESHOLD = 0.60
MIN_STRONG_SIGNALS_FOR_AUTO_LINK = 2
STRONG_SIGNAL_THRESHOLD = 0.5

# Signal weights — sum to 1.0
WEIGHT_CLIENT_ID_MATCH = 0.35
WEIGHT_SERVICE_TYPE_TOKEN = 0.25
WEIGHT_ATTACHMENT_MATCH = 0.15
WEIGHT_TEMPORAL_OVERLAP = 0.15
WEIGHT_FUZZY_NAME = 0.10

# Time windows
PRACTICE_LOOKFORWARD_DAYS = 14
PRACTICE_LOOKBACK_DAYS = 30
TEMPORAL_OVERLAP_SLACK_DAYS = 30  # outside-window decay window
TEMPORAL_FORWARD_GRACE_DAYS = 14

# Fuzzy name fallback when practice has no title
FUZZY_NAME_FALLBACK = 0.5


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ScorerMetrics:
    """Aggregate run metrics."""

    conversations_scanned: int = 0
    conversations_without_client_id: int = 0
    conversations_no_candidates: int = 0
    practice_pairs_evaluated: int = 0
    candidates_auto_linked: int = 0
    candidates_pending_review: int = 0
    candidates_skipped_low_score: int = 0
    candidates_skipped_already_exists: int = 0
    score_distribution: dict[str, int] = field(default_factory=Counter)
    signal_avg: dict[str, float] = field(default_factory=dict)
    wall_ms: int = 0


@dataclass
class ConversationCtx:
    """Hydrated conversation for scoring."""

    conversation_id: int
    client_id: int
    client_full_name: str | None
    started_at: _dt.datetime | None
    last_customer_at: _dt.datetime | None
    visa_type_tokens: set[str]


@dataclass
class PracticeCtx:
    """Hydrated practice for scoring."""

    practice_id: int
    client_id: int
    practice_type_code: str | None
    practice_type_id: int | None
    title: str | None
    type_code: str | None  # from practice_types JOIN
    type_name: str | None
    type_category: str | None
    created_at: _dt.datetime
    inquiry_date: _dt.datetime | None
    completion_date: _dt.datetime | None


@dataclass
class ScoreBreakdown:
    """Per-pair signal scores."""

    client_id_match: float
    service_type_token: float
    attachment_match: float
    temporal_overlap: float
    fuzzy_name: float
    total: float

    def strong_signals(self) -> int:
        return sum(
            1 for v in (
                self.client_id_match,
                self.service_type_token,
                self.attachment_match,
                self.temporal_overlap,
                self.fuzzy_name,
            ) if v > STRONG_SIGNAL_THRESHOLD
        )

    def as_signals_json(self) -> dict[str, float]:
        return {
            "client_id_match": round(self.client_id_match, 4),
            "service_type_token": round(self.service_type_token, 4),
            "attachment_match": round(self.attachment_match, 4),
            "temporal_overlap": round(self.temporal_overlap, 4),
            "fuzzy_name": round(self.fuzzy_name, 4),
            "total": round(self.total, 4),
            "scorer_version": SCORER_VERSION,
        }


# ---------------------------------------------------------------------------
# Scoring primitives
# ---------------------------------------------------------------------------

def _normalize_token(s: str) -> str:
    """Uppercase, strip non-alnum to single space, trim."""
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def score_client_id_match(conv: ConversationCtx, practice: PracticeCtx) -> float:
    return 1.0 if conv.client_id == practice.client_id else 0.0


def score_service_type_token(conv: ConversationCtx, practice: PracticeCtx) -> float:
    """Compare extraction visa_type tokens to practice service type signals.

    Practice service type sources (in order of strength):
      - practice.practice_type_code     (e.g. 'kitas', 'visa')
      - practice_types.code             (e.g. 'kitas_investor_2yr_offshore')
      - practice_types.name             (e.g. 'Investor KITAS 2 Years (Offshore)')
      - practice_types.category         (e.g. 'kitas', 'single_entry_visa')

    Returns 1.0 for exact token match, 0.8 for partial substring match, 0.0 else.
    """
    if not conv.visa_type_tokens:
        return 0.0

    practice_tokens: set[str] = set()
    for src in (
        practice.practice_type_code,
        practice.type_code,
        practice.type_name,
        practice.type_category,
    ):
        if not src:
            continue
        normalized = _normalize_token(src)
        if normalized:
            practice_tokens.add(normalized)
            # Also add individual words for substring-style matching
            for word in normalized.split():
                if len(word) >= 3:  # skip noise like "PT", "1Y"
                    practice_tokens.add(word)

    if not practice_tokens:
        return 0.0

    best = 0.0
    for vt in conv.visa_type_tokens:
        vt_norm = _normalize_token(vt)
        if not vt_norm:
            continue
        # Exact full-token match
        if vt_norm in practice_tokens:
            return 1.0
        # Substring either direction (e.g. 'KITAS' in 'INVESTOR KITAS 2 YEARS')
        for pt in practice_tokens:
            if vt_norm in pt or pt in vt_norm:
                if len(vt_norm) >= 3 and len(pt) >= 3:
                    best = max(best, 0.8)
    return best


def score_attachment_match(conv: ConversationCtx, practice: PracticeCtx) -> float:
    """v1 placeholder — no attachment FK ready. Always 0.0."""
    return 0.0


def score_temporal_overlap(conv: ConversationCtx, practice: PracticeCtx) -> float:
    """Conversation in [practice_start - 30d, practice_end + 14d] → 1.0.

    Decays by days outside that window divided by 30.
    """
    if conv.last_customer_at is None:
        return 0.0

    practice_start = practice.inquiry_date or practice.created_at
    practice_end = practice.completion_date or (
        _dt.datetime.now(_dt.timezone.utc)
    )

    # Normalize to aware
    if practice_start.tzinfo is None:
        practice_start = practice_start.replace(tzinfo=_dt.timezone.utc)
    if practice_end.tzinfo is None:
        practice_end = practice_end.replace(tzinfo=_dt.timezone.utc)

    window_start = practice_start - _dt.timedelta(days=PRACTICE_LOOKBACK_DAYS)
    window_end = practice_end + _dt.timedelta(days=TEMPORAL_FORWARD_GRACE_DAYS)

    msg_dt = conv.last_customer_at
    if msg_dt.tzinfo is None:
        msg_dt = msg_dt.replace(tzinfo=_dt.timezone.utc)

    if window_start <= msg_dt <= window_end:
        return 1.0

    if msg_dt < window_start:
        days_outside = (window_start - msg_dt).days
    else:
        days_outside = (msg_dt - window_end).days

    decay = max(0.0, 1.0 - days_outside / TEMPORAL_OVERLAP_SLACK_DAYS)
    return round(decay, 4)


def compute_weighted_total(breakdown_partial: dict[str, float]) -> float:
    return round(
        WEIGHT_CLIENT_ID_MATCH * breakdown_partial["client_id_match"]
        + WEIGHT_SERVICE_TYPE_TOKEN * breakdown_partial["service_type_token"]
        + WEIGHT_ATTACHMENT_MATCH * breakdown_partial["attachment_match"]
        + WEIGHT_TEMPORAL_OVERLAP * breakdown_partial["temporal_overlap"]
        + WEIGHT_FUZZY_NAME * breakdown_partial["fuzzy_name"],
        4,
    )


# ---------------------------------------------------------------------------
# Data hydration
# ---------------------------------------------------------------------------

async def fetch_conversations(
    pool: asyncpg.Pool, limit: int | None
) -> list[ConversationCtx]:
    """Pull all conversations with client_id resolved + their visa_type extractions
    and client full_name.
    """
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    sql = f"""
        SELECT
            c.conversation_id,
            c.client_id,
            c.started_at,
            c.last_customer_at,
            cl.full_name AS client_full_name,
            COALESCE(
                (
                    SELECT array_agg(DISTINCT (e.fact_value->>'value'))
                    FROM whatsapp_extractions e
                    WHERE e.conversation_id = c.conversation_id
                      AND e.fact_type = 'visa_type'
                      AND e.fact_value ? 'value'
                ),
                ARRAY[]::text[]
            ) AS visa_types
        FROM whatsapp_conversations c
        LEFT JOIN clients cl ON cl.id = c.client_id
        WHERE c.client_id IS NOT NULL
        ORDER BY c.conversation_id
        {limit_clause}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
    out: list[ConversationCtx] = []
    for r in rows:
        out.append(
            ConversationCtx(
                conversation_id=int(r["conversation_id"]),
                client_id=int(r["client_id"]),
                client_full_name=r["client_full_name"],
                started_at=r["started_at"],
                last_customer_at=r["last_customer_at"],
                visa_type_tokens={v for v in (r["visa_types"] or []) if v},
            )
        )
    return out


async def fetch_practices_for_client(
    conn: asyncpg.Connection,
    client_id: int,
    conv_last_customer_at: _dt.datetime | None,
    conv_started_at: _dt.datetime | None,
) -> list[PracticeCtx]:
    """Pull candidate practices for a client within the temporal window."""
    # When timestamps are missing, fall back to a wider net (NULL guards).
    sql = """
        SELECT
            p.id AS practice_id,
            p.client_id,
            p.practice_type_code,
            p.practice_type_id,
            p.title,
            pt.code AS type_code,
            pt.name AS type_name,
            pt.category AS type_category,
            p.created_at,
            p.inquiry_date,
            p.completion_date
        FROM practices p
        LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
        WHERE p.client_id = $1
          AND ($2::timestamptz IS NULL OR p.created_at < $2::timestamptz + INTERVAL '14 days')
          AND (
              p.completion_date IS NULL
              OR $3::timestamptz IS NULL
              OR p.completion_date > $3::timestamptz - INTERVAL '30 days'
          )
        ORDER BY p.created_at DESC
    """
    rows = await conn.fetch(sql, client_id, conv_last_customer_at, conv_started_at)
    out: list[PracticeCtx] = []
    for r in rows:
        out.append(
            PracticeCtx(
                practice_id=int(r["practice_id"]),
                client_id=int(r["client_id"]),
                practice_type_code=r["practice_type_code"],
                practice_type_id=r["practice_type_id"],
                title=r["title"],
                type_code=r["type_code"],
                type_name=r["type_name"],
                type_category=r["type_category"],
                created_at=r["created_at"],
                inquiry_date=r["inquiry_date"],
                completion_date=r["completion_date"],
            )
        )
    return out


async def fuzzy_name_similarity(
    conn: asyncpg.Connection,
    client_full_name: str | None,
    practice_title: str | None,
) -> float:
    """Compute pg_trgm similarity between client.full_name and practice.title.

    Returns FUZZY_NAME_FALLBACK (0.5) when practice has no title (most rows).
    """
    if not practice_title or not practice_title.strip():
        return FUZZY_NAME_FALLBACK
    if not client_full_name or not client_full_name.strip():
        return 0.0
    row = await conn.fetchrow(
        "SELECT similarity($1::text, $2::text) AS sim",
        client_full_name, practice_title,
    )
    sim = float(row["sim"] or 0.0)
    return round(sim, 4)


# ---------------------------------------------------------------------------
# Scoring loop
# ---------------------------------------------------------------------------

async def score_pair(
    conn: asyncpg.Connection,
    conv: ConversationCtx,
    practice: PracticeCtx,
) -> ScoreBreakdown:
    c = score_client_id_match(conv, practice)
    s = score_service_type_token(conv, practice)
    a = score_attachment_match(conv, practice)
    t = score_temporal_overlap(conv, practice)
    n = await fuzzy_name_similarity(conn, conv.client_full_name, practice.title)
    partial = {
        "client_id_match": c,
        "service_type_token": s,
        "attachment_match": a,
        "temporal_overlap": t,
        "fuzzy_name": n,
    }
    total = compute_weighted_total(partial)
    return ScoreBreakdown(
        client_id_match=c,
        service_type_token=s,
        attachment_match=a,
        temporal_overlap=t,
        fuzzy_name=n,
        total=total,
    )


async def candidate_exists(
    conn: asyncpg.Connection, conversation_id: int, practice_id: int
) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1 FROM whatsapp_practice_candidates
        WHERE conversation_id = $1 AND practice_id = $2
        LIMIT 1
        """,
        conversation_id, practice_id,
    )
    return row is not None


async def insert_candidate(
    conn: asyncpg.Connection,
    *,
    conversation_id: int,
    practice_id: int,
    breakdown: ScoreBreakdown,
    status: str,
) -> None:
    # confidence column is NUMERIC(3,2) → clamp to [0, 0.99] band
    conf = max(0.0, min(0.99, breakdown.total))
    await conn.execute(
        """
        INSERT INTO whatsapp_practice_candidates
            (conversation_id, practice_id, confidence, signals, status, created_at)
        VALUES ($1, $2, $3::numeric, $4::jsonb, $5, now())
        """,
        conversation_id,
        practice_id,
        round(conf, 2),
        json.dumps(breakdown.as_signals_json()),
        status,
    )


def _score_bucket(score: float) -> str:
    if score >= 0.90:
        return "0.90-1.00"
    if score >= 0.85:
        return "0.85-0.90"
    if score >= 0.70:
        return "0.70-0.85"
    if score >= 0.60:
        return "0.60-0.70"
    if score >= 0.40:
        return "0.40-0.60"
    if score >= 0.20:
        return "0.20-0.40"
    return "0.00-0.20"


async def score_all(
    pool: asyncpg.Pool,
    *,
    batch_size: int,
    limit: int | None,
    auto_link_threshold: float,
    review_threshold: float,
    dry_run: bool,
) -> ScorerMetrics:
    metrics = ScorerMetrics()
    t0 = time.monotonic()

    # Pre-flight count of conversations without client_id (audit signal only)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS n FROM whatsapp_conversations WHERE client_id IS NULL"
        )
        metrics.conversations_without_client_id = int(row["n"])

    conversations = await fetch_conversations(pool, limit=limit)
    metrics.conversations_scanned = len(conversations)
    logger.info(
        "loaded %d conversations with client_id (skipping %d without)",
        metrics.conversations_scanned,
        metrics.conversations_without_client_id,
    )

    if metrics.conversations_scanned == 0:
        metrics.wall_ms = int((time.monotonic() - t0) * 1000)
        return metrics

    # Per-signal running averages
    signal_sums: Counter = Counter()
    signal_counts: Counter = Counter()

    inserts_buffered: list[tuple[int, int, ScoreBreakdown, str]] = []

    async with pool.acquire() as conn:
        for idx, conv in enumerate(conversations):
            practices = await fetch_practices_for_client(
                conn,
                conv.client_id,
                conv.last_customer_at,
                conv.started_at,
            )
            if not practices:
                metrics.conversations_no_candidates += 1
                continue

            for practice in practices:
                breakdown = await score_pair(conn, conv, practice)
                metrics.practice_pairs_evaluated += 1
                metrics.score_distribution[_score_bucket(breakdown.total)] += 1

                signal_sums["client_id_match"] += breakdown.client_id_match
                signal_sums["service_type_token"] += breakdown.service_type_token
                signal_sums["attachment_match"] += breakdown.attachment_match
                signal_sums["temporal_overlap"] += breakdown.temporal_overlap
                signal_sums["fuzzy_name"] += breakdown.fuzzy_name
                for k in (
                    "client_id_match",
                    "service_type_token",
                    "attachment_match",
                    "temporal_overlap",
                    "fuzzy_name",
                ):
                    signal_counts[k] += 1

                if breakdown.total < review_threshold:
                    metrics.candidates_skipped_low_score += 1
                    continue

                if (
                    breakdown.total >= auto_link_threshold
                    and breakdown.strong_signals() >= MIN_STRONG_SIGNALS_FOR_AUTO_LINK
                ):
                    status = "auto_linked"
                else:
                    status = "pending_review"

                # Dedup probe even in dry-run for accurate counts
                if await candidate_exists(conn, conv.conversation_id, practice.practice_id):
                    metrics.candidates_skipped_already_exists += 1
                    continue

                if status == "auto_linked":
                    metrics.candidates_auto_linked += 1
                else:
                    metrics.candidates_pending_review += 1

                inserts_buffered.append(
                    (conv.conversation_id, practice.practice_id, breakdown, status)
                )

            if (idx + 1) % 100 == 0:
                logger.info(
                    "scored %d/%d conversations (pairs_evaluated=%d, auto=%d, review=%d, low=%d, dup=%d)",
                    idx + 1, len(conversations),
                    metrics.practice_pairs_evaluated,
                    metrics.candidates_auto_linked,
                    metrics.candidates_pending_review,
                    metrics.candidates_skipped_low_score,
                    metrics.candidates_skipped_already_exists,
                )

    # Compute signal averages
    for k, total in signal_sums.items():
        if signal_counts[k] > 0:
            metrics.signal_avg[k] = round(total / signal_counts[k], 4)

    if dry_run:
        logger.info(
            "DRY RUN — skipping %d candidate inserts (auto=%d, review=%d)",
            len(inserts_buffered),
            metrics.candidates_auto_linked,
            metrics.candidates_pending_review,
        )
        metrics.wall_ms = int((time.monotonic() - t0) * 1000)
        return metrics

    # Persist in batches
    persisted = 0
    for batch_start in range(0, len(inserts_buffered), batch_size):
        batch = inserts_buffered[batch_start : batch_start + batch_size]
        async with pool.acquire() as conn:
            async with conn.transaction():
                for conv_id, pr_id, breakdown, status in batch:
                    await insert_candidate(
                        conn,
                        conversation_id=conv_id,
                        practice_id=pr_id,
                        breakdown=breakdown,
                        status=status,
                    )
        persisted += len(batch)
        logger.info("persisted %d/%d candidate rows", persisted, len(inserts_buffered))

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
    parser = argparse.ArgumentParser(prog="practice_scorer")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="Persist candidate rows")
    g.add_argument("--dry-run", action="store_true", help="Score only, no DB writes")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of conversations scanned (smoke test)")
    parser.add_argument("--auto-link-threshold", type=float,
                        default=DEFAULT_AUTO_LINK_THRESHOLD)
    parser.add_argument("--review-threshold", type=float,
                        default=DEFAULT_REVIEW_THRESHOLD)
    parser.add_argument("--metrics-json", default=None)
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    if args.review_threshold > args.auto_link_threshold:
        logger.error(
            "--review-threshold (%.2f) must be <= --auto-link-threshold (%.2f)",
            args.review_threshold, args.auto_link_threshold,
        )
        return 2

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
        metrics = await score_all(
            pool,
            batch_size=args.batch_size,
            limit=args.limit,
            auto_link_threshold=args.auto_link_threshold,
            review_threshold=args.review_threshold,
            dry_run=args.dry_run,
        )
    finally:
        await pool.close()

    payload = {
        "scorer_version": SCORER_VERSION,
        "dry_run": args.dry_run,
        "limit": args.limit,
        "auto_link_threshold": args.auto_link_threshold,
        "review_threshold": args.review_threshold,
        **asdict(metrics),
    }
    payload["score_distribution"] = dict(metrics.score_distribution)
    payload["signal_avg"] = dict(metrics.signal_avg)

    out = json.dumps(payload, indent=2, default=str)
    logger.info("RUN_METRICS %s", out)
    if args.metrics_json:
        with open(args.metrics_json, "w") as fh:
            fh.write(out)
        logger.info("wrote metrics to %s", args.metrics_json)

    return 0


def main() -> None:
    sys.exit(asyncio.run(cli_main()))


if __name__ == "__main__":
    main()

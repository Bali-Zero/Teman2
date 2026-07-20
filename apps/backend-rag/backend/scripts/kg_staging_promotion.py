"""
KG staging → production promotion job (S5) — arms the quarantine pattern's second half.

`kg_auto_expansion.py` writes auto-extracted entities/relationships to
`kg_nodes_staging` / `kg_edges_staging` (migration_077, 2026-04-03). This job is the
batch validation/promotion runner its docstring has always promised: it validates
staged rows and promotes the good ones to the production `kg_nodes` / `kg_edges`
tables. Until this file existed (2026-07-18), staged rows accumulated as
`promotion_status='pending'` forever — a write-only dead end.

Design contract (pre-registered, do not drift):
`research/operations/2026-07-18-kg-staging-promotion-job-design.md` (v2, post-refuter)
and `docs/GRAPHRAG_EVOLUTION_ARCHITECTURE.md` §3.4 (quarantine pattern).

Concurrency model (v2):
- Singleton via `SELECT pg_try_advisory_lock(770077)`; if the lock is busy another
  run is in progress → log and exit 0. NO `FOR UPDATE` / `SKIP LOCKED` anywhere:
  the writer only appends rows (`ON CONFLICT DO NOTHING`), which never conflicts
  with status flips on disjoint pending rows.
- Chunked short transactions, never one big batch: each chunk is ≤25 rows in its
  own transaction (validate → promote → mark). A dropped fly-ssh connection kills
  at most one 25-row transaction, rolled back by Postgres on disconnect; processed
  rows are already marked, so resume is natural. A chunk that raises rolls back,
  its staging rows stay pending, and the run continues with the next chunk —
  chunk outcomes are merged into the report ONLY after a successful commit, so
  the report never claims rolled-back work.
- Daily cap: max 50 NEW node promotions per day (§3.4), oldest-first; the backlog
  drains over days, not one run.
- Dry-run is genuinely read-only: plain SELECTs inside a single read-only
  transaction, zero writes, zero explicit locks (no advisory lock either).

Phases:
  0 — census (read-only): counts by status, oldest pending age, growth/day,
      alert conditions (>100K rows, >5%/day) in the run report.
  1 — node validation: provenance (`extraction_source` set) · confidence ≥ 0.65 ·
      normalized `entity_id` · conservative dedup (exact prod match → mark promoted
      + confidence-boost UPDATE on the prod row; fuzzy name similarity > 0.85 →
      `rejected(fuzzy_ambiguous_review)`, NEVER auto-merged; no match → candidate).
  2 — edge validation: only edges whose source+target exist in prod KG after
      Phase 1 (no dangling). Edge dedup (source,target,type): exact duplicate →
      corroboration +0.05, capped at 1.0.
  3 — promotion (per chunk, atomic): INSERT nodes → UPDATE prod confidences →
      INSERT edges → flip staging rows (`promoted` / `rejected` + reason).
  4 — retention + report: prune `rejected` rows older than 30 days (uses
      `updated_at` from migration 247) and emit the structured report via logger.

Placement: GitHub Actions cron every 6h → `fly ssh console -C 'PYTHONPATH=.
python -m backend.scripts.kg_staging_promotion [--dry-run|--apply]'`. Default is
`--dry-run` (shadow-first); arming is an explicit operator GO (Legge 5 — writes
the prod KG), flipped via the `KG_PROMOTION_MODE` workflow secret, not a redeploy.

Companion migration: `backend/db/migrations_v2/247_kg_staging_status_integrity.sql`
(promotion_status CHECK + updated_at). The job degrades honestly if 247 is not
applied yet: retention is skipped with a warning and the daily cap falls back to
a per-run cap.

Usage:
    PYTHONPATH=. python -m backend.scripts.kg_staging_promotion [--dry-run|--apply] [--limit N]

DATABASE_URL comes from the environment; it is never hardcoded. Fail-closed: no
DATABASE_URL → exit 2 before touching anything.

Author: Nuzantara Team (campaign S5)
Date: 2026-07-18
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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import asyncpg

from backend.services.rag.kg_auto_expansion import normalize_entity_id

logger = logging.getLogger(__name__)

# ============================================================================
# Constants (contract: GRAPHRAG_EVOLUTION_ARCHITECTURE.md §3.4 + S5 design v2)
# ============================================================================

ADVISORY_LOCK_ID = 770077
CHUNK_SIZE = 25
DAILY_NODE_CAP = 50
MIN_CONFIDENCE = 0.65
FUZZY_MATCH_THRESHOLD = 0.85
CORROBORATION_BONUS = 0.05
MAX_CONFIDENCE = 1.0
REJECTION_RETENTION_DAYS = 30
ALERT_TOTAL_ROWS = 100_000
ALERT_GROWTH_PCT_PER_DAY = 5.0

REASON_MISSING_PROVENANCE = "missing_provenance"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_NOT_NORMALIZED = "entity_id_not_normalized"
REASON_FUZZY_AMBIGUOUS = "fuzzy_ambiguous_review"
REASON_DANGLING_ENDPOINT = "dangling_endpoint"

_KEYSET_START_TS = datetime.min.replace(tzinfo=timezone.utc)

# ============================================================================
# SQL (module-level constants — tests reference these; no dynamic table names)
# ============================================================================

SQL_LOCK = "SELECT pg_try_advisory_lock($1)"
SQL_UNLOCK = "SELECT pg_advisory_unlock($1)"

SQL_CENSUS_NODES = (
    "SELECT promotion_status, count(*)::int AS n "
    "FROM kg_nodes_staging GROUP BY promotion_status"
)
SQL_CENSUS_EDGES = (
    "SELECT promotion_status, count(*)::int AS n "
    "FROM kg_edges_staging GROUP BY promotion_status"
)
SQL_OLDEST_PENDING_NODE = (
    "SELECT min(created_at) FROM kg_nodes_staging WHERE promotion_status = 'pending'"
)
SQL_OLDEST_PENDING_EDGE = (
    "SELECT min(created_at) FROM kg_edges_staging WHERE promotion_status = 'pending'"
)
SQL_GROWTH_NODES_24H = (
    "SELECT count(*)::int FROM kg_nodes_staging "
    "WHERE created_at > now() - interval '1 day'"
)
SQL_GROWTH_EDGES_24H = (
    "SELECT count(*)::int FROM kg_edges_staging "
    "WHERE created_at > now() - interval '1 day'"
)
SQL_HAS_UPDATED_AT = (
    "SELECT count(*)::int FROM information_schema.columns "
    "WHERE table_name = ANY($1::text[]) AND column_name = 'updated_at'"
)
SQL_PROMOTED_TODAY = (
    "SELECT count(*)::int FROM kg_nodes_staging "
    "WHERE promotion_status = 'promoted' AND updated_at >= date_trunc('day', now())"
)

# Keyset pagination ((created_at, id) cursor) — stable under the append-only
# writer and under dry-run, where rows are never flipped out of 'pending'.
SQL_PENDING_NODES_PAGE = """
SELECT entity_id, entity_type, name, description, properties, confidence,
       source_chunk_ids, extraction_source, created_at
FROM kg_nodes_staging
WHERE promotion_status = 'pending'
  AND (COALESCE(created_at, '-infinity'::timestamptz), entity_id) > ($1, $2)
ORDER BY COALESCE(created_at, '-infinity'::timestamptz), entity_id
LIMIT $3
"""
SQL_PENDING_EDGES_PAGE = """
SELECT relationship_id, source_entity_id, target_entity_id, relationship_type,
       properties, confidence, source_chunk_ids, extraction_source, created_at
FROM kg_edges_staging
WHERE promotion_status = 'pending'
  AND (COALESCE(created_at, '-infinity'::timestamptz), relationship_id) > ($1, $2)
ORDER BY COALESCE(created_at, '-infinity'::timestamptz), relationship_id
LIMIT $3
"""

SQL_PROD_NODE_BY_ID = "SELECT entity_id, name, confidence FROM kg_nodes WHERE entity_id = $1"
SQL_PROD_NAMES_BY_TYPE = "SELECT entity_id, name FROM kg_nodes WHERE entity_type = $1"
SQL_INSERT_PROD_NODE = """
INSERT INTO kg_nodes (
    entity_id, entity_type, name, description, properties, confidence,
    source_chunk_ids, created_at, updated_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
ON CONFLICT (entity_id) DO NOTHING
"""
SQL_BOOST_PROD_NODE = (
    "UPDATE kg_nodes SET confidence = LEAST(confidence + $2, $3), updated_at = now() "
    "WHERE entity_id = $1"
)
SQL_FLIP_NODE = (
    "UPDATE kg_nodes_staging "
    "SET promotion_status = $2, rejection_reason = $3, updated_at = now() "
    "WHERE entity_id = $1"
)
# Pre-247 fallback (no updated_at column): same flip without the timestamp.
SQL_FLIP_NODE_NO_TS = (
    "UPDATE kg_nodes_staging SET promotion_status = $2, rejection_reason = $3 "
    "WHERE entity_id = $1"
)

SQL_ENDPOINT_STATE = """
SELECT
  (SELECT 1 FROM kg_nodes WHERE entity_id = $1) AS in_prod,
  (SELECT 1 FROM kg_nodes_staging
    WHERE entity_id = $1 AND promotion_status = 'pending') AS in_pending
"""
SQL_PROD_EDGE_BY_SRT = """
SELECT relationship_id, confidence FROM kg_edges
WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = $3
LIMIT 1
"""
SQL_INSERT_PROD_EDGE = """
INSERT INTO kg_edges (
    relationship_id, source_entity_id, target_entity_id, relationship_type,
    properties, confidence, source_chunk_ids, created_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
ON CONFLICT (relationship_id) DO NOTHING
"""
SQL_CORROBORATE_EDGE = (
    "UPDATE kg_edges SET confidence = LEAST(confidence + $2, $3) WHERE relationship_id = $1"
)
SQL_FLIP_EDGE = (
    "UPDATE kg_edges_staging "
    "SET promotion_status = $2, rejection_reason = $3, updated_at = now() "
    "WHERE relationship_id = $1"
)
SQL_FLIP_EDGE_NO_TS = (
    "UPDATE kg_edges_staging SET promotion_status = $2, rejection_reason = $3 "
    "WHERE relationship_id = $1"
)

_SQL_RETENTION_WINDOW = f"interval '{REJECTION_RETENTION_DAYS} days'"
SQL_PRUNE_NODES = (
    "DELETE FROM kg_nodes_staging WHERE promotion_status = 'rejected' "
    f"AND updated_at < now() - {_SQL_RETENTION_WINDOW}"
)
SQL_PRUNE_EDGES = (
    "DELETE FROM kg_edges_staging WHERE promotion_status = 'rejected' "
    f"AND updated_at < now() - {_SQL_RETENTION_WINDOW}"
)
SQL_COUNT_PRUNABLE_NODES = (
    "SELECT count(*)::int FROM kg_nodes_staging WHERE promotion_status = 'rejected' "
    f"AND updated_at < now() - {_SQL_RETENTION_WINDOW}"
)
SQL_COUNT_PRUNABLE_EDGES = (
    "SELECT count(*)::int FROM kg_edges_staging WHERE promotion_status = 'rejected' "
    f"AND updated_at < now() - {_SQL_RETENTION_WINDOW}"
)

# ============================================================================
# Pure helpers (DB-free — unit-tested directly)
# ============================================================================


def normalize_name(raw: str) -> str:
    """Canonical name form: lowercase, strip, whitespace/dash runs → underscore.

    §3.4 dedup contract: "PT PMA" → "pt_pma", "KITAS" → "kitas".
    """
    return re.sub(r"[\s\-]+", "_", raw.strip().lower())


def name_similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio on canonical name forms (0.0–1.0)."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def boosted_confidence(current: float) -> float:
    """Corroboration bonus +0.05, hard-capped at 1.0 (§3.4)."""
    return min(current + CORROBORATION_BONUS, MAX_CONFIDENCE)


def gate_staged_node(row: Mapping[str, Any]) -> str | None:
    """Static (DB-free) node gates, in spec order. Returns a rejection reason or None.

    1. provenance: `extraction_source` must be set
    2. confidence ≥ 0.65
    3. `entity_id` must equal the canonical normalization of (name, entity_type)
    """
    if not row.get("extraction_source"):
        return REASON_MISSING_PROVENANCE
    confidence = row.get("confidence")
    if confidence is None or float(confidence) < MIN_CONFIDENCE:
        return REASON_LOW_CONFIDENCE
    expected_id = normalize_entity_id(str(row["name"]), str(row["entity_type"]))
    if row.get("entity_id") != expected_id:
        return REASON_NOT_NORMALIZED
    return None


def _affected_count(status: str) -> int:
    """Parse asyncpg command status ('DELETE 7' / 'UPDATE 3') → affected rows."""
    try:
        return int(status.rsplit(" ", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _age_days(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return round((datetime.now(tz=timezone.utc) - ts).total_seconds() / 86400, 2)


def _new_report(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "census": {},
        "alerts": [],
        "budget_nodes": 0,
        "validated": {"nodes": 0, "edges": 0},
        "promoted": {"nodes_inserted": 0, "nodes_exact_match": 0, "edges_inserted": 0},
        "rejected": {"nodes": 0, "edges": 0, "reasons": {}},
        "corroborated": {"nodes": 0, "edges": 0},
        "deferred_nodes": 0,
        "deferred_edges": 0,
        "pruned": {"nodes": 0, "edges": 0},
        "chunks": 0,
        "failures": 0,
        "failure_details": [],
    }


# ============================================================================
# Decisions
# ============================================================================


@dataclass
class NodeDecision:
    """Outcome of validating one staged node."""

    action: str  # "insert" | "boost" | "reject"
    entity_id: str
    row: Mapping[str, Any]
    reason: str | None = None
    matched_prod_id: str | None = None
    similarity: float | None = None


@dataclass
class EdgeDecision:
    """Outcome of validating one staged edge."""

    action: str  # "insert" | "corroborate" | "reject" | "defer"
    relationship_id: str
    row: Mapping[str, Any]
    reason: str | None = None
    prod_relationship_id: str | None = None


@dataclass
class _ChunkDelta:
    """Outcome of one processed chunk.

    Merged into the run report ONLY after the chunk's transaction commits — a
    rolled-back chunk must leave no trace in the report (its rows stay pending
    and will be reprocessed by a later run).
    """

    validated: int = 0
    inserted: int = 0
    boosted: int = 0  # nodes: exact-match boost | edges: corroboration
    corroborated: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    deferred: int = 0
    promotions: int = 0  # NEW node inserts — consumes the daily budget
    promoted_names: list[tuple[str, str, str]] = field(default_factory=list)
    would_ids: list[str] = field(default_factory=list)  # dry-run only

    def reject(self, reason: str | None) -> None:
        key = reason or "unknown"
        self.rejected[key] = self.rejected.get(key, 0) + 1


# ============================================================================
# Pool creation — mirrors app.setup.service_initializer.initialize_services_light
# (jsonb codecs + statement_timeout per connection, statement_cache_size=0 for
# PgBouncer transaction mode). Never hand-serialize jsonb (scar 242/243).
# ============================================================================


def _clean_database_dsn(dsn: str) -> tuple[str, bool | None]:
    """Strip sslmode= (asyncpg rejects it in the DSN). Returns (clean_dsn, ssl).

    Same logic as service_initializer._clean_database_dsn; duplicated here so the
    script stays import-light (no FastAPI app-stack import chain).
    """
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(dsn)
    params = parse_qs(parsed.query)
    sslmode = params.pop("sslmode", [None])[0]
    ssl_context: bool | None = None
    if sslmode == "disable":
        ssl_context = False
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True))), ssl_context


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection init: statement timeout + jsonb/json codecs (prod-pool shape)."""
    await conn.execute("SET statement_timeout = '30s'")
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def create_pool(database_url: str) -> asyncpg.Pool:
    """Create the job's own pool, mirroring the prod pool's safety settings."""
    dsn, ssl_ctx = _clean_database_dsn(database_url)
    pool_kwargs: dict[str, Any] = {
        "dsn": dsn,
        "min_size": 1,
        "max_size": 2,
        "command_timeout": 60,
        "max_inactive_connection_lifetime": 30.0,
        "init": _init_connection,
        # Required for PgBouncer transaction mode — prevents prepared-statement leak
        "statement_cache_size": 0,
    }
    if ssl_ctx is not None:
        pool_kwargs["ssl"] = ssl_ctx
    return await asyncpg.create_pool(**pool_kwargs)


# ============================================================================
# The job
# ============================================================================


class StagingPromotionJob:
    """Validates kg_*_staging rows and promotes the good ones to prod KG.

    One instance == one run. All DB access goes through a single pooled
    connection so the advisory lock (apply mode) is held for the whole run.
    """

    def __init__(self, pool: asyncpg.Pool, *, apply: bool, limit: int | None = None) -> None:
        self.pool = pool
        self.apply = apply
        self.limit = limit
        self.report = _new_report("apply" if apply else "dry-run")
        self._prod_names_cache: dict[str, list[tuple[str, str]]] = {}
        # Dry-run only: entity_ids that WOULD be in prod after this run, so the
        # edge phase simulates post-Phase-1 state without writing anything.
        self._would_promote: set[str] = set()
        self._has_updated_at = True
        self._budget = 0
        self._promotions_used = 0

    # ------------------------------------------------------------------ run

    async def run(self) -> int:
        """Execute the run. Exit 0 on success AND on advisory-lock-busy; 1 on error."""
        start = time.monotonic()
        exit_code = 0
        try:
            if self.apply:
                async with self.pool.acquire() as conn:
                    locked = await conn.fetchval(SQL_LOCK, ADVISORY_LOCK_ID)
                    if not locked:
                        logger.info(
                            "KG promotion: advisory lock %s busy — another run in "
                            "progress, exiting 0 (no work done)",
                            ADVISORY_LOCK_ID,
                        )
                        return 0
                    try:
                        await self._run_all_phases(conn)
                    finally:
                        await conn.fetchval(SQL_UNLOCK, ADVISORY_LOCK_ID)
            else:
                # Genuinely read-only: plain SELECTs in one read-only transaction,
                # zero writes, zero explicit locks.
                async with self.pool.acquire() as conn, conn.transaction(readonly=True):
                    await self._run_all_phases(conn)
        except Exception as e:
            logger.error("KG staging promotion run failed: %s", e, exc_info=True)
            self.report["failures"] += 1
            self.report["failure_details"].append(f"run: {e!r}")
            exit_code = 1
        self.report["duration_ms"] = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "KG staging promotion report: %s",
            json.dumps(self.report, default=str, sort_keys=True),
        )
        return exit_code

    async def _run_all_phases(self, conn: asyncpg.Connection) -> None:
        await self._phase0_census(conn)
        await self._phase_nodes(conn)
        await self._phase_edges(conn)
        await self._phase4_retention(conn)

    # ------------------------------------------------------------- phase 0

    async def _phase0_census(self, conn: asyncpg.Connection) -> None:
        """Census (read-only): counts by status, oldest pending age, growth/day."""
        nodes_by_status = {
            r["promotion_status"]: r["n"] for r in await conn.fetch(SQL_CENSUS_NODES)
        }
        edges_by_status = {
            r["promotion_status"]: r["n"] for r in await conn.fetch(SQL_CENSUS_EDGES)
        }
        total_nodes = sum(nodes_by_status.values())
        total_edges = sum(edges_by_status.values())
        growth_nodes = await conn.fetchval(SQL_GROWTH_NODES_24H) or 0
        growth_edges = await conn.fetchval(SQL_GROWTH_EDGES_24H) or 0
        oldest_node = await conn.fetchval(SQL_OLDEST_PENDING_NODE)
        oldest_edge = await conn.fetchval(SQL_OLDEST_PENDING_EDGE)
        oldest_pending = min(
            (t for t in (oldest_node, oldest_edge) if t is not None), default=None
        )

        updated_at_cols = await conn.fetchval(
            SQL_HAS_UPDATED_AT, ["kg_nodes_staging", "kg_edges_staging"]
        )
        self._has_updated_at = (updated_at_cols or 0) == 2
        if not self._has_updated_at:
            logger.warning(
                "kg_*_staging.updated_at missing — migration 247 not applied: "
                "retention prune will be skipped and the daily cap is per-run only"
            )

        total = total_nodes + total_edges
        growth_pct = (100.0 * (growth_nodes + growth_edges) / total) if total else 0.0
        alerts: list[str] = []
        if total > ALERT_TOTAL_ROWS:
            alerts.append("staging_rows_over_100k")
        if growth_pct > ALERT_GROWTH_PCT_PER_DAY:
            alerts.append("staging_growth_over_5pct_per_day")

        self.report["census"] = {
            "nodes_by_status": nodes_by_status,
            "edges_by_status": edges_by_status,
            "total_rows": total,
            "pending_nodes": nodes_by_status.get("pending", 0),
            "pending_edges": edges_by_status.get("pending", 0),
            "oldest_pending_age_days": _age_days(oldest_pending),
            "growth_last_24h": growth_nodes + growth_edges,
            "growth_pct_per_day": round(growth_pct, 2),
        }
        self.report["alerts"] = alerts
        for alert in alerts:
            logger.warning("KG staging alert: %s (census=%s)", alert, self.report["census"])

        # Daily cap: 50 NEW node promotions per UTC day, minus what earlier runs
        # already promoted today. --limit can only shrink the budget, never raise
        # it above the contract's 50/day.
        if self._has_updated_at:
            promoted_today = await conn.fetchval(SQL_PROMOTED_TODAY) or 0
        else:
            promoted_today = 0
        remaining = max(0, DAILY_NODE_CAP - promoted_today)
        self._budget = min(remaining, self.limit) if self.limit is not None else remaining
        self.report["budget_nodes"] = self._budget

    # -------------------------------------------------------- phases 1 + 3

    async def _classify_node(
        self, conn: asyncpg.Connection, row: Mapping[str, Any]
    ) -> NodeDecision:
        """Phase 1 node validation: static gates → exact prod dedup → fuzzy dedup."""
        entity_id = str(row["entity_id"])
        reason = gate_staged_node(row)
        if reason is not None:
            return NodeDecision(action="reject", entity_id=entity_id, row=row, reason=reason)

        prod = await conn.fetchrow(SQL_PROD_NODE_BY_ID, entity_id)
        if prod is not None:
            # Exact prod match → mark promoted + confidence-boost UPDATE on the
            # prod row (no INSERT, no provenance merge).
            return NodeDecision(
                action="boost", entity_id=entity_id, row=row, matched_prod_id=entity_id
            )

        best_id: str | None = None
        best_sim = 0.0
        for prod_id, prod_name in await self._prod_names_for_type(
            conn, str(row["entity_type"])
        ):
            sim = name_similarity(str(row["name"]), prod_name)
            if sim > best_sim:
                best_id, best_sim = prod_id, sim
        if best_sim > FUZZY_MATCH_THRESHOLD:
            # Conservative: NEVER auto-merge — a false positive would corrupt prod
            # provenance irreversibly. Surface for human review instead.
            return NodeDecision(
                action="reject",
                entity_id=entity_id,
                row=row,
                reason=REASON_FUZZY_AMBIGUOUS,
                matched_prod_id=best_id,
                similarity=round(best_sim, 4),
            )
        return NodeDecision(action="insert", entity_id=entity_id, row=row)

    async def _prod_names_for_type(
        self, conn: asyncpg.Connection, entity_type: str
    ) -> list[tuple[str, str]]:
        """(entity_id, name) pairs for one entity_type, cached per run."""
        if entity_type not in self._prod_names_cache:
            rows = await conn.fetch(SQL_PROD_NAMES_BY_TYPE, entity_type)
            self._prod_names_cache[entity_type] = [
                (str(r["entity_id"]), str(r["name"])) for r in rows
            ]
        return self._prod_names_cache[entity_type]

    async def _process_node_chunk(
        self, conn: asyncpg.Connection, page: Sequence[Mapping[str, Any]]
    ) -> _ChunkDelta:
        """Validate one ≤25-row node chunk and (in apply mode) promote/mark it.

        Returns the chunk delta; the caller merges it into the report ONLY after
        the chunk's transaction commits.
        """
        delta = _ChunkDelta()
        decisions: list[NodeDecision] = []
        for row in page:
            delta.validated += 1
            decisions.append(await self._classify_node(conn, row))

        flip_sql = SQL_FLIP_NODE if self._has_updated_at else SQL_FLIP_NODE_NO_TS
        for decision in decisions:
            row = decision.row
            if (
                decision.action == "insert"
                and self._promotions_used + delta.promotions >= self._budget
            ):
                # Daily cap hit mid-chunk: leave the row pending for the next run.
                delta.deferred += 1
                continue
            if self.apply:
                if decision.action == "insert":
                    await conn.execute(
                        SQL_INSERT_PROD_NODE,
                        decision.entity_id,
                        str(row["entity_type"]),
                        str(row["name"]),
                        row.get("description"),
                        row.get("properties") or {},
                        float(row["confidence"]),
                        list(row.get("source_chunk_ids") or []),
                        row.get("created_at"),
                    )
                    await conn.execute(flip_sql, decision.entity_id, "promoted", None)
                elif decision.action == "boost":
                    await conn.execute(
                        SQL_BOOST_PROD_NODE,
                        decision.entity_id,
                        CORROBORATION_BONUS,
                        MAX_CONFIDENCE,
                    )
                    await conn.execute(flip_sql, decision.entity_id, "promoted", None)
                else:
                    await conn.execute(flip_sql, decision.entity_id, "rejected", decision.reason)
            if decision.action == "insert":
                delta.promotions += 1
                delta.inserted += 1
                delta.promoted_names.append(
                    (str(row["entity_type"]), decision.entity_id, str(row["name"]))
                )
                if not self.apply:
                    delta.would_ids.append(decision.entity_id)
            elif decision.action == "boost":
                delta.boosted += 1
                if not self.apply:
                    delta.would_ids.append(decision.entity_id)
            else:
                delta.reject(decision.reason)
        return delta

    def _merge_node_delta(self, delta: _ChunkDelta) -> None:
        """Merge a COMMITTED chunk's outcome into the run state/report."""
        self.report["validated"]["nodes"] += delta.validated
        self.report["promoted"]["nodes_inserted"] += delta.inserted
        self.report["promoted"]["nodes_exact_match"] += delta.boosted
        self.report["corroborated"]["nodes"] += delta.boosted
        self.report["deferred_nodes"] += delta.deferred
        self.report["rejected"]["nodes"] += sum(delta.rejected.values())
        for reason, n in delta.rejected.items():
            reasons = self.report["rejected"]["reasons"]
            reasons[reason] = reasons.get(reason, 0) + n
        self._promotions_used += delta.promotions
        self._would_promote.update(delta.would_ids)
        for entity_type, entity_id, name in delta.promoted_names:
            # Keep the fuzzy cache in sync with what this run put (or would put)
            # in prod, so later chunks in the same run dedup against it.
            self._prod_names_cache.setdefault(entity_type, []).append((entity_id, name))

    async def _phase_nodes(self, conn: asyncpg.Connection) -> None:
        """Phases 1+3 for nodes: chunked ≤25-row transactions, oldest-first."""
        cursor_ts = _KEYSET_START_TS
        cursor_id = ""
        while self._promotions_used < self._budget:
            page = await conn.fetch(SQL_PENDING_NODES_PAGE, cursor_ts, cursor_id, CHUNK_SIZE)
            if not page:
                break
            last = page[-1]
            cursor_ts = last["created_at"] or _KEYSET_START_TS
            cursor_id = str(last["entity_id"])
            try:
                if self.apply:
                    async with conn.transaction():
                        delta = await self._process_node_chunk(conn, page)
                else:
                    delta = await self._process_node_chunk(conn, page)
            except Exception as e:
                # Apply: the chunk rolled back, staging is untouched, the run
                # continues with the next chunk. Dry-run: the read-only tx is
                # poisoned after an error — stop the node loop.
                self.report["failures"] += 1
                self.report["failure_details"].append(f"node_chunk@{cursor_id}: {e!r}")
                logger.error(
                    "KG promotion node chunk failed (rolled back, run continues): %s",
                    e,
                    exc_info=True,
                )
                if not self.apply:
                    break
                continue
            self._merge_node_delta(delta)
            self.report["chunks"] += 1

    # -------------------------------------------------------- phases 2 + 3

    async def _classify_edge(
        self, conn: asyncpg.Connection, row: Mapping[str, Any]
    ) -> EdgeDecision:
        """Phase 2 edge validation: no dangling endpoints, then (s,t,type) dedup."""
        rel_id = str(row["relationship_id"])
        for endpoint in (str(row["source_entity_id"]), str(row["target_entity_id"])):
            state = await conn.fetchrow(SQL_ENDPOINT_STATE, endpoint)
            in_prod = bool(state and state["in_prod"]) or endpoint in self._would_promote
            if in_prod:
                continue
            if state and state["in_pending"]:
                # Endpoint still quarantined — resolvable by a later run; leave pending.
                return EdgeDecision(action="defer", relationship_id=rel_id, row=row)
            return EdgeDecision(
                action="reject",
                relationship_id=rel_id,
                row=row,
                reason=REASON_DANGLING_ENDPOINT,
            )

        existing = await conn.fetchrow(
            SQL_PROD_EDGE_BY_SRT,
            str(row["source_entity_id"]),
            str(row["target_entity_id"]),
            str(row["relationship_type"]),
        )
        if existing is not None:
            # Exact duplicate → corroboration +0.05 cap 1.0 on the prod edge.
            return EdgeDecision(
                action="corroborate",
                relationship_id=rel_id,
                row=row,
                prod_relationship_id=str(existing["relationship_id"]),
            )
        return EdgeDecision(action="insert", relationship_id=rel_id, row=row)

    async def _process_edge_chunk(
        self, conn: asyncpg.Connection, page: Sequence[Mapping[str, Any]]
    ) -> _ChunkDelta:
        """Validate one ≤25-row edge chunk and (in apply mode) promote/mark it."""
        delta = _ChunkDelta()
        decisions: list[EdgeDecision] = []
        for row in page:
            delta.validated += 1
            decisions.append(await self._classify_edge(conn, row))

        flip_sql = SQL_FLIP_EDGE if self._has_updated_at else SQL_FLIP_EDGE_NO_TS
        for decision in decisions:
            row = decision.row
            if decision.action == "defer":
                delta.deferred += 1
                continue  # leave pending for a later run
            if self.apply:
                if decision.action == "insert":
                    await conn.execute(
                        SQL_INSERT_PROD_EDGE,
                        decision.relationship_id,
                        str(row["source_entity_id"]),
                        str(row["target_entity_id"]),
                        str(row["relationship_type"]),
                        row.get("properties") or {},
                        float(row["confidence"]),
                        list(row.get("source_chunk_ids") or []),
                        row.get("created_at"),
                    )
                    await conn.execute(flip_sql, decision.relationship_id, "promoted", None)
                elif decision.action == "corroborate":
                    await conn.execute(
                        SQL_CORROBORATE_EDGE,
                        decision.prod_relationship_id,
                        CORROBORATION_BONUS,
                        MAX_CONFIDENCE,
                    )
                    await conn.execute(flip_sql, decision.relationship_id, "promoted", None)
                else:
                    await conn.execute(
                        flip_sql, decision.relationship_id, "rejected", decision.reason
                    )
            if decision.action == "insert":
                delta.inserted += 1
            elif decision.action == "corroborate":
                delta.corroborated += 1
            else:
                delta.reject(decision.reason)
        return delta

    def _merge_edge_delta(self, delta: _ChunkDelta) -> None:
        """Merge a COMMITTED edge chunk's outcome into the run report."""
        self.report["validated"]["edges"] += delta.validated
        self.report["promoted"]["edges_inserted"] += delta.inserted
        self.report["corroborated"]["edges"] += delta.corroborated
        self.report["deferred_edges"] += delta.deferred
        self.report["rejected"]["edges"] += sum(delta.rejected.values())
        for reason, n in delta.rejected.items():
            reasons = self.report["rejected"]["reasons"]
            reasons[reason] = reasons.get(reason, 0) + n

    async def _phase_edges(self, conn: asyncpg.Connection) -> None:
        """Phases 2+3 for edges: after nodes, chunked ≤25-row transactions."""
        cursor_ts = _KEYSET_START_TS
        cursor_id = ""
        while True:
            page = await conn.fetch(SQL_PENDING_EDGES_PAGE, cursor_ts, cursor_id, CHUNK_SIZE)
            if not page:
                break
            last = page[-1]
            cursor_ts = last["created_at"] or _KEYSET_START_TS
            cursor_id = str(last["relationship_id"])
            try:
                if self.apply:
                    async with conn.transaction():
                        delta = await self._process_edge_chunk(conn, page)
                else:
                    delta = await self._process_edge_chunk(conn, page)
            except Exception as e:
                self.report["failures"] += 1
                self.report["failure_details"].append(f"edge_chunk@{cursor_id}: {e!r}")
                logger.error(
                    "KG promotion edge chunk failed (rolled back, run continues): %s",
                    e,
                    exc_info=True,
                )
                if not self.apply:
                    break
                continue
            self._merge_edge_delta(delta)
            self.report["chunks"] += 1

    # ------------------------------------------------------------- phase 4

    async def _phase4_retention(self, conn: asyncpg.Connection) -> None:
        """Prune `rejected` rows older than 30 days (uses updated_at from m247)."""
        if not self._has_updated_at:
            self.report["alerts"].append("retention_skipped_no_updated_at")
            logger.warning("Retention prune skipped: kg_*_staging.updated_at missing (m247)")
            return
        if not self.apply:
            self.report["pruned"] = {
                "nodes": await conn.fetchval(SQL_COUNT_PRUNABLE_NODES) or 0,
                "edges": await conn.fetchval(SQL_COUNT_PRUNABLE_EDGES) or 0,
            }
            return
        async with conn.transaction():
            res_nodes = await conn.execute(SQL_PRUNE_NODES)
            res_edges = await conn.execute(SQL_PRUNE_EDGES)
        self.report["pruned"] = {
            "nodes": _affected_count(res_nodes),
            "edges": _affected_count(res_edges),
        }


# ============================================================================
# CLI
# ============================================================================


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """CLI: --dry-run (default) | --apply, plus an optional per-run --limit."""
    parser = argparse.ArgumentParser(
        prog="kg_staging_promotion",
        description=(
            "Validate kg_nodes_staging/kg_edges_staging and promote to prod KG. "
            "Dry-run (read-only) by default; --apply writes. Every 6h via GH Actions cron."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="read-only shadow run (default): plain SELECTs, zero writes, no locks",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="armed mode: promote/mark staging rows (advisory-lock singleton)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="max NEW node promotions this run (can only shrink the 50/day cap)",
    )
    return parser.parse_args(argv)


async def async_main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        logger.error("DATABASE_URL is not set — refusing to run (fail-closed)")
        return 2
    pool = await create_pool(database_url)
    try:
        job = StagingPromotionJob(pool, apply=bool(args.apply), limit=args.limit)
        return await job.run()
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()

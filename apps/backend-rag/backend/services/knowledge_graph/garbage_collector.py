"""CRM Knowledge Graph — Garbage Collector

Soft-deletes crm_kg_nodes when their backing CRM data has been removed,
keeping the graph in sync with the source-of-truth tables.

Two phases:

  Phase 1 — Soft delete: mark `deleted_at = NOW()` on nodes whose backing
            row in `documents` / `clients` / `practices` is gone (or
            already soft-deleted there). Edges are NOT removed yet —
            they remain queryable for audit/recovery for a grace window.

  Phase 2 — Hard delete edges: drop `crm_kg_edges` rows whose source OR
            target node has been soft-deleted for more than the grace
            window (default 30 days). Hard delete cascades on the FK,
            so the edges go automatically when we hard-delete the nodes
            themselves — but we do edges first to keep the graph
            queryable from non-deleted neighbors.

Rationale for grace window:
  - 30 days lets ops recover from accidental Drive deletions
  - Aligns with typical UU PDP retention review cadence
  - Hard delete is irreversible; soft is the safe default

Idempotency:
  Safe to run on every cron tick — soft-deleting an already-soft-deleted
  node is a no-op (WHERE deleted_at IS NULL filters them out).

Failure mode:
  Best-effort. Any DB error is logged and swallowed. The next cron tick
  retries from a clean slate; no partial state can corrupt the graph
  because each phase is its own SQL statement.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Grace window between soft-delete and hard-delete. Generous default —
# 30 days lets a careless Drive deletion be recovered without losing the
# graph context (audit trail, related-doc edges still queryable).
_HARD_DELETE_GRACE_DAYS = 30

# Per-pass safety caps — protect against a runaway single transaction
# locking the table for minutes if something pathological happens
# (e.g., 100k orphan rows after a bulk Drive cleanup).
_MAX_SOFT_DELETE_PER_PASS = 5_000
_MAX_HARD_DELETE_PER_PASS = 5_000


async def garbage_collect(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """Run a single pass of the garbage collector.

    Returns:
        {
            "ok": True,
            "soft_deleted": {
                "documents": <int>,
                "clients": <int>,
                "practices": <int>,
            },
            "hard_deleted_edges": <int>,
            "elapsed_s": <float>,
        }
        or {"ok": False, "error": "<reason>"}
    """
    started = time.monotonic()

    try:
        async with db_pool.acquire() as conn:
            soft_doc = await _soft_delete_orphan_documents(conn)
            soft_cli = await _soft_delete_orphan_clients(conn)
            soft_prac = await _soft_delete_orphan_practices(conn)
            hard_edges = await _hard_delete_old_edges(conn)

        elapsed = time.monotonic() - started
        result = {
            "ok": True,
            "soft_deleted": {
                "documents": soft_doc,
                "clients": soft_cli,
                "practices": soft_prac,
            },
            "hard_deleted_edges": hard_edges,
            "elapsed_s": round(elapsed, 2),
        }
        logger.info("crm_kg garbage_collect: %s", result)
        return result

    except Exception as e:
        logger.error(
            "crm_kg garbage_collect failed: %s", e, exc_info=True,
        )
        return {"ok": False, "error": str(e)}


async def _soft_delete_orphan_documents(conn: asyncpg.Connection) -> int:
    """Soft-delete crm_document nodes whose file_id is gone from documents.

    A row is "gone" if either:
      - documents row no longer exists for that file_id, OR
      - documents.is_archived = true (existing CRM convention)

    The node remains in the graph (queryable) until the grace window
    expires and _hard_delete_old_edges fires. Source-of-truth is the
    `documents` table; the graph just lags behind in soft-delete state.
    """
    sql = """
    UPDATE crm_kg_nodes
    SET deleted_at = NOW(), updated_at = NOW()
    WHERE entity_id IN (
        SELECT n.entity_id
        FROM crm_kg_nodes n
        WHERE n.entity_type = 'crm_document'
          AND n.deleted_at IS NULL
          AND n.file_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM documents d
              WHERE d.file_id = n.file_id
                AND COALESCE(d.is_archived, FALSE) = FALSE
          )
        LIMIT $1
    )
    """
    result = await conn.execute(sql, _MAX_SOFT_DELETE_PER_PASS)
    return _parse_updated_count(result)


async def _soft_delete_orphan_clients(conn: asyncpg.Connection) -> int:
    """Soft-delete crm_client nodes whose clients row is soft-deleted."""
    sql = """
    UPDATE crm_kg_nodes
    SET deleted_at = NOW(), updated_at = NOW()
    WHERE entity_id IN (
        SELECT n.entity_id
        FROM crm_kg_nodes n
        WHERE n.entity_type = 'crm_client'
          AND n.deleted_at IS NULL
          AND n.client_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM clients c
              WHERE c.id = n.client_id
                AND c.deleted_at IS NULL
          )
        LIMIT $1
    )
    """
    result = await conn.execute(sql, _MAX_SOFT_DELETE_PER_PASS)
    return _parse_updated_count(result)


async def _soft_delete_orphan_practices(conn: asyncpg.Connection) -> int:
    """Soft-delete crm_practice nodes whose practices row is missing.

    practices table convention varies (some installs have deleted_at,
    others don't) — we just check existence by id.
    """
    sql = """
    UPDATE crm_kg_nodes
    SET deleted_at = NOW(), updated_at = NOW()
    WHERE entity_id IN (
        SELECT n.entity_id
        FROM crm_kg_nodes n
        WHERE n.entity_type = 'crm_practice'
          AND n.deleted_at IS NULL
          AND n.practice_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM practices p
              WHERE p.id = n.practice_id
          )
        LIMIT $1
    )
    """
    result = await conn.execute(sql, _MAX_SOFT_DELETE_PER_PASS)
    return _parse_updated_count(result)


async def _hard_delete_old_edges(conn: asyncpg.Connection) -> int:
    """Hard-delete edges whose source or target node has been soft-deleted
    for more than the grace window. The cascading FK on crm_kg_edges
    would do this automatically when we eventually hard-delete the nodes,
    but we run it explicitly so edges go away on a predictable cadence
    regardless of when (or if) the nodes are physically removed.

    NB: we do NOT hard-delete the nodes themselves yet. Audit recovery
    can still resurrect a soft-deleted node by clearing deleted_at,
    but only re-running the linker will rebuild its edges.
    """
    sql = """
    DELETE FROM crm_kg_edges
    WHERE relationship_id IN (
        SELECT e.relationship_id
        FROM crm_kg_edges e
        JOIN crm_kg_nodes ns ON ns.entity_id = e.source_entity_id
        JOIN crm_kg_nodes nt ON nt.entity_id = e.target_entity_id
        WHERE
            (ns.deleted_at IS NOT NULL AND ns.deleted_at < NOW() - ($1 || ' days')::interval)
            OR
            (nt.deleted_at IS NOT NULL AND nt.deleted_at < NOW() - ($1 || ' days')::interval)
        LIMIT $2
    )
    """
    result = await conn.execute(
        sql, str(_HARD_DELETE_GRACE_DAYS), _MAX_HARD_DELETE_PER_PASS,
    )
    return _parse_deleted_count(result)


def _parse_updated_count(execute_result: str) -> int:
    """Parse asyncpg execute() return string ('UPDATE N') for row count."""
    try:
        parts = (execute_result or "").split()
        if len(parts) >= 2 and parts[0] == "UPDATE":
            return int(parts[1])
    except (ValueError, IndexError, AttributeError):
        pass
    return 0


def _parse_deleted_count(execute_result: str) -> int:
    """Parse asyncpg execute() return string ('DELETE N') for row count."""
    try:
        parts = (execute_result or "").split()
        if len(parts) >= 2 and parts[0] == "DELETE":
            return int(parts[1])
    except (ValueError, IndexError, AttributeError):
        pass
    return 0

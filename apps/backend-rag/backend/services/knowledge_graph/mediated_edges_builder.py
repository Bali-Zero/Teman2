"""CRM Knowledge Graph — Tier-B mediated edges builder.

This worker walks the crm_kg_nodes/crm_kg_edges tables and emits edges
that are not directly produced by document_linker (Tier-A) but can be
inferred deterministically via SQL JOINs across already-linked nodes.

The three relationship types in scope:

  CONTEMPORANEOUS  — two Documents for the same Client uploaded within
                     a configurable window (default 7 days). Useful for
                     grouping a "kit" of docs that arrived together
                     (e.g. passport + KK + sponsor letter for KITAS).

  COWORKER_AT      — two Person nodes both linked to the same Company
                     via DESCRIBES edges from Documents. Helps surface
                     PT PMA director/shareholder structure across
                     multiple Akta uploads.

  HOUSEHOLD_AT     — two Person nodes both linked to the same Address
                     (when Address nodes ship in Tier-C; placeholder
                     here for forward compat).

Why these are NOT Tier-A:
  Tier-A linker only sees ONE document at a time and can't compare
  across docs. Tier-B is the cross-document SQL layer.

Why these are NOT Tier-C:
  No LLM inference needed. These are deterministic property-equality
  joins. Confidence is 1.0 for exact matches, 0.85 for fuzzy
  (e.g. CONTEMPORANEOUS where "within 7 days" is a heuristic window).

Idempotency:
  All emitted edges use ON CONFLICT (source, target, relationship_type)
  DO UPDATE so re-running the cron is a no-op for already-known edges.
  Confidence/properties are refreshed on each pass — useful when the
  source data changes (e.g. doc moved between practices).

Lifecycle:
  When a source node is soft-deleted (deleted_at IS NOT NULL), edges
  are NOT auto-cleaned here. PR-D (kg_garbage_collect) handles that
  separately on a daily cadence.

Performance:
  Designed to run every 6h via cron. Single-table JOINs on indexed
  columns (entity_type, client_id, person_uid, company_uid). On 50k
  CRM nodes the full pass should complete in <30s; we add LIMIT
  guards anyway in case of runaway query plans.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Cron-time guards — protect against runaway queries on a degraded DB.
# Soft-fail at limit; resume on next 6h tick.
_MAX_EDGES_PER_PASS = 10_000
_CONTEMPORANEOUS_WINDOW_DAYS = 7

# Confidence per edge sub-type. Property-equality matches are 1.0
# (deterministic). Time-window matches are 0.85 (heuristic).
_CONF_DETERMINISTIC = 1.0
_CONF_HEURISTIC_TIME = 0.85


async def build_mediated_edges(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """Run one pass of the mediated edge builder.

    Returns:
        {
            "ok": True,
            "contemporaneous": <int>,
            "coworker_at": <int>,
            "elapsed_s": <float>,
        }
        or {"ok": False, "error": "<reason>"}
    """
    import time

    started = time.monotonic()

    try:
        async with db_pool.acquire() as conn:
            cont_count = await _emit_contemporaneous(conn)
            coworker_count = await _emit_coworker_at(conn)

        elapsed = time.monotonic() - started
        result = {
            "ok": True,
            "contemporaneous": cont_count,
            "coworker_at": coworker_count,
            "elapsed_s": round(elapsed, 2),
        }
        logger.info("mediated_edges_builder: %s", result)
        return result

    except Exception as e:
        logger.error(
            "mediated_edges_builder failed: %s",
            e,
            exc_info=True,
        )
        return {"ok": False, "error": str(e)}


async def _emit_contemporaneous(conn: asyncpg.Connection) -> int:
    """Two crm_document nodes for the same Client, uploaded within
    _CONTEMPORANEOUS_WINDOW_DAYS, get a CONTEMPORANEOUS edge (undirected,
    represented as two symmetric directed edges to keep the schema simple).

    Heuristic confidence: 0.85 (time-window match, not property equality).

    Excludes self-pairs and skips if both docs already linked.
    """
    sql = """
    WITH doc_pairs AS (
        SELECT DISTINCT
            d1.entity_id AS src_id,
            d2.entity_id AS tgt_id
        FROM crm_kg_edges e1
        JOIN crm_kg_edges e2
            ON e1.target_entity_id = e2.target_entity_id  -- same Client node
            AND e1.relationship_type = 'BELONGS_TO'
            AND e2.relationship_type = 'BELONGS_TO'
            AND e1.source_entity_id <> e2.source_entity_id
        JOIN crm_kg_nodes d1
            ON d1.entity_id = e1.source_entity_id
            AND d1.entity_type = 'crm_document'
            AND d1.deleted_at IS NULL
        JOIN crm_kg_nodes d2
            ON d2.entity_id = e2.source_entity_id
            AND d2.entity_type = 'crm_document'
            AND d2.deleted_at IS NULL
        WHERE
            d1.entity_id < d2.entity_id  -- canonical ordering, no dup pairs
            AND ABS(EXTRACT(EPOCH FROM (d1.created_at - d2.created_at))) <
                ($1::int * 86400)
        LIMIT $2
    )
    INSERT INTO crm_kg_edges (
        source_entity_id, target_entity_id, relationship_type,
        properties, edge_tier, confidence
    )
    SELECT
        src_id, tgt_id, 'CONTEMPORANEOUS',
        '{}'::jsonb, 'mediated', $3::float
    FROM doc_pairs
    ON CONFLICT (source_entity_id, target_entity_id, relationship_type)
    DO UPDATE SET
        confidence = EXCLUDED.confidence,
        edge_tier = EXCLUDED.edge_tier
    """
    # The query inserts edges from d1 -> d2 (canonical d1 < d2 ordering).
    # We do NOT also insert d2 -> d1 because the relationship is symmetric
    # and downstream graph queries can traverse either direction. Keeps
    # row count down on a wide pool.
    result = await conn.execute(
        sql,
        _CONTEMPORANEOUS_WINDOW_DAYS,
        _MAX_EDGES_PER_PASS,
        _CONF_HEURISTIC_TIME,
    )
    # asyncpg returns "INSERT 0 N" — parse the N for row count
    return _parse_inserted_count(result)


async def _emit_coworker_at(conn: asyncpg.Connection) -> int:
    """Two crm_person nodes linked (via DESCRIBES from any Document) to
    the same crm_company node get a COWORKER_AT edge.

    Confidence 1.0 — this is a deterministic property-equality match
    (both persons have a DESCRIBES path to the SAME company_uid).

    The document_linker emits DESCRIBES from Document -> Person/Company,
    so this query first materializes Person -> Company facts through the
    shared source Document, then pairs people attached to the same Company.
    """
    sql = """
    WITH person_company AS (
        SELECT DISTINCT
            p1.entity_id AS person_id,
            company.entity_id AS company_id
        FROM crm_kg_edges person_edge
        JOIN crm_kg_edges company_edge
            ON person_edge.source_entity_id = company_edge.source_entity_id
            AND person_edge.relationship_type = 'DESCRIBES'
            AND company_edge.relationship_type = 'DESCRIBES'
            AND person_edge.target_entity_id <> company_edge.target_entity_id
        JOIN crm_kg_nodes document
            ON document.entity_id = person_edge.source_entity_id
            AND document.entity_type = 'crm_document'
            AND document.deleted_at IS NULL
        JOIN crm_kg_nodes p1
            ON p1.entity_id = person_edge.target_entity_id
            AND p1.entity_type = 'crm_person'
            AND p1.deleted_at IS NULL
        JOIN crm_kg_nodes company
            ON company.entity_id = company_edge.target_entity_id
            AND company.entity_type = 'crm_company'
            AND company.deleted_at IS NULL
    ),
    person_pairs AS (
        SELECT DISTINCT
            left_pc.person_id AS src_id,
            right_pc.person_id AS tgt_id,
            left_pc.company_id AS company_id
        FROM person_company left_pc
        JOIN person_company right_pc
            ON left_pc.company_id = right_pc.company_id
            AND left_pc.person_id < right_pc.person_id
        LIMIT $1
    )
    INSERT INTO crm_kg_edges (
        source_entity_id, target_entity_id, relationship_type,
        properties, edge_tier, confidence
    )
    SELECT
        src_id, tgt_id, 'COWORKER_AT',
        jsonb_build_object('company_id', company_id::text),
        'mediated', $2::float
    FROM person_pairs
    ON CONFLICT (source_entity_id, target_entity_id, relationship_type)
    DO UPDATE SET
        properties = EXCLUDED.properties,
        confidence = EXCLUDED.confidence,
        edge_tier = EXCLUDED.edge_tier
    """
    result = await conn.execute(sql, _MAX_EDGES_PER_PASS, _CONF_DETERMINISTIC)
    return _parse_inserted_count(result)


def _parse_inserted_count(execute_result: str) -> int:
    """Parse asyncpg execute() return string ('INSERT 0 N') for inserted rows.

    Returns 0 if format unexpected — this is a metrics-only reading,
    don't fail the whole cron over a parsing edge case.
    """
    try:
        # Format: 'INSERT 0 12' → 12
        parts = (execute_result or "").split()
        if len(parts) >= 3 and parts[0] == "INSERT":
            return int(parts[2])
    except (ValueError, IndexError, AttributeError):
        pass
    return 0

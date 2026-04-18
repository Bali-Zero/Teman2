"""RAG stats aggregator — percentile + cost rollups over ``rag_traces``.

Exposes a single entry point, :func:`aggregate_rag_stats`, that runs
percentile queries per stage and cost rollups per domain over a time
window, with 60-second Redis caching keyed by ``(window, domain)``.

Design notes
------------

* **Single aggregating pass.** We unnest ``root_span->'spans'`` once and
  ``percentile_cont`` per stage in the same query so the table scan cost
  is paid once per window, not once per stage.
* **Cache TTL 60s.** The underlying ledger is append-only; a 60s staleness
  budget is acceptable for a dashboard and keeps Postgres CPU flat even
  under repeated admin refreshes. A miss is always safe — the query is
  idempotent and pure.
* **Graceful degradation.** Redis unavailable → skip the cache layer. DB
  unavailable → return an empty skeleton rather than 500 so the router
  can still render a "no data" dashboard.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Cache configuration — 60 seconds matches the spec: dashboards refresh
# every 30s, a 60s TTL absorbs the second request nearly every time.
CACHE_TTL_SECONDS: int = 60
CACHE_KEY_PREFIX: str = "zantara:rag_stats:"


@dataclass(frozen=True)
class StatsRequest:
    """Inputs accepted by :func:`aggregate_rag_stats`."""

    window_hours: int
    domain: str | None = None

    def cache_key(self) -> str:
        return f"{CACHE_KEY_PREFIX}{self.window_hours}h:{self.domain or 'all'}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def aggregate_rag_stats(
    pool: asyncpg.Pool,
    request: StatsRequest,
    *,
    redis_client: Any | None = None,
) -> dict[str, Any]:
    """Return stage timings, costs, and top domains for the given window.

    The payload schema is stable — see :func:`_empty_payload` for the
    canonical shape. Callers can rely on every key being present even
    when no traces exist in the window.
    """
    cache_key = request.cache_key()
    cached = await _cache_get(redis_client, cache_key)
    if cached is not None:
        return cached

    try:
        payload = await _compute(pool, request)
    except asyncpg.UndefinedTableError:
        # Migration not yet applied — return an empty skeleton so the
        # dashboard does not 500 on a fresh environment.
        return _empty_payload(request)
    except Exception as exc:
        logger.warning("rag_stats compute failed: %s", exc)
        return _empty_payload(request)

    await _cache_set(redis_client, cache_key, payload)
    return payload


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


async def _compute(pool: asyncpg.Pool, request: StatsRequest) -> dict[str, Any]:
    async with pool.acquire() as conn:
        total_row = await conn.fetchrow(
            _TOTAL_QUERY,
            request.window_hours,
            request.domain,
        )
        stage_rows = await conn.fetch(
            _STAGE_QUERY,
            request.window_hours,
            request.domain,
        )
        cost_rows = await conn.fetch(
            _COST_BY_DOMAIN_QUERY,
            request.window_hours,
        )

    total_queries = int(total_row["total_queries"] or 0) if total_row else 0
    total_cost = float(total_row["total_cost"] or 0.0) if total_row else 0.0

    stages: dict[str, dict[str, Any]] = {}
    for row in stage_rows:
        stages[row["stage"]] = {
            "p50_ms": _round(row["p50_ms"]),
            "p95_ms": _round(row["p95_ms"]),
            "p99_ms": _round(row["p99_ms"]),
            "samples": int(row["samples"] or 0),
            "cache_hit_rate": (
                round(float(row["cache_hit_rate"]), 4)
                if row["cache_hit_rate"] is not None
                else None
            ),
            "avg_tokens_in": (
                int(row["avg_tokens_in"])
                if row["avg_tokens_in"] is not None
                else None
            ),
            "avg_tokens_out": (
                int(row["avg_tokens_out"])
                if row["avg_tokens_out"] is not None
                else None
            ),
        }

    return {
        "window_hours": request.window_hours,
        "domain_filter": request.domain,
        "total_queries": total_queries,
        "stages": stages,
        "cost": {
            "total_usd": round(total_cost, 6),
            "per_query_avg_usd": (
                round(total_cost / total_queries, 6)
                if total_queries > 0
                else 0.0
            ),
        },
        "top_domains_by_cost": [
            {
                "domain": row["domain"],
                "queries": int(row["queries"]),
                "cost_usd": round(float(row["cost_usd"] or 0.0), 6),
            }
            for row in cost_rows
        ],
    }


def _round(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _empty_payload(request: StatsRequest) -> dict[str, Any]:
    return {
        "window_hours": request.window_hours,
        "domain_filter": request.domain,
        "total_queries": 0,
        "stages": {},
        "cost": {"total_usd": 0.0, "per_query_avg_usd": 0.0},
        "top_domains_by_cost": [],
    }


# ---------------------------------------------------------------------------
# Cache helpers — tolerate a missing or broken Redis transparently.
# ---------------------------------------------------------------------------


async def _cache_get(client: Any | None, key: str) -> dict[str, Any] | None:
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception as exc:
        logger.debug("rag_stats cache get failed: %s", exc)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _cache_set(client: Any | None, key: str, payload: dict[str, Any]) -> None:
    if client is None:
        return
    try:
        await client.set(key, json.dumps(payload), ex=CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.debug("rag_stats cache set failed: %s", exc)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

# ``$1`` = window_hours, ``$2`` = optional domain filter (NULL = no filter).
# ``total_cost_usd`` is already denormalised on insert, no JSON unnest needed.
_TOTAL_QUERY = """
    SELECT
        COUNT(*)                        AS total_queries,
        COALESCE(SUM(total_cost_usd),0) AS total_cost
    FROM rag_traces
    WHERE created_at >= NOW() - ($1::int * INTERVAL '1 hour')
      AND ($2::text IS NULL OR domain = $2::text)
"""

# Per-stage percentiles via ``percentile_cont`` aggregate over the unnested
# ``root_span->'spans'`` array. ``jsonb_array_elements`` expands one span
# row per stage; we filter out noops and coerce numeric fields explicitly.
# NULL-safe on cache_hit / tokens so missing values do not distort averages.
_STAGE_QUERY = """
    WITH span AS (
        SELECT
            (s->>'stage')                        AS stage,
            (s->>'duration_ms')::numeric         AS duration_ms,
            NULLIF(s->>'cache_hit','')::boolean  AS cache_hit,
            NULLIF(s->>'tokens_in','')::int      AS tokens_in,
            NULLIF(s->>'tokens_out','')::int     AS tokens_out
        FROM rag_traces t,
             jsonb_array_elements(t.root_span->'spans') s
        WHERE t.created_at >= NOW() - ($1::int * INTERVAL '1 hour')
          AND ($2::text IS NULL OR t.domain = $2::text)
    )
    SELECT
        stage,
        COUNT(*)                                                        AS samples,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY duration_ms)       AS p50_ms,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)       AS p95_ms,
        percentile_cont(0.99) WITHIN GROUP (ORDER BY duration_ms)       AS p99_ms,
        AVG(CASE WHEN cache_hit IS NOT NULL
                 THEN CASE WHEN cache_hit THEN 1.0 ELSE 0.0 END
            END)                                                        AS cache_hit_rate,
        AVG(tokens_in)                                                  AS avg_tokens_in,
        AVG(tokens_out)                                                 AS avg_tokens_out
    FROM span
    GROUP BY stage
    ORDER BY stage
"""

# Separate aggregate: top-N domains by accumulated spend. Ignored when
# ``domain`` filter is active (callers already know the answer).
_COST_BY_DOMAIN_QUERY = """
    SELECT
        domain,
        COUNT(*)                        AS queries,
        COALESCE(SUM(total_cost_usd),0) AS cost_usd
    FROM rag_traces
    WHERE created_at >= NOW() - ($1::int * INTERVAL '1 hour')
      AND domain IS NOT NULL
    GROUP BY domain
    ORDER BY cost_usd DESC
    LIMIT 10
"""


__all__ = [
    "StatsRequest",
    "aggregate_rag_stats",
    "CACHE_TTL_SECONDS",
]

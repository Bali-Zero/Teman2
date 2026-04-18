"""Unit tests for stats_aggregator — mocked asyncpg pool.

The integration test in tests/integration/test_rag_trace_integration.py
exercises the real queries against Postgres; here we focus on the routing
logic (empty skeleton on missing table, cache hit/miss, shape of payload).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.services.observability.stats_aggregator import (
    CACHE_TTL_SECONDS,
    StatsRequest,
    aggregate_rag_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_pool(total_row=None, stage_rows=None, cost_rows=None, raise_on_total=None):
    """Build a MagicMock that mimics asyncpg.Pool with an async context."""
    conn = MagicMock()
    if raise_on_total is not None:
        conn.fetchrow = AsyncMock(side_effect=raise_on_total)
    else:
        conn.fetchrow = AsyncMock(return_value=total_row or {})
    conn.fetch = AsyncMock(side_effect=[stage_rows or [], cost_rows or []])

    pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


# ---------------------------------------------------------------------------
# Cache key shape
# ---------------------------------------------------------------------------


def test_cache_key_includes_window_and_domain():
    a = StatsRequest(window_hours=24, domain="visa").cache_key()
    b = StatsRequest(window_hours=24, domain=None).cache_key()
    c = StatsRequest(window_hours=12, domain="visa").cache_key()
    assert a != b != c
    assert "24h" in a and "visa" in a
    assert "all" in b


# ---------------------------------------------------------------------------
# Empty skeleton on missing table
# ---------------------------------------------------------------------------


async def test_missing_table_returns_empty_payload():
    pool, _ = _mock_pool(raise_on_total=asyncpg.UndefinedTableError("rag_traces"))
    req = StatsRequest(window_hours=24)
    payload = await aggregate_rag_stats(pool, req)
    assert payload["total_queries"] == 0
    assert payload["stages"] == {}
    assert payload["cost"]["total_usd"] == 0.0
    assert payload["top_domains_by_cost"] == []


async def test_generic_error_also_returns_empty_payload():
    pool, _ = _mock_pool(raise_on_total=RuntimeError("boom"))
    req = StatsRequest(window_hours=24)
    payload = await aggregate_rag_stats(pool, req)
    assert payload["total_queries"] == 0
    assert payload["stages"] == {}


# ---------------------------------------------------------------------------
# Shape of full response
# ---------------------------------------------------------------------------


async def test_full_payload_shape():
    pool, _ = _mock_pool(
        total_row={"total_queries": 100, "total_cost": Decimal("12.34")},
        stage_rows=[
            {
                "stage": "retrieval",
                "samples": 100,
                "p50_ms": Decimal("42"),
                "p95_ms": Decimal("180"),
                "p99_ms": Decimal("450"),
                "cache_hit_rate": Decimal("0.67"),
                "avg_tokens_in": Decimal("10"),
                "avg_tokens_out": None,
            },
            {
                "stage": "reasoning",
                "samples": 90,
                "p50_ms": Decimal("800"),
                "p95_ms": Decimal("3200"),
                "p99_ms": Decimal("8000"),
                "cache_hit_rate": None,
                "avg_tokens_in": Decimal("450"),
                "avg_tokens_out": Decimal("120"),
            },
        ],
        cost_rows=[
            {"domain": "visa", "queries": 60, "cost_usd": Decimal("7.50")},
            {"domain": "tax", "queries": 40, "cost_usd": Decimal("4.84")},
        ],
    )
    req = StatsRequest(window_hours=24, domain=None)
    payload = await aggregate_rag_stats(pool, req)
    assert payload["total_queries"] == 100
    assert payload["cost"]["total_usd"] == pytest.approx(12.34)
    assert payload["cost"]["per_query_avg_usd"] == pytest.approx(0.1234, rel=1e-3)

    retrieval = payload["stages"]["retrieval"]
    assert retrieval["p50_ms"] == 42.0
    assert retrieval["p95_ms"] == 180.0
    assert retrieval["p99_ms"] == 450.0
    assert retrieval["cache_hit_rate"] == pytest.approx(0.67)
    assert retrieval["avg_tokens_in"] == 10
    assert retrieval["avg_tokens_out"] is None

    reasoning = payload["stages"]["reasoning"]
    assert reasoning["cache_hit_rate"] is None  # NULL preserved
    assert reasoning["avg_tokens_in"] == 450

    assert payload["top_domains_by_cost"][0]["domain"] == "visa"
    assert payload["top_domains_by_cost"][0]["cost_usd"] == 7.5


async def test_zero_queries_avg_is_zero():
    pool, _ = _mock_pool(total_row={"total_queries": 0, "total_cost": Decimal("0")})
    payload = await aggregate_rag_stats(pool, StatsRequest(window_hours=24))
    assert payload["cost"]["per_query_avg_usd"] == 0.0


# ---------------------------------------------------------------------------
# Redis cache
# ---------------------------------------------------------------------------


async def test_cache_hit_short_circuits_db():
    pool, conn = _mock_pool()
    cached = {"total_queries": 999, "stages": {}, "cost": {"total_usd": 1.23,
              "per_query_avg_usd": 0.01}, "top_domains_by_cost": [],
              "window_hours": 24, "domain_filter": None}
    redis = MagicMock()
    redis.get = AsyncMock(return_value=json.dumps(cached))
    redis.set = AsyncMock()

    payload = await aggregate_rag_stats(
        pool, StatsRequest(window_hours=24), redis_client=redis,
    )
    assert payload == cached
    conn.fetchrow.assert_not_called()
    redis.set.assert_not_called()  # we didn't compute, nothing to cache


async def test_cache_miss_writes_result():
    pool, _ = _mock_pool(total_row={"total_queries": 5, "total_cost": Decimal("1.0")})
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    payload = await aggregate_rag_stats(
        pool, StatsRequest(window_hours=24), redis_client=redis,
    )
    assert payload["total_queries"] == 5
    redis.set.assert_awaited_once()
    _, kwargs = redis.set.call_args
    assert kwargs["ex"] == CACHE_TTL_SECONDS


async def test_cache_broken_does_not_break_query():
    pool, _ = _mock_pool(total_row={"total_queries": 2, "total_cost": Decimal("0.5")})
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=RuntimeError("redis down"))
    redis.set = AsyncMock(side_effect=RuntimeError("redis down"))

    # Must still compute from DB and return a valid payload.
    payload = await aggregate_rag_stats(
        pool, StatsRequest(window_hours=24), redis_client=redis,
    )
    assert payload["total_queries"] == 2


async def test_cache_corrupted_json_triggers_recompute():
    pool, conn = _mock_pool(
        total_row={"total_queries": 3, "total_cost": Decimal("0.5")},
    )
    redis = MagicMock()
    redis.get = AsyncMock(return_value="{not valid json")
    redis.set = AsyncMock()

    payload = await aggregate_rag_stats(
        pool, StatsRequest(window_hours=24), redis_client=redis,
    )
    assert payload["total_queries"] == 3
    conn.fetchrow.assert_awaited()
    redis.set.assert_awaited_once()

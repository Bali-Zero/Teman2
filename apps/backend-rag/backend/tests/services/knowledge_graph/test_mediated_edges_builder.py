"""Tests for mediated_edges_builder — Tier-B SQL JOIN cross-doc edges."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.knowledge_graph.mediated_edges_builder import (
    _CONF_DETERMINISTIC,
    _CONF_HEURISTIC_TIME,
    _CONTEMPORANEOUS_WINDOW_DAYS,
    _MAX_EDGES_PER_PASS,
    _parse_inserted_count,
    build_mediated_edges,
)

# ─── _parse_inserted_count: defensive parsing ───────────────────────────


def test_parse_inserted_count_normal():
    assert _parse_inserted_count("INSERT 0 12") == 12
    assert _parse_inserted_count("INSERT 0 0") == 0
    assert _parse_inserted_count("INSERT 0 9999") == 9999


def test_parse_inserted_count_handles_weird_formats():
    """Don't crash on unexpected execute() return values."""
    assert _parse_inserted_count("") == 0
    assert _parse_inserted_count("UPDATE 5") == 0
    assert _parse_inserted_count("WEIRD") == 0
    assert _parse_inserted_count("INSERT 0 not_a_number") == 0
    # asyncpg conventionally returns "INSERT 0 N", but be paranoid
    assert _parse_inserted_count(None) == 0  # type: ignore[arg-type]


# ─── Constants sanity ───────────────────────────────────────────────────


def test_constants_have_safe_values():
    """Sanity-check thresholds — avoid accidental config that runs forever."""
    assert _MAX_EDGES_PER_PASS > 0
    assert _MAX_EDGES_PER_PASS <= 100_000  # don't insert more than 100k/pass
    assert 1 <= _CONTEMPORANEOUS_WINDOW_DAYS <= 30
    assert _CONF_DETERMINISTIC == 1.0  # property match must be exact
    assert 0.5 <= _CONF_HEURISTIC_TIME < 1.0  # below deterministic, above noise


# ─── build_mediated_edges happy-path + failure modes ────────────────────


@pytest.mark.asyncio
async def test_build_mediated_edges_happy_path():
    """SQL execute returns 'INSERT 0 N' twice → totals propagated."""
    conn = AsyncMock()
    # Two execute() calls inside the function: contemporaneous + coworker
    conn.execute = AsyncMock(side_effect=["INSERT 0 5", "INSERT 0 3"])
    pool = _make_pool_mock(conn)

    result = await build_mediated_edges(pool)

    assert result["ok"] is True
    assert result["contemporaneous"] == 5
    assert result["coworker_at"] == 3
    assert result["elapsed_s"] >= 0.0
    # Two distinct INSERT statements should have run
    assert conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_build_mediated_edges_swallows_db_error():
    """Any DB exception → ok=False with error message, no raise to caller."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=RuntimeError("PG connection lost"))
    pool = _make_pool_mock(conn)

    result = await build_mediated_edges(pool)

    assert result["ok"] is False
    assert "PG connection lost" in result["error"]
    assert "contemporaneous" not in result  # didn't reach the metrics


@pytest.mark.asyncio
async def test_build_mediated_edges_passes_window_to_sql():
    """The CONTEMPORANEOUS query must receive the configured window in days."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["INSERT 0 0", "INSERT 0 0"])
    pool = _make_pool_mock(conn)

    await build_mediated_edges(pool)

    # First execute() is the contemporaneous query; check its bound params
    cont_args = conn.execute.call_args_list[0][0]
    # cont_args = (sql, days, max_edges, confidence)
    assert cont_args[1] == _CONTEMPORANEOUS_WINDOW_DAYS
    assert cont_args[2] == _MAX_EDGES_PER_PASS
    assert cont_args[3] == _CONF_HEURISTIC_TIME

    # Second execute() is COWORKER_AT
    cow_args = conn.execute.call_args_list[1][0]
    # cow_args = (sql, max_edges, confidence)
    assert cow_args[1] == _MAX_EDGES_PER_PASS
    assert cow_args[2] == _CONF_DETERMINISTIC


@pytest.mark.asyncio
async def test_build_mediated_edges_zero_inserts_is_ok():
    """No new edges to insert (steady state) is a normal outcome, not error."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["INSERT 0 0", "INSERT 0 0"])
    pool = _make_pool_mock(conn)

    result = await build_mediated_edges(pool)

    assert result["ok"] is True
    assert result["contemporaneous"] == 0
    assert result["coworker_at"] == 0


# ─── SQL contract guards ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contemporaneous_query_uses_canonical_pair_ordering():
    """Verify the CONTEMPORANEOUS SQL uses d1 < d2 to dedupe pairs."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["INSERT 0 0", "INSERT 0 0"])
    pool = _make_pool_mock(conn)

    await build_mediated_edges(pool)

    # First call → CONTEMPORANEOUS sql
    cont_sql = conn.execute.call_args_list[0][0][0]
    assert "CONTEMPORANEOUS" in cont_sql
    # Canonical ordering pattern (avoids duplicate symmetric pairs)
    assert "d1.entity_id < d2.entity_id" in cont_sql
    # Filters deleted nodes
    assert "deleted_at IS NULL" in cont_sql


@pytest.mark.asyncio
async def test_coworker_query_uses_idempotent_upsert():
    """COWORKER_AT must use ON CONFLICT to be re-runnable."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=["INSERT 0 0", "INSERT 0 0"])
    pool = _make_pool_mock(conn)

    await build_mediated_edges(pool)

    cow_sql = conn.execute.call_args_list[1][0][0]
    assert "COWORKER_AT" in cow_sql
    assert "ON CONFLICT" in cow_sql
    assert "DO UPDATE" in cow_sql


# ─── Helpers ────────────────────────────────────────────────────────────


def _make_pool_mock(conn):
    """asyncpg.Pool-like mock yielding `conn` from `async with pool.acquire()`."""
    pool = AsyncMock()

    class _Acquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    pool.acquire = lambda: _Acquire()
    return pool

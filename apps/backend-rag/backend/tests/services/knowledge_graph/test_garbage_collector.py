"""Tests for crm_kg garbage_collector — orphan node soft-delete + edge GC."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.knowledge_graph.garbage_collector import (
    _HARD_DELETE_GRACE_DAYS,
    _MAX_HARD_DELETE_PER_PASS,
    _MAX_SOFT_DELETE_PER_PASS,
    _parse_deleted_count,
    _parse_updated_count,
    garbage_collect,
)

# ─── Defensive parsers ──────────────────────────────────────────────────


def test_parse_updated_count_normal():
    assert _parse_updated_count("UPDATE 0") == 0
    assert _parse_updated_count("UPDATE 7") == 7
    assert _parse_updated_count("UPDATE 9999") == 9999


def test_parse_updated_count_handles_garbage():
    assert _parse_updated_count("") == 0
    assert _parse_updated_count("INSERT 0 5") == 0  # wrong verb
    assert _parse_updated_count("UPDATE not_a_number") == 0
    assert _parse_updated_count(None) == 0  # type: ignore[arg-type]


def test_parse_deleted_count_normal():
    assert _parse_deleted_count("DELETE 0") == 0
    assert _parse_deleted_count("DELETE 42") == 42


def test_parse_deleted_count_handles_garbage():
    assert _parse_deleted_count("") == 0
    assert _parse_deleted_count("UPDATE 5") == 0  # wrong verb
    assert _parse_deleted_count(None) == 0  # type: ignore[arg-type]


# ─── Constants sanity ───────────────────────────────────────────────────


def test_grace_days_is_safe_default():
    """Window must be long enough for ops recovery, not too long for stale."""
    assert 7 <= _HARD_DELETE_GRACE_DAYS <= 90


def test_max_per_pass_is_bounded():
    """Per-pass cap protects against runaway transactions."""
    assert 0 < _MAX_SOFT_DELETE_PER_PASS <= 100_000
    assert 0 < _MAX_HARD_DELETE_PER_PASS <= 100_000


# ─── garbage_collect happy-path + failure modes ─────────────────────────


@pytest.mark.asyncio
async def test_garbage_collect_happy_path():
    """4 SQL statements (3 soft + 1 hard) → counts aggregated in result."""
    conn = AsyncMock()
    # Order matches function: orphan_documents, orphan_clients,
    # orphan_practices, hard_delete_old_edges
    conn.execute = AsyncMock(side_effect=[
        "UPDATE 3",   # documents
        "UPDATE 1",   # clients
        "UPDATE 2",   # practices
        "DELETE 7",   # edges
    ])
    pool = _make_pool_mock(conn)

    result = await garbage_collect(pool)

    assert result["ok"] is True
    assert result["soft_deleted"]["documents"] == 3
    assert result["soft_deleted"]["clients"] == 1
    assert result["soft_deleted"]["practices"] == 2
    assert result["hard_deleted_edges"] == 7
    assert conn.execute.call_count == 4


@pytest.mark.asyncio
async def test_garbage_collect_swallows_db_error():
    """DB exception → ok=False with error message, no raise."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=RuntimeError("PG timeout"))
    pool = _make_pool_mock(conn)

    result = await garbage_collect(pool)

    assert result["ok"] is False
    assert "PG timeout" in result["error"]
    assert "soft_deleted" not in result


@pytest.mark.asyncio
async def test_garbage_collect_zero_orphans_is_normal():
    """Steady state (no orphans) is the expected case after first cleanup."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=[
        "UPDATE 0", "UPDATE 0", "UPDATE 0", "DELETE 0",
    ])
    pool = _make_pool_mock(conn)

    result = await garbage_collect(pool)

    assert result["ok"] is True
    assert sum(result["soft_deleted"].values()) == 0
    assert result["hard_deleted_edges"] == 0


@pytest.mark.asyncio
async def test_garbage_collect_passes_grace_days_to_sql():
    """The hard-delete query must receive the configured grace days."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=[
        "UPDATE 0", "UPDATE 0", "UPDATE 0", "DELETE 0",
    ])
    pool = _make_pool_mock(conn)

    await garbage_collect(pool)

    # Last call is _hard_delete_old_edges
    hard_args = conn.execute.call_args_list[3][0]
    # hard_args = (sql, grace_days_str, max_delete)
    assert hard_args[1] == str(_HARD_DELETE_GRACE_DAYS)
    assert hard_args[2] == _MAX_HARD_DELETE_PER_PASS


# ─── SQL contract guards ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_delete_documents_query_filters_archived():
    """Documents that are is_archived = TRUE should also be considered orphan."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=[
        "UPDATE 0", "UPDATE 0", "UPDATE 0", "DELETE 0",
    ])
    pool = _make_pool_mock(conn)

    await garbage_collect(pool)

    docs_sql = conn.execute.call_args_list[0][0][0]
    assert "crm_document" in docs_sql
    assert "is_archived" in docs_sql
    # Must filter live nodes only (don't re-soft-delete already deleted)
    assert "deleted_at IS NULL" in docs_sql


@pytest.mark.asyncio
async def test_soft_delete_clients_respects_clients_deleted_at():
    """clients table uses soft-delete via deleted_at — same pattern."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=[
        "UPDATE 0", "UPDATE 0", "UPDATE 0", "DELETE 0",
    ])
    pool = _make_pool_mock(conn)

    await garbage_collect(pool)

    clients_sql = conn.execute.call_args_list[1][0][0]
    assert "crm_client" in clients_sql
    assert "c.deleted_at IS NULL" in clients_sql


@pytest.mark.asyncio
async def test_hard_delete_edges_uses_grace_window():
    """Edge GC must use NOW() - interval to filter expired soft-deletes."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=[
        "UPDATE 0", "UPDATE 0", "UPDATE 0", "DELETE 0",
    ])
    pool = _make_pool_mock(conn)

    await garbage_collect(pool)

    edges_sql = conn.execute.call_args_list[3][0][0]
    assert "DELETE FROM crm_kg_edges" in edges_sql
    assert "deleted_at IS NOT NULL" in edges_sql
    # Interval expression for grace window
    assert "interval" in edges_sql.lower()


# ─── Helpers ────────────────────────────────────────────────────────────


def _make_pool_mock(conn):
    pool = AsyncMock()

    class _Acquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    pool.acquire = lambda: _Acquire()
    return pool

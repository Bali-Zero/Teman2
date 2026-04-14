"""Tests for bridge outbox retention."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.bridge.retention import RETENTION_DAYS, prune_outbox


def test_retention_days_constant():
    assert RETENTION_DAYS == 30


@pytest.mark.asyncio
async def test_prune_outbox_returns_deleted_count():
    """asyncpg 'DELETE N' result string is parsed to int."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 42")

    deleted = await prune_outbox(conn)
    assert deleted == 42
    conn.execute.assert_called_once()
    sql = conn.execute.call_args.args[0]
    assert "DELETE FROM bridge_outbox" in sql
    assert "30 days" in sql


@pytest.mark.asyncio
async def test_prune_outbox_custom_days():
    """Custom retention_days reflected in SQL."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 0")
    await prune_outbox(conn, retention_days=7)
    sql = conn.execute.call_args.args[0]
    assert "7 days" in sql


@pytest.mark.asyncio
async def test_prune_outbox_handles_unparseable_result():
    """If result is empty/garbage, return 0 (no crash)."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="")
    deleted = await prune_outbox(conn)
    assert deleted == 0


@pytest.mark.asyncio
async def test_prune_outbox_handles_none_result():
    """asyncpg may return None for some setups."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    deleted = await prune_outbox(conn)
    assert deleted == 0

"""Tests for cortex tables bootstrap — idempotent, all 7 tables created."""
import pytest
from unittest.mock import AsyncMock

from cell.core.db import create_cortex_tables


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_create_cortex_tables_runs_all_statements(monkeypatch, mock_pool):
    from cell.core import db as cell_db

    monkeypatch.setattr(cell_db, "get_pool", AsyncMock(return_value=mock_pool))
    await cell_db.create_cortex_tables()
    # 7 CREATE TABLE + at least 14 CREATE INDEX = 21+ execute calls
    assert mock_pool.execute.await_count >= 21


@pytest.mark.asyncio
async def test_create_cortex_tables_idempotent(monkeypatch, mock_pool):
    """Running twice should not raise."""
    from cell.core import db as cell_db

    monkeypatch.setattr(cell_db, "get_pool", AsyncMock(return_value=mock_pool))
    await cell_db.create_cortex_tables()
    await cell_db.create_cortex_tables()
    # Should have doubled the call count
    assert mock_pool.execute.await_count >= 42


@pytest.mark.asyncio
async def test_create_cortex_tables_handles_db_error(monkeypatch, caplog):
    """DB failure should log error, not raise."""
    from cell.core import db as cell_db

    failing_pool = AsyncMock()
    failing_pool.execute = AsyncMock(side_effect=Exception("connection refused"))
    monkeypatch.setattr(cell_db, "get_pool", AsyncMock(return_value=failing_pool))

    # Should not raise
    await cell_db.create_cortex_tables()
    assert "Failed to create cortex tables" in caplog.text

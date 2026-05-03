"""Tests for portal dashboard summary endpoint."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from backend.app.routers.portal_dashboard import (
    _fetch_deadlines,
    _fetch_open_actions,
    _fetch_unread_count,
)


@pytest.mark.asyncio
async def test_open_actions_returns_formatted_list() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 1,
            "title": "KITAS Extension",
            "type": "kitas_ext",
            "pending_from_client": "passport_scan",
            "status": "waiting_documents",
            "updated_at": datetime.now(timezone.utc),
        },
    ]
    actions = await _fetch_open_actions(mock_conn, 42)
    assert len(actions) == 1
    assert actions[0]["id"] == 1
    assert actions[0]["pending_from_client"] == "passport_scan"


@pytest.mark.asyncio
async def test_open_actions_graceful_on_missing_table() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception("relation 'practices' does not exist")
    assert await _fetch_open_actions(mock_conn, 42) == []


@pytest.mark.asyncio
async def test_deadlines_merges_visa_and_practices_sorted() -> None:
    mock_conn = AsyncMock()
    future_visa = date.today() + timedelta(days=10)
    future_passport = date.today() + timedelta(days=20)
    future_practice = datetime.now(timezone.utc) + timedelta(days=5)

    mock_conn.fetchrow.return_value = {
        "id": 42,
        "visa_expiry": future_visa,
        "passport_expiry": future_passport,
    }
    mock_conn.fetch.return_value = [
        {
            "id": 7,
            "label": "Tax report",
            "expiry_date": future_practice,
            "kind": "tax",
        },
    ]
    deadlines = await _fetch_deadlines(mock_conn, 42)
    assert len(deadlines) == 3
    # Practice is soonest (5 days) then visa (10) then passport (20)
    assert deadlines[0]["kind"] == "tax"
    assert deadlines[1]["kind"] == "visa"
    assert deadlines[2]["kind"] == "passport"


@pytest.mark.asyncio
async def test_deadlines_graceful_on_missing_column() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = Exception("column 'visa_expiry' does not exist")
    mock_conn.fetch.side_effect = Exception("relation 'practices' does not exist")
    assert await _fetch_deadlines(mock_conn, 42) == []


@pytest.mark.asyncio
async def test_unread_count_returns_int() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 3
    assert await _fetch_unread_count(mock_conn, 42) == 3


@pytest.mark.asyncio
async def test_unread_count_graceful_on_missing_table() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchval.side_effect = Exception("no portal_messages table")
    assert await _fetch_unread_count(mock_conn, 42) == 0


@pytest.mark.asyncio
async def test_dashboard_summary_has_three_sections(monkeypatch) -> None:
    """Integration-ish: verify summary endpoint returns 3 required keys."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_database_pool
    from backend.app.routers.portal import get_current_client
    from backend.app.routers.portal_dashboard import router

    app = FastAPI()
    app.include_router(router)

    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = []
    mock_conn.fetchrow.return_value = None
    mock_conn.fetchval.return_value = 0

    class _PoolCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _PoolCtx()

    app.dependency_overrides[get_current_client] = lambda: {"client_id": 42}
    app.dependency_overrides[get_database_pool] = lambda: _Pool()

    client = TestClient(app)
    r = client.get("/api/portal/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert "open_actions" in body
    assert "upcoming_deadlines" in body
    assert "unread_messages" in body
    assert isinstance(body["open_actions"], list)
    assert isinstance(body["upcoming_deadlines"], list)
    assert isinstance(body["unread_messages"], int)

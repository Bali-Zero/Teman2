"""Tests for portal notification prefs endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.routers.portal_notification_prefs import router


def _build_app(mock_conn: AsyncMock, client: dict | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    class _PoolCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _PoolCtx()

    app.dependency_overrides[get_current_client] = lambda: client or {
        "client_id": 42,
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
    }
    app.dependency_overrides[get_database_pool] = lambda: _Pool()
    return TestClient(app)


def test_get_prefs_returns_defaults_when_row_missing() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None
    tc = _build_app(mock_conn)
    r = tc.get("/api/portal/notifications/prefs")
    assert r.status_code == 200
    assert r.json() == {
        "email_enabled": True,
        "wa_enabled": False,
        "wa_phone": None,
    }


def test_get_prefs_returns_stored_row() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "email_enabled": False,
        "wa_enabled": True,
        "wa_phone": "628123456789",
    }
    tc = _build_app(mock_conn)
    r = tc.get("/api/portal/notifications/prefs")
    assert r.status_code == 200
    body = r.json()
    assert body["wa_enabled"] is True
    assert body["wa_phone"] == "628123456789"


def test_put_prefs_rejects_wa_enabled_without_phone() -> None:
    mock_conn = AsyncMock()
    tc = _build_app(mock_conn)
    r = tc.put(
        "/api/portal/notifications/prefs",
        json={"email_enabled": True, "wa_enabled": True, "wa_phone": None},
    )
    assert r.status_code == 422


def test_put_prefs_rejects_invalid_e164() -> None:
    mock_conn = AsyncMock()
    tc = _build_app(mock_conn)
    r = tc.put(
        "/api/portal/notifications/prefs",
        json={
            "email_enabled": True,
            "wa_enabled": True,
            "wa_phone": "+628123456789",  # leading '+' not allowed
        },
    )
    assert r.status_code == 422


def test_put_prefs_upserts_successfully() -> None:
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = "INSERT 0 1"
    tc = _build_app(mock_conn)
    r = tc.put(
        "/api/portal/notifications/prefs",
        json={
            "email_enabled": True,
            "wa_enabled": True,
            "wa_phone": "628123456789",
        },
    )
    assert r.status_code == 200
    assert r.json()["wa_enabled"] is True
    mock_conn.execute.assert_awaited_once()


def test_put_prefs_503_when_table_missing() -> None:
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = Exception(
        "relation 'notification_prefs' does not exist"
    )
    tc = _build_app(mock_conn)
    r = tc.put(
        "/api/portal/notifications/prefs",
        json={"email_enabled": True, "wa_enabled": False, "wa_phone": None},
    )
    assert r.status_code == 503

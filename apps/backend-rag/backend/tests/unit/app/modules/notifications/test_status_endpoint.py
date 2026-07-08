"""Regression test for ``GET /api/notifications/status`` (live prod 500).

BUG (captured live 2026-07-08):
    get_database_pool() missing 1 required positional argument: 'request'

Root cause: ``get_notification_status`` (and 10 sibling handlers across
``router.py`` / ``admin_router.py`` / ``test_endpoint.py`` in this same
module — W89 class-audit) called ``await get_database_pool()`` with no
arguments. ``get_database_pool`` is a **sync**, non-async FastAPI
dependency that requires a ``Request`` (``backend/app/deps/database.py``)
— it is meant to be resolved via ``Depends(get_database_pool)`` as a
handler parameter, exactly like the working sibling handlers in
``admin_team_activity.py`` (``db_pool: asyncpg.Pool = Depends(get_database_pool)``).

Calling it directly with zero args raises
``TypeError: get_database_pool() missing 1 required positional
argument: 'request'`` — FastAPI's exception middleware turns that into
an unhandled 500 (it never even reaches the router's own
``try/except Exception`` block, because the crash happens while FastAPI
is resolving dependencies, before the handler body runs).

This test drives the router through a real ``TestClient`` (no live DB,
no network) so it exercises the *actual* dependency-resolution path —
a bare unit test that imports the coroutine and calls it manually would
have hidden this exact bug (the missing positional arg only bites when
FastAPI tries to resolve dependencies for the wired-up handler).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.modules.notifications.admin_router import router as admin_router
from backend.app.modules.notifications.router import router as notifications_router


class _PoolCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a):
        return False


class _Pool:
    """Minimal asyncpg.Pool stand-in — no live DB, no network."""

    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _PoolCtx(self._conn)


def _make_client(router, pool: _Pool, *, is_admin: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {
        "email": "tester@balizero.com",
        "is_admin": is_admin,
    }
    app.dependency_overrides[get_database_pool] = lambda: pool
    return TestClient(app)


def test_notification_status_returns_200_not_500() -> None:
    """GUILT: this is the exact live-prod call. Pre-fix, FastAPI cannot
    resolve ``get_database_pool()`` (called with 0 args, needs ``request``)
    and the endpoint 500s before the handler body ever runs. Post-fix,
    the pool is injected via ``Depends`` and the handler returns 200."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.side_effect = [3, datetime(2026, 7, 1, tzinfo=timezone.utc)]

    client = _make_client(notifications_router, _Pool(mock_conn))
    resp = client.get("/api/notifications/status")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "operational"
    assert body["pending_alerts"] == 3
    assert body["email_provider"] == "sendgrid"


def test_notification_status_innocence_pool_never_called_with_zero_args() -> None:
    """INNOCENCE: the fixed handler must resolve the pool via FastAPI's
    dependency-injection (Depends), never by invoking the dependency
    function directly with no arguments. Guards against a regression
    that re-introduces ``await get_database_pool()`` (bare call)."""
    import inspect

    from backend.app.modules.notifications.router import get_notification_status

    sig = inspect.signature(get_notification_status)
    assert "pool" in sig.parameters, (
        "get_notification_status must accept `pool` as a FastAPI-injected "
        "parameter (Depends(get_database_pool)) — calling get_database_pool() "
        "directly with no args is the exact live bug this test guards against."
    )


def test_admin_dashboard_returns_200_not_500() -> None:
    """W89 class-audit sibling: admin_router.get_dashboard had the same
    ``await get_database_pool()`` (0-arg) defect in the same module."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "total_24h": 1,
        "total_7d": 2,
        "total_30d": 3,
        "pending": 0,
        "sent_24h": 1,
        "failed_24h": 0,
    }
    mock_conn.fetch.return_value = []  # type/status/top_clients/recent — all empty
    mock_conn.fetchval.return_value = None

    client = _make_client(admin_router, _Pool(mock_conn), is_admin=True)
    resp = client.get("/api/admin/notifications/dashboard")

    assert resp.status_code == 200, resp.text
    assert resp.json()["system_status"] == "healthy"

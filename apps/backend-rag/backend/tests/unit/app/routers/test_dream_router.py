"""
Tests for backend.app.routers.dream — TODO #77 closure.

The save_state/get_state pair must now go through Postgres JSONB instead
of the legacy in-memory MOCK_DB. The pool is injected via
``get_database_pool`` and the asyncpg JSONB codec means we pass dicts
(NOT json.dumps strings — see
``discovery_jsonb_double_encoding_systemic_2026_05_14`` memory entry).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.deps.database import get_database_pool
from backend.app.routers.dream import router

app = FastAPI()
app.include_router(router)


def _make_pool_with_conn(conn_mock: AsyncMock) -> MagicMock:
    """Create a fake asyncpg-style pool that yields ``conn_mock``
    via ``async with pool.acquire() as conn``.
    """
    pool = MagicMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn_mock

        async def __aexit__(self, exc_type, exc, tb):
            return None

    pool.acquire = MagicMock(side_effect=lambda: _AcquireCtx())
    return pool


def test_save_state_upserts_dict_not_json_string() -> None:
    """asyncpg pool has a jsonb codec — we MUST pass dict, not json.dumps.
    Regression guard for the systemic jsonb-double-encoding scar
    (memory: discovery_jsonb_double_encoding_systemic_2026_05_14).
    """
    conn = AsyncMock()
    conn.execute.return_value = None
    pool = _make_pool_with_conn(conn)

    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        payload = {"articles": ["a", "b"], "inspirations": []}
        response = client.post(
            "/api/dream/state?user_id=user-123",
            json=payload,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "timestamp" in body
    finally:
        app.dependency_overrides.clear()

    # Inspect the SQL call.
    assert conn.execute.await_count == 1
    args = conn.execute.await_args.args
    sql = args[0]
    assert "INSERT INTO dream_room_state" in sql
    assert "ON CONFLICT" in sql
    # 2nd positional arg = user_id, 3rd = state dict (NOT json string).
    assert args[1] == "user-123"
    assert args[2] == payload
    # CRITICAL: passing a string instead of a dict means double-encoding.
    assert not isinstance(args[2], str), (
        "TODO #77 regression: state passed as string would double-encode "
        "through the jsonb codec — see "
        "discovery_jsonb_double_encoding_systemic_2026_05_14.md"
    )


def test_save_state_returns_iso_timestamp() -> None:
    conn = AsyncMock()
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        response = client.post(
            "/api/dream/state?user_id=u",
            json={"x": 1},
        )
        assert response.status_code == 200
        ts = response.json()["timestamp"]
        # ISO 8601 starts with year-month-day; cheap sanity check.
        assert "T" in ts
        assert len(ts) >= 19
    finally:
        app.dependency_overrides.clear()


def test_get_state_returns_dict_when_present() -> None:
    conn = AsyncMock()
    conn.fetchrow.return_value = {"state": {"articles": ["a"], "inspirations": []}}
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        response = client.get("/api/dream/state/user-123")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["state"] == {"articles": ["a"], "inspirations": []}
    finally:
        app.dependency_overrides.clear()

    assert conn.fetchrow.await_count == 1
    args = conn.fetchrow.await_args.args
    assert "SELECT state FROM dream_room_state" in args[0]
    assert args[1] == "user-123"


def test_get_state_returns_none_when_missing() -> None:
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        response = client.get("/api/dream/state/missing-user")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["state"] is None
    finally:
        app.dependency_overrides.clear()


def test_mock_db_global_is_gone() -> None:
    """The legacy in-memory MOCK_DB must be removed — it was a foot-gun
    that silently dropped state on every machine restart."""
    from backend.app.routers import dream as dream_module
    assert not hasattr(dream_module, "MOCK_DB"), (
        "MOCK_DB still present — TODO #77 not fully closed. "
        "Persistence must go through Postgres only."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

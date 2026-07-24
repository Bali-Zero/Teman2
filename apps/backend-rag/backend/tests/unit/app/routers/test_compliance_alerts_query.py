"""Unit tests for compliance-alert list query construction."""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.routers.compliance_alerts import list_alerts


class _FakeConnection:
    def __init__(self) -> None:
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.query = query
        self.args = args
        return []


class _Acquire:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakePool:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    def acquire(self) -> _Acquire:
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_active_only_filters_and_orders_before_limit() -> None:
    pool = _FakePool()

    result = await list_alerts(
        client_id=None,
        category=None,
        severity=None,
        status_filter=None,
        active_only=True,
        limit=6,
        offset=0,
        user={"email": "zero@balizero.com"},
        pool=pool,  # type: ignore[arg-type]
    )

    query = " ".join(pool.connection.query.split())
    assert "WHERE status IN ('pending','sent','acknowledged')" in query
    assert "ORDER BY deadline ASC, created_at DESC LIMIT $1 OFFSET $2" in query
    assert query.index("status IN") < query.index("LIMIT")
    assert pool.connection.args == (6, 0)
    assert result == {"items": [], "limit": 6, "offset": 0}


@pytest.mark.asyncio
async def test_active_only_preserves_team_scope_and_parameter_indexes() -> None:
    pool = _FakePool()

    await list_alerts(
        client_id=None,
        category=None,
        severity=None,
        status_filter=None,
        active_only=True,
        limit=6,
        offset=0,
        user={"email": "member@example.test"},
        pool=pool,  # type: ignore[arg-type]
    )

    query = " ".join(pool.connection.query.split())
    assert "assigned_to = $1" in query
    assert "status IN ('pending','sent','acknowledged')" in query
    assert "LIMIT $2 OFFSET $3" in query
    assert pool.connection.args == ("member@example.test", 6, 0)

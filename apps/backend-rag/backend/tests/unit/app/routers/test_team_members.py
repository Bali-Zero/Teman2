"""Tests for team_members router."""
from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool with acquire() context manager."""
    pool = MagicMock()
    conn = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


@pytest.fixture
def test_app(mock_db_pool):
    """Minimal FastAPI app with team_members router and dependency overrides."""
    from backend.app.routers import team_members

    app = FastAPI()
    app.include_router(team_members.router)

    pool, _conn = mock_db_pool

    def override_pool():
        return pool

    def override_user():
        return {"email": "admin@balizero.com", "role": "admin"}

    app.dependency_overrides[get_database_pool] = override_pool
    app.dependency_overrides[get_current_user] = override_user

    return app, mock_db_pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_team_members_returns_members(test_app):
    """GET /api/team/members returns the list of active team members."""
    app, (pool, conn) = test_app

    # Simulate two asyncpg Record-like dicts returned by conn.fetch
    fake_rows = [
        {"email": "damar@balizero.com", "full_name": "Damar", "role": "agent", "avatar_url": None},
        {"email": "asya@balizero.com", "full_name": "Asya", "role": "manager", "avatar_url": "https://example.com/asya.png"},
    ]
    conn.fetch = AsyncMock(return_value=fake_rows)

    client = TestClient(app)
    response = client.get("/api/team/members")

    assert response.status_code == 200
    data = response.json()
    assert "members" in data
    assert len(data["members"]) == 2
    assert data["members"][0]["email"] == "damar@balizero.com"
    assert data["members"][1]["email"] == "asya@balizero.com"


def test_list_team_members_empty(test_app):
    """GET /api/team/members returns empty list when no active members."""
    app, (pool, conn) = test_app

    conn.fetch = AsyncMock(return_value=[])

    client = TestClient(app)
    response = client.get("/api/team/members")

    assert response.status_code == 200
    assert response.json() == {"members": []}


def test_list_team_members_endpoint_requires_auth():
    """The endpoint declares get_current_user as a dependency."""
    from backend.app.routers.team_members import list_team_members

    sig = inspect.signature(list_team_members)
    param_names = list(sig.parameters.keys())
    assert "current_user" in param_names, "current_user dependency missing from signature"
    assert "pool" in param_names, "pool dependency missing from signature"


def test_list_team_members_sql_uses_pool(test_app):
    """conn.fetch is called exactly once per request."""
    app, (pool, conn) = test_app

    conn.fetch = AsyncMock(return_value=[])

    client = TestClient(app)
    client.get("/api/team/members")

    conn.fetch.assert_awaited_once()


def test_list_team_members_avatar_url_nullable(test_app):
    """avatar_url is included even when None."""
    app, (pool, conn) = test_app

    fake_rows = [
        {"email": "a@balizero.com", "full_name": "A", "role": "agent", "avatar_url": None},
    ]
    conn.fetch = AsyncMock(return_value=fake_rows)

    client = TestClient(app)
    response = client.get("/api/team/members")

    member = response.json()["members"][0]
    assert "avatar_url" in member
    assert member["avatar_url"] is None

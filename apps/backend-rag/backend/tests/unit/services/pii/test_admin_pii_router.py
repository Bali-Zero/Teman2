"""
Unit tests for backend.app.routers.admin_pii.

We build a minimal FastAPI app, override the auth + database_pool
dependencies, and assert on the SQL parameters + response shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.deps.database import get_database_pool
from backend.app.routers.admin_pii import router as admin_pii_router
from backend.app.routers.debug import verify_debug_access


def _row(**fields):
    """Stub that behaves like an asyncpg.Record for dict(r)."""
    class _R(dict):
        def __init__(self, d):
            super().__init__(d)
    return _R(fields)


@pytest.fixture
def app_with_pool():
    app = FastAPI()
    app.include_router(admin_pii_router)

    fetch = AsyncMock()
    pool = MagicMock()
    pool.fetch = fetch

    app.dependency_overrides[get_database_pool] = lambda: pool
    app.dependency_overrides[verify_debug_access] = lambda: True

    return app, fetch


class TestListViolations:
    def test_default_since_is_24h_ago(self, app_with_pool):
        app, fetch = app_with_pool
        fetch.return_value = []
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/violations")
        assert r.status_code == 200
        # Query was called with a `since` datetime ~24h old
        args = fetch.call_args.args
        since = args[1]
        assert isinstance(since, datetime)
        age = datetime.now(timezone.utc) - since
        assert timedelta(hours=23, minutes=55) < age < timedelta(hours=24, minutes=5)

    def test_filter_by_pattern_includes_param(self, app_with_pool):
        app, fetch = app_with_pool
        fetch.return_value = []
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/violations?pattern=ID_KTP&limit=50")
        assert r.status_code == 200
        sql = fetch.call_args.args[0]
        assert "pattern_matched = $" in sql
        # Pattern value and limit appear in the positional args
        assert "ID_KTP" in fetch.call_args.args
        assert 50 in fetch.call_args.args

    def test_cursor_produces_keyset_clause(self, app_with_pool):
        app, fetch = app_with_pool
        fetch.return_value = []
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/violations?cursor=500")
        assert r.status_code == 200
        sql = fetch.call_args.args[0]
        assert "id < $" in sql

    def test_next_cursor_set_when_page_full(self, app_with_pool):
        app, fetch = app_with_pool
        # Return exactly `limit` rows → next_cursor must be last id
        fetch.return_value = [
            _row(
                id=100 - i, request_id=None, route="/x",
                pattern_matched="ID_KTP", severity="high",
                user_hash=None, occurrence_count=1,
                created_at=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/violations?limit=5")
        body = r.json()
        assert body["count"] == 5
        assert body["next_cursor"] == 96

    def test_next_cursor_null_when_partial_page(self, app_with_pool):
        app, fetch = app_with_pool
        fetch.return_value = [
            _row(
                id=7, request_id=None, route="/x",
                pattern_matched="ID_KTP", severity="high",
                user_hash=None, occurrence_count=1,
                created_at=datetime.now(timezone.utc),
            ),
        ]
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/violations?limit=50")
        body = r.json()
        assert body["count"] == 1
        assert body["next_cursor"] is None


class TestTrend:
    def test_trend_shape(self, app_with_pool):
        app, fetch = app_with_pool
        fetch.return_value = [
            _row(
                pattern_matched="ID_KTP",
                day=datetime(2026, 4, 18, tzinfo=timezone.utc),
                count=3, total_occurrences=5,
            ),
        ]
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/trend?days=7")
        assert r.status_code == 200
        body = r.json()
        assert body["days"] == 7
        assert len(body["buckets"]) == 1
        assert body["buckets"][0]["pattern_matched"] == "ID_KTP"


class TestByRoute:
    def test_route_aggregation(self, app_with_pool):
        app, fetch = app_with_pool
        fetch.return_value = [
            _row(
                route="/api/agentic/ask",
                violation_count=42, total_occurrences=99,
                distinct_patterns=3,
                last_seen=datetime.now(timezone.utc),
            ),
        ]
        with TestClient(app) as c:
            r = c.get("/api/admin/pii/by-route")
        body = r.json()
        assert body["days"] == 7  # default
        assert body["routes"][0]["route"] == "/api/agentic/ask"
        assert body["routes"][0]["violation_count"] == 42

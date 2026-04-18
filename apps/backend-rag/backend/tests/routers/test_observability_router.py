"""Tests for the admin-only RAG observability router.

Exercises RBAC + response shape with a mocked pool so the test runs without
a live Postgres instance. The real DB path is verified in
``tests/integration/test_rag_trace_integration.py``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers.observability import router as observability_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_pool(total_queries: int = 7):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={
        "total_queries": total_queries,
        "total_cost": Decimal("1.23"),
    })
    conn.fetch = AsyncMock(side_effect=[
        [
            {
                "stage": "retrieval", "samples": 7,
                "p50_ms": Decimal("10"), "p95_ms": Decimal("20"),
                "p99_ms": Decimal("30"), "cache_hit_rate": Decimal("0.5"),
                "avg_tokens_in": Decimal("5"), "avg_tokens_out": None,
            },
        ],
        [{"domain": "visa", "queries": 5, "cost_usd": Decimal("1.0")}],
    ])

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


@pytest.fixture
def app_client_factory():
    """Return a factory so each test can wire its own user stub."""

    def _factory(user: dict | None):
        app = FastAPI()
        app.include_router(observability_router)

        pool = _build_pool()
        app.dependency_overrides[get_database_pool] = lambda: pool
        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app, raise_server_exceptions=False)

    return _factory


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_rag_stats_rejects_non_admin(app_client_factory):
    client = app_client_factory({"email": "not-admin@example.com", "role": "user"})
    resp = client.get("/api/observability/rag-stats")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "admin only"


def test_rag_stats_allows_admin_by_role(app_client_factory):
    client = app_client_factory({"email": "some@example.com", "role": "admin"})
    resp = client.get("/api/observability/rag-stats")
    assert resp.status_code == 200


def test_rag_stats_allows_admin_by_email(app_client_factory, monkeypatch):
    # admin_emails_set is a property derived from .admin_emails — patch the
    # backing field (the env-driven string) so the property recomputes.
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "admin_emails", "zero@balizero.com")
    client = app_client_factory({"email": "zero@balizero.com", "role": "user"})
    resp = client.get("/api/observability/rag-stats")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Query shape
# ---------------------------------------------------------------------------


def test_rag_stats_default_window_24h(app_client_factory):
    client = app_client_factory({"email": "a@b", "role": "admin"})
    resp = client.get("/api/observability/rag-stats")
    body = resp.json()
    assert body["window_hours"] == 24
    assert body["domain_filter"] is None
    assert body["total_queries"] == 7
    assert "retrieval" in body["stages"]
    assert body["stages"]["retrieval"]["p95_ms"] == 20.0
    assert body["top_domains_by_cost"][0]["domain"] == "visa"


def test_rag_stats_custom_window_and_domain(app_client_factory):
    client = app_client_factory({"email": "a@b", "role": "admin"})
    resp = client.get("/api/observability/rag-stats?window=6&domain=tax")
    body = resp.json()
    assert body["window_hours"] == 6
    assert body["domain_filter"] == "tax"


def test_rag_stats_rejects_out_of_range_window(app_client_factory):
    client = app_client_factory({"email": "a@b", "role": "admin"})
    resp = client.get("/api/observability/rag-stats?window=0")
    assert resp.status_code == 422
    resp = client.get("/api/observability/rag-stats?window=999")
    assert resp.status_code == 422

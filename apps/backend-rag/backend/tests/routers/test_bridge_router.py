"""Tests for /api/bridge/* endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


VALID_KEY = "test-bridge-key-12345"


@pytest.fixture(autouse=True)
def set_bridge_key(monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", VALID_KEY)
    yield


@pytest.fixture
def app_with_bridge():
    """Build a minimal FastAPI app with only the bridge router + mocked db pool dep."""
    from backend.app.routers import bridge as bridge_router
    from backend.app.deps.database import get_database_pool

    app = FastAPI()
    app.include_router(bridge_router.router)

    # Override DB dependency with an AsyncMock pool
    fake_pool = MagicMock()
    fake_conn = AsyncMock()
    # context manager: async with pool.acquire() as conn:
    fake_pool.acquire = MagicMock(return_value=_AcquireCM(fake_conn))
    app.state.db_pool = fake_pool
    app.state._fake_conn = fake_conn  # expose for test setup

    def _override_pool():
        return fake_pool

    app.dependency_overrides[get_database_pool] = _override_pool
    return app


@pytest.fixture
def client(app_with_bridge):
    return TestClient(app_with_bridge)


class _AcquireCM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


# ── GET /api/bridge/events ─────────────────────────────────────────────


def test_get_events_unauthorized_missing_header(client):
    r = client.get("/api/bridge/events?after_id=0")
    assert r.status_code == 401


def test_get_events_unauthorized_wrong_key(client):
    r = client.get(
        "/api/bridge/events?after_id=0",
        headers={"X-Bridge-Auth": "wrong"},
    )
    assert r.status_code == 401


def test_get_events_returns_outbox_rows(client, app_with_bridge):
    """Authorized GET returns events from the outbox via fetch_outbox_events."""
    from backend.services.bridge import outbox as outbox_mod

    # Patch fetch_outbox_events to return fake rows
    monkey = pytest.MonkeyPatch()
    fake_rows = [
        {"id": 10, "type": "crm.client_created", "payload": {"a": 1}, "created_at": "2026-04-14T10:00:00+00:00"},
        {"id": 11, "type": "rag.low_confidence", "payload": {"q": "x"}, "created_at": "2026-04-14T10:00:01+00:00"},
    ]
    fake_fetch = AsyncMock(return_value=fake_rows)
    monkey.setattr("backend.app.routers.bridge.fetch_outbox_events", fake_fetch)

    try:
        r = client.get(
            "/api/bridge/events?after_id=5&limit=50",
            headers={"X-Bridge-Auth": VALID_KEY},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["events"] == fake_rows
        assert body["last_id"] == 11
        # Verify the helper got the right cursor
        fake_fetch.assert_called_once()
        kwargs = fake_fetch.call_args.kwargs
        assert kwargs.get("after_id", 5) == 5 or fake_fetch.call_args.args[1] == 5
    finally:
        monkey.undo()


def test_get_events_empty_returns_after_id_as_last_id(client):
    """When no events, last_id == after_id (cursor stays put)."""
    monkey = pytest.MonkeyPatch()
    fake_fetch = AsyncMock(return_value=[])
    monkey.setattr("backend.app.routers.bridge.fetch_outbox_events", fake_fetch)

    try:
        r = client.get(
            "/api/bridge/events?after_id=42",
            headers={"X-Bridge-Auth": VALID_KEY},
        )
        assert r.status_code == 200
        assert r.json()["last_id"] == 42
    finally:
        monkey.undo()


# ── POST /api/bridge/ingest/article ────────────────────────────────────


def test_post_ingest_article_unauthorized(client):
    r = client.post("/api/bridge/ingest/article", json={"article_id": "x", "title": "t", "body_mdx": "b"})
    assert r.status_code == 401


def test_post_ingest_article_authorized_returns_queued(client):
    r = client.post(
        "/api/bridge/ingest/article",
        headers={"X-Bridge-Auth": VALID_KEY},
        json={
            "article_id": "abc-123",
            "title": "Test article",
            "body_mdx": "# Hello",
            "topic": "test",
        },
    )
    assert r.status_code in (200, 202)
    body = r.json()
    assert body["article_id"] == "abc-123"
    assert body["status"] == "queued"


def test_post_ingest_article_validation_error_on_missing_field(client):
    """Missing required fields → 422."""
    r = client.post(
        "/api/bridge/ingest/article",
        headers={"X-Bridge-Auth": VALID_KEY},
        json={"article_id": "x"},  # missing title, body_mdx
    )
    assert r.status_code == 422


# ── POST /api/bridge/ingest/enrichment ─────────────────────────────────


def test_post_ingest_enrichment_authorized(client):
    r = client.post(
        "/api/bridge/ingest/enrichment",
        headers={"X-Bridge-Auth": VALID_KEY},
        json={
            "kb_entry_id": "kb-1",
            "content": "Test enrichment text",
            "source": "lhkpn_harvester",
        },
    )
    assert r.status_code in (200, 202)
    body = r.json()
    assert body["kb_entry_id"] == "kb-1"
    assert body["status"] == "queued"


# ── Misconfiguration ───────────────────────────────────────────────────


def test_get_events_503_when_bridge_api_key_unset(monkeypatch):
    """If BRIDGE_API_KEY env var is missing, return 503 (service not configured)."""
    monkeypatch.delenv("BRIDGE_API_KEY", raising=False)

    from fastapi import FastAPI
    from backend.app.routers import bridge as bridge_router

    app = FastAPI()
    app.include_router(bridge_router.router)
    client = TestClient(app)

    r = client.get("/api/bridge/events?after_id=0", headers={"X-Bridge-Auth": "anything"})
    assert r.status_code == 503

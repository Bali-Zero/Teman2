"""Auth tests for the WA Meta Inbox router (/api/wa-inbox/*).

The router uses a route-level scoped dependency (require_wa_inbox_key) that
requires the X-API-Key header to EQUAL settings.wa_inbox_api_key exactly —
least-privilege on top of the middleware. These tests assert:

  - 401 when no X-API-Key is sent
  - 401 when a wrong / generic key is sent
  - 200/ok when the exact wa-inbox key is sent
  - the public WhatsApp webhook stays reachable (not gated by wa-inbox key)

We mount the router on a bare FastAPI app and override get_database_pool, then
flip settings.wa_inbox_api_key for the duration of each test. The dependency
reads settings at call time, so patching the live settings object is enough.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.deps.database import get_database_pool
from backend.app.routers.wa_inbox import router

WA_INBOX_KEY = "wa-inbox-secret-test-key-0001"


@pytest.fixture
def mock_db_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    # No threads → empty list keeps the happy-path query trivial.
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def client(mock_db_pool: MagicMock):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return TestClient(app)


@pytest.fixture
def configured_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "wa_inbox_api_key", WA_INBOX_KEY)
    yield WA_INBOX_KEY


def test_threads_rejects_without_key(client: TestClient, configured_key: str) -> None:
    resp = client.get("/api/wa-inbox/threads")
    assert resp.status_code == 401


def test_threads_rejects_wrong_key(client: TestClient, configured_key: str) -> None:
    resp = client.get("/api/wa-inbox/threads", headers={"X-API-Key": "some-other-admin-secret"})
    assert resp.status_code == 401


def test_threads_accepts_exact_key(client: TestClient, configured_key: str) -> None:
    resp = client.get("/api/wa-inbox/threads", headers={"X-API-Key": WA_INBOX_KEY})
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "next_cursor": None}


def test_rejects_when_server_key_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If wa_inbox_api_key is None server-side, every request is denied."""
    monkeypatch.setattr(settings, "wa_inbox_api_key", None)
    resp = client.get("/api/wa-inbox/threads", headers={"X-API-Key": WA_INBOX_KEY})
    assert resp.status_code == 401


def test_send_and_takeover_also_gated(client: TestClient, configured_key: str) -> None:
    """Mutating routes must enforce the same scoped key."""
    no_key = client.post(
        "/api/wa-inbox/threads/1/send",
        json={"text": "hi", "idempotency_key": "k1"},
    )
    assert no_key.status_code == 401

    no_key_takeover = client.post("/api/wa-inbox/threads/1/takeover")
    assert no_key_takeover.status_code == 401


def test_webhook_not_gated_by_wa_inbox_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Meta WhatsApp webhook (GET verification) is a separate surface and
    must NOT require the wa-inbox key. It is gated only by the Meta verify
    token, never by settings.wa_inbox_api_key."""
    from backend.app.routers import whatsapp_chat
    from backend.app.routers.whatsapp_chat import router as wa_router

    # Pin a known verify token (the live settings object may be a MagicMock
    # when an earlier test patched the config module).
    monkeypatch.setattr(whatsapp_chat.settings, "whatsapp_verify_token", "verify-tok-xyz")

    app = FastAPI()
    app.include_router(wa_router)
    webhook_client = TestClient(app)

    # Matching token → 200 + echoed challenge. No wa-inbox key involved.
    ok = webhook_client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-tok-xyz",
            "hub.challenge": "challenge-123",
        },
    )
    assert ok.status_code == 200
    assert ok.text == "challenge-123"

    # Wrong token → 403 (Meta-token gate), NOT 401 (which would mean the
    # wa-inbox scoped dependency is leaking onto the webhook surface).
    bad = webhook_client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "WRONG",
            "hub.challenge": "challenge-123",
        },
    )
    assert bad.status_code == 403

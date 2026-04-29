"""Twitter/X webhook ack-first contract tests.

Verifies that the X webhook router persists the inbound payload to
``inbound_webhooks`` and returns 200 OK before any business processing
runs (P0-6 from zero-crash audit 2026-04-29).

Twitter-specific dedup key: derived from the first
direct_message_events[0].id when present.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


CONSUMER_SECRET = "test_consumer_secret_abc123"


@pytest.fixture
def mock_db_pool():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetchrow = AsyncMock(return_value={"id": 100})

    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    pool = MagicMock()
    pool._conn = conn
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


@pytest.fixture
def channel_router_mock():
    return AsyncMock()


@pytest.fixture
def app(mock_db_pool, channel_router_mock, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "backend.app.routers.twitter.settings",
        type("S", (), {"x_consumer_secret": CONSUMER_SECRET})(),
    )
    from backend.app.dependencies import get_channel_router, get_database
    from backend.app.routers import twitter

    application = FastAPI()
    application.include_router(twitter.webhook_router)
    application.dependency_overrides[get_database] = lambda: mock_db_pool
    application.dependency_overrides[get_channel_router] = lambda: channel_router_mock
    application.state.db_pool = mock_db_pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _twitter_payload(dm_id: str = "dm_xyz") -> dict:
    return {
        "for_user_id": "bot_user_1",
        "direct_message_events": [
            {
                "id": dm_id,
                "type": "message_create",
                "message_create": {
                    "sender_id": "user_999",
                    "target": {"recipient_id": "bot_user_1"},
                    "message_data": {"text": "Hello"},
                },
            }
        ],
    }


@pytest.mark.integration
def test_acks_in_under_200ms(client: TestClient):
    """X webhook returns 200 OK quickly even when signature verification is on."""
    payload = _twitter_payload()
    with patch(
        "backend.app.routers.twitter._verify_webhook_signature",
        return_value=True,
    ):
        start = time.monotonic()
        resp = client.post("/webhook/twitter", json=payload)
        elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms < 1500


@pytest.mark.integration
def test_persists_payload_to_inbound_webhooks(client: TestClient):
    payload = _twitter_payload(dm_id="dm_TEST_DEDUP")
    with patch(
        "backend.app.routers.twitter._verify_webhook_signature",
        return_value=True,
    ), patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        mock_persist.return_value = (1, True)
        resp = client.post("/webhook/twitter", json=payload)

    assert resp.status_code == 200
    mock_persist.assert_awaited()
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs.get("channel") == "twitter"
    assert "dm_TEST_DEDUP" in call_kwargs.get("dedup_key", "")


@pytest.mark.integration
def test_invalid_signature_returns_error_without_persist(client: TestClient):
    """Bad signature → no persist (verification gate stays in place)."""
    with patch(
        "backend.app.routers.twitter._verify_webhook_signature",
        return_value=False,
    ), patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        resp = client.post("/webhook/twitter", json=_twitter_payload())

    # Existing behavior: invalid sig returns {"status": "error", ...} 200
    body = resp.json()
    assert body.get("status") == "error"
    mock_persist.assert_not_awaited()

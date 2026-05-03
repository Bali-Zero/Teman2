"""Instagram webhook ack-first contract tests.

Verifies that the Instagram webhook router persists the inbound payload
to ``inbound_webhooks`` and returns 200 OK before any business processing
runs (P0-6 from zero-crash audit 2026-04-29).

Instagram-specific dedup key: derived from messaging[0].message.mid.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


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
def app(mock_db_pool, channel_router_mock):
    from backend.app.dependencies import get_channel_router, get_database
    from backend.app.routers import instagram_chat

    application = FastAPI()
    application.include_router(instagram_chat.webhook_router)
    application.dependency_overrides[get_database] = lambda: mock_db_pool
    application.dependency_overrides[get_channel_router] = lambda: channel_router_mock
    application.state.db_pool = mock_db_pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _ig_payload(mid: str = "ig_msg_xyz") -> dict:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": "ig_entry_1",
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": "user_1"},
                        "recipient": {"id": "page_1"},
                        "timestamp": 1700000000,
                        "message": {"mid": mid, "text": "Hello", "is_echo": False},
                    }
                ],
            }
        ],
    }


@pytest.mark.integration
def test_acks_in_under_200ms(client: TestClient):
    start = time.monotonic()
    resp = client.post("/webhook/instagram", json=_ig_payload())
    elapsed_ms = (time.monotonic() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 1500


@pytest.mark.integration
def test_persists_payload_to_inbound_webhooks(client: TestClient):
    payload = _ig_payload(mid="ig_msg_TEST_DEDUP")
    with patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        mock_persist.return_value = (1, True)
        resp = client.post("/webhook/instagram", json=payload)

    assert resp.status_code == 200
    mock_persist.assert_awaited()
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs.get("channel") == "instagram"
    assert "ig_msg_TEST_DEDUP" in call_kwargs.get("dedup_key", "")


@pytest.mark.integration
def test_echo_message_skipped_no_persist(client: TestClient):
    """Echo messages (sent by our own bot) must not be persisted."""
    payload = _ig_payload()
    payload["entry"][0]["messaging"][0]["message"]["is_echo"] = True

    with patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        resp = client.post("/webhook/instagram", json=payload)

    assert resp.status_code == 200
    mock_persist.assert_not_awaited()

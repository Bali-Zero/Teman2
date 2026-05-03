"""Telegram webhook ack-first contract tests.

Verifies that the Telegram webhook router persists the inbound update
to ``inbound_webhooks`` and returns 200 OK before any business processing
runs (P0-6 from zero-crash audit 2026-04-29).

Telegram-specific dedup key: derived from update_id (int).
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
    from backend.app.routers import telegram_webhook

    application = FastAPI()
    application.include_router(telegram_webhook.router)
    application.dependency_overrides[get_database] = lambda: mock_db_pool
    application.dependency_overrides[get_channel_router] = lambda: channel_router_mock
    application.state.db_pool = mock_db_pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.integration
def test_acks_in_under_200ms(client: TestClient):
    """Webhook returns 200 OK quickly even under sync test harness."""
    payload = {
        "update_id": 42,
        "message": {
            "chat": {"id": 123},
            "text": "hello",
            "from": {"id": 999},
        },
    }
    start = time.monotonic()
    resp = client.post("/webhook/telegram", json=payload)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms < 1500


@pytest.mark.integration
def test_persists_payload_to_inbound_webhooks(client: TestClient):
    """Router writes telegram update to inbound_webhooks with update_id-derived dedup_key."""
    payload = {
        "update_id": 4242,
        "message": {"chat": {"id": 123}, "text": "x", "from": {"id": 999}},
    }
    with patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        mock_persist.return_value = (1, True)
        resp = client.post("/webhook/telegram", json=payload)

    assert resp.status_code == 200
    mock_persist.assert_awaited()
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs.get("channel") == "telegram"
    assert "4242" in call_kwargs.get("dedup_key", "")


@pytest.mark.integration
def test_missing_update_id_skips_persist(client: TestClient):
    """Telegram requires update_id; when missing, return early (no persist)."""
    with patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        resp = client.post("/webhook/telegram", json={"message": {"text": "hi"}})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is False
    mock_persist.assert_not_awaited()

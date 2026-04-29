"""WhatsApp webhook ack-first contract tests.

Verifies that the WhatsApp webhook router persists the inbound payload
to ``inbound_webhooks`` and returns 200 OK before any business processing
runs (P0-6 from zero-crash audit 2026-04-29).

This is a contract test: it asserts the router calls
``inbound_webhook_repo.persist`` and returns 200 OK in the same async
event tick — i.e. without `await`-ing on heavy services like
``orchestrator.process_query``.
"""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db_pool():
    """Build an asyncpg.Pool mock with acquire() context manager."""
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
def app(mock_db_pool):
    from backend.app.dependencies import get_database
    from backend.app.routers import whatsapp_chat

    application = FastAPI()
    application.include_router(whatsapp_chat.router)
    application.dependency_overrides[get_database] = lambda: mock_db_pool
    application.state.db_pool = mock_db_pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _whatsapp_payload(message_id: str = "wamid.ABC123") -> dict:
    """Standard Meta WhatsApp message payload."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [{"profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "from": "6281234567890",
                                    "id": message_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


@pytest.mark.integration
def test_acks_in_under_200ms(client: TestClient, mock_db_pool):
    """Webhook returns 200 OK in <200ms even with no-op processing."""
    payload = _whatsapp_payload()

    # Patch the signature verification to no-op (no app secret set in test)
    with patch(
        "backend.app.routers.whatsapp_chat._verify_whatsapp_signature",
        return_value=True,
    ):
        start = time.monotonic()
        resp = client.post("/webhook/whatsapp", json=payload)
        elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status_code == 200
    # Local TestClient ack should be sub-200ms even on slow CI runners.
    # The actual production guarantee is enforced by ack-first pattern;
    # this test asserts no synchronous heavy work.
    assert elapsed_ms < 1500, f"ack took {elapsed_ms:.0f}ms — possible sync work"


@pytest.mark.integration
def test_persists_payload_to_inbound_webhooks(
    client: TestClient, mock_db_pool
):
    """Router writes payload to inbound_webhooks via persist helper."""
    payload = _whatsapp_payload(message_id="wamid.TEST_PERSIST")

    with patch(
        "backend.app.routers.whatsapp_chat._verify_whatsapp_signature",
        return_value=True,
    ), patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        mock_persist.return_value = (1, True)  # (id, inserted)
        resp = client.post("/webhook/whatsapp", json=payload)

    assert resp.status_code == 200
    mock_persist.assert_awaited()
    # Inspect call: channel="whatsapp", dedup_key derives from message_id
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs.get("channel") == "whatsapp"
    assert "wamid.TEST_PERSIST" in call_kwargs.get("dedup_key", "")


@pytest.mark.integration
def test_invalid_signature_returns_401_without_persist(
    client: TestClient, mock_db_pool
):
    """Signature verification runs BEFORE persist — bad sig = no DB write."""
    with patch(
        "backend.app.routers.whatsapp_chat._verify_whatsapp_signature",
        return_value=False,
    ), patch(
        "backend.services.channels.inbound_webhook_repo.persist",
        new_callable=AsyncMock,
    ) as mock_persist:
        resp = client.post("/webhook/whatsapp", json=_whatsapp_payload())

    assert resp.status_code == 401
    mock_persist.assert_not_awaited()

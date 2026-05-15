"""
Tests for the newsletter double-opt-in confirmation email (TODO #80).

The subscribe endpoint must:
- generate a confirmation_token (already done),
- now ALSO send a double-opt-in email through the internal Brevo adapter
  (``backend.app.services.internal_email.send_internal_email``) with
  the canonical from=zantara@balizero.com (set by the adapter, not by
  this caller), and a link back to /api/blog/newsletter/confirm?token=...

A new GET /api/blog/newsletter/confirm?token=X endpoint resolves the
subscriber by token alone, since the mouth frontend redirect link does
not carry the subscriberId.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.dependencies import get_database_pool
from backend.app.routers.newsletter import (
    router,
    send_confirmation_email,
)

app = FastAPI()
app.include_router(router)


def _make_pool_with_conn(conn_mock: AsyncMock) -> MagicMock:
    pool = MagicMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn_mock

        async def __aexit__(self, exc_type, exc, tb):
            return None

    pool.acquire = MagicMock(side_effect=lambda: _AcquireCtx())
    return pool


# ============================================================================
# send_confirmation_email helper
# ============================================================================


@pytest.mark.asyncio
async def test_send_confirmation_email_calls_internal_email() -> None:
    """The helper must delegate to send_internal_email so the Brevo
    sender (zantara@balizero.com) is set centrally — never re-implement
    the from-address in this module."""
    with patch(
        "backend.app.routers.newsletter.send_internal_email",
        new=AsyncMock(),
    ) as mock_sender:
        await send_confirmation_email(
            email="user@example.com",
            token="abc123-token",
        )

    assert mock_sender.await_count == 1
    kwargs = mock_sender.await_args.kwargs
    assert kwargs["to"] == "user@example.com"
    # Subject is English, mentions "confirm" or similar.
    assert "confirm" in kwargs["subject"].lower()
    # Body contains the confirm link with the token.
    assert "abc123-token" in kwargs["body"]
    assert "/api/blog/newsletter/confirm" in kwargs["body"]


@pytest.mark.asyncio
async def test_send_confirmation_email_uses_public_host_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_HOST", "https://example.org")
    with patch(
        "backend.app.routers.newsletter.send_internal_email",
        new=AsyncMock(),
    ) as mock_sender:
        await send_confirmation_email(
            email="x@y.com",
            token="tok",
        )

    body = mock_sender.await_args.kwargs["body"]
    assert "https://example.org/api/blog/newsletter/confirm?token=tok" in body


@pytest.mark.asyncio
async def test_send_confirmation_email_url_encodes_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """secrets.token_urlsafe is already URL-safe, but the link must still
    encode defensively in case the token format ever changes."""
    monkeypatch.setenv("PUBLIC_HOST", "https://x.com")
    with patch(
        "backend.app.routers.newsletter.send_internal_email",
        new=AsyncMock(),
    ) as mock_sender:
        await send_confirmation_email(email="a@b.com", token="abc/def&xyz")

    body = mock_sender.await_args.kwargs["body"]
    # Either fully URL-encoded or the link is still parseable.
    assert "abc%2Fdef%26xyz" in body or "abc/def&xyz" in body
    # And the raw `&` in the path would break URL parsing — ensure encoded.
    assert "abc%2Fdef%26xyz" in body


@pytest.mark.asyncio
async def test_send_confirmation_email_swallows_failures() -> None:
    """The send must be fire-and-forget so subscribe() still succeeds when
    Brevo is briefly unavailable. The token row already persists; admin
    can trigger a re-send via the existing resend-confirmation path."""
    mock_sender = AsyncMock(side_effect=RuntimeError("brevo down"))
    with patch(
        "backend.app.routers.newsletter.send_internal_email",
        new=mock_sender,
    ):
        # Must not raise.
        await send_confirmation_email(email="x@y.com", token="t")


# ============================================================================
# subscribe() integration
# ============================================================================


def test_subscribe_new_calls_send_confirmation_email() -> None:
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        None,  # SELECT existing → not found
        {"id": "sub-uuid-1"},  # INSERT RETURNING id
    ]
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        with patch(
            "backend.app.routers.newsletter.send_confirmation_email",
            new=AsyncMock(),
        ) as mock_send, patch(
            "backend.app.routers.newsletter.invalidate_cache",
            new=AsyncMock(),
        ):
            response = client.post(
                "/api/blog/newsletter/subscribe",
                json={
                    "email": "new@example.com",
                    "name": "Test",
                    "categories": [],
                    "frequency": "weekly",
                    "language": "en",
                },
            )

        assert response.status_code == 200
        assert mock_send.await_count == 1
        kwargs = mock_send.await_args.kwargs
        assert kwargs["email"] == "new@example.com"
        assert isinstance(kwargs["token"], str)
        assert len(kwargs["token"]) >= 30  # secrets.token_urlsafe(32) yields ~43 chars
    finally:
        app.dependency_overrides.clear()


def test_subscribe_resend_calls_send_confirmation_email() -> None:
    """Existing-but-unconfirmed subscriber path must also send the email."""
    conn = AsyncMock()
    # SELECT existing returns an unconfirmed subscriber.
    conn.fetchrow.return_value = {
        "id": "sub-uuid-2",
        "confirmed": False,
        "unsubscribed_at": None,
    }
    conn.execute = AsyncMock()
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        with patch(
            "backend.app.routers.newsletter.send_confirmation_email",
            new=AsyncMock(),
        ) as mock_send, patch(
            "backend.app.routers.newsletter.invalidate_cache",
            new=AsyncMock(),
        ):
            response = client.post(
                "/api/blog/newsletter/subscribe",
                json={
                    "email": "pending@example.com",
                    "frequency": "weekly",
                },
            )

        assert response.status_code == 200
        assert mock_send.await_count == 1
    finally:
        app.dependency_overrides.clear()


# ============================================================================
# GET /confirm endpoint (token-only lookup)
# ============================================================================


def test_confirm_via_get_resolves_token_alone() -> None:
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "sub-uuid-3",
        "email": "user@example.com",
        "confirmed": False,
    }
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        with patch(
            "backend.app.routers.newsletter.invalidate_cache",
            new=AsyncMock(),
        ):
            response = client.get(
                "/api/blog/newsletter/confirm?token=abc-token",
            )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "confirmed" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()

    # Verify the SQL hit the token-only path.
    sql_calls: list[str] = []
    for call in conn.fetchrow.await_args_list:
        # Support both positional and keyword invocation.
        if call.args:
            sql_calls.append(call.args[0])
        elif "query" in call.kwargs:
            sql_calls.append(call.kwargs["query"])
    assert any("confirmation_token = $1" in s for s in sql_calls), (
        f"expected confirmation_token = $1 in SQL calls; got {sql_calls!r}"
    )


def test_confirm_via_get_returns_404_for_invalid_token() -> None:
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        response = client.get(
            "/api/blog/newsletter/confirm?token=invalid",
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_confirm_via_get_returns_already_confirmed_when_repeated() -> None:
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "sub-uuid-4",
        "email": "u@x.com",
        "confirmed": True,
    }
    pool = _make_pool_with_conn(conn)
    app.dependency_overrides[get_database_pool] = lambda: pool
    client = TestClient(app)
    try:
        response = client.get(
            "/api/blog/newsletter/confirm?token=already-used",
        )
        assert response.status_code == 200
        assert "already" in response.json()["message"].lower()
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

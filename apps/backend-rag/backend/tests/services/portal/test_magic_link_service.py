"""Unit tests for the passwordless magic-link login service (FASE 6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal.magic_link_service import (
    MAX_LIVE_TOKENS_PER_EMAIL,
    MagicLinkService,
    _hash_token,
)


class _AsyncCtx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


def _service_with_conn(conn: AsyncMock) -> MagicLinkService:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return MagicLinkService(pool)


def _portal_user(**over: object) -> dict[str, object]:
    return {
        "id": 7,
        "email": "client@example.com",
        "full_name": "Client One",
        "name": "Client One",
        "role": "client",
        "portal_access": True,
        "active": True,
        **over,
    }


# ---------------------------------------------------------------------------
# request_magic_link
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_mints_token_for_active_portal_client() -> None:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    # 1) user lookup, then fetchval for live-count
    conn.fetchrow = AsyncMock(return_value=_portal_user())
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    result = await service.request_magic_link("Client@Example.com", created_ip="1.2.3.4")

    assert result["is_client"] is True
    assert result["token"]  # raw token returned for the email send
    # The INSERT stored the HASH, never the raw token.
    insert_args = conn.execute.call_args.args
    assert insert_args[2] == _hash_token(result["token"])  # token_hash positional ($2)
    assert result["token"] not in insert_args


@pytest.mark.asyncio
async def test_request_is_enumeration_safe_for_unknown_email() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)  # no portal user
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    result = await service.request_magic_link("nobody@example.com")

    assert result["is_client"] is False
    assert result["token"] is None
    conn.execute.assert_not_awaited()  # nothing minted


@pytest.mark.asyncio
async def test_request_rate_limits_per_email() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_portal_user())
    conn.fetchval = AsyncMock(return_value=MAX_LIVE_TOKENS_PER_EMAIL)  # at the cap
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    result = await service.request_magic_link("client@example.com")

    assert result["is_client"] is True
    assert result["token"] is None
    assert result["rate_limited"] is True
    conn.execute.assert_not_awaited()  # no new token


@pytest.mark.asyncio
async def test_request_ignores_blank_email() -> None:
    conn = AsyncMock()
    service = _service_with_conn(conn)
    result = await service.request_magic_link("   ")
    assert result["token"] is None
    assert result["is_client"] is False


# ---------------------------------------------------------------------------
# verify_magic_link
# ---------------------------------------------------------------------------


def _valid_token_row(**over: object) -> dict[str, object]:
    return {
        "id": 99,
        "email": "client@example.com",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "used_at": None,
        **over,
    }


@pytest.mark.asyncio
async def test_verify_consumes_token_and_returns_user() -> None:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    # 1) token row (FOR UPDATE), 2) portal user resolve
    conn.fetchrow = AsyncMock(side_effect=[_valid_token_row(), _portal_user()])
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    user = await service.verify_magic_link("raw-token-abc")

    assert user is not None
    assert user["email"] == "client@example.com"
    assert user["role"] == "client"
    # token marked used (single-use)
    assert "UPDATE magic_link_tokens SET used_at" in conn.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_verify_rejects_unknown_token() -> None:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    assert await service.verify_magic_link("nope") is None
    conn.execute.assert_not_awaited()  # nothing consumed


@pytest.mark.asyncio
async def test_verify_rejects_already_used_token() -> None:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    conn.fetchrow = AsyncMock(
        return_value=_valid_token_row(used_at=datetime.now(timezone.utc))
    )
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    assert await service.verify_magic_link("raw") is None
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_rejects_expired_token() -> None:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    conn.fetchrow = AsyncMock(
        return_value=_valid_token_row(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
    )
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    assert await service.verify_magic_link("raw") is None
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_rejects_when_user_no_longer_eligible() -> None:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    # valid token, but the user resolve returns None (access revoked)
    conn.fetchrow = AsyncMock(side_effect=[_valid_token_row(), None])
    conn.execute = AsyncMock()
    service = _service_with_conn(conn)

    assert await service.verify_magic_link("raw") is None
    # token still consumed (used_at marked) — a revoked link is spent, not reusable
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_verify_ignores_empty_token() -> None:
    conn = AsyncMock()
    service = _service_with_conn(conn)
    assert await service.verify_magic_link("") is None

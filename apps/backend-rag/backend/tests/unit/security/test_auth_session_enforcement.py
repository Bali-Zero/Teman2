"""Launch gate for fail-closed JWT expiry and session revocation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.requests import Request

from backend.app.auth.validation import validate_auth_token
from backend.app.core.config import settings
from backend.app.deps.auth import get_current_user
from backend.middleware.hybrid_auth import HybridAuthMiddleware
from backend.services.security.token_revocation import (
    RevocationStoreUnavailable,
    TokenRevocationService,
)


def _token(*, expired: bool = False, include_exp: bool = True) -> str:
    now = datetime.now(timezone.utc)
    expiry = now - timedelta(minutes=5) if expired else now + timedelta(minutes=30)
    claims = {
        "sub": "synthetic-user-1",
        "email": "synthetic.user@example.test",
        "role": "admin",
        "iat": now,
        "jti": "synthetic-jti-1",
        "type": "access",
    }
    if include_exp:
        claims["exp"] = expiry
    return jwt.encode(
        claims,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _request(*, authorization: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/protected",
            "headers": headers,
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
        }
    )


def test_session_security_is_enforced_by_default() -> None:
    assert settings.jwt_enforce_expiry is True
    assert settings.enable_token_revocation is True


def test_expired_header_token_is_rejected_by_dependency_without_feature_flag() -> None:
    credentials = MagicMock(credentials=_token(expired=True))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request(), credentials)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_is_rejected_by_unified_validation_without_feature_flag() -> None:
    assert await validate_auth_token(_token(expired=True)) is None


@pytest.mark.asyncio
async def test_access_token_without_exp_is_rejected_by_unified_validation() -> None:
    assert await validate_auth_token(_token(include_exp=False)) is None


@pytest.mark.parametrize("transport", ["header", "cookie"])
@pytest.mark.asyncio
async def test_expired_token_is_rejected_by_middleware_for_header_and_cookie(
    transport: str,
) -> None:
    middleware = HybridAuthMiddleware(MagicMock())
    token = _token(expired=True)

    if transport == "header":
        result = await middleware.authenticate_jwt(_request(authorization=f"Bearer {token}"))
    else:
        result = await middleware.authenticate_jwt_token(token)

    assert result is None


@pytest.mark.parametrize("transport", ["header", "cookie"])
@pytest.mark.asyncio
async def test_access_token_without_exp_is_rejected_by_middleware(
    transport: str,
) -> None:
    middleware = HybridAuthMiddleware(MagicMock())
    token = _token(include_exp=False)

    if transport == "header":
        result = await middleware.authenticate_jwt(_request(authorization=f"Bearer {token}"))
    else:
        result = await middleware.authenticate_jwt_token(token)

    assert result is None


def test_access_token_without_exp_is_rejected_by_dependency() -> None:
    credentials = MagicMock(credentials=_token(include_exp=False))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(_request(), credentials)

    assert exc_info.value.status_code == 401


@pytest.mark.parametrize("transport", ["header", "cookie"])
@pytest.mark.parametrize("revoked_scope", ["token", "user"])
@pytest.mark.asyncio
async def test_revoked_session_is_rejected_for_header_and_cookie(
    transport: str,
    revoked_scope: str,
) -> None:
    redis_client = MagicMock()

    async def exists(key: str) -> int:
        if revoked_scope == "token":
            return int(key == "revoked:synthetic-jti-1")
        return int(key == "revoked_user:synthetic.user@example.test")

    redis_client.exists = AsyncMock(side_effect=exists)
    redis_manager = MagicMock()
    redis_manager.get_async_client.return_value = redis_client
    middleware = HybridAuthMiddleware(MagicMock())
    token = _token()

    with patch(
        "backend.core.redis_manager.RedisManager.get_instance",
        return_value=redis_manager,
    ):
        if transport == "header":
            result = await middleware.authenticate_jwt(_request(authorization=f"Bearer {token}"))
        else:
            result = await middleware.authenticate_jwt_token(token)

    assert result is None


@pytest.mark.asyncio
async def test_revocation_lookup_fails_closed_when_store_is_unavailable() -> None:
    service = TokenRevocationService(redis_client=None)

    with pytest.raises(RuntimeError):
        await service.is_revoked("synthetic-jti-1")


@pytest.mark.parametrize("transport", ["header", "cookie"])
@pytest.mark.asyncio
async def test_middleware_fails_closed_when_revocation_store_is_unavailable(
    transport: str,
) -> None:
    redis_manager = MagicMock()
    redis_manager.get_async_client.return_value = None
    middleware = HybridAuthMiddleware(MagicMock())
    token = _token()

    with (
        patch(
            "backend.core.redis_manager.RedisManager.get_instance",
            return_value=redis_manager,
        ),
        pytest.raises(RevocationStoreUnavailable),
    ):
        if transport == "header":
            await middleware.authenticate_jwt(_request(authorization=f"Bearer {token}"))
        else:
            await middleware.authenticate_jwt_token(token)


@pytest.mark.asyncio
async def test_revocation_outage_returns_sanitized_503_at_middleware_boundary() -> None:
    redis_manager = MagicMock()
    redis_manager.get_async_client.return_value = None
    middleware = HybridAuthMiddleware(MagicMock())
    call_next = AsyncMock()
    request = _request(authorization=f"Bearer {_token()}")

    with patch(
        "backend.core.redis_manager.RedisManager.get_instance",
        return_value=redis_manager,
    ):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 503
    assert b"Authentication service temporarily unavailable" in response.body
    assert b"RevocationStoreUnavailable" not in response.body
    assert b"error_type" not in response.body
    call_next.assert_not_awaited()


@pytest.mark.parametrize("revoked_scope", ["token", "user"])
def test_dependency_rejects_revoked_header_session(revoked_scope: str) -> None:
    redis_client = MagicMock()

    def exists(key: str) -> int:
        if revoked_scope == "token":
            return int(key == "revoked:synthetic-jti-1")
        return int(key == "revoked_user:synthetic.user@example.test")

    redis_client.exists.side_effect = exists
    redis_manager = MagicMock()
    redis_manager.get_sync_client.return_value = redis_client
    credentials = MagicMock(credentials=_token())

    with (
        patch(
            "backend.core.redis_manager.RedisManager.get_instance",
            return_value=redis_manager,
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        get_current_user(_request(), credentials)

    assert exc_info.value.status_code == 401

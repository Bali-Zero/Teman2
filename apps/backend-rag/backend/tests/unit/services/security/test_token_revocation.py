"""Tests for Redis-backed token revocation — S03 Sprint 2."""

from unittest.mock import AsyncMock

import pytest


class TestTokenRevocationService:
    """Test token revocation via Redis."""

    @pytest.mark.asyncio
    async def test_revoke_token_sets_redis_key(self):
        from backend.services.security.token_revocation import TokenRevocationService
        mock_redis = AsyncMock()
        svc = TokenRevocationService(redis_client=mock_redis)
        await svc.revoke_token("jti-123", ttl_seconds=3600, reason="logout")
        mock_redis.setex.assert_called_once_with("revoked:jti-123", 3600, "logout")

    @pytest.mark.asyncio
    async def test_is_revoked_returns_true_for_revoked_token(self):
        from backend.services.security.token_revocation import TokenRevocationService
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_revoked("jti-123")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_revoked_returns_false_for_valid_token(self):
        from backend.services.security.token_revocation import TokenRevocationService
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_revoked("jti-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_sets_user_key(self):
        from backend.services.security.token_revocation import TokenRevocationService
        mock_redis = AsyncMock()
        svc = TokenRevocationService(redis_client=mock_redis)
        await svc.revoke_all_user_tokens("user@balizero.com", reason="password_change")
        mock_redis.setex.assert_called_once_with("revoked_user:user@balizero.com", 86400, "password_change")

    @pytest.mark.asyncio
    async def test_is_user_revoked_checks_user_key(self):
        from backend.services.security.token_revocation import TokenRevocationService
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_user_revoked("user@balizero.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_graceful_on_redis_unavailable(self):
        from backend.services.security.token_revocation import TokenRevocationService
        svc = TokenRevocationService(redis_client=None)
        result = await svc.is_revoked("jti-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_graceful_on_redis_error(self):
        from backend.services.security.token_revocation import TokenRevocationService
        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = ConnectionError("Redis down")
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_revoked("jti-123")
        assert result is False

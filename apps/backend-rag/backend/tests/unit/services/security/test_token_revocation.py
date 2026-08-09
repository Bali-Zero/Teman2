"""Tests for Redis-backed token revocation — S03 Sprint 2."""

from unittest.mock import AsyncMock, patch

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
        with patch(
            "backend.services.security.token_revocation.time.time",
            return_value=1_700_000_000.125,
        ):
            await svc.revoke_all_user_tokens(
                "User@BaliZero.com", reason="password_change"
            )
        mock_redis.setex.assert_called_once_with(
            "revoked_user:user@balizero.com", 86400, "1700000000.125"
        )

    @pytest.mark.asyncio
    async def test_is_user_revoked_rejects_token_issued_before_marker(self):
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"1700000000.125"
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_user_revoked("User@BaliZero.com", 1_699_999_999.9)
        assert result is True
        mock_redis.get.assert_awaited_once_with("revoked_user:user@balizero.com")

    @pytest.mark.asyncio
    async def test_is_user_revoked_accepts_new_login_after_marker(self):
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.get.return_value = "1700000000.125"
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_user_revoked("User@BaliZero.com", 1_700_000_000.25)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_user_revoked_accepts_when_marker_is_absent(self):
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        svc = TokenRevocationService(redis_client=mock_redis)
        result = await svc.is_user_revoked("User@BaliZero.com", 1_700_000_000.25)
        assert result is False

    @pytest.mark.parametrize(
        ("token_issued_at", "revoked_at"),
        [
            (None, "1700000000.125"),
            ("not-a-timestamp", "1700000000.125"),
            (1_700_000_000.25, "corrupt-marker"),
            (float("nan"), "1700000000.125"),
        ],
    )
    @pytest.mark.asyncio
    async def test_is_user_revoked_fails_closed_on_invalid_timestamp_state(
        self,
        token_issued_at: object,
        revoked_at: object,
    ) -> None:
        from backend.services.security.token_revocation import TokenRevocationService

        mock_redis = AsyncMock()
        mock_redis.get.return_value = revoked_at
        svc = TokenRevocationService(redis_client=mock_redis)
        assert await svc.is_user_revoked("User@BaliZero.com", token_issued_at) is True

    @pytest.mark.asyncio
    async def test_fails_closed_on_redis_unavailable(self):
        from backend.services.security.token_revocation import (
            RevocationStoreUnavailable,
            TokenRevocationService,
        )

        svc = TokenRevocationService(redis_client=None)
        with pytest.raises(RevocationStoreUnavailable):
            await svc.is_revoked("jti-123")

    @pytest.mark.asyncio
    async def test_fails_closed_on_redis_error(self):
        from backend.services.security.token_revocation import (
            RevocationStoreUnavailable,
            TokenRevocationService,
        )

        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = ConnectionError("Redis down")
        svc = TokenRevocationService(redis_client=mock_redis)
        with pytest.raises(RevocationStoreUnavailable):
            await svc.is_revoked("jti-123")

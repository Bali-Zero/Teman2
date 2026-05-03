"""Tests for brute force detection — S03 Sprint 3."""

from unittest.mock import AsyncMock

import pytest


class TestBruteForceDetection:

    @pytest.mark.asyncio
    async def test_record_failure_increments_counter(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis)
        await detector.record_failure("1.2.3.4", "user@test.com")
        mock_redis.incr.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_blocked_false_under_threshold(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        detector = BruteForceDetector(redis_client=mock_redis)
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is False

    @pytest.mark.asyncio
    async def test_is_blocked_true_when_blocked(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        detector = BruteForceDetector(redis_client=mock_redis)
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is True

    @pytest.mark.asyncio
    async def test_blocks_after_threshold(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=6)
        mock_redis.expire = AsyncMock()
        mock_redis.setex = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis, max_failures=5)
        await detector.record_failure("1.2.3.4", "u@t.com")
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_redis_unavailable(self):
        from backend.services.security.brute_force import BruteForceDetector
        detector = BruteForceDetector(redis_client=None)
        assert await detector.is_blocked("1.2.3.4", "u@t.com") is False

    @pytest.mark.asyncio
    async def test_clear_on_success(self):
        from backend.services.security.brute_force import BruteForceDetector
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        detector = BruteForceDetector(redis_client=mock_redis)
        await detector.clear_on_success("1.2.3.4", "u@t.com")
        mock_redis.delete.assert_called()

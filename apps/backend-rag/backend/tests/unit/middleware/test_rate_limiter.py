"""Tests for Rate Limiter — fail-safe fallback on Redis error."""
import pytest
from unittest.mock import MagicMock
from backend.middleware.rate_limiter import RateLimiter, _rate_limit_storage


class TestRateLimiterFailSafe:
    def setup_method(self):
        _rate_limit_storage.clear()

    def test_in_memory_fallback_on_redis_error(self):
        limiter = RateLimiter()
        limiter.redis_available = True
        limiter.redis_client = MagicMock()
        limiter.redis_client.pipeline.side_effect = Exception("Redis down")
        allowed, info = limiter.is_allowed("test:key", limit=100, window=60)
        assert allowed is True
        assert info["limit"] == 50

    def test_fallback_enforces_halved_limit(self):
        limiter = RateLimiter()
        limiter.redis_available = True
        limiter.redis_client = MagicMock()
        limiter.redis_client.pipeline.side_effect = Exception("Redis down")
        for _ in range(5):
            limiter.is_allowed("test:flood", limit=10, window=60)
        allowed, _ = limiter.is_allowed("test:flood", limit=10, window=60)
        assert allowed is False

    def test_normal_redis_uses_full_limit(self):
        limiter = RateLimiter()
        limiter.redis_available = True
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None, 3, True, True]
        limiter.redis_client = MagicMock()
        limiter.redis_client.pipeline.return_value = mock_pipe
        allowed, info = limiter.is_allowed("test:ok", limit=100, window=60)
        assert allowed is True
        assert info["limit"] == 100

    def test_no_redis_uses_memory(self):
        limiter = RateLimiter()
        limiter.redis_available = False
        limiter.redis_client = None
        allowed, info = limiter.is_allowed("test:mem", limit=50, window=60)
        assert allowed is True
        assert info["limit"] == 50

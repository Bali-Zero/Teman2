"""
Comprehensive tests for backend/middleware/rate_limiter.py.

Tests cover:
- RateLimiter class
- In-memory rate limiting
- Redis rate limiting (mocked)
- Rate limit middleware
"""

from unittest.mock import MagicMock, patch

from backend.middleware.rate_limiter import RateLimiter, _rate_limit_storage


class TestRateLimiterInMemory:
    """Tests for RateLimiter with in-memory storage."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        _rate_limit_storage.clear()

    @patch("backend.app.core.config.settings")
    def test_init_without_redis(self, mock_settings: MagicMock) -> None:
        """Test initialization without Redis."""
        mock_settings.redis_url = None

        limiter = RateLimiter()

        assert limiter.redis_available is False
        assert limiter.redis_client is None

    @patch("backend.app.core.config.settings")
    def test_is_allowed_first_request(self, mock_settings: MagicMock) -> None:
        """Test first request is always allowed."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        allowed, info = limiter.is_allowed("test_key", limit=10, window=60)

        assert allowed is True
        assert info["limit"] == 10
        assert info["remaining"] >= 0

    @patch("backend.app.core.config.settings")
    def test_is_allowed_under_limit(self, mock_settings: MagicMock) -> None:
        """Test requests under limit are allowed."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        for i in range(5):
            allowed, info = limiter.is_allowed("test_key", limit=10, window=60)
            assert allowed is True

    @patch("backend.app.core.config.settings")
    def test_is_allowed_at_limit(self, mock_settings: MagicMock) -> None:
        """Test request at limit is rejected."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        # Make requests up to limit
        for i in range(10):
            limiter.is_allowed("limit_test_key", limit=10, window=60)

        # Next request should be blocked
        allowed, info = limiter.is_allowed("limit_test_key", limit=10, window=60)
        assert allowed is False

    @patch("backend.app.core.config.settings")
    def test_different_keys_independent(self, mock_settings: MagicMock) -> None:
        """Test different keys have independent limits."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        # Max out key1
        for i in range(10):
            limiter.is_allowed("key1", limit=10, window=60)

        # key2 should still be allowed
        allowed, info = limiter.is_allowed("key2", limit=10, window=60)
        assert allowed is True

    @patch("backend.app.core.config.settings")
    def test_info_contains_required_fields(self, mock_settings: MagicMock) -> None:
        """Test info dict contains required fields."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        allowed, info = limiter.is_allowed("info_test", limit=100, window=60)

        assert "limit" in info
        assert "remaining" in info
        assert "reset" in info
        assert info["limit"] == 100

    @patch("backend.app.core.config.settings")
    def test_remaining_decreases(self, mock_settings: MagicMock) -> None:
        """Test remaining count decreases with each request."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        _, info1 = limiter.is_allowed("decr_test", limit=10, window=60)
        _, info2 = limiter.is_allowed("decr_test", limit=10, window=60)

        assert info2["remaining"] < info1["remaining"]


class TestRateLimiterWithRedis:
    """Tests for RateLimiter with Redis (mocked)."""

    @patch("redis.from_url")
    @patch("backend.app.core.config.settings")
    def test_init_with_redis(
        self, mock_settings: MagicMock, mock_redis_from_url: MagicMock
    ) -> None:
        """Test initialization with Redis."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_redis_from_url.return_value = mock_client

        limiter = RateLimiter()

        mock_redis_from_url.assert_called_once()
        mock_client.ping.assert_called_once()
        assert limiter.redis_available is True

    @patch("redis.from_url")
    @patch("backend.app.core.config.settings")
    def test_redis_failure_falls_back_to_memory(
        self, mock_settings: MagicMock, mock_redis_from_url: MagicMock
    ) -> None:
        """Test fallback to memory when Redis fails."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_redis_from_url.side_effect = Exception("Connection failed")

        limiter = RateLimiter()

        assert limiter.redis_available is False

    @patch("redis.from_url")
    @patch("backend.app.core.config.settings")
    def test_is_allowed_with_redis(
        self, mock_settings: MagicMock, mock_redis_from_url: MagicMock
    ) -> None:
        """Test is_allowed with Redis backend."""
        mock_settings.redis_url = "redis://localhost:6379"
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None, 5, None, None]  # count = 5
        mock_client.pipeline.return_value = mock_pipe
        mock_redis_from_url.return_value = mock_client

        limiter = RateLimiter()
        allowed, info = limiter.is_allowed("redis_test", limit=10, window=60)

        assert allowed is True
        assert info["remaining"] == 4  # 10 - 5 - 1


class TestRateLimiterEdgeCases:
    """Edge case tests for RateLimiter."""

    @patch("backend.app.core.config.settings")
    def test_zero_limit(self, mock_settings: MagicMock) -> None:
        """Test with zero limit."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        allowed, info = limiter.is_allowed("zero_limit", limit=0, window=60)
        assert allowed is False

    @patch("backend.app.core.config.settings")
    def test_very_short_window(self, mock_settings: MagicMock) -> None:
        """Test with very short window."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        allowed, info = limiter.is_allowed("short_window", limit=100, window=1)
        assert allowed is True

    @patch("backend.app.core.config.settings")
    def test_empty_key(self, mock_settings: MagicMock) -> None:
        """Test with empty key."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        allowed, info = limiter.is_allowed("", limit=10, window=60)
        assert allowed is True  # Empty key should still work

    @patch("backend.app.core.config.settings")
    def test_special_characters_in_key(self, mock_settings: MagicMock) -> None:
        """Test with special characters in key."""
        mock_settings.redis_url = None
        limiter = RateLimiter()

        allowed, info = limiter.is_allowed("user@email.com:192.168.1.1", limit=10, window=60)
        assert allowed is True

"""
Unit tests for middleware/rate_limiter.py
Target: >95% coverage
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.rate_limiter import RateLimiter, RateLimitMiddleware, get_rate_limit_stats


class TestRateLimiter:
    """Tests for RateLimiter"""

    def test_init_with_redis(self):
        """Test RateLimiter initialization with Redis"""
        with patch("middleware.rate_limiter.redis") as mock_redis, \
             patch("middleware.rate_limiter.settings") as mock_settings:

            mock_settings.redis_url = "redis://localhost:6379"
            mock_redis_client = MagicMock()
            mock_redis_client.ping.return_value = True
            mock_redis.from_url.return_value = mock_redis_client

            limiter = RateLimiter()

            assert limiter.redis_available is True
            assert limiter.redis_client == mock_redis_client

    def test_init_without_redis(self):
        """Test RateLimiter initialization without Redis"""
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = None

            limiter = RateLimiter()

            assert limiter.redis_available is False
            assert limiter.redis_client is None

    def test_init_redis_connection_failure(self):
        """Test RateLimiter initialization with Redis connection failure"""
        with patch("middleware.rate_limiter.redis") as mock_redis, \
             patch("middleware.rate_limiter.settings") as mock_settings:

            mock_settings.redis_url = "redis://localhost:6379"
            mock_redis.from_url.side_effect = Exception("Connection failed")

            limiter = RateLimiter()

            assert limiter.redis_available is False

    def test_is_allowed_redis_success(self):
        """Test rate limit check with Redis (allowed)"""
        with patch("middleware.rate_limiter.redis") as mock_redis, \
             patch("middleware.rate_limiter.settings") as mock_settings:

            mock_settings.redis_url = "redis://localhost:6379"
            mock_redis_client = MagicMock()
            mock_redis_client.ping.return_value = True
            mock_redis.from_url.return_value = mock_redis_client

            limiter = RateLimiter()

            # Mock pipeline results
            mock_pipe = MagicMock()
            mock_pipe.execute.return_value = [None, 5]  # count = 5
            mock_redis_client.pipeline.return_value = mock_pipe

            allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            assert allowed is True
            assert info["limit"] == 10
            assert info["remaining"] == 4

    def test_is_allowed_redis_exceeded(self):
        """Test rate limit check with Redis (exceeded)"""
        with patch("middleware.rate_limiter.redis") as mock_redis, \
             patch("middleware.rate_limiter.settings") as mock_settings:

            mock_settings.redis_url = "redis://localhost:6379"
            mock_redis_client = MagicMock()
            mock_redis_client.ping.return_value = True
            mock_redis.from_url.return_value = mock_redis_client

            limiter = RateLimiter()

            # Mock pipeline results - count exceeds limit
            mock_pipe = MagicMock()
            mock_pipe.execute.return_value = [None, 10]  # count = 10, limit = 10
            mock_redis_client.pipeline.return_value = mock_pipe

            allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            assert allowed is False

    def test_is_allowed_memory_success(self):
        """Test rate limit check with memory (allowed)"""
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = None

            limiter = RateLimiter()

            # First request should be allowed
            allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            assert allowed is True
            assert info["limit"] == 10
            assert info["remaining"] == 9

    def test_is_allowed_memory_exceeded(self):
        """Test rate limit check with memory (exceeded)"""
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = None

            limiter = RateLimiter()

            # Make requests up to limit
            for i in range(10):
                allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            # Next request should be denied
            allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            assert allowed is False

    def test_is_allowed_memory_window_expiry(self):
        """Test rate limit check with memory window expiry"""
        with patch("middleware.rate_limiter.settings") as mock_settings, \
             patch("middleware.rate_limiter.time") as mock_time:

            mock_settings.redis_url = None

            limiter = RateLimiter()

            # Set initial time
            mock_time.time.return_value = 1000

            # Make requests up to limit
            for i in range(10):
                allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            # Advance time beyond window
            mock_time.time.return_value = 1070  # 70 seconds later

            # Should be allowed again
            allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

            assert allowed is True

    def test_is_allowed_error_fail_open(self):
        """Test rate limit check error handling (fail open)"""
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = None

            limiter = RateLimiter()

            # Force error by using invalid key type
            with patch.object(limiter, 'redis_available', True):
                limiter.redis_client = MagicMock()
                limiter.redis_client.pipeline.side_effect = Exception("Redis error")

                allowed, info = limiter.is_allowed("test-key", limit=10, window=60)

                # Should fail open (allow request)
                assert allowed is True


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware"""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app"""
        app = MagicMock()
        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance"""
        return RateLimitMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_dispatch_health_check_skip(self, middleware):
        """Test that health checks are skipped"""
        mock_request = MagicMock()
        mock_request.url.path = "/health"

        mock_response = MagicMock()

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response

    @pytest.mark.asyncio
    async def test_dispatch_allowed(self, middleware):
        """Test dispatch with allowed request"""
        mock_request = MagicMock()
        mock_request.url.path = "/api/test"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = None

        mock_response = MagicMock()
        mock_response.headers = {}

        async def call_next(request):
            return mock_response

        with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (True, {
                "limit": 100,
                "remaining": 99,
                "reset": int(time.time()) + 60
            })

            result = await middleware.dispatch(mock_request, call_next)

            assert result == mock_response
            assert "X-RateLimit-Limit" in result.headers
            assert "X-RateLimit-Remaining" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_rate_limit_exceeded(self, middleware):
        """Test dispatch with rate limit exceeded"""
        mock_request = MagicMock()
        mock_request.url.path = "/api/test"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = None

        async def call_next(request):
            return MagicMock()

        with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (False, {
                "limit": 100,
                "remaining": 0,
                "reset": int(time.time()) + 60
            })

            result = await middleware.dispatch(mock_request, call_next)

            assert result.status_code == 429
            assert "Rate limit exceeded" in result.body.decode()

    def test_get_rate_limit_exact_match(self, middleware):
        """Test getting rate limit with exact match"""
        limit, window = middleware._get_rate_limit("/api/agents/journey/create")
        assert limit == 10
        assert window == 3600

    def test_get_rate_limit_prefix_match(self, middleware):
        """Test getting rate limit with prefix match"""
        limit, window = middleware._get_rate_limit("/api/agents/journey/status")
        assert limit == 60
        assert window == 60

    def test_get_rate_limit_default(self, middleware):
        """Test getting default rate limit"""
        limit, window = middleware._get_rate_limit("/unknown/path")
        assert limit == 200
        assert window == 60


class TestRateLimitStats:
    """Tests for rate limit statistics"""

    def test_get_rate_limit_stats_with_redis(self):
        """Test getting stats with Redis"""
        with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
            mock_limiter.redis_available = True

            stats = get_rate_limit_stats()

            assert stats["backend"] == "redis"
            assert stats["connected"] is True

    def test_get_rate_limit_stats_without_redis(self):
        """Test getting stats without Redis"""
        with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
            mock_limiter.redis_available = False

            stats = get_rate_limit_stats()

            assert stats["backend"] == "memory"
            assert stats["connected"] is False





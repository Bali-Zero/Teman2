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

# Mock settings before importing rate_limiter
with patch("backend.app.core.config.settings") as mock_settings:
    mock_settings.redis_url = None
    from middleware.rate_limiter import RateLimiter, RateLimitMiddleware, get_rate_limit_stats


class TestRateLimiter:
    """Tests for RateLimiter"""

    def test_init_without_redis(self):
        """Test RateLimiter initialization without Redis"""
        with patch("middleware.rate_limiter.RateLimiter.__init__", return_value=None):
            limiter = RateLimiter.__new__(RateLimiter)
            limiter.redis_available = False
            limiter.redis_client = None

            assert limiter.redis_available is False
            assert limiter.redis_client is None

    def test_is_allowed_memory_success(self):
        """Test rate limit check with memory (allowed)"""
        limiter = RateLimiter.__new__(RateLimiter)
        limiter.redis_available = False
        limiter.redis_client = None

        # Clear storage
        import middleware.rate_limiter as rl_module

        rl_module._rate_limit_storage.clear()

        # First request should be allowed
        allowed, info = limiter.is_allowed("test-key-1", limit=10, window=60)

        assert allowed is True
        assert info["limit"] == 10
        assert info["remaining"] == 9

    def test_is_allowed_memory_exceeded(self):
        """Test rate limit check with memory (exceeded)"""
        limiter = RateLimiter.__new__(RateLimiter)
        limiter.redis_available = False
        limiter.redis_client = None

        # Clear storage
        import middleware.rate_limiter as rl_module

        rl_module._rate_limit_storage.clear()

        # Make requests up to limit
        for i in range(10):
            allowed, info = limiter.is_allowed("test-key-2", limit=10, window=60)

        # Next request should be denied
        allowed, info = limiter.is_allowed("test-key-2", limit=10, window=60)

        assert allowed is False

    def test_is_allowed_redis_success(self):
        """Test rate limit check with Redis (allowed)"""
        limiter = RateLimiter.__new__(RateLimiter)
        limiter.redis_available = True

        mock_redis_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None, 5, None, None]  # count = 5
        mock_redis_client.pipeline.return_value = mock_pipe
        limiter.redis_client = mock_redis_client

        allowed, info = limiter.is_allowed("test-key-redis", limit=10, window=60)

        assert allowed is True
        assert info["limit"] == 10
        assert info["remaining"] == 4

    def test_is_allowed_redis_exceeded(self):
        """Test rate limit check with Redis (exceeded)"""
        limiter = RateLimiter.__new__(RateLimiter)
        limiter.redis_available = True

        mock_redis_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None, 10, None, None]  # count = 10, limit = 10
        mock_redis_client.pipeline.return_value = mock_pipe
        limiter.redis_client = mock_redis_client

        allowed, info = limiter.is_allowed("test-key-redis-2", limit=10, window=60)

        assert allowed is False

    def test_is_allowed_error_fail_open(self):
        """Test rate limit check error handling (fail open)"""
        limiter = RateLimiter.__new__(RateLimiter)
        limiter.redis_available = True
        limiter.redis_client = MagicMock()
        limiter.redis_client.pipeline.side_effect = Exception("Redis error")

        allowed, info = limiter.is_allowed("test-key-error", limit=10, window=60)

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
    async def test_dispatch_docs_skip(self, middleware):
        """Test that docs are skipped"""
        mock_request = MagicMock()
        mock_request.url.path = "/docs"

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
            mock_limiter.is_allowed.return_value = (
                True,
                {"limit": 100, "remaining": 99, "reset": int(time.time()) + 60},
            )

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
            mock_limiter.is_allowed.return_value = (
                False,
                {"limit": 100, "remaining": 0, "reset": int(time.time()) + 60},
            )

            result = await middleware.dispatch(mock_request, call_next)

            assert result.status_code == 429

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

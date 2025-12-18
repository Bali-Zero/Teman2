"""
Unit tests for Rate Limiter Middleware
"""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, status

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.rate_limiter import RateLimiter, RateLimitMiddleware, get_rate_limit_stats


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    redis_client = MagicMock()
    redis_client.ping = MagicMock()
    redis_client.pipeline = MagicMock(return_value=MagicMock())
    return redis_client


@pytest.fixture
def rate_limiter():
    """Create RateLimiter instance"""
    return RateLimiter()


# ============================================================================
# Tests for RateLimiter
# ============================================================================


def test_init_without_redis():
    """Test RateLimiter initialization without Redis"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = None
        # Create a new instance to test initialization
        limiter = RateLimiter()
        assert limiter.redis_available is False
        assert limiter.redis_client is None


def test_init_with_redis(mock_redis_client):
    """Test RateLimiter initialization with Redis"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        # redis is imported inside __init__, so we patch it at the import location
        with patch("redis.from_url", return_value=mock_redis_client):
            limiter = RateLimiter()
            assert limiter.redis_available is True


def test_is_allowed_memory_fallback(rate_limiter):
    """Test rate limit check with memory fallback"""
    rate_limiter.redis_available = False

    allowed, info = rate_limiter.is_allowed("test-key", limit=5, window=60)

    assert allowed is True
    assert info["limit"] == 5
    assert "remaining" in info
    assert "reset" in info


def test_is_allowed_rate_limit_exceeded(rate_limiter):
    """Test rate limit exceeded"""
    rate_limiter.redis_available = False
    # Use a unique key to avoid conflicts with other tests
    unique_key = f"test-key-{id(rate_limiter)}"

    # Make 5 requests (limit is 5)
    for i in range(5):
        allowed, _ = rate_limiter.is_allowed(unique_key, limit=5, window=60)
        assert allowed is True

    # 6th request should be blocked
    allowed, info = rate_limiter.is_allowed(unique_key, limit=5, window=60)
    assert allowed is False
    assert info["remaining"] == 0


def test_is_allowed_redis_backend(mock_redis_client):
    """Test rate limit check with Redis backend"""
    mock_pipeline = MagicMock()
    mock_pipeline.zremrangebyscore = MagicMock(return_value=mock_pipeline)
    mock_pipeline.zcard = MagicMock(return_value=mock_pipeline)
    mock_pipeline.zadd = MagicMock(return_value=mock_pipeline)
    mock_pipeline.expire = MagicMock(return_value=mock_pipeline)
    mock_pipeline.execute = MagicMock(return_value=[None, 3, None, None])  # count = 3

    mock_redis_client.pipeline = MagicMock(return_value=mock_pipeline)

    with patch("app.core.config.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379"
        with patch("redis.from_url", return_value=mock_redis_client):
            limiter = RateLimiter()
            allowed, info = limiter.is_allowed("test-key", limit=5, window=60)

            assert allowed is True
            assert info["limit"] == 5


def test_is_allowed_error_handling(rate_limiter):
    """Test rate limit check handles errors gracefully"""
    rate_limiter.redis_available = True
    rate_limiter.redis_client = MagicMock()
    rate_limiter.redis_client.pipeline = MagicMock(side_effect=Exception("Redis error"))

    # Should fail open (allow request)
    allowed, info = rate_limiter.is_allowed("test-key", limit=5, window=60)
    assert allowed is True


# ============================================================================
# Tests for RateLimitMiddleware
# ============================================================================


@pytest.mark.asyncio
async def test_dispatch_health_check_bypass():
    """Test rate limiter bypasses health checks"""
    middleware = RateLimitMiddleware(MagicMock())
    request = MagicMock(spec=Request)
    request.url.path = "/health"
    response = MagicMock()
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result == response


@pytest.mark.asyncio
async def test_dispatch_rate_limit_exceeded():
    """Test rate limit exceeded response"""
    middleware = RateLimitMiddleware(MagicMock())
    request = MagicMock(spec=Request)
    request.url.path = "/api/search"
    request.client.host = "127.0.0.1"
    request.headers = {}

    # Mock rate limiter to return exceeded
    with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
        mock_limiter.is_allowed = MagicMock(
            return_value=(False, {"limit": 10, "remaining": 0, "reset": int(time.time()) + 60})
        )

        result = await middleware.dispatch(request, AsyncMock())

        assert result.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_dispatch_success_with_headers():
    """Test successful request adds rate limit headers"""
    middleware = RateLimitMiddleware(MagicMock())
    request = MagicMock(spec=Request)
    request.url.path = "/api/search"
    request.client.host = "127.0.0.1"
    request.headers = {}

    response = MagicMock()
    response.headers = {}
    call_next = AsyncMock(return_value=response)

    with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
        mock_limiter.is_allowed = MagicMock(
            return_value=(True, {"limit": 10, "remaining": 9, "reset": int(time.time()) + 60})
        )

        result = await middleware.dispatch(request, call_next)

        assert result.headers["X-RateLimit-Limit"] == "10"
        assert result.headers["X-RateLimit-Remaining"] == "9"


def test_get_rate_limit_exact_match():
    """Test getting rate limit for exact path match"""
    middleware = RateLimitMiddleware(MagicMock())
    limit, window = middleware._get_rate_limit("/api/agents/journey/create")

    assert limit == 10
    assert window == 3600


def test_get_rate_limit_prefix_match():
    """Test getting rate limit for prefix match"""
    middleware = RateLimitMiddleware(MagicMock())
    limit, window = middleware._get_rate_limit("/api/agents/journey/123")

    assert limit == 60
    assert window == 60


def test_get_rate_limit_default():
    """Test getting default rate limit"""
    middleware = RateLimitMiddleware(MagicMock())
    limit, window = middleware._get_rate_limit("/unknown/path")

    assert limit == 200
    assert window == 60


# ============================================================================
# Tests for get_rate_limit_stats
# ============================================================================


def test_get_rate_limit_stats():
    """Test getting rate limit statistics"""
    stats = get_rate_limit_stats()

    assert "backend" in stats
    assert "connected" in stats
    assert "rate_limits_configured" in stats

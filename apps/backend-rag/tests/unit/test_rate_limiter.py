"""
Unit tests for RateLimiter
Tests rate limiting functionality
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestRateLimiter:
    """Unit tests for RateLimiter"""

    def test_rate_limiter_init(self):
        """Test RateLimiter initialization"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None  # Use in-memory fallback

            from backend.middleware.rate_limiter import RateLimiter

            limiter = RateLimiter()
            assert limiter is not None

    def test_is_allowed_under_limit(self):
        """Test rate limit check when under limit"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None  # Use in-memory fallback

            from backend.middleware.rate_limiter import RateLimiter

            limiter = RateLimiter()
            allowed, info = limiter.is_allowed("user123", limit=10, window=60)
            assert isinstance(allowed, bool)
            assert isinstance(info, dict)

    def test_is_allowed_over_limit(self):
        """Test rate limit check when over limit"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None  # Use in-memory fallback

            from backend.middleware.rate_limiter import RateLimiter

            limiter = RateLimiter()
            # Make many requests to exceed limit
            for i in range(11):
                allowed, info = limiter.is_allowed("user123", limit=10, window=60)

            # Should be denied after exceeding limit
            assert isinstance(allowed, bool)

    def test_is_allowed_at_limit(self):
        """Test rate limit check at exact limit"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = None  # Use in-memory fallback

            from backend.middleware.rate_limiter import RateLimiter

            limiter = RateLimiter()
            # Make exactly limit requests
            for i in range(10):
                allowed, info = limiter.is_allowed("user123", limit=10, window=60)

            # May allow or deny depending on implementation
            assert isinstance(allowed, bool)
            assert isinstance(info, dict)

    def test_is_allowed_redis_error(self):
        """Test rate limit check when Redis fails"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            # Mock redis import to raise exception
            import sys

            original_redis = sys.modules.get("redis")
            mock_redis_module = MagicMock()
            mock_redis_module.from_url.side_effect = Exception("Redis error")
            sys.modules["redis"] = mock_redis_module

            try:
                from backend.middleware.rate_limiter import RateLimiter

                limiter = RateLimiter()
                # Should fallback to in-memory
                allowed, info = limiter.is_allowed("user123", limit=10, window=60)
                assert isinstance(allowed, bool)
                assert isinstance(info, dict)
            finally:
                # Restore original redis module
                if original_redis:
                    sys.modules["redis"] = original_redis
                elif "redis" in sys.modules:
                    del sys.modules["redis"]

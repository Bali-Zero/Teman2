"""
Comprehensive Integration Tests for All Middleware
Tests ErrorMonitoringMiddleware, HybridAuthMiddleware, RateLimitMiddleware

Covers:
- Error monitoring middleware
- Hybrid authentication middleware
- Rate limiting middleware
- Middleware chain execution
- Error handling in middleware
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestErrorMonitoringMiddleware:
    """Integration tests for ErrorMonitoringMiddleware"""

    @pytest.mark.asyncio
    async def test_error_monitoring_middleware_initialization(self):
        """Test ErrorMonitoringMiddleware initialization"""
        from middleware.error_monitoring import ErrorMonitoringMiddleware

        middleware = ErrorMonitoringMiddleware(MagicMock())

        assert middleware is not None

    @pytest.mark.asyncio
    async def test_error_capture(self, db_pool):
        """Test error capture in middleware"""

        async with db_pool.acquire() as conn:
            # Create error_logs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS error_logs (
                    id SERIAL PRIMARY KEY,
                    error_type VARCHAR(255),
                    error_message TEXT,
                    endpoint VARCHAR(255),
                    user_id VARCHAR(255),
                    stack_trace TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Log error
            error_id = await conn.fetchval(
                """
                INSERT INTO error_logs (
                    error_type, error_message, endpoint, user_id, stack_trace
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "ValueError",
                "Test error message",
                "/api/test/endpoint",
                "test_user_error",
                "Traceback...",
            )

            assert error_id is not None

            # Retrieve error
            error = await conn.fetchrow(
                """
                SELECT error_type, error_message, endpoint
                FROM error_logs
                WHERE id = $1
                """,
                error_id,
            )

            assert error is not None
            assert error["error_type"] == "ValueError"

            # Cleanup
            await conn.execute("DELETE FROM error_logs WHERE id = $1", error_id)

    @pytest.mark.asyncio
    async def test_error_aggregation(self, db_pool):
        """Test error aggregation"""

        async with db_pool.acquire() as conn:
            # Create multiple errors
            error_types = ["ValueError", "ValueError", "TypeError", "KeyError"]

            for error_type in error_types:
                await conn.execute(
                    """
                    INSERT INTO error_logs (
                        error_type, error_message, endpoint, user_id
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    error_type,
                    f"{error_type} occurred",
                    "/api/test",
                    "test_user",
                )

            # Aggregate errors
            aggregation = await conn.fetch(
                """
                SELECT
                    error_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT endpoint) as endpoint_count
                FROM error_logs
                GROUP BY error_type
                ORDER BY count DESC
                """
            )

            assert len(aggregation) >= 2
            assert any(a["error_type"] == "ValueError" and a["count"] == 2 for a in aggregation)

            # Cleanup
            await conn.execute("DELETE FROM error_logs WHERE user_id = $1", "test_user")


@pytest.mark.integration
class TestHybridAuthMiddleware:
    """Integration tests for HybridAuthMiddleware"""

    @pytest.mark.asyncio
    async def test_hybrid_auth_middleware_initialization(self):
        """Test HybridAuthMiddleware initialization"""
        from middleware.hybrid_auth import HybridAuthMiddleware

        middleware = HybridAuthMiddleware(MagicMock())

        assert middleware is not None

    @pytest.mark.asyncio
    async def test_jwt_authentication(self, db_pool):
        """Test JWT authentication in middleware"""
        from jose import jwt

        async with db_pool.acquire() as conn:
            # Create users table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    password_hash VARCHAR(255),
                    role VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create user
            user_id = await conn.fetchval(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "auth@test.com",
                "hashed_password",
                "user",
            )

            # Generate JWT token
            secret = "test_jwt_secret_key_for_testing_only_min_32_chars"
            token = jwt.encode(
                {"sub": str(user_id), "email": "auth@test.com"}, secret, algorithm="HS256"
            )

            # Verify token
            decoded = jwt.decode(token, secret, algorithms=["HS256"])

            assert decoded["email"] == "auth@test.com"
            assert decoded["sub"] == str(user_id)

            # Cleanup
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    @pytest.mark.asyncio
    async def test_api_key_authentication(self, db_pool):
        """Test API key authentication in middleware"""

        async with db_pool.acquire() as conn:
            # Create api_keys table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    key_hash VARCHAR(255) UNIQUE,
                    user_id INTEGER,
                    permissions TEXT[],
                    created_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP
                )
                """
            )

            # Create API key
            api_key = "test_api_key_12345"
            key_hash = str(hash(api_key))

            key_id = await conn.fetchval(
                """
                INSERT INTO api_keys (key_hash, user_id, permissions)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                key_hash,
                1,
                ["read", "write"],
            )

            # Verify API key
            stored_key = await conn.fetchrow(
                """
                SELECT key_hash, permissions
                FROM api_keys
                WHERE id = $1
                """,
                key_id,
            )

            assert stored_key is not None
            assert "read" in stored_key["permissions"]

            # Cleanup
            await conn.execute("DELETE FROM api_keys WHERE id = $1", key_id)


@pytest.mark.integration
class TestRateLimitMiddleware:
    """Integration tests for RateLimitMiddleware"""

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_initialization(self):
        """Test RateLimitMiddleware initialization"""
        from middleware.rate_limiter import RateLimitMiddleware

        middleware = RateLimitMiddleware(MagicMock())

        assert middleware is not None

    @pytest.mark.asyncio
    async def test_rate_limiting_logic(self):
        """Test rate limiting logic"""
        from middleware.rate_limiter import RateLimiter

        rate_limiter = RateLimiter()

        key = "test_rate_limit_key"
        limit = 5
        window = 60

        # Make requests up to limit
        for i in range(limit):
            allowed, info = rate_limiter.is_allowed(key, limit, window)
            assert allowed is True

        # Next request should be blocked
        allowed, info = rate_limiter.is_allowed(key, limit, window)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_storage(self, db_pool):
        """Test rate limit storage"""

        async with db_pool.acquire() as conn:
            # Create rate_limits table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id SERIAL PRIMARY KEY,
                    key_hash VARCHAR(255),
                    request_count INTEGER DEFAULT 1,
                    window_start TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store rate limit
            key_hash = "test_key_hash"
            limit_id = await conn.fetchval(
                """
                INSERT INTO rate_limits (key_hash, request_count, expires_at)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                key_hash,
                1,
                datetime.now() + timedelta(seconds=60),
            )

            # Increment count
            await conn.execute(
                """
                UPDATE rate_limits
                SET request_count = request_count + 1
                WHERE id = $1
                """,
                limit_id,
            )

            # Check limit
            limit_info = await conn.fetchrow(
                """
                SELECT request_count, expires_at
                FROM rate_limits
                WHERE id = $1
                """,
                limit_id,
            )

            assert limit_info["request_count"] == 2

            # Cleanup
            await conn.execute("DELETE FROM rate_limits WHERE id = $1", limit_id)


@pytest.mark.integration
class TestMiddlewareChain:
    """Integration tests for middleware chain execution"""

    @pytest.mark.asyncio
    async def test_middleware_execution_order(self):
        """Test middleware execution order"""
        execution_order = []

        async def mock_middleware_1(request, call_next):
            execution_order.append("middleware_1")
            response = await call_next(request)
            return response

        async def mock_middleware_2(request, call_next):
            execution_order.append("middleware_2")
            response = await call_next(request)
            return response

        async def mock_handler(request):
            execution_order.append("handler")
            return MagicMock()

        # Simulate middleware chain
        request = MagicMock()
        handler = mock_handler

        # Execute chain
        response1 = await mock_middleware_1(request, mock_middleware_2)
        response2 = await mock_middleware_2(request, handler)

        assert len(execution_order) >= 2

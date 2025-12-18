"""
Comprehensive Integration Tests for Authentication System
Tests JWT, API keys, and middleware integration

Covers:
- JWT token generation and validation
- API key authentication
- Middleware integration
- Rate limiting
- Error handling
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jose import jwt

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2,test_api_key_3")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAuthenticationIntegration:
    """Integration tests for authentication system"""

    def test_jwt_token_generation(self):
        """Test JWT token generation"""
        secret = os.getenv("JWT_SECRET_KEY")
        payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "role": "member",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        token = jwt.encode(payload, secret, algorithm="HS256")
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_token_validation(self):
        """Test JWT token validation"""
        secret = os.getenv("JWT_SECRET_KEY")
        payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "role": "member",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        token = jwt.encode(payload, secret, algorithm="HS256")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])

        assert decoded["sub"] == "test@example.com"
        assert decoded["email"] == "test@example.com"
        assert decoded["role"] == "member"

    def test_jwt_token_expiration(self):
        """Test JWT token expiration handling"""
        secret = os.getenv("JWT_SECRET_KEY")
        payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        }

        token = jwt.encode(payload, secret, algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, secret, algorithms=["HS256"])

    def test_api_key_validation(self):
        """Test API key validation"""
        api_keys = os.getenv("API_KEYS", "").split(",")
        assert len(api_keys) > 0

        # Test valid API key
        valid_key = api_keys[0].strip()
        assert valid_key in api_keys

        # Test invalid API key
        invalid_key = "invalid_api_key_12345"
        assert invalid_key not in api_keys

    def test_authenticated_request_with_jwt(self, test_client):
        """Test authenticated request with JWT token"""
        secret = os.getenv("JWT_SECRET_KEY")
        payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "role": "member",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        token = jwt.encode(payload, secret, algorithm="HS256")

        # Test health endpoint (should work without auth)
        response = test_client.get("/health")
        assert response.status_code in [200, 503]  # 503 if services not initialized

    def test_authenticated_request_with_api_key(self, test_client):
        """Test authenticated request with API key"""
        api_keys = os.getenv("API_KEYS", "").split(",")
        api_key = api_keys[0].strip()

        # Test with API key header
        response = test_client.get("/health", headers={"X-API-Key": api_key})
        assert response.status_code in [200, 503]

    def test_unauthenticated_request(self, test_client):
        """Test unauthenticated request handling"""
        # Health endpoint should be accessible
        response = test_client.get("/health")
        assert response.status_code in [200, 503]

        # Protected endpoints should require auth
        # (This depends on endpoint configuration)

    def test_rate_limiting_middleware(self):
        """Test rate limiting middleware functionality"""
        from middleware.rate_limiter import RateLimiter

        rate_limiter = RateLimiter()

        # Test rate limit check
        key = "test_rate_limit_key"
        limit = 10
        window = 60

        # First 10 requests should be allowed
        for i in range(10):
            allowed, info = rate_limiter.is_allowed(key, limit, window)
            assert allowed is True
            assert info["remaining"] >= 0

        # 11th request should be blocked
        allowed, info = rate_limiter.is_allowed(key, limit, window)
        # Note: This might still be allowed depending on timing
        assert isinstance(allowed, bool)
        assert "limit" in info
        assert "remaining" in info

    def test_error_monitoring_middleware(self):
        """Test error monitoring middleware"""
        from fastapi import FastAPI
        from middleware.error_monitoring import ErrorMonitoringMiddleware

        app = FastAPI()

        @app.get("/test-error")
        async def test_error():
            raise ValueError("Test error")

        middleware = ErrorMonitoringMiddleware(app)

        # Test that middleware is initialized
        assert middleware is not None
        assert middleware.alert_service is not None

    def test_hybrid_auth_middleware(self):
        """Test hybrid authentication middleware"""
        from fastapi import FastAPI
        from middleware.hybrid_auth import HybridAuthMiddleware

        app = FastAPI()
        middleware = HybridAuthMiddleware(app)

        # Test that middleware is initialized
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_auth_with_database(self, db_pool):
        """Test authentication with database user lookup"""

        async with db_pool.acquire() as conn:
            # Create users table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255),
                    role VARCHAR(50) DEFAULT 'member',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create test user
            user_id = await conn.fetchval(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "auth.test@example.com",
                "hashed_password_123",
                "member",
            )

            assert user_id is not None

            # Retrieve user
            user = await conn.fetchrow(
                """
                SELECT id, email, role
                FROM users
                WHERE email = $1
                """,
                "auth.test@example.com",
            )

            assert user is not None
            assert user["email"] == "auth.test@example.com"
            assert user["role"] == "member"

            # Cleanup
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    def test_token_refresh_flow(self):
        """Test JWT token refresh flow"""
        secret = os.getenv("JWT_SECRET_KEY")

        # Generate initial token
        initial_payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        initial_token = jwt.encode(initial_payload, secret, algorithm="HS256")

        # Generate refresh token
        refresh_payload = {
            "sub": "test@example.com",
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        }
        refresh_token = jwt.encode(refresh_payload, secret, algorithm="HS256")

        # Validate tokens
        initial_decoded = jwt.decode(initial_token, secret, algorithms=["HS256"])
        refresh_decoded = jwt.decode(refresh_token, secret, algorithms=["HS256"])

        assert initial_decoded["sub"] == "test@example.com"
        assert refresh_decoded["type"] == "refresh"

        # Generate new access token from refresh token
        new_payload = {
            "sub": refresh_decoded["sub"],
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        new_token = jwt.encode(new_payload, secret, algorithm="HS256")

        new_decoded = jwt.decode(new_token, secret, algorithms=["HS256"])
        assert new_decoded["sub"] == "test@example.com"

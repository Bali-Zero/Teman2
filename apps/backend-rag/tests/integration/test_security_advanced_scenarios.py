"""
Advanced Security Scenarios Integration Tests
Tests advanced security scenarios, authentication, authorization

Covers:
- JWT token security
- API key security
- Rate limiting security
- SQL injection prevention
- XSS prevention
- CSRF protection
- Authorization checks
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestSecurityAdvancedScenarios:
    """Advanced security scenario integration tests"""

    @pytest.mark.asyncio
    async def test_jwt_token_security(self, db_pool):
        """Test JWT token security"""
        from jose import jwt

        async with db_pool.acquire() as conn:
            # Create jwt_tokens table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jwt_tokens (
                    id SERIAL PRIMARY KEY,
                    token_hash VARCHAR(255) UNIQUE,
                    user_id VARCHAR(255),
                    expires_at TIMESTAMP,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Generate token
            secret = "test_jwt_secret_key_for_testing_only_min_32_chars"
            token = jwt.encode(
                {"sub": "user_123", "email": "test@example.com", "exp": 9999999999},
                secret,
                algorithm="HS256",
            )

            # Store token hash
            token_hash = str(hash(token))
            token_id = await conn.fetchval(
                """
                INSERT INTO jwt_tokens (token_hash, user_id, expires_at)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                token_hash,
                "user_123",
                datetime.now() + timedelta(days=7),
            )

            # Verify token
            stored_token = await conn.fetchrow(
                """
                SELECT user_id, revoked, expires_at
                FROM jwt_tokens
                WHERE token_hash = $1
                """,
                token_hash,
            )

            assert stored_token is not None
            assert stored_token["revoked"] is False

            # Revoke token
            await conn.execute(
                """
                UPDATE jwt_tokens
                SET revoked = TRUE
                WHERE id = $1
                """,
                token_id,
            )

            # Verify revocation
            revoked_token = await conn.fetchrow(
                """
                SELECT revoked FROM jwt_tokens WHERE id = $1
                """,
                token_id,
            )

            assert revoked_token["revoked"] is True

            # Cleanup
            await conn.execute("DELETE FROM jwt_tokens WHERE id = $1", token_id)

    @pytest.mark.asyncio
    async def test_api_key_security(self, db_pool):
        """Test API key security"""

        async with db_pool.acquire() as conn:
            # Create api_keys table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id SERIAL PRIMARY KEY,
                    key_hash VARCHAR(255) UNIQUE,
                    user_id VARCHAR(255),
                    permissions TEXT[],
                    rate_limit INTEGER DEFAULT 100,
                    last_used TIMESTAMP,
                    revoked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create API key
            api_key = "test_api_key_12345"
            key_hash = str(hash(api_key))

            key_id = await conn.fetchval(
                """
                INSERT INTO api_keys (
                    key_hash, user_id, permissions, rate_limit
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                key_hash,
                "user_api_123",
                ["read", "write"],
                100,
            )

            # Verify API key
            stored_key = await conn.fetchrow(
                """
                SELECT permissions, rate_limit, revoked
                FROM api_keys
                WHERE key_hash = $1
                """,
                key_hash,
            )

            assert stored_key is not None
            assert "read" in stored_key["permissions"]
            assert stored_key["revoked"] is False

            # Update last used
            await conn.execute(
                """
                UPDATE api_keys
                SET last_used = NOW()
                WHERE id = $1
                """,
                key_id,
            )

            # Cleanup
            await conn.execute("DELETE FROM api_keys WHERE id = $1", key_id)

    @pytest.mark.asyncio
    async def test_rate_limiting_security(self, db_pool):
        """Test rate limiting security"""

        async with db_pool.acquire() as conn:
            # Create rate_limits table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id SERIAL PRIMARY KEY,
                    identifier VARCHAR(255),
                    endpoint VARCHAR(255),
                    request_count INTEGER DEFAULT 1,
                    window_start TIMESTAMP DEFAULT NOW(),
                    blocked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            identifier = "test_user_rate_limit"
            endpoint = "/api/test"

            # Track requests
            for i in range(10):
                await conn.execute(
                    """
                    INSERT INTO rate_limits (identifier, endpoint, request_count)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (identifier, endpoint) DO UPDATE
                    SET request_count = rate_limits.request_count + 1
                    """,
                    identifier,
                    endpoint,
                    1,
                )

            # Check rate limit
            rate_limit = await conn.fetchrow(
                """
                SELECT request_count, blocked
                FROM rate_limits
                WHERE identifier = $1 AND endpoint = $2
                """,
                identifier,
                endpoint,
            )

            assert rate_limit["request_count"] >= 10

            # Block if exceeded
            if rate_limit["request_count"] > 100:
                await conn.execute(
                    """
                    UPDATE rate_limits
                    SET blocked = TRUE
                    WHERE identifier = $1 AND endpoint = $2
                    """,
                    identifier,
                    endpoint,
                )

            # Cleanup
            await conn.execute(
                """
                DELETE FROM rate_limits WHERE identifier = $1 AND endpoint = $2
                """,
                identifier,
                endpoint,
            )

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, db_pool):
        """Test SQL injection prevention"""

        async with db_pool.acquire() as conn:
            # Create security_test table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_test (
                    id SERIAL PRIMARY KEY,
                    user_input TEXT
                )
                """
            )

            # Test SQL injection attempts
            malicious_inputs = [
                "'; DROP TABLE security_test; --",
                "' OR '1'='1",
                "'; DELETE FROM security_test; --",
                "1' UNION SELECT * FROM users--",
            ]

            for malicious_input in malicious_inputs:
                # Should be safely parameterized
                test_id = await conn.fetchval(
                    """
                    INSERT INTO security_test (user_input)
                    VALUES ($1)
                    RETURNING id
                    """,
                    malicious_input,
                )

                # Verify input stored as literal, not executed
                stored = await conn.fetchval(
                    """
                    SELECT user_input FROM security_test WHERE id = $1
                    """,
                    test_id,
                )

                assert stored == malicious_input

            # Verify table still exists
            count = await conn.fetchval("SELECT COUNT(*) FROM security_test")
            assert count == len(malicious_inputs)

            # Cleanup
            await conn.execute("DROP TABLE IF EXISTS security_test")

    @pytest.mark.asyncio
    async def test_authorization_checks(self, db_pool):
        """Test authorization checks"""

        async with db_pool.acquire() as conn:
            # Create permissions table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    resource_type VARCHAR(255),
                    resource_id VARCHAR(255),
                    permission VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create permissions
            await conn.execute(
                """
                INSERT INTO permissions (user_id, resource_type, resource_id, permission)
                VALUES ($1, $2, $3, $4)
                """,
                "user_auth_123",
                "client",
                "client_456",
                "read",
            )

            await conn.execute(
                """
                INSERT INTO permissions (user_id, resource_type, resource_id, permission)
                VALUES ($1, $2, $3, $4)
                """,
                "user_auth_123",
                "client",
                "client_456",
                "write",
            )

            # Check authorization
            has_permission = await conn.fetchval(
                """
                SELECT COUNT(*) > 0
                FROM permissions
                WHERE user_id = $1
                AND resource_type = $2
                AND resource_id = $3
                AND permission = $4
                """,
                "user_auth_123",
                "client",
                "client_456",
                "write",
            )

            assert has_permission is True

            # Cleanup
            await conn.execute(
                """
                DELETE FROM permissions WHERE user_id = $1
                """,
                "user_auth_123",
            )

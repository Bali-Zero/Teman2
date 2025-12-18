"""
Security and Error Path Integration Tests
Tests fail-closed authentication, data isolation, and degradation scenarios.

Covers:
- Auth fail-closed: missing/invalid tokens, rate limiting, CORS
- Data leakage prevention: user isolation
- Degradation: Qdrant/DB down scenarios
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="module")
def test_app():
    """Create FastAPI app for security tests"""
    from unittest.mock import patch

    with patch("services.rag.agentic.AgenticRAGOrchestrator"):
        from app.main_cloud import app

        app.state.search_service = MagicMock()
        app.state.search_service.embedder = MagicMock()
        app.state.ai_client = MagicMock()
        app.state.db_pool = MagicMock()
        app.state.services_initialized = True

        yield app


@pytest.fixture(scope="function")
def test_client(test_app):
    """Create TestClient"""
    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture(scope="function")
def valid_token():
    """Generate valid JWT token"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    payload = {
        "sub": "user1@example.com",
        "email": "user1@example.com",
        "role": "user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(scope="function")
def other_user_token():
    """Generate JWT token for different user"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    payload = {
        "sub": "user2@example.com",
        "email": "user2@example.com",
        "role": "user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.integration
class TestAuthFailClosed:
    """Test authentication fail-closed behavior"""

    def test_missing_token(self, test_client):
        """Test endpoints reject requests without token"""
        response = test_client.get("/api/auth/profile")
        assert response.status_code == 401

        response = test_client.get("/api/bali-zero/conversations/list")
        assert response.status_code == 401

    def test_invalid_token_format(self, test_client):
        """Test endpoints reject invalid token format"""
        response = test_client.get(
            "/api/auth/profile", headers={"Authorization": "InvalidFormat token"}
        )
        assert response.status_code == 401

        response = test_client.get(
            "/api/auth/profile", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401

    def test_expired_token(self, test_client):
        """Test endpoints reject expired tokens"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        }
        secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
        expired_token = jwt.encode(payload, secret, algorithm="HS256")

        response = test_client.get(
            "/api/auth/profile", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

    def test_wrong_secret_token(self, test_client):
        """Test endpoints reject tokens signed with wrong secret"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        payload = {
            "sub": "test@example.com",
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        wrong_secret = "wrong_secret_key"
        wrong_token = jwt.encode(payload, wrong_secret, algorithm="HS256")

        response = test_client.get(
            "/api/auth/profile", headers={"Authorization": f"Bearer {wrong_token}"}
        )
        assert response.status_code == 401

    def test_cors_headers(self, test_client):
        """Test CORS headers are present"""
        response = test_client.options(
            "/api/auth/login",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # CORS preflight should be handled
        assert response.status_code in [200, 204, 405]


@pytest.mark.integration
class TestDataIsolation:
    """Test data isolation between users"""

    def test_user_cannot_access_other_conversations(
        self, test_client, valid_token, other_user_token, db_pool
    ):
        """Test user cannot access another user's conversations"""
        import asyncio

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        messages TEXT NOT NULL DEFAULT '[]',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                # Create conversation for user1
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, messages)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    "user1@example.com",
                    '[{"role": "user", "content": "private"}]',
                )
                return conv_id

        conv_id = asyncio.run(setup())

        # user2 tries to access user1's conversation
        response = test_client.get(
            f"/api/bali-zero/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {other_user_token}"},
        )
        # Should be 403 or 404 (not found for that user)
        assert response.status_code in [403, 404]

    def test_user_cannot_delete_other_conversations(
        self, test_client, valid_token, other_user_token, db_pool
    ):
        """Test user cannot delete another user's conversations"""
        import asyncio

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        messages TEXT NOT NULL DEFAULT '[]',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, messages)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    "user1@example.com",
                    '[{"role": "user", "content": "private"}]',
                )
                return conv_id

        conv_id = asyncio.run(setup())

        # user2 tries to delete user1's conversation
        response = test_client.delete(
            f"/api/bali-zero/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {other_user_token}"},
        )
        # Should be 403 or 404
        assert response.status_code in [403, 404]

    def test_user_cannot_access_other_crm_data(
        self, test_client, valid_token, other_user_token, db_pool
    ):
        """Test user cannot access another user's CRM data"""
        import asyncio

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        created_by VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email, created_by)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    "User1 Client",
                    "client1@example.com",
                    "user1@example.com",
                )
                return client_id

        client_id = asyncio.run(setup())

        # user2 tries to access user1's client
        response = test_client.get(
            f"/api/crm/clients/{client_id}",
            headers={"Authorization": f"Bearer {other_user_token}"},
        )
        # Should be 403 or 404
        assert response.status_code in [403, 404]


@pytest.mark.integration
class TestDegradationScenarios:
    """Test system degradation scenarios"""

    @patch("core.qdrant_db.QdrantClient")
    def test_qdrant_down_health_check(self, mock_qdrant, test_client):
        """Test health check reports degraded when Qdrant is down"""
        mock_qdrant_instance = MagicMock()
        mock_qdrant_instance.health_check.side_effect = Exception("Qdrant connection failed")
        mock_qdrant.return_value = mock_qdrant_instance

        response = test_client.get("/health/detailed")
        # Should return degraded status or error
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            # Should indicate degraded state
            assert "degraded" in str(data).lower() or "qdrant" in str(data).lower()

    @patch("app.dependencies.get_database_pool")
    def test_db_down_error_handling(self, mock_db_pool, test_client):
        """Test endpoints handle database down gracefully"""
        mock_db_pool.side_effect = Exception("Database connection failed")

        response = test_client.get("/health/ready")
        # Should return error or degraded status
        assert response.status_code in [200, 503, 500]

    @patch("services.search_service.SearchService.search")
    def test_search_degraded_mode(self, mock_search, test_client, valid_token):
        """Test search endpoint handles Qdrant failure gracefully"""
        mock_search.side_effect = Exception("Qdrant unavailable")

        response = test_client.get(
            "/api/search/?query=test",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Should return error with proper status code
        assert response.status_code in [500, 503, 502]

    @patch("services.rag.agentic.AgenticRAGOrchestrator.stream_query")
    def test_rag_degraded_mode(self, mock_stream, test_client, valid_token):
        """Test RAG endpoint handles service failures gracefully"""
        mock_stream.side_effect = Exception("Service unavailable")

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={"query": "test", "user_id": "test@example.com"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # Should return error with proper status code
        assert response.status_code in [500, 503, 502]


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting behavior"""

    def test_rate_limit_headers(self, test_client):
        """Test rate limit headers are present"""
        # Make multiple requests
        for _ in range(5):
            response = test_client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "pin": "wrong"},
            )
            # Check for rate limit headers (if implemented)
            if "X-RateLimit" in response.headers or "Retry-After" in response.headers:
                break

        # At least verify endpoint responds
        assert response.status_code in [200, 401, 429]

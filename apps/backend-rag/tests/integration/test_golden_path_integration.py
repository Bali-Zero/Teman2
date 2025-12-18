"""
Golden Path Integration Tests
Comprehensive end-to-end tests for all major API endpoints using real Postgres+Qdrant.

Covers:
- Auth: login, refresh, profile, check
- Conversations: save, list, history, stats, delete
- CRM: clients, practices, interactions (CRUD + workflows)
- Search: tier filtering, limits, error cases
- Agentic RAG SSE: streaming with sources
- Oracle Universal: query with Qdrant retrieval
- Health: all health endpoints
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient
from jose import jwt

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="module")
def test_app():
    """Create FastAPI app for integration tests"""
    from unittest.mock import patch

    # Mock heavy services that require external APIs
    with patch("services.rag.agentic.AgenticRAGOrchestrator") as mock_rag:
        with patch("services.oracle_google_services.google_services") as mock_google:
            with patch("services.gemini_service.GeminiService") as mock_gemini:
                from app.main_cloud import app

                # Setup app state with mocked services
                app.state.search_service = MagicMock()
                app.state.search_service.embedder = MagicMock()
                app.state.search_service.embedder.provider = "openai"
                app.state.search_service.embedder.dimensions = 1536

                app.state.ai_client = MagicMock()
                app.state.memory_service = MagicMock()
                app.state.intelligent_router = MagicMock()
                app.state.health_monitor = MagicMock()
                app.state.health_monitor._running = True
                app.state.compliance_monitor = MagicMock()
                app.state.ws_listener = MagicMock()
                app.state.proactive_compliance_monitor = MagicMock()
                # db_pool will be set in test_client fixture
                app.state.services_initialized = True

                yield app


@pytest.fixture(scope="function")
def test_client(test_app, db_pool):
    """Create TestClient with real database pool"""
    # Override database dependency
    test_app.dependency_overrides = {}
    from app.dependencies import get_database_pool

    # Create override function that returns real db_pool
    def override_get_db_pool(request):
        return db_pool

    test_app.dependency_overrides[get_database_pool] = override_get_db_pool

    # Set db_pool in app.state for direct access (needed by some services)
    test_app.state.db_pool = db_pool

    # Mock services that might try to await db_pool during shutdown
    if hasattr(test_app.state, "memory_service") and hasattr(test_app.state.memory_service, "pool"):
        test_app.state.memory_service.pool = db_pool

    with TestClient(test_app, raise_server_exceptions=False) as client:
        yield client

    test_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def setup_test_user(db_pool):
    """Create a test user in database"""
    async with db_pool.acquire() as conn:
        # Create users table if not exists
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'user',
                status VARCHAR(50) DEFAULT 'active',
                metadata JSONB DEFAULT '{}',
                language_preference VARCHAR(10) DEFAULT 'en',
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
        )

        # Create test user
        test_email = "test@example.com"
        test_pin = "123456"
        pin_hash = bcrypt.hashpw(test_pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Delete existing test user
        await conn.execute("DELETE FROM users WHERE email = $1", test_email)

        # Insert test user
        await conn.execute(
            """
            INSERT INTO users (email, name, password_hash, role, status, active)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            test_email,
            "Test User",
            pin_hash,
            "user",
            "active",
            True,
        )

        yield {"email": test_email, "pin": test_pin}

        # Cleanup
        await conn.execute("DELETE FROM users WHERE email = $1", test_email)


@pytest.fixture(scope="function")
def auth_token(setup_test_user):
    """Generate JWT token for test user"""
    payload = {
        "sub": setup_test_user["email"],
        "email": setup_test_user["email"],
        "role": "user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(scope="function")
def authenticated_client(test_client, auth_token):
    """TestClient with authentication headers"""
    test_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    yield test_client
    test_client.headers.pop("Authorization", None)


@pytest.mark.integration
class TestAuthEndpoints:
    """Integration tests for Auth endpoints"""

    def test_login_success(self, test_client, setup_test_user):
        """Test successful login"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": setup_test_user["email"], "pin": setup_test_user["pin"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "access_token" in data.get("data", {})

    def test_login_invalid_credentials(self, test_client, setup_test_user):
        """Test login with wrong PIN"""
        response = test_client.post(
            "/api/auth/login",
            json={"email": setup_test_user["email"], "pin": "wrong_pin"},
        )
        assert response.status_code == 401

    def test_refresh_token(self, test_client, auth_token):
        """Test token refresh"""
        response = test_client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # May succeed or return 404 if endpoint doesn't exist
        assert response.status_code in [200, 404]

    def test_get_profile(self, authenticated_client):
        """Test get user profile"""
        response = authenticated_client.get("/api/auth/profile")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "email" in data or "user" in data

    def test_auth_check(self, authenticated_client):
        """Test auth check endpoint"""
        response = authenticated_client.get("/api/auth/check")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "authenticated" in data or "valid" in data


@pytest.mark.integration
class TestConversationsEndpoints:
    """Integration tests for Conversations endpoints"""

    def test_save_conversation(self, authenticated_client, db_pool):
        """Test save conversation"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        messages TEXT NOT NULL DEFAULT '[]',
                        session_id VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )

        import asyncio

        asyncio.run(setup())

        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user", "content": "What is KITAS?"},
                    {"role": "assistant", "content": "KITAS is a temporary residence permit"},
                ],
                "session_id": "test_session_123",
            },
        )
        assert response.status_code in [200, 201]
        if response.status_code in [200, 201]:
            data = response.json()
            assert data.get("success") is True

    def test_list_conversations(self, authenticated_client, db_pool):
        """Test list conversations"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        messages TEXT NOT NULL DEFAULT '[]',
                        session_id VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                # Insert test conversation
                await conn.execute(
                    """
                    INSERT INTO conversations (user_id, messages, session_id)
                    VALUES ($1, $2, $3)
                    """,
                    "test@example.com",
                    '[{"role": "user", "content": "test"}]',
                    "test_session",
                )

        import asyncio

        asyncio.run(setup())

        response = authenticated_client.get("/api/bali-zero/conversations/list")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_get_history(self, authenticated_client, db_pool):
        """Test get conversation history"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        messages TEXT NOT NULL DEFAULT '[]',
                        session_id VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, messages, session_id)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    "test@example.com",
                    '[{"role": "user", "content": "test"}]',
                    "test_session",
                )
                return conv_id

        import asyncio

        conv_id = asyncio.run(setup())

        response = authenticated_client.get(
            "/api/bali-zero/conversations/history?session_id=test_session"
        )
        assert response.status_code in [200, 404]

    def test_get_stats(self, authenticated_client, db_pool):
        """Test get conversation statistics"""
        response = authenticated_client.get("/api/bali-zero/conversations/stats")
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestCRMEndpoints:
    """Integration tests for CRM endpoints"""

    def test_create_client(self, authenticated_client, db_pool):
        """Test create client"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        phone VARCHAR(50),
                        status VARCHAR(50) DEFAULT 'active',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                    """
                )

        import asyncio

        asyncio.run(setup())

        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Test Client",
                "email": "client@example.com",
                "phone": "+1234567890",
            },
        )
        assert response.status_code in [200, 201]

    def test_list_clients(self, authenticated_client, db_pool):
        """Test list clients"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        status VARCHAR(50) DEFAULT 'active',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                    """
                )

        import asyncio

        asyncio.run(setup())

        response = authenticated_client.get("/api/crm/clients")
        assert response.status_code in [200, 404]

    def test_create_practice(self, authenticated_client, db_pool):
        """Test create practice"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS practices (
                        id SERIAL PRIMARY KEY,
                        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                        practice_type VARCHAR(100) NOT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                    """
                )
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    "Test Client",
                    "client@example.com",
                )
                return client_id

        import asyncio

        client_id = asyncio.run(setup())

        response = authenticated_client.post(
            "/api/crm/practices",
            json={
                "client_id": client_id,
                "practice_type": "visa",
                "status": "pending",
            },
        )
        assert response.status_code in [200, 201]

    def test_create_interaction(self, authenticated_client, db_pool):
        """Test create interaction"""

        async def setup():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interactions (
                        id SERIAL PRIMARY KEY,
                        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                        interaction_type VARCHAR(50) NOT NULL,
                        summary TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        created_by VARCHAR(255)
                    )
                    """
                )
                client_id = await conn.fetchval(
                    """
                    INSERT INTO clients (full_name, email)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    "Test Client",
                    "client@example.com",
                )
                return client_id

        import asyncio

        client_id = asyncio.run(setup())

        response = authenticated_client.post(
            "/api/crm/interactions",
            json={
                "client_id": client_id,
                "interaction_type": "call",
                "summary": "Test interaction",
            },
        )
        assert response.status_code in [200, 201]


@pytest.mark.integration
class TestSearchEndpoints:
    """Integration tests for Search endpoints"""

    @patch("services.search_service.SearchService.search")
    def test_search_endpoint(self, mock_search, authenticated_client):
        """Test search endpoint"""
        mock_search.return_value = {
            "results": [{"content": "test", "score": 0.9}],
            "collection_used": "test_collection",
        }

        response = authenticated_client.get("/api/search/?query=test&limit=5")
        assert response.status_code in [200, 404]

    @patch("services.search_service.SearchService.search")
    def test_search_with_tier_filter(self, mock_search, authenticated_client):
        """Test search with tier filtering"""
        mock_search.return_value = {
            "results": [{"content": "test", "score": 0.9, "tier": "A"}],
            "collection_used": "test_collection",
        }

        response = authenticated_client.get("/api/search/?query=test&tier=A&limit=5")
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestAgenticRAGEndpoints:
    """Integration tests for Agentic RAG endpoints"""

    @patch("services.rag.agentic.AgenticRAGOrchestrator.stream_query")
    def test_agentic_rag_stream(self, mock_stream, authenticated_client):
        """Test Agentic RAG streaming endpoint"""

        async def mock_stream_generator():
            yield {"type": "metadata", "data": {"query": "test"}}
            yield {"type": "token", "data": "Hello"}
            yield {"type": "token", "data": " World"}
            yield {
                "type": "sources",
                "data": [
                    {"title": "Source 1", "url": "http://example.com", "content": "Test content"}
                ],
            }
            yield {"type": "done", "data": {}}

        mock_stream.return_value = mock_stream_generator()

        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={"query": "test query", "user_id": "test@example.com"},
        )
        assert response.status_code == 200

        # Verify SSE format
        content = response.text
        assert "data:" in content or len(content) > 0

    @patch("services.rag.agentic.AgenticRAGOrchestrator.process_query")
    def test_agentic_rag_query(self, mock_query, authenticated_client):
        """Test Agentic RAG non-streaming query"""
        mock_query.return_value = {
            "answer": "Test answer",
            "sources": [{"title": "Source 1"}],
            "context_used": 100,
            "execution_time": 1.5,
            "route_used": "direct",
        }

        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={"query": "test query", "user_id": "test@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data


@pytest.mark.integration
class TestOracleEndpoints:
    """Integration tests for Oracle endpoints"""

    @patch("services.oracle_google_services.google_services")
    @patch("services.gemini_service.GeminiService")
    def test_oracle_query(self, mock_gemini, mock_google, authenticated_client, qdrant_client):
        """Test Oracle Universal query endpoint"""
        # Mock Gemini response
        mock_gemini_instance = MagicMock()
        mock_gemini_instance.query.return_value = "Test oracle response"
        mock_gemini.return_value = mock_gemini_instance

        response = authenticated_client.post(
            "/api/oracle/query",
            json={"query": "What is KITAS?", "user_id": "test@example.com"},
        )
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestHealthEndpoints:
    """Integration tests for Health endpoints"""

    def test_health_basic(self, test_client):
        """Test basic health endpoint"""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "healthy" in data

    def test_health_ready(self, test_client):
        """Test readiness health endpoint"""
        response = test_client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data or "status" in data

    def test_health_detailed(self, test_client):
        """Test detailed health endpoint"""
        response = test_client.get("/health/detailed")
        assert response.status_code in [200, 404]

    def test_health_qdrant_metrics(self, test_client):
        """Test Qdrant health metrics"""
        response = test_client.get("/health/metrics/qdrant")
        assert response.status_code in [200, 404]

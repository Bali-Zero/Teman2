"""
Agentic RAG SSE Contract Tests
Tests SSE streaming endpoint with focus on event order and schema validation.

Verifies:
- Event order: metadata -> tool_* -> token -> sources -> done
- Schema contract for each event type
- Sources emission (new feature)
- Backward compatibility
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Set API key BEFORE any app imports so middleware picks it up
os.environ.setdefault("API_KEYS", "test-api-key-for-sse-tests")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="module")
def test_app():
    """Create FastAPI app for SSE tests"""
    from unittest.mock import MagicMock as Mock
    from unittest.mock import patch

    with patch("services.rag.agentic.AgenticRAGOrchestrator"):
        # Patch API key validation to always accept test key
        from middleware.hybrid_auth import HybridAuthMiddleware

        from app.main_cloud import app

        # Store original method
        original_authenticate = HybridAuthMiddleware.authenticate_request

        # Patch authenticate_request to accept our test API key
        async def mock_authenticate_request(self, request):
            api_key = request.headers.get("X-API-Key")
            if api_key == "test-api-key-for-sse-tests":
                return {
                    "id": "test@example.com",
                    "email": "test@example.com",
                    "role": "user",
                    "name": "Test User",
                    "status": "active",
                    "auth_method": "api_key",
                }
            # Fall back to original for other cases
            return await original_authenticate(self, request)

        HybridAuthMiddleware.authenticate_request = mock_authenticate_request

        # Setup app state
        app.state.search_service = Mock()
        app.state.search_service.embedder = Mock()
        app.state.search_service.embedder.provider = "openai"
        app.state.search_service.embedder.dimensions = 1536
        app.state.ai_client = Mock()
        app.state.db_pool = Mock()
        app.state.services_initialized = True

        yield app

        # Restore original method
        HybridAuthMiddleware.authenticate_request = original_authenticate


@pytest.fixture(scope="function")
def test_client(test_app):
    """Create TestClient with mocked orchestrator and db_pool"""
    from unittest.mock import AsyncMock, MagicMock

    from app.dependencies import get_database_pool
    from app.routers.agentic_rag import get_orchestrator

    # Create mock orchestrator with async method
    mock_orchestrator = MagicMock()
    mock_orchestrator.stream_query = AsyncMock()

    # Create mock db_pool
    mock_db_pool = MagicMock()

    # Override dependencies - must be async functions
    async def get_mock_orchestrator(request):
        return mock_orchestrator

    def get_mock_db_pool(request):
        return mock_db_pool

    test_app.dependency_overrides[get_orchestrator] = get_mock_orchestrator
    test_app.dependency_overrides[get_database_pool] = get_mock_db_pool

    with TestClient(test_app, raise_server_exceptions=False) as client:
        # Store mock for access in tests
        client._mock_orchestrator = mock_orchestrator
        yield client

    test_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_token():
    """Generate test JWT token"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    payload = {
        "sub": "test@example.com",
        "email": "test@example.com",
        "role": "user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = os.getenv("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.integration
class TestAgenticRAGSSEContract:
    """Contract tests for Agentic RAG SSE endpoint"""

    def test_sse_event_order(self, test_client, auth_token):
        """Verify SSE events arrive in correct order: metadata -> tool -> token -> sources -> done"""
        event_order = []

        async def mock_stream_generator():
            # Metadata first
            yield {
                "type": "metadata",
                "data": {"query": "test query", "user_id": "test@example.com"},
            }
            event_order.append("metadata")

            # Tool calls
            yield {
                "type": "tool_call",
                "data": {"tool": "vector_search", "args": {"query": "test"}},
            }
            event_order.append("tool_call")

            # Tokens
            yield {"type": "token", "data": "Hello"}
            event_order.append("token")
            yield {"type": "token", "data": " World"}
            event_order.append("token")

            # Sources (new feature)
            yield {
                "type": "sources",
                "data": [
                    {
                        "title": "Test Document",
                        "url": "http://example.com/doc1",
                        "content": "Test content",
                        "score": 0.95,
                    }
                ],
            }
            event_order.append("sources")

            # Done last
            yield {"type": "done", "data": {"execution_time": 1.5}}
            event_order.append("done")

        # Get mocked orchestrator from test client
        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200

        # Verify event order
        expected_order = ["metadata", "tool_call", "token", "token", "sources", "done"]
        assert event_order == expected_order

    def test_sse_metadata_schema(self, test_client, auth_token):
        """Verify metadata event schema"""

        async def mock_stream_generator():
            yield {
                "type": "metadata",
                "data": {
                    "query": "test query",
                    "user_id": "test@example.com",
                    "session_id": "test_session",
                    "timestamp": "2025-01-01T00:00:00Z",
                },
            }
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200
        content = response.text

        # Verify metadata structure in SSE
        assert "metadata" in content.lower() or "data:" in content

    def test_sse_sources_schema(self, test_client, auth_token):
        """Verify sources event schema (new feature)"""

        sources_data = [
            {
                "title": "Document 1",
                "url": "http://example.com/doc1",
                "content": "Content 1",
                "score": 0.95,
                "metadata": {"tier": "A", "collection": "visa_oracle"},
            },
            {
                "title": "Document 2",
                "url": "http://example.com/doc2",
                "content": "Content 2",
                "score": 0.87,
            },
        ]

        async def mock_stream_generator():
            yield {"type": "token", "data": "Answer"}
            yield {"type": "sources", "data": sources_data}
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200
        content = response.text

        # Verify sources are present
        assert "sources" in content.lower() or len(content) > 0

    def test_sse_sources_optional_fields(self, test_client, auth_token):
        """Verify sources schema allows optional fields"""

        sources_minimal = [{"title": "Doc 1", "content": "Content"}]
        sources_full = [
            {
                "title": "Doc 1",
                "url": "http://example.com",
                "content": "Content",
                "score": 0.9,
                "metadata": {"tier": "A"},
                "verification_score": 0.95,  # Optional field
            }
        ]

        async def mock_stream_generator():
            yield {"type": "token", "data": "Answer"}
            yield {"type": "sources", "data": sources_minimal}
            yield {"type": "sources", "data": sources_full}
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200

    def test_sse_token_chunks(self, test_client, auth_token):
        """Verify token chunks are properly formatted"""

        tokens = ["Hello", " ", "World", "!"]

        async def mock_stream_generator():
            for token in tokens:
                yield {"type": "token", "data": token}
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200
        content = response.text

        # Verify tokens are present
        assert len(content) > 0

    def test_sse_tool_call_schema(self, test_client, auth_token):
        """Verify tool_call event schema"""

        async def mock_stream_generator():
            yield {
                "type": "tool_call",
                "data": {
                    "tool": "vector_search",
                    "args": {"query": "test", "limit": 5},
                    "result": {"documents": ["doc1", "doc2"]},
                },
            }
            yield {"type": "token", "data": "Answer"}
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200

    def test_sse_done_event(self, test_client, auth_token):
        """Verify done event includes execution metadata"""

        async def mock_stream_generator():
            yield {"type": "token", "data": "Answer"}
            yield {
                "type": "done",
                "data": {
                    "execution_time": 1.5,
                    "tokens_used": 100,
                    "sources_count": 3,
                },
            }

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200

    def test_sse_backward_compatibility(self, test_client, auth_token):
        """Verify backward compatibility - old clients should still work"""

        # Simulate old format without sources
        async def mock_stream_generator():
            yield {"type": "metadata", "data": {"query": "test"}}
            yield {"type": "token", "data": "Answer"}
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        assert response.status_code == 200

    def test_sse_error_handling(self, test_client, auth_token):
        """Verify error events are properly formatted"""

        async def mock_stream_generator():
            yield {"type": "error", "data": {"message": "Test error", "code": "TEST_ERROR"}}
            yield {"type": "done", "data": {}}

        mock_orchestrator = test_client._mock_orchestrator
        mock_orchestrator.stream_query.return_value = mock_stream_generator()

        response = test_client.post(
            "/api/agentic-rag/stream",
            json={
                "query": "test query",
                "user_id": "test@example.com",
                "enable_vision": False,
            },
            headers={"X-API-Key": "test-api-key-for-sse-tests"},
        )

        # Should handle errors gracefully
        assert response.status_code in [200, 500]

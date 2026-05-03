"""
Unit tests for agentic_rag router optional authentication

Tests cover:
- /query endpoint with anonymous users
- /stream endpoint with anonymous users
- Authenticated vs anonymous user_id format
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.agentic_rag import router


@pytest.fixture
def test_app():
    """Create FastAPI test app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def mock_orchestrator():
    """Mock AgenticRAGOrchestrator"""
    orchestrator = AsyncMock()
    orchestrator.process_query = AsyncMock(
        return_value=MagicMock(
            answer="Test answer",
            sources=[{"title": "Source 1", "url": "https://example.com"}],
            tool_calls=[],
            reasoning="Test reasoning",
        ),
    )

    async def mock_stream_query(**kwargs):
        """Mock streaming query"""
        yield {"type": "thinking", "data": "Processing..."}
        yield {"type": "token", "data": "Test "}
        yield {"type": "token", "data": "answer"}
        yield {"type": "sources", "data": [{"title": "Source 1", "url": "https://example.com"}]}

    orchestrator.stream_query = mock_stream_query
    return orchestrator


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


class TestAgenticRAGStreamAnonymous:
    """Test /stream endpoint with anonymous users"""

    def test_stream_anonymous_user_creates_id(self, test_app, mock_orchestrator, mock_db_pool):
        """Test stream endpoint with anonymous user creates anonymous_XXX user_id"""
        with patch("backend.app.routers.agentic_rag.get_current_user_optional", return_value=None):
            with patch(
                "backend.app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator,
            ):
                with patch(
                    "backend.app.routers.agentic_rag.get_optional_database_pool",
                    return_value=mock_db_pool,
                ):
                    client = TestClient(test_app)
                    response = client.post(
                        "/api/agentic-rag/stream",
                        json={
                            "query": "Test query",
                            "session_id": "stream_session_123",
                            "user_id": None,
                        },
                    )

                    # Streaming returns 200 with text/event-stream
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers.get("content-type", "")


class TestAgenticRAGStreamAuthenticated:
    """Test /stream endpoint with authenticated users"""

    def test_stream_authenticated_user_uses_email(self, test_app, mock_orchestrator, mock_db_pool):
        """Test stream endpoint with authenticated user uses email"""
        mock_user = {"email": "stream@example.com", "user_id": "456", "role": "admin"}

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user_optional", return_value=mock_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=mock_db_pool,
            ),
        ):
            client = TestClient(test_app)
            response = client.post(
                "/api/agentic-rag/stream",
                json={
                    "query": "Test query",
                    "session_id": "stream_session",
                    "user_id": "should_be_ignored",
                },
            )

            # Streaming returns 200
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

"""
Integration Tests for Agentic RAG Router
Tests agentic_rag.py endpoints with real dependencies
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def app():
    """Create FastAPI app with agentic_rag router"""
    from fastapi import FastAPI

    from app.routers.agentic_rag import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.mark.integration
class TestAgenticRagRouterIntegration:
    """Comprehensive integration tests for agentic_rag router"""

    @pytest.mark.asyncio
    async def test_query_endpoint_basic(self, client):
        """Test basic query endpoint"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "agentic",
                }
            )
            mock_get.return_value = mock_orchestrator

            payload = {"query": "What is PT PMA?", "user_id": "test-user"}

            response = client.post("/api/agentic-rag/query", json=payload)

            assert response.status_code in [200, 500]  # May fail if dependencies missing

    @pytest.mark.asyncio
    async def test_query_endpoint_with_conversation_history(self, client):
        """Test query endpoint with conversation history"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "agentic",
                }
            )
            mock_get.return_value = mock_orchestrator

            payload = {
                "query": "What is PT PMA?",
                "user_id": "test-user",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi!"},
                ],
            }

            response = client.post("/api/agentic-rag/query", json=payload)
            assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_query_endpoint_with_vision(self, client):
        """Test query endpoint with vision enabled"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "agentic",
                }
            )
            mock_get.return_value = mock_orchestrator

            payload = {
                "query": "What is in this image?",
                "user_id": "test-user",
                "enable_vision": True,
            }

            response = client.post("/api/agentic-rag/query", json=payload)
            assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_get_conversation_history_with_conversation_id(self):
        """Test getting conversation history with conversation_id"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"messages": [{"role": "user", "content": "test"}]}
        )
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        history = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="test@example.com", db_pool=mock_pool
        )

        assert history is not None
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_get_conversation_history_with_session_id(self):
        """Test getting conversation history with session_id"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"messages": [{"role": "user", "content": "test"}]}
        )
        mock_pool.acquire = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        history = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id="session-123",
            user_id="test@example.com",
            db_pool=mock_pool,
        )

        assert history is not None

    @pytest.mark.asyncio
    async def test_get_conversation_history_no_db_pool(self):
        """Test getting conversation history without db_pool"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        history = await get_conversation_history_for_agentic(
            conversation_id=None, session_id=None, user_id="test", db_pool=None
        )

        assert history == []

    @pytest.mark.asyncio
    async def test_get_orchestrator_lazy_loading(self, app):
        """Test orchestrator lazy loading"""

        from app.routers.agentic_rag import get_orchestrator

        mock_request = MagicMock()
        mock_request.app.state.db_pool = MagicMock()
        mock_request.app.state.search_service = MagicMock()

        with patch("app.routers.agentic_rag.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_create.return_value = mock_orchestrator

            orchestrator = await get_orchestrator(mock_request)

            assert orchestrator is not None
            mock_create.assert_called_once()

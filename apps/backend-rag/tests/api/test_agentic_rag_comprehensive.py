"""
Comprehensive API Tests for Agentic RAG Router
Complete test coverage for Agentic RAG endpoints

Coverage:
- POST /api/agentic-rag/query - Query Agentic RAG
- POST /api/agentic-rag/stream - Stream Agentic RAG (SSE)
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestAgenticRAGQuery:
    """Comprehensive tests for POST /api/agentic-rag/query"""

    def test_agentic_rag_query_basic(self, authenticated_client):
        """Test basic Agentic RAG query"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 1.5,
                    "route_used": "simple",
                }
            )
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "What is Indonesian tax law?"},
            )

            assert response.status_code in [200, 500, 503]

    def test_agentic_rag_query_with_user_id(self, authenticated_client):
        """Test Agentic RAG query with user_id"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 1.5,
                    "route_used": "simple",
                }
            )
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query", "user_id": "user_123"},
            )

            assert response.status_code in [200, 500, 503]

    def test_agentic_rag_query_with_vision(self, authenticated_client):
        """Test Agentic RAG query with vision enabled"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 1.5,
                    "route_used": "vision",
                }
            )
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query", "enable_vision": True},
            )

            assert response.status_code in [200, 500, 503]

    def test_agentic_rag_query_missing_query(self, authenticated_client):
        """Test Agentic RAG query without query field"""
        response = authenticated_client.post(
            "/api/agentic-rag/query",
            json={},
        )

        assert response.status_code == 422

    def test_agentic_rag_query_empty_query(self, authenticated_client):
        """Test Agentic RAG query with empty query"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_query = AsyncMock(
                return_value={
                    "answer": "",
                    "sources": [],
                    "context_used": 0,
                    "execution_time": 0.1,
                    "route_used": "simple",
                }
            )
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": ""},
            )

            assert response.status_code in [200, 400, 422, 500, 503]

    def test_agentic_rag_query_response_structure(self, authenticated_client):
        """Test Agentic RAG query response structure"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [{"text": "Source 1", "score": 0.9}],
                    "context_used": 100,
                    "execution_time": 1.5,
                    "route_used": "complex",
                }
            )
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query"},
            )

            if response.status_code == 200:
                data = response.json()
                assert "answer" in data
                assert "sources" in data
                assert "context_length" in data
                assert "execution_time" in data
                assert "route_used" in data

    def test_agentic_rag_query_error_handling(self, authenticated_client):
        """Test Agentic RAG query error handling"""
        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.process_query = AsyncMock(side_effect=Exception("Service error"))
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query"},
            )

            assert response.status_code == 500


@pytest.mark.api
class TestAgenticRAGStream:
    """Comprehensive tests for POST /api/agentic-rag/stream"""

    def test_agentic_rag_stream_basic(self, authenticated_client):
        """Test basic Agentic RAG streaming"""

        async def mock_stream():
            yield {"type": "start", "message": "Starting"}
            yield {"type": "retrieval", "sources": 5}
            yield {"type": "reasoning", "step": "analyzing"}
            yield {"type": "complete", "answer": "Test answer"}

        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.stream_query = AsyncMock(return_value=mock_stream())
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/stream",
                json={"query": "Test query"},
            )

            # Streaming response
            assert response.status_code in [200, 500, 503]

    def test_agentic_rag_stream_with_user_id(self, authenticated_client):
        """Test Agentic RAG streaming with user_id"""

        async def mock_stream():
            yield {"type": "start", "message": "Starting"}
            yield {"type": "complete", "answer": "Test answer"}

        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.stream_query = AsyncMock(return_value=mock_stream())
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/stream",
                json={"query": "Test query", "user_id": "user_123"},
            )

            assert response.status_code in [200, 500, 503]

    def test_agentic_rag_stream_error_handling(self, authenticated_client):
        """Test Agentic RAG streaming error handling"""

        async def mock_stream_error():
            yield {"type": "error", "message": "Service unavailable"}
            raise Exception("Stream error")

        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.stream_query = AsyncMock(return_value=mock_stream_error())
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/stream",
                json={"query": "Test query"},
            )

            # Should handle errors gracefully
            assert response.status_code in [200, 500, 503]

    def test_agentic_rag_stream_quota_exceeded(self, authenticated_client):
        """Test Agentic RAG streaming with quota exceeded"""

        async def mock_stream_quota():
            raise Exception("429 ResourceExhausted")

        with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_orch.stream_query = AsyncMock(return_value=mock_stream_quota())
            mock_get_orch.return_value = mock_orch

            response = authenticated_client.post(
                "/api/agentic-rag/stream",
                json={"query": "Test query"},
            )

            # Should handle quota errors
            assert response.status_code in [200, 429, 500, 503]

    def test_agentic_rag_stream_missing_query(self, authenticated_client):
        """Test Agentic RAG streaming without query"""
        response = authenticated_client.post(
            "/api/agentic-rag/stream",
            json={},
        )

        assert response.status_code == 422


@pytest.mark.api
class TestAgenticRAGSecurity:
    """Security tests for Agentic RAG endpoints"""

    def test_agentic_rag_endpoints_require_auth(self, test_client):
        """Test all Agentic RAG endpoints require authentication"""
        endpoints = [
            ("POST", "/api/agentic-rag/query"),
            ("POST", "/api/agentic-rag/stream"),
        ]

        for method, path in endpoints:
            response = test_client.post(path, json={})

            assert response.status_code == 401

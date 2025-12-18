"""
API Tests for Agentic RAG Router
Tests agentic RAG query endpoint

Coverage:
- POST /api/agentic-rag/query - Agentic RAG query
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestAgenticRAGEndpoints:
    """Tests for agentic RAG endpoints"""

    def test_query_agentic_rag(self, authenticated_client):
        """Test POST /api/agentic-rag/query"""
        with patch(
            "app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock
        ) as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": ["source1", "source2"],
                    "context_used": 1000,
                    "execution_time": 1.5,
                    "route_used": "test_route",
                }
            )
            mock_get_orchestrator.return_value = mock_orchestrator

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query", "user_id": "user123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data

    def test_query_agentic_rag_with_vision(self, authenticated_client):
        """Test POST /api/agentic-rag/query with vision enabled"""
        with patch(
            "app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock
        ) as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 500,
                    "execution_time": 1.0,
                    "route_used": "vision_route",
                }
            )
            mock_get_orchestrator.return_value = mock_orchestrator

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query", "enable_vision": True},
            )

            assert response.status_code == 200

    def test_query_agentic_rag_error(self, authenticated_client):
        """Test POST /api/agentic-rag/query when orchestrator fails"""
        with patch(
            "app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock
        ) as mock_get_orchestrator:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Orchestrator error"))
            mock_get_orchestrator.return_value = mock_orchestrator

            response = authenticated_client.post(
                "/api/agentic-rag/query",
                json={"query": "Test query"},
            )

            assert response.status_code == 500

    def test_agentic_rag_requires_auth(self, test_client):
        """Test that agentic RAG endpoints require authentication"""
        response = test_client.post(
            "/api/agentic-rag/query",
            json={"query": "Test query"},
        )
        assert response.status_code == 401

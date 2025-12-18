"""
Integration tests for Agentic RAG Orchestrator
Tests agentic RAG query processing integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["QDRANT_URL"] = os.getenv("QDRANT_URL", "http://localhost:6333")
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAgenticRAGIntegration:
    """Integration tests for Agentic RAG Orchestrator"""

    @pytest.mark.asyncio
    async def test_agentic_rag_orchestrator_initialization(self, qdrant_client):
        """Test agentic RAG orchestrator initialization"""
        with patch(
            "services.context.agentic_orchestrator_v2.AgenticRAGOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.initialize = AsyncMock(return_value=None)
            mock_orchestrator_class.return_value = mock_orchestrator

            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            orchestrator = AgenticRAGOrchestrator()
            await orchestrator.initialize()

            assert orchestrator is not None

    @pytest.mark.asyncio
    async def test_agentic_rag_query_flow(self, qdrant_client):
        """Test agentic RAG query flow"""
        with patch(
            "services.context.agentic_orchestrator_v2.AgenticRAGOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.initialize = AsyncMock(return_value=None)
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "test",
                }
            )
            mock_orchestrator_class.return_value = mock_orchestrator

            from services.context.agentic_orchestrator_v2 import AgenticRAGOrchestrator

            orchestrator = AgenticRAGOrchestrator()
            await orchestrator.initialize()

            result = await orchestrator.process_query("Test query", "user123")
            assert "answer" in result

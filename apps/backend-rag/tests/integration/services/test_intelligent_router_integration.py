"""
Integration Tests for IntelligentRouter
Tests intelligent routing with agentic RAG
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestIntelligentRouterIntegration:
    """Comprehensive integration tests for IntelligentRouter"""

    @pytest_asyncio.fixture
    async def mock_search_service(self):
        """Create mock search service"""
        return MagicMock()

    @pytest_asyncio.fixture
    async def mock_db_pool(self):
        """Create mock database pool"""
        return MagicMock()

    @pytest_asyncio.fixture
    async def router(self, mock_search_service, mock_db_pool):
        """Create IntelligentRouter instance"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.initialize = AsyncMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": [],
                    "context_used": 100,
                    "execution_time": 0.5,
                    "route_used": "agentic",
                }
            )
            mock_orchestrator.stream_query = AsyncMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(
                search_service=mock_search_service,
                db_pool=mock_db_pool,
            )
            router.orchestrator = mock_orchestrator
            return router

    @pytest.mark.asyncio
    async def test_initialization(self, router):
        """Test router initialization"""
        assert router is not None
        assert router.orchestrator is not None

    @pytest.mark.asyncio
    async def test_initialize(self, router):
        """Test async initialization"""
        await router.initialize()
        router.orchestrator.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_chat(self, router):
        """Test routing chat message"""
        result = await router.route_chat(
            message="What is PT PMA?",
            user_id="test-user",
            conversation_history=[],
        )

        assert result is not None
        assert "response" in result
        assert result["ai_used"] == "agentic-rag"
        assert result["used_rag"] is True

    @pytest.mark.asyncio
    async def test_route_chat_with_memory(self, router):
        """Test routing chat with memory"""
        memory = {"facts": ["User prefers English"], "summary": "Test summary"}

        result = await router.route_chat(
            message="What is PT PMA?",
            user_id="test-user",
            memory=memory,
        )

        assert result is not None
        assert "response" in result

    @pytest.mark.asyncio
    async def test_route_chat_with_collaborator(self, router):
        """Test routing chat with collaborator"""
        collaborator = MagicMock()
        collaborator.name = "Test User"
        collaborator.role = "Developer"

        result = await router.route_chat(
            message="What is PT PMA?",
            user_id="test-user",
            collaborator=collaborator,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_stream_chat(self, router):
        """Test streaming chat"""
        router.orchestrator.stream_query = AsyncMock()
        router.orchestrator.stream_query.return_value = iter(
            [
                {"type": "token", "data": "Test"},
                {"type": "token", "data": " answer"},
                {"type": "done", "data": {}},
            ]
        )

        chunks = []
        async for chunk in router.stream_chat(
            message="What is PT PMA?",
            user_id="test-user",
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_route_chat_error_handling(self, router):
        """Test error handling in route_chat"""
        router.orchestrator.process_query = AsyncMock(side_effect=Exception("Test error"))

        with pytest.raises(Exception):
            await router.route_chat(message="test", user_id="test-user")

    @pytest.mark.asyncio
    async def test_stream_chat_error_handling(self, router):
        """Test error handling in stream_chat"""
        router.orchestrator.stream_query = AsyncMock(side_effect=Exception("Test error"))

        with pytest.raises(Exception):
            async for _ in router.stream_chat(message="test", user_id="test-user"):
                pass

    def test_get_stats(self, router):
        """Test getting router statistics"""
        stats = router.get_stats()

        assert stats is not None
        assert stats["router"] == "agentic_rag_wrapper"
        assert stats["rag_available"] is True

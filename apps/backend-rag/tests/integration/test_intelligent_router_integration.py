"""
Comprehensive Integration Tests for IntelligentRouter
Tests the main routing service that delegates to AgenticRAG

Covers:
- Route chat functionality
- Agentic RAG delegation
- Error handling
- Memory integration
- Tool execution integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestIntelligentRouterIntegration:
    """Integration tests for IntelligentRouter"""

    @pytest.mark.asyncio
    async def test_intelligent_router_initialization(self, db_pool, qdrant_client):
        """Test IntelligentRouter initialization"""
        with (
            patch("services.intelligent_router.create_agentic_rag") as mock_create_rag,
            patch("services.search_service.SearchService") as mock_search,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.initialize = AsyncMock()
            mock_create_rag.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search.return_value)
            await router.initialize()

            assert router is not None
            assert router.orchestrator is not None

    @pytest.mark.asyncio
    async def test_route_chat_basic(self, db_pool):
        """Test basic route_chat functionality"""
        with (
            patch("services.intelligent_router.create_agentic_rag") as mock_create_rag,
            patch("services.search_service.SearchService") as mock_search,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test response",
                    "sources": [{"text": "Source 1", "score": 0.9}],
                }
            )
            mock_create_rag.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search.return_value)
            await router.initialize()

            result = await router.route_chat(
                message="What is KITAS?",
                user_id="test_user_router_1",
            )

            assert result is not None
            assert result["response"] == "Test response"
            assert result["ai_used"] == "agentic-rag"
            assert result["used_rag"] is True
            assert len(result["sources"]) == 1

    @pytest.mark.asyncio
    async def test_route_chat_with_memory(self, db_pool):
        """Test route_chat with user memory"""
        with (
            patch("services.intelligent_router.create_agentic_rag") as mock_create_rag,
            patch("services.search_service.SearchService") as mock_search,
            patch("services.memory_service_postgres.MemoryServicePostgres") as mock_memory,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Response with memory context",
                    "sources": [],
                }
            )
            mock_create_rag.return_value = mock_orchestrator

            mock_memory_instance = MagicMock()
            mock_memory_instance.get_memory = AsyncMock(
                return_value=MagicMock(profile_facts=["User likes Python"])
            )

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search.return_value)
            await router.initialize()

            result = await router.route_chat(
                message="What programming language should I use?",
                user_id="test_user_router_2",
                memory=mock_memory_instance.get_memory("test_user_router_2"),
            )

            assert result is not None
            assert "response" in result

    @pytest.mark.asyncio
    async def test_route_chat_with_conversation_history(self, db_pool):
        """Test route_chat with conversation history"""
        with (
            patch("services.intelligent_router.create_agentic_rag") as mock_create_rag,
            patch("services.search_service.SearchService") as mock_search,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Follow-up response",
                    "sources": [],
                }
            )
            mock_create_rag.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search.return_value)
            await router.initialize()

            conversation_history = [
                {"role": "user", "content": "What is KITAS?"},
                {"role": "assistant", "content": "KITAS is a temporary residence permit"},
            ]

            result = await router.route_chat(
                message="How long does it take?",
                user_id="test_user_router_3",
                conversation_history=conversation_history,
            )

            assert result is not None
            assert "response" in result

    @pytest.mark.asyncio
    async def test_route_chat_error_handling(self, db_pool):
        """Test route_chat error handling"""
        with (
            patch("services.intelligent_router.create_agentic_rag") as mock_create_rag,
            patch("services.search_service.SearchService") as mock_search,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Test error"))
            mock_create_rag.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search.return_value)
            await router.initialize()

            with pytest.raises(Exception) as exc_info:
                await router.route_chat(
                    message="Test query",
                    user_id="test_user_router_4",
                )

            assert "Routing failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_route_chat_with_tools(self, db_pool):
        """Test route_chat with frontend tools"""
        with (
            patch("services.intelligent_router.create_agentic_rag") as mock_create_rag,
            patch("services.search_service.SearchService") as mock_search,
        ):
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Response with tools",
                    "sources": [],
                    "tools_called": ["get_pricing"],
                }
            )
            mock_create_rag.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search.return_value)
            await router.initialize()

            frontend_tools = [
                {"name": "get_pricing", "description": "Get pricing information"},
            ]

            result = await router.route_chat(
                message="What are your prices?",
                user_id="test_user_router_5",
                frontend_tools=frontend_tools,
            )

            assert result is not None
            assert result["used_tools"] is False  # Tools handled by orchestrator

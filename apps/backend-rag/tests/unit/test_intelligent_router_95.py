"""
Unit Tests for services/intelligent_router.py - 95% Coverage Target
Tests the IntelligentRouter class
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test IntelligentRouter initialization
# ============================================================================


class TestIntelligentRouterInit:
    """Test suite for IntelligentRouter initialization"""

    def test_init_with_search_service(self):
        """Test initialization with search service"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            mock_search = MagicMock()
            mock_db_pool = MagicMock()

            router = IntelligentRouter(search_service=mock_search, db_pool=mock_db_pool)

            mock_create.assert_called_once_with(
                retriever=mock_search,
                db_pool=mock_db_pool,
                web_search_client=None,
            )
            assert router.orchestrator == mock_orchestrator

    def test_init_without_services(self):
        """Test initialization without services"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()

            mock_create.assert_called_once_with(
                retriever=None,
                db_pool=None,
                web_search_client=None,
            )

    def test_init_with_collaborator_service(self):
        """Test initialization stores collaborator service"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            mock_collaborator = MagicMock()

            router = IntelligentRouter(collaborator_service=mock_collaborator)

            assert router.collaborator_service == mock_collaborator


# ============================================================================
# Test initialize
# ============================================================================


class TestInitialize:
    """Test suite for initialize method"""

    @pytest.mark.asyncio
    async def test_initialize_calls_orchestrator(self):
        """Test initialize calls orchestrator initialize"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.initialize = AsyncMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()
            await router.initialize()

            mock_orchestrator.initialize.assert_called_once()


# ============================================================================
# Test route_chat
# ============================================================================


class TestRouteChat:
    """Test suite for route_chat method"""

    @pytest.mark.asyncio
    async def test_route_chat_success(self):
        """Test successful chat routing"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "This is the answer",
                    "sources": [{"title": "Source 1", "url": "http://example.com"}],
                }
            )
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()
            result = await router.route_chat(
                message="What is KITAS?",
                user_id="user123",
            )

            assert result["response"] == "This is the answer"
            assert result["ai_used"] == "agentic-rag"
            assert result["category"] == "agentic"
            assert result["model"] == "gemini-2.5-flash"
            assert result["used_rag"] is True
            assert result["used_tools"] is False
            assert result["tools_called"] == []
            assert result["sources"] == [{"title": "Source 1", "url": "http://example.com"}]

    @pytest.mark.asyncio
    async def test_route_chat_with_conversation_history(self):
        """Test chat routing with conversation history"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Response with context", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()
            history = [
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"},
            ]
            result = await router.route_chat(
                message="Follow up question",
                user_id="user123",
                conversation_history=history,
            )

            assert result["response"] == "Response with context"
            mock_orchestrator.process_query.assert_called_once_with(
                query="Follow up question", user_id="user123"
            )

    @pytest.mark.asyncio
    async def test_route_chat_with_optional_params(self):
        """Test chat routing with optional parameters"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Result", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()

            mock_memory = MagicMock()
            mock_emotional = MagicMock()
            mock_collaborator = MagicMock()

            result = await router.route_chat(
                message="Test message",
                user_id="user456",
                conversation_history=None,
                memory=mock_memory,
                emotional_profile=mock_emotional,
                _last_ai_used="gpt-4",
                collaborator=mock_collaborator,
                frontend_tools=[{"name": "tool1"}],
            )

            assert result["response"] == "Result"

    @pytest.mark.asyncio
    async def test_route_chat_error_handling(self):
        """Test chat routing error handling"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Query failed"))
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()

            with pytest.raises(Exception, match="Routing failed: Query failed"):
                await router.route_chat(message="Test", user_id="user123")


# ============================================================================
# Test stream_chat
# ============================================================================


class TestStreamChat:
    """Test suite for stream_chat method"""

    @pytest.mark.asyncio
    async def test_stream_chat_success(self):
        """Test successful chat streaming"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield {"type": "token", "content": "Hello"}
                yield {"type": "token", "content": " world"}
                yield {"type": "done"}

            mock_orchestrator.stream_query = mock_stream
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()

            chunks = []
            async for chunk in router.stream_chat(
                message="Say hello",
                user_id="user123",
            ):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0] == {"type": "token", "content": "Hello"}
            assert chunks[1] == {"type": "token", "content": " world"}
            assert chunks[2] == {"type": "done"}

    @pytest.mark.asyncio
    async def test_stream_chat_with_optional_params(self):
        """Test streaming with optional parameters"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield {"content": "Response chunk"}

            mock_orchestrator.stream_query = mock_stream
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()

            mock_memory = MagicMock()
            mock_collaborator = MagicMock()
            history = [{"role": "user", "content": "Previous"}]

            chunks = []
            async for chunk in router.stream_chat(
                message="Test",
                user_id="user123",
                conversation_history=history,
                memory=mock_memory,
                collaborator=mock_collaborator,
            ):
                chunks.append(chunk)

            assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_stream_chat_error_handling(self):
        """Test streaming error handling"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()

            async def mock_stream(*args, **kwargs):
                raise Exception("Stream failed")
                yield  # Make it a generator

            mock_orchestrator.stream_query = mock_stream
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()

            with pytest.raises(Exception, match="Streaming failed: Stream failed"):
                async for _ in router.stream_chat(message="Test", user_id="user123"):
                    pass


# ============================================================================
# Test get_stats
# ============================================================================


class TestGetStats:
    """Test suite for get_stats method"""

    def test_get_stats_returns_dict(self):
        """Test get_stats returns proper dictionary"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()
            stats = router.get_stats()

            assert stats == {
                "router": "agentic_rag_wrapper",
                "model": "gemini-2.5-flash",
                "rag_available": True,
            }

    def test_get_stats_model_info(self):
        """Test get_stats contains model info"""
        with patch("services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_create.return_value = mock_orchestrator

            from services.intelligent_router import IntelligentRouter

            router = IntelligentRouter()
            stats = router.get_stats()

            assert "model" in stats
            assert stats["model"] == "gemini-2.5-flash"
            assert stats["rag_available"] is True

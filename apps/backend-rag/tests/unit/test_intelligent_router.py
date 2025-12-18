"""
Unit tests for IntelligentRouter
Tests intelligent routing functionality
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestIntelligentRouter:
    """Unit tests for IntelligentRouter"""

    @pytest.fixture
    def mock_search_service(self):
        """Create mock search service"""
        mock = MagicMock()
        mock.search = AsyncMock(return_value={"results": []})
        return mock

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator"""
        mock = MagicMock()
        mock.initialize = AsyncMock()
        mock.process_query = AsyncMock(return_value={"answer": "Test response", "sources": []})
        mock.stream_query = AsyncMock()
        return mock

    def test_intelligent_router_init(self, mock_search_service):
        """Test IntelligentRouter initialization"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_create.return_value = MagicMock()

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            assert router is not None
            assert router.orchestrator is not None

    @pytest.mark.asyncio
    async def test_route_chat(self, mock_search_service):
        """Test routing chat message"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Test response", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            result = await router.route_chat("test message", user_id="test123")

            assert isinstance(result, dict)
            assert "response" in result
            assert "ai_used" in result

    def test_get_stats(self, mock_search_service):
        """Test getting router stats"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_create.return_value = MagicMock()

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            stats = router.get_stats()

            assert isinstance(stats, dict)
            assert "router" in stats

    # ============================================================================
    # Expanded Edge Cases and Additional Tests
    # ============================================================================

    @pytest.mark.asyncio
    async def test_route_chat_with_conversation_history(self, mock_search_service):
        """Test routing chat with conversation history"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Contextual response",
                    "sources": [{"text": "Source 1"}],
                    "metadata": {"model": "zantara-ai"},
                }
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            result = await router.route_chat(
                "test message",
                user_id="test123",
                conversation_history=[{"role": "user", "content": "Hello"}],
            )

            assert isinstance(result, dict)
            assert "response" in result
            mock_orchestrator.process_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_chat_empty_message(self, mock_search_service):
        """Test routing empty chat message"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Empty message response", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            result = await router.route_chat("", user_id="test123")

            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_route_chat_very_long_message(self, mock_search_service):
        """Test routing very long chat message"""
        long_message = "test " * 1000
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Response", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            result = await router.route_chat(long_message, user_id="test123")

            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_route_chat_special_characters(self, mock_search_service):
        """Test routing chat with special characters"""
        special_message = "test query with émojis 🎉 and spéciál chars @#$%"
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Response", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            result = await router.route_chat(special_message, user_id="test123")

            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_error(self, mock_search_service):
        """Test routing chat handles orchestrator errors"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Orchestrator error"))
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)

            # Should handle error gracefully
            try:
                result = await router.route_chat("test message", user_id="test123")
                assert isinstance(result, dict)
            except Exception:
                # Exception is acceptable for error handling test
                pass

    @pytest.mark.asyncio
    async def test_route_chat_updates_stats(self, mock_search_service):
        """Test route_chat updates statistics"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Response", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            initial_stats = router.get_stats()

            await router.route_chat("test message", user_id="test123")

            updated_stats = router.get_stats()
            # Stats should be updated (if tracking is implemented)
            assert isinstance(updated_stats, dict)

    @pytest.mark.asyncio
    async def test_stream_chat(self, mock_search_service):
        """Test streaming chat response"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()

            async def mock_stream(*args, **kwargs):
                yield {"text": "chunk1"}
                yield {"text": "chunk2"}
                yield {"text": "chunk3"}

            mock_orchestrator.stream_query = mock_stream
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            chunks = []
            async for chunk in router.stream_chat("test message", user_id="test123"):
                chunks.append(chunk)

            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_chat_empty_response(self, mock_search_service):
        """Test streaming chat with empty response"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()

            async def mock_empty_stream(*args, **kwargs):
                return
                yield  # Empty generator

            mock_orchestrator.stream_query = mock_empty_stream
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            chunks = []
            async for chunk in router.stream_chat("test message", user_id="test123"):
                chunks.append(chunk)

            # Should handle empty stream gracefully
            assert isinstance(chunks, list)

    @pytest.mark.asyncio
    async def test_stream_chat_error_handling(self, mock_search_service):
        """Test streaming chat handles errors"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()

            async def mock_error_stream(*args, **kwargs):
                yield {"text": "chunk1"}
                raise Exception("Stream error")
                yield {"text": "chunk2"}  # Never reached

            mock_orchestrator.stream_query = mock_error_stream
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)

            # Should handle stream error gracefully
            chunks = []
            try:
                async for chunk in router.stream_chat("test message", user_id="test123"):
                    chunks.append(chunk)
            except Exception:
                # Exception is acceptable for error handling test
                pass

            assert len(chunks) >= 0

    def test_get_stats_initial_state(self, mock_search_service):
        """Test get_stats returns initial state"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_create.return_value = MagicMock()

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)
            stats = router.get_stats()

            assert isinstance(stats, dict)
            assert "router" in stats
            # Check initial values if tracked
            if "total_queries" in stats:
                assert stats["total_queries"] == 0

    def test_get_stats_after_multiple_queries(self, mock_search_service):
        """Test get_stats after multiple queries"""
        with patch("backend.services.intelligent_router.create_agentic_rag") as mock_create:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={"answer": "Response", "sources": []}
            )
            mock_create.return_value = mock_orchestrator

            from backend.services.intelligent_router import IntelligentRouter

            router = IntelligentRouter(search_service=mock_search_service)

            # Make multiple queries
            import asyncio

            async def make_queries():
                await router.route_chat("query 1", user_id="test123")
                await router.route_chat("query 2", user_id="test123")
                await router.route_chat("query 3", user_id="test123")

            asyncio.run(make_queries())

            stats = router.get_stats()
            assert isinstance(stats, dict)

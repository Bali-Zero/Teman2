"""
Comprehensive unit tests for IntelligentRouter service.
Target: 90%+ code coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path for imports
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from services.routing.intelligent_router import IntelligentRouter


class TestIntelligentRouterInit:
    """Test IntelligentRouter initialization."""

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_init_minimal_params(self, mock_create_agentic_rag):
        """Test initialization with minimal required parameters."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_create_agentic_rag.return_value = mock_orchestrator
        mock_search_service = MagicMock()
        mock_db_pool = MagicMock()

        # Act
        router = IntelligentRouter(
            search_service=mock_search_service,
            db_pool=mock_db_pool,
        )

        # Assert
        assert router.orchestrator == mock_orchestrator
        assert router.collaborator_service is None
        # Verify key arguments were passed
        call_kwargs = mock_create_agentic_rag.call_args.kwargs
        assert call_kwargs["retriever"] == mock_search_service
        assert call_kwargs["db_pool"] == mock_db_pool
        assert call_kwargs["web_search_client"] is None

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_init_all_params(self, mock_create_agentic_rag):
        """Test initialization with all parameters."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_create_agentic_rag.return_value = mock_orchestrator
        mock_ai_client = MagicMock()
        mock_search_service = MagicMock()
        mock_tool_executor = MagicMock()
        mock_cultural_rag_service = MagicMock()
        mock_autonomous_research_service = MagicMock()
        mock_cross_oracle_synthesis_service = MagicMock()
        mock_client_journey_orchestrator = MagicMock()
        mock_personality_service = MagicMock()
        mock_collaborator_service = MagicMock()
        mock_db_pool = MagicMock()

        # Act
        router = IntelligentRouter(
            ai_client=mock_ai_client,
            search_service=mock_search_service,
            tool_executor=mock_tool_executor,
            cultural_rag_service=mock_cultural_rag_service,
            autonomous_research_service=mock_autonomous_research_service,
            cross_oracle_synthesis_service=mock_cross_oracle_synthesis_service,
            client_journey_orchestrator=mock_client_journey_orchestrator,
            personality_service=mock_personality_service,
            collaborator_service=mock_collaborator_service,
            db_pool=mock_db_pool,
        )

        # Assert
        assert router.orchestrator == mock_orchestrator
        assert router.collaborator_service == mock_collaborator_service
        # Verify key arguments were passed
        call_kwargs = mock_create_agentic_rag.call_args.kwargs
        assert call_kwargs["retriever"] == mock_search_service
        assert call_kwargs["db_pool"] == mock_db_pool
        assert call_kwargs["web_search_client"] is None

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @patch("services.routing.intelligent_router.logger")
    def test_init_logs_success(self, mock_logger, mock_create_agentic_rag):
        """Test that initialization logs success message."""
        # Arrange
        mock_create_agentic_rag.return_value = MagicMock()

        # Act
        IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Assert
        mock_logger.info.assert_called_once_with(
            "🎯 [IntelligentRouter] Initialized (NEXT-GEN AGENTIC RAG MODE)"
        )


class TestIntelligentRouterInitialize:
    """Test async initialize method."""

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_create_agentic_rag):
        """Test successful async initialization."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.initialize = AsyncMock()
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        await router.initialize()

        # Assert
        mock_orchestrator.initialize.assert_called_once()

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_initialize_propagates_error(self, mock_create_agentic_rag):
        """Test that initialization errors are propagated."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.initialize = AsyncMock(side_effect=ValueError("Init failed"))
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(ValueError, match="Init failed"):
            await router.initialize()


class TestIntelligentRouterRouteChat:
    """Test route_chat method."""

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_success_minimal(self, mock_create_agentic_rag):
        """Test successful route_chat with minimal parameters."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "This is the answer",
                "sources": [{"title": "Source 1", "url": "http://example.com"}],
            }
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="Hello", user_id="user123")

        # Assert
        assert result["response"] == "This is the answer"
        assert result["ai_used"] == "agentic-rag"
        assert result["category"] == "agentic"
        assert result["model"] == "gemini-3-flash-preview"
        assert result["tokens"] == {}
        assert result["used_rag"] is True
        assert result["used_tools"] is False
        assert result["tools_called"] == []
        assert result["sources"] == [{"title": "Source 1", "url": "http://example.com"}]

        mock_orchestrator.process_query.assert_called_once_with(
            query="Hello", user_id="user123", conversation_history=None
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_success_all_params(self, mock_create_agentic_rag):
        """Test successful route_chat with all parameters."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "Detailed answer",
                "sources": [{"title": "Doc 1"}],
            }
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        conversation_history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        memory = {"key": "value"}
        emotional_profile = {"state": "happy"}
        collaborator = {"name": "Alice"}
        frontend_tools = [{"name": "tool1"}]

        # Act
        result = await router.route_chat(
            message="What is PT PMA?",
            user_id="user456",
            conversation_history=conversation_history,
            memory=memory,
            emotional_profile=emotional_profile,
            _last_ai_used="gemini",
            collaborator=collaborator,
            frontend_tools=frontend_tools,
        )

        # Assert
        assert result["response"] == "Detailed answer"
        assert result["sources"] == [{"title": "Doc 1"}]

        # The implementation now passes conversation_history to process_query
        mock_orchestrator.process_query.assert_called_once_with(
            query="What is PT PMA?", user_id="user456", conversation_history=conversation_history
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_empty_sources(self, mock_create_agentic_rag):
        """Test route_chat when orchestrator returns empty sources."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "Answer without sources",
                "sources": [],
            }
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="Test", user_id="user789")

        # Assert
        assert result["sources"] == []

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @patch("services.routing.intelligent_router.logger")
    @pytest.mark.asyncio
    async def test_route_chat_logs_routing(self, mock_logger, mock_create_agentic_rag):
        """Test that route_chat logs routing information."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(return_value={"answer": "Test", "sources": []})
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        await router.route_chat(message="Hello", user_id="test_user")

        # Assert
        mock_logger.info.assert_any_call(
            "🚦 [Router] Routing message for user test_user via Agentic RAG"
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_exception(self, mock_create_agentic_rag):
        """Test route_chat when orchestrator raises an exception."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            side_effect=ValueError("Database connection failed")
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(Exception, match="Routing failed: Database connection failed"):
            await router.route_chat(message="Test", user_id="user123")

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @patch("services.routing.intelligent_router.logger")
    @pytest.mark.asyncio
    async def test_route_chat_logs_error(self, mock_logger, mock_create_agentic_rag):
        """Test that route_chat logs errors."""
        # Arrange
        mock_orchestrator = MagicMock()
        error = RuntimeError("Test error")
        mock_orchestrator.process_query = AsyncMock(side_effect=error)
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(Exception):
            await router.route_chat(message="Test", user_id="user123")

        mock_logger.error.assert_called_once()
        assert "❌ [Router] Routing error:" in str(mock_logger.error.call_args)

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_timeout(self, mock_create_agentic_rag):
        """Test route_chat when orchestrator times out."""
        # Arrange
        import asyncio

        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            side_effect=asyncio.TimeoutError("Query timeout")
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(Exception, match="Routing failed: Query timeout"):
            await router.route_chat(message="Test", user_id="user123")

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_none_user_id(self, mock_create_agentic_rag):
        """Test route_chat with None user_id (anonymous)."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={"answer": "Anonymous answer", "sources": []}
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="Test", user_id=None)

        # Assert
        assert result["response"] == "Anonymous answer"
        mock_orchestrator.process_query.assert_called_once_with(
            query="Test", user_id=None, conversation_history=None
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_preserves_orchestrator_result_structure(
        self, mock_create_agentic_rag
    ):
        """Test that route_chat correctly transforms orchestrator result."""
        # Arrange
        mock_orchestrator = MagicMock()
        orchestrator_result = {
            "answer": "Complex answer with sources",
            "sources": [
                {"title": "Source 1", "url": "http://example1.com", "score": 0.95},
                {"title": "Source 2", "url": "http://example2.com", "score": 0.87},
            ],
            "execution_time": 1.234,
            "route_used": "agentic-rag (gemini-2.0-flash)",
            "steps": [{"step": 1, "thought": "Searching..."}],
            "tools_called": 1,
            "total_steps": 2,
        }
        mock_orchestrator.process_query = AsyncMock(return_value=orchestrator_result)
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="Test", user_id="user123")

        # Assert
        assert result["response"] == "Complex answer with sources"
        assert len(result["sources"]) == 2
        assert result["sources"][0]["title"] == "Source 1"
        assert result["sources"][1]["score"] == 0.87


class TestIntelligentRouterStreamChat:
    """Test stream_chat method."""

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_success(self, mock_create_agentic_rag):
        """Test successful stream_chat."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "metadata", "data": {"status": "started"}}
            yield {"type": "token", "data": "Hello"}
            yield {"type": "token", "data": " world"}
            yield {"type": "sources", "data": [{"title": "Source 1"}]}
            yield {"type": "done", "data": None}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        chunks = []
        async for chunk in router.stream_chat(message="Test", user_id="user123"):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 5
        assert chunks[0]["type"] == "metadata"
        assert chunks[1]["type"] == "token"
        assert chunks[1]["data"] == "Hello"
        assert chunks[2]["data"] == " world"
        assert chunks[3]["type"] == "sources"
        assert chunks[4]["type"] == "done"

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_minimal_params(self, mock_create_agentic_rag):
        """Test stream_chat with minimal parameters."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Response"}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        chunks = []
        async for chunk in router.stream_chat(message="Test", user_id="user123"):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 1
        assert chunks[0]["data"] == "Response"

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_all_params(self, mock_create_agentic_rag):
        """Test stream_chat with all parameters."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Test"}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        conversation_history = [{"role": "user", "content": "Hi"}]
        memory = {"facts": ["User likes coffee"]}
        collaborator = {"name": "Bob"}

        # Act
        chunks = []
        async for chunk in router.stream_chat(
            message="Test",
            user_id="user456",
            conversation_history=conversation_history,
            memory=memory,
            collaborator=collaborator,
        ):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 1

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @patch("services.routing.intelligent_router.logger")
    @pytest.mark.asyncio
    async def test_stream_chat_logs_start(self, mock_logger, mock_create_agentic_rag):
        """Test that stream_chat logs start message."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Test"}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        async for _ in router.stream_chat(message="Test", user_id="user789"):
            pass

        # Assert
        mock_logger.info.assert_any_call(
            "🚦 [Router Stream] Starting stream for user user789 via Agentic RAG"
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @patch("services.routing.intelligent_router.logger")
    @pytest.mark.asyncio
    async def test_stream_chat_logs_completion(self, mock_logger, mock_create_agentic_rag):
        """Test that stream_chat logs completion message."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Done"}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        async for _ in router.stream_chat(message="Test", user_id="user123"):
            pass

        # Assert
        mock_logger.info.assert_any_call("✅ [Router Stream] Completed")

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_orchestrator_exception(self, mock_create_agentic_rag):
        """Test stream_chat when orchestrator raises an exception."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Start"}
            raise ValueError("Stream error")

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(Exception, match="Streaming failed"):
            async for _ in router.stream_chat(message="Test", user_id="user123"):
                pass

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @patch("services.routing.intelligent_router.logger")
    @pytest.mark.asyncio
    async def test_stream_chat_logs_error(self, mock_logger, mock_create_agentic_rag):
        """Test that stream_chat logs errors."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            raise RuntimeError("Streaming failed")
            yield  # Never reached, but makes it a generator

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(Exception):
            async for _ in router.stream_chat(message="Test", user_id="user123"):
                pass

        mock_logger.error.assert_called_once()
        assert "❌ [Router Stream] Error:" in str(mock_logger.error.call_args)

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_empty_stream(self, mock_create_agentic_rag):
        """Test stream_chat with empty stream."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            return
            yield  # Never reached

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        chunks = []
        async for chunk in router.stream_chat(message="Test", user_id="user123"):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 0

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_passes_through_all_chunk_types(self, mock_create_agentic_rag):
        """Test that stream_chat passes through all chunk types correctly."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "metadata", "data": {"status": "started", "model": "gemini"}}
            yield {"type": "status", "data": "Step 1: Thinking..."}
            yield {"type": "tool_start", "data": {"name": "vector_search"}}
            yield {"type": "tool_end", "data": {"result": "Found 5 documents"}}
            yield {"type": "token", "data": "The "}
            yield {"type": "token", "data": "answer "}
            yield {"type": "token", "data": "is..."}
            yield {"type": "sources", "data": [{"id": 1, "title": "Doc 1"}]}
            yield {
                "type": "metadata",
                "data": {"status": "completed", "execution_time": 2.5},
            }
            yield {"type": "done", "data": {"final_answer": "Complete"}}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        chunks = []
        async for chunk in router.stream_chat(message="Test", user_id="user123"):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 10
        assert chunks[0]["type"] == "metadata"
        assert chunks[1]["type"] == "status"
        assert chunks[2]["type"] == "tool_start"
        assert chunks[3]["type"] == "tool_end"
        assert chunks[4]["type"] == "token"
        assert chunks[7]["type"] == "sources"
        assert chunks[9]["type"] == "done"

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_none_conversation_history(self, mock_create_agentic_rag):
        """Test stream_chat with None conversation_history."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Response"}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        chunks = []
        async for chunk in router.stream_chat(
            message="Test", user_id="user123", conversation_history=None
        ):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 1


class TestIntelligentRouterGetStats:
    """Test get_stats method."""

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_get_stats_returns_correct_structure(self, mock_create_agentic_rag):
        """Test that get_stats returns the correct structure."""
        # Arrange
        mock_create_agentic_rag.return_value = MagicMock()
        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        stats = router.get_stats()

        # Assert
        assert "router" in stats
        assert "model" in stats
        assert "rag_available" in stats
        assert stats["router"] == "agentic_rag_wrapper"
        assert stats["model"] == "gemini-3-flash-preview"
        assert stats["rag_available"] is True

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_get_stats_returns_dict(self, mock_create_agentic_rag):
        """Test that get_stats returns a dictionary."""
        # Arrange
        mock_create_agentic_rag.return_value = MagicMock()
        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        stats = router.get_stats()

        # Assert
        assert isinstance(stats, dict)

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_get_stats_values(self, mock_create_agentic_rag):
        """Test get_stats returns expected values."""
        # Arrange
        mock_create_agentic_rag.return_value = MagicMock()
        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        stats = router.get_stats()

        # Assert
        assert stats == {
            "router": "agentic_rag_wrapper",
            "model": "gemini-3-flash-preview",
            "rag_available": True,
        }

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_get_stats_immutability(self, mock_create_agentic_rag):
        """Test that get_stats returns a new dict each time."""
        # Arrange
        mock_create_agentic_rag.return_value = MagicMock()
        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        stats1 = router.get_stats()
        stats2 = router.get_stats()

        # Assert
        assert stats1 == stats2
        assert stats1 is not stats2  # Different objects


class TestIntelligentRouterEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_with_empty_message(self, mock_create_agentic_rag):
        """Test route_chat with empty message."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={"answer": "Please provide a question", "sources": []}
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="", user_id="user123")

        # Assert
        assert "response" in result
        mock_orchestrator.process_query.assert_called_once_with(
            query="", user_id="user123", conversation_history=None
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_with_very_long_message(self, mock_create_agentic_rag):
        """Test route_chat with very long message."""
        # Arrange
        long_message = "A" * 10000
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={"answer": "Processed long message", "sources": []}
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message=long_message, user_id="user123")

        # Assert
        assert result["response"] == "Processed long message"
        mock_orchestrator.process_query.assert_called_once_with(
            query=long_message, user_id="user123", conversation_history=None
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_with_special_characters(self, mock_create_agentic_rag):
        """Test route_chat with special characters in message."""
        # Arrange
        message_with_special_chars = "What is <script>alert('test')</script> PT PMA?"
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={"answer": "Safe response", "sources": []}
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message=message_with_special_chars, user_id="user123")

        # Assert
        assert result["response"] == "Safe response"

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_with_empty_user_id(self, mock_create_agentic_rag):
        """Test route_chat with empty user_id string."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={"answer": "Response", "sources": []}
        )
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="Test", user_id="")

        # Assert
        assert "response" in result
        mock_orchestrator.process_query.assert_called_once_with(
            query="Test", user_id="", conversation_history=None
        )

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_stream_chat_with_none_memory(self, mock_create_agentic_rag):
        """Test stream_chat with None memory."""

        # Arrange
        async def mock_stream(query, user_id, conversation_history=None, session_id=None):
            yield {"type": "token", "data": "Test"}

        mock_orchestrator = MagicMock()
        mock_orchestrator.stream_query = mock_stream
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        chunks = []
        async for chunk in router.stream_chat(message="Test", user_id="user123", memory=None):
            chunks.append(chunk)

        # Assert
        assert len(chunks) == 1

    @patch("services.routing.intelligent_router.create_agentic_rag")
    def test_init_with_none_db_pool(self, mock_create_agentic_rag):
        """Test initialization with None db_pool."""
        # Arrange
        mock_search_service = MagicMock()
        mock_create_agentic_rag.return_value = MagicMock()

        # Act
        router = IntelligentRouter(search_service=mock_search_service, db_pool=None)

        # Assert
        assert router.orchestrator is not None
        # Verify call was made with correct arguments
        call_args = mock_create_agentic_rag.call_args
        assert call_args.kwargs["retriever"] == mock_search_service
        assert call_args.kwargs["db_pool"] is None
        assert call_args.kwargs["web_search_client"] is None

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_returns_none_answer(self, mock_create_agentic_rag):
        """Test route_chat when orchestrator returns None as answer."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(return_value={"answer": None, "sources": []})
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act
        result = await router.route_chat(message="Test", user_id="user123")

        # Assert
        assert result["response"] is None

    @patch("services.routing.intelligent_router.create_agentic_rag")
    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_missing_sources_key(self, mock_create_agentic_rag):
        """Test route_chat when orchestrator result doesn't have sources key."""
        # Arrange
        mock_orchestrator = MagicMock()
        mock_orchestrator.process_query = AsyncMock(side_effect=KeyError("sources"))
        mock_create_agentic_rag.return_value = mock_orchestrator

        router = IntelligentRouter(search_service=MagicMock(), db_pool=MagicMock())

        # Act & Assert
        with pytest.raises(Exception, match="Routing failed"):
            await router.route_chat(message="Test", user_id="user123")

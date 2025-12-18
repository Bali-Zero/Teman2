"""
Comprehensive Tests for Agentic RAG Router - Target 95% Coverage
Tests all endpoints, functions, error paths, and edge cases
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Request

# ============================================================================
# PYDANTIC MODEL TESTS
# ============================================================================


class TestPydanticModels:
    """Test Pydantic model definitions"""

    def test_conversation_message_input(self):
        """Test ConversationMessageInput model"""
        from backend.app.routers.agentic_rag import ConversationMessageInput

        msg = ConversationMessageInput(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_agentic_query_request_minimal(self):
        """Test AgenticQueryRequest with minimal fields"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest

        request = AgenticQueryRequest(query="What is KITAS?")
        assert request.query == "What is KITAS?"
        assert request.user_id == "anonymous"
        assert request.enable_vision is False

    def test_agentic_query_request_full(self):
        """Test AgenticQueryRequest with all fields"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, ConversationMessageInput

        history = [
            ConversationMessageInput(role="user", content="Hello"),
            ConversationMessageInput(role="assistant", content="Hi!"),
        ]

        request = AgenticQueryRequest(
            query="What is KITAS?",
            user_id="test@example.com",
            enable_vision=True,
            session_id="session-123",
            conversation_id=1,
            conversation_history=history,
        )

        assert request.query == "What is KITAS?"
        assert request.user_id == "test@example.com"
        assert request.enable_vision is True
        assert request.session_id == "session-123"
        assert request.conversation_id == 1
        assert len(request.conversation_history) == 2

    def test_agentic_query_response(self):
        """Test AgenticQueryResponse model"""
        from backend.app.routers.agentic_rag import AgenticQueryResponse

        response = AgenticQueryResponse(
            answer="KITAS is a limited stay permit",
            sources=["doc1", "doc2"],
            context_length=500,
            execution_time=0.5,
            route_used="agentic-rag",
        )

        assert response.answer == "KITAS is a limited stay permit"
        assert len(response.sources) == 2
        assert response.context_length == 500
        assert response.execution_time == 0.5
        assert response.route_used == "agentic-rag"


# ============================================================================
# GET ORCHESTRATOR TESTS
# ============================================================================


class TestGetOrchestrator:
    """Test get_orchestrator dependency"""

    @pytest.mark.asyncio
    async def test_get_orchestrator_creates_new(self):
        """Test get_orchestrator creates new instance when none exists"""
        import backend.app.routers.agentic_rag as module

        # Reset global
        module._orchestrator = None

        mock_request = Mock(spec=Request)
        mock_request.app.state.db_pool = Mock()
        mock_request.app.state.search_service = Mock()

        with patch("backend.app.routers.agentic_rag.create_agentic_rag") as mock_create:
            mock_orchestrator = Mock()
            mock_create.return_value = mock_orchestrator

            result = await module.get_orchestrator(mock_request)

            assert result == mock_orchestrator
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_orchestrator_returns_existing(self):
        """Test get_orchestrator returns existing instance"""
        import backend.app.routers.agentic_rag as module

        mock_orchestrator = Mock()
        module._orchestrator = mock_orchestrator

        mock_request = Mock(spec=Request)

        result = await module.get_orchestrator(mock_request)

        assert result == mock_orchestrator

    @pytest.mark.asyncio
    async def test_get_orchestrator_no_db_pool(self):
        """Test get_orchestrator handles missing db_pool"""
        import backend.app.routers.agentic_rag as module

        module._orchestrator = None

        mock_request = Mock(spec=Request)
        mock_request.app.state = Mock(spec=[])  # Empty state

        with patch("backend.app.routers.agentic_rag.create_agentic_rag") as mock_create:
            mock_orchestrator = Mock()
            mock_create.return_value = mock_orchestrator

            result = await module.get_orchestrator(mock_request)

            assert result == mock_orchestrator


# ============================================================================
# QUERY ENDPOINT TESTS
# ============================================================================


class TestQueryEndpoint:
    """Test query_agentic_rag endpoint"""

    @pytest.mark.asyncio
    async def test_query_endpoint_success(self):
        """Test successful query execution"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, query_agentic_rag

        request = AgenticQueryRequest(query="What is KITAS?", user_id="test@example.com")

        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "KITAS is a limited stay permit",
                "sources": ["doc1"],
                "context_used": 500,
                "execution_time": 0.5,
                "route_used": "agentic-rag",
            }
        )

        response = await query_agentic_rag(request, mock_orchestrator)

        assert response.answer == "KITAS is a limited stay permit"
        assert response.route_used == "agentic-rag"
        mock_orchestrator.process_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_endpoint_error(self):
        """Test query endpoint handles errors"""
        from fastapi import HTTPException

        from backend.app.routers.agentic_rag import AgenticQueryRequest, query_agentic_rag

        request = AgenticQueryRequest(query="Test", user_id="test@example.com")

        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Processing error"))

        with pytest.raises(HTTPException) as exc_info:
            await query_agentic_rag(request, mock_orchestrator)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_query_endpoint_anonymous_user(self):
        """Test query with anonymous user"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, query_agentic_rag

        request = AgenticQueryRequest(query="Test query")  # Default anonymous

        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "Answer",
                "sources": [],
                "context_used": 100,
                "execution_time": 0.1,
                "route_used": "agentic-rag",
            }
        )

        response = await query_agentic_rag(request, mock_orchestrator)

        assert response.answer == "Answer"
        # Verify anonymous user passed
        call_args = mock_orchestrator.process_query.call_args
        assert call_args.kwargs["user_id"] == "anonymous"


# ============================================================================
# CONVERSATION HISTORY HELPER TESTS
# ============================================================================


class TestGetConversationHistoryForAgentic:
    """Test get_conversation_history_for_agentic function"""

    @pytest.mark.asyncio
    async def test_no_db_pool(self):
        """Test returns empty when no db_pool"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id="session", user_id="user", db_pool=None
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_no_user_id(self):
        """Test returns empty when no user_id"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_pool = Mock()

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id="session", user_id=None, db_pool=mock_pool
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_with_conversation_id(self):
        """Test retrieval with conversation_id"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic
        from tests.conftest import create_mock_db_pool

        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.return_value = {
            "messages": json.dumps(
                [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
            )
        }

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="user@example.com", db_pool=mock_pool
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_with_session_id(self):
        """Test retrieval with session_id"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic
        from tests.conftest import create_mock_db_pool

        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.return_value = {"messages": [{"role": "user", "content": "Test"}]}

        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id="session-123",
            user_id="user@example.com",
            db_pool=mock_pool,
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_most_recent_conversation(self):
        """Test retrieval of most recent conversation"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic
        from tests.conftest import create_mock_db_pool

        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.return_value = {"messages": [{"role": "user", "content": "Recent"}]}

        result = await get_conversation_history_for_agentic(
            conversation_id=None, session_id=None, user_id="user@example.com", db_pool=mock_pool
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_user_id_to_email_conversion(self):
        """Test user_id to email conversion"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic
        from tests.conftest import create_mock_db_pool

        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.side_effect = [
            {"email": "found@example.com"},
            {"messages": [{"role": "user", "content": "Test"}]},
        ]

        result = await get_conversation_history_for_agentic(
            conversation_id=None, session_id=None, user_id="123", db_pool=mock_pool
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_no_messages_found(self):
        """Test when no messages found"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic
        from tests.conftest import create_mock_db_pool

        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.return_value = None

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="user@example.com", db_pool=mock_pool
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_db_error_handling(self):
        """Test handling of database errors"""
        from backend.app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_pool = Mock()
        mock_pool.acquire.side_effect = Exception("DB connection failed")

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="user@example.com", db_pool=mock_pool
        )

        assert result == []


# ============================================================================
# STREAM ENDPOINT TESTS
# ============================================================================


class TestStreamEndpoint:
    """Test stream_agentic_rag endpoint"""

    @pytest.mark.asyncio
    async def test_stream_with_frontend_history(self):
        """Test streaming with conversation_history from frontend"""
        from backend.app.routers.agentic_rag import (
            AgenticQueryRequest,
            ConversationMessageInput,
            stream_agentic_rag,
        )

        history = [
            ConversationMessageInput(role="user", content="Hello"),
            ConversationMessageInput(role="assistant", content="Hi!"),
        ]

        request = AgenticQueryRequest(
            query="What is KITAS?", user_id="test@example.com", conversation_history=history
        )

        mock_orchestrator = Mock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "metadata", "data": {"status": "started"}}
            yield {"type": "token", "data": "KITAS "}
            yield {"type": "token", "data": "is "}
            yield {"type": "done", "data": None}

        mock_orchestrator.stream_query = mock_stream

        response = await stream_agentic_rag(request, mock_orchestrator, db_pool=None)

        # Check it's a StreamingResponse
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_stream_with_db_history(self):
        """Test streaming with history from database"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, stream_agentic_rag
        from tests.conftest import create_mock_db_pool

        request = AgenticQueryRequest(
            query="What is KITAS?",
            user_id="test@example.com",
            conversation_id=1,
            conversation_history=None,
        )

        mock_orchestrator = Mock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "done", "data": None}

        mock_orchestrator.stream_query = mock_stream

        mock_pool, mock_conn = create_mock_db_pool()
        mock_conn.fetchrow.return_value = {"messages": []}

        response = await stream_agentic_rag(request, mock_orchestrator, db_pool=mock_pool)

        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_stream_error_handling_quota(self):
        """Test streaming handles quota exceeded errors"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, stream_agentic_rag

        request = AgenticQueryRequest(query="Test", user_id="test@example.com")

        mock_orchestrator = Mock()

        async def mock_stream_error(*args, **kwargs):
            raise Exception("429 ResourceExhausted")

        mock_orchestrator.stream_query = mock_stream_error

        response = await stream_agentic_rag(request, mock_orchestrator, db_pool=None)

        # Should still return StreamingResponse (error handled inside generator)
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_stream_error_handling_service_unavailable(self):
        """Test streaming handles service unavailable errors"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, stream_agentic_rag

        request = AgenticQueryRequest(query="Test", user_id="test@example.com")

        mock_orchestrator = Mock()

        async def mock_stream_error(*args, **kwargs):
            raise Exception("503 ServiceUnavailable")

        mock_orchestrator.stream_query = mock_stream_error

        response = await stream_agentic_rag(request, mock_orchestrator, db_pool=None)

        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_stream_no_history(self):
        """Test streaming without any history"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, stream_agentic_rag

        request = AgenticQueryRequest(query="What is KITAS?", user_id="anonymous")

        mock_orchestrator = Mock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "metadata", "data": {"status": "started"}}
            yield {"type": "done", "data": None}

        mock_orchestrator.stream_query = mock_stream

        response = await stream_agentic_rag(request, mock_orchestrator, db_pool=None)

        assert response.media_type == "text/event-stream"


# ============================================================================
# ROUTER CONFIGURATION TESTS
# ============================================================================


class TestRouterConfiguration:
    """Test router configuration"""

    def test_router_exists(self):
        """Test router is properly configured"""
        from backend.app.routers.agentic_rag import router

        assert router is not None
        assert router.prefix == "/api/agentic-rag"

    def test_router_has_endpoints(self):
        """Test router has expected endpoints"""
        from backend.app.routers.agentic_rag import router

        routes = [r.path for r in router.routes]
        assert "/query" in routes or any("/query" in str(r) for r in routes)
        assert "/stream" in routes or any("/stream" in str(r) for r in routes)

    def test_router_tags(self):
        """Test router has correct tags"""
        from backend.app.routers.agentic_rag import router

        assert "agentic-rag" in router.tags


# ============================================================================
# INTEGRATION-STYLE TESTS
# ============================================================================


class TestEndpointIntegration:
    """Integration-style tests for endpoints"""

    @pytest.mark.asyncio
    async def test_full_query_flow(self):
        """Test complete query flow"""
        from backend.app.routers.agentic_rag import (
            AgenticQueryRequest,
            ConversationMessageInput,
            query_agentic_rag,
        )

        history = [
            ConversationMessageInput(role="user", content="Mi chiamo Marco"),
            ConversationMessageInput(role="assistant", content="Ciao Marco!"),
        ]

        request = AgenticQueryRequest(
            query="Come mi chiamo?",
            user_id="marco@example.com",
            session_id="test-session",
            conversation_history=history,
        )

        mock_orchestrator = Mock()
        mock_orchestrator.process_query = AsyncMock(
            return_value={
                "answer": "Ti chiami Marco!",
                "sources": [],
                "context_used": 100,
                "execution_time": 0.2,
                "route_used": "agentic-rag",
            }
        )

        response = await query_agentic_rag(request, mock_orchestrator)

        assert "Marco" in response.answer

    @pytest.mark.asyncio
    async def test_stream_with_tool_events(self):
        """Test streaming with tool call events"""
        from backend.app.routers.agentic_rag import AgenticQueryRequest, stream_agentic_rag

        request = AgenticQueryRequest(query="Calculate 5+5", user_id="test@example.com")

        mock_orchestrator = Mock()

        async def mock_stream(*args, **kwargs):
            yield {"type": "metadata", "data": {"status": "started", "model": "gemini-2.0-flash"}}
            yield {"type": "status", "data": "Step 1: Thinking..."}
            yield {
                "type": "tool_start",
                "data": {"name": "calculator", "args": {"expression": "5+5"}},
            }
            yield {"type": "tool_end", "data": {"result": "10"}}
            yield {"type": "token", "data": "The "}
            yield {"type": "token", "data": "result "}
            yield {"type": "token", "data": "is "}
            yield {"type": "token", "data": "10."}
            yield {"type": "done", "data": None}

        mock_orchestrator.stream_query = mock_stream

        response = await stream_agentic_rag(request, mock_orchestrator, db_pool=None)

        # Verify response type and headers
        assert response.media_type == "text/event-stream"
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("X-Accel-Buffering") == "no"

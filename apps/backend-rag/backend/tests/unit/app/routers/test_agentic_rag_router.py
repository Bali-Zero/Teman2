"""
Unit tests for Agentic RAG Router
Target: 100% coverage
Composer: 2
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.agentic_rag import (
    router, get_orchestrator, AgenticQueryRequest, AgenticQueryResponse,
    clean_image_generation_response, get_conversation_history_for_agentic
)


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock(spec=Request)
    request.app.state = MagicMock()
    request.app.state.db_pool = AsyncMock()
    request.app.state.search_service = MagicMock()
    return request


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator"""
    orchestrator = AsyncMock()
    orchestrator.process_query = AsyncMock(return_value=MagicMock(
        answer="test answer",
        sources=[],
        document_count=5,
        timings={"total": 1.0},
        route_used="flash",
        tools_called=["tool1"],
        model_used="gemini-3-flash",
        cache_hit=False
    ))
    return orchestrator


@pytest.fixture
def mock_current_user():
    """Mock current user"""
    return {"email": "test@example.com", "user_id": "123"}


class TestAgenticRagRouter:
    """Tests for Agentic RAG Router"""

    @pytest.mark.asyncio
    async def test_get_orchestrator_creates_new(self, mock_request):
        """Test orchestrator creation"""
        with patch("app.routers.agentic_rag.create_agentic_rag") as mock_create:
            mock_create.return_value = MagicMock()
            orchestrator = await get_orchestrator(mock_request)
            assert orchestrator is not None

    @pytest.mark.asyncio
    async def test_get_orchestrator_reuses_existing(self, mock_request):
        """Test orchestrator reuse"""
        existing = MagicMock()
        with patch("app.routers.agentic_rag._orchestrator", existing):
            orchestrator = await get_orchestrator(mock_request)
            assert orchestrator == existing

    def test_clean_image_generation_response_no_pollinations(self):
        """Test cleaning response without pollinations"""
        text = "This is a normal response"
        result = clean_image_generation_response(text)
        assert result == text

    def test_clean_image_generation_response_with_pollinations(self):
        """Test cleaning response with pollinations URL"""
        text = "Here is the image: https://pollinations.ai/image.jpg"
        result = clean_image_generation_response(text)
        assert "pollinations" not in result.lower()

    def test_clean_image_generation_response_version_patterns(self):
        """Test cleaning version patterns"""
        # Include pollinations to trigger cleaning
        # Add enough content so it doesn't get replaced by default message
        text = "https://pollinations.ai/image.jpg\n1. Versione 1\n2. Versione 2\nThis is the actual content that should remain in the response after cleaning."
        result = clean_image_generation_response(text)
        assert "Versione" not in result
        assert "actual content" in result  # Content should remain

    @pytest.mark.asyncio
    async def test_query_endpoint_success(self, mock_orchestrator, mock_current_user):
        """Test successful query endpoint"""
        request_data = AgenticQueryRequest(query="What is KITAS?")
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=None):
            
            from app.routers.agentic_rag import query_agentic_rag
            
            result = await query_agentic_rag(
                request=request_data,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None
            )
            
            assert isinstance(result, AgenticQueryResponse)
            assert result.answer == "test answer"

    @pytest.mark.asyncio
    async def test_query_endpoint_with_conversation_history(self, mock_orchestrator, mock_current_user):
        """Test query with conversation history"""
        request_data = AgenticQueryRequest(
            query="Tell me more",
            conversation_history=[
                {"role": "user", "content": "What is KITAS?"},
                {"role": "assistant", "content": "KITAS is a work permit"}
            ]
        )
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator):
            
            from app.routers.agentic_rag import query_agentic_rag
            
            result = await query_agentic_rag(
                request=request_data,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_query_endpoint_error_handling(self, mock_orchestrator, mock_current_user):
        """Test error handling"""
        request_data = AgenticQueryRequest(query="test")
        mock_orchestrator.process_query.side_effect = Exception("Error")
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator):
            
            from app.routers.agentic_rag import query_agentic_rag
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException):
                await query_agentic_rag(
                    request=request_data,
                    current_user=mock_current_user,
                    orchestrator=mock_orchestrator,
                    db_pool=None
                )

    @pytest.mark.asyncio
    async def test_get_conversation_history_for_agentic_with_conversation_id(self):
        """Test getting history by conversation ID"""
        from contextlib import asynccontextmanager
        
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock fetchrow to return messages - use dict-like object
        messages = [
            {"role": "user", "content": "test", "created_at": "2024-01-01"}
        ]
        # Create a dict-like object that supports both .get() and [] access
        class MockRow(dict):
            def __init__(self, messages):
                super().__init__()
                self["messages"] = messages
        
        mock_row = MockRow(messages)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        
        # Create proper async context manager mock
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        mock_db.acquire = acquire
        
        result = await get_conversation_history_for_agentic(
            conversation_id=123,
            session_id=None,
            user_id="test@example.com",
            db_pool=mock_db
        )
        
        assert len(result) > 0
        assert result == messages

    @pytest.mark.asyncio
    async def test_get_conversation_history_for_agentic_with_session_id(self):
        """Test getting history by session ID"""
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        mock_db.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetch.return_value = []
        
        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id="session-123",
            user_id="test@example.com",
            db_pool=mock_db
        )
        
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_conversation_history_for_agentic_no_db(self):
        """Test getting history without DB"""
        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id=None,
            user_id="test@example.com",
            db_pool=None
        )
        
        assert result == []


class TestAgenticQueryRequest:
    """Tests for AgenticQueryRequest model"""

    def test_request_creation(self):
        """Test request creation"""
        request = AgenticQueryRequest(query="test")
        assert request.query == "test"
        assert request.user_id == "anonymous"

    def test_request_with_images(self):
        """Test request with images"""
        request = AgenticQueryRequest(
            query="test",
            images=[{"base64": "data:image/png;base64,...", "name": "test.png"}]
        )
        assert len(request.images) == 1


class TestAgenticQueryResponse:
    """Tests for AgenticQueryResponse model"""

    def test_response_creation(self):
        """Test response creation"""
        response = AgenticQueryResponse(
            answer="test",
            sources=[],
            context_length=5,
            execution_time=1.0,
            route_used="flash"
        )
        assert response.answer == "test"
        assert response.tools_called == 0
        assert response.route_used == "flash"

    @pytest.mark.asyncio
    async def test_get_conversation_history_with_user_id_not_email(self):
        """Test getting history when user_id is not an email"""
        from contextlib import asynccontextmanager
        
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        
        # Mock email lookup
        mock_email_row = MagicMock()
        mock_email_row.get.return_value = "found@example.com"
        mock_conn.fetchrow = AsyncMock(side_effect=[
            mock_email_row,  # Email lookup
            None  # No conversation found
        ])
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        mock_db.acquire = acquire
        
        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id=None,
            user_id="user123",  # Not an email
            db_pool=mock_db
        )
        
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_conversation_history_most_recent(self):
        """Test getting most recent conversation"""
        from contextlib import asynccontextmanager
        
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        
        messages = [{"role": "user", "content": "test"}]
        # Create a proper dict-like object
        class MockRow(dict):
            def __init__(self, messages):
                super().__init__()
                self["messages"] = messages
        
        mock_row = MockRow(messages)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        mock_db.acquire = acquire
        
        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id=None,
            user_id="test@example.com",
            db_pool=mock_db
        )
        
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_conversation_history_json_string(self):
        """Test getting history with JSON string messages"""
        from contextlib import asynccontextmanager
        import json
        
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        
        messages = [{"role": "user", "content": "test"}]
        # Create a proper dict-like object with JSON string
        class MockRow(dict):
            def __init__(self, messages_json):
                super().__init__()
                self["messages"] = messages_json
        
        mock_row = MockRow(json.dumps(messages))  # JSON string
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        mock_db.acquire = acquire
        
        result = await get_conversation_history_for_agentic(
            conversation_id=123,
            session_id=None,
            user_id="test@example.com",
            db_pool=mock_db
        )
        
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_conversation_history_error(self):
        """Test error handling in get_conversation_history"""
        from contextlib import asynccontextmanager
        
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        mock_db.acquire = acquire
        
        result = await get_conversation_history_for_agentic(
            conversation_id=123,
            session_id=None,
            user_id="test@example.com",
            db_pool=mock_db
        )
        
        assert result == []

    @pytest.mark.asyncio
    async def test_query_endpoint_with_db_history(self, mock_orchestrator, mock_current_user):
        """Test query endpoint retrieving history from DB"""
        from contextlib import asynccontextmanager
        
        mock_db = AsyncMock()
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.get.return_value = [{"role": "user", "content": "previous"}]
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        
        @asynccontextmanager
        async def acquire():
            yield mock_conn
        
        mock_db.acquire = acquire
        
        request_data = AgenticQueryRequest(
            query="Tell me more",
            conversation_id=123
        )
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=mock_db):
            
            from app.routers.agentic_rag import query_agentic_rag
            
            result = await query_agentic_rag(
                request=request_data,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=mock_db
            )
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_stream_endpoint_success(self, mock_orchestrator, mock_current_user):
        """Test stream endpoint success"""
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-correlation-id"
        mock_request.is_disconnected = AsyncMock(return_value=False)
        
        request_data = AgenticQueryRequest(query="test query")
        
        # Mock stream_query to yield events
        async def mock_stream():
            yield {"type": "token", "data": "test"}
            yield {"type": "done", "data": "[DONE]"}
        
        mock_orchestrator.stream_query = AsyncMock(return_value=mock_stream())
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=None):
            
            from app.routers.agentic_rag import stream_agentic_rag
            
            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None
            )
            
            assert response is not None

    @pytest.mark.asyncio
    async def test_stream_endpoint_empty_query(self, mock_orchestrator, mock_current_user):
        """Test stream endpoint with empty query"""
        from fastapi import Request
        from contextlib import contextmanager
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = None
        mock_request.headers = {}
        mock_request.is_disconnected = AsyncMock(return_value=False)
        
        request_data = AgenticQueryRequest(query="")  # Empty query
        
        # Mock trace_span to return a synchronous context manager (as used in code)
        @contextmanager
        def mock_trace_span(*args, **kwargs):
            yield MagicMock()
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=None), \
             patch("app.routers.agentic_rag.trace_span", side_effect=mock_trace_span):
            from app.routers.agentic_rag import stream_agentic_rag
            from fastapi import HTTPException
            
            # The error is raised before the generator is created
            with pytest.raises(HTTPException) as exc_info:
                response = await stream_agentic_rag(
                    request_body=request_data,
                    http_request=mock_request,
                    current_user=mock_current_user,
                    orchestrator=mock_orchestrator,
                    db_pool=None
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_stream_endpoint_with_images(self, mock_orchestrator, mock_current_user):
        """Test stream endpoint with images"""
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-id"
        mock_request.is_disconnected = AsyncMock(return_value=False)
        
        request_data = AgenticQueryRequest(
            query="test",
            enable_vision=True,
            images=[{"base64": "data:image/png;base64,test", "name": "test.png"}]
        )
        
        async def mock_stream():
            yield {"type": "token", "data": "test"}
            yield {"type": "done", "data": "[DONE]"}
        
        mock_orchestrator.stream_query = AsyncMock(return_value=mock_stream())
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=None):
            
            from app.routers.agentic_rag import stream_agentic_rag
            
            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None
            )
            
            assert response is not None

    @pytest.mark.asyncio
    async def test_stream_endpoint_client_disconnect(self, mock_orchestrator, mock_current_user):
        """Test stream endpoint with client disconnect"""
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-id"
        mock_request.is_disconnected = AsyncMock(return_value=True)  # Disconnected
        
        request_data = AgenticQueryRequest(query="test")
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=None):
            
            from app.routers.agentic_rag import stream_agentic_rag
            
            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None
            )
            
            assert response is not None

    @pytest.mark.asyncio
    async def test_stream_endpoint_error_handling(self, mock_orchestrator, mock_current_user):
        """Test stream endpoint error handling"""
        from fastapi import Request
        
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        mock_request.state.correlation_id = "test-id"
        mock_request.is_disconnected = AsyncMock(return_value=False)
        
        request_data = AgenticQueryRequest(query="test")
        
        # Mock stream_query to raise exception
        mock_orchestrator.stream_query = AsyncMock(side_effect=Exception("Stream error"))
        
        with patch("app.routers.agentic_rag.get_current_user", return_value=mock_current_user), \
             patch("app.routers.agentic_rag.get_orchestrator", return_value=mock_orchestrator), \
             patch("app.routers.agentic_rag.get_optional_database_pool", return_value=None):
            
            from app.routers.agentic_rag import stream_agentic_rag
            
            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None
            )
            
            assert response is not None

    def test_clean_image_generation_response_short_text(self):
        """Test cleaning response that becomes too short"""
        text = "https://pollinations.ai/image.jpg"
        result = clean_image_generation_response(text)
        assert len(result) >= 20  # Should have default message

    def test_get_optional_database_pool_503(self):
        """Test get_optional_database_pool with 503 error"""
        from fastapi import HTTPException
        
        mock_request = MagicMock()
        
        with patch("app.routers.agentic_rag.get_database_pool", side_effect=HTTPException(status_code=503)):
            from app.routers.agentic_rag import get_optional_database_pool
            result = get_optional_database_pool(mock_request)
            assert result is None

    def test_get_optional_database_pool_other_error(self):
        """Test get_optional_database_pool with other error"""
        from fastapi import HTTPException
        
        mock_request = MagicMock()
        
        with patch("app.routers.agentic_rag.get_database_pool", side_effect=HTTPException(status_code=500)):
            from app.routers.agentic_rag import get_optional_database_pool
            
            with pytest.raises(HTTPException):
                get_optional_database_pool(mock_request)


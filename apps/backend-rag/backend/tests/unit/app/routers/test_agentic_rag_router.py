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

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.agentic_rag import (
    AgenticQueryRequest,
    AgenticQueryResponse,
    clean_image_generation_response,
    get_conversation_history_for_agentic,
    get_orchestrator,
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
    """Mock orchestrator - return object with concrete attributes (no MagicMock)"""
    result = MagicMock()
    result.answer = "test answer"
    result.sources = []
    result.document_count = 5
    result.timings = {"total": 1.0}
    result.route_used = "flash"
    result.tools_called = ["tool1"]
    result.model_used = "gemini-3-flash"
    result.cache_hit = False
    result.entities = {}
    result.reasoning = ""
    result.confidence_score = 0.9
    result.abstain_reason = None
    result.evidence_score = 0.9
    result.workflow = None

    orchestrator = AsyncMock()
    orchestrator.process_query = AsyncMock(return_value=result)
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
        with patch("backend.services.rag.agentic.create_agentic_rag") as mock_create:
            mock_create.return_value = MagicMock()
            import backend.app.dependencies as deps

            original = deps._agentic_rag_orchestrator
            deps._agentic_rag_orchestrator = None
            try:
                orchestrator = await get_orchestrator(mock_request)
                assert orchestrator is not None
            finally:
                deps._agentic_rag_orchestrator = original

    @pytest.mark.asyncio
    async def test_get_orchestrator_reuses_existing(self, mock_request):
        """Test orchestrator reuse — get_orchestrator is async, must be awaited."""
        existing = MagicMock()
        import backend.app.deps.orchestrator as orch_mod

        original = orch_mod._agentic_rag_orchestrator
        orch_mod._agentic_rag_orchestrator = existing
        try:
            orchestrator = await get_orchestrator(mock_request)
            assert orchestrator == existing
        finally:
            orch_mod._agentic_rag_orchestrator = original

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

        mock_metrics = AsyncMock()
        mock_ab_manager = MagicMock()
        mock_ab_manager.metrics_tracker = MagicMock()
        mock_ab_manager.metrics_tracker.record_query_metrics = mock_metrics
        mock_ab_manager.assign_variant = MagicMock(return_value="control")
        mock_ab_manager.get_variant_config = MagicMock(return_value={})

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            result = await query_agentic_rag(
                request=request_data,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
            )

            assert isinstance(result, AgenticQueryResponse)
            assert result.answer == "test answer"

    @pytest.mark.asyncio
    async def test_query_endpoint_surfaces_tool_names_and_keeps_the_count(
        self, mock_orchestrator, mock_current_user
    ):
        """The response must carry tool NAMES, and still carry the count.

        `tools_called` has always been `len(result.tools_called)` — a number.
        Measured 2026-08-11 on the live worker, that made an abstaining run
        indistinguishable from outside: `tools_called: 1` names nothing, so
        "why did one tool call yield evidence 0.0" could not be answered
        without guessing. `tools_used` carries the names.

        Both halves are asserted deliberately. Replacing the count with the
        list would be the tidier-looking change and would break every existing
        consumer that reads it as a number (`stress_test_zantara.py`, the
        red-team evaluator's older payload path, the analytics rows).
        """
        mock_orchestrator.process_query.return_value.tools_called = [
            "get_pricing",
            "vector_search",
        ]

        mock_ab_manager = MagicMock()
        mock_ab_manager.metrics_tracker = MagicMock()
        mock_ab_manager.metrics_tracker.record_query_metrics = AsyncMock()
        mock_ab_manager.assign_variant = MagicMock(return_value="control")
        mock_ab_manager.get_variant_config = MagicMock(return_value={})

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            result = await query_agentic_rag(
                request=AgenticQueryRequest(query="Quanto costa una PT PMA?"),
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
            )

        assert result.tools_used == ["get_pricing", "vector_search"]
        assert result.tools_called == 2

    @pytest.mark.asyncio
    async def test_query_endpoint_with_conversation_history(
        self,
        mock_orchestrator,
        mock_current_user,
    ):
        """Test query with conversation history"""
        request_data = AgenticQueryRequest(
            query="Tell me more",
            conversation_history=[
                {"role": "user", "content": "What is KITAS?"},
                {"role": "assistant", "content": "KITAS is a work permit"},
            ],
        )

        mock_metrics = AsyncMock()
        mock_ab_manager = MagicMock()
        mock_ab_manager.metrics_tracker = MagicMock()
        mock_ab_manager.metrics_tracker.record_query_metrics = mock_metrics
        mock_ab_manager.assign_variant = MagicMock(return_value="control")
        mock_ab_manager.get_variant_config = MagicMock(return_value={})

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            result = await query_agentic_rag(
                request=request_data,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_query_endpoint_error_handling(self, mock_orchestrator, mock_current_user):
        """Test error handling"""
        request_data = AgenticQueryRequest(query="test")
        mock_orchestrator.process_query.side_effect = Exception("Error")

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            from fastapi import HTTPException

            from backend.app.routers.agentic_rag import query_agentic_rag

            with pytest.raises(HTTPException):
                await query_agentic_rag(
                    request=request_data,
                    current_user=mock_current_user,
                    orchestrator=mock_orchestrator,
                    db_pool=None,
                )

    @pytest.mark.asyncio
    async def test_get_conversation_history_for_agentic_with_conversation_id(self):
        """Test getting history by conversation ID"""
        from contextlib import asynccontextmanager

        mock_db = AsyncMock()
        mock_conn = AsyncMock()

        # Mock fetchrow to return messages - use dict-like object
        messages = [{"role": "user", "content": "test", "created_at": "2024-01-01"}]

        # Create a dict-like object that supports both .get() and [] access
        class MockRow(dict):
            def __init__(self, messages) -> None:
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
            db_pool=mock_db,
        )

        assert len(result) > 0
        assert result == messages

    @pytest.mark.asyncio
    async def test_get_conversation_history_for_agentic_with_session_id(self):
        """Test getting history by session ID"""
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_db.acquire = MagicMock(return_value=acquire_cm)
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch.return_value = []

        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id="session-123",
            user_id="test@example.com",
            db_pool=mock_db,
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_conversation_history_for_agentic_no_db(self):
        """Test getting history without DB"""
        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id=None,
            user_id="test@example.com",
            db_pool=None,
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
            images=[{"base64": "data:image/png;base64,...", "name": "test.png"}],
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
            route_used="flash",
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
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                mock_email_row,  # Email lookup
                None,  # No conversation found
            ],
        )

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db.acquire = acquire

        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id=None,
            user_id="user123",  # Not an email
            db_pool=mock_db,
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
            def __init__(self, messages) -> None:
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
            db_pool=mock_db,
        )

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_conversation_history_json_string(self):
        """Test getting history with JSON string messages"""
        import json
        from contextlib import asynccontextmanager

        mock_db = AsyncMock()
        mock_conn = AsyncMock()

        messages = [{"role": "user", "content": "test"}]

        # Create a proper dict-like object with JSON string
        class MockRow(dict):
            def __init__(self, messages_json) -> None:
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
            db_pool=mock_db,
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
            db_pool=mock_db,
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

        request_data = AgenticQueryRequest(query="Tell me more", conversation_id=123)

        mock_metrics = AsyncMock()
        mock_ab_manager = MagicMock()
        mock_ab_manager.metrics_tracker = MagicMock()
        mock_ab_manager.metrics_tracker.record_query_metrics = mock_metrics
        mock_ab_manager.assign_variant = MagicMock(return_value="control")
        mock_ab_manager.get_variant_config = MagicMock(return_value={})

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=mock_db,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            result = await query_agentic_rag(
                request=request_data,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=mock_db,
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

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
        ):
            from backend.app.routers.agentic_rag import stream_agentic_rag

            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
            )

            assert response is not None

    @pytest.mark.asyncio
    async def test_stream_endpoint_empty_query(self, mock_orchestrator, mock_current_user):
        """Test stream endpoint with empty query"""
        from contextlib import contextmanager

        from fastapi import Request

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

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
            patch("backend.app.routers.agentic_rag.trace_span", side_effect=mock_trace_span),
        ):
            from fastapi import HTTPException

            from backend.app.routers.agentic_rag import stream_agentic_rag

            # The error is raised before the generator is created
            with pytest.raises(HTTPException) as exc_info:
                await stream_agentic_rag(
                    request_body=request_data,
                    http_request=mock_request,
                    current_user=mock_current_user,
                    orchestrator=mock_orchestrator,
                    db_pool=None,
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
            images=[{"base64": "data:image/png;base64,test", "name": "test.png"}],
        )

        async def mock_stream():
            yield {"type": "token", "data": "test"}
            yield {"type": "done", "data": "[DONE]"}

        mock_orchestrator.stream_query = AsyncMock(return_value=mock_stream())

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
        ):
            from backend.app.routers.agentic_rag import stream_agentic_rag

            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
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

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
        ):
            from backend.app.routers.agentic_rag import stream_agentic_rag

            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
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

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=mock_current_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
        ):
            from backend.app.routers.agentic_rag import stream_agentic_rag

            response = await stream_agentic_rag(
                request_body=request_data,
                http_request=mock_request,
                current_user=mock_current_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
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

        with patch(
            "backend.app.deps.database.get_database_pool",
            side_effect=HTTPException(status_code=503),
        ):
            from backend.app.dependencies import get_optional_database_pool

            result = get_optional_database_pool(mock_request)
            assert result is None

    def test_get_optional_database_pool_other_error(self):
        """Test get_optional_database_pool with other error"""
        from fastapi import HTTPException

        mock_request = MagicMock()

        with patch(
            "backend.app.deps.database.get_database_pool",
            side_effect=HTTPException(status_code=500),
        ):
            from backend.app.dependencies import get_optional_database_pool

            with pytest.raises(HTTPException):
                get_optional_database_pool(mock_request)


class TestExtractWhatsappPhone:
    """Pure-function coverage for `_extract_whatsapp_phone` — the gate that
    decides whether `_resolve_trusted_wa_profile` even attempts a DB lookup."""

    def test_whatsapp_shaped_user_id_extracts_phone(self):
        from backend.app.routers.agentic_rag import _extract_whatsapp_phone

        assert _extract_whatsapp_phone("whatsapp_628123456789") == "628123456789"

    def test_bare_shared_identity_is_not_whatsapp_shaped(self):
        """Innocence: the shared pseudo-identity's own `user_id` value
        must NOT itself parse as a phone."""
        from backend.app.routers.agentic_rag import _extract_whatsapp_phone

        assert _extract_whatsapp_phone("wa-mirror-internal") is None

    def test_none_and_empty_user_id(self):
        from backend.app.routers.agentic_rag import _extract_whatsapp_phone

        assert _extract_whatsapp_phone(None) is None
        assert _extract_whatsapp_phone("") is None
        assert _extract_whatsapp_phone("whatsapp_") is None


class TestResolveTrustedWaProfile:
    """P0-ID containment (2026-07-24, hardened same day after adversarial
    review): replaces the old client-supplied `profile` request field
    (removed — no longer exists on `AgenticQueryRequest`). A FIRST version
    of this fix re-derived the sender from a phone parsed out of the
    client-settable `user_id` field, gated only on the SHARED
    `role=="internal"` identity — an independent review found this was the
    identical forgery bug relocated, not closed: the owner's WA number is
    documented-public, so ANY holder of the shared `X-Internal-Key` could
    send `user_id="whatsapp_<owner number>"` and get the creator persona.
    The real fix gates resolution on `is_wa_inbox_bot` (see
    `_verify_wa_inbox_bot_profile_key` — a SECOND secret exclusive to
    wa_inbox_bot.py, never a request body field). These tests target
    `_resolve_trusted_wa_profile` directly with that boolean explicit."""

    @pytest.mark.asyncio
    async def test_owner_phone_yields_creator_profile(self):
        from backend.app.routers.agentic_rag import _resolve_trusted_wa_profile

        with patch(
            "backend.app.routers.agentic_rag.resolve_sender_identity",
            new=AsyncMock(return_value={"role": "owner"}),
        ):
            result = await _resolve_trusted_wa_profile(
                True, "whatsapp_62811000111", None
            )
        assert result == {"role": "creator"}

    @pytest.mark.asyncio
    async def test_team_phone_yields_team_profile_with_name_and_email(self):
        from backend.app.routers.agentic_rag import _resolve_trusted_wa_profile

        with patch(
            "backend.app.routers.agentic_rag.resolve_sender_identity",
            new=AsyncMock(
                return_value={
                    "role": "team",
                    "team_member": "Ari",
                    "team_member_email": "ari@balizero.com",
                }
            ),
        ):
            result = await _resolve_trusted_wa_profile(
                True, "whatsapp_62811000222", None
            )
        assert result == {"role": "team", "name": "Ari", "email": "ari@balizero.com"}

    @pytest.mark.asyncio
    async def test_client_or_unknown_phone_yields_no_override(self):
        """Innocence: a resolved client/unknown sender never gets a
        privileged persona, even WITH the dedicated bot key."""
        from backend.app.routers.agentic_rag import _resolve_trusted_wa_profile

        for identity in ({"role": "client", "client_id": 1}, {"role": "unknown"}):
            with patch(
                "backend.app.routers.agentic_rag.resolve_sender_identity",
                new=AsyncMock(return_value=identity),
            ):
                result = await _resolve_trusted_wa_profile(
                    True, "whatsapp_62899999999", None
                )
            assert result is None

    @pytest.mark.asyncio
    async def test_non_whatsapp_user_id_short_circuits_before_any_lookup(self):
        """Innocence: even WITH the dedicated bot key, no override — and no
        DB lookup at all — when `user_id` isn't WA-shaped."""
        from backend.app.routers.agentic_rag import _resolve_trusted_wa_profile

        mock_resolve = AsyncMock(return_value={"role": "owner"})
        with patch(
            "backend.app.routers.agentic_rag.resolve_sender_identity", new=mock_resolve
        ):
            result = await _resolve_trusted_wa_profile(True, "wa-mirror-internal", None)
        assert result is None
        mock_resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_without_dedicated_bot_key_no_override_even_with_owner_phone(self):
        """Guilt (the actual vulnerability this hardening closes): WITHOUT
        `is_wa_inbox_bot` — i.e. any caller lacking wa_inbox_bot.py's own
        dedicated secret, including one holding the SHARED `X-Internal-Key`
        and sending a WA-shaped `user_id` for the documented-public owner
        number — gets no override, and no DB lookup is even attempted.
        This is the exact payload the pre-hardening version would have
        granted a creator persona for."""
        from backend.app.routers.agentic_rag import _resolve_trusted_wa_profile

        mock_resolve = AsyncMock(return_value={"role": "owner"})
        with patch(
            "backend.app.routers.agentic_rag.resolve_sender_identity", new=mock_resolve
        ):
            result = await _resolve_trusted_wa_profile(
                False, "whatsapp_62811000111", None
            )
        assert result is None
        mock_resolve.assert_not_awaited()


class TestVerifyWaInboxBotProfileKey:
    """Direct coverage of the dedicated-secret gate itself."""

    @staticmethod
    def _request(header_value: str | None):
        req = MagicMock()
        req.headers = {"X-WA-Bot-Profile-Key": header_value} if header_value else {}
        return req

    @pytest.mark.asyncio
    async def test_matching_key_is_true(self):
        from backend.app.routers.agentic_rag import _verify_wa_inbox_bot_profile_key

        with patch(
            "backend.app.routers.agentic_rag.settings.wa_inbox_bot_profile_key",
            "s3cr3t",
        ):
            assert await _verify_wa_inbox_bot_profile_key(self._request("s3cr3t")) is True

    @pytest.mark.asyncio
    async def test_wrong_key_is_false(self):
        from backend.app.routers.agentic_rag import _verify_wa_inbox_bot_profile_key

        with patch(
            "backend.app.routers.agentic_rag.settings.wa_inbox_bot_profile_key",
            "s3cr3t",
        ):
            assert (
                await _verify_wa_inbox_bot_profile_key(self._request("wrong")) is False
            )

    @pytest.mark.asyncio
    async def test_missing_header_is_false(self):
        from backend.app.routers.agentic_rag import _verify_wa_inbox_bot_profile_key

        with patch(
            "backend.app.routers.agentic_rag.settings.wa_inbox_bot_profile_key",
            "s3cr3t",
        ):
            assert await _verify_wa_inbox_bot_profile_key(self._request(None)) is False

    @pytest.mark.asyncio
    async def test_unconfigured_secret_is_false_even_with_a_header(self):
        """Fail-safe: an unset secret must never accidentally match an
        empty/None header value."""
        from backend.app.routers.agentic_rag import _verify_wa_inbox_bot_profile_key

        with patch(
            "backend.app.routers.agentic_rag.settings.wa_inbox_bot_profile_key",
            None,
        ):
            assert await _verify_wa_inbox_bot_profile_key(self._request("")) is False


class TestWaTrustedProfileRouterWiring:
    """Router-level integration: `query_agentic_rag` must forward whatever
    `_resolve_trusted_wa_profile` returns to the orchestrator as `profile`,
    and the wire contract must no longer accept a client-declared one.
    `is_wa_inbox_bot` is passed explicitly since these tests call the route
    function directly (bypassing FastAPI's own dependency resolution)."""

    @staticmethod
    def _base_kwargs(mock_orchestrator, user_id, channel="whatsapp"):
        request_data = AgenticQueryRequest(query="Any question", channel=channel, user_id=user_id)
        mock_ab_manager = MagicMock()
        mock_ab_manager.metrics_tracker = MagicMock()
        mock_ab_manager.metrics_tracker.record_query_metrics = AsyncMock()
        mock_ab_manager.assign_variant = MagicMock(return_value="control")
        mock_ab_manager.get_variant_config = MagicMock(return_value={})
        return request_data, mock_ab_manager

    @pytest.mark.asyncio
    async def test_owner_phone_profile_reaches_orchestrator(self, mock_orchestrator):
        """Guilt: WITH the dedicated bot key + a phone that resolves to
        'owner' → creator profile forwarded to the orchestrator."""
        internal_user = {
            "role": "internal",
            "email": "wa-mirror-internal@balizero.com",
            "user_id": "wa-mirror-internal",
        }
        request_data, mock_ab_manager = self._base_kwargs(
            mock_orchestrator, "whatsapp_62811000111"
        )

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=internal_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=None,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
            patch(
                "backend.app.routers.agentic_rag.resolve_sender_identity",
                new=AsyncMock(return_value={"role": "owner"}),
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            await query_agentic_rag(
                request=request_data,
                current_user=internal_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
                is_wa_inbox_bot=True,
            )

        _, call_kwargs = mock_orchestrator.process_query.call_args
        assert call_kwargs.get("profile") == {"role": "creator"}

    @pytest.mark.asyncio
    async def test_shared_internal_key_alone_without_bot_key_gets_no_profile(
        self, mock_orchestrator
    ):
        """Guilt (the actual vulnerability this hardening closes): a caller
        with the SHARED `role=="internal"` identity but WITHOUT the
        dedicated bot key (`is_wa_inbox_bot=False`) — even sending the
        exact owner-phone-shaped `user_id` a real attacker would use — gets
        no profile at all."""
        internal_user = {
            "role": "internal",
            "email": "wa-mirror-internal@balizero.com",
            "user_id": "wa-mirror-internal",
        }
        request_data, mock_ab_manager = self._base_kwargs(
            mock_orchestrator, "whatsapp_62811000111"
        )
        mock_resolve = AsyncMock(return_value={"role": "owner"})

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=internal_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=None,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
            patch(
                "backend.app.routers.agentic_rag.resolve_sender_identity", new=mock_resolve
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            await query_agentic_rag(
                request=request_data,
                current_user=internal_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
                is_wa_inbox_bot=False,
            )

        _, call_kwargs = mock_orchestrator.process_query.call_args
        assert "profile" not in call_kwargs
        mock_resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_client_phone_no_profile_reaches_orchestrator(self, mock_orchestrator):
        """Innocence: a resolved client/unknown sender's request is
        completely unaffected — no `profile` key at all reaches the
        orchestrator, matching the pre-identity-wiring shape."""
        internal_user = {"role": "internal", "email": "wa-mirror-internal@balizero.com"}
        request_data, mock_ab_manager = self._base_kwargs(
            mock_orchestrator, "whatsapp_62899999999"
        )

        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=internal_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=None,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
            patch(
                "backend.app.routers.agentic_rag.resolve_sender_identity",
                new=AsyncMock(return_value={"role": "unknown"}),
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            await query_agentic_rag(
                request=request_data,
                current_user=internal_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
                is_wa_inbox_bot=True,
            )

        _, call_kwargs = mock_orchestrator.process_query.call_args
        assert "profile" not in call_kwargs

    def test_request_schema_has_no_client_declarable_profile_field(self):
        """Guilt: the old client-declared `profile` field is gone from the
        wire contract entirely — Pydantic silently drops an unknown
        `profile` key (default `extra="ignore"`), it can never reach the
        model, let alone influence identity."""
        req = AgenticQueryRequest(
            query="test",
            channel="whatsapp",
            **{"profile": {"role": "creator"}},
        )
        assert not hasattr(req, "profile")


class TestDeriveWaAgentRole:
    """T4 unified principal (spec `2026-07-24-zantara-bot-consultant-
    assistant-spec.md` §5 item T4 — "two parallel auth systems").
    `_derive_wa_agent_role` maps the already-trusted WA profile dict (the
    SAME shape `TestResolveTrustedWaProfile` above exercises — this
    function's only caller-shape) onto `team_agent_config`'s existing
    AgentRole catalogue. No new trust surface: it is read-only over a dict
    this router never lets a request body populate (see
    `TestWaAgentRoleForgeryResistance` below)."""

    def test_creator_maps_to_role_admin_by_identity(self):
        """GUILT — owner: maps to the EXACT SAME object team_agent_config
        already uses for the JWT-authenticated admin (zero@balizero.com).
        Owner is not a new privilege tier — it reuses the existing entry by
        reference (`is` check, not just equal role_id)."""
        from backend.app.routers.agentic_rag import _derive_wa_agent_role
        from backend.services.agents.team_agent_config import ROLE_ADMIN

        assert _derive_wa_agent_role({"role": "creator"}) is ROLE_ADMIN

    def test_registered_team_email_maps_to_that_members_own_role(self):
        """GUILT — team: a DB-resolved sender with a registered VASSAL role
        gets THEIR OWN scope, never admin-equivalent."""
        from backend.app.routers.agentic_rag import _derive_wa_agent_role
        from backend.services.agents.team_agent_config import (
            ROLE_ADMIN,
            ROLE_EXECUTIVE_CONSULTANT,
        )

        result = _derive_wa_agent_role(
            {"role": "team", "name": "Adit", "email": "adit@balizero.com"}
        )
        assert result is ROLE_EXECUTIVE_CONSULTANT
        assert result is not ROLE_ADMIN  # regression guard: never over-grants

    def test_team_without_email_degrades_to_none(self):
        """INNOCENCE / DEGRADE: the env-resolved `WHATSAPP_TEAM_NUMBERS`
        branch of `resolve_sender_identity` (see `whatsapp_identity.py`
        `_team_numbers()`) carries a name but no email — must degrade
        silently, never crash or over-grant."""
        from backend.app.routers.agentic_rag import _derive_wa_agent_role

        assert _derive_wa_agent_role({"role": "team", "name": "Someone"}) is None

    def test_team_with_unregistered_email_degrades_to_none(self):
        """INNOCENCE: a real `team_members` DB row whose email isn't (yet)
        registered in `TEAM_AGENTS` must never be silently upgraded to any
        role."""
        from backend.app.routers.agentic_rag import _derive_wa_agent_role

        result = _derive_wa_agent_role(
            {"role": "team", "name": "Ghost", "email": "ghost@balizero.com"}
        )
        assert result is None

    def test_client_unknown_and_absent_profile_all_yield_none(self):
        """INNOCENCE: the non-privileged branches of `resolve_sender_identity`
        (client/unknown), plus the "no trusted profile at all" case
        (`trusted_profile is None` — no dedicated bot key, a non-WA caller,
        or an empty dict) must never produce a principal."""
        from backend.app.routers.agentic_rag import _derive_wa_agent_role

        assert _derive_wa_agent_role({"role": "client", "client_id": 1}) is None
        assert _derive_wa_agent_role({"role": "unknown"}) is None
        assert _derive_wa_agent_role(None) is None
        assert _derive_wa_agent_role({}) is None

    def test_degrade_branches_log_role_and_boolean_never_email(self, caplog):
        """PII boundary (UU PDP, non-negotiable per project CLAUDE.md §14):
        the two DEGRADE log lines must be grep-distinguishable from each
        other, but must NEVER contain the member's email or any phone
        number — only role + booleans."""
        import logging

        from backend.app.routers.agentic_rag import _derive_wa_agent_role

        with caplog.at_level(logging.INFO, logger="backend.app.routers.agentic_rag"):
            _derive_wa_agent_role({"role": "team", "name": "X"})
            _derive_wa_agent_role(
                {"role": "team", "name": "Y", "email": "y-secret@balizero.com"}
            )

        assert "degrade=no_email" in caplog.text
        assert "degrade=unregistered_email" in caplog.text
        assert "y-secret@balizero.com" not in caplog.text
        assert "@" not in caplog.text  # no email of any shape escaped through


class TestWaAgentRoleForgeryResistance:
    """T4 FORGERY tests: no request-body field can ever influence the
    derived `agent_role` — mirrors `test_request_schema_has_no_client_
    declarable_profile_field` above for the new T4 surface. The tool-call
    `arguments`-side forgery vector (`_agent_role`/`_caller_profile`/
    `_user_id` reserved keys) is covered in
    `backend/tests/unit/services/rag/agentic/test_tool_executor.py`
    (P0-ARG containment) — `agent_role` itself never travels through the
    LLM-facing `arguments` dict at all (it is a separate Python keyword
    argument threaded via `AgentState.agent_role`), so there is no
    tool-call-shaped forgery surface for it to begin with."""

    def test_body_supplied_agent_role_and_agent_email_are_dropped(self):
        """The wire contract (`AgenticQueryRequest`) has no `agent_role` /
        `agent_email` field — Pydantic silently drops unknown keys (default
        `extra='ignore'`), so a request body can never reach
        `_derive_wa_agent_role`, which only ever sees the server-resolved
        `trusted_profile` dict, never anything off `request`."""
        req = AgenticQueryRequest(
            query="test",
            channel="whatsapp",
            **{
                "agent_role": "admin",
                "agent_email": "zero@balizero.com",
                "profile": {"role": "creator"},
            },
        )
        assert not hasattr(req, "agent_role")
        assert not hasattr(req, "agent_email")
        assert not hasattr(req, "profile")


class TestWaAgentRoleFlagWiring:
    """T4 router-level integration: `query_agentic_rag` must forward the
    T4-derived `agent_role` to the orchestrator ONLY when
    `settings.wa_bot_agent_role_enabled` is True, and — mirroring
    `TestWaTrustedProfileRouterWiring` above for `profile` — the P0-ID
    tourniquet (dedicated bot key, non-privileged senders) must still hold
    with the flag on. `is_wa_inbox_bot` is passed explicitly since these
    tests call the route function directly (bypassing FastAPI's own
    dependency resolution), same convention as the class above."""

    @staticmethod
    def _base_kwargs(user_id, channel="whatsapp"):
        request_data = AgenticQueryRequest(query="Any question", channel=channel, user_id=user_id)
        mock_ab_manager = MagicMock()
        mock_ab_manager.metrics_tracker = MagicMock()
        mock_ab_manager.metrics_tracker.record_query_metrics = AsyncMock()
        mock_ab_manager.assign_variant = MagicMock(return_value="control")
        mock_ab_manager.get_variant_config = MagicMock(return_value={})
        return request_data, mock_ab_manager

    @staticmethod
    def _internal_user():
        return {"role": "internal", "email": "wa-mirror-internal@balizero.com"}

    async def _run(
        self,
        mock_orchestrator,
        *,
        flag_enabled: bool,
        is_wa_inbox_bot: bool,
        identity: dict,
        user_id: str = "whatsapp_62811000111",
    ):
        request_data, mock_ab_manager = self._base_kwargs(user_id)
        internal_user = self._internal_user()
        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=internal_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=None,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
            patch(
                "backend.app.routers.agentic_rag.resolve_sender_identity",
                new=AsyncMock(return_value=identity),
            ),
            patch(
                "backend.app.routers.agentic_rag.settings.wa_bot_agent_role_enabled",
                flag_enabled,
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            await query_agentic_rag(
                request=request_data,
                current_user=internal_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
                is_wa_inbox_bot=is_wa_inbox_bot,
            )
        _, call_kwargs = mock_orchestrator.process_query.call_args
        return call_kwargs

    @pytest.mark.asyncio
    async def test_flag_off_owner_phone_gets_no_agent_role(self, mock_orchestrator):
        """FLAG-OFF: byte-identical to today even for the strongest possible
        signal (verified bot key + owner phone) — the flag is the single
        kill switch, and `profile` (pre-existing V1 field) is UNCHANGED by
        it either way."""
        call_kwargs = await self._run(
            mock_orchestrator,
            flag_enabled=False,
            is_wa_inbox_bot=True,
            identity={"role": "owner"},
        )
        assert "agent_role" not in call_kwargs
        assert call_kwargs.get("profile") == {"role": "creator"}

    @pytest.mark.asyncio
    async def test_flag_on_owner_phone_gets_role_admin(self, mock_orchestrator):
        """GUILT: flag on + verified bot key + owner phone -> ROLE_ADMIN
        reaches the orchestrator, alongside the pre-existing `profile`."""
        from backend.services.agents.team_agent_config import ROLE_ADMIN

        call_kwargs = await self._run(
            mock_orchestrator,
            flag_enabled=True,
            is_wa_inbox_bot=True,
            identity={"role": "owner"},
        )
        assert call_kwargs.get("agent_role") is ROLE_ADMIN
        assert call_kwargs.get("profile") == {"role": "creator"}

    @pytest.mark.asyncio
    async def test_flag_on_registered_team_email_gets_own_role(self, mock_orchestrator):
        """GUILT: flag on + verified bot key + DB-resolved team sender with
        a registered VASSAL role -> that member's own AgentRole (never
        admin) — this is the actual defect T4 fixes: a real team member
        can now use a previously-hard-denied SENSITIVE_TOOLS entry with
        their own scope."""
        from backend.services.agents.team_agent_config import (
            ROLE_ADMIN,
            ROLE_EXECUTIVE_CONSULTANT,
        )

        call_kwargs = await self._run(
            mock_orchestrator,
            flag_enabled=True,
            is_wa_inbox_bot=True,
            identity={
                "role": "team",
                "team_member": "Adit",
                "team_member_email": "adit@balizero.com",
            },
            user_id="whatsapp_62811000222",
        )
        assert call_kwargs.get("agent_role") is ROLE_EXECUTIVE_CONSULTANT
        assert call_kwargs.get("agent_role") is not ROLE_ADMIN

    @pytest.mark.asyncio
    async def test_flag_on_client_phone_gets_no_agent_role(self, mock_orchestrator):
        """INNOCENCE: flag on but the resolved sender is a client — never a
        principal, exactly like `profile` above it (regression target:
        PR #2962/#3062's public PII-exposure tourniquet on
        crm_query/timesheet/team_knowledge)."""
        call_kwargs = await self._run(
            mock_orchestrator,
            flag_enabled=True,
            is_wa_inbox_bot=True,
            identity={"role": "client", "client_id": 1},
            user_id="whatsapp_62899999999",
        )
        assert "agent_role" not in call_kwargs

    @pytest.mark.asyncio
    async def test_flag_on_unknown_phone_gets_no_agent_role(self, mock_orchestrator):
        """INNOCENCE: same as above for an unresolvable phone."""
        call_kwargs = await self._run(
            mock_orchestrator,
            flag_enabled=True,
            is_wa_inbox_bot=True,
            identity={"role": "unknown"},
            user_id="whatsapp_62800000000",
        )
        assert "agent_role" not in call_kwargs

    @pytest.mark.asyncio
    async def test_flag_on_without_dedicated_bot_key_gets_no_agent_role(
        self, mock_orchestrator
    ):
        """INNOCENCE (the exact regression this proves did not come back —
        PR #3062 P0-ID hardening): flag on, owner-shaped phone, but the
        caller lacks wa_inbox_bot.py's OWN dedicated secret
        (`is_wa_inbox_bot=False`). Any holder of the shared
        `X-Internal-Key` alone must NEVER be able to mint a principal, T4
        or not — and `resolve_sender_identity` must not even be called."""
        mock_resolve = AsyncMock(return_value={"role": "owner"})
        request_data, mock_ab_manager = self._base_kwargs("whatsapp_62811000111")
        internal_user = self._internal_user()
        with (
            patch(
                "backend.app.routers.agentic_rag.get_current_user",
                return_value=internal_user,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_orchestrator",
                return_value=mock_orchestrator,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_optional_database_pool",
                return_value=None,
            ),
            patch(
                "backend.app.routers.agentic_rag.get_ab_test_manager",
                return_value=mock_ab_manager,
            ),
            patch(
                "backend.app.routers.agentic_rag.resolve_sender_identity",
                new=mock_resolve,
            ),
            patch(
                "backend.app.routers.agentic_rag.settings.wa_bot_agent_role_enabled",
                True,
            ),
        ):
            from backend.app.routers.agentic_rag import query_agentic_rag

            await query_agentic_rag(
                request=request_data,
                current_user=internal_user,
                orchestrator=mock_orchestrator,
                db_pool=None,
                is_wa_inbox_bot=False,
            )
        _, call_kwargs = mock_orchestrator.process_query.call_args
        assert "agent_role" not in call_kwargs
        assert "profile" not in call_kwargs
        mock_resolve.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_flag_on_env_resolved_team_no_email_degrades_silently(
        self, mock_orchestrator
    ):
        """DEGRADE: flag on, dedicated bot key present, but the sender
        resolves via the env-keyed `WHATSAPP_TEAM_NUMBERS` branch (name
        only, no email — see `whatsapp_identity.py` `_team_numbers()`) ->
        no `agent_role`, no crash. `profile` still carries the name
        unaffected (V1 behavior preserved)."""
        call_kwargs = await self._run(
            mock_orchestrator,
            flag_enabled=True,
            is_wa_inbox_bot=True,
            identity={"role": "team", "team_member": "EnvOnly"},
            user_id="whatsapp_62811000333",
        )
        assert "agent_role" not in call_kwargs
        assert call_kwargs.get("profile") == {"role": "team", "name": "EnvOnly"}

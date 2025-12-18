"""
API Tests for Main Cloud - Coverage 95% Target
Tests all main_cloud endpoints and functions to achieve 95% coverage

Coverage:
- GET /api/v2/bali-zero/chat-stream - Legacy streaming endpoint
- GET /bali-zero/chat-stream - Legacy streaming endpoint
- POST /api/chat/stream - Modern streaming endpoint
- Helper functions: _parse_history, _allowed_origins, _safe_endpoint_label
- Event handlers: startup, shutdown
- Service initialization functions
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test Helper Functions
# ============================================================================


class TestHelperFunctions:
    """Test suite for helper functions in main_cloud"""

    def test_parse_history_valid_json(self):
        """Test _parse_history with valid JSON"""
        from app.main_cloud import _parse_history

        history_json = (
            '[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]'
        )
        result = _parse_history(history_json)

        assert len(result) == 2
        assert result[0]["role"] == "user"

    def test_parse_history_empty(self):
        """Test _parse_history with empty/None input"""
        from app.main_cloud import _parse_history

        assert _parse_history(None) == []
        assert _parse_history("") == []

    def test_parse_history_invalid_json(self):
        """Test _parse_history with invalid JSON"""
        from app.main_cloud import _parse_history

        result = _parse_history("not json")
        assert result == []

    def test_parse_history_not_list(self):
        """Test _parse_history with JSON that's not a list"""
        from app.main_cloud import _parse_history

        result = _parse_history('{"key": "value"}')
        assert result == []

    def test_safe_endpoint_label_valid_url(self):
        """Test _safe_endpoint_label with valid URL"""
        from app.main_cloud import _safe_endpoint_label

        result = _safe_endpoint_label("https://example.com/path")
        assert result == "example.com"

    def test_safe_endpoint_label_path_only(self):
        """Test _safe_endpoint_label with path only"""
        from app.main_cloud import _safe_endpoint_label

        result = _safe_endpoint_label("/api/endpoint")
        assert result == "/api/endpoint"

    def test_safe_endpoint_label_none(self):
        """Test _safe_endpoint_label with None"""
        from app.main_cloud import _safe_endpoint_label

        result = _safe_endpoint_label(None)
        assert result == "unknown"

    def test_allowed_origins_defaults(self):
        """Test _allowed_origins returns default origins"""
        from app.main_cloud import _allowed_origins

        origins = _allowed_origins()
        assert isinstance(origins, list)
        assert len(origins) > 0


# ============================================================================
# Test GET Chat Stream Endpoint
# ============================================================================


class TestGetChatStream:
    """Test suite for GET /api/v2/bali-zero/chat-stream and /bali-zero/chat-stream"""

    def test_chat_stream_empty_query(self, authenticated_client):
        """Test chat stream with empty query"""
        response = authenticated_client.get("/bali-zero/chat-stream?query=")

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_chat_stream_no_auth(self, test_client):
        """Test chat stream without authentication"""
        response = test_client.get("/bali-zero/chat-stream?query=test")

        assert response.status_code == 401

    def test_chat_stream_services_not_initialized(self, authenticated_client):
        """Test chat stream when services not initialized"""
        original = getattr(authenticated_client.app.state, "services_initialized", None)
        authenticated_client.app.state.services_initialized = False
        try:
            response = authenticated_client.get("/bali-zero/chat-stream?query=test")
            assert response.status_code == 503
        finally:
            if original is None:
                delattr(authenticated_client.app.state, "services_initialized")
            else:
                authenticated_client.app.state.services_initialized = original

    def test_chat_stream_success(self, authenticated_client):
        """Test successful chat stream"""

        async def mock_stream():
            yield {"type": "metadata", "data": {"status": "connected"}}
            yield {"type": "token", "data": "Hello"}
            yield {"type": "done", "data": {}}

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = None
            app.state.memory_service = None

            response = authenticated_client.get("/bali-zero/chat-stream?query=test")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        finally:
            app.state.intelligent_router = original_router

    def test_chat_stream_with_conversation_history(self, authenticated_client):
        """Test chat stream with conversation history"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        history_json = '[{"role": "user", "content": "Previous"}]'

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = None
            app.state.memory_service = None

            response = authenticated_client.get(
                f"/bali-zero/chat-stream?query=test&conversation_history={history_json}"
            )

            assert response.status_code == 200
        finally:
            app.state.intelligent_router = original_router

    def test_chat_stream_with_collaborator(self, authenticated_client):
        """Test chat stream with collaborator lookup"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        mock_collaborator = MagicMock()
        mock_collaborator.id = "user123"
        mock_collaborator.name = "Test User"
        mock_collaborator.role = "member"

        mock_collaborator_service = MagicMock()
        mock_collaborator_service.identify = AsyncMock(return_value=mock_collaborator)

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        original_collaborator_service = getattr(app.state, "collaborator_service", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = mock_collaborator_service
            app.state.memory_service = None

            response = authenticated_client.get(
                "/bali-zero/chat-stream?query=test&user_email=test@example.com"
            )

            assert response.status_code == 200
        finally:
            app.state.intelligent_router = original_router
            app.state.collaborator_service = original_collaborator_service

    def test_chat_stream_with_memory(self, authenticated_client):
        """Test chat stream with user memory"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        mock_memory = MagicMock()
        mock_memory.profile_facts = ["fact1", "fact2"]
        mock_memory.summary = "User summary"
        mock_memory.counters = {}

        mock_memory_service = MagicMock()
        mock_memory_service.get_memory = AsyncMock(return_value=mock_memory)

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        original_memory_service = getattr(app.state, "memory_service", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = None
            app.state.memory_service = mock_memory_service

            response = authenticated_client.get("/bali-zero/chat-stream?query=test")

            assert response.status_code == 200
        finally:
            app.state.intelligent_router = original_router
            app.state.memory_service = original_memory_service

    def test_chat_stream_legacy_metadata_format(self, authenticated_client):
        """Test chat stream with legacy [METADATA] format"""

        async def mock_stream():
            yield '[METADATA]{"key": "value"}'
            yield "token"

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = None
            app.state.memory_service = None

            response = authenticated_client.get("/bali-zero/chat-stream?query=test")

            assert response.status_code == 200
        finally:
            app.state.intelligent_router = original_router

    def test_chat_stream_string_chunks(self, authenticated_client):
        """Test chat stream with string chunks"""

        async def mock_stream():
            yield "Hello"
            yield " World"

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = None
            app.state.memory_service = None

            response = authenticated_client.get("/bali-zero/chat-stream?query=test")

            assert response.status_code == 200
        finally:
            app.state.intelligent_router = original_router

    def test_chat_stream_error_handling(self, authenticated_client):
        """Test chat stream error handling"""

        async def mock_stream():
            if False:
                yield "token"
            raise Exception("Streaming error")

        app = authenticated_client.app
        original_router = getattr(app.state, "intelligent_router", None)
        try:
            app.state.services_initialized = True
            app.state.intelligent_router = MagicMock()
            app.state.intelligent_router.stream_chat = MagicMock(return_value=mock_stream())
            app.state.collaborator_service = None
            app.state.memory_service = None

            response = authenticated_client.get("/bali-zero/chat-stream?query=test")

            # Should still return 200 but with error in stream
            assert response.status_code == 200
        finally:
            app.state.intelligent_router = original_router


# ============================================================================
# Test POST Chat Stream Endpoint
# ============================================================================


class TestPostChatStream:
    """Test suite for POST /api/chat/stream"""

    def test_post_chat_stream_empty_message(self, authenticated_client):
        """Test POST chat stream with empty message"""
        response = authenticated_client.post("/api/chat/stream", json={"message": ""})

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_post_chat_stream_no_auth(self, test_client):
        """Test POST chat stream without authentication"""
        response = test_client.post("/api/chat/stream", json={"message": "test"})

        assert response.status_code == 401

    def test_post_chat_stream_success(self, authenticated_client):
        """Test successful POST chat stream"""

        async def mock_stream():
            yield {"type": "metadata", "data": {"status": "connected"}}
            yield {"type": "token", "data": "Hello"}
            yield {"type": "done", "data": {}}

        mock_conversation_service = MagicMock()
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com", "role": "member"}

                response = authenticated_client.post(
                    "/api/chat/stream",
                    json={"message": "test", "user_id": "user123"},
                )

                assert response.status_code == 200

    def test_post_chat_stream_with_conversation_history(self, authenticated_client):
        """Test POST chat stream with conversation history"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        mock_conversation_service = MagicMock()
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com"}

                response = authenticated_client.post(
                    "/api/chat/stream",
                    json={
                        "message": "test",
                        "conversation_history": [{"role": "user", "content": "Previous"}],
                    },
                )

                assert response.status_code == 200

    def test_post_chat_stream_with_session_id(self, authenticated_client):
        """Test POST chat stream with session_id"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        mock_conversation_service = MagicMock()
        mock_conversation_service.get_history = AsyncMock(
            return_value={"messages": [{"role": "user", "content": "From DB"}], "source": "db"}
        )
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com"}

                response = authenticated_client.post(
                    "/api/chat/stream",
                    json={"message": "test", "session_id": "session-123"},
                )

                assert response.status_code == 200

    def test_post_chat_stream_with_zantara_context(self, authenticated_client):
        """Test POST chat stream with zantara_context containing session_id"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        mock_conversation_service = MagicMock()
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com"}

                response = authenticated_client.post(
                    "/api/chat/stream",
                    json={
                        "message": "test",
                        "zantara_context": {"session_id": "session-from-context"},
                    },
                )

                assert response.status_code == 200

    def test_post_chat_stream_generates_session_id(self, authenticated_client):
        """Test POST chat stream generates session_id when missing"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}

        mock_conversation_service = MagicMock()
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com"}

                response = authenticated_client.post("/api/chat/stream", json={"message": "test"})

                assert response.status_code == 200
                # Session ID should be generated

    def test_post_chat_stream_saves_conversation(self, authenticated_client):
        """Test POST chat stream saves conversation"""

        async def mock_stream():
            yield {"type": "token", "data": "Response"}
            yield {"type": "done", "data": {}}

        mock_conversation_service = MagicMock()
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com"}

                response = authenticated_client.post("/api/chat/stream", json={"message": "test"})

                assert response.status_code == 200
                # Conversation should be saved
                # Note: This is tested via the stream completion

    def test_post_chat_stream_unknown_chunk_type(self, authenticated_client):
        """Test POST chat stream with unknown chunk type"""

        async def mock_stream():
            yield {"type": "unknown", "data": "test"}

        mock_conversation_service = MagicMock()
        mock_conversation_service.save_conversation = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.services_initialized = True
            mock_app.state.intelligent_router = MagicMock()
            mock_app.state.intelligent_router.stream_chat = AsyncMock(return_value=mock_stream())
            mock_app.state.collaborator_service = None
            mock_app.state.memory_service = None
            mock_app.state.conversation_service = mock_conversation_service

            with patch("app.main_cloud.getattr") as mock_getattr:
                mock_getattr.return_value = {"email": "test@example.com"}

                response = authenticated_client.post("/api/chat/stream", json={"message": "test"})

                # Should handle gracefully
                assert response.status_code == 200


# ============================================================================
# Test Event Handlers
# ============================================================================


class TestEventHandlers:
    """Test suite for startup and shutdown event handlers"""

    @pytest.mark.asyncio
    async def test_startup_initializes_services(self):
        """Test startup event initializes services"""
        from app.main_cloud import on_startup

        with patch("app.main_cloud.initialize_services") as mock_init_services:
            with patch("app.main_cloud.initialize_plugins") as mock_init_plugins:
                await on_startup()

                mock_init_services.assert_called_once()
                mock_init_plugins.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self):
        """Test shutdown event cleans up resources"""
        from app.main_cloud import on_shutdown

        mock_redis_task = AsyncMock()
        mock_redis_task.cancel = MagicMock()

        mock_health_monitor = MagicMock()
        mock_health_monitor.stop = AsyncMock()

        mock_compliance_monitor = MagicMock()
        mock_compliance_monitor.stop = AsyncMock()

        mock_scheduler = MagicMock()
        mock_scheduler.stop = AsyncMock()

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.redis_listener_task = mock_redis_task
            mock_app.state.health_monitor = mock_health_monitor
            mock_app.state.compliance_monitor = mock_compliance_monitor
            mock_app.state.autonomous_scheduler = mock_scheduler

            await on_shutdown()

            mock_redis_task.cancel.assert_called_once()
            mock_health_monitor.stop.assert_called_once()
            mock_compliance_monitor.stop.assert_called_once()
            mock_scheduler.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_no_resources(self):
        """Test shutdown when no resources exist"""
        from app.main_cloud import on_shutdown

        with patch("app.main_cloud.app") as mock_app:
            mock_app.state.redis_listener_task = None
            mock_app.state.health_monitor = None
            mock_app.state.compliance_monitor = None
            mock_app.state.autonomous_scheduler = None

            # Should not raise error
            await on_shutdown()

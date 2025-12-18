"""
API Tests for Agentic RAG Router - Coverage 95% Target
Tests all endpoints and edge cases to achieve 95% coverage

Coverage:
- POST /api/agentic-rag/query - Query endpoint with all edge cases
- POST /api/agentic-rag/stream - Streaming endpoint with conversation history
- get_conversation_history_for_agentic - All code paths
- Error handling and edge cases
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
os.environ["GOOGLE_API_KEY"] = "test_google_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["DEEPSEEK_API_KEY"] = "test_deepseek_api_key_for_testing"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test Query Endpoint - Edge Cases
# ============================================================================


class TestAgenticRAGQueryEdgeCases:
    """Test suite for POST /api/agentic-rag/query endpoint - edge cases"""

    def test_query_with_all_fields(self, authenticated_client):
        """Test query with all optional fields"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Test answer",
                    "sources": ["source1"],
                    "context_used": 500,
                    "execution_time": 1.0,
                    "route_used": "test",
                }
            )
            mock_get.return_value = mock_orchestrator

            query_data = {
                "query": "Test query",
                "user_id": "user123",
                "enable_vision": True,
                "session_id": "session-123",
                "conversation_id": 456,
                "conversation_history": [
                    {"role": "user", "content": "Previous message"},
                    {"role": "assistant", "content": "Previous response"},
                ],
            }

            response = authenticated_client.post("/api/agentic-rag/query", json=query_data)

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data

    def test_query_with_minimal_fields(self, authenticated_client):
        """Test query with only required fields"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(
                return_value={
                    "answer": "Answer",
                    "sources": [],
                    "context_used": 0,
                    "execution_time": 0.5,
                    "route_used": None,
                }
            )
            mock_get.return_value = mock_orchestrator

            query_data = {"query": "Simple query"}

            response = authenticated_client.post("/api/agentic-rag/query", json=query_data)

            assert response.status_code == 200
            data = response.json()
            assert data["answer"] == "Answer"

    def test_query_orchestrator_error(self, authenticated_client):
        """Test query when orchestrator raises error"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()
            mock_orchestrator.process_query = AsyncMock(side_effect=Exception("Orchestrator error"))
            mock_get.return_value = mock_orchestrator

            query_data = {"query": "Test query"}

            response = authenticated_client.post("/api/agentic-rag/query", json=query_data)

            assert response.status_code == 500
            assert "error" in response.json()["detail"].lower()


# ============================================================================
# Test Streaming Endpoint
# ============================================================================


class TestAgenticRAGStreamEndpoint:
    """Test suite for POST /api/agentic-rag/stream endpoint"""

    def test_stream_with_frontend_history(self, authenticated_client):
        """Test streaming with conversation_history from frontend"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()

            async def mock_stream():
                yield {"type": "thinking", "data": "Processing..."}
                yield {"type": "answer", "data": "Test answer"}

            mock_orchestrator.stream_query = mock_stream()
            mock_get.return_value = mock_orchestrator

            query_data = {
                "query": "Test query",
                "user_id": "user123",
                "conversation_history": [
                    {"role": "user", "content": "Previous"},
                    {"role": "assistant", "content": "Response"},
                ],
            }

            response = authenticated_client.post("/api/agentic-rag/stream", json=query_data)

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_stream_with_conversation_id(self, authenticated_client):
        """Test streaming with conversation_id (DB lookup)"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()

            async def mock_stream():
                yield {"type": "answer", "data": "Answer"}

            mock_orchestrator.stream_query = mock_stream()
            mock_get.return_value = mock_orchestrator

            with patch(
                "app.routers.agentic_rag.get_conversation_history_for_agentic"
            ) as mock_history:
                mock_history.return_value = [
                    {"role": "user", "content": "From DB"},
                ]

                query_data = {
                    "query": "Test",
                    "user_id": "user123",
                    "conversation_id": 456,
                }

                response = authenticated_client.post("/api/agentic-rag/stream", json=query_data)

                assert response.status_code == 200

    def test_stream_with_session_id(self, authenticated_client):
        """Test streaming with session_id (DB lookup)"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()

            async def mock_stream():
                yield {"type": "answer", "data": "Answer"}

            mock_orchestrator.stream_query = mock_stream()
            mock_get.return_value = mock_orchestrator

            with patch(
                "app.routers.agentic_rag.get_conversation_history_for_agentic"
            ) as mock_history:
                mock_history.return_value = []

                query_data = {
                    "query": "Test",
                    "user_id": "user123",
                    "session_id": "session-123",
                }

                response = authenticated_client.post("/api/agentic-rag/stream", json=query_data)

                assert response.status_code == 200

    def test_stream_without_history(self, authenticated_client):
        """Test streaming without conversation history"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()

            async def mock_stream():
                yield {"type": "answer", "data": "Answer"}

            mock_orchestrator.stream_query = mock_stream()
            mock_get.return_value = mock_orchestrator

            query_data = {"query": "Test query", "user_id": "user123"}

            response = authenticated_client.post("/api/agentic-rag/stream", json=query_data)

            assert response.status_code == 200

    def test_stream_with_quota_error(self, authenticated_client):
        """Test streaming with quota exceeded error"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()

            async def mock_stream():
                raise Exception("429 Quota exceeded")

            mock_orchestrator.stream_query = mock_stream()
            mock_get.return_value = mock_orchestrator

            query_data = {"query": "Test query"}

            response = authenticated_client.post("/api/agentic-rag/stream", json=query_data)

            assert response.status_code == 200
            # Should return error event in stream

    def test_stream_with_service_unavailable_error(self, authenticated_client):
        """Test streaming with service unavailable error"""
        with patch("app.routers.agentic_rag.get_orchestrator", new_callable=AsyncMock) as mock_get:
            mock_orchestrator = MagicMock()

            async def mock_stream():
                raise Exception("503 ServiceUnavailable")

            mock_orchestrator.stream_query = mock_stream()
            mock_get.return_value = mock_orchestrator

            query_data = {"query": "Test query"}

            response = authenticated_client.post("/api/agentic-rag/stream", json=query_data)

            assert response.status_code == 200


# ============================================================================
# Test Conversation History Helper
# ============================================================================


class TestConversationHistoryHelper:
    """Test suite for get_conversation_history_for_agentic helper function"""

    @pytest.mark.asyncio
    async def test_get_history_no_db_pool(self):
        """Test get_conversation_history when db_pool is None"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="user123", db_pool=None
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_no_user_id(self):
        """Test get_conversation_history when user_id is None"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_pool = MagicMock()
        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id=None, db_pool=mock_pool
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_with_conversation_id(self):
        """Test get_conversation_history with conversation_id"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"messages": '[{"role": "user", "content": "Test"}]'}
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=123, session_id=None, user_id="test@example.com", db_pool=mock_pool
        )

        assert len(result) == 1
        assert result[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_history_with_session_id(self):
        """Test get_conversation_history with session_id"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"messages": '[{"role": "assistant", "content": "Response"}]'}
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=None,
            session_id="session-123",
            user_id="test@example.com",
            db_pool=mock_pool,
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_history_most_recent(self):
        """Test get_conversation_history getting most recent conversation"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"messages": '[{"role": "user", "content": "Recent"}]'}
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=None, session_id=None, user_id="test@example.com", db_pool=mock_pool
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_history_user_id_not_email(self):
        """Test get_conversation_history when user_id is not an email"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        # First call: find email for user_id
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                {"email": "found@example.com"},  # Email lookup
                {"messages": '[{"role": "user", "content": "Test"}]'},  # Conversation lookup
            ]
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=123, session_id=None, user_id="user123", db_pool=mock_pool
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_history_user_id_not_found(self):
        """Test get_conversation_history when user_id email not found"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        # Email lookup returns None
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                None,  # Email lookup fails
                {
                    "messages": '[{"role": "user", "content": "Test"}]'
                },  # Still try with original user_id
            ]
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=123, session_id=None, user_id="user123", db_pool=mock_pool
        )

        # Should still try to get conversation with original user_id
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_history_messages_as_dict(self):
        """Test get_conversation_history when messages is already a dict (not JSON string)"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"messages": [{"role": "user", "content": "Test"}]}
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=123, session_id=None, user_id="test@example.com", db_pool=mock_pool
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_history_no_messages(self):
        """Test get_conversation_history when no messages found"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=123, session_id=None, user_id="test@example.com", db_pool=mock_pool
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_history_database_error(self):
        """Test get_conversation_history when database error occurs"""
        from app.routers.agentic_rag import get_conversation_history_for_agentic

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("Database error"))

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_conversation_history_for_agentic(
            conversation_id=123, session_id=None, user_id="test@example.com", db_pool=mock_pool
        )

        # Should return empty list on error
        assert result == []

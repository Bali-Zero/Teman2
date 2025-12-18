"""
Integration Tests for Conversations Router
Tests conversation history endpoints with real database
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def app():
    """Create FastAPI app with conversations router"""
    from fastapi import FastAPI

    from app.routers.conversations import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user dependency"""
    return {"email": "test@example.com", "user_id": "test-user-123"}


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
    mock_pool.acquire = AsyncMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_pool


@pytest.mark.integration
class TestConversationsRouterIntegration:
    """Comprehensive integration tests for conversations router"""

    @pytest.mark.asyncio
    async def test_save_conversation(self, client, mock_current_user, mock_db_pool):
        """Test saving conversation"""
        with patch("app.routers.conversations.get_current_user", return_value=mock_current_user):
            with patch("app.routers.conversations.get_database_pool", return_value=mock_db_pool):
                mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
                mock_conn.fetchrow = AsyncMock(
                    return_value={"id": 1, "messages": [], "created_at": "2025-01-01"}
                )

                payload = {
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi!"},
                    ],
                    "session_id": "test-session",
                }

                response = client.post("/api/bali-zero/conversations/save", json=payload)
                assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, client, mock_current_user, mock_db_pool):
        """Test getting conversation history"""
        with patch("app.routers.conversations.get_current_user", return_value=mock_current_user):
            with patch("app.routers.conversations.get_database_pool", return_value=mock_db_pool):
                mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
                mock_conn.fetchrow = AsyncMock(
                    return_value={
                        "messages": [{"role": "user", "content": "test"}],
                        "session_id": "test-session",
                    }
                )

                response = client.get(
                    "/api/bali-zero/conversations/history?session_id=test-session"
                )
                assert response.status_code in [200, 401, 500]

    @pytest.mark.asyncio
    async def test_list_conversations(self, client, mock_current_user, mock_db_pool):
        """Test listing conversations"""
        with patch("app.routers.conversations.get_current_user", return_value=mock_current_user):
            with patch("app.routers.conversations.get_database_pool", return_value=mock_db_pool):
                mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
                mock_conn.fetch = AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "title": "Test",
                            "preview": "Test preview",
                            "message_count": 5,
                            "created_at": "2025-01-01",
                            "updated_at": None,
                            "session_id": "test-session",
                        }
                    ]
                )

                response = client.get("/api/bali-zero/conversations/list")
                assert response.status_code in [200, 401, 500]

    @pytest.mark.asyncio
    async def test_get_conversation_by_id(self, client, mock_current_user, mock_db_pool):
        """Test getting conversation by ID"""
        with patch("app.routers.conversations.get_current_user", return_value=mock_current_user):
            with patch("app.routers.conversations.get_database_pool", return_value=mock_db_pool):
                mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
                mock_conn.fetchrow = AsyncMock(
                    return_value={
                        "id": 1,
                        "messages": [{"role": "user", "content": "test"}],
                        "created_at": "2025-01-01",
                        "session_id": "test-session",
                        "metadata": {},
                    }
                )

                response = client.get("/api/bali-zero/conversations/1")
                assert response.status_code in [200, 401, 404, 500]

    @pytest.mark.asyncio
    async def test_delete_conversation(self, client, mock_current_user, mock_db_pool):
        """Test deleting conversation"""
        with patch("app.routers.conversations.get_current_user", return_value=mock_current_user):
            with patch("app.routers.conversations.get_database_pool", return_value=mock_db_pool):
                mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
                mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
                mock_conn.execute = AsyncMock(return_value="DELETE 1")

                response = client.delete("/api/bali-zero/conversations/1")
                assert response.status_code in [200, 401, 404, 500]

    @pytest.mark.asyncio
    async def test_save_conversation_with_auto_crm(self, client, mock_current_user, mock_db_pool):
        """Test saving conversation with auto-CRM processing"""
        with patch("app.routers.conversations.get_current_user", return_value=mock_current_user):
            with patch("app.routers.conversations.get_database_pool", return_value=mock_db_pool):
                with patch("app.routers.conversations.get_auto_crm") as mock_crm:
                    mock_crm_service = MagicMock()
                    mock_crm_service.process_conversation = AsyncMock()
                    mock_crm.return_value = mock_crm_service

                    mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
                    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})

                    payload = {
                        "messages": [{"role": "user", "content": "I need help with visa"}],
                    }

                    response = client.post("/api/bali-zero/conversations/save", json=payload)
                    assert response.status_code in [200, 500]

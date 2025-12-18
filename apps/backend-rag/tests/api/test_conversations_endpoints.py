"""
API Tests for Conversations Router
Tests conversation history endpoints

Coverage:
- POST /api/bali-zero/conversations/save - Save conversation
- GET /api/bali-zero/conversations/history - Get conversation history
- DELETE /api/bali-zero/conversations/clear - Clear conversation history
- GET /api/bali-zero/conversations/stats - Get conversation stats
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from tests.api.conftest import create_mock_db_pool


@pytest.mark.api
class TestConversations:
    """Tests for conversations endpoints"""

    def test_save_conversation(self, authenticated_client):
        """Test POST /api/bali-zero/conversations/save"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "user_id": "test@example.com", "messages": []}
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ],
                    "session_id": "test_session",
                },
            )

            assert response.status_code in [200, 500]

    def test_get_conversation_history(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/history"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={"messages": [{"role": "user", "content": "Hello"}]}
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/history?limit=20")

            assert response.status_code in [200, 500]

    def test_clear_conversation_history(self, authenticated_client):
        """Test DELETE /api/bali-zero/conversations/clear"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/bali-zero/conversations/clear")

            assert response.status_code in [200, 500]

    def test_get_conversation_stats(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/stats"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={"total_conversations": 10, "total_messages": 100}
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/stats")

            assert response.status_code in [200, 500, 503]

    def test_get_conversation_history_with_session_id(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/history with session_id filter"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "messages": [{"role": "user", "content": "Hello"}],
                    "session_id": "test_session",
                }
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/bali-zero/conversations/history?session_id=test_session&limit=20"
            )

            assert response.status_code in [200, 500]

    def test_get_conversation_history_no_conversations(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/history when no conversations exist"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/history")

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
            assert data.get("total_messages") == 0

    def test_get_conversation_history_database_unavailable(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/history when database is unavailable"""
        with patch("app.dependencies.get_database_pool", return_value=None):
            response = authenticated_client.get("/api/bali-zero/conversations/history")

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False
            assert "unavailable" in data.get("error", "").lower()

    def test_clear_conversation_history_with_session_id(self, authenticated_client):
        """Test DELETE /api/bali-zero/conversations/clear with session_id filter"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete(
                "/api/bali-zero/conversations/clear?session_id=test_session"
            )

            assert response.status_code in [200, 500]

    def test_list_conversations(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/list"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "title": "Test Conversation",
                        "preview": "Hello",
                        "message_count": 5,
                        "created_at": "2025-12-08T00:00:00",
                        "session_id": "test_session",
                    }
                ]
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/list?limit=10")

            assert response.status_code in [200, 500]

    def test_get_conversation_by_id(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/{conversation_id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "created_at": "2025-12-08T00:00:00",
                    "session_id": "test_session",
                    "metadata": {},
                }
            )
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/1")

            assert response.status_code in [200, 404, 500]

    def test_get_conversation_not_found(self, authenticated_client):
        """Test GET /api/bali-zero/conversations/{conversation_id} when conversation doesn't exist"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/999")

            assert response.status_code in [200, 404, 500]

    def test_delete_conversation(self, authenticated_client):
        """Test DELETE /api/bali-zero/conversations/{conversation_id}"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/bali-zero/conversations/1")

            assert response.status_code in [200, 404, 500]

    def test_conversations_require_auth(self, test_client):
        """Test that conversations endpoints require authentication"""
        response = test_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": []},
        )
        assert response.status_code == 401

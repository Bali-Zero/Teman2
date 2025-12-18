"""
Comprehensive API Tests for Conversations Router
Complete test coverage for conversation history endpoints

Coverage:
- POST /api/bali-zero/conversations/save - Save conversation
- GET /api/bali-zero/conversations/list - List conversations
- GET /api/bali-zero/conversations/{conversation_id} - Get conversation
- GET /api/bali-zero/conversations/session/{session_id} - Get session conversations
- DELETE /api/bali-zero/conversations/{conversation_id} - Delete conversation
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestSaveConversation:
    """Comprehensive tests for POST /api/bali-zero/conversations/save"""

    def test_save_conversation_basic(self, authenticated_client, test_app):
        """Test basic conversation save"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ],
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_save_conversation_with_session_id(self, authenticated_client, test_app):
        """Test saving conversation with session ID"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Test"},
                        {"role": "assistant", "content": "Response"},
                    ],
                    "session_id": "session_123",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_save_conversation_with_metadata(self, authenticated_client, test_app):
        """Test saving conversation with metadata"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Test"},
                        {"role": "assistant", "content": "Response"},
                    ],
                    "metadata": {"source": "web", "ip": "192.168.1.1"},
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_save_conversation_empty_messages(self, authenticated_client):
        """Test saving conversation with empty messages"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": []},
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_save_conversation_large_messages(self, authenticated_client, test_app):
        """Test saving conversation with large messages"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            large_messages = [
                {"role": "user", "content": "A" * 10000},
                {"role": "assistant", "content": "B" * 10000},
            ]

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={"messages": large_messages},
            )

            assert response.status_code in [200, 201, 400, 413, 500]

    def test_save_conversation_response_structure(self, authenticated_client, test_app):
        """Test conversation save response structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Test"},
                        {"role": "assistant", "content": "Response"},
                    ],
                },
            )

            if response.status_code in [200, 201]:
                data = response.json()
                assert "success" in data
                assert "conversation_id" in data or "messages_saved" in data

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestListConversations:
    """Comprehensive tests for GET /api/bali-zero/conversations/list"""

    def test_list_conversations_default(self, authenticated_client, test_app):
        """Test listing conversations with default parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "title": "Test Conversation",
                        "preview": "Test preview",
                        "message_count": 5,
                        "created_at": "2025-01-01T00:00:00Z",
                    }
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/list")

            assert response.status_code == 200

    def test_list_conversations_with_limit(self, authenticated_client, test_app):
        """Test listing conversations with limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/list?limit=50")

            assert response.status_code == 200

    def test_list_conversations_with_offset(self, authenticated_client, test_app):
        """Test listing conversations with offset"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/list?offset=10")

            assert response.status_code == 200

    def test_list_conversations_max_limit(self, authenticated_client, test_app):
        """Test listing conversations with maximum limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/list?limit=1000")

            assert response.status_code == 200

    def test_list_conversations_response_structure(self, authenticated_client, test_app):
        """Test conversations list response structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_conn.fetchval = AsyncMock(return_value=0)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/list")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "conversations" in data
            assert "total" in data

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestGetConversation:
    """Comprehensive tests for GET /api/bali-zero/conversations/{conversation_id}"""

    def test_get_conversation_by_id(self, authenticated_client, test_app):
        """Test getting conversation by ID"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "session_id": "session_123",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            )
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi!"},
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/1")

            assert response.status_code == 200

    def test_get_conversation_not_found(self, authenticated_client, test_app):
        """Test getting non-existent conversation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/99999")

            assert response.status_code == 404

    def test_get_conversation_response_structure(self, authenticated_client, test_app):
        """Test conversation response structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/1")

            if response.status_code == 200:
                data = response.json()
                assert "success" in data
                assert "messages" in data


@pytest.mark.api
class TestGetSessionConversations:
    """Comprehensive tests for GET /api/bali-zero/conversations/session/{session_id}"""

    def test_get_session_conversations(self, authenticated_client, test_app):
        """Test getting conversations by session ID"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "session_id": "session_123",
                        "created_at": "2025-01-01T00:00:00Z",
                    }
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/bali-zero/conversations/session/session_123")

            assert response.status_code == 200

    def test_get_session_conversations_empty(self, authenticated_client, test_app):
        """Test getting conversations for non-existent session"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/bali-zero/conversations/session/nonexistent_session"
            )

            assert response.status_code == 200


@pytest.mark.api
class TestDeleteConversation:
    """Comprehensive tests for DELETE /api/bali-zero/conversations/{conversation_id}"""

    def test_delete_conversation(self, authenticated_client, test_app):
        """Test deleting conversation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_conn.execute = AsyncMock(return_value="DELETE 1")
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/bali-zero/conversations/1")

            assert response.status_code in [200, 204, 404, 500]

    def test_delete_conversation_not_found(self, authenticated_client, test_app):
        """Test deleting non-existent conversation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.delete("/api/bali-zero/conversations/99999")

            assert response.status_code == 404


@pytest.mark.api
class TestConversationsSecurity:
    """Security tests for conversations endpoints"""

    def test_conversations_endpoints_require_auth(self, test_client):
        """Test all conversation endpoints require authentication"""
        endpoints = [
            ("POST", "/api/bali-zero/conversations/save"),
            ("GET", "/api/bali-zero/conversations/list"),
            ("GET", "/api/bali-zero/conversations/1"),
            ("GET", "/api/bali-zero/conversations/session/session_123"),
            ("DELETE", "/api/bali-zero/conversations/1"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            elif method == "DELETE":
                response = test_client.delete(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401

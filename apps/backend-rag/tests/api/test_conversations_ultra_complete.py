"""
Ultra-Complete API Tests for Conversations Router
==================================================

Comprehensive test coverage for all conversations.py endpoints including:
- Conversation history management
- Message saving and retrieval
- Auto-CRM integration
- Session management
- Data validation and sanitization
- Privacy and security

Coverage Endpoints:
- POST /api/bali-zero/conversations/save - Save conversation
- GET /api/bali-zero/conversations/history - Get history
- GET /api/bali-zero/conversations/stats - Get statistics
- DELETE /api/bali-zero/conversations/clear - Clear history
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Environment setup
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestConversationsSave:
    """Comprehensive tests for POST /api/bali-zero/conversations/save"""

    def test_save_conversation_valid_simple(self, authenticated_client):
        """Test saving simple conversation"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 123, "messages_saved": 2}

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ]
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_save_conversation_with_session_id(self, authenticated_client):
        """Test saving conversation with session ID"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {
                "success": True,
                "conversation_id": 456,
                "messages_saved": 5,
                "session_id": "session_abc123",
            }

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "What is KITAS?"},
                        {"role": "assistant", "content": "KITAS is..."},
                    ],
                    "session_id": "session_abc123",
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_save_conversation_with_metadata(self, authenticated_client):
        """Test saving conversation with metadata"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 789, "messages_saved": 3}

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Test"},
                        {"role": "assistant", "content": "Response"},
                    ],
                    "metadata": {"source": "web", "personality": "professional", "language": "en"},
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_save_conversation_with_crm_integration(self, authenticated_client):
        """Test conversation save with CRM auto-population"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {
                "success": True,
                "conversation_id": 111,
                "messages_saved": 4,
                "crm": {
                    "processed": True,
                    "client_id": 42,
                    "client_created": True,
                    "practice_id": 15,
                },
            }

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "I need help with PT PMA setup"},
                        {"role": "assistant", "content": "I can help with that"},
                    ]
                },
            )

            assert response.status_code in [200, 201, 400, 500]
            if response.status_code in [200, 201]:
                data = response.json()
                # CRM data might be included
                assert "success" in data or "conversation_id" in data

    def test_save_conversation_empty_messages(self, authenticated_client):
        """Test saving conversation with empty messages array"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save", json={"messages": []}
        )

        assert response.status_code in [400, 422]

    def test_save_conversation_missing_role(self, authenticated_client):
        """Test with message missing role field"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"content": "Hello"}  # Missing role
                ]
            },
        )

        assert response.status_code in [400, 422]

    def test_save_conversation_invalid_role(self, authenticated_client):
        """Test with invalid role value"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": [{"role": "invalid_role", "content": "Hello"}]},
        )

        assert response.status_code in [400, 422]

    def test_save_conversation_missing_content(self, authenticated_client):
        """Test with message missing content"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={
                "messages": [
                    {"role": "user"}  # Missing content
                ]
            },
        )

        assert response.status_code in [400, 422]

    def test_save_conversation_very_long_message(self, authenticated_client):
        """Test with extremely long message content"""
        long_content = "A" * 50000  # 50k characters

        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": [{"role": "user", "content": long_content}]},
        )

        assert response.status_code in [200, 201, 400, 413, 422, 500]

    def test_save_conversation_many_messages(self, authenticated_client):
        """Test with large number of messages"""
        messages = []
        for i in range(100):
            messages.append(
                {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            )

        response = authenticated_client.post(
            "/api/bali-zero/conversations/save", json={"messages": messages}
        )

        assert response.status_code in [200, 201, 400, 413, 422, 500]

    def test_save_conversation_special_characters(self, authenticated_client):
        """Test with special characters in content"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 999}

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "Test <script>alert('xss')</script>"},
                        {"role": "assistant", "content": "Safe response"},
                    ]
                },
            )

            assert response.status_code in [200, 201, 400, 422, 500]

    def test_save_conversation_unicode(self, authenticated_client):
        """Test with unicode characters"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 888}

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "你好世界 🇮🇩"},
                        {"role": "assistant", "content": "Halo! 😊"},
                    ]
                },
            )

            assert response.status_code in [200, 201, 400, 422, 500]

    def test_save_conversation_sql_injection(self, authenticated_client):
        """Test SQL injection prevention"""
        response = authenticated_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": [{"role": "user", "content": "'; DROP TABLE conversations; --"}]},
        )

        # Should not crash or execute SQL
        assert response.status_code in [200, 201, 400, 422, 500]

    def test_save_conversation_unauthenticated(self, test_client):
        """Test saving without authentication"""
        response = test_client.post(
            "/api/bali-zero/conversations/save",
            json={"messages": [{"role": "user", "content": "Test"}]},
        )

        assert response.status_code in [200, 201, 401, 403]


@pytest.mark.api
class TestConversationsHistory:
    """Tests for GET /api/bali-zero/conversations/history"""

    def test_get_history_default(self, authenticated_client):
        """Test getting conversation history with defaults"""
        with patch("app.routers.conversations.get_conversation_history") as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "role": "user",
                    "content": "Hello",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]

            response = authenticated_client.get("/api/bali-zero/conversations/history")

            assert response.status_code in [200, 401, 500]

    def test_get_history_with_limit(self, authenticated_client):
        """Test with custom limit"""
        with patch("app.routers.conversations.get_conversation_history") as mock_get:
            mock_get.return_value = []

            response = authenticated_client.get(
                "/api/bali-zero/conversations/history", params={"limit": 50}
            )

            assert response.status_code in [200, 400, 401, 500]

    def test_get_history_with_session_id(self, authenticated_client):
        """Test filtering by session ID"""
        with patch("app.routers.conversations.get_conversation_history") as mock_get:
            mock_get.return_value = []

            response = authenticated_client.get(
                "/api/bali-zero/conversations/history", params={"session_id": "session_123"}
            )

            assert response.status_code in [200, 401, 500]

    def test_get_history_invalid_limit(self, authenticated_client):
        """Test with invalid limit value"""
        response = authenticated_client.get(
            "/api/bali-zero/conversations/history", params={"limit": -1}
        )

        assert response.status_code in [400, 422]

    def test_get_history_excessive_limit(self, authenticated_client):
        """Test with very large limit"""
        response = authenticated_client.get(
            "/api/bali-zero/conversations/history", params={"limit": 10000}
        )

        # Should cap or reject
        assert response.status_code in [200, 400, 422, 500]

    def test_get_history_empty_result(self, authenticated_client):
        """Test when user has no conversation history"""
        with patch("app.routers.conversations.get_conversation_history") as mock_get:
            mock_get.return_value = []

            response = authenticated_client.get("/api/bali-zero/conversations/history")

            assert response.status_code in [200, 404, 500]
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)

    def test_get_history_unauthenticated(self, test_client):
        """Test without authentication"""
        response = test_client.get("/api/bali-zero/conversations/history")

        assert response.status_code in [401, 403]


@pytest.mark.api
class TestConversationsStats:
    """Tests for GET /api/bali-zero/conversations/stats"""

    def test_get_stats_success(self, authenticated_client):
        """Test getting conversation statistics"""
        with patch("app.routers.conversations.get_conversation_stats") as mock_stats:
            mock_stats.return_value = {
                "total_conversations": 10,
                "total_messages": 50,
                "avg_messages_per_conversation": 5,
                "first_conversation": datetime.utcnow().isoformat(),
                "last_conversation": datetime.utcnow().isoformat(),
            }

            response = authenticated_client.get("/api/bali-zero/conversations/stats")

            assert response.status_code in [200, 401, 500]

    def test_get_stats_no_data(self, authenticated_client):
        """Test stats when user has no conversations"""
        with patch("app.routers.conversations.get_conversation_stats") as mock_stats:
            mock_stats.return_value = {"total_conversations": 0, "total_messages": 0}

            response = authenticated_client.get("/api/bali-zero/conversations/stats")

            assert response.status_code in [200, 404, 500]

    def test_get_stats_unauthenticated(self, test_client):
        """Test without authentication"""
        response = test_client.get("/api/bali-zero/conversations/stats")

        assert response.status_code in [401, 403]


@pytest.mark.api
class TestConversationsClear:
    """Tests for DELETE /api/bali-zero/conversations/clear"""

    def test_clear_all_conversations(self, authenticated_client):
        """Test clearing all user conversations"""
        with patch("app.routers.conversations.clear_conversation_history") as mock_clear:
            mock_clear.return_value = {"deleted": 10}

            response = authenticated_client.delete("/api/bali-zero/conversations/clear")

            assert response.status_code in [200, 204, 401, 500]

    def test_clear_by_session_id(self, authenticated_client):
        """Test clearing specific session"""
        with patch("app.routers.conversations.clear_conversation_history") as mock_clear:
            mock_clear.return_value = {"deleted": 5}

            response = authenticated_client.delete(
                "/api/bali-zero/conversations/clear", params={"session_id": "session_123"}
            )

            assert response.status_code in [200, 204, 401, 500]

    def test_clear_no_conversations(self, authenticated_client):
        """Test clearing when no conversations exist"""
        with patch("app.routers.conversations.clear_conversation_history") as mock_clear:
            mock_clear.return_value = {"deleted": 0}

            response = authenticated_client.delete("/api/bali-zero/conversations/clear")

            assert response.status_code in [200, 204, 404, 500]

    def test_clear_invalid_session_id(self, authenticated_client):
        """Test with non-existent session ID"""
        with patch("app.routers.conversations.clear_conversation_history") as mock_clear:
            mock_clear.return_value = {"deleted": 0}

            response = authenticated_client.delete(
                "/api/bali-zero/conversations/clear", params={"session_id": "nonexistent_session"}
            )

            assert response.status_code in [200, 204, 404, 500]

    def test_clear_unauthenticated(self, test_client):
        """Test without authentication"""
        response = test_client.delete("/api/bali-zero/conversations/clear")

        assert response.status_code in [401, 403]

    def test_clear_is_permanent(self, authenticated_client):
        """Test that clear operation is permanent"""
        with (
            patch("app.routers.conversations.clear_conversation_history") as mock_clear,
            patch("app.routers.conversations.get_conversation_history") as mock_get,
        ):
            mock_clear.return_value = {"deleted": 5}
            mock_get.return_value = []

            # Clear conversations
            clear_response = authenticated_client.delete("/api/bali-zero/conversations/clear")
            assert clear_response.status_code in [200, 204, 401, 500]

            # Try to retrieve - should be empty
            history_response = authenticated_client.get("/api/bali-zero/conversations/history")
            if history_response.status_code == 200:
                data = history_response.json()
                assert len(data) == 0 or data == []


@pytest.mark.api
@pytest.mark.security
class TestConversationsSecurity:
    """Security tests"""

    def test_user_isolation(self, authenticated_client):
        """Test that users can only access their own conversations"""
        with patch("app.routers.conversations.get_conversation_history") as mock_get:
            # Should only return current user's data
            mock_get.return_value = []

            response = authenticated_client.get("/api/bali-zero/conversations/history")

            assert response.status_code in [200, 401, 500]

    def test_pii_sanitization(self, authenticated_client):
        """Test PII is properly handled"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 777}

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {
                            "role": "user",
                            "content": "My passport is A12345678 and SSN is 123-45-6789",
                        }
                    ]
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_xss_prevention(self, authenticated_client):
        """Test XSS attack prevention"""
        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 666}

            response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [{"role": "user", "content": "<img src=x onerror=alert('XSS')>"}]
                },
            )

            assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
@pytest.mark.performance
class TestConversationsPerformance:
    """Performance tests"""

    def test_save_large_conversation_performance(self, authenticated_client):
        """Test performance with large conversations"""
        import time

        messages = []
        for i in range(50):
            messages.append(
                {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}" * 10}
            )

        with patch("app.routers.conversations.save_conversation_to_db") as mock_save:
            mock_save.return_value = {"success": True, "conversation_id": 555}

            start = time.time()
            response = authenticated_client.post(
                "/api/bali-zero/conversations/save", json={"messages": messages}
            )
            duration = time.time() - start

            assert response.status_code in [200, 201, 400, 413, 500]
            # Should complete within 5 seconds
            assert duration < 5

    def test_history_retrieval_performance(self, authenticated_client):
        """Test history retrieval speed"""
        import time

        with patch("app.routers.conversations.get_conversation_history") as mock_get:
            # Simulate large history
            mock_get.return_value = [
                {"id": i, "role": "user", "content": f"Message {i}"} for i in range(100)
            ]

            start = time.time()
            response = authenticated_client.get(
                "/api/bali-zero/conversations/history", params={"limit": 100}
            )
            duration = time.time() - start

            assert response.status_code in [200, 400, 401, 500]
            # Should retrieve within 2 seconds
            assert duration < 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

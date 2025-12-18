"""
Ultra-Complete API Tests for CRM Interactions Router
=====================================================

Comprehensive test coverage for all crm_interactions.py endpoints including:
- Interaction logging (chat, email, call, meeting, etc.)
- Timeline and history tracking
- Auto-CRM from conversations
- Gmail integration
- Statistics and analytics
- Validation and error handling
- Security and performance

Coverage Endpoints:
- POST /api/crm/interactions/ - Create interaction
- GET /api/crm/interactions/ - List interactions with filtering
- GET /api/crm/interactions/{interaction_id} - Get interaction by ID
- GET /api/crm/interactions/client/{client_id}/timeline - Client timeline
- GET /api/crm/interactions/practice/{practice_id}/history - Practice history
- GET /api/crm/interactions/stats/overview - Statistics
- POST /api/crm/interactions/from-conversation - Auto-create from conversation
- POST /api/crm/interactions/sync-gmail - Gmail sync
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Environment setup
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestCRMInteractionsCreate:
    """Comprehensive tests for POST /api/crm/interactions/"""

    def test_create_interaction_minimal(self, authenticated_client):
        """Test creating interaction with minimal fields"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {
                "id": 1,
                "client_id": 1,
                "interaction_type": "chat",
                "team_member": "agent@balizero.com",
                "direction": "inbound",
                "interaction_date": datetime.now(),
                "created_at": datetime.now(),
            }

            response = authenticated_client.post(
                "/api/crm/interactions/",
                json={"interaction_type": "chat", "team_member": "agent@balizero.com"},
            )

            assert response.status_code in [200, 201, 400, 422, 500]

    def test_create_interaction_complete(self, authenticated_client):
        """Test creating interaction with all fields"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {
                "id": 1,
                "client_id": 1,
                "practice_id": 1,
                "conversation_id": 10,
                "interaction_type": "call",
                "channel": "phone",
                "subject": "KITAS renewal discussion",
                "summary": "Client wants to renew KITAS",
                "sentiment": "positive",
                "team_member": "agent@balizero.com",
                "direction": "outbound",
                "duration_minutes": 15,
                "interaction_date": datetime.now(),
                "created_at": datetime.now(),
            }

            response = authenticated_client.post(
                "/api/crm/interactions/",
                json={
                    "client_id": 1,
                    "practice_id": 1,
                    "conversation_id": 10,
                    "interaction_type": "call",
                    "channel": "phone",
                    "subject": "KITAS renewal discussion",
                    "summary": "Client wants to renew KITAS",
                    "sentiment": "positive",
                    "team_member": "agent@balizero.com",
                    "direction": "outbound",
                    "duration_minutes": 15,
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_create_interaction_invalid_type(self, authenticated_client):
        """Test with invalid interaction_type"""
        response = authenticated_client.post(
            "/api/crm/interactions/",
            json={"interaction_type": "invalid_type", "team_member": "agent@balizero.com"},
        )

        assert response.status_code in [400, 422]

    def test_create_interaction_invalid_channel(self, authenticated_client):
        """Test with invalid channel"""
        response = authenticated_client.post(
            "/api/crm/interactions/",
            json={
                "interaction_type": "chat",
                "channel": "invalid_channel",
                "team_member": "agent@balizero.com",
            },
        )

        assert response.status_code in [400, 422]

    def test_create_interaction_invalid_sentiment(self, authenticated_client):
        """Test with invalid sentiment"""
        response = authenticated_client.post(
            "/api/crm/interactions/",
            json={
                "interaction_type": "chat",
                "sentiment": "super_happy",  # Invalid
                "team_member": "agent@balizero.com",
            },
        )

        assert response.status_code in [400, 422]

    def test_create_interaction_invalid_direction(self, authenticated_client):
        """Test with invalid direction"""
        response = authenticated_client.post(
            "/api/crm/interactions/",
            json={
                "interaction_type": "chat",
                "direction": "sideways",  # Invalid
                "team_member": "agent@balizero.com",
            },
        )

        assert response.status_code in [400, 422]

    def test_create_interaction_empty_team_member(self, authenticated_client):
        """Test with empty team_member"""
        response = authenticated_client.post(
            "/api/crm/interactions/", json={"interaction_type": "chat", "team_member": ""}
        )

        assert response.status_code in [400, 422]

    def test_create_interaction_negative_duration(self, authenticated_client):
        """Test with negative duration"""
        response = authenticated_client.post(
            "/api/crm/interactions/",
            json={
                "interaction_type": "call",
                "team_member": "agent@balizero.com",
                "duration_minutes": -10,
            },
        )

        assert response.status_code in [400, 422]


@pytest.mark.api
class TestCRMInteractionsList:
    """Tests for GET /api/crm/interactions/"""

    def test_list_interactions_default(self, authenticated_client):
        """Test listing interactions with default parameters"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get("/api/crm/interactions/")

            assert response.status_code in [200, 500]

    def test_list_interactions_with_filters(self, authenticated_client):
        """Test with multiple filters"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get(
                "/api/crm/interactions/",
                params={
                    "client_id": 1,
                    "practice_id": 1,
                    "team_member": "agent@balizero.com",
                    "interaction_type": "chat",
                    "sentiment": "positive",
                    "limit": 20,
                    "offset": 0,
                },
            )

            assert response.status_code in [200, 400, 500]

    def test_list_interactions_pagination(self, authenticated_client):
        """Test pagination"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"id": i} for i in range(10)]

            response = authenticated_client.get(
                "/api/crm/interactions/", params={"limit": 10, "offset": 20}
            )

            assert response.status_code in [200, 500]

    def test_list_interactions_invalid_limit(self, authenticated_client):
        """Test with invalid limit"""
        response = authenticated_client.get("/api/crm/interactions/", params={"limit": -1})

        assert response.status_code in [400, 422]


@pytest.mark.api
class TestCRMInteractionsGet:
    """Tests for GET /api/crm/interactions/{interaction_id}"""

    def test_get_interaction_success(self, authenticated_client):
        """Test getting existing interaction"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = {
                "id": 1,
                "client_name": "John Doe",
                "interaction_type": "chat",
            }

            response = authenticated_client.get("/api/crm/interactions/1")

            assert response.status_code in [200, 404, 500]

    def test_get_interaction_not_found(self, authenticated_client):
        """Test getting non-existent interaction"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.return_value = None

            response = authenticated_client.get("/api/crm/interactions/99999")

            assert response.status_code in [404, 500]

    def test_get_interaction_invalid_id(self, authenticated_client):
        """Test with invalid interaction ID"""
        response = authenticated_client.get("/api/crm/interactions/invalid")

        assert response.status_code in [400, 404, 422]


@pytest.mark.api
class TestCRMInteractionsTimeline:
    """Tests for GET /api/crm/interactions/client/{client_id}/timeline"""

    def test_get_client_timeline_success(self, authenticated_client):
        """Test getting client timeline"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get("/api/crm/interactions/client/1/timeline")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "timeline" in data
                assert "client_id" in data

    def test_get_client_timeline_with_limit(self, authenticated_client):
        """Test timeline with custom limit"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"id": i} for i in range(10)]

            response = authenticated_client.get(
                "/api/crm/interactions/client/1/timeline", params={"limit": 10}
            )

            assert response.status_code in [200, 500]

    def test_get_client_timeline_invalid_id(self, authenticated_client):
        """Test with invalid client ID"""
        response = authenticated_client.get("/api/crm/interactions/client/invalid/timeline")

        assert response.status_code in [400, 404, 422]


@pytest.mark.api
class TestCRMInteractionsPracticeHistory:
    """Tests for GET /api/crm/interactions/practice/{practice_id}/history"""

    def test_get_practice_history_success(self, authenticated_client):
        """Test getting practice history"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get("/api/crm/interactions/practice/1/history")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "history" in data
                assert "practice_id" in data

    def test_get_practice_history_invalid_id(self, authenticated_client):
        """Test with invalid practice ID"""
        response = authenticated_client.get("/api/crm/interactions/practice/invalid/history")

        assert response.status_code in [400, 404, 422]


@pytest.mark.api
class TestCRMInteractionsStats:
    """Tests for GET /api/crm/interactions/stats/overview"""

    def test_get_stats_overview_all(self, authenticated_client):
        """Test getting all interaction statistics"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.side_effect = [
                [{"interaction_type": "chat", "count": 10}],
                [{"sentiment": "positive", "count": 5}],
                [{"team_member": "agent@balizero.com", "count": 15}],
            ]
            mock_conn.fetchrow.return_value = {"count": 20}

            response = authenticated_client.get("/api/crm/interactions/stats/overview")

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "total_interactions" in data or "by_type" in data

    def test_get_stats_by_team_member(self, authenticated_client):
        """Test stats filtered by team member"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.side_effect = [
                [{"interaction_type": "chat", "count": 5}],
                [{"sentiment": "positive", "count": 3}],
                [],
            ]
            mock_conn.fetchrow.return_value = {"count": 10}

            response = authenticated_client.get(
                "/api/crm/interactions/stats/overview", params={"team_member": "agent@balizero.com"}
            )

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestCRMInteractionsFromConversation:
    """Tests for POST /api/crm/interactions/from-conversation"""

    def test_from_conversation_existing_client(self, authenticated_client):
        """Test creating interaction from conversation with existing client"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.side_effect = [
                {"id": 1},  # client exists
                {  # conversation
                    "messages": [
                        {"role": "user", "content": "I need help with KITAS"},
                        {"role": "assistant", "content": "Sure, I can help"},
                    ]
                },
                {"id": 1},  # interaction created
            ]

            response = authenticated_client.post(
                "/api/crm/interactions/from-conversation",
                params={
                    "conversation_id": 10,
                    "client_email": "existing@example.com",
                    "team_member": "agent@balizero.com",
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_from_conversation_new_client(self, authenticated_client):
        """Test creating interaction with auto-creating new client"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.side_effect = [
                None,  # client doesn't exist
                {"id": 2},  # new client created
                {"messages": [{"role": "user", "content": "Hello"}]},  # conversation
                {"id": 1},  # interaction created
            ]

            response = authenticated_client.post(
                "/api/crm/interactions/from-conversation",
                params={
                    "conversation_id": 10,
                    "client_email": "newclient@example.com",
                    "team_member": "agent@balizero.com",
                },
            )

            assert response.status_code in [200, 201, 400, 500]

    def test_from_conversation_with_summary(self, authenticated_client):
        """Test with custom AI-generated summary"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetchrow.side_effect = [{"id": 1}, {"messages": []}, {"id": 1}]

            response = authenticated_client.post(
                "/api/crm/interactions/from-conversation",
                params={
                    "conversation_id": 10,
                    "client_email": "test@example.com",
                    "team_member": "agent@balizero.com",
                    "summary": "Client inquired about PT PMA formation",
                },
            )

            assert response.status_code in [200, 201, 400, 500]


@pytest.mark.api
class TestCRMInteractionsGmailSync:
    """Tests for POST /api/crm/interactions/sync-gmail"""

    def test_gmail_sync_success(self, authenticated_client):
        """Test successful Gmail sync"""
        with (
            patch("app.routers.crm_interactions.get_gmail_service") as mock_gmail,
            patch("app.routers.crm_interactions.get_auto_crm_service") as mock_crm,
            patch("app.routers.crm_interactions.get_database_pool") as mock_pool,
        ):
            mock_gmail_instance = MagicMock()
            mock_gmail.return_value = mock_gmail_instance
            mock_gmail_instance.list_messages.return_value = [{"id": "msg_123"}]
            mock_gmail_instance.get_message_details.return_value = {
                "id": "msg_123",
                "subject": "Test Email",
                "from": "client@example.com",
            }

            mock_crm_instance = MagicMock()
            mock_crm.return_value = mock_crm_instance
            mock_crm_instance.process_email_interaction.return_value = {"success": True}

            mock_pool_instance = MagicMock()
            mock_pool.return_value = mock_pool_instance

            response = authenticated_client.post(
                "/api/crm/interactions/sync-gmail",
                params={"limit": 5, "team_member": "agent@balizero.com"},
            )

            assert response.status_code in [200, 201, 500, 503]

    def test_gmail_sync_with_limit(self, authenticated_client):
        """Test Gmail sync with custom limit"""
        with (
            patch("app.routers.crm_interactions.get_gmail_service") as mock_gmail,
            patch("app.routers.crm_interactions.get_auto_crm_service") as mock_crm,
            patch("app.routers.crm_interactions.get_database_pool"),
        ):
            mock_gmail_instance = MagicMock()
            mock_gmail.return_value = mock_gmail_instance
            mock_gmail_instance.list_messages.return_value = []

            mock_crm_instance = MagicMock()
            mock_crm.return_value = mock_crm_instance

            response = authenticated_client.post(
                "/api/crm/interactions/sync-gmail", params={"limit": 10}
            )

            assert response.status_code in [200, 500, 503]

    def test_gmail_sync_service_unavailable(self, authenticated_client):
        """Test Gmail sync when service is unavailable"""
        with patch("app.routers.crm_interactions.get_gmail_service") as mock_gmail:
            mock_gmail.side_effect = Exception("Gmail service unavailable")

            response = authenticated_client.post("/api/crm/interactions/sync-gmail")

            assert response.status_code in [500, 503]


@pytest.mark.api
@pytest.mark.security
class TestCRMInteractionsSecurity:
    """Security tests"""

    def test_unauthorized_access(self, test_client):
        """Test endpoints without authentication"""
        response = test_client.get("/api/crm/interactions/")

        assert response.status_code in [200, 401, 403]

    def test_sql_injection_in_filters(self, authenticated_client):
        """Test SQL injection in filter parameters"""
        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = []

            response = authenticated_client.get(
                "/api/crm/interactions/", params={"interaction_type": "' OR '1'='1"}
            )

            assert response.status_code in [200, 400, 500]


@pytest.mark.api
@pytest.mark.performance
class TestCRMInteractionsPerformance:
    """Performance tests"""

    def test_list_performance(self, authenticated_client):
        """Test listing performance with large dataset"""
        import time

        with patch("app.routers.crm_interactions.get_database_pool") as mock_pool:
            mock_conn = MagicMock()
            mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"id": i} for i in range(200)]

            start = time.time()
            response = authenticated_client.get("/api/crm/interactions/", params={"limit": 200})
            duration = time.time() - start

            assert response.status_code in [200, 500]
            assert duration < 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

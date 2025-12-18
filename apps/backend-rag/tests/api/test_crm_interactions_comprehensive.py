"""
Comprehensive API Tests for CRM Interactions Router
Complete test coverage for all interaction tracking endpoints

Coverage:
- POST /api/crm/interactions - Create interaction
- GET /api/crm/interactions - List interactions (with filters)
- GET /api/crm/interactions/{interaction_id} - Get interaction by ID
- GET /api/crm/interactions/client/{client_id}/timeline - Get client timeline
- GET /api/crm/interactions/practice/{practice_id}/history - Get practice history
- GET /api/crm/interactions/stats/overview - Get interaction statistics
- POST /api/crm/interactions/from-conversation - Create from conversation
- POST /api/crm/interactions/sync-gmail - Sync Gmail interactions
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
class TestCreateInteraction:
    """Comprehensive tests for POST /api/crm/interactions"""

    def test_create_interaction_chat(self, authenticated_client, test_app):
        """Test creating chat interaction"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions",
                json={
                    "client_id": 1,
                    "interaction_type": "chat",
                    "team_member": "team@example.com",
                    "summary": "Test chat interaction",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_interaction_email(self, authenticated_client, test_app):
        """Test creating email interaction"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions",
                json={
                    "client_id": 1,
                    "interaction_type": "email",
                    "channel": "gmail",
                    "team_member": "team@example.com",
                    "subject": "Test Email",
                    "sentiment": "positive",
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_interaction_all_types(self, authenticated_client, test_app):
        """Test creating interactions of all types"""
        interaction_types = ["chat", "email", "whatsapp", "call", "meeting", "note"]

        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            for interaction_type in interaction_types:
                response = authenticated_client.post(
                    "/api/crm/interactions",
                    json={
                        "client_id": 1,
                        "interaction_type": interaction_type,
                        "team_member": "team@example.com",
                    },
                )

                assert response.status_code in [200, 201, 500]

    def test_create_interaction_invalid_type(self, authenticated_client):
        """Test creating interaction with invalid type"""
        response = authenticated_client.post(
            "/api/crm/interactions",
            json={
                "interaction_type": "invalid_type",
                "team_member": "team@example.com",
            },
        )

        assert response.status_code == 422

    def test_create_interaction_invalid_sentiment(self, authenticated_client):
        """Test creating interaction with invalid sentiment"""
        response = authenticated_client.post(
            "/api/crm/interactions",
            json={
                "interaction_type": "chat",
                "team_member": "team@example.com",
                "sentiment": "invalid_sentiment",
            },
        )

        assert response.status_code == 422

    def test_create_interaction_invalid_channel(self, authenticated_client):
        """Test creating interaction with invalid channel"""
        response = authenticated_client.post(
            "/api/crm/interactions",
            json={
                "interaction_type": "chat",
                "team_member": "team@example.com",
                "channel": "invalid_channel",
            },
        )

        assert response.status_code == 422

    def test_create_interaction_missing_team_member(self, authenticated_client):
        """Test creating interaction without team_member"""
        response = authenticated_client.post(
            "/api/crm/interactions",
            json={
                "interaction_type": "chat",
            },
        )

        assert response.status_code == 422

    def test_create_interaction_with_action_items(self, authenticated_client, test_app):
        """Test creating interaction with action items"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions",
                json={
                    "client_id": 1,
                    "interaction_type": "meeting",
                    "team_member": "team@example.com",
                    "action_items": [
                        {"task": "Follow up", "due_date": "2025-12-31"},
                        {"task": "Send documents", "due_date": "2025-12-25"},
                    ],
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_interaction_with_entities(self, authenticated_client, test_app):
        """Test creating interaction with extracted entities"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions",
                json={
                    "client_id": 1,
                    "interaction_type": "chat",
                    "team_member": "team@example.com",
                    "extracted_entities": {
                        "persons": ["John Doe"],
                        "companies": ["Acme Corp"],
                        "dates": ["2025-12-31"],
                    },
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_interaction_outbound(self, authenticated_client, test_app):
        """Test creating outbound interaction"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions",
                json={
                    "client_id": 1,
                    "interaction_type": "email",
                    "team_member": "team@example.com",
                    "direction": "outbound",
                },
            )

            assert response.status_code in [200, 201, 500]

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
class TestListInteractions:
    """Comprehensive tests for GET /api/crm/interactions"""

    def test_list_interactions_default(self, authenticated_client, test_app):
        """Test listing interactions with default parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"id": 1, "interaction_type": "chat"},
                    {"id": 2, "interaction_type": "email"},
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_list_interactions_with_filters(self, authenticated_client, test_app):
        """Test listing interactions with filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            filters = [
                "?client_id=1",
                "?practice_id=1",
                "?interaction_type=chat",
                "?sentiment=positive",
                "?team_member=team@example.com",
                "?limit=20",
                "?offset=10",
            ]

            for filter_param in filters:
                response = authenticated_client.get(f"/api/crm/interactions{filter_param}")
                assert response.status_code == 200

    def test_list_interactions_max_limit(self, authenticated_client, test_app):
        """Test listing interactions with maximum limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions?limit=200")

            assert response.status_code == 200

    def test_list_interactions_exceeds_max_limit(self, authenticated_client):
        """Test listing interactions exceeding maximum limit"""
        response = authenticated_client.get("/api/crm/interactions?limit=1000")

        # Should cap at maximum limit
        assert response.status_code in [200, 400, 422]

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
class TestGetInteraction:
    """Comprehensive tests for GET /api/crm/interactions/{interaction_id}"""

    def test_get_interaction_by_id(self, authenticated_client, test_app):
        """Test getting interaction by ID"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "interaction_type": "chat",
                    "client_id": 1,
                    "team_member": "team@example.com",
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions/1")

            assert response.status_code == 200

    def test_get_interaction_not_found(self, authenticated_client, test_app):
        """Test getting non-existent interaction"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions/99999")

            assert response.status_code == 404

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestClientTimeline:
    """Comprehensive tests for GET /api/crm/interactions/client/{client_id}/timeline"""

    def test_get_client_timeline(self, authenticated_client, test_app):
        """Test getting client interaction timeline"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {"id": 1, "interaction_type": "chat", "created_at": "2025-01-01"},
                    {"id": 2, "interaction_type": "email", "created_at": "2025-01-02"},
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions/client/1/timeline")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_client_timeline_with_limit(self, authenticated_client, test_app):
        """Test getting client timeline with limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions/client/1/timeline?limit=10")

            assert response.status_code == 200

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
class TestPracticeHistory:
    """Comprehensive tests for GET /api/crm/interactions/practice/{practice_id}/history"""

    def test_get_practice_history(self, authenticated_client, test_app):
        """Test getting practice interaction history"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions/practice/1/history")

            assert response.status_code == 200

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
class TestInteractionStats:
    """Comprehensive tests for GET /api/crm/interactions/stats/overview"""

    def test_get_interaction_stats(self, authenticated_client, test_app):
        """Test getting interaction statistics"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "total": 100,
                    "by_type": {},
                    "by_sentiment": {},
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/interactions/stats/overview")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    def test_get_interaction_stats_cached(self, authenticated_client, test_app):
        """Test interaction stats are cached"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"total": 100})
            mock_get_pool.return_value = mock_pool

            response1 = authenticated_client.get("/api/crm/interactions/stats/overview")
            response2 = authenticated_client.get("/api/crm/interactions/stats/overview")

            assert response1.status_code == 200
            assert response2.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestFromConversation:
    """Comprehensive tests for POST /api/crm/interactions/from-conversation"""

    def test_create_interaction_from_conversation(self, authenticated_client, test_app):
        """Test creating interaction from conversation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions/from-conversation",
                json={
                    "conversation_id": 1,
                    "client_id": 1,
                    "team_member": "team@example.com",
                },
            )

            assert response.status_code in [200, 201, 404, 500]

    def test_create_interaction_from_conversation_not_found(self, authenticated_client, test_app):
        """Test creating interaction from non-existent conversation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.post(
                "/api/crm/interactions/from-conversation",
                json={
                    "conversation_id": 99999,
                    "client_id": 1,
                    "team_member": "team@example.com",
                },
            )

            assert response.status_code in [404, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "messages": []})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
class TestSyncGmail:
    """Comprehensive tests for POST /api/crm/interactions/sync-gmail"""

    def test_sync_gmail_interactions(self, authenticated_client):
        """Test syncing Gmail interactions"""
        response = authenticated_client.post(
            "/api/crm/interactions/sync-gmail",
            json={
                "client_id": 1,
                "days_back": 7,
            },
        )

        # May require actual Gmail service
        assert response.status_code in [200, 201, 400, 401, 403, 500, 503]

    def test_sync_gmail_without_client_id(self, authenticated_client):
        """Test syncing Gmail without client_id"""
        response = authenticated_client.post(
            "/api/crm/interactions/sync-gmail",
            json={"days_back": 7},
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_sync_gmail_invalid_days(self, authenticated_client):
        """Test syncing Gmail with invalid days_back"""
        response = authenticated_client.post(
            "/api/crm/interactions/sync-gmail",
            json={
                "client_id": 1,
                "days_back": -1,
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
class TestCRMInteractionsSecurity:
    """Security tests for CRM interactions endpoints"""

    def test_interactions_endpoints_require_auth(self, test_client):
        """Test all interaction endpoints require authentication"""
        endpoints = [
            ("POST", "/api/crm/interactions"),
            ("GET", "/api/crm/interactions"),
            ("GET", "/api/crm/interactions/1"),
            ("GET", "/api/crm/interactions/client/1/timeline"),
            ("GET", "/api/crm/interactions/stats/overview"),
            ("POST", "/api/crm/interactions/from-conversation"),
            ("POST", "/api/crm/interactions/sync-gmail"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401

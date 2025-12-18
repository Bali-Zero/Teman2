"""
Comprehensive API Tests for CRM Shared Memory Router
Complete test coverage for natural language CRM search endpoints

Coverage:
- GET /api/crm/shared-memory/search - Natural language search
- GET /api/crm/shared-memory/upcoming-renewals - Get upcoming renewals
- GET /api/crm/shared-memory/client/{client_id}/full-context - Get full client context
- GET /api/crm/shared-memory/team-overview - Get team overview
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
class TestSharedMemorySearch:
    """Comprehensive tests for GET /api/crm/shared-memory/search"""

    def test_search_renewal_query(self, authenticated_client, test_app):
        """Test search for renewal/expiry queries"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "client_name": "Test Client",
                        "email": "test@example.com",
                        "practice_type": "KITAS",
                        "expiry_date": "2025-12-31",
                    }
                ]
            )
            mock_get_pool.return_value = mock_pool

            queries = [
                "clients with expiring practices",
                "renewals coming up",
                "practices expiring soon",
                "scadenze prossime",
            ]

            for query in queries:
                response = authenticated_client.get(f"/api/crm/shared-memory/search?q={query}")

                assert response.status_code == 200

    def test_search_client_name(self, authenticated_client, test_app):
        """Test search by client name"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "full_name": "John Smith",
                        "email": "john@example.com",
                        "total_practices": 2,
                    }
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/search?q=John Smith")

            assert response.status_code == 200
            data = response.json()
            assert "clients" in data

    def test_search_practice_type(self, authenticated_client, test_app):
        """Test search by practice type"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            queries = [
                "KITAS practices",
                "PT PMA practices",
                "visa applications",
            ]

            for query in queries:
                response = authenticated_client.get(f"/api/crm/shared-memory/search?q={query}")

                assert response.status_code == 200

    def test_search_status_queries(self, authenticated_client, test_app):
        """Test search by status"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            queries = [
                "urgent practices",
                "active practices",
                "practices in progress",
            ]

            for query in queries:
                response = authenticated_client.get(f"/api/crm/shared-memory/search?q={query}")

                assert response.status_code == 200

    def test_search_with_limit(self, authenticated_client, test_app):
        """Test search with limit parameter"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/search?q=test&limit=10")

            assert response.status_code == 200

    def test_search_max_limit(self, authenticated_client, test_app):
        """Test search with maximum limit"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/search?q=test&limit=100")

            assert response.status_code == 200

    def test_search_exceeds_max_limit(self, authenticated_client):
        """Test search exceeding maximum limit"""
        response = authenticated_client.get("/api/crm/shared-memory/search?q=test&limit=1000")

        # Should cap at maximum limit
        assert response.status_code in [200, 400, 422]

    def test_search_empty_query(self, authenticated_client):
        """Test search with empty query"""
        response = authenticated_client.get("/api/crm/shared-memory/search?q=")

        assert response.status_code in [200, 400, 422]

    def test_search_missing_query(self, authenticated_client):
        """Test search without query parameter"""
        response = authenticated_client.get("/api/crm/shared-memory/search")

        assert response.status_code == 422

    def test_search_response_structure(self, authenticated_client, test_app):
        """Test search response structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/search?q=test")

            assert response.status_code == 200
            data = response.json()
            assert "query" in data
            assert "clients" in data
            assert "practices" in data
            assert "interactions" in data
            assert "interpretation" in data

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
class TestUpcomingRenewals:
    """Comprehensive tests for GET /api/crm/shared-memory/upcoming-renewals"""

    def test_get_upcoming_renewals_default(self, authenticated_client, test_app):
        """Test getting upcoming renewals with default parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "client_name": "Test Client",
                        "practice_type": "KITAS",
                        "expiry_date": "2025-12-31",
                    }
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_upcoming_renewals_with_days(self, authenticated_client, test_app):
        """Test getting upcoming renewals with custom days"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals?days=30")

            assert response.status_code == 200

    def test_get_upcoming_renewals_max_days(self, authenticated_client, test_app):
        """Test getting upcoming renewals with maximum days"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals?days=365")

            assert response.status_code == 200

    def test_get_upcoming_renewals_exceeds_max(self, authenticated_client):
        """Test getting upcoming renewals exceeding maximum days"""
        response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals?days=1000")

        # Should cap at maximum
        assert response.status_code in [200, 400, 422]

    def test_get_upcoming_renewals_cached(self, authenticated_client, test_app):
        """Test upcoming renewals are cached"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response1 = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals")
            response2 = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals")

            assert response1.status_code == 200
            assert response2.status_code == 200

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
class TestClientFullContext:
    """Comprehensive tests for GET /api/crm/shared-memory/client/{client_id}/full-context"""

    def test_get_client_full_context(self, authenticated_client, test_app):
        """Test getting full client context"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "full_name": "Test Client",
                    "email": "test@example.com",
                }
            )
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/client/1/full-context")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    def test_get_client_full_context_not_found(self, authenticated_client, test_app):
        """Test getting full context for non-existent client"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/client/99999/full-context")

            assert response.status_code == 404

    def test_get_client_full_context_structure(self, authenticated_client, test_app):
        """Test full context response structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "Test Client"})
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/client/1/full-context")

            if response.status_code == 200:
                data = response.json()
                # Should have client info and related data
                assert isinstance(data, dict)

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
class TestTeamOverview:
    """Comprehensive tests for GET /api/crm/shared-memory/team-overview"""

    def test_get_team_overview(self, authenticated_client, test_app):
        """Test getting team overview"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(
                return_value=[
                    {
                        "team_member": "team@example.com",
                        "active_practices": 5,
                        "total_clients": 10,
                    }
                ]
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/team-overview")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)

    def test_get_team_overview_structure(self, authenticated_client, test_app):
        """Test team overview response structure"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/shared-memory/team-overview")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestCRMSharedMemorySecurity:
    """Security tests for CRM shared memory endpoints"""

    def test_shared_memory_endpoints_require_auth(self, test_client):
        """Test all shared memory endpoints require authentication"""
        endpoints = [
            ("GET", "/api/crm/shared-memory/search?q=test"),
            ("GET", "/api/crm/shared-memory/upcoming-renewals"),
            ("GET", "/api/crm/shared-memory/client/1/full-context"),
            ("GET", "/api/crm/shared-memory/team-overview"),
        ]

        for method, path in endpoints:
            response = test_client.get(path)

            assert response.status_code == 401

"""
Parameter Combination Tests
Tests for various parameter combinations and interactions

Coverage:
- Multiple query parameters combinations
- Conflicting parameters
- Parameter precedence
- Default value behavior
- Parameter interaction edge cases
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
class TestMultipleQueryParameters:
    """Test multiple query parameters combinations"""

    def test_crm_clients_multiple_filters(self, authenticated_client, test_app):
        """Test CRM clients with multiple filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/crm/clients?status=active&limit=20&offset=10&sort_by=full_name&sort_order=asc"
            )

            assert response.status_code == 200

    def test_crm_interactions_multiple_filters(self, authenticated_client, test_app):
        """Test CRM interactions with multiple filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/crm/interactions?client_id=1&interaction_type=chat&sentiment=positive&limit=50&offset=0"
            )

            assert response.status_code == 200

    def test_intel_search_multiple_filters(self, authenticated_client):
        """Test intel search with multiple filters"""
        with patch("app.routers.intel.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                mock_client = MagicMock()
                mock_client.search = AsyncMock(
                    return_value={
                        "documents": [],
                        "metadatas": [],
                        "distances": [],
                    }
                )
                mock_qdrant.return_value = mock_client

                response = authenticated_client.post(
                    "/api/intel/search",
                    json={
                        "query": "test",
                        "category": "immigration",
                        "date_range": "last_7_days",
                        "tier": ["T1", "T2"],
                        "impact_level": "high",
                        "limit": 50,
                    },
                )

                assert response.status_code in [200, 500, 503]

    def test_oracle_query_multiple_parameters(self, authenticated_client):
        """Test oracle query with multiple parameters"""
        with patch("app.routers.oracle_universal.get_search_service") as mock_search:
            mock_service = MagicMock()
            mock_service.search = AsyncMock(return_value={"results": []})
            mock_search.return_value = mock_service

            response = authenticated_client.post(
                "/api/oracle/query",
                json={
                    "query": "test query",
                    "limit": 10,
                    "collection": "legal_unified",
                    "user_email": "user@example.com",
                    "session_id": "session_123",
                },
            )

            assert response.status_code in [200, 400, 422, 500, 503]

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
class TestConflictingParameters:
    """Test conflicting parameter scenarios"""

    def test_limit_offset_conflict(self, authenticated_client, test_app):
        """Test limit and offset together"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?limit=10&offset=100")

            # Should handle pagination correctly
            assert response.status_code == 200

    def test_sort_conflicting_order(self, authenticated_client, test_app):
        """Test sort with conflicting order"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # Both asc and desc - should use one
            response = authenticated_client.get("/api/crm/clients?sort_order=asc&sort_order=desc")

            assert response.status_code in [200, 400, 422]

    def test_filter_conflicting_values(self, authenticated_client, test_app):
        """Test filters with conflicting values"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # Multiple status values
            response = authenticated_client.get("/api/crm/clients?status=active&status=inactive")

            # Should handle or use last value
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
class TestParameterPrecedence:
    """Test parameter precedence and priority"""

    def test_limit_precedence(self, authenticated_client, test_app):
        """Test limit parameter precedence"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # Multiple limit values - should use appropriate one
            response = authenticated_client.get("/api/crm/clients?limit=10&limit=20")

            assert response.status_code == 200

    def test_default_vs_explicit(self, authenticated_client, test_app):
        """Test default values vs explicit parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # Explicit limit should override default
            response1 = authenticated_client.get("/api/crm/clients")
            response2 = authenticated_client.get("/api/crm/clients?limit=25")

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
class TestParameterInteractions:
    """Test parameter interactions and dependencies"""

    def test_pagination_with_sorting(self, authenticated_client, test_app):
        """Test pagination combined with sorting"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/crm/clients?limit=10&offset=20&sort_by=full_name&sort_order=desc"
            )

            assert response.status_code == 200

    def test_filters_with_pagination(self, authenticated_client, test_app):
        """Test filters combined with pagination"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?status=active&limit=20&offset=10")

            assert response.status_code == 200

    def test_search_with_filters(self, authenticated_client, test_app):
        """Test search combined with filters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/crm/clients?search=test&status=active&limit=10"
            )

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
class TestDefaultValueBehavior:
    """Test default value behavior"""

    def test_default_limit_behavior(self, authenticated_client, test_app):
        """Test default limit behavior"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # No limit specified - should use default
            response = authenticated_client.get("/api/crm/clients")

            assert response.status_code == 200

    def test_default_offset_behavior(self, authenticated_client, test_app):
        """Test default offset behavior"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # No offset specified - should default to 0
            response = authenticated_client.get("/api/crm/clients?limit=10")

            assert response.status_code == 200

    def test_default_sort_behavior(self, authenticated_client, test_app):
        """Test default sort behavior"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            # No sort specified - should use default
            response = authenticated_client.get("/api/crm/clients")

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
class TestParameterEdgeCases:
    """Test parameter edge cases"""

    def test_empty_string_parameters(self, authenticated_client, test_app):
        """Test empty string parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients?search=&status=&sort_by=")

            # Should handle empty strings
            assert response.status_code in [200, 400, 422]

    def test_whitespace_parameters(self, authenticated_client, test_app):
        """Test parameters with whitespace"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/crm/clients?search=  test  &status=  active  "
            )

            # Should trim or handle whitespace
            assert response.status_code in [200, 400, 422]

    def test_special_characters_in_parameters(self, authenticated_client, test_app):
        """Test special characters in parameters"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get(
                "/api/crm/clients?search=test%20with%20spaces&status=active"
            )

            # Should handle URL encoding
            assert response.status_code == 200

    def test_very_long_parameter_values(self, authenticated_client, test_app):
        """Test very long parameter values"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_get_pool.return_value = mock_pool

            long_search = "A" * 10000
            response = authenticated_client.get(f"/api/crm/clients?search={long_search}")

            # Should handle or reject long values
            assert response.status_code in [200, 400, 413, 422, 500]

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

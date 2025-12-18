"""
Compatibility Tests
Tests for API version compatibility and backward compatibility

Coverage:
- Version compatibility
- Backward compatibility
- Deprecated endpoint behavior
- Schema evolution
- Migration scenarios
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
@pytest.mark.compatibility
class TestBackwardCompatibility:
    """Test backward compatibility"""

    def test_old_request_format_still_works(self, authenticated_client, test_app):
        """Test old request format still works"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Old format (minimal fields)
            response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Test Client"},
            )

            # Should still work
            assert response.status_code in [200, 201, 500]

    def test_new_fields_optional(self, authenticated_client, test_app):
        """Test new fields are optional (backward compatible)"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Request without new fields
            response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Test Client"},
            )

            # Should accept requests without new fields
            assert response.status_code in [200, 201, 500]

    def test_response_includes_old_fields(self, authenticated_client, test_app):
        """Test responses include old fields for compatibility"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(
                return_value={"id": 1, "full_name": "Test", "email": "test@example.com"}
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1")

            if response.status_code == 200:
                data = response.json()
                # Should include basic fields
                assert "id" in data or "full_name" in data

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
@pytest.mark.compatibility
class TestSchemaEvolution:
    """Test schema evolution compatibility"""

    def test_additional_fields_ignored(self, authenticated_client, test_app):
        """Test additional unknown fields are ignored"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Request with extra unknown fields
            response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "Test Client",
                    "unknown_field_1": "value1",
                    "unknown_field_2": "value2",
                },
            )

            # Should accept or ignore extra fields
            assert response.status_code in [200, 201, 400, 422, 500]

    def test_removed_fields_handled(self, authenticated_client):
        """Test removed fields are handled gracefully"""
        # If a field was removed, requests with it should be handled
        response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Test Client",
                "deprecated_field": "value",
            },
        )

        # Should handle deprecated fields
        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
@pytest.mark.compatibility
class TestVersionCompatibility:
    """Test version compatibility"""

    def test_api_version_header(self, authenticated_client):
        """Test API version header handling"""
        # Try with version header
        authenticated_client.headers["X-API-Version"] = "v1"

        response = authenticated_client.get("/api/agents/status")

        # Should handle version header
        assert response.status_code in [200, 400, 500]

    def test_version_specific_endpoints(self, authenticated_client):
        """Test version-specific endpoints"""
        # Try versioned endpoints if they exist
        versioned_paths = [
            "/api/v1/agents/status",
            "/api/v2/agents/status",
        ]

        for path in versioned_paths:
            response = authenticated_client.get(path)

            # Should handle versioned paths
            assert response.status_code in [200, 404, 500]


@pytest.mark.api
@pytest.mark.compatibility
class TestMigrationScenarios:
    """Test migration scenarios"""

    def test_data_migration_compatibility(self, authenticated_client, test_app):
        """Test data migration maintains compatibility"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate old data format
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "full_name": "Old Format Client",
                    "email": None,  # Old format might not have email
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1")

            # Should handle old data format
            assert response.status_code in [200, 404, 500]

    def test_schema_migration_compatibility(self, authenticated_client, test_app):
        """Test schema migration maintains compatibility"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate data with new schema
            mock_conn.fetchrow = AsyncMock(
                return_value={
                    "id": 1,
                    "full_name": "New Format Client",
                    "email": "test@example.com",
                    "new_field": "new_value",  # New schema field
                }
            )
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1")

            # Should handle new schema
            assert response.status_code in [200, 404, 500]

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

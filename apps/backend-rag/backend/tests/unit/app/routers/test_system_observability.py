"""
Unit tests for system observability router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.system_observability import router
from app.routers.team_activity import get_admin_email
from services.monitoring.unified_health_service import get_unified_health_service


@pytest.fixture
def mock_unified_health_service():
    """Mock UnifiedHealthService"""
    service = MagicMock()
    service.http_client = None
    service.initialize = AsyncMock()
    service.run_all_checks = AsyncMock(return_value={"status": "healthy"})
    return service


@pytest.fixture
def app(mock_unified_health_service):
    """Create FastAPI app with router and dependency overrides"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_admin_email] = lambda: "admin@example.com"
    app.dependency_overrides[get_unified_health_service] = lambda: mock_unified_health_service
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestSystemObservabilityRouter:
    """Tests for system observability router"""

    def test_get_system_health(self, app, client, mock_unified_health_service):
        """Test getting system health"""
        response = client.get("/api/admin/system-health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_get_system_health_initializes_service(self, app, client, mock_unified_health_service):
        """Test system health initializes service if needed"""
        mock_unified_health_service.http_client = None
        response = client.get("/api/admin/system-health")
        assert response.status_code == 200
        mock_unified_health_service.initialize.assert_called_once()

    def test_get_system_health_error(self, app, client, mock_unified_health_service):
        """Test system health with error"""
        mock_unified_health_service.run_all_checks = AsyncMock(
            side_effect=Exception("Service error")
        )
        app.dependency_overrides[get_unified_health_service] = lambda: mock_unified_health_service

        response = client.get("/api/admin/system-health")
        assert response.status_code == 500

    @patch("app.core.config.settings")
    @patch("asyncpg.connect")
    def test_get_postgres_tables(self, mock_connect, mock_settings, app, client):
        """Test getting PostgreSQL tables"""
        mock_settings.database_url = "postgresql://test"
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"table_name": "test_table"}.get(key)
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.close = AsyncMock()
        mock_connect.return_value = mock_conn

        response = client.get("/api/admin/postgres/tables")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @patch("app.core.config.settings")
    @patch("asyncpg.connect")
    def test_get_postgres_tables_error(self, mock_connect, mock_settings, app, client):
        """Test getting PostgreSQL tables with error"""
        mock_settings.database_url = "postgresql://test"
        mock_connect.side_effect = Exception("Connection error")

        response = client.get("/api/admin/postgres/tables")
        assert response.status_code == 500

    @patch("app.core.config.settings")
    @patch("asyncpg.connect")
    def test_get_table_data(self, mock_connect, mock_settings, app, client):
        """Test getting table data"""
        mock_settings.database_url = "postgresql://test"
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"column1": "value1"}.get(key)
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.close = AsyncMock()
        mock_connect.return_value = mock_conn

        response = client.get("/api/admin/postgres/data?table=test_table")
        assert response.status_code == 200
        data = response.json()
        assert "table" in data
        assert "rows" in data or "data" in data

    def test_get_table_data_invalid_table_name(self):
        """Test getting table data with invalid table name"""
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_admin_email] = lambda: "admin@example.com"
        client = TestClient(app)

        response = client.get("/api/admin/postgres/data?table=test-table!")
        assert response.status_code == 400

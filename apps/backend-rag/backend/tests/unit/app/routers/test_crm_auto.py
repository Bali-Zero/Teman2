"""
Unit tests for CRM Auto Router
Target: >99% coverage
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.dependencies import get_database_pool
from app.routers.crm_auto import router


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()
    conn = AsyncMock()

    # Mock rows for various queries
    mock_total_extractions = MagicMock()
    mock_total_extractions.__getitem__ = lambda self, key: {"count": 100}.get(key)
    mock_total_extractions["count"] = 100

    mock_successful = MagicMock()
    mock_successful.__getitem__ = lambda self, key: {"count": 80}.get(key)
    mock_successful["count"] = 80

    mock_clients_created = MagicMock()
    mock_clients_created.__getitem__ = lambda self, key: {"count": 20}.get(key)
    mock_clients_created["count"] = 20

    mock_clients_updated = MagicMock()
    mock_clients_updated.__getitem__ = lambda self, key: {"count": 15}.get(key)
    mock_clients_updated["count"] = 15

    mock_practices_created = MagicMock()
    mock_practices_created.__getitem__ = lambda self, key: {"count": 10}.get(key)
    mock_practices_created["count"] = 10

    mock_last_24h = MagicMock()
    mock_last_24h.__getitem__ = lambda self, key: {
        "extractions": 10,
        "clients": 5,
        "practices": 3,
    }.get(key)
    mock_last_24h["extractions"] = 10
    mock_last_24h["clients"] = 5
    mock_last_24h["practices"] = 3

    mock_last_7d = MagicMock()
    mock_last_7d.__getitem__ = lambda self, key: {
        "extractions": 50,
        "clients": 12,
        "practices": 8,
    }.get(key)
    mock_last_7d["extractions"] = 50
    mock_last_7d["clients"] = 12
    mock_last_7d["practices"] = 8

    mock_confidence = MagicMock()
    mock_confidence.__getitem__ = lambda self, key: {"avg_confidence": 0.85}.get(key)
    mock_confidence["avg_confidence"] = 0.85

    mock_top_practices = MagicMock()
    mock_top_practices.__getitem__ = lambda self, idx: [
        {"code": "KITAS", "name": "KITAS", "count": 5},
        {"code": "PMA", "name": "PT PMA", "count": 3},
    ][idx]
    mock_top_practices.__iter__ = lambda self: iter(
        [
            {"code": "KITAS", "name": "KITAS", "count": 5},
            {"code": "PMA", "name": "PT PMA", "count": 3},
        ]
    )

    mock_recent = MagicMock()
    mock_recent.__getitem__ = lambda self, idx: [
        {
            "id": 1,
            "client_id": 1,
            "practice_id": 1,
            "summary": "Test interaction",
            "sentiment": "positive",
            "created_at": datetime.now(),
            "client_name": "Test Client",
            "practice_type_code": "KITAS",
        }
    ][idx]
    mock_recent.__iter__ = lambda self: iter(
        [
            {
                "id": 1,
                "client_id": 1,
                "practice_id": 1,
                "summary": "Test interaction",
                "sentiment": "positive",
                "created_at": datetime.now(),
                "client_name": "Test Client",
                "practice_type_code": "KITAS",
            }
        ]
    )

    # Setup fetchrow side_effect for multiple calls
    conn.fetchrow = AsyncMock(
        side_effect=[
            mock_total_extractions,
            mock_successful,
            mock_clients_created,
            mock_clients_updated,
            mock_practices_created,
            mock_last_24h,
            mock_last_7d,
            mock_confidence,
        ]
    )
    conn.fetch = AsyncMock(side_effect=[mock_top_practices, mock_recent])

    # Create async context manager
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)

    return pool


@pytest.fixture
def app(mock_db_pool):
    """Create FastAPI app with router and dependency override"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestCRMAutoRouter:
    """Tests for CRM Auto Router"""

    def test_get_auto_crm_stats_success(self, client, mock_db_pool):
        """Test getting AUTO CRM stats successfully"""
        response = client.get("/api/crm/auto/stats?days=7")
        assert response.status_code == 200
        data = response.json()
        assert "total_extractions" in data
        assert "successful_extractions" in data
        assert "failed_extractions" in data
        assert "clients_created" in data
        assert "clients_updated" in data
        assert "practices_created" in data
        assert "last_24h" in data
        assert "last_7d" in data
        assert "extraction_confidence_avg" in data
        assert "top_practice_types" in data
        assert "recent_extractions" in data

    def test_get_auto_crm_stats_default_days(self, client, mock_db_pool):
        """Test getting AUTO CRM stats with default days parameter"""
        response = client.get("/api/crm/auto/stats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_auto_crm_stats_custom_days(self, client, mock_db_pool):
        """Test getting AUTO CRM stats with custom days parameter"""
        response = client.get("/api/crm/auto/stats?days=30")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_auto_crm_stats_min_days(self, client, mock_db_pool):
        """Test getting AUTO CRM stats with minimum days (1)"""
        response = client.get("/api/crm/auto/stats?days=1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_auto_crm_stats_max_days(self, client, mock_db_pool):
        """Test getting AUTO CRM stats with maximum days (30)"""
        response = client.get("/api/crm/auto/stats?days=30")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_auto_crm_stats_invalid_days_too_low(self, client):
        """Test getting AUTO CRM stats with invalid days (< 1)"""
        response = client.get("/api/crm/auto/stats?days=0")
        assert response.status_code == 422  # Validation error

    def test_get_auto_crm_stats_invalid_days_too_high(self, client):
        """Test getting AUTO CRM stats with invalid days (> 30)"""
        response = client.get("/api/crm/auto/stats?days=31")
        assert response.status_code == 422  # Validation error

    def test_get_auto_crm_stats_no_confidence(self, client):
        """Test getting AUTO CRM stats when no confidence data"""
        pool = MagicMock()
        conn = AsyncMock()

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"count": 0}.get(key)
        mock_row["count"] = 0

        mock_confidence_none = MagicMock()
        mock_confidence_none.__getitem__ = lambda self, key: {"avg_confidence": None}.get(key)
        mock_confidence_none["avg_confidence"] = None

        mock_empty_list = MagicMock()
        mock_empty_list.__iter__ = lambda self: iter([])

        conn.fetchrow = AsyncMock(
            side_effect=[
                mock_row,  # total_extractions
                mock_row,  # successful
                mock_row,  # clients_created
                mock_row,  # clients_updated
                mock_row,  # practices_created
                mock_row,  # last_24h
                mock_row,  # last_7d
                mock_confidence_none,  # confidence
            ]
        )
        conn.fetch = AsyncMock(side_effect=[mock_empty_list, mock_empty_list])

        acquire_cm = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acquire_cm)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_database_pool] = lambda: pool
        test_client = TestClient(app)

        response = test_client.get("/api/crm/auto/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["extraction_confidence_avg"] is None

    def test_get_auto_crm_stats_empty_data(self, client):
        """Test getting AUTO CRM stats with empty data"""
        pool = MagicMock()
        conn = AsyncMock()

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"count": 0}.get(key)
        mock_row["count"] = 0

        mock_confidence_none = MagicMock()
        mock_confidence_none.__getitem__ = lambda self, key: {"avg_confidence": None}.get(key)
        mock_confidence_none["avg_confidence"] = None

        mock_empty_list = MagicMock()
        mock_empty_list.__iter__ = lambda self: iter([])

        conn.fetchrow = AsyncMock(
            side_effect=[
                mock_row,
                mock_row,
                mock_row,
                mock_row,
                mock_row,
                mock_row,
                mock_row,
                mock_confidence_none,
            ]
        )
        conn.fetch = AsyncMock(side_effect=[mock_empty_list, mock_empty_list])

        acquire_cm = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acquire_cm)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_database_pool] = lambda: pool
        test_client = TestClient(app)

        response = test_client.get("/api/crm/auto/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_extractions"] == 0
        assert data["successful_extractions"] == 0
        assert data["failed_extractions"] == 0
        assert data["clients_created"] == 0
        assert data["clients_updated"] == 0
        assert data["practices_created"] == 0

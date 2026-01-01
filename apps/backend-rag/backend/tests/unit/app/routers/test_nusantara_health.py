"""
Unit tests for nusantara health router
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.nusantara_health import router, get_status_from_score


@pytest.fixture
def app():
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestNusantaraHealthRouter:
    """Tests for nusantara health router"""

    def test_get_nusantara_health(self, client):
        """Test getting Nusantara health"""
        response = client.get("/api/nusantara/health")
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "overall_score" in data
        assert "overall_status" in data
        assert "status_counts" in data
        assert "islands" in data
        assert len(data["islands"]) > 0

    def test_get_status_from_score_healthy(self):
        """Test status from score - healthy"""
        assert get_status_from_score(95.0) == "healthy"
        assert get_status_from_score(90.0) == "healthy"

    def test_get_status_from_score_warning(self):
        """Test status from score - warning"""
        assert get_status_from_score(75.0) == "warning"
        assert get_status_from_score(70.0) == "warning"

    def test_get_status_from_score_degraded(self):
        """Test status from score - degraded"""
        assert get_status_from_score(60.0) == "degraded"
        assert get_status_from_score(50.0) == "degraded"

    def test_get_status_from_score_critical(self):
        """Test status from score - critical"""
        assert get_status_from_score(40.0) == "critical"
        assert get_status_from_score(0.0) == "critical"

    def test_nusantara_health_structure(self, client):
        """Test Nusantara health response structure"""
        response = client.get("/api/nusantara/health")
        assert response.status_code == 200
        data = response.json()
        
        # Check island structure
        for island_name, island_data in data["islands"].items():
            assert "name" in island_data
            assert "label" in island_data
            assert "health_score" in island_data
            assert "status" in island_data
            assert "metrics" in island_data
            assert "coordinates" in island_data


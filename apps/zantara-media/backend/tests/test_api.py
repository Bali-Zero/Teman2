"""
ZANTARA MEDIA - API Tests
Tests for FastAPI endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


class TestAutomationAPI:
    """Test automation API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ZANTARA MEDIA"

    @patch("app.routers.automation.scheduler_service")
    def test_get_automation_status(self, mock_scheduler, client):
        """Test getting automation status."""
        mock_scheduler.get_status.return_value = {
            "running": True,
            "jobs": [
                {
                    "id": "daily_content_generation",
                    "name": "Daily Content Generation Pipeline",
                    "next_run": "2025-01-11T06:00:00",
                    "trigger": "cron[hour=6, minute=0]",
                }
            ],
        }

        response = client.get("/api/automation/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "daily_content_generation"

    @patch("app.routers.automation.scheduler_service")
    def test_trigger_manual_run(self, mock_scheduler, client):
        """Test triggering manual pipeline run."""
        response = client.post("/api/automation/trigger")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "triggered successfully" in data["message"].lower()


class TestContentAPI:
    """Test content API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_list_content(self, client):
        """Test listing content."""
        response = client.get("/api/content")

        assert response.status_code == 200
        data = response.json()
        # Returns a PaginatedResponse with 'items' key
        assert "items" in data
        assert "total" in data
        assert "page" in data


class TestDashboardAPI:
    """Test dashboard API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "ZANTARA MEDIA"
        assert "version" in data

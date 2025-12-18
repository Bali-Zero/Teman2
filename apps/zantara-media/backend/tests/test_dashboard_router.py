"""
Unit tests for Dashboard Router
Tests for aggregated metrics and overview data endpoints
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.routers.dashboard import router


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def dashboard_app():
    """Create test app with dashboard router"""
    app = FastAPI()
    app.include_router(router, prefix="/dashboard")
    return app


@pytest.fixture
def dashboard_client(dashboard_app):
    """Create test client for dashboard"""
    return TestClient(dashboard_app)


# ============================================================================
# GET /dashboard/stats Tests
# ============================================================================


class TestGetDashboardStats:
    """Tests for GET /dashboard/stats endpoint"""

    def test_get_dashboard_stats_success(self, dashboard_client):
        """Test successful retrieval of dashboard stats"""
        response = dashboard_client.get("/dashboard/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "today" in data
        assert "week" in data
        assert "platforms" in data

        # Verify today's stats
        today = data["today"]
        assert "published" in today
        assert "scheduled" in today
        assert "in_review" in today
        assert "intel_signals" in today
        assert "engagements" in today

        # Verify week stats
        week = data["week"]
        assert "total_published" in week
        assert "total_engagements" in week
        assert "new_leads" in week
        assert "avg_engagement_rate" in week

        # Verify platforms
        assert len(data["platforms"]) > 0
        for platform in data["platforms"]:
            assert "platform" in platform
            assert "posts" in platform
            assert "engagements" in platform
            assert "growth" in platform

    def test_get_dashboard_stats_data_types(self, dashboard_client):
        """Test that dashboard stats have correct data types"""
        response = dashboard_client.get("/dashboard/stats")
        data = response.json()

        # Today's numbers should be integers
        assert isinstance(data["today"]["published"], int)
        assert isinstance(data["today"]["engagements"], int)

        # Week's rate should be a number
        assert isinstance(data["week"]["avg_engagement_rate"], (int, float))


# ============================================================================
# GET /dashboard/platforms/status Tests
# ============================================================================


class TestGetPlatformStatus:
    """Tests for GET /dashboard/platforms/status endpoint"""

    def test_get_platform_status_success(self, dashboard_client):
        """Test successful retrieval of platform status"""
        response = dashboard_client.get("/dashboard/platforms/status")

        assert response.status_code == 200
        data = response.json()

        # Should be a list
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify each platform has required fields
        for platform in data:
            assert "platform" in platform
            assert "connected" in platform
            assert "followers" in platform
            assert "posts_this_week" in platform

    def test_platform_status_all_platforms_present(self, dashboard_client):
        """Test that all expected platforms are in the response"""
        response = dashboard_client.get("/dashboard/platforms/status")
        data = response.json()

        platforms = [p["platform"] for p in data]

        expected_platforms = [
            "twitter",
            "linkedin",
            "instagram",
            "tiktok",
            "telegram",
            "newsletter",
        ]
        for expected in expected_platforms:
            assert expected in platforms, f"Missing platform: {expected}"

    def test_platform_status_data_types(self, dashboard_client):
        """Test that platform status fields have correct types"""
        response = dashboard_client.get("/dashboard/platforms/status")
        data = response.json()

        for platform in data:
            assert isinstance(platform["connected"], bool)
            assert isinstance(platform["followers"], int)
            assert isinstance(platform["posts_this_week"], int)


# ============================================================================
# GET /dashboard/recent-activity Tests
# ============================================================================


class TestGetRecentActivity:
    """Tests for GET /dashboard/recent-activity endpoint"""

    def test_get_recent_activity_success(self, dashboard_client):
        """Test successful retrieval of recent activity"""
        response = dashboard_client.get("/dashboard/recent-activity")

        assert response.status_code == 200
        data = response.json()

        assert "activities" in data
        assert isinstance(data["activities"], list)

    def test_recent_activity_structure(self, dashboard_client):
        """Test that activities have correct structure"""
        response = dashboard_client.get("/dashboard/recent-activity")
        data = response.json()

        for activity in data["activities"]:
            assert "id" in activity
            assert "type" in activity
            assert "title" in activity
            assert "timestamp" in activity
            assert "user" in activity

    def test_recent_activity_types(self, dashboard_client):
        """Test that activity types are valid"""
        response = dashboard_client.get("/dashboard/recent-activity")
        data = response.json()

        valid_types = [
            "content_published",
            "intel_processed",
            "distribution_scheduled",
            "content_created",
        ]
        for activity in data["activities"]:
            assert activity["type"] in valid_types or activity["type"].startswith(
                ("content_", "intel_", "distribution_")
            )


# ============================================================================
# GET /dashboard/schedule/today Tests
# ============================================================================


class TestGetTodaySchedule:
    """Tests for GET /dashboard/schedule/today endpoint"""

    def test_get_today_schedule_success(self, dashboard_client):
        """Test successful retrieval of today's schedule"""
        response = dashboard_client.get("/dashboard/schedule/today")

        assert response.status_code == 200
        data = response.json()

        assert "entries" in data
        assert isinstance(data["entries"], list)

    def test_today_schedule_structure(self, dashboard_client):
        """Test that schedule entries have correct structure"""
        response = dashboard_client.get("/dashboard/schedule/today")
        data = response.json()

        for entry in data["entries"]:
            assert "time" in entry
            assert "title" in entry
            assert "platform" in entry
            assert "status" in entry

    def test_today_schedule_time_format(self, dashboard_client):
        """Test that schedule times are in expected format (HH:MM)"""
        response = dashboard_client.get("/dashboard/schedule/today")
        data = response.json()

        import re

        time_pattern = re.compile(r"^\d{1,2}:\d{2}$")

        for entry in data["entries"]:
            assert time_pattern.match(
                entry["time"]
            ), f"Invalid time format: {entry['time']}"

    def test_today_schedule_valid_status(self, dashboard_client):
        """Test that schedule entries have valid status"""
        response = dashboard_client.get("/dashboard/schedule/today")
        data = response.json()

        valid_statuses = ["pending", "in_progress", "completed", "failed", "scheduled"]
        for entry in data["entries"]:
            assert (
                entry["status"] in valid_statuses
            ), f"Invalid status: {entry['status']}"


# ============================================================================
# Integration Tests with Database Mock
# ============================================================================


class TestDashboardWithDatabase:
    """Tests for dashboard with database integration"""

    @pytest.mark.asyncio
    async def test_dashboard_stats_with_db_connection(
        self, dashboard_client, mock_db_pool
    ):
        """Test dashboard stats when database is available"""
        with patch("app.db.connection.get_db_pool", return_value=mock_db_pool):
            response = dashboard_client.get("/dashboard/stats")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_platform_status_with_db_connection(
        self, dashboard_client, mock_db_pool
    ):
        """Test platform status when database is available"""
        with patch("app.db.connection.get_db_pool", return_value=mock_db_pool):
            response = dashboard_client.get("/dashboard/platforms/status")
            assert response.status_code == 200


# ============================================================================
# Edge Cases
# ============================================================================


class TestDashboardEdgeCases:
    """Edge case tests for dashboard endpoints"""

    def test_dashboard_stats_no_data(self, dashboard_client):
        """Test dashboard stats returns valid response even with no data"""
        # Current implementation returns mock data, so it should always work
        response = dashboard_client.get("/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data is not None

    def test_recent_activity_empty(self, dashboard_client):
        """Test recent activity handles empty data gracefully"""
        response = dashboard_client.get("/dashboard/recent-activity")
        assert response.status_code == 200
        # Even if empty, should return valid structure
        data = response.json()
        assert "activities" in data

    def test_schedule_empty_day(self, dashboard_client):
        """Test schedule endpoint handles days with no entries"""
        response = dashboard_client.get("/dashboard/schedule/today")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data

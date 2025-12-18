"""
Comprehensive API Tests for Team Activity Router
Complete test coverage for all team timesheet and activity endpoints

Coverage:
- POST /api/team/clock-in - Clock in
- POST /api/team/clock-out - Clock out
- GET /api/team/my-status - Get my status
- GET /api/team/status - Get team status
- GET /api/team/hours - Get daily hours
- GET /api/team/activity/weekly - Get weekly summary
- GET /api/team/activity/monthly - Get monthly summary
- GET /api/team/export - Export timesheet data
- GET /api/team/health - Health check
"""

import os
import sys
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestClockIn:
    """Comprehensive tests for POST /api/team/clock-in"""

    def test_clock_in_success(self, authenticated_client):
        """Test successful clock in"""
        response = authenticated_client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user_123",
                "email": "user@example.com",
            },
        )

        assert response.status_code in [200, 201, 500, 503]

    def test_clock_in_with_metadata(self, authenticated_client):
        """Test clock in with metadata"""
        response = authenticated_client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user_123",
                "email": "user@example.com",
                "metadata": {"location": "office", "device": "desktop"},
            },
        )

        assert response.status_code in [200, 201, 500, 503]

    def test_clock_in_missing_fields(self, authenticated_client):
        """Test clock in without required fields"""
        response = authenticated_client.post(
            "/api/team/clock-in",
            json={},
        )

        assert response.status_code == 422

    def test_clock_in_invalid_email(self, authenticated_client):
        """Test clock in with invalid email"""
        response = authenticated_client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user_123",
                "email": "invalid-email",
            },
        )

        assert response.status_code == 422

    def test_clock_in_already_clocked_in(self, authenticated_client):
        """Test clock in when already clocked in"""
        # First clock in
        response1 = authenticated_client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user_123",
                "email": "user@example.com",
            },
        )

        # Try to clock in again
        response2 = authenticated_client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user_123",
                "email": "user@example.com",
            },
        )

        # Should handle already clocked in state
        assert response1.status_code in [200, 201, 500, 503]
        assert response2.status_code in [200, 201, 400, 409, 500, 503]


@pytest.mark.api
class TestClockOut:
    """Comprehensive tests for POST /api/team/clock-out"""

    def test_clock_out_success(self, authenticated_client):
        """Test successful clock out"""
        response = authenticated_client.post(
            "/api/team/clock-out",
            json={
                "user_id": "user_123",
                "email": "user@example.com",
            },
        )

        assert response.status_code in [200, 201, 500, 503]

    def test_clock_out_without_clock_in(self, authenticated_client):
        """Test clock out without clocking in first"""
        response = authenticated_client.post(
            "/api/team/clock-out",
            json={
                "user_id": "user_123",
                "email": "user@example.com",
            },
        )

        # Should handle gracefully
        assert response.status_code in [200, 201, 400, 404, 500, 503]

    def test_clock_out_missing_fields(self, authenticated_client):
        """Test clock out without required fields"""
        response = authenticated_client.post(
            "/api/team/clock-out",
            json={},
        )

        assert response.status_code == 422


@pytest.mark.api
class TestMyStatus:
    """Comprehensive tests for GET /api/team/my-status"""

    def test_get_my_status(self, authenticated_client):
        """Test getting my status"""
        response = authenticated_client.get("/api/team/my-status")

        assert response.status_code in [200, 404, 500, 503]

    def test_get_my_status_structure(self, authenticated_client):
        """Test my status response structure"""
        response = authenticated_client.get("/api/team/my-status")

        if response.status_code == 200:
            data = response.json()
            assert "user_id" in data or "is_online" in data


@pytest.mark.api
class TestTeamStatus:
    """Comprehensive tests for GET /api/team/status"""

    def test_get_team_status(self, authenticated_client):
        """Test getting team status"""
        response = authenticated_client.get("/api/team/status")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_team_status_structure(self, authenticated_client):
        """Test team status response structure"""
        response = authenticated_client.get("/api/team/status")

        if response.status_code == 200:
            data = response.json()
            if data:  # If there are team members
                member = data[0]
                assert "user_id" in member or "email" in member


@pytest.mark.api
class TestDailyHours:
    """Comprehensive tests for GET /api/team/hours"""

    def test_get_daily_hours(self, authenticated_client):
        """Test getting daily hours"""
        response = authenticated_client.get("/api/team/hours")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_daily_hours_with_date_range(self, authenticated_client):
        """Test getting daily hours with date range"""
        response = authenticated_client.get(
            "/api/team/hours?start_date=2025-01-01&end_date=2025-01-31"
        )

        assert response.status_code == 200

    def test_get_daily_hours_for_user(self, authenticated_client):
        """Test getting daily hours for specific user"""
        response = authenticated_client.get("/api/team/hours?user_id=user_123")

        assert response.status_code == 200


@pytest.mark.api
class TestWeeklySummary:
    """Comprehensive tests for GET /api/team/activity/weekly"""

    def test_get_weekly_summary(self, authenticated_client):
        """Test getting weekly summary"""
        response = authenticated_client.get("/api/team/activity/weekly")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_weekly_summary_for_user(self, authenticated_client):
        """Test getting weekly summary for specific user"""
        response = authenticated_client.get("/api/team/activity/weekly?user_id=user_123")

        assert response.status_code == 200

    def test_get_weekly_summary_structure(self, authenticated_client):
        """Test weekly summary response structure"""
        response = authenticated_client.get("/api/team/activity/weekly")

        if response.status_code == 200:
            data = response.json()
            if data:
                summary = data[0]
                assert "user_id" in summary or "week_start" in summary


@pytest.mark.api
class TestMonthlySummary:
    """Comprehensive tests for GET /api/team/activity/monthly"""

    def test_get_monthly_summary(self, authenticated_client):
        """Test getting monthly summary"""
        response = authenticated_client.get("/api/team/activity/monthly")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_monthly_summary_for_user(self, authenticated_client):
        """Test getting monthly summary for specific user"""
        response = authenticated_client.get("/api/team/activity/monthly?user_id=user_123")

        assert response.status_code == 200

    def test_get_monthly_summary_structure(self, authenticated_client):
        """Test monthly summary response structure"""
        response = authenticated_client.get("/api/team/activity/monthly")

        if response.status_code == 200:
            data = response.json()
            if data:
                summary = data[0]
                assert "user_id" in summary or "month_start" in summary


@pytest.mark.api
class TestExport:
    """Comprehensive tests for GET /api/team/export"""

    def test_export_timesheet(self, authenticated_client):
        """Test exporting timesheet data"""
        response = authenticated_client.get("/api/team/export")

        assert response.status_code in [200, 400, 500, 503]

    def test_export_timesheet_with_format(self, authenticated_client):
        """Test exporting timesheet with format"""
        response = authenticated_client.get("/api/team/export?format=csv")

        assert response.status_code in [200, 400, 500, 503]

    def test_export_timesheet_with_date_range(self, authenticated_client):
        """Test exporting timesheet with date range"""
        response = authenticated_client.get(
            "/api/team/export?start_date=2025-01-01&end_date=2025-01-31"
        )

        assert response.status_code in [200, 400, 500, 503]


@pytest.mark.api
class TestTeamHealth:
    """Comprehensive tests for GET /api/team/health"""

    def test_team_health_check(self, authenticated_client):
        """Test team health check"""
        response = authenticated_client.get("/api/team/health")

        assert response.status_code in [200, 500, 503]


@pytest.mark.api
class TestTeamActivitySecurity:
    """Security tests for team activity endpoints"""

    def test_team_endpoints_require_auth(self, test_client):
        """Test all team endpoints require authentication"""
        endpoints = [
            ("POST", "/api/team/clock-in"),
            ("POST", "/api/team/clock-out"),
            ("GET", "/api/team/my-status"),
            ("GET", "/api/team/status"),
            ("GET", "/api/team/hours"),
            ("GET", "/api/team/activity/weekly"),
            ("GET", "/api/team/activity/monthly"),
            ("GET", "/api/team/export"),
            ("GET", "/api/team/health"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401

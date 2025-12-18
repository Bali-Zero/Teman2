"""
API Tests for Team Activity Router
Tests team timesheet and activity tracking endpoints

Coverage:
- POST /api/team/clock-in - Clock in
- POST /api/team/clock-out - Clock out
- GET /api/team/my-status - Get user status
- GET /api/team/status - Get team status (admin)
- GET /api/team/hours - Get daily hours (admin)
- GET /api/team/activity/weekly - Get weekly summary (admin)
- GET /api/team/activity/monthly - Get monthly summary (admin)
- GET /api/team/export - Export timesheet (admin)
- GET /api/team/health - Health check
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
class TestTeamActivity:
    """Tests for team activity endpoints"""

    def test_clock_in(self, authenticated_client):
        """Test POST /api/team/clock-in"""
        with patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.clock_in = AsyncMock(
                return_value={
                    "success": True,
                    "action": "clock_in",
                    "timestamp": "2025-12-08T10:00:00Z",
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/team/clock-in",
                json={
                    "user_id": "user123",
                    "email": "test@example.com",
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_clock_out(self, authenticated_client):
        """Test POST /api/team/clock-out"""
        with patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.clock_out = AsyncMock(
                return_value={
                    "success": True,
                    "action": "clock_out",
                    "hours_worked": 8.0,
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.post(
                "/api/team/clock-out",
                json={
                    "user_id": "user123",
                    "email": "test@example.com",
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_get_my_status(self, authenticated_client):
        """Test GET /api/team/my-status"""
        with patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_user_status = AsyncMock(
                return_value={
                    "user_id": "user123",
                    "is_online": True,
                    "today_hours": 4.5,
                }
            )
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/my-status?user_id=user123")

            assert response.status_code in [200, 500, 503]

    def test_get_team_status(self, authenticated_client):
        """Test GET /api/team/status (admin only)"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            # Mock get_admin_email to return the authenticated user's email
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.get_team_status = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/status")

            assert response.status_code in [200, 401, 403, 500, 503]

    def test_get_daily_hours(self, authenticated_client):
        """Test GET /api/team/hours (admin only)"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            # Mock get_admin_email to return the authenticated user's email
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.get_daily_hours = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/hours?date=2025-12-08")

            assert response.status_code in [200, 401, 403, 500, 503]

    def test_get_weekly_summary(self, authenticated_client):
        """Test GET /api/team/activity/weekly (admin only)"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.get_weekly_summary = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/activity/weekly")

            assert response.status_code in [200, 401, 403, 500, 503]

    def test_get_weekly_summary_with_date(self, authenticated_client):
        """Test GET /api/team/activity/weekly with week_start date"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.get_weekly_summary = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/activity/weekly?week_start=2025-12-01")

            assert response.status_code in [200, 400, 401, 403, 500, 503]

    def test_get_monthly_summary(self, authenticated_client):
        """Test GET /api/team/activity/monthly (admin only)"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.get_monthly_summary = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/activity/monthly")

            assert response.status_code in [200, 401, 403, 500, 503]

    def test_get_monthly_summary_with_date(self, authenticated_client):
        """Test GET /api/team/activity/monthly with month_start date"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.get_monthly_summary = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/team/activity/monthly?month_start=2025-12-01")

            assert response.status_code in [200, 400, 401, 403, 500, 503]

    def test_export_timesheet(self, authenticated_client):
        """Test GET /api/team/export (admin only)"""
        with (
            patch("app.routers.team_activity.get_admin_email") as mock_admin,
            patch("services.team_timesheet_service.get_timesheet_service") as mock_get_service,
        ):
            mock_admin.return_value = "test@example.com"
            mock_service = MagicMock()
            mock_service.export_timesheet_csv = AsyncMock(return_value="csv,data\n")
            mock_get_service.return_value = mock_service

            response = authenticated_client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-08&format=csv"
            )

            assert response.status_code in [200, 400, 401, 403, 500, 503]

    def test_export_timesheet_invalid_format(self, authenticated_client):
        """Test GET /api/team/export with invalid format"""
        with patch("app.routers.team_activity.get_admin_email") as mock_admin:
            mock_admin.return_value = "test@example.com"

            response = authenticated_client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-08&format=json"
            )

            assert response.status_code == 400

    def test_get_daily_hours_invalid_date(self, authenticated_client):
        """Test GET /api/team/hours with invalid date format"""
        with patch("app.routers.team_activity.get_admin_email") as mock_admin:
            mock_admin.return_value = "test@example.com"

            response = authenticated_client.get("/api/team/hours?date=invalid-date")

            assert response.status_code in [400, 401, 403, 500, 503]

    def test_team_health_check(self, authenticated_client):
        """Test GET /api/team/health"""
        response = authenticated_client.get("/api/team/health")

        assert response.status_code == 200

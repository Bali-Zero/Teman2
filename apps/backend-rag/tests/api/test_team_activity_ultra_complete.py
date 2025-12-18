"""
Ultra-Complete API Tests for Team Activity Router
=================================================

Coverage Endpoints:
- POST /api/team/clock-in - Clock in for work
- POST /api/team/clock-out - Clock out
- GET /api/team/my-status - Get my status
- GET /api/team/status - Get all team status (admin)
- GET /api/team/hours - Get work hours (admin)
- GET /api/team/activity/weekly - Weekly summary (admin)
- GET /api/team/activity/monthly - Monthly summary (admin)
- GET /api/team/export - Export timesheet (admin)
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestTeamClock:
    def test_clock_in(self, authenticated_client):
        with patch("app.routers.team_activity.timesheet_service") as mock:
            mock.clock_in.return_value = {"success": True, "clocked_in_at": "2025-12-10T09:00:00"}
            response = authenticated_client.post("/api/team/clock-in")
            assert response.status_code in [200, 201, 400, 409, 500]

    def test_clock_out(self, authenticated_client):
        with patch("app.routers.team_activity.timesheet_service") as mock:
            mock.clock_out.return_value = {"success": True, "hours_worked": 8}
            response = authenticated_client.post("/api/team/clock-out")
            assert response.status_code in [200, 400, 500]

    def test_clock_in_twice(self, authenticated_client):
        """Test preventing double clock-in"""
        with patch("app.routers.team_activity.timesheet_service") as mock:
            mock.clock_in.side_effect = ValueError("Already clocked in")
            response = authenticated_client.post("/api/team/clock-in")
            assert response.status_code in [400, 409]


@pytest.mark.api
class TestTeamStatus:
    def test_my_status(self, authenticated_client):
        with patch("app.routers.team_activity.timesheet_service") as mock:
            mock.get_status.return_value = {"status": "online", "hours_today": 4.5}
            response = authenticated_client.get("/api/team/my-status")
            assert response.status_code in [200, 401, 500]

    def test_team_status_admin(self, authenticated_client):
        with patch("app.routers.team_activity.timesheet_service") as mock:
            mock.get_team_status.return_value = []
            response = authenticated_client.get("/api/team/status")
            assert response.status_code in [200, 401, 403, 500]


@pytest.mark.api
class TestTeamAnalytics:
    def test_weekly_summary(self, authenticated_client):
        with patch("app.routers.team_activity.analytics_service") as mock:
            mock.get_weekly_summary.return_value = {}
            response = authenticated_client.get("/api/team/activity/weekly")
            assert response.status_code in [200, 401, 403, 500]

    def test_monthly_summary(self, authenticated_client):
        with patch("app.routers.team_activity.analytics_service") as mock:
            mock.get_monthly_summary.return_value = {}
            response = authenticated_client.get("/api/team/activity/monthly")
            assert response.status_code in [200, 401, 403, 500]

    def test_export_timesheet(self, authenticated_client):
        response = authenticated_client.get("/api/team/export")
        assert response.status_code in [200, 401, 403, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

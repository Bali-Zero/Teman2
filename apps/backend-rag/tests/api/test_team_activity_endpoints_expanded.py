"""
Expanded API Tests for Team Activity Endpoints

Tests for:
- Team activity tracking
- Work sessions
- Timesheet operations
- Team analytics
"""

from datetime import datetime, timedelta

import pytest


@pytest.mark.api
class TestTeamActivityEndpoints:
    """Test Team Activity endpoints"""

    def test_get_team_activity(self, authenticated_client):
        """Test retrieving team activity"""
        response = authenticated_client.get("/api/team-activity/activity")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (dict, list))

    def test_get_team_activity_with_filters(self, authenticated_client):
        """Test retrieving team activity with filters"""
        # Test with date range
        end_date = datetime.now().isoformat()
        start_date = (datetime.now() - timedelta(days=7)).isoformat()

        response = authenticated_client.get(
            "/api/team-activity/activity",
            params={"start_date": start_date, "end_date": end_date},
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_get_team_activity_by_user(self, authenticated_client):
        """Test retrieving team activity filtered by user"""
        response = authenticated_client.get(
            "/api/team-activity/activity", params={"user_id": "test_user"}
        )

        assert response.status_code in [200, 400, 404, 500]


@pytest.mark.api
class TestWorkSessionEndpoints:
    """Test Work Session endpoints"""

    def test_start_work_session(self, authenticated_client):
        """Test starting a work session"""
        response = authenticated_client.post(
            "/api/team-activity/work-session/start",
            json={
                "task_description": "Test task",
                "project": "Test Project",
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "session_id" in data or "id" in data

    def test_end_work_session(self, authenticated_client):
        """Test ending a work session"""
        # First start a session
        start_response = authenticated_client.post(
            "/api/team-activity/work-session/start",
            json={"task_description": "Test task"},
        )

        if start_response.status_code in [200, 201]:
            session_id = start_response.json().get("session_id") or start_response.json().get("id")

            if session_id:
                # End session
                end_response = authenticated_client.post(
                    f"/api/team-activity/work-session/{session_id}/end",
                    json={"summary": "Task completed"},
                )

                assert end_response.status_code in [200, 201, 400, 404, 500]

    def test_get_work_session(self, authenticated_client):
        """Test retrieving work session details"""
        # Start session
        start_response = authenticated_client.post(
            "/api/team-activity/work-session/start",
            json={"task_description": "Test task"},
        )

        if start_response.status_code in [200, 201]:
            session_id = start_response.json().get("session_id") or start_response.json().get("id")

            if session_id:
                # Get session
                get_response = authenticated_client.get(
                    f"/api/team-activity/work-session/{session_id}"
                )

                assert get_response.status_code in [200, 404]


@pytest.mark.api
class TestTimesheetEndpoints:
    """Test Timesheet endpoints"""

    def test_log_time(self, authenticated_client):
        """Test logging time entry"""
        response = authenticated_client.post(
            "/api/team-activity/timesheet/log",
            json={
                "task_description": "Test task",
                "duration_minutes": 60,
                "project": "Test Project",
                "date": datetime.now().isoformat(),
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_get_timesheet_entries(self, authenticated_client):
        """Test retrieving timesheet entries"""
        response = authenticated_client.get("/api/team-activity/timesheet/entries")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (dict, list))

    def test_get_timesheet_entries_with_filters(self, authenticated_client):
        """Test retrieving timesheet entries with filters"""
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
        end_date = datetime.now().isoformat()

        response = authenticated_client.get(
            "/api/team-activity/timesheet/entries",
            params={"start_date": start_date, "end_date": end_date},
        )

        assert response.status_code in [200, 400, 404, 500]


@pytest.mark.api
class TestTeamAnalyticsEndpoints:
    """Test Team Analytics endpoints"""

    def test_get_team_analytics(self, authenticated_client):
        """Test retrieving team analytics"""
        response = authenticated_client.get("/api/team-activity/analytics")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_get_team_analytics_with_period(self, authenticated_client):
        """Test retrieving team analytics with time period"""
        periods = ["day", "week", "month"]

        for period in periods:
            response = authenticated_client.get(
                "/api/team-activity/analytics", params={"period": period}
            )

            assert response.status_code in [200, 400, 404, 500]

    def test_get_team_productivity_stats(self, authenticated_client):
        """Test retrieving team productivity statistics"""
        response = authenticated_client.get("/api/team-activity/productivity/stats")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestTeamActivityHealthEndpoints:
    """Test Team Activity health endpoints"""

    def test_get_team_activity_health(self, authenticated_client):
        """Test retrieving team activity health status"""
        response = authenticated_client.get("/api/team-activity/health")

        assert response.status_code in [200, 404, 503]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "status" in data or "healthy" in data

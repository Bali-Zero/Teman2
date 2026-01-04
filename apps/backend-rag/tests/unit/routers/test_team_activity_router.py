"""
Unit tests for team_activity router - targeting 90% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# UNIT TESTS FOR HELPER FUNCTIONS
# ============================================================================


class TestVerifyAdmin:
    """Tests for verify_admin function"""

    def test_verify_admin_valid_zero_email(self):
        """Test admin verification with zero@balizero.com"""
        from app.routers.team_activity import verify_admin

        assert verify_admin("zero@balizero.com") is True

    def test_verify_admin_valid_zantara_email(self):
        """Test admin verification with admin@zantara.io"""
        from app.routers.team_activity import verify_admin

        assert verify_admin("admin@zantara.io") is True

    def test_verify_admin_valid_balizero_admin(self):
        """Test admin verification with admin@balizero.com"""
        from app.routers.team_activity import verify_admin

        assert verify_admin("admin@balizero.com") is True

    def test_verify_admin_case_insensitive(self):
        """Test admin verification is case-insensitive"""
        from app.routers.team_activity import verify_admin

        assert verify_admin("ZERO@BALIZERO.COM") is True
        assert verify_admin("Admin@Zantara.IO") is True

    def test_verify_admin_invalid_email(self):
        """Test admin verification with non-admin email"""
        from app.routers.team_activity import verify_admin

        assert verify_admin("user@example.com") is False
        assert verify_admin("notadmin@balizero.com") is False


class TestGetAdminEmail:
    """Tests for get_admin_email dependency"""

    @pytest.mark.asyncio
    async def test_get_admin_email_valid_x_user_email(self):
        """Test admin email extraction from X-User-Email header"""
        from app.routers.team_activity import get_admin_email

        email = await get_admin_email(x_user_email="zero@balizero.com")
        assert email == "zero@balizero.com"

    @pytest.mark.asyncio
    async def test_get_admin_email_case_insensitive(self):
        """Test admin email extraction with uppercase"""
        from app.routers.team_activity import get_admin_email

        email = await get_admin_email(x_user_email="ADMIN@ZANTARA.IO")
        assert email == "admin@zantara.io"

    @pytest.mark.asyncio
    async def test_get_admin_email_forbidden_non_admin(self):
        """Test admin email with non-admin user"""
        from fastapi import HTTPException

        from app.routers.team_activity import get_admin_email

        with pytest.raises(HTTPException) as exc_info:
            await get_admin_email(x_user_email="user@example.com")

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_admin_email_no_headers(self):
        """Test admin email with no authentication headers"""
        from fastapi import HTTPException

        from app.routers.team_activity import get_admin_email

        with pytest.raises(HTTPException) as exc_info:
            await get_admin_email(_authorization=None, x_user_email=None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================


@pytest.fixture
def mock_timesheet_service():
    """Create mock timesheet service"""
    service = AsyncMock()
    service.running = True
    return service


@pytest.fixture
def test_app():
    """Create FastAPI test app with router"""
    from app.routers.team_activity import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


# ============================================================================
# Clock-in Endpoint Tests
# ============================================================================


class TestClockInEndpoint:
    """Tests for /api/team/clock-in endpoint"""

    def test_clock_in_success(self, client, mock_timesheet_service):
        """Test successful clock-in"""
        # Mock service response
        mock_timesheet_service.clock_in.return_value = {
            "success": True,
            "action": "clock_in",
            "timestamp": "2025-12-23T09:00:00+08:00",
            "bali_time": "09:00",
            "message": "Successfully clocked in",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-in",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "clock_in"
        assert data["bali_time"] == "09:00"
        assert "Successfully clocked in" in data["message"]

        # Verify service was called correctly
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="user_123",
            email="test@example.com",
            metadata=None,
        )

    def test_clock_in_with_metadata(self, client, mock_timesheet_service):
        """Test clock-in with metadata"""
        mock_timesheet_service.clock_in.return_value = {
            "success": True,
            "action": "clock_in",
            "timestamp": "2025-12-23T09:00:00+08:00",
            "bali_time": "09:00",
            "message": "Successfully clocked in",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-in",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                    "metadata": {"ip_address": "192.168.1.1", "user_agent": "Chrome"},
                },
            )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="user_123",
            email="test@example.com",
            metadata={"ip_address": "192.168.1.1", "user_agent": "Chrome"},
        )

    def test_clock_in_already_clocked_in(self, client, mock_timesheet_service):
        """Test clock-in when already clocked in"""
        mock_timesheet_service.clock_in.return_value = {
            "success": False,
            "error": "already_clocked_in",
            "message": "Already clocked in at 08:30 Bali time",
            "clocked_in_at": "2025-12-23T08:30:00+08:00",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-in",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "already_clocked_in"
        assert "Already clocked in" in data["message"]

    def test_clock_in_service_unavailable(self, client):
        """Test clock-in when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.post(
                "/api/team/clock-in",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 503
        assert "Timesheet service unavailable" in response.json()["detail"]

    def test_clock_in_service_error(self, client, mock_timesheet_service):
        """Test clock-in when service raises exception"""
        mock_timesheet_service.clock_in.side_effect = Exception("Database connection failed")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-in",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]

    def test_clock_in_invalid_email(self, client):
        """Test clock-in with invalid email format"""
        response = client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user_123",
                "email": "invalid-email",
            },
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# Clock-out Endpoint Tests
# ============================================================================


class TestClockOutEndpoint:
    """Tests for /api/team/clock-out endpoint"""

    def test_clock_out_success(self, client, mock_timesheet_service):
        """Test successful clock-out"""
        mock_timesheet_service.clock_out.return_value = {
            "success": True,
            "action": "clock_out",
            "timestamp": "2025-12-23T17:30:00+08:00",
            "bali_time": "17:30",
            "clock_in_time": "2025-12-23T09:00:00+08:00",
            "hours_worked": 8.5,
            "message": "Successfully clocked out. Worked 8.5 hours",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-out",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "clock_out"
        assert data["hours_worked"] == 8.5
        assert "Successfully clocked out" in data["message"]

        mock_timesheet_service.clock_out.assert_called_once_with(
            user_id="user_123",
            email="test@example.com",
            metadata=None,
        )

    def test_clock_out_not_clocked_in(self, client, mock_timesheet_service):
        """Test clock-out when not clocked in"""
        mock_timesheet_service.clock_out.return_value = {
            "success": False,
            "error": "not_clocked_in",
            "message": "Not currently clocked in",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-out",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "not_clocked_in"

    def test_clock_out_service_unavailable(self, client):
        """Test clock-out when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.post(
                "/api/team/clock-out",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 503
        assert "Timesheet service unavailable" in response.json()["detail"]

    def test_clock_out_service_error(self, client, mock_timesheet_service):
        """Test clock-out when service raises exception"""
        mock_timesheet_service.clock_out.side_effect = Exception("Database error")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-out",
                json={
                    "user_id": "user_123",
                    "email": "test@example.com",
                },
            )

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


# ============================================================================
# My Status Endpoint Tests
# ============================================================================


class TestMyStatusEndpoint:
    """Tests for /api/team/my-status endpoint"""

    def test_get_my_status_success(self, client, mock_timesheet_service):
        """Test successful status retrieval"""
        mock_timesheet_service.get_my_status.return_value = {
            "user_id": "user_123",
            "is_online": True,
            "last_action": "2025-12-23T09:00:00+08:00",
            "last_action_type": "clock_in",
            "today_hours": 6.5,
            "week_hours": 32.0,
            "week_days": 4,
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/my-status?user_id=user_123")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_123"
        assert data["is_online"] is True
        assert data["today_hours"] == 6.5
        assert data["week_hours"] == 32.0
        assert data["week_days"] == 4

        mock_timesheet_service.get_my_status.assert_called_once_with("user_123")

    def test_get_my_status_offline(self, client, mock_timesheet_service):
        """Test status when user is offline"""
        mock_timesheet_service.get_my_status.return_value = {
            "user_id": "user_123",
            "is_online": False,
            "last_action": None,
            "last_action_type": None,
            "today_hours": 0.0,
            "week_hours": 0.0,
            "week_days": 0,
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/my-status?user_id=user_123")

        assert response.status_code == 200
        data = response.json()
        assert data["is_online"] is False
        assert data["today_hours"] == 0.0

    def test_get_my_status_missing_user_id(self, client):
        """Test status endpoint without user_id parameter"""
        response = client.get("/api/team/my-status")

        assert response.status_code == 422  # Validation error

    def test_get_my_status_service_unavailable(self, client):
        """Test status when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get("/api/team/my-status?user_id=user_123")

        assert response.status_code == 503

    def test_get_my_status_service_error(self, client, mock_timesheet_service):
        """Test status when service raises exception"""
        mock_timesheet_service.get_my_status.side_effect = Exception("Query failed")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/my-status?user_id=user_123")

        assert response.status_code == 500


# ============================================================================
# Team Status Endpoint Tests (Admin Only)
# ============================================================================


class TestTeamStatusEndpoint:
    """Tests for /api/team/status endpoint (admin only)"""

    def test_get_team_status_success(self, client, mock_timesheet_service):
        """Test successful team status retrieval"""
        mock_timesheet_service.get_team_online_status.return_value = [
            {
                "user_id": "user_1",
                "email": "user1@example.com",
                "is_online": True,
                "last_action": "2025-12-23T09:00:00+08:00",
                "last_action_type": "clock_in",
            },
            {
                "user_id": "user_2",
                "email": "user2@example.com",
                "is_online": False,
                "last_action": "2025-12-22T17:30:00+08:00",
                "last_action_type": "clock_out",
            },
        ]

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/status",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["user_id"] == "user_1"
        assert data[0]["is_online"] is True
        assert data[1]["is_online"] is False

    def test_get_team_status_forbidden_non_admin(self, client, mock_timesheet_service):
        """Test team status with non-admin user"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/status",
                headers={"X-User-Email": "user@example.com"},
            )

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    def test_get_team_status_no_auth(self, client, mock_timesheet_service):
        """Test team status without authentication"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/status")

        assert response.status_code == 401

    def test_get_team_status_service_unavailable(self, client):
        """Test team status when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get(
                "/api/team/status",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 503

    def test_get_team_status_service_error(self, client, mock_timesheet_service):
        """Test team status when service raises exception"""
        mock_timesheet_service.get_team_online_status.side_effect = Exception("Database error")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/status",
                headers={"X-User-Email": "admin@zantara.io"},
            )

        assert response.status_code == 500


# ============================================================================
# Daily Hours Endpoint Tests (Admin Only)
# ============================================================================


class TestDailyHoursEndpoint:
    """Tests for /api/team/hours endpoint (admin only)"""

    def test_get_daily_hours_success(self, client, mock_timesheet_service):
        """Test successful daily hours retrieval"""
        mock_timesheet_service.get_daily_hours.return_value = [
            {
                "user_id": "user_1",
                "email": "user1@example.com",
                "date": "2025-12-23",
                "clock_in": "09:00",
                "clock_out": "17:30",
                "hours_worked": 8.5,
            },
        ]

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/hours",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["hours_worked"] == 8.5
        assert data[0]["clock_in"] == "09:00"

    def test_get_daily_hours_specific_date(self, client, mock_timesheet_service):
        """Test daily hours for specific date"""
        mock_timesheet_service.get_daily_hours.return_value = []

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/hours?date=2025-12-20",
                headers={"X-User-Email": "admin@balizero.com"},
            )

        assert response.status_code == 200
        # Verify the service was called with a datetime object
        mock_timesheet_service.get_daily_hours.assert_called_once()
        call_args = mock_timesheet_service.get_daily_hours.call_args[0]
        assert call_args[0] is not None  # datetime object passed

    def test_get_daily_hours_invalid_date_format(self, client, mock_timesheet_service):
        """Test daily hours with invalid date format"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/hours?date=invalid-date",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_get_daily_hours_forbidden_non_admin(self, client, mock_timesheet_service):
        """Test daily hours with non-admin user"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/hours",
                headers={"X-User-Email": "user@example.com"},
            )

        assert response.status_code == 403

    def test_get_daily_hours_service_unavailable(self, client):
        """Test daily hours when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get(
                "/api/team/hours",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 503

    def test_get_daily_hours_service_error(self, client, mock_timesheet_service):
        """Test daily hours when service raises exception"""
        mock_timesheet_service.get_daily_hours.side_effect = Exception("Query error")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/hours",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 500


# ============================================================================
# Weekly Summary Endpoint Tests (Admin Only)
# ============================================================================


class TestWeeklySummaryEndpoint:
    """Tests for /api/team/activity/weekly endpoint (admin only)"""

    def test_get_weekly_summary_success(self, client, mock_timesheet_service):
        """Test successful weekly summary retrieval"""
        mock_timesheet_service.get_weekly_summary.return_value = [
            {
                "user_id": "user_1",
                "email": "user1@example.com",
                "week_start": "2025-12-16",
                "days_worked": 5,
                "total_hours": 42.5,
                "avg_hours_per_day": 8.5,
            },
        ]

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/weekly",
                headers={"X-User-Email": "admin@zantara.io"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["total_hours"] == 42.5
        assert data[0]["days_worked"] == 5

    def test_get_weekly_summary_specific_week(self, client, mock_timesheet_service):
        """Test weekly summary for specific week"""
        mock_timesheet_service.get_weekly_summary.return_value = []

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/weekly?week_start=2025-12-16",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 200
        mock_timesheet_service.get_weekly_summary.assert_called_once()

    def test_get_weekly_summary_invalid_date(self, client, mock_timesheet_service):
        """Test weekly summary with invalid date"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/weekly?week_start=bad-date",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_get_weekly_summary_forbidden(self, client, mock_timesheet_service):
        """Test weekly summary with non-admin"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/weekly",
                headers={"X-User-Email": "user@example.com"},
            )

        assert response.status_code == 403

    def test_get_weekly_summary_service_unavailable(self, client):
        """Test weekly summary when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get(
                "/api/team/activity/weekly",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 503

    def test_get_weekly_summary_service_error(self, client, mock_timesheet_service):
        """Test weekly summary service error"""
        mock_timesheet_service.get_weekly_summary.side_effect = Exception("DB error")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/weekly",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 500


# ============================================================================
# Monthly Summary Endpoint Tests (Admin Only)
# ============================================================================


class TestMonthlySummaryEndpoint:
    """Tests for /api/team/activity/monthly endpoint (admin only)"""

    def test_get_monthly_summary_success(self, client, mock_timesheet_service):
        """Test successful monthly summary retrieval"""
        mock_timesheet_service.get_monthly_summary.return_value = [
            {
                "user_id": "user_1",
                "email": "user1@example.com",
                "month_start": "2025-12-01",
                "days_worked": 20,
                "total_hours": 168.0,
                "avg_hours_per_day": 8.4,
            },
        ]

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/monthly",
                headers={"X-User-Email": "admin@zantara.io"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["total_hours"] == 168.0
        assert data[0]["days_worked"] == 20

    def test_get_monthly_summary_specific_month(self, client, mock_timesheet_service):
        """Test monthly summary for specific month"""
        mock_timesheet_service.get_monthly_summary.return_value = []

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/monthly?month_start=2025-11-01",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 200
        mock_timesheet_service.get_monthly_summary.assert_called_once()

    def test_get_monthly_summary_invalid_date(self, client, mock_timesheet_service):
        """Test monthly summary with invalid date"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/monthly?month_start=invalid",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_get_monthly_summary_forbidden(self, client, mock_timesheet_service):
        """Test monthly summary with non-admin"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/monthly",
                headers={"X-User-Email": "user@example.com"},
            )

        assert response.status_code == 403

    def test_get_monthly_summary_service_unavailable(self, client):
        """Test monthly summary when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get(
                "/api/team/activity/monthly",
                headers={"X-User-Email": "admin@balizero.com"},
            )

        assert response.status_code == 503

    def test_get_monthly_summary_service_error(self, client, mock_timesheet_service):
        """Test monthly summary service error"""
        mock_timesheet_service.get_monthly_summary.side_effect = Exception("Connection error")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/activity/monthly",
                headers={"X-User-Email": "admin@balizero.com"},
            )

        assert response.status_code == 500


# ============================================================================
# Export Timesheet Endpoint Tests (Admin Only)
# ============================================================================


class TestExportTimesheetEndpoint:
    """Tests for /api/team/export endpoint (admin only)"""

    def test_export_timesheet_success(self, client, mock_timesheet_service):
        """Test successful timesheet export"""
        csv_data = "Email,Date,Clock In,Clock Out,Hours Worked\nuser1@example.com,2025-12-23,09:00,17:30,8.5"
        mock_timesheet_service.export_timesheet_csv.return_value = csv_data

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-23",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "timesheet_2025-12-01_to_2025-12-23.csv" in response.headers["content-disposition"]
        assert "Email,Date,Clock In,Clock Out,Hours Worked" in response.text

    def test_export_timesheet_invalid_format(self, client, mock_timesheet_service):
        """Test export with invalid format"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-23&format=json",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 400
        assert "Only CSV format supported" in response.json()["detail"]

    def test_export_timesheet_invalid_start_date(self, client, mock_timesheet_service):
        """Test export with invalid start date"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=bad-date&end_date=2025-12-23",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_export_timesheet_invalid_end_date(self, client, mock_timesheet_service):
        """Test export with invalid end date"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=invalid",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_export_timesheet_missing_parameters(self, client, mock_timesheet_service):
        """Test export without required parameters"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 422  # Validation error

    def test_export_timesheet_forbidden(self, client, mock_timesheet_service):
        """Test export with non-admin user"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-23",
                headers={"X-User-Email": "user@example.com"},
            )

        assert response.status_code == 403

    def test_export_timesheet_service_unavailable(self, client):
        """Test export when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-23",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 503

    def test_export_timesheet_service_error(self, client, mock_timesheet_service):
        """Test export when service raises exception"""
        mock_timesheet_service.export_timesheet_csv.side_effect = Exception("Export failed")

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-23",
                headers={"X-User-Email": "admin@zantara.io"},
            )

        assert response.status_code == 500
        assert "Export failed" in response.json()["detail"]


# ============================================================================
# Health Check Endpoint Tests
# ============================================================================


class TestHealthCheckEndpoint:
    """Tests for /api/team/health endpoint"""

    def test_health_check_healthy(self, client, mock_timesheet_service):
        """Test health check when service is available"""
        mock_timesheet_service.running = True

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "team-activity"
        assert data["status"] == "healthy"
        assert data["auto_logout_enabled"] is True

    def test_health_check_unavailable(self, client):
        """Test health check when service is unavailable"""
        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service", return_value=None
        ):
            response = client.get("/api/team/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "team-activity"
        assert data["status"] == "unavailable"
        assert data["auto_logout_enabled"] is False

    def test_health_check_service_not_running(self, client, mock_timesheet_service):
        """Test health check when service exists but auto-logout not running"""
        mock_timesheet_service.running = False

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["auto_logout_enabled"] is False


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios"""

    def test_all_admin_emails_accepted(self, client, mock_timesheet_service):
        """Test that all admin emails work for admin endpoints"""
        mock_timesheet_service.get_team_online_status.return_value = []

        admin_emails = ["zero@balizero.com", "admin@zantara.io", "admin@balizero.com"]

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            for email in admin_emails:
                response = client.get(
                    "/api/team/status",
                    headers={"X-User-Email": email},
                )
                assert response.status_code == 200, f"Failed for {email}"

    def test_concurrent_clock_operations(self, client, mock_timesheet_service):
        """Test clock-in/out called multiple times"""
        mock_timesheet_service.clock_in.return_value = {
            "success": True,
            "action": "clock_in",
            "timestamp": "2025-12-23T09:00:00+08:00",
            "bali_time": "09:00",
            "message": "Successfully clocked in",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            for _ in range(3):
                response = client.post(
                    "/api/team/clock-in",
                    json={"user_id": "user_123", "email": "test@example.com"},
                )
                assert response.status_code == 200

    def test_empty_metadata(self, client, mock_timesheet_service):
        """Test clock-in with empty metadata dict"""
        mock_timesheet_service.clock_in.return_value = {
            "success": True,
            "action": "clock_in",
            "timestamp": "2025-12-23T09:00:00+08:00",
            "bali_time": "09:00",
            "message": "Successfully clocked in",
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.post(
                "/api/team/clock-in",
                json={"user_id": "user_123", "email": "test@example.com", "metadata": {}},
            )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="user_123",
            email="test@example.com",
            metadata={},
        )

    def test_export_with_default_csv_format(self, client, mock_timesheet_service):
        """Test export defaults to CSV format"""
        mock_timesheet_service.export_timesheet_csv.return_value = "CSV data"

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get(
                "/api/team/export?start_date=2025-12-01&end_date=2025-12-23&format=csv",
                headers={"X-User-Email": "zero@balizero.com"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

    def test_null_last_action_in_status(self, client, mock_timesheet_service):
        """Test status response with null last_action"""
        mock_timesheet_service.get_my_status.return_value = {
            "user_id": "user_123",
            "is_online": False,
            "last_action": None,
            "last_action_type": None,
            "today_hours": 0.0,
            "week_hours": 0.0,
            "week_days": 0,
        }

        with patch(
            "services.analytics.team_timesheet_service.get_timesheet_service",
            return_value=mock_timesheet_service,
        ):
            response = client.get("/api/team/my-status?user_id=user_123")

        assert response.status_code == 200
        data = response.json()
        assert data["last_action"] is None
        assert data["last_action_type"] is None

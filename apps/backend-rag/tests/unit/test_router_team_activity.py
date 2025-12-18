"""
Unit tests for Team Activity Router
90% coverage target with comprehensive endpoint testing
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_timesheet_service():
    """Mock timesheet service"""
    service = MagicMock()
    service.running = True

    # Clock in/out responses
    service.clock_in = AsyncMock(
        return_value={
            "success": True,
            "action": "clock_in",
            "timestamp": "2025-01-15T09:00:00Z",
            "bali_time": "2025-01-15 17:00:00",
            "message": "Clocked in successfully",
        }
    )

    service.clock_out = AsyncMock(
        return_value={
            "success": True,
            "action": "clock_out",
            "timestamp": "2025-01-15T17:00:00Z",
            "bali_time": "2025-01-16 01:00:00",
            "message": "Clocked out successfully",
            "hours_worked": 8.0,
        }
    )

    # Status responses
    service.get_my_status = AsyncMock(
        return_value={
            "user_id": "user123",
            "is_online": True,
            "last_action": "2025-01-15T09:00:00Z",
            "last_action_type": "clock_in",
            "today_hours": 4.5,
            "week_hours": 20.0,
            "week_days": 3,
        }
    )

    service.get_team_online_status = AsyncMock(
        return_value=[
            {
                "user_id": "user1",
                "email": "user1@test.com",
                "is_online": True,
                "last_action": "2025-01-15T09:00:00Z",
                "last_action_type": "clock_in",
            },
            {
                "user_id": "user2",
                "email": "user2@test.com",
                "is_online": False,
                "last_action": "2025-01-14T17:00:00Z",
                "last_action_type": "clock_out",
            },
        ]
    )

    service.get_daily_hours = AsyncMock(
        return_value=[
            {
                "user_id": "user1",
                "email": "user1@test.com",
                "date": "2025-01-15",
                "clock_in": "09:00:00",
                "clock_out": "17:00:00",
                "hours_worked": 8.0,
            }
        ]
    )

    service.get_weekly_summary = AsyncMock(
        return_value=[
            {
                "user_id": "user1",
                "email": "user1@test.com",
                "week_start": "2025-01-13",
                "days_worked": 5,
                "total_hours": 40.0,
                "avg_hours_per_day": 8.0,
            }
        ]
    )

    service.get_monthly_summary = AsyncMock(
        return_value=[
            {
                "user_id": "user1",
                "email": "user1@test.com",
                "month_start": "2025-01-01",
                "days_worked": 20,
                "total_hours": 160.0,
                "avg_hours_per_day": 8.0,
            }
        ]
    )

    service.export_timesheet_csv = AsyncMock(
        return_value="user_id,email,date,hours\nuser1,user1@test.com,2025-01-15,8.0"
    )

    return service


@pytest.fixture
def client():
    """Create test client"""
    from fastapi import FastAPI

    from app.routers.team_activity import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ============================================================================
# Test Admin Helpers
# ============================================================================


def test_verify_admin_valid():
    """Test admin verification with valid admin email"""
    from app.routers.team_activity import verify_admin

    assert verify_admin("zero@balizero.com") is True
    assert verify_admin("admin@zantara.io") is True
    assert verify_admin("admin@balizero.com") is True
    assert verify_admin("ZERO@BALIZERO.COM") is True  # Case insensitive


def test_verify_admin_invalid():
    """Test admin verification with non-admin email"""
    from app.routers.team_activity import verify_admin

    assert verify_admin("user@example.com") is False
    assert verify_admin("test@test.com") is False


@pytest.mark.asyncio
async def test_get_admin_email_with_valid_header():
    """Test getting admin email from X-User-Email header"""
    from app.routers.team_activity import get_admin_email

    admin_email = await get_admin_email(x_user_email="zero@balizero.com")
    assert admin_email == "zero@balizero.com"


@pytest.mark.asyncio
async def test_get_admin_email_non_admin():
    """Test getting admin email with non-admin user"""
    from app.routers.team_activity import get_admin_email

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_email(x_user_email="user@example.com")

    assert exc_info.value.status_code == 403
    assert "admin access required" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_get_admin_email_no_header():
    """Test getting admin email without header"""
    from app.routers.team_activity import get_admin_email

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_email(_authorization=None, x_user_email=None)

    assert exc_info.value.status_code == 401
    assert "authentication required" in exc_info.value.detail.lower()


# ============================================================================
# Test POST /api/team/clock-in
# ============================================================================


def test_clock_in_success(client, mock_timesheet_service):
    """Test successful clock in"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.post(
            "/api/team/clock-in", json={"user_id": "user123", "email": "test@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "clock_in"
        assert "timestamp" in data


def test_clock_in_with_metadata(client, mock_timesheet_service):
    """Test clock in with metadata"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.post(
            "/api/team/clock-in",
            json={
                "user_id": "user123",
                "email": "test@example.com",
                "metadata": {"location": "office", "device": "laptop"},
            },
        )

        assert response.status_code == 200


def test_clock_in_missing_user_id(client):
    """Test clock in without user_id"""
    response = client.post("/api/team/clock-in", json={"email": "test@example.com"})

    assert response.status_code == 422


def test_clock_in_missing_email(client):
    """Test clock in without email"""
    response = client.post("/api/team/clock-in", json={"user_id": "user123"})

    assert response.status_code == 422


def test_clock_in_invalid_email(client):
    """Test clock in with invalid email format"""
    response = client.post(
        "/api/team/clock-in", json={"user_id": "user123", "email": "not-an-email"}
    )

    assert response.status_code == 422


def test_clock_in_service_unavailable(client):
    """Test clock in when service is unavailable"""
    with patch("services.team_timesheet_service.get_timesheet_service", return_value=None):
        response = client.post(
            "/api/team/clock-in", json={"user_id": "user123", "email": "test@example.com"}
        )

        assert response.status_code == 503
        data = response.json()
        assert "timesheet service unavailable" in data["detail"].lower()


def test_clock_in_service_error(client, mock_timesheet_service):
    """Test clock in when service raises error"""
    mock_timesheet_service.clock_in.side_effect = Exception("Database error")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.post(
            "/api/team/clock-in", json={"user_id": "user123", "email": "test@example.com"}
        )

        assert response.status_code == 500


# ============================================================================
# Test POST /api/team/clock-out
# ============================================================================


def test_clock_out_success(client, mock_timesheet_service):
    """Test successful clock out"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.post(
            "/api/team/clock-out", json={"user_id": "user123", "email": "test@example.com"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "clock_out"
        assert "hours_worked" in data


def test_clock_out_with_metadata(client, mock_timesheet_service):
    """Test clock out with metadata"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.post(
            "/api/team/clock-out",
            json={
                "user_id": "user123",
                "email": "test@example.com",
                "metadata": {"location": "home"},
            },
        )

        assert response.status_code == 200


def test_clock_out_service_unavailable(client):
    """Test clock out when service unavailable"""
    with patch("services.team_timesheet_service.get_timesheet_service", return_value=None):
        response = client.post(
            "/api/team/clock-out", json={"user_id": "user123", "email": "test@example.com"}
        )

        assert response.status_code == 503


def test_clock_out_service_error(client, mock_timesheet_service):
    """Test clock out when service raises error"""
    mock_timesheet_service.clock_out.side_effect = Exception("Not clocked in")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.post(
            "/api/team/clock-out", json={"user_id": "user123", "email": "test@example.com"}
        )

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/my-status
# ============================================================================


def test_get_my_status_success(client, mock_timesheet_service):
    """Test getting user status successfully"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/my-status?user_id=user123")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"
        assert "is_online" in data
        assert "today_hours" in data


def test_get_my_status_missing_user_id(client):
    """Test getting status without user_id"""
    response = client.get("/api/team/my-status")

    assert response.status_code == 422


def test_get_my_status_service_unavailable(client):
    """Test getting status when service unavailable"""
    with patch("services.team_timesheet_service.get_timesheet_service", return_value=None):
        response = client.get("/api/team/my-status?user_id=user123")

        assert response.status_code == 503


def test_get_my_status_service_error(client, mock_timesheet_service):
    """Test getting status when service errors"""
    mock_timesheet_service.get_my_status.side_effect = Exception("User not found")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/my-status?user_id=user123")

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/status (Admin Only)
# ============================================================================


def test_get_team_status_success(client, mock_timesheet_service):
    """Test getting team status as admin"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/status", headers={"X-User-Email": "zero@balizero.com"})

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2


def test_get_team_status_non_admin(client):
    """Test getting team status as non-admin"""
    response = client.get("/api/team/status", headers={"X-User-Email": "user@example.com"})

    assert response.status_code == 403


def test_get_team_status_no_auth(client):
    """Test getting team status without authentication"""
    response = client.get("/api/team/status")

    assert response.status_code == 401


def test_get_team_status_service_unavailable(client):
    """Test getting team status when service unavailable"""
    with patch("services.team_timesheet_service.get_timesheet_service", return_value=None):
        response = client.get("/api/team/status", headers={"X-User-Email": "zero@balizero.com"})

        assert response.status_code == 503


def test_get_team_status_service_error(client, mock_timesheet_service):
    """Test getting team status when service errors"""
    mock_timesheet_service.get_team_online_status.side_effect = Exception("Database error")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/status", headers={"X-User-Email": "zero@balizero.com"})

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/hours (Admin Only)
# ============================================================================


def test_get_daily_hours_success(client, mock_timesheet_service):
    """Test getting daily hours as admin"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/hours?date=2025-01-15", headers={"X-User-Email": "admin@zantara.io"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


def test_get_daily_hours_default_date(client, mock_timesheet_service):
    """Test getting daily hours without date (uses today)"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/hours", headers={"X-User-Email": "admin@zantara.io"})

        assert response.status_code == 200


def test_get_daily_hours_invalid_date(client, mock_timesheet_service):
    """Test getting daily hours with invalid date format"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/hours?date=invalid-date", headers={"X-User-Email": "admin@zantara.io"}
        )

        assert response.status_code == 400


def test_get_daily_hours_non_admin(client):
    """Test getting daily hours as non-admin"""
    response = client.get("/api/team/hours", headers={"X-User-Email": "user@example.com"})

    assert response.status_code == 403


def test_get_daily_hours_service_error(client, mock_timesheet_service):
    """Test getting daily hours when service errors"""
    mock_timesheet_service.get_daily_hours.side_effect = Exception("Query failed")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/hours", headers={"X-User-Email": "admin@zantara.io"})

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/activity/weekly (Admin Only)
# ============================================================================


def test_get_weekly_summary_success(client, mock_timesheet_service):
    """Test getting weekly summary as admin"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/weekly?week_start=2025-01-13",
            headers={"X-User-Email": "admin@balizero.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


def test_get_weekly_summary_default_week(client, mock_timesheet_service):
    """Test getting weekly summary without week_start"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/weekly", headers={"X-User-Email": "admin@balizero.com"}
        )

        assert response.status_code == 200


def test_get_weekly_summary_invalid_date(client, mock_timesheet_service):
    """Test getting weekly summary with invalid date"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/weekly?week_start=bad-date",
            headers={"X-User-Email": "admin@balizero.com"},
        )

        assert response.status_code == 400


def test_get_weekly_summary_non_admin(client):
    """Test getting weekly summary as non-admin"""
    response = client.get("/api/team/activity/weekly", headers={"X-User-Email": "user@test.com"})
    assert response.status_code == 403


def test_get_weekly_summary_service_error(client, mock_timesheet_service):
    """Test getting weekly summary when service errors"""
    mock_timesheet_service.get_weekly_summary.side_effect = Exception("Error")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/weekly", headers={"X-User-Email": "admin@balizero.com"}
        )

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/activity/monthly (Admin Only)
# ============================================================================


def test_get_monthly_summary_success(client, mock_timesheet_service):
    """Test getting monthly summary as admin"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/monthly?month_start=2025-01-01",
            headers={"X-User-Email": "zero@balizero.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


def test_get_monthly_summary_default_month(client, mock_timesheet_service):
    """Test getting monthly summary without month_start"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/monthly", headers={"X-User-Email": "zero@balizero.com"}
        )

        assert response.status_code == 200


def test_get_monthly_summary_invalid_date(client, mock_timesheet_service):
    """Test getting monthly summary with invalid date"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/monthly?month_start=invalid",
            headers={"X-User-Email": "zero@balizero.com"},
        )

        assert response.status_code == 400


def test_get_monthly_summary_non_admin(client):
    """Test getting monthly summary as non-admin"""
    response = client.get("/api/team/activity/monthly", headers={"X-User-Email": "user@test.com"})
    assert response.status_code == 403


def test_get_monthly_summary_service_error(client, mock_timesheet_service):
    """Test getting monthly summary when service errors"""
    mock_timesheet_service.get_monthly_summary.side_effect = Exception("Error")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/activity/monthly", headers={"X-User-Email": "zero@balizero.com"}
        )

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/export (Admin Only)
# ============================================================================


def test_export_timesheet_success(client, mock_timesheet_service):
    """Test exporting timesheet as admin"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/export?start_date=2025-01-01&end_date=2025-01-31&format=csv",
            headers={"X-User-Email": "admin@zantara.io"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in response.headers


def test_export_timesheet_default_format(client, mock_timesheet_service):
    """Test exporting with default CSV format"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/export?start_date=2025-01-01&end_date=2025-01-31",
            headers={"X-User-Email": "admin@zantara.io"},
        )

        assert response.status_code == 200


def test_export_timesheet_invalid_format(client, mock_timesheet_service):
    """Test exporting with invalid format"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/export?start_date=2025-01-01&end_date=2025-01-31&format=pdf",
            headers={"X-User-Email": "admin@zantara.io"},
        )

        assert response.status_code == 400
        assert "only csv format supported" in response.json()["detail"].lower()


def test_export_timesheet_missing_start_date(client):
    """Test exporting without start_date"""
    response = client.get(
        "/api/team/export?end_date=2025-01-31", headers={"X-User-Email": "admin@zantara.io"}
    )

    assert response.status_code == 422


def test_export_timesheet_missing_end_date(client):
    """Test exporting without end_date"""
    response = client.get(
        "/api/team/export?start_date=2025-01-01", headers={"X-User-Email": "admin@zantara.io"}
    )

    assert response.status_code == 422


def test_export_timesheet_invalid_date_format(client, mock_timesheet_service):
    """Test exporting with invalid date format"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/export?start_date=bad-date&end_date=2025-01-31",
            headers={"X-User-Email": "admin@zantara.io"},
        )

        assert response.status_code == 400


def test_export_timesheet_non_admin(client):
    """Test exporting as non-admin"""
    response = client.get(
        "/api/team/export?start_date=2025-01-01&end_date=2025-01-31",
        headers={"X-User-Email": "user@test.com"},
    )

    assert response.status_code == 403


def test_export_timesheet_service_unavailable(client):
    """Test exporting when service unavailable"""
    with patch("services.team_timesheet_service.get_timesheet_service", return_value=None):
        response = client.get(
            "/api/team/export?start_date=2025-01-01&end_date=2025-01-31",
            headers={"X-User-Email": "admin@zantara.io"},
        )

        assert response.status_code == 503


def test_export_timesheet_service_error(client, mock_timesheet_service):
    """Test exporting when service errors"""
    mock_timesheet_service.export_timesheet_csv.side_effect = Exception("Export failed")

    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get(
            "/api/team/export?start_date=2025-01-01&end_date=2025-01-31",
            headers={"X-User-Email": "admin@zantara.io"},
        )

        assert response.status_code == 500


# ============================================================================
# Test GET /api/team/health
# ============================================================================


def test_health_check_service_available(client, mock_timesheet_service):
    """Test health check when service is available"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        response = client.get("/api/team/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "team-activity"
        assert data["status"] == "healthy"
        assert data["auto_logout_enabled"] is True


def test_health_check_service_unavailable(client):
    """Test health check when service is unavailable"""
    with patch("services.team_timesheet_service.get_timesheet_service", return_value=None):
        response = client.get("/api/team/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["auto_logout_enabled"] is False


def test_health_check_no_auth_required(client, mock_timesheet_service):
    """Test health check doesn't require authentication"""
    with patch(
        "services.team_timesheet_service.get_timesheet_service", return_value=mock_timesheet_service
    ):
        # Should work without any headers
        response = client.get("/api/team/health")

        assert response.status_code == 200

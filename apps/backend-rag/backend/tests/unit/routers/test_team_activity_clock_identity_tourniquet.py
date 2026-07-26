"""
CI-collected identity-gate tests for backend/app/routers/team_activity.py
clock-in / clock-out / my-status (TOURNIQUET, 2026-07-21).

Why this file exists (and isn't just an addition to the pre-existing
tests/unit/routers/test_team_activity_router.py): that file lives under
apps/backend-rag/tests/ — a top-level tree neither GitHub Actions
(.github/workflows/tests.yml runs `pytest backend/tests/`) nor the local
pre-push hook (.husky/pre-push, same `backend/tests/` scope) ever collects
(pytest.ini `testpaths = backend/tests` confirms the same for a bare
`pytest`). Discovered live during this tourniquet's round-1 review — see
memory `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
Putting the actual security-gate tests here means CI genuinely verifies
the gate instead of a suite that only ever runs by accident.

Covers 3 endpoints + `_resolve_actor_identity`:
    * POST /api/team/clock-in
    * POST /api/team/clock-out
    * GET  /api/team/my-status

Round 1 (email-only comparison, 403 on mismatch) was HAS-HOLE per Codex
red-team on the real diff: `team_timesheet_service` keys every row on
`user_id`, which round 1 left unverified — a non-admin could send their
own (token-matching) email with a VICTIM's user_id and clock the victim
in/out under their own attendance record. Round 2 (this file) closes it by
having `_resolve_actor_identity` IGNORE the caller-supplied identity
outright for non-admins (never validate-then-trust) and use the
authenticated principal's own (user_id, email) instead.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_timesheet_service():
    service = AsyncMock()
    service.running = True
    return service


@pytest.fixture
def mock_user_data():
    """Default caller is a non-admin team member — the class this
    tourniquet protects. Admin behavior is exercised explicitly per-test."""
    return {"email": "damar@balizero.com", "role": "team", "user_id": "damar_uuid"}


@pytest.fixture
def test_app(mock_timesheet_service, mock_user_data):
    from backend.app.routers.team_activity import router

    app = FastAPI()
    app.include_router(router)

    from backend.app.dependencies import get_current_user

    def override_get_current_user(request=None):
        if not hasattr(app.state, "current_user") or app.state.current_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return app.state.current_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.state.current_user = mock_user_data

    with patch(
        "backend.services.analytics.team_timesheet_service.get_timesheet_service",
        return_value=mock_timesheet_service,
    ):
        yield app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def _ok_clock_response() -> dict:
    return {
        "success": True,
        "action": "clock_in",
        "timestamp": "2026-07-21T09:00:00+08:00",
        "bali_time": "09:00",
        "message": "Successfully clocked in",
    }


# ============================================================================
# clock-in / clock-out — no session at all
# ============================================================================


class TestClockNoAuth:
    def test_clock_in_no_auth_rejected(self, client, test_app):
        test_app.state.current_user = None
        response = client.post(
            "/api/team/clock-in",
            json={"user_id": "user_123", "email": "test@example.com"},
        )
        assert response.status_code == 401

    def test_clock_out_no_auth_rejected(self, client, test_app):
        test_app.state.current_user = None
        response = client.post(
            "/api/team/clock-out",
            json={"user_id": "user_123", "email": "test@example.com"},
        )
        assert response.status_code == 401

    def test_my_status_no_auth_rejected(self, client, test_app):
        test_app.state.current_user = None
        response = client.get("/api/team/my-status?user_id=user_123")
        assert response.status_code == 401


# ============================================================================
# clock-in / clock-out — identity resolution (the round-2 fix)
# ============================================================================


class TestClockIdentityResolution:
    """GUILT: a non-admin's caller-supplied identity (user_id AND/OR email)
    must never reach the timesheet service — only the authenticated
    principal's own identity does, regardless of what the body claims."""

    def test_clock_in_user_id_impersonation_uses_own_identity(
        self, client, mock_timesheet_service
    ):
        """The exact round-2 hole: matching email + a VICTIM's user_id.

        Round 1 would have let this through (email matched). The service
        must be called with the PRINCIPAL's own user_id, never the body's.
        """
        mock_timesheet_service.clock_in.return_value = _ok_clock_response()

        response = client.post(
            "/api/team/clock-in",
            json={"user_id": "victim_uuid", "email": "damar@balizero.com"},
        )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="damar_uuid",  # own principal id, NOT "victim_uuid"
            email="damar@balizero.com",
            metadata=None,
        )

    def test_clock_in_email_impersonation_uses_own_identity(
        self, client, mock_timesheet_service
    ):
        """Mirror case: own user_id, a victim's email — still overridden."""
        mock_timesheet_service.clock_in.return_value = _ok_clock_response()

        response = client.post(
            "/api/team/clock-in",
            json={"user_id": "damar_uuid", "email": "victim@balizero.com"},
        )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="damar_uuid",
            email="damar@balizero.com",  # own principal email, NOT the victim's
            metadata=None,
        )

    def test_clock_in_full_impersonation_attempt_uses_own_identity(
        self, client, mock_timesheet_service
    ):
        """Both fields spoofed to a victim — still resolves to the principal."""
        mock_timesheet_service.clock_in.return_value = _ok_clock_response()

        response = client.post(
            "/api/team/clock-in",
            json={"user_id": "victim_uuid", "email": "victim@balizero.com"},
        )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="damar_uuid",
            email="damar@balizero.com",
            metadata=None,
        )

    def test_clock_out_user_id_impersonation_uses_own_identity(
        self, client, mock_timesheet_service
    ):
        """Same class of attack on clock-out."""
        mock_timesheet_service.clock_out.return_value = {
            "success": True,
            "action": "clock_out",
            "timestamp": "2026-07-21T17:00:00+08:00",
            "bali_time": "17:00",
            "hours_worked": 8.0,
            "message": "Successfully clocked out",
        }

        response = client.post(
            "/api/team/clock-out",
            json={"user_id": "victim_uuid", "email": "damar@balizero.com"},
        )

        assert response.status_code == 200
        mock_timesheet_service.clock_out.assert_called_once_with(
            user_id="damar_uuid",
            email="damar@balizero.com",
            metadata=None,
        )

    # ── INNOCENCE: self clock-in keeps working unchanged ─────────────────

    def test_clock_in_self_matches_own_identity(self, client, mock_timesheet_service):
        """The common case: caller sends their own (matching) identity."""
        mock_timesheet_service.clock_in.return_value = _ok_clock_response()

        response = client.post(
            "/api/team/clock-in",
            json={"user_id": "damar_uuid", "email": "damar@balizero.com"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="damar_uuid",
            email="damar@balizero.com",
            metadata=None,
        )

    def test_clock_in_metadata_still_forwarded(self, client, mock_timesheet_service):
        """Non-identity fields (metadata) are untouched by the resolver."""
        mock_timesheet_service.clock_in.return_value = _ok_clock_response()

        response = client.post(
            "/api/team/clock-in",
            json={
                "user_id": "damar_uuid",
                "email": "damar@balizero.com",
                "metadata": {"ip_address": "10.0.0.1"},
            },
        )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="damar_uuid",
            email="damar@balizero.com",
            metadata={"ip_address": "10.0.0.1"},
        )

    # ── INNOCENCE: admin keeps acting on behalf of others ─────────────────

    def test_clock_in_admin_on_behalf_of_other_still_honored(
        self, client, test_app, mock_timesheet_service
    ):
        """Existing `is_crm_admin` precedent must not regress."""
        test_app.state.current_user = {"email": "zero@balizero.com", "role": "admin"}
        mock_timesheet_service.clock_in.return_value = _ok_clock_response()

        response = client.post(
            "/api/team/clock-in",
            json={"user_id": "someone_else_id", "email": "someone_else@balizero.com"},
        )

        assert response.status_code == 200
        mock_timesheet_service.clock_in.assert_called_once_with(
            user_id="someone_else_id",
            email="someone_else@balizero.com",
            metadata=None,
        )


# ============================================================================
# my-status — same identity class (get_my_status sibling)
# ============================================================================


class TestMyStatusIdentityResolution:
    def test_my_status_enumeration_returns_own_status_not_requested(
        self, client, mock_timesheet_service
    ):
        """GUILT: a non-admin querying someone else's user_id must get THEIR
        OWN status back — the service must be called with the principal's
        id, never the query param's."""
        mock_timesheet_service.get_my_status.return_value = {
            "user_id": "damar_uuid",
            "is_online": True,
            "last_action": "2026-07-21T09:00:00+08:00",
            "last_action_type": "clock_in",
            "today_hours": 1.0,
            "week_hours": 1.0,
            "week_days": 1,
        }

        response = client.get("/api/team/my-status?user_id=victim_uuid")

        assert response.status_code == 200
        mock_timesheet_service.get_my_status.assert_called_once_with("damar_uuid")

    def test_my_status_self_matches_own_identity(self, client, mock_timesheet_service):
        """INNOCENCE: the common case — caller queries their own status."""
        mock_timesheet_service.get_my_status.return_value = {
            "user_id": "damar_uuid",
            "is_online": False,
            "last_action": None,
            "last_action_type": None,
            "today_hours": 0.0,
            "week_hours": 0.0,
            "week_days": 0,
        }

        response = client.get("/api/team/my-status?user_id=damar_uuid")

        assert response.status_code == 200
        mock_timesheet_service.get_my_status.assert_called_once_with("damar_uuid")

    def test_my_status_admin_can_query_anyone(self, client, test_app, mock_timesheet_service):
        """INNOCENCE: admin keeps the ability to look up any member's status."""
        test_app.state.current_user = {"email": "zero@balizero.com", "role": "admin"}
        mock_timesheet_service.get_my_status.return_value = {
            "user_id": "someone_else_id",
            "is_online": True,
            "last_action": "2026-07-21T09:00:00+08:00",
            "last_action_type": "clock_in",
            "today_hours": 2.0,
            "week_hours": 10.0,
            "week_days": 3,
        }

        response = client.get("/api/team/my-status?user_id=someone_else_id")

        assert response.status_code == 200
        mock_timesheet_service.get_my_status.assert_called_once_with("someone_else_id")

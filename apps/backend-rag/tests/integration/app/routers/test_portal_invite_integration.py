"""Current-contract tests for portal invitation and registration routes.

All service and email effects are synthetic dependency overrides. The email
adapter is replaced before any request, so the tests cannot send externally.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers import portal_invite as invite_router

TEAM_USER = {
    "email": "qa.team@example.test",
    "user_id": "qa-team-user",
    "name": "QA Team",
    "role": "team",
    "permissions": [],
}


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    invite_service = AsyncMock()
    db_pool = MagicMock(name="synthetic_db_pool")
    email_sink = AsyncMock(name="portal_invite_email_sink")

    monkeypatch.setattr(invite_router, "send_portal_invite_email", email_sink)
    monkeypatch.setattr(
        invite_router.settings,
        "frontend_portal_url",
        "https://portal.example.test",
    )

    app = FastAPI()
    app.include_router(invite_router.router)
    app.dependency_overrides[get_current_user] = lambda: TEAM_USER
    app.dependency_overrides[get_database_pool] = lambda: db_pool
    app.dependency_overrides[invite_router.get_invite_service] = lambda: invite_service

    with TestClient(app) as client:
        yield SimpleNamespace(
            app=app,
            client=client,
            db_pool=db_pool,
            email_sink=email_sink,
            invite_service=invite_service,
        )

    app.dependency_overrides.clear()


@pytest.mark.integration
class TestPortalInviteContracts:
    def test_send_invitation_uses_current_endpoint_and_email_sink(
        self,
        harness: SimpleNamespace,
    ) -> None:
        harness.invite_service.create_invitation.return_value = {
            "client_id": 42,
            "client_name": "Synthetic Client",
            "email": "synthetic.client@example.com",
            "invite_url": "/portal/invite/synthetic-token",
        }

        response = harness.client.post(
            "/api/portal/invite/send",
            json={"client_id": 42, "email": "synthetic.client@example.com"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["email_sent"] is True
        assert response.json()["email_error"] is None
        assert response.json()["data"]["full_invite_url"] == (
            "https://portal.example.test/portal/invite/synthetic-token"
        )
        harness.invite_service.create_invitation.assert_awaited_once_with(
            client_id=42,
            email="synthetic.client@example.com",
            created_by=TEAM_USER["email"],
        )
        harness.email_sink.assert_awaited_once_with(
            to="synthetic.client@example.com",
            client_name="Synthetic Client",
            invite_url="https://portal.example.test/portal/invite/synthetic-token",
            db_pool=harness.db_pool,
            client_id=42,
        )

    def test_get_client_invitation_history_uses_current_endpoint(
        self,
        harness: SimpleNamespace,
    ) -> None:
        harness.invite_service.get_client_invitations.return_value = [
            {"id": 7, "status": "pending"},
        ]

        response = harness.client.get("/api/portal/invite/client/42")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "data": [{"id": 7, "status": "pending"}],
        }
        harness.invite_service.get_client_invitations.assert_awaited_once_with(42)
        harness.email_sink.assert_not_awaited()

    def test_validate_invalid_token_returns_public_contract(
        self,
        harness: SimpleNamespace,
    ) -> None:
        harness.invite_service.validate_token.return_value = None

        response = harness.client.get("/api/portal/invite/validate/synthetic-invalid-token")

        assert response.status_code == 200
        assert response.json() == {
            "valid": False,
            "error": "invalid_token",
            "message": "This invitation link is invalid",
            "client_name": None,
            "email": None,
            "invitation_id": None,
            "client_id": None,
        }
        harness.invite_service.validate_token.assert_awaited_once_with(
            "synthetic-invalid-token",
        )
        harness.email_sink.assert_not_awaited()

    def test_complete_registration_rejects_invalid_token(
        self,
        harness: SimpleNamespace,
    ) -> None:
        harness.invite_service.complete_registration.side_effect = ValueError(
            "Invalid or expired invitation token",
        )

        response = harness.client.post(
            "/api/portal/invite/complete",
            json={"token": "synthetic-invalid-token", "pin": "654321"},
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid or expired invitation token"}
        harness.invite_service.complete_registration.assert_awaited_once_with(
            token="synthetic-invalid-token",
            pin="654321",
        )
        harness.email_sink.assert_not_awaited()

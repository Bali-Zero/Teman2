"""Contract tests for the team-side CRM portal integration router.

The router is exercised through FastAPI with synthetic dependency overrides. No
production database, account, or outbound transport is reachable from this file.
"""

import os
import sys
from datetime import datetime, timezone
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
from backend.app.deps.crm_access import get_crm_user_filter
from backend.app.routers import crm_portal_integration as crm_router

TEAM_USER = {
    "email": "qa.team@example.test",
    "user_id": "qa-team-user",
    "name": "QA Team",
    "role": "team",
    "permissions": [],
}


class _Acquire:
    def __init__(self, connection: AsyncMock) -> None:
        self._connection = connection

    async def __aenter__(self) -> AsyncMock:
        return self._connection

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.fixture
def harness() -> SimpleNamespace:
    """Build an isolated router harness with explicit auth, DB and services."""
    connection = AsyncMock()
    db_pool = MagicMock()
    db_pool.acquire.side_effect = lambda: _Acquire(connection)
    invite_service = AsyncMock()
    portal_service = AsyncMock()

    app = FastAPI()
    app.include_router(crm_router.router)
    app.dependency_overrides[get_current_user] = lambda: TEAM_USER
    app.dependency_overrides[get_database_pool] = lambda: db_pool
    app.dependency_overrides[crm_router.get_invite_service] = lambda: invite_service
    app.dependency_overrides[crm_router.get_portal_service] = lambda: portal_service
    app.dependency_overrides[get_crm_user_filter] = lambda: None

    with TestClient(app) as client:
        yield SimpleNamespace(
            app=app,
            client=client,
            connection=connection,
            db_pool=db_pool,
            invite_service=invite_service,
            portal_service=portal_service,
        )

    app.dependency_overrides.clear()


@pytest.fixture
def allow_client_access(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    access_check = AsyncMock()
    monkeypatch.setattr(crm_router, "verify_client_access", access_check)
    return access_check


@pytest.mark.integration
class TestCRMPortalIntegrationContracts:
    def test_get_portal_status_without_access(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        harness.connection.fetchrow.side_effect = [None, None]

        response = harness.client.get("/api/crm/portal/clients/42/status")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "data": {
                "has_portal_access": False,
                "portal_user_id": None,
                "portal_email": None,
                "last_login": None,
                "pending_invite": False,
                "invite_expires_at": None,
            },
        }
        allow_client_access.assert_awaited_once_with(
            42,
            TEAM_USER,
            harness.connection,
            allow_assigned=True,
        )

    def test_send_portal_invite_uses_current_route_and_service_contract(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        harness.invite_service.create_invitation.return_value = {
            "client_id": 42,
            "invite_url": "/portal/invite/synthetic-token",
            "client_name": "Synthetic Client",
        }

        response = harness.client.post(
            "/api/crm/portal/clients/42/invite",
            json={"email": "synthetic.client@example.com"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["message"] == "Invitation sent to synthetic.client@example.com"
        harness.invite_service.create_invitation.assert_awaited_once_with(
            client_id=42,
            email="synthetic.client@example.com",
            created_by=TEAM_USER["email"],
        )
        allow_client_access.assert_awaited_once()

    def test_get_unread_messages_count_returns_typed_payload(
        self,
        harness: SimpleNamespace,
    ) -> None:
        harness.connection.fetchval.return_value = 3
        harness.connection.fetch.return_value = [
            {"client_id": 42, "client_name": "Synthetic Client", "unread_count": 3},
        ]

        response = harness.client.get("/api/crm/portal/messages/unread-count")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "data": {
                "total_unread": 3,
                "by_client": [
                    {
                        "client_id": 42,
                        "client_name": "Synthetic Client",
                        "unread_count": 3,
                    },
                ],
            },
        }

    def test_get_client_messages_forwards_pagination_and_impersonation_context(
        self,
        harness: SimpleNamespace,
        allow_client_access: AsyncMock,
    ) -> None:
        harness.portal_service.get_messages.return_value = {"messages": [], "total": 0}

        response = harness.client.get(
            "/api/crm/portal/clients/42/messages?limit=25&offset=5",
        )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "data": {"messages": [], "total": 0},
        }
        call = harness.portal_service.get_messages.await_args
        assert call.args == (42,)
        assert call.kwargs["limit"] == 25
        assert call.kwargs["offset"] == 5
        assert call.kwargs["current_user"]["client_id"] == 42
        assert call.kwargs["current_user"]["impersonating"] is True
        assert call.kwargs["current_user"]["email"] == TEAM_USER["email"]
        allow_client_access.assert_awaited_once()

    def test_get_recent_activity_uses_current_route_and_serializes_timestamp(
        self,
        harness: SimpleNamespace,
    ) -> None:
        created_at = datetime(2026, 8, 6, 9, 30, tzinfo=timezone.utc)
        harness.connection.fetch.return_value = [
            {
                "id": 7,
                "activity_type": "message",
                "client_id": 42,
                "client_name": "Synthetic Client",
                "subject": "Synthetic subject",
                "preview": "Synthetic body",
                "created_at": created_at,
            },
        ]

        response = harness.client.get("/api/crm/portal/activity/recent?limit=5")

        assert response.status_code == 200
        assert response.json()["data"]["activities"] == [
            {
                "id": 7,
                "type": "message",
                "client_id": 42,
                "client_name": "Synthetic Client",
                "subject": "Synthetic subject",
                "preview": "Synthetic body",
                "timestamp": created_at.isoformat(),
            },
        ]
        fetch_args = harness.connection.fetch.await_args
        assert fetch_args.args[1:] == (5,)

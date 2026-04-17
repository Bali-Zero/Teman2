"""Tests for the CRM practices router."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.crm_practices as crm_practices_module
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.crm.practice_state_machine import InvalidTransitionError


def _ts() -> datetime:
    return datetime.now(timezone.utc)


def _practice_row(**overrides: object) -> dict[str, object]:
    return {
        "id": 10,
        "uuid": "22222222-2222-2222-2222-222222222222",
        "client_id": 1,
        "practice_type_id": 5,
        "status": "inquiry",
        "priority": "normal",
        "quoted_price": Decimal("1000000"),
        "actual_price": None,
        "payment_status": "pending",
        "assigned_to": "test@balizero.com",
        "start_date": None,
        "completion_date": None,
        "expiry_date": date(2030, 1, 1),
        "created_at": _ts(),
        "created_by": "test@balizero.com",
        "client_visible": True,
        "client_summary": "Summary",
        **overrides,
    }


async def _noop_async(*_args: object, **_kwargs: object) -> None:
    return None


@pytest.fixture
def fake_user() -> dict[str, str]:
    return {"id": "1", "email": "test@balizero.com", "role": "admin"}


@pytest.fixture
def app(mock_db_pool, fake_user: dict[str, str]) -> FastAPI:
    pool, _conn = mock_db_pool
    application = FastAPI()
    application.include_router(crm_practices_module.router)
    application.dependency_overrides[get_current_user] = lambda: fake_user
    application.dependency_overrides[get_database_pool] = lambda: pool
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert crm_practices_module.router.prefix == "/api/crm/practices"
        assert crm_practices_module.router.tags == ["crm-practices"]

    @pytest.mark.unit
    def test_practice_create_model_validation(self) -> None:
        payload = crm_practices_module.PracticeCreate.model_validate(
            {"client_id": 1, "practice_type_code": "kitas_investor"},
        )
        assert payload.client_id == 1


class TestCreatePractice:
    @pytest.mark.integration
    def test_create_practice_success(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": 5, "base_price": Decimal("1000000"), "category": "visa", "name": "Investor KITAS"},
                _practice_row(),
            ],
        )
        conn.execute = AsyncMock(return_value="OK")

        with (
            patch("backend.app.routers.crm_practices.invalidate_cache", AsyncMock()),
            patch("backend.services.crm.welcome.welcome_practice_service.send_practice_kickoff", new=_noop_async),
        ):
            response = client.post(
                "/api/crm/practices/",
                json={"client_id": 1, "practice_type_code": "kitas_investor", "assigned_to": "test@balizero.com"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 10
        assert body["status"] == "inquiry"


class TestListPractices:
    @pytest.mark.integration
    def test_list_practices_returns_rows(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[{
            **_practice_row(),
            "client_name": "Alice Example",
            "client_email": "alice@example.com",
            "client_phone": "+628123456789",
            "client_lead": "test@balizero.com",
            "practice_type_name": "Investor KITAS",
            "practice_type_code": "kitas_investor",
            "practice_category": "visa",
        }])

        with patch("backend.app.routers.crm_practices.get_practices_user_filter", return_value=None):
            response = client.get("/api/crm/practices/")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["practice_type_code"] == "kitas_investor"


class TestGetPractice:
    @pytest.mark.integration
    def test_get_practice_by_id_success(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={
            **_practice_row(),
            "client_name": "Alice Example",
            "client_email": "alice@example.com",
            "client_phone": "+628123456789",
            "client_lead": "test@balizero.com",
            "practice_type_name": "Investor KITAS",
            "practice_type_code": "kitas_investor",
            "practice_category": "visa",
            "required_documents": [],
        })

        with patch("backend.app.routers.crm_practices.get_practices_user_filter", return_value=None):
            response = client.get("/api/crm/practices/10")

        assert response.status_code == 200
        assert response.json()["id"] == 10


class TestUpdatePractice:
    @pytest.mark.integration
    def test_update_practice_status_valid_transition(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"status": "inquiry", "client_id": 1, "client_visible": True, "created_by": "test@balizero.com", "assigned_to": "test@balizero.com"},
                _practice_row(status="on_process"),
                {"code": "kitas_investor"},
            ],
        )
        conn.execute = AsyncMock(return_value="OK")

        notification_service = MagicMock()
        notification_service.notify_practice_status_changed = AsyncMock()

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch("backend.app.routers.crm_practices.validate_transition", return_value=None),
            patch("backend.app.routers.crm_practices.invalidate_cache", AsyncMock()),
            patch("backend.services.portal.portal_notification_service.PortalNotificationService", return_value=notification_service),
            patch("backend.app.routers.crm_practices.spawn", MagicMock()),
        ):
            response = client.patch("/api/crm/practices/10", json={"status": "on_process"})

        assert response.status_code == 200
        assert response.json()["status"] == "on_process"

    @pytest.mark.integration
    def test_update_practice_status_invalid_transition_returns_400(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "status": "inquiry",
                "client_id": 1,
                "client_visible": True,
                "created_by": "test@balizero.com",
                "assigned_to": "test@balizero.com",
            },
        )

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch(
                "backend.app.routers.crm_practices.validate_transition",
                side_effect=InvalidTransitionError("inquiry", "completed"),
            ),
        ):
            response = client.patch("/api/crm/practices/10", json={"status": "completed"})

        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]

    @pytest.mark.integration
    def test_update_practice_returns_404_when_row_missing(
        self,
        client: TestClient,
        mock_db_pool,
    ) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"status": "inquiry", "client_id": 1, "client_visible": True, "created_by": "test@balizero.com", "assigned_to": "test@balizero.com"},
                None,
            ],
        )

        with (
            patch("backend.app.routers.crm_practices.is_crm_admin", return_value=True),
            patch("backend.app.routers.crm_practices.validate_transition", return_value=None),
        ):
            response = client.patch("/api/crm/practices/10", json={"status": "on_process"})

        assert response.status_code == 404

"""Tests for the E33 Second Home internal console router (F4a case entrance)."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.e33_cases as e33_cases_module
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.crm.e33_case_repository import E33CaseRepository
from backend.services.crm.e33_guarantee_scanner import ScanSwitchState
from backend.services.crm.e33_lifecycle import E33Case, E33Stage, GuaranteeBasis

CASE_ID_RE = re.compile(r"^E33-\d{4}-[0-9a-f]{6}$")


def _make_app(pool, user: dict[str, object]) -> FastAPI:
    application = FastAPI()
    application.include_router(e33_cases_module.router)
    application.dependency_overrides[get_current_user] = lambda: user
    application.dependency_overrides[get_database_pool] = lambda: pool
    return application


@pytest.fixture
def admin_user() -> dict[str, str]:
    return {"id": "1", "email": "admin@balizero.com", "role": "admin"}


@pytest.fixture
def team_user() -> dict[str, str]:
    return {"id": "2", "email": "team@balizero.com", "role": "team_member"}


@pytest.fixture
def client_user() -> dict[str, str]:
    return {"id": "3", "email": "client@example.com", "role": "client"}


def _existing_case(
    *,
    case_id: str = "E33-2026-abc123",
    stage: E33Stage = E33Stage.FIT_MEMO,
    client_id: int = 1,
) -> E33Case:
    return E33Case(case_id=case_id, client_id=client_id, basis=GuaranteeBasis.DEPOSIT, stage=stage)


class TestCreateCase:
    @pytest.mark.integration
    def test_create_case_success_mints_case_id_and_starts_at_fit_memo(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)
        conn.fetchval = AsyncMock(return_value="Alice Example")

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["stage"] == "fit_memo"
        assert CASE_ID_RE.match(body["case_id"]), body["case_id"]
        assert body["stage_history"] == []
        fake_repo.insert.assert_awaited_once()

    @pytest.mark.integration
    def test_dependent_without_principal_case_id_returns_422(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, _conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        response = client.post(
            "/api/e33/cases",
            json={"client_id": 1, "basis": "deposit", "dependent_code": "E31B"},
        )

        assert response.status_code == 422

    @pytest.mark.integration
    def test_unknown_dependent_code_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, _conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        response = client.post(
            "/api/e33/cases",
            json={
                "client_id": 1,
                "basis": "deposit",
                "dependent_code": "NOT_A_CODE",
                "principal_case_id": "E33-2026-abc123",
            },
        )

        assert response.status_code == 422

    @pytest.mark.integration
    def test_fk_violation_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, _conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(
            side_effect=asyncpg.ForeignKeyViolationError(
                "insert or update on table violates foreign key constraint"
            )
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 999999, "basis": "deposit"},
            )

        assert response.status_code == 422

    @pytest.mark.integration
    def test_unique_violation_remints_once_then_500(self, mock_db_pool, admin_user) -> None:
        pool, _conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(
            side_effect=asyncpg.UniqueViolationError("duplicate key value")
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit"},
            )

        assert response.status_code == 500
        assert fake_repo.insert.await_count == 2


class TestListCases:
    @pytest.mark.integration
    def test_admin_list_has_no_assigned_to_filter(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetch = AsyncMock(return_value=[])

        response = client.get("/api/e33/cases")

        assert response.status_code == 200
        assert response.json() == {"cases": [], "total": 0}
        query = conn.fetch.call_args.args[0]
        assert "assigned_to" not in query

    @pytest.mark.integration
    def test_non_admin_list_is_filtered_by_assigned_to(self, mock_db_pool, team_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, team_user), raise_server_exceptions=False)
        conn.fetch = AsyncMock(return_value=[])

        response = client.get("/api/e33/cases")

        assert response.status_code == 200
        query = conn.fetch.call_args.args[0]
        params = conn.fetch.call_args.args[1:]
        assert "assigned_to" in query
        assert team_user["email"].lower() in params

    @pytest.mark.integration
    def test_list_returns_case_summary_rows(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "case_id": "E33-2026-abc123",
                    "client_id": 1,
                    "client_name": "Alice Example",
                    "basis": "deposit",
                    "stage": "fit_memo",
                    "owner_email": None,
                    "guarantee_proof_deadline": None,
                    "stayguard_eligible": False,
                    "dependent_code": None,
                    "principal_case_id": None,
                    "created_at": e33_cases_module.datetime.now(tz=e33_cases_module.timezone.utc),
                }
            ]
        )

        response = client.get("/api/e33/cases")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["cases"][0]["case_id"] == "E33-2026-abc123"
        assert body["cases"][0]["client_name"] == "Alice Example"


class TestRBAC:
    @pytest.mark.integration
    def test_client_role_jwt_returns_403(self, mock_db_pool, client_user) -> None:
        pool, _conn = mock_db_pool
        client = TestClient(_make_app(pool, client_user), raise_server_exceptions=False)

        response = client.get("/api/e33/cases")

        assert response.status_code == 403


class TestGetCase:
    @pytest.mark.integration
    def test_get_case_not_found_returns_404(self, mock_db_pool, admin_user) -> None:
        pool, _conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=None)

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.get("/api/e33/cases/E33-2026-notexist")

        assert response.status_code == 404

    @pytest.mark.integration
    def test_get_case_non_admin_not_assigned_returns_403(self, mock_db_pool, team_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, team_user), raise_server_exceptions=False)

        case = _existing_case()
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "someone-else@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.get(f"/api/e33/cases/{case.case_id}")

        assert response.status_code == 403

    @pytest.mark.integration
    def test_get_case_success_includes_allowed_next_stages(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case()
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.get(f"/api/e33/cases/{case.case_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["allowed_next_stages"] == ["bank_precheck"]
        assert body["guarantee"] is None
        assert body["forecasts"] == []


class TestAdvanceCase:
    @pytest.mark.integration
    def test_invalid_transition_returns_409(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case()  # stage=fit_memo — payment is unreachable directly
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        fake_repo.save = AsyncMock(return_value=None)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                f"/api/e33/cases/{case.case_id}/advance",
                json={"to_stage": "payment"},
            )

        assert response.status_code == 409
        fake_repo.save.assert_not_awaited()

    @pytest.mark.integration
    def test_transition_into_itap_eval_returns_409_even_though_edge_exists(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        fake_repo.save = AsyncMock(return_value=None)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                f"/api/e33/cases/{case.case_id}/advance",
                json={"to_stage": "itap_eval"},
            )

        assert response.status_code == 409
        assert "letter-006" in response.json()["detail"].lower()
        fake_repo.save.assert_not_awaited()

    @pytest.mark.integration
    def test_advance_happy_path_appends_stage_history(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case()  # stage=fit_memo
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        fake_repo.save = AsyncMock(return_value=None)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                f"/api/e33/cases/{case.case_id}/advance",
                json={"to_stage": "bank_precheck", "note": "docs received"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["stage"] == "bank_precheck"
        assert len(body["stage_history"]) == 1
        assert body["stage_history"][0]["to_stage"] == "bank_precheck"
        assert body["stage_history"][0]["from_stage"] == "fit_memo"
        assert body["stage_history"][0]["note"] == "docs received"
        fake_repo.save.assert_awaited_once()


class TestAddEvidence:
    @pytest.mark.integration
    def test_custody_violating_metadata_key_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        fake_repo.save = AsyncMock(return_value=None)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                f"/api/e33/cases/{case.case_id}/evidence",
                json={
                    "kind": "bank_confirmation",
                    "document_ref": "doc-1",
                    "metadata": {"account_number": "1234567890"},
                },
            )

        assert response.status_code == 422
        assert "no-custody" in response.json()["detail"].lower()
        fake_repo.save.assert_not_awaited()
        assert case.evidence == []

    @pytest.mark.integration
    def test_add_evidence_happy_path(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        fake_repo.save = AsyncMock(return_value=None)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                f"/api/e33/cases/{case.case_id}/evidence",
                json={
                    "kind": "bank_confirmation",
                    "document_ref": "doc-1",
                    "issuing_party": "Bank Mandiri",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["evidence"]) == 1
        assert body["evidence"][0]["document_ref"] == "doc-1"
        assert body["evidence"][0]["metadata"]["issuing_party"] == "Bank Mandiri"
        fake_repo.save.assert_awaited_once()


class TestSummary:
    @pytest.mark.integration
    def test_summary_reports_unprovisioned_switch_state(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        with patch.object(
            e33_cases_module,
            "resolve_scan_switch",
            AsyncMock(return_value=ScanSwitchState.UNPROVISIONED),
        ):
            response = client.get("/api/e33/summary")

        assert response.status_code == 200
        body = response.json()
        assert body["scan_switch"] == "unprovisioned"
        assert body["by_stage"] == {}
        assert body["active_total"] == 0
        assert body["guarantee_due_30d"] == 0

    @pytest.mark.integration
    def test_summary_active_total_excludes_terminal_stages(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetch = AsyncMock(
            return_value=[
                {"stage": "fit_memo", "n": 3},
                {"stage": "epo", "n": 2},
                {"stage": "status_change", "n": 1},
            ]
        )
        conn.fetchval = AsyncMock(return_value=0)

        with patch.object(
            e33_cases_module,
            "resolve_scan_switch",
            AsyncMock(return_value=ScanSwitchState.ENABLED),
        ):
            response = client.get("/api/e33/summary")

        assert response.status_code == 200
        body = response.json()
        assert body["by_stage"] == {"fit_memo": 3, "epo": 2, "status_change": 1}
        assert body["active_total"] == 3
        assert body["scan_switch"] == "enabled"


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert e33_cases_module.router.prefix == "/api/e33"
        assert e33_cases_module.router.tags == ["e33"]

    @pytest.mark.unit
    def test_repository_and_scanner_imports_are_real(self) -> None:
        # Guards against a stale/renamed re-export in the router module.
        assert e33_cases_module.E33CaseRepository is E33CaseRepository

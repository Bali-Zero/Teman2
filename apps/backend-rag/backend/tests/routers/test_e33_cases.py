"""Tests for the E33 Second Home internal console router (F4a case entrance)."""

from __future__ import annotations

import re
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.e33_cases as e33_cases_module
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.crm.e33_case_repository import E33CaseRepository, case_to_row
from backend.services.crm.e33_guarantee_scanner import ScanSwitchState
from backend.services.crm.e33_lifecycle import (
    E33Case,
    E33Stage,
    EvidenceKind,
    EvidenceRef,
    GuaranteeBasis,
)

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
    # "team" is a role production issues; "team_member" never was one, and the
    # team gate is an allow-list now (service_accounts.py::TEAM_ROLES).
    return {"id": "2", "email": "team@balizero.com", "role": "team"}


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


def _wire_txn_conn(conn, *, case: E33Case | None, client_row: dict[str, object] | None) -> None:
    """Wire mock_db_pool's shared conn for the load(FOR UPDATE)->mutate->save
    path used by advance_case/add_evidence, which run the REAL
    E33CaseRepository.with_connection(conn) (not a patched repo class).

    fetchrow order: 1) repo.load()'s full-row SELECT, 2) the client
    full_name/assigned_to lookup. A ``None`` case models "not found" — only
    the first fetchrow (repo.load) then returns None; the second is not
    reached by the router in that path, so client_row may be omitted.
    """
    if case is None:
        conn.fetchrow = AsyncMock(return_value=None)
    else:
        side_effects = [case_to_row(case)]
        if client_row is not None:
            side_effects.append(client_row)
        conn.fetchrow = AsyncMock(side_effect=side_effects)
    conn.execute = AsyncMock(return_value="OK")


class TestCreateCase:
    @pytest.mark.integration
    def test_create_case_success_mints_case_id_and_starts_at_fit_memo(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice Example",
                "assigned_to": "admin@balizero.com",
                "deleted_at": None,
            }
        )
        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)
        fake_repo.load = AsyncMock()

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["stage"] == "fit_memo"
        assert body["client_name"] == "Alice Example"
        assert CASE_ID_RE.match(body["case_id"]), body["case_id"]
        assert body["stage_history"] == []
        fake_repo.insert.assert_awaited_once()
        assert fake_repo.insert.await_args.args[0].practice_id is None
        fake_repo.load.assert_not_awaited()
        conn.fetchval.assert_not_awaited()

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "scenario, role, principal_client_id, assigned_to, expected_status",
        [
            ("different-clients", "team", 2, "TEAM@balizero.com", 201),
            ("admin", "admin", 2, "other@example.com", 201),
            ("same-client", "team", 1, "team@balizero.com", 201),
            ("missing-principal", "team", 2, "team@balizero.com", 422),
            ("missing-client", "team", 2, "team@balizero.com", 422),
            ("archived-client", "team", 2, "team@balizero.com", 422),
            ("other-staff", "team", 2, "other@example.com", 422),
            ("unassigned", "team", 2, None, 422),
        ],
        ids=lambda value: str(value),
    )
    def test_principal_link_requires_access_to_both_clients(
        self,
        mock_db_pool,
        scenario: str,
        role: str,
        principal_client_id: int,
        assigned_to: str | None,
        expected_status: int,
    ) -> None:
        pool, conn = mock_db_pool
        user = {"id": "2", "email": "team@balizero.com", "role": role}
        requested_client = {
            "full_name": "Synthetic dependent",
            "assigned_to": user["email"],
            "deleted_at": None,
        }
        principal_client = {
            "full_name": "Synthetic principal",
            "assigned_to": assigned_to,
            "deleted_at": "2026-01-01" if scenario == "archived-client" else None,
        }
        rows = [requested_client]
        if scenario != "missing-principal":
            rows.append(None if scenario == "missing-client" else principal_client)
        conn.fetchrow = AsyncMock(side_effect=rows)
        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)
        principal = (
            None
            if scenario == "missing-principal"
            else _existing_case(client_id=principal_client_id)
        )
        fake_repo.load = AsyncMock(return_value=principal)
        client = TestClient(_make_app(pool, user), raise_server_exceptions=False)

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={
                    "client_id": 1,
                    "basis": "deposit",
                    "dependent_code": "E31B",
                    "principal_case_id": "E33-2026-abc123",
                },
            )

        assert response.status_code == expected_status
        fake_repo.load.assert_awaited_once_with("E33-2026-abc123")
        assert conn.fetchrow.await_count == len(rows)
        if principal is not None:
            assert conn.fetchrow.await_args.args[1:] == (principal_client_id,)
        if expected_status == 201:
            fake_repo.insert.assert_awaited_once()
            created = fake_repo.insert.await_args.args[0]
            assert (created.client_id, created.dependent_code, created.principal_case_id) == (
                1,
                "E31B",
                "E33-2026-abc123",
            )
        else:
            assert response.json() == {"detail": "principal case is not available"}
            fake_repo.insert.assert_not_awaited()

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "access_error",
        [HTTPException(409, "synthetic conflict"), RuntimeError("synthetic failure")],
    )
    def test_unexpected_principal_access_error_is_not_masked(
        self, mock_db_pool, team_user, access_error: Exception
    ) -> None:
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Synthetic client",
                "assigned_to": team_user["email"],
                "deleted_at": None,
            }
        )
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=_existing_case(client_id=2))
        fake_repo.insert = AsyncMock()
        client = TestClient(_make_app(pool, team_user), raise_server_exceptions=False)
        with (
            patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo),
            patch.object(
                e33_cases_module, "_assert_client_access", side_effect=[None, access_error]
            ),
        ):
            response = client.post(
                "/api/e33/cases",
                json={
                    "client_id": 1,
                    "basis": "deposit",
                    "dependent_code": "E31B",
                    "principal_case_id": "E33-2026-abc123",
                },
            )
        assert response.status_code == (409 if isinstance(access_error, HTTPException) else 500)
        fake_repo.insert.assert_not_awaited()

    @pytest.mark.integration
    def test_configured_crm_admin_can_link_different_clients(self, mock_db_pool, team_user) -> None:
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Synthetic client", "assigned_to": None, "deleted_at": None}
        )
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=_existing_case(client_id=2))
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)
        client = TestClient(_make_app(pool, team_user), raise_server_exceptions=False)
        with (
            patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo),
            patch(
                "backend.app.utils.crm_utils._crm_admin_emails",
                return_value=frozenset({team_user["email"]}),
            ),
        ):
            response = client.post(
                "/api/e33/cases",
                json={
                    "client_id": 1,
                    "basis": "deposit",
                    "dependent_code": "E31B",
                    "principal_case_id": "E33-2026-abc123",
                },
            )
        assert response.status_code == 201
        fake_repo.load.assert_awaited_once_with("E33-2026-abc123")
        fake_repo.insert.assert_awaited_once()

    @pytest.mark.integration
    @pytest.mark.parametrize("role", ["admin", "team"])
    def test_practice_for_requested_client_is_linked(
        self, mock_db_pool, admin_user, role: str
    ) -> None:
        pool, conn = mock_db_pool
        user = {**admin_user, "role": role}
        client = TestClient(_make_app(pool, user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice Example",
                "assigned_to": user["email"],
                "deleted_at": None,
            }
        )
        conn.fetchval = AsyncMock(return_value=1)
        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit", "practice_id": 42},
            )

        assert response.status_code == 201
        fake_repo.insert.assert_awaited_once()
        case = fake_repo.insert.await_args.args[0]
        assert (case.client_id, case.practice_id) == (1, 42)
        conn.fetchval.assert_awaited_once()
        assert conn.fetchval.await_args.args[1:] == (42,)

    @pytest.mark.integration
    @pytest.mark.parametrize("practice_client_id", [None, 2], ids=["missing", "other-client"])
    def test_unavailable_practice_returns_same_422_and_never_inserts(
        self, mock_db_pool, admin_user, practice_client_id: int | None
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice Example",
                "assigned_to": admin_user["email"],
                "deleted_at": None,
            }
        )
        conn.fetchval = AsyncMock(return_value=practice_client_id)
        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit", "practice_id": 42},
            )

        assert response.status_code == 422
        assert response.json() == {"detail": "practice is not available for this client"}
        fake_repo.insert.assert_not_awaited()

    @pytest.mark.integration
    def test_explicit_null_practice_preserves_case_creation(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice Example",
                "assigned_to": admin_user["email"],
                "deleted_at": None,
            }
        )
        fake_repo = MagicMock()
        fake_repo.insert = AsyncMock(side_effect=lambda case: case)

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit", "practice_id": None},
            )

        assert response.status_code == 201
        assert fake_repo.insert.await_args.args[0].practice_id is None
        conn.fetchval.assert_not_awaited()

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
    def test_property_basis_returns_422_and_never_touches_db(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        response = client.post(
            "/api/e33/cases",
            json={"client_id": 1, "basis": "property"},
        )

        assert response.status_code == 422
        assert "property" in response.json()["detail"].lower()
        conn.fetchrow.assert_not_called()

    @pytest.mark.integration
    def test_client_does_not_exist_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(return_value=None)

        response = client.post(
            "/api/e33/cases",
            json={"client_id": 999999, "basis": "deposit"},
        )

        assert response.status_code == 422
        assert "does not exist" in response.json()["detail"]

    @pytest.mark.integration
    def test_archived_client_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice",
                "assigned_to": "admin@balizero.com",
                "deleted_at": "2026-01-01T00:00:00+00:00",
            }
        )

        response = client.post(
            "/api/e33/cases",
            json={"client_id": 1, "basis": "deposit"},
        )

        assert response.status_code == 422
        assert "archived" in response.json()["detail"]

    @pytest.mark.integration
    def test_non_admin_creating_for_unassigned_client_returns_403(
        self, mock_db_pool, team_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, team_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice",
                "assigned_to": "someone-else@balizero.com",
                "deleted_at": None,
            }
        )

        response = client.post(
            "/api/e33/cases",
            json={
                "client_id": 1,
                "basis": "deposit",
                "practice_id": 42,
                "dependent_code": "E31B",
                "principal_case_id": "E33-2026-abc123",
            },
        )

        assert response.status_code == 403
        conn.fetchval.assert_not_awaited()

    @pytest.mark.integration
    def test_fk_violation_returns_422_generic_detail(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice",
                "assigned_to": "admin@balizero.com",
                "deleted_at": None,
            }
        )

        fake_repo = MagicMock()
        raw_pg_detail = "insert or update on table violates foreign key constraint pk_practice_42"
        fake_repo.insert = AsyncMock(side_effect=asyncpg.ForeignKeyViolationError(raw_pg_detail))
        # The practice can disappear after the pre-insert ownership lookup.
        conn.fetchval = AsyncMock(return_value=1)

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.post(
                "/api/e33/cases",
                json={"client_id": 1, "basis": "deposit", "practice_id": 999999},
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert raw_pg_detail not in detail  # no raw asyncpg exception text leaked to the client
        assert "does not exist" in detail
        fake_repo.insert.assert_awaited_once()

    @pytest.mark.integration
    def test_unique_violation_remints_once_then_500(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetchrow = AsyncMock(
            return_value={
                "full_name": "Alice",
                "assigned_to": "admin@balizero.com",
                "deleted_at": None,
            }
        )

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
    def test_get_case_success_includes_allowed_next_stages(self, mock_db_pool, admin_user) -> None:
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
        assert body["guarantee_evidence_complete"] is False

    @pytest.mark.integration
    def test_get_case_guarantee_evidence_complete_true_with_full_evidence(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        case = _existing_case(stage=E33Stage.GUARANTEE_PROOF_DUE)
        case.add_evidence(
            EvidenceRef(
                evidence_id="ev-1", kind=EvidenceKind.BANK_CONFIRMATION, document_ref="doc-1"
            )
        )
        case.add_evidence(
            EvidenceRef(
                evidence_id="ev-2",
                kind=EvidenceKind.IMMIGRATION_FILING,
                document_ref="doc-2",
                filed_date=date(2026, 1, 1),
            )
        )
        fake_repo = MagicMock()
        fake_repo.load = AsyncMock(return_value=case)
        conn.fetchrow = AsyncMock(
            return_value={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        with patch.object(e33_cases_module, "E33CaseRepository", return_value=fake_repo):
            response = client.get(f"/api/e33/cases/{case.case_id}")

        assert response.status_code == 200
        assert response.json()["guarantee_evidence_complete"] is True


class TestAdvanceCase:
    @pytest.mark.integration
    def test_advance_locks_row_for_update_via_same_connection(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case()  # fit_memo
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "bank_precheck"},
        )

        assert response.status_code == 200
        lock_call = conn.execute.call_args_list[0]
        assert "FOR UPDATE" in lock_call.args[0]
        assert lock_call.args[1] == case.case_id
        # load (repo) and the lock both went through the same conn — a
        # second, separately-acquired connection would defeat the lock.
        assert conn.fetchrow.call_count == 2

    @pytest.mark.integration
    def test_advance_not_found_returns_404(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        _wire_txn_conn(conn, case=None, client_row=None)

        response = client.post(
            "/api/e33/cases/E33-2026-notexist/advance",
            json={"to_stage": "bank_precheck"},
        )

        assert response.status_code == 404

    @pytest.mark.integration
    def test_advance_non_admin_not_assigned_returns_403(self, mock_db_pool, team_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, team_user), raise_server_exceptions=False)
        case = _existing_case()
        _wire_txn_conn(
            conn,
            case=case,
            client_row={"full_name": "Alice", "assigned_to": "someone-else@balizero.com"},
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "bank_precheck"},
        )

        assert response.status_code == 403
        assert conn.execute.call_count == 1  # lock only, save() never reached

    @pytest.mark.integration
    def test_same_stage_advance_returns_409_and_never_saves(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "itas_active"},
        )

        assert response.status_code == 409
        assert "already in stage" in response.json()["detail"]
        assert conn.execute.call_count == 1  # lock only, save() never called

    @pytest.mark.integration
    def test_invalid_transition_returns_409(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case()  # fit_memo — payment is unreachable directly
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "payment"},
        )

        assert response.status_code == 409
        assert conn.execute.call_count == 1

    @pytest.mark.integration
    def test_transition_into_itap_eval_returns_409_even_though_edge_exists(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "itap_eval"},
        )

        assert response.status_code == 409
        assert "letter-006" in response.json()["detail"].lower()
        assert conn.execute.call_count == 1

    @pytest.mark.integration
    def test_advance_happy_path_appends_stage_history(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case()  # fit_memo
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

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
        assert conn.execute.call_count == 2  # lock + save()

    @pytest.mark.integration
    def test_guarantee_proof_due_to_annual_maintenance_blocked_without_evidence(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.GUARANTEE_PROOF_DUE)
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "annual_maintenance"},
        )

        assert response.status_code == 409
        assert "guarantee evidence" in response.json()["detail"].lower()
        assert conn.execute.call_count == 1

    @pytest.mark.integration
    def test_guarantee_proof_due_to_annual_maintenance_allowed_with_complete_evidence(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.GUARANTEE_PROOF_DUE)
        case.add_evidence(
            EvidenceRef(
                evidence_id="ev-1", kind=EvidenceKind.BANK_CONFIRMATION, document_ref="doc-1"
            )
        )
        case.add_evidence(
            EvidenceRef(
                evidence_id="ev-2",
                kind=EvidenceKind.IMMIGRATION_FILING,
                document_ref="doc-2",
                filed_date=date(2026, 1, 1),
            )
        )
        assert case.guarantee_evidence_complete  # sanity on the fixture itself
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/advance",
            json={"to_stage": "annual_maintenance"},
        )

        assert response.status_code == 200
        assert response.json()["stage"] == "annual_maintenance"


class TestAddEvidence:
    @pytest.mark.integration
    def test_custody_violating_metadata_key_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

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
        assert conn.execute.call_count == 1  # lock only, save() never reached
        assert case.evidence == []

    @pytest.mark.integration
    def test_nested_custody_key_smuggled_in_dict_value_returns_422(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        response = client.post(
            "/api/e33/cases/E33-2026-abc123/evidence",
            json={
                "kind": "bank_confirmation",
                "document_ref": "doc-1",
                "metadata": {"details": {"account_number": "1234567890"}},
            },
        )

        assert response.status_code == 422
        assert "scalar" in response.json()["detail"][0]["msg"].lower()
        # rejected by pydantic before the endpoint runs — no DB round-trip at all
        conn.fetchrow.assert_not_called()

    @pytest.mark.integration
    def test_empty_document_ref_returns_422(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)

        response = client.post(
            "/api/e33/cases/E33-2026-abc123/evidence",
            json={"kind": "bank_confirmation", "document_ref": ""},
        )

        assert response.status_code == 422
        conn.fetchrow.assert_not_called()

    @pytest.mark.integration
    def test_top_level_issuing_party_overwrites_metadata_key(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

        response = client.post(
            f"/api/e33/cases/{case.case_id}/evidence",
            json={
                "kind": "bank_confirmation",
                "document_ref": "doc-1",
                "issuing_party": "Bank Mandiri",
                "metadata": {"issuing_party": "should be overwritten"},
            },
        )

        assert response.status_code == 200
        assert response.json()["evidence"][0]["metadata"]["issuing_party"] == "Bank Mandiri"

    @pytest.mark.integration
    def test_add_evidence_happy_path(self, mock_db_pool, admin_user) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        case = _existing_case(stage=E33Stage.ITAS_ACTIVE)
        _wire_txn_conn(
            conn, case=case, client_row={"full_name": "Alice", "assigned_to": "admin@balizero.com"}
        )

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
        assert conn.execute.call_count == 2  # lock + save()


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
    def test_summary_active_total_excludes_terminal_stages(self, mock_db_pool, admin_user) -> None:
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

    @pytest.mark.integration
    def test_guarantee_due_30d_filters_to_active_permit_stages_only(
        self, mock_db_pool, admin_user
    ) -> None:
        pool, conn = mock_db_pool
        client = TestClient(_make_app(pool, admin_user), raise_server_exceptions=False)
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=2)

        with patch.object(
            e33_cases_module,
            "resolve_scan_switch",
            AsyncMock(return_value=ScanSwitchState.ENABLED),
        ):
            response = client.get("/api/e33/summary")

        assert response.status_code == 200
        assert response.json()["guarantee_due_30d"] == 2

        due_query = conn.fetchval.call_args.args[0]
        due_params = conn.fetchval.call_args.args[1:]
        assert "ANY(" in due_query
        assert ["annual_maintenance", "guarantee_proof_due", "itas_active"] in due_params
        # terminal stages must never appear in the "due" stage filter
        assert not any("epo" in p for p in due_params if isinstance(p, list))
        assert not any("status_change" in p for p in due_params if isinstance(p, list))


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert e33_cases_module.router.prefix == "/api/e33"
        assert e33_cases_module.router.tags == ["e33"]

    @pytest.mark.unit
    def test_repository_and_scanner_imports_are_real(self) -> None:
        # Guards against a stale/renamed re-export in the router module.
        assert e33_cases_module.E33CaseRepository is E33CaseRepository

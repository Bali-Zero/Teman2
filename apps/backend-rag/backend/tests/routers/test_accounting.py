"""Tests for the accounting router (P0 read-only endpoints + RBAC gate).

Mirrors the crm_practices test pattern: mock_db_pool fixture, dependency
overrides, TestClient. Verifies RBAC (Asya/admin allowed, others 403), the
three read endpoints, and query-param validation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.accounting as accounting_module
from backend.app.dependencies import get_current_user, get_database_pool


@pytest.fixture
def asya_user() -> dict[str, str]:
    # asya@ is in CRM_EXTRA_ADMIN_EMAILS -> is_crm_admin() True
    return {"id": "asya", "email": "asya@balizero.com", "role": "user"}


@pytest.fixture
def outsider_user() -> dict[str, str]:
    return {"id": "x", "email": "random@balizero.com", "role": "user"}


def _build_app(mock_db_pool, user: dict[str, str]) -> FastAPI:
    pool, _conn = mock_db_pool
    app = FastAPI()
    app.include_router(accounting_module.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database_pool] = lambda: pool
    return app


class TestRBAC:
    def test_asya_allowed_cashout(self, mock_db_pool, asya_user) -> None:
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/cashout")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_outsider_denied_cashout(self, mock_db_pool, outsider_user) -> None:
        client = TestClient(_build_app(mock_db_pool, outsider_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/cashout")
        assert resp.status_code == 403

    def test_outsider_denied_summary(self, mock_db_pool, outsider_user) -> None:
        client = TestClient(_build_app(mock_db_pool, outsider_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/summary")
        assert resp.status_code == 403


class TestCashoutEndpoint:
    def test_cashout_returns_rows(self, mock_db_pool, asya_user) -> None:
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "movement_date": "2026-06-25",
                    "type": "invoice_payment",
                    "amount_idr": 4000000,
                    "pnbp_idr": 1000000,
                    "margin_idr": 3000000,
                    "final_price_idr": 4000000,
                    "client_name": "REDACTED",
                }
            ]
        )
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/cashout?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["margin_idr"] == 3000000


class TestBankTransactionsEndpoint:
    def test_invalid_reconciled_status_422(self, mock_db_pool, asya_user) -> None:
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/bank-transactions?reconciled_status=bogus")
        assert resp.status_code == 422

    def test_valid_status_passes(self, mock_db_pool, asya_user) -> None:
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/bank-transactions?reconciled_status=unmatched")
        assert resp.status_code == 200


class TestMatchCandidates:
    def test_txn_not_found_404(self, mock_db_pool, asya_user) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=None)
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/match-candidates/999")
        assert resp.status_code == 404

    def test_debit_txn_rejected_422(self, mock_db_pool, asya_user) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "id": 1, "txn_date": "2026-06-25", "amount_idr": 4000000,
                "direction": "debit", "description": "outgoing",
            }
        )
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/match-candidates/1")
        assert resp.status_code == 422

    def test_outsider_denied(self, mock_db_pool, outsider_user) -> None:
        client = TestClient(_build_app(mock_db_pool, outsider_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/match-candidates/1")
        assert resp.status_code == 403


class TestConfirm:
    def test_outsider_denied(self, mock_db_pool, outsider_user) -> None:
        client = TestClient(_build_app(mock_db_pool, outsider_user), raise_server_exceptions=False)
        resp = client.post("/api/crm/accounting/confirm", json={"practice_id": 1, "amount_applied_idr": 100})
        assert resp.status_code == 403

    def test_bad_status_422(self, mock_db_pool, asya_user) -> None:
        # reconcile_service raises ReconcileError -> 422; mock confirm to raise
        from backend.services.accounting.reconcile_service import ReconcileError

        with patch(
            "backend.app.routers.accounting.reconcile_service.confirm_payment",
            AsyncMock(side_effect=ReconcileError("new_status must be one of ...")),
        ):
            client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
            resp = client.post(
                "/api/crm/accounting/confirm",
                json={"practice_id": 1, "amount_applied_idr": 100, "new_status": "bogus"},
            )
        assert resp.status_code == 422

    def test_confirm_success_path(self, mock_db_pool, asya_user) -> None:
        """D3: a valid confirm returns 200, derives confirmed_by from the JWT
        (lowercased email — never client-supplied), echoes the audit ids, and
        invalidates the same CRM cache keys the PATCH path uses (superscar #9)."""
        from backend.services.accounting.reconcile_service import ConfirmResult

        fake_result = ConfirmResult(
            practice_id=10,
            invoice_id=5,
            cashout_id=77,
            reconciliation_log_id=88,
            status_before="unpaid",
            status_after="paid",
        )
        confirm_mock = AsyncMock(return_value=fake_result)
        cache_mock = AsyncMock()

        with patch(
            "backend.app.routers.accounting.reconcile_service.confirm_payment", confirm_mock
        ), patch("backend.core.cache.invalidate_cache", cache_mock):
            client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
            resp = client.post(
                "/api/crm/accounting/confirm",
                json={
                    "bank_txn_id": 3,
                    "practice_id": 10,
                    "invoice_id": 5,
                    "amount_applied_idr": 4_000_000,
                    "new_status": "paid",
                    "payment_reference": "CIMB-REF-1",
                    "margin_idr": 4_000_000,
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["practice_id"] == 10
        assert body["cashout_id"] == 77
        assert body["reconciliation_log_id"] == 88
        assert body["status_before"] == "unpaid"
        assert body["status_after"] == "paid"

        # confirmed_by comes from the JWT identity, lowercased — not the payload.
        assert confirm_mock.await_count == 1
        kwargs = confirm_mock.await_args.kwargs
        assert kwargs["confirmed_by"] == "asya@balizero.com"
        assert kwargs["practice_id"] == 10
        assert kwargs["amount_applied_idr"] == 4_000_000

        # both CRM cache namespaces invalidated.
        invalidated = {c.args[0] for c in cache_mock.await_args_list}
        assert "zantara:crm_practices_stats:*" in invalidated
        assert "zantara:crm_clients_stats:*" in invalidated

    def test_confirm_caps_email_case(self, mock_db_pool) -> None:
        """confirmed_by is always lowercased even if the JWT email is mixed-case."""
        from backend.services.accounting.reconcile_service import ConfirmResult

        mixed = {"id": "asya", "email": "Asya@BaliZero.com", "role": "user"}
        confirm_mock = AsyncMock(
            return_value=ConfirmResult(
                practice_id=1, invoice_id=None, cashout_id=1,
                reconciliation_log_id=1, status_before="unpaid", status_after="paid",
            )
        )
        with patch(
            "backend.app.routers.accounting.reconcile_service.confirm_payment", confirm_mock
        ), patch("backend.core.cache.invalidate_cache", AsyncMock()):
            client = TestClient(_build_app(mock_db_pool, mixed), raise_server_exceptions=False)
            resp = client.post(
                "/api/crm/accounting/confirm",
                json={"practice_id": 1, "amount_applied_idr": 100, "new_status": "paid"},
            )
        assert resp.status_code == 200
        assert confirm_mock.await_args.kwargs["confirmed_by"] == "asya@balizero.com"


class TestSummaryEndpoint:
    def test_summary_shape(self, mock_db_pool, asya_user) -> None:
        _pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(
            return_value={
                "income_idr": 10000000,
                "outgoing_idr": 3000000,
                "margin_total_idr": 5000000,
                "pnbp_total_idr": 2000000,
                "row_count": 4,
            }
        )
        conn.fetch = AsyncMock(return_value=[])
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.get("/api/crm/accounting/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["income_idr"] == 10000000
        assert data["net_idr"] == 7000000  # 10M - 3M
        assert data["margin_total_idr"] == 5000000

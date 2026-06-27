"""Tests for the accounting router (P0 read-only endpoints + RBAC gate).

Mirrors the crm_practices test pattern: mock_db_pool fixture, dependency
overrides, TestClient. Verifies RBAC (Asya/admin allowed, others 403), the
three read endpoints, and query-param validation.
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.accounting as accounting_module
from backend.app.dependencies import get_current_user, get_database_pool


def _gabungan_pdf_bytes() -> bytes:
    """A minimal 2-week GABUNGAN cashout worksheet PDF (gridded so pdfplumber
    sees the tables the way it sees Asya's spreadsheet export)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    header = ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE", "NOTE"]
    data = [
        ["NEW CASHOUT 6 MARCH 2026", "", "", "", "", "", "", ""],
        header,
        ["CLIENT ONE", "C1", "Rp1.000.000", "", "", "Rp600.000", "Rp2.300.000", ""],
        ["CLIENT TWO", "C1 - Urgent", "Rp1.000.000", "Rp800.000", "", "Rp600.000", "Rp3.300.000", ""],
        ["NEW CASHOUT 13 MARCH 2026", "", "", "", "", "", "", ""],
        header,
        ["CLIENT THREE", "C1", "Rp1.000.000", "", "", "Rp600.000", "Rp2.300.000", ""],
    ]
    table = Table(data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    doc.build([table])
    return buf.getvalue()


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


class TestExportSheet:
    def test_outsider_denied(self, mock_db_pool, outsider_user) -> None:
        client = TestClient(_build_app(mock_db_pool, outsider_user), raise_server_exceptions=False)
        resp = client.post("/api/crm/accounting/export-sheet")
        assert resp.status_code == 403

    def test_missing_env_returns_503(self, mock_db_pool, asya_user, monkeypatch) -> None:
        # No ACCOUNTING_EXPORT_SHEET_ID -> 503 with a config hint, never a 500.
        monkeypatch.delenv("ACCOUNTING_EXPORT_SHEET_ID", raising=False)
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.post("/api/crm/accounting/export-sheet")
        assert resp.status_code == 503
        assert "ACCOUNTING_EXPORT_SHEET_ID" in resp.json()["detail"]

    def test_success_writes_rows(self, mock_db_pool, asya_user, monkeypatch) -> None:
        monkeypatch.setenv("ACCOUNTING_EXPORT_SHEET_ID", "sheet-abc-123")
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "movement_date": "2026-06-25",
                    "week_label": "2026-W26",
                    "client_name": "Dina B",
                    "category": "KITAS",
                    "pnbp_idr": 1000000,
                    "urgent_idr": 0,
                    "rptka_imta_idr": 0,
                    "margin_idr": 3000000,
                    "final_price_idr": 4000000,
                    "description": "ref",
                }
            ]
        )

        write_mock = AsyncMock(return_value={"updatedCells": 20})

        class FakeSheets:
            write_range = write_mock

        with patch(
            "backend.services.integrations.sheets_service.SheetsService",
            FakeSheets,
        ):
            client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
            resp = client.post("/api/crm/accounting/export-sheet")

        assert resp.status_code == 200
        body = resp.json()
        assert body["spreadsheet_id"] == "sheet-abc-123"
        assert body["rows_exported"] == 1  # header excluded
        assert body["updated_cells"] == 20
        # the SheetsService was actually called with our spreadsheet id
        assert write_mock.await_count == 1
        assert write_mock.await_args.args[0] == "sheet-abc-123"

    def test_custom_tab_env_used_in_write_range(
        self, mock_db_pool, asya_user, monkeypatch
    ) -> None:
        # ACCOUNTING_EXPORT_SHEET_TAB overrides the default 'Cashout' tab, so a
        # fresh sheet whose tab is still 'Sheet1' works without renaming.
        monkeypatch.setenv("ACCOUNTING_EXPORT_SHEET_ID", "sheet-abc-123")
        monkeypatch.setenv("ACCOUNTING_EXPORT_SHEET_TAB", "Sheet1")
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        write_mock = AsyncMock(return_value={"updatedCells": 10})

        class FakeSheets:
            write_range = write_mock

        with patch(
            "backend.services.integrations.sheets_service.SheetsService",
            FakeSheets,
        ):
            client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
            resp = client.post("/api/crm/accounting/export-sheet")

        assert resp.status_code == 200
        # write_range(spreadsheet_id, range_, values) — range is positional arg 1
        assert write_mock.await_args.args[1] == "'Sheet1'!A1"

    def test_sheets_credentials_missing_returns_503(
        self, mock_db_pool, asya_user, monkeypatch
    ) -> None:
        monkeypatch.setenv("ACCOUNTING_EXPORT_SHEET_ID", "sheet-abc-123")
        _pool, conn = mock_db_pool
        conn.fetch = AsyncMock(return_value=[])

        class FakeSheets:
            write_range = AsyncMock(
                side_effect=FileNotFoundError("Google credentials not found.")
            )

        with patch(
            "backend.services.integrations.sheets_service.SheetsService",
            FakeSheets,
        ):
            client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
            resp = client.post("/api/crm/accounting/export-sheet")
        assert resp.status_code == 503


class TestImportCashout:
    def test_outsider_denied(self, mock_db_pool, outsider_user) -> None:
        client = TestClient(_build_app(mock_db_pool, outsider_user), raise_server_exceptions=False)
        resp = client.post(
            "/api/crm/accounting/import-cashout",
            files={"file": ("GABUNGAN.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 403

    def test_non_pdf_rejected_422(self, mock_db_pool, asya_user) -> None:
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.post(
            "/api/crm/accounting/import-cashout",
            files={"file": ("ledger.csv", b"a,b,c", "text/csv")},
        )
        assert resp.status_code == 422

    def test_undated_pdf_fails_loud_422(self, mock_db_pool, asya_user) -> None:
        # A PDF with no "NEW CASHOUT" title must 422, never a silent 0-row import.
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        t = Table([["NAME", "PROCESS", "PNBP"], ["JOHN", "C1", "Rp1.000.000"]])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
        doc.build([t])

        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.post(
            "/api/crm/accounting/import-cashout",
            files={"file": ("no-title.pdf", buf.getvalue(), "application/pdf")},
        )
        assert resp.status_code == 422

    def test_import_success_persists_rows(self, mock_db_pool, asya_user) -> None:
        """A real 2-week GABUNGAN PDF imports 3 client rows over 2 weeks, writes
        them with the import sentinel, and reports the weeks back."""
        _pool, conn = mock_db_pool
        # asyncpg-style command tags: delete reports 0 prior rows, each insert 1.
        conn.execute = AsyncMock(side_effect=lambda *a, **k: (
            "DELETE 0" if "DELETE" in a[0] else "INSERT 0 1"
        ))

        with patch("backend.core.cache.invalidate_cache", AsyncMock()):
            client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
            resp = client.post(
                "/api/crm/accounting/import-cashout",
                files={"file": ("GABUNGAN BS.pdf", _gabungan_pdf_bytes(), "application/pdf")},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["imported"] == 3
        assert body["weeks"] == ["2026-W10", "2026-W11"]
        assert body["source_filename"] == "GABUNGAN BS.pdf"

        # two DELETE (one per week) + three INSERT calls hit the connection.
        calls = [c.args[0] for c in conn.execute.await_args_list]
        assert sum("DELETE FROM weekly_cashout" in q for q in calls) == 2
        assert sum("INSERT INTO weekly_cashout" in q for q in calls) == 3
        # every insert carries the import sentinel as recorded_by, never the real
        # row content as a different writer (scope safety for idempotent re-import).
        insert_args = [c.args for c in conn.execute.await_args_list if "INSERT" in c.args[0]]
        assert all(args[-1] == "cashout-pdf-import" for args in insert_args)

    def test_empty_file_rejected_422(self, mock_db_pool, asya_user) -> None:
        client = TestClient(_build_app(mock_db_pool, asya_user), raise_server_exceptions=False)
        resp = client.post(
            "/api/crm/accounting/import-cashout",
            files={"file": ("GABUNGAN.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 422


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

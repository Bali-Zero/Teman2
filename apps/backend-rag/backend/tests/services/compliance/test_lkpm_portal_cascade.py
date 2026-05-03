"""
Regression tests for the LKPM portal shareholder cascade.

SCAR: 2026-04-15 — `get_history_for_portal_client` and
`get_receipts_for_portal_client` used to join on `r.client_id`, which is
inconsistently populated: some rows use a real `clients.id`, others use a
`companies.id` (Lori's import convention, see
`scripts/import_lkpm_q1_2026.py:15`). `client_company_links.client_id` is
always a real client id, so for rows with the Lori convention the cascade
silently returned 0.

These tests are not about the exact number of rows returned — they guard the
SQL SHAPE. Specifically: both methods MUST join via `r.company_id IN (SELECT
ccl.company_id ...)`, not `r.client_id IN (...)`.

See `.claude/rules/cicatrix-scars.md` for the full scar and antibody.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

# ──────────────────────────────────────────────────────────────────────
# Fixture
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_pool() -> MagicMock:
    """Same shape as `TestLKPMServiceWithMockedDB.mock_pool` in test_lkpm_service.py."""
    pool = MagicMock()
    conn = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    pool._conn = conn
    # fetch() returns [] by default — methods under test still issue the SQL.
    conn.fetch.return_value = []
    return pool


def _captured_sql(conn: AsyncMock) -> str:
    """Extract the SQL string the service passed to `conn.fetch(...)`."""
    assert conn.fetch.await_count == 1, (
        f"expected exactly one conn.fetch call, got {conn.fetch.await_count}"
    )
    call = conn.fetch.await_args
    # `conn.fetch(sql, *params)` — positional arg 0 is the SQL.
    sql = call.args[0]
    assert isinstance(sql, str) and sql.strip(), "SQL is empty"
    return sql


def _normalize(sql: str) -> str:
    """Collapse whitespace so we can match phrases that span lines."""
    return re.sub(r"\s+", " ", sql).strip()


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────


class TestGetHistoryForPortalClientCascade:
    """Regression: the cascade must key on `r.company_id`, not `r.client_id`."""

    @pytest.mark.asyncio
    async def test_query_filters_by_r_company_id_in_ccl_company_id(
        self, mock_pool: MagicMock,
    ) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        await service.get_history_for_portal_client(client_id=11139)

        sql = _normalize(_captured_sql(mock_pool._conn))

        # Antibody present: the shareholder cascade keys via company_id.
        assert "r.company_id IN" in sql, (
            f"cascade must filter lkpm_reports via company_id, got SQL:\n{sql}"
        )
        # Inner subquery must pull company_id from client_company_links, not client_id.
        assert re.search(r"SELECT\s+DISTINCT\s+ccl\.company_id", sql), (
            "subquery should SELECT DISTINCT ccl.company_id from "
            f"client_company_links, got:\n{sql}"
        )
        # Scar tripwire: the old broken pattern must NOT reappear.
        assert "r.client_id IN" not in sql, (
            "regressed: query now keys lkpm_reports via r.client_id — see "
            "cicatrix-scars.md SCAR: lkpm_service.py\nSQL:\n" + sql
        )
        # And we must still filter only active links.
        assert "status = 'active'" in sql, (
            "cascade must filter client_company_links.status = 'active'"
        )

    @pytest.mark.asyncio
    async def test_passes_client_id_as_positional_param(
        self, mock_pool: MagicMock,
    ) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        await service.get_history_for_portal_client(client_id=11139)

        call = mock_pool._conn.fetch.await_args
        # Positional: (sql, client_id)
        assert call.args[1] == 11139, (
            f"client_id must be passed as param $1, got {call.args[1:]}"
        )


class TestGetReceiptsForPortalClientCascade:
    """Same SCAR, applied to the OSS tanda terima (receipts) cascade."""

    @pytest.mark.asyncio
    async def test_receipts_cascade_keys_on_r_company_id(
        self, mock_pool: MagicMock,
    ) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        await service.get_receipts_for_portal_client(client_id=11139)

        sql = _normalize(_captured_sql(mock_pool._conn))

        assert "r.company_id IN" in sql, (
            f"receipts cascade must filter via r.company_id, got:\n{sql}"
        )
        assert re.search(r"SELECT\s+DISTINCT\s+ccl\.company_id", sql), (
            f"subquery should SELECT DISTINCT ccl.company_id, got:\n{sql}"
        )
        assert "r.client_id IN" not in sql, (
            "regressed: receipts cascade now keys via r.client_id — see "
            "cicatrix-scars.md SCAR: lkpm_service.py\nSQL:\n" + sql
        )
        # The JOIN chain must still reach lkpm_receipts → lkpm_reports.
        assert "lkpm_receipts" in sql and "lkpm_reports" in sql, (
            f"expected join across lkpm_receipts and lkpm_reports, got:\n{sql}"
        )

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rows(
        self, mock_pool: MagicMock,
    ) -> None:
        """With empty DB response, the method returns [] (not None / raise)."""
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        result = await service.get_receipts_for_portal_client(client_id=11139)

        assert result == []


class TestGetReceiptsForReport:
    """Sibling method used by the workspace side — not a cascade, but covered
    so a future refactor doesn't silently change its query shape."""

    @pytest.mark.asyncio
    async def test_filters_by_lkpm_report_id(
        self, mock_pool: MagicMock,
    ) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        await service.get_receipts_for_report(lkpm_report_id=124)

        sql = _normalize(_captured_sql(mock_pool._conn))
        assert "FROM lkpm_receipts" in sql
        assert "lkpm_report_id = $1" in sql
        call = mock_pool._conn.fetch.await_args
        assert call.args[1] == 124


class TestGetHistoryWorkspaceCascade:
    """
    Workspace-side `get_history(client_id)` is consumed by the kita TaxTab via
    `lkpmApi.getClientHistory`. It used to be a plain `WHERE r.client_id = $1`
    — same bug as the portal side. Must now cascade via `r.company_id` so that
    a shareholder's TaxTab shows all of their PT's reports.
    """

    @pytest.mark.asyncio
    async def test_cascade_keys_on_r_company_id(
        self, mock_pool: MagicMock,
    ) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        await service.get_history(client_id=11139)

        sql = _normalize(_captured_sql(mock_pool._conn))
        assert "r.company_id IN" in sql, (
            f"workspace get_history must cascade via r.company_id, got:\n{sql}"
        )
        assert re.search(r"SELECT\s+DISTINCT\s+ccl\.company_id", sql), (
            f"subquery should SELECT DISTINCT ccl.company_id, got:\n{sql}"
        )
        assert "r.client_id = $1" not in sql, (
            "regressed: workspace get_history is back to plain r.client_id filter"
        )


class TestGetReceiptsForClientWorkspace:
    """Workspace TaxTab: `get_receipts_for_client` mirrors the portal cascade."""

    @pytest.mark.asyncio
    async def test_receipts_cascade_keys_on_r_company_id(
        self, mock_pool: MagicMock,
    ) -> None:
        from backend.services.compliance.lkpm_service import LKPMService

        service = LKPMService(db_pool=mock_pool)
        await service.get_receipts_for_client(client_id=11139)

        sql = _normalize(_captured_sql(mock_pool._conn))
        assert "r.company_id IN" in sql
        assert re.search(r"SELECT\s+DISTINCT\s+ccl\.company_id", sql)
        assert "r.client_id IN" not in sql
        assert "lkpm_receipts" in sql and "lkpm_reports" in sql

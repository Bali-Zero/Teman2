"""Guard: the client portal only shows companies through an ACTIVE link.

A client_company_links row stays in the table after the relation ends
(status other than 'active', or end_date set). The portal Matters page
already scopes companies with ``ccl.status = 'active' AND ccl.end_date IS
NULL`` (portal_matters.py); the Companies list, the company detail page,
the dashboard company tile, the co-shareholder list and "set primary"
did not, so an ended or pool link kept showing the company — with its
deeds and the other shareholders' names — to the client.

These tests read the SQL each method sends and require the same active-link
predicate on every client_company_links read the portal makes for a client.
The positive control proves the predicate text this guard looks for is the
one portal_matters.py already uses.
"""

import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal.portal_service import PortalService

ACTIVE_STATUS = re.compile(r"\bstatus\s*=\s*'active'")
OPEN_END = re.compile(r"\bend_date\s+IS\s+NULL", re.IGNORECASE)


class _AsyncCtx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


def _service_with_conn() -> tuple[PortalService, AsyncMock]:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return PortalService(pool), conn


def _ctx(client_id: int = 1) -> dict[str, Any]:
    return {"client_id": client_id, "email": f"client-{client_id}@example.com"}


def _link_sql(mock: AsyncMock) -> list[str]:
    return [
        str(call.args[0])
        for call in mock.await_args_list
        if call.args and "client_company_links" in str(call.args[0])
    ]


def _assert_active_scope(sql: str) -> None:
    assert ACTIVE_STATUS.search(sql), f"missing status = 'active' in:\n{sql}"
    assert OPEN_END.search(sql), f"missing end_date IS NULL in:\n{sql}"


def test_positive_control_portal_matters_uses_the_same_predicate() -> None:
    source = (
        Path(__file__).resolve().parents[5] / "app" / "routers" / "portal_matters.py"
    ).read_text(encoding="utf-8")
    assert ACTIVE_STATUS.search(source)
    assert OPEN_END.search(source)


def test_guilt_case_unscoped_query_is_rejected() -> None:
    with pytest.raises(AssertionError):
        _assert_active_scope("SELECT * FROM client_company_links ccl WHERE ccl.client_id = $1")


@pytest.mark.asyncio
async def test_companies_list_reads_active_links_only() -> None:
    service, conn = _service_with_conn()
    conn.fetch.return_value = []

    assert await service.get_companies(1, current_user=_ctx()) == []

    queries = _link_sql(conn.fetch)
    assert len(queries) == 1
    _assert_active_scope(queries[0])


@pytest.mark.asyncio
async def test_company_detail_ownership_and_shareholders_read_active_links_only() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"role": "director", "is_primary": True, "ownership_percentage": 75},
        {
            "id": 10,
            "company_name": "PT Test",
            "company_type": "PMA",
            "nib": None,
            "npwp_company": None,
            "kbli_code": None,
            "status": "active",
            "registered_address": None,
            "company_email": None,
            "company_phone": None,
            "akta_pendirian_no": None,
            "akta_pendirian_date": None,
            "sk_menhumkam_no": None,
            "custom_fields": None,
        },
    ]
    conn.fetch.side_effect = [[], [], []]

    await service.get_company_detail(1, 10, current_user=_ctx())

    ownership = _link_sql(conn.fetchrow)
    shareholders = _link_sql(conn.fetch)
    assert len(ownership) == 1
    assert len(shareholders) == 1
    _assert_active_scope(ownership[0])
    _assert_active_scope(shareholders[0])


@pytest.mark.asyncio
async def test_company_detail_ended_link_is_not_found() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [None]

    with pytest.raises(ValueError, match="Company not found"):
        await service.get_company_detail(1, 10, current_user=_ctx())


@pytest.mark.asyncio
async def test_dashboard_company_tile_reads_active_links_only() -> None:
    service, conn = _service_with_conn()
    conn.fetchrow.side_effect = [
        {"id": 1, "full_name": "Client One", "email": "client@example.com"},
        RuntimeError("visa table unavailable"),
        RuntimeError("documents table unavailable"),
    ]
    conn.fetch.side_effect = [
        RuntimeError("visa document fallback unavailable"),
        [],
        RuntimeError("practices table unavailable"),
    ]
    conn.fetchval.side_effect = RuntimeError("messages table unavailable")

    await service.get_dashboard(1, current_user=_ctx())

    queries = _link_sql(conn.fetch)
    assert len(queries) == 1
    _assert_active_scope(queries[0])


@pytest.mark.asyncio
async def test_set_primary_targets_an_active_link_only() -> None:
    service, conn = _service_with_conn()
    conn.execute.side_effect = ["UPDATE 1", "UPDATE 1"]

    await service.set_primary_company(1, 10, current_user=_ctx())

    updates = _link_sql(conn.execute)
    assert len(updates) == 2
    _assert_active_scope(updates[1])

"""Pure routing tests for OCR-extracted document subject names.

These lock the handoff between FASE-3 extraction and FASE-4 routing: if OCR
already extracted a subject name, routing must look at the right CRM table for
that document type instead of dropping the document into NO_MATCH.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import routing as rt


class FakeConn:
    """Minimal asyncpg.Connection stand-in with table-specific fuzzy rows."""

    def __init__(
        self,
        *,
        company_npwp_rows: list[dict[str, Any]] | None = None,
        client_fuzzy_rows: list[dict[str, Any]] | None = None,
        company_fuzzy_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.company_npwp_rows = company_npwp_rows or []
        self.client_fuzzy_rows = client_fuzzy_rows or []
        self.company_fuzzy_rows = company_fuzzy_rows or []
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:  # noqa: ARG002
        self.queries.append(query)
        if "npwp_company" in query:
            return self.company_npwp_rows
        if "similarity" in query and "FROM clients" in query:
            return self.client_fuzzy_rows
        if "similarity" in query and "FROM companies" in query:
            return self.company_fuzzy_rows
        return []


class FakePool:
    """Wraps a FakeConn behind the pool.acquire() async-context protocol."""

    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _Ctx:
            async def __aenter__(self) -> FakeConn:
                return conn

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_payment_receipt_uses_payer_name_for_client_destination() -> None:
    conn = FakeConn(
        client_fuzzy_rows=[{"id": 11, "name": "Mario Rossi", "sim": 0.88}]
    )

    out = await rt.resolve_entity(
        {"payer_name": {"value": "Mario Rossi"}},
        "payment_receipt",
        FakePool(conn),
    )

    assert out["decision"] == rt.DECISION_LINK_CANDIDATE
    assert out["subject_kind"] == "person"
    assert out["candidates"][0]["table"] == "clients"
    assert out["candidates"][0]["id"] == 11
    assert any("FROM clients" in query for query in conn.queries)


@pytest.mark.asyncio
async def test_skt_company_taxpayer_name_routes_to_company_destination() -> None:
    conn = FakeConn(
        company_fuzzy_rows=[
            {"id": 22, "name": "PT ZANTARA TEST MANDIRI", "sim": 0.91}
        ]
    )

    out = await rt.resolve_entity(
        {"name": {"value": "PT ZANTARA TEST MANDIRI"}},
        "skt",
        FakePool(conn),
    )

    assert out["decision"] == rt.DECISION_LINK_CANDIDATE
    assert out["subject_kind"] == "company"
    assert out["candidates"][0]["table"] == "companies"
    assert out["candidates"][0]["id"] == 22
    assert any("FROM companies" in query for query in conn.queries)


@pytest.mark.asyncio
async def test_skt_npwp_number_strong_matches_company_destination() -> None:
    conn = FakeConn(
        company_npwp_rows=[{"id": 33, "company_name": "PT ZANTARA TEST MANDIRI"}]
    )

    out = await rt.resolve_entity(
        {"npwp_number": {"value": "09.876.543.2-901.000"}},
        "skt",
        FakePool(conn),
    )

    assert out["decision"] == rt.DECISION_AUTO_ATTACH
    assert out["subject_kind"] == "company"
    assert out["candidates"][0]["table"] == "companies"
    assert out["candidates"][0]["id"] == 33
    assert out["candidates"][0]["method"] == "npwp_company"

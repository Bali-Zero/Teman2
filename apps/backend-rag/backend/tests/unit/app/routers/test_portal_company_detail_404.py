"""
Test for GET /api/portal/company/{company_id} not-found → 404 (not 500).

SCAR CONTEXT (live prod, 2026-07-08): portal_service.get_company_detail raises
`ValueError("Company not found or not accessible")` when the calling client
has no `client_company_links` row for the requested company_id (see
`backend/services/portal/_mixins/dashboard.py::get_company_detail`, guarded by
`@require_client_access`). The router's `get_company_detail` handler caught
that ValueError with the generic `except Exception -> 500`, so a legitimate
not-found surfaced to the client portal as an opaque
"Failed to load company information" 500 instead of a 404. This is the same
class of bug fixed for get_dashboard/get_companies/etc in #2149, but that PR
did not cover this endpoint (W89 class-audit gap, closed here).

Uses a real FastAPI TestClient (not the static AST/regex heuristic in
test_portal_notfound_404.py, which has a real blind spot: its 18-line
lookback window from the `except Exception` line does not reach far enough
back to see `portal_service.get_company_detail(...)` /
`client["client_id"]` in this endpoint's try-body, because ~11 lines of
camelCase remapping logic sit in between — so it silently passed both before
and after this fix).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.portal import get_current_client, get_portal_service, router


def _make_client(portal_service: AsyncMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_client] = lambda: {"client_id": 42}
    app.dependency_overrides[get_portal_service] = lambda: portal_service
    return TestClient(app)


def test_company_detail_not_found_returns_404_not_500() -> None:
    """GUILT: ValueError from the service must surface as 404, not 500."""
    portal_service = AsyncMock()
    portal_service.get_company_detail.side_effect = ValueError(
        "Company not found or not accessible"
    )

    client = _make_client(portal_service)
    resp = client.get("/api/portal/company/1")

    assert resp.status_code == 404, (
        f"expected 404 for not-found company, got {resp.status_code}: {resp.text}"
    )
    assert "not found" in resp.json()["detail"].lower()


def test_company_detail_generic_error_still_returns_500() -> None:
    """INNOCENCE: a genuine internal error must still surface as 500, not be
    masked as a 404 by an overly broad except clause."""
    portal_service = AsyncMock()
    portal_service.get_company_detail.side_effect = RuntimeError("db connection lost")

    client = _make_client(portal_service)
    resp = client.get("/api/portal/company/1")

    assert resp.status_code == 500, (
        f"expected 500 for a genuine internal error, got {resp.status_code}: {resp.text}"
    )


def test_company_detail_success_returns_200_with_mapped_fields() -> None:
    """INNOCENCE: the happy path (data found) still returns 200 with the
    camelCase remap intact — the new except clause must not interfere."""
    portal_service = AsyncMock()
    portal_service.get_company_detail.return_value = {
        "id": 1,
        "name": "PT Example",
        "ownership": {"is_primary": True},
        "akta_no": "123/AKT",
        "akta_date": "2026-01-01",
        "sk_number": "SK-1",
        "tax_office": "KPP Denpasar",
        "company_status": "active",
        "investment_type": "PMA",
        "authorized_capital": 1_000_000_000,
    }

    client = _make_client(portal_service)
    resp = client.get("/api/portal/company/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["isPrimary"] is True
    assert body["data"]["aktaNo"] == "123/AKT"


@pytest.mark.asyncio
async def test_dashboard_still_maps_value_error_to_404_regression_guard() -> None:
    """Sanity check that the sibling get_dashboard pattern this fix mirrors
    is unaffected (no accidental collateral edit to that handler)."""
    from backend.app.dependencies import get_database_pool
    from backend.app.routers.portal import get_portal_service as _gps

    portal_service = AsyncMock()
    portal_service.get_dashboard.side_effect = ValueError("Client 42 not found")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_client] = lambda: {"client_id": 42}
    app.dependency_overrides[_gps] = lambda: portal_service
    app.dependency_overrides[get_database_pool] = lambda: AsyncMock()

    client = TestClient(app)
    resp = client.get("/api/portal/dashboard")
    assert resp.status_code == 404

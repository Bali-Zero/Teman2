"""Integration tests for owner cashout router with auth gating."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.auth import get_current_user
from backend.app.deps.database import get_database_pool
from backend.app.routers.hr_owner_cashout import router


def make_app(user_email: str) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def fake_user():
        return {"email": user_email, "role": "admin"}

    async def fake_pool():
        return AsyncMock()

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_database_pool] = fake_pool
    return app


@pytest.mark.asyncio
async def test_overview_denies_non_owner():
    app = make_app("asya@balizero.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/hr/owner/cashout/overview")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_overview_allows_owner():
    app = make_app("zero@balizero.com")
    fake_result = {
        "total_weeks": 22, "first_week": None, "last_week": None,
        "kpi": {"margin_bz_total_idr": 0, "margin_bz_last_week_idr": 0,
                "margin_bs_total_idr": 0, "practices_total": 0, "practices_last_week": 0},
        "trend": [],
    }
    with patch(
        "backend.services.hr.owner_cashout.repository.get_overview",
        new=AsyncMock(return_value=fake_result),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/hr/owner/cashout/overview")
    assert r.status_code == 200
    assert r.json()["total_weeks"] == 22


@pytest.mark.asyncio
async def test_overview_allows_alias_owner():
    app = make_app("antonellosiano@balizero.com")
    with patch(
        "backend.services.hr.owner_cashout.repository.get_overview",
        new=AsyncMock(return_value={"total_weeks": 0, "first_week": None,
                                    "last_week": None, "kpi": {}, "trend": []}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/hr/owner/cashout/overview")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_weeks_list_gated():
    app = make_app("random@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/hr/owner/cashout/weeks")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_week_detail_404():
    app = make_app("zero@balizero.com")
    with patch(
        "backend.services.hr.owner_cashout.repository.get_week_details",
        new=AsyncMock(return_value=None),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/hr/owner/cashout/weeks/999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_sync_trigger_gated():
    app = make_app("adit@balizero.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/hr/owner/cashout/sync")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_sync_trigger_owner_returns_202():
    app = make_app("zero@balizero.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/hr/owner/cashout/sync")
    assert r.status_code == 202
    assert r.json()["status"] == "started"

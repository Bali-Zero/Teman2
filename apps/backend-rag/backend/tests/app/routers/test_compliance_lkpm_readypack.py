"""
Integration tests for POST /api/v1/lkpm/ready-pack/{client_id}.

3 tests:
  1. Happy path — admin user, dry_run=True → 200.
  2. Incomplete report (missing realization field) → 422.
  3. Team user without assignment → 403.

Auth stubbed via dependency_overrides (no real JWT).
DB uses real Postgres; test data committed + cleaned up in teardown.
LkpmReadyPack.generate is mocked where it lives so the heavy orchestration
(Drive, Brevo, PDF) does not execute during router tests.
"""
from __future__ import annotations

import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.auth import get_current_user
from backend.app.deps.database import get_database_pool
from backend.app.routers.lkpm import router

pytestmark = pytest.mark.integration

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)

# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------


def make_app(user: dict, pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def fake_user() -> dict:
        return user

    async def fake_pool() -> asyncpg.Pool:
        return pool

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_database_pool] = fake_pool
    return app


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def pool() -> AsyncGenerator[asyncpg.Pool, None]:
    try:
        p = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"DB unreachable: {exc}")
    try:
        yield p
    finally:
        await p.close()


async def _ensure_tables(pool: asyncpg.Pool) -> None:
    """Create minimal LKPM tables in the test DB if they don't exist."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lkpm_reports (
                id                          SERIAL PRIMARY KEY,
                client_id                   INT NOT NULL,
                company_id                  INT,
                quarter                     TEXT NOT NULL,
                year                        INT NOT NULL,
                status                      TEXT NOT NULL DEFAULT 'draft',
                lkpm_assigned_to            TEXT,
                realized_equipment_domestic BIGINT DEFAULT 0,
                realized_equipment_import   BIGINT DEFAULT 0,
                realized_building_domestic  BIGINT DEFAULT 0,
                realized_building_import    BIGINT DEFAULT 0,
                realized_vehicle_domestic   BIGINT DEFAULT 0,
                realized_vehicle_import     BIGINT DEFAULT 0,
                realized_land               BIGINT DEFAULT 0,
                realized_working_capital    BIGINT DEFAULT 0,
                realized_other              BIGINT DEFAULT 0,
                oss_submitted               BOOLEAN NOT NULL DEFAULT FALSE,
                oss_receipt_number          TEXT,
                client_approved             BOOLEAN NOT NULL DEFAULT FALSE,
                validation_status           TEXT DEFAULT 'pending',
                validation_alerts           JSONB DEFAULT '[]',
                updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lkpm_receipts (
                id                  SERIAL PRIMARY KEY,
                lkpm_report_id      INT NOT NULL,
                kbli_code           TEXT,
                kegiatan_usaha_desc TEXT,
                oss_status          TEXT,
                stage               TEXT
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lkpm_client_config (
                id           SERIAL PRIMARY KEY,
                client_id    INT NOT NULL,
                company_id   INT,
                company_name TEXT,
                nib          TEXT,
                npwp         TEXT,
                kbli_codes   TEXT[] DEFAULT '{}',
                oss_username TEXT,
                oss_password TEXT,
                oss_creds_updated_at TIMESTAMPTZ,
                oss_creds_updated_by TEXT
            )
            """
        )


_cleanup_clients: list[int] = []
_cleanup_reports: list[int] = []


@pytest_asyncio.fixture(autouse=True)
async def setup_and_teardown(pool: asyncpg.Pool) -> AsyncGenerator[None, None]:
    _cleanup_clients.clear()
    _cleanup_reports.clear()
    await _ensure_tables(pool)
    yield
    async with pool.acquire() as conn:
        if _cleanup_reports:
            await conn.execute(
                "DELETE FROM lkpm_receipts WHERE lkpm_report_id = ANY($1::int[])",
                _cleanup_reports,
            )
            await conn.execute(
                "DELETE FROM lkpm_reports WHERE id = ANY($1::int[])",
                _cleanup_reports,
            )
        if _cleanup_clients:
            await conn.execute(
                "DELETE FROM clients WHERE id = ANY($1::int[])",
                _cleanup_clients,
            )


async def _insert_client(pool: asyncpg.Pool) -> int:
    email = f"rp-router-{uuid4().hex[:10]}@example.com"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clients (full_name, email, google_drive_folder_id, created_at, updated_at)
            VALUES ('RP Router Test', $1, 'drive_folder_rp', NOW(), NOW())
            RETURNING id
            """,
            email,
        )
    cid = int(row["id"])
    _cleanup_clients.append(cid)
    return cid


async def _insert_report(
    pool: asyncpg.Pool,
    client_id: int,
    quarter: str,
    year: int,
    assigned_to: str | None,
    complete: bool = True,
) -> int:
    equipment_val = "100000000" if complete else "NULL"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            INSERT INTO lkpm_reports (
                client_id, quarter, year, status, lkpm_assigned_to,
                realized_equipment_domestic, realized_equipment_import,
                realized_building_domestic, realized_building_import,
                realized_vehicle_domestic, realized_vehicle_import,
                realized_land, realized_working_capital, realized_other,
                oss_submitted
            ) VALUES (
                $1, $2, $3, 'draft', $4,
                {equipment_val}, 0, 0, 0, 0, 0, 0, 0, 0,
                FALSE
            ) RETURNING id
            """,
            client_id,
            quarter,
            year,
            assigned_to,
        )
    rid = int(row["id"])
    _cleanup_reports.append(rid)
    return rid


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_admin_dry_run(pool: asyncpg.Pool) -> None:
    """Admin + complete report + dry_run=True → 200 with hashes."""
    client_id = await _insert_client(pool)
    await _insert_report(pool, client_id, "Q1", 2026, assigned_to=None, complete=True)

    admin_user = {"email": "zero@balizero.com", "role": "admin", "is_admin": True}
    app = make_app(admin_user, pool)

    mock_result = {
        "drive_url": None,
        "pdf_sha256": "a" * 64,
        "xlsx_sha256": "b" * 64,
        "email_sent_to": None,
        "validation_warnings": [],
    }

    # Patch the module where LkpmReadyPack is defined (lazy-imported in router)
    with patch(
        "backend.services.compliance.lkpm_ready_pack.LkpmReadyPack",
        autospec=False,
    ) as MockClass:
        instance = MagicMock()
        instance.generate = AsyncMock(return_value=mock_result)
        MockClass.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            resp = await http.post(
                f"/api/v1/lkpm/ready-pack/{client_id}",
                json={"period": "Q1 2026", "send_email": False, "dry_run": True},
            )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["pdf_sha256"] == "a" * 64
    assert body["drive_url"] is None


@pytest.mark.asyncio
async def test_incomplete_report_returns_422(pool: asyncpg.Pool) -> None:
    """LkpmValidationError from generate() → 422."""
    client_id = await _insert_client(pool)

    admin_user = {"email": "zero@balizero.com", "role": "admin", "is_admin": True}
    app = make_app(admin_user, pool)

    from backend.services.compliance.exceptions import LkpmValidationError

    # Mock generate() to raise LkpmValidationError (avoids DB lock in teardown)
    with patch(
        "backend.services.compliance.lkpm_ready_pack.LkpmReadyPack",
        autospec=False,
    ) as MockClass:
        instance = MagicMock()
        instance.generate = AsyncMock(
            side_effect=LkpmValidationError(
                "LKPM report is incomplete. Missing: ['realized_equipment_domestic']"
            )
        )
        MockClass.return_value = instance

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            resp = await http.post(
                f"/api/v1/lkpm/ready-pack/{client_id}",
                json={"period": "Q2 2026", "send_email": False, "dry_run": False},
            )

    assert resp.status_code == 422, resp.text
    detail = resp.json().get("detail", "").lower()
    assert "incomplete" in detail or "missing" in detail


@pytest.mark.asyncio
async def test_team_user_not_assigned_gets_403(pool: asyncpg.Pool) -> None:
    """Team user whose email != lkpm_assigned_to → 403."""
    client_id = await _insert_client(pool)
    await _insert_report(
        pool,
        client_id,
        "Q1",
        2026,
        assigned_to="veronika.tax@balizero.com",
        complete=True,
    )

    team_user = {"email": "kadek.tax@balizero.com", "role": "team", "is_admin": False}
    app = make_app(team_user, pool)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        resp = await http.post(
            f"/api/v1/lkpm/ready-pack/{client_id}",
            json={"period": "Q1 2026", "send_email": False, "dry_run": True},
        )

    assert resp.status_code == 403, resp.text

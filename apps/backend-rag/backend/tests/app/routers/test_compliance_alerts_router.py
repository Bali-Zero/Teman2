"""
Integration tests for /api/compliance/alerts router.

POST /{id}/outcome   — record acted/dismissed
GET  /               — list (RBAC scoped)
GET  /{id}           — detail + outcomes + deliveries
GET  /metrics        — admin-only precision/recall/F1
POST /retrain        — admin-only autotune trigger

Auth is stubbed via dependency_overrides so no real JWT is needed.
DB uses real Postgres; test data is committed then cleaned up in teardown
because the router endpoints use pool.acquire() (a different connection)
and cannot see uncommitted data from a test transaction.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import AsyncGenerator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.auth import get_current_user
from backend.app.deps.database import get_database_pool
from backend.app.routers.compliance_alerts import router

pytestmark = pytest.mark.integration

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)


# ── App factory ──────────────────────────────────────────────────────────


def make_app(user: dict, pool: asyncpg.Pool) -> FastAPI:
    """Build a minimal FastAPI app with stubbed auth and real DB pool."""
    app = FastAPI()
    app.include_router(router)

    async def fake_user():
        return user

    async def fake_pool():
        return pool

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_database_pool] = fake_pool
    return app


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    # Skip cleanly when the test DB is unreachable or lacks the schema this
    # suite needs (e.g. CI's empty postgres:15 service has no `clients` or
    # `compliance_alerts` table — these tests assume a migrated DB).
    try:
        pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"DB unreachable: {exc}")
        return  # help static analyzers see pool is unbound on this path

    skip_reason: str | None = None
    try:
        async with pool.acquire() as conn:
            for table in ("clients", "compliance_alerts"):
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    skip_reason = f"required table '{table}' missing in test DB"
                    break
        if skip_reason is None:
            yield pool
    finally:
        await pool.close()
    if skip_reason:
        pytest.skip(skip_reason)


@pytest_asyncio.fixture
async def db_tx(db_pool: asyncpg.Pool) -> AsyncGenerator[asyncpg.Connection, None]:
    """Per-test transaction rolled back at teardown (for system_settings changes)."""
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
        finally:
            await tx.rollback()


async def _insert_client(pool: asyncpg.Pool, email: str, assigned_to: str | None = None) -> dict:
    """Insert a client row with real commit (visible across connections)."""
    async with pool.acquire() as conn:
        if assigned_to is not None:
            row = await conn.fetchrow(
                "INSERT INTO clients (full_name, email, assigned_to, created_at, updated_at) VALUES ($1,$2,$3,NOW(),NOW()) RETURNING id, full_name, email, assigned_to",
                "Router Test Client",
                email,
                assigned_to,
            )
        else:
            row = await conn.fetchrow(
                "INSERT INTO clients (full_name, email, created_at, updated_at) VALUES ($1,$2,NOW(),NOW()) RETURNING id, full_name, email",
                "Router Test Client",
                email,
            )
    return dict(row)


async def _delete_client(pool: asyncpg.Pool, client_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM compliance_alerts WHERE client_id = $1", client_id
        )
        await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


async def _insert_alert(pool: asyncpg.Pool, client_id: int, category: str = "visa_expiry") -> dict:
    """Insert a compliance_alerts row with real commit."""
    aid = f"t_{uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO compliance_alerts (
              alert_id, client_id, category, severity, status,
              deadline, days_until, dedup_key
            ) VALUES ($1,$2,$3,'urgent','pending',$4,7,$5)
            """,
            aid,
            client_id,
            category,
            date.today() + timedelta(days=7),
            f"{category}:{client_id}:{aid}",
        )
    return {"alert_id": aid, "client_id": client_id, "category": category}


async def _delete_alert(pool: asyncpg.Pool, alert_id: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM alert_outcomes WHERE alert_id = $1", alert_id
        )
        await conn.execute(
            "DELETE FROM compliance_alerts WHERE alert_id = $1", alert_id
        )


# Admin + team user dicts
_ADMIN_USER: dict = {"email": "zero@balizero.com", "role": "admin"}
_TEAM_USER: dict = {"email": "team@balizero.com", "role": "user"}


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_outcome_creates_row(db_pool: asyncpg.Pool) -> None:
    """Admin posts 'acted' outcome → 200 and correct response shape."""
    email = f"ro-{uuid4().hex[:8]}@example.com"
    client = await _insert_client(db_pool, email)
    alert = await _insert_alert(db_pool, client["id"])
    try:
        app = make_app(_ADMIN_USER, db_pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/compliance/alerts/{alert['alert_id']}/outcome",
                json={"outcome": "acted", "note": "renewed KITAS"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["outcome"] == "acted"
        assert body["alert_id"] == alert["alert_id"]
    finally:
        await _delete_alert(db_pool, alert["alert_id"])
        await _delete_client(db_pool, client["id"])


@pytest.mark.asyncio
async def test_post_outcome_rejects_invalid_outcome(db_pool: asyncpg.Pool) -> None:
    """Invalid outcome value → 422 Unprocessable Entity."""
    email = f"ro-{uuid4().hex[:8]}@example.com"
    client = await _insert_client(db_pool, email)
    alert = await _insert_alert(db_pool, client["id"])
    try:
        app = make_app(_ADMIN_USER, db_pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                f"/api/compliance/alerts/{alert['alert_id']}/outcome",
                json={"outcome": "maybe"},
            )
        assert r.status_code == 422
    finally:
        await _delete_alert(db_pool, alert["alert_id"])
        await _delete_client(db_pool, client["id"])


@pytest.mark.asyncio
async def test_get_alerts_rbac_team_sees_own(db_pool: asyncpg.Pool) -> None:
    """Team member sees alerts for their assigned clients."""
    email = f"team-cli-{uuid4().hex[:8]}@example.com"
    client = await _insert_client(db_pool, email, assigned_to="team@balizero.com")
    alert = await _insert_alert(db_pool, client["id"])
    try:
        app = make_app(_TEAM_USER, db_pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/api/compliance/alerts")
        assert r.status_code == 200, r.text
        alert_ids = {a["alert_id"] for a in r.json()["items"]}
        assert alert["alert_id"] in alert_ids
    finally:
        await _delete_alert(db_pool, alert["alert_id"])
        await _delete_client(db_pool, client["id"])


@pytest.mark.asyncio
async def test_get_alerts_team_blocked_for_others_clients(db_pool: asyncpg.Pool) -> None:
    """Team member does NOT see alerts for another team member's clients."""
    email = f"other-cli-{uuid4().hex[:8]}@example.com"
    client = await _insert_client(db_pool, email, assigned_to="other@balizero.com")
    alert = await _insert_alert(db_pool, client["id"])
    try:
        app = make_app(_TEAM_USER, db_pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/api/compliance/alerts")
        assert r.status_code == 200, r.text
        alert_ids = {a["alert_id"] for a in r.json()["items"]}
        assert alert["alert_id"] not in alert_ids
    finally:
        await _delete_alert(db_pool, alert["alert_id"])
        await _delete_client(db_pool, client["id"])


@pytest.mark.asyncio
async def test_metrics_admin_only(db_pool: asyncpg.Pool) -> None:
    """Team member gets 403 on /metrics."""
    app = make_app(_TEAM_USER, db_pool)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/compliance/alerts/metrics")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_metrics_admin_returns_shape(db_pool: asyncpg.Pool) -> None:
    """Admin gets 200 with by_category and overall keys."""
    app = make_app(_ADMIN_USER, db_pool)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/compliance/alerts/metrics")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "by_category" in body
    assert "overall" in body


@pytest.mark.asyncio
async def test_retrain_gated_by_autotune_flag(db_pool: asyncpg.Pool) -> None:
    """POST /retrain returns autotune_disabled when kill-switch is off."""
    # Ensure autotune is disabled (default state in fresh envs)
    async with db_pool.acquire() as conn:
        original = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key='compliance_alert_autotune_enabled'",
        )
        await conn.execute(
            "INSERT INTO system_settings (key, value) VALUES "
            "('compliance_alert_autotune_enabled','false') "
            "ON CONFLICT (key) DO UPDATE SET value='false'",
        )
    try:
        app = make_app(_ADMIN_USER, db_pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.post(
                "/api/compliance/alerts/retrain",
                json={"dry_run": False},
            )
        assert r.status_code == 200, r.text
        assert r.json()["reason"] == "autotune_disabled"
    finally:
        # Restore original value or delete if it wasn't set
        async with db_pool.acquire() as conn:
            if original is not None:
                await conn.execute(
                    "UPDATE system_settings SET value=$1 WHERE key='compliance_alert_autotune_enabled'",
                    original,
                )
            else:
                await conn.execute(
                    "DELETE FROM system_settings WHERE key='compliance_alert_autotune_enabled'",
                )


@pytest.mark.asyncio
async def test_team_blocked_on_null_assigned_client(db_pool: asyncpg.Pool) -> None:
    """Team member is denied GET /{id} and POST /{id}/outcome for unassigned (NULL) clients."""
    # Insert a client with assigned_to = NULL (no owner)
    async with db_pool.acquire() as conn:
        client_id = await conn.fetchval(
            "INSERT INTO clients (full_name, email, created_at, updated_at) VALUES ($1, $2, NOW(), NOW()) RETURNING id",
            "Unassigned Client",
            f"null-{uuid4().hex[:6]}@example.com",
        )
        alert_id = f"a_null_{uuid4().hex[:6]}"
        await conn.execute(
            "INSERT INTO compliance_alerts "
            "(alert_id, client_id, category, severity, status, deadline, "
            " days_until, dedup_key) "
            "VALUES ($1, $2, 'visa_expiry', 'urgent', 'pending', $3, 7, $4)",
            alert_id,
            client_id,
            date.today() + timedelta(days=7),
            f"visa:{client_id}:{alert_id}",
        )
    try:
        app = make_app(_TEAM_USER, db_pool)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # GET detail → 403 (NULL assigned_to must be denied)
            r1 = await ac.get(f"/api/compliance/alerts/{alert_id}")
            assert r1.status_code == 403, f"Expected 403 on GET, got {r1.status_code}: {r1.text}"

            # POST outcome → 403
            r2 = await ac.post(
                f"/api/compliance/alerts/{alert_id}/outcome",
                json={"outcome": "acted"},
            )
            assert r2.status_code == 403, f"Expected 403 on POST outcome, got {r2.status_code}: {r2.text}"
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM compliance_alerts WHERE alert_id = $1", alert_id
            )
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

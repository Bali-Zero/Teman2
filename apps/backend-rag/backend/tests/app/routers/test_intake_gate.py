"""Integration tests for the INTAKE login gate (Anello 7).

Covers:
- gate_evaluator.evaluate_gate_status (the F4 shared evaluator)
- GET  /api/intake/gate/status                 (#7 probe)
- POST /api/hr/my-late-incident/resolve        (#9 authenticated late resolve)
- POST /api/compliance/alerts/{id}/outcome     (#10 acknowledged outcome)
- require_gate_cleared dependency               (#10 423 lock + F1 allowlist)

Auth is stubbed via dependency_overrides; DB is real Postgres (nuzantara_dev on
the Pro). Test rows are committed then cleaned in teardown (endpoints use a
separate pool connection and cannot see an uncommitted tx). NOT M5-skippable in
spirit — runs fully only where the migrated schema + gate tables exist; skips
cleanly on a partial/unreachable DB (the same discipline that caught 4 real bugs
in #1145).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.auth import get_current_user
from backend.app.deps.database import get_database_pool
from backend.app.deps.gate import require_gate_cleared
from backend.app.routers.compliance_alerts import router as compliance_router
from backend.app.routers.hr_my_late_incident import router as hr_router
from backend.app.routers.intake_gate import router as gate_router
from backend.services.intake.gate_evaluator import evaluate_gate_status

pytestmark = pytest.mark.integration

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)

_REQUIRED_TABLES = (
    "clients",
    "compliance_alerts",
    "alert_outcomes",
    "attendance_late_incidents",
    "intake_queue",
    "document_routing_proposal",
)


# ── App factory ──────────────────────────────────────────────────────────


def make_app(user: dict, pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI()
    app.include_router(gate_router)
    app.include_router(hr_router)
    app.include_router(compliance_router)

    # A guarded business endpoint to exercise require_gate_cleared (#10).
    @app.post("/api/clients/_test_guarded", dependencies=[Depends(require_gate_cleared)])
    async def _guarded() -> dict[str, Any]:
        return {"ok": True}

    async def fake_user():
        return user

    async def fake_pool():
        return pool

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_database_pool] = fake_pool
    return app


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def pool() -> AsyncGenerator[asyncpg.Pool, None]:
    try:
        p = await asyncpg.create_pool(_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"DB unreachable: {exc}")
        return

    skip_reason: str | None = None
    try:
        async with p.acquire() as conn:
            for table in _REQUIRED_TABLES:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    skip_reason = f"required table '{table}' missing in test DB"
                    break
            # intake_queue.received_by is the by-receiver column (migration 218).
            if skip_reason is None:
                has_recv = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='intake_queue' AND column_name='received_by')"
                )
                if not has_recv:
                    skip_reason = "intake_queue.received_by missing (migration 218)"
        if skip_reason is None:
            yield p
    finally:
        await p.close()
    if skip_reason:
        pytest.skip(skip_reason)


# ── Row helpers (commit-visible, tracked for cleanup) ──────────────────────


async def _mk_late(pool: asyncpg.Pool, email: str, state: str, days_ago: int = 0) -> str:
    """Insert a pending late incident; return its id (str)."""
    rid = str(uuid.uuid4())
    async with pool.acquire() as conn:
        # checkin_time is NOT NULL on attendance_late_incidents — supply it.
        await conn.execute(
            """
            INSERT INTO attendance_late_incidents
                (id, email, full_name, late_date, checkin_time, state, reply_token,
                 created_at, updated_at)
            VALUES ($1, $2, 'Gate Test', CURRENT_DATE - ($3 || ' days')::interval,
                    NOW(), $4, $5, NOW(), NOW())
            """,
            rid,
            email,
            str(days_ago),
            state,
            str(uuid.uuid4()),
        )
    return rid


async def _cleanup_late(pool: asyncpg.Pool, ids: list[str]) -> None:
    if not ids:
        return
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM attendance_late_incidents WHERE id = ANY($1::uuid[])", ids)


async def _mk_deadline(
    pool: asyncpg.Pool,
    email: str,
    status: str,
) -> tuple[int, str]:
    """Insert an assigned client plus one gate-blocking compliance alert."""
    alert_id = f"gate_{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        async with conn.transaction():
            client_id = await conn.fetchval(
                """
                INSERT INTO clients
                    (full_name, email, assigned_to, created_at, updated_at)
                VALUES ('Gate Deadline Client', $1, $2, NOW(), NOW())
                RETURNING id
                """,
                f"client-{uuid.uuid4().hex[:8]}@example.com",
                email,
            )
            await conn.execute(
                """
                INSERT INTO compliance_alerts
                    (alert_id, client_id, category, severity, status, deadline,
                     days_until, dedup_key)
                VALUES ($1, $2, 'visa_expiry', 'urgent', $3, $4, 3, $5)
                """,
                alert_id,
                client_id,
                status,
                date.today() + timedelta(days=3),
                f"gate-test:{client_id}:{alert_id}",
            )
    return int(client_id), alert_id


async def _cleanup_deadline(
    pool: asyncpg.Pool,
    client_id: int,
    alert_id: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM alert_outcomes WHERE alert_id = $1", alert_id)
        await conn.execute("DELETE FROM compliance_alerts WHERE alert_id = $1", alert_id)
        await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


# ── Evaluator: empty-state = not blocked ───────────────────────────────────


@pytest.mark.asyncio
async def test_evaluator_clear_user_not_blocked(pool):
    # A user with no docs/late/deadlines anywhere → blocked False.
    email = f"clear-{uuid.uuid4().hex[:8]}@balizero.com"
    result = await evaluate_gate_status(pool, user_email=email, is_admin=False)
    assert result["blocked"] is False
    assert result["degraded"] is False
    assert result["sections"]["late_note"]["count"] == 0


# ── Gate 2 (late) blocks; ALL dates (F2) ───────────────────────────────────


@pytest.mark.asyncio
async def test_late_incident_any_date_blocks(pool):
    email = f"late-{uuid.uuid4().hex[:8]}@balizero.com"
    ids: list[str] = []
    try:
        # An incident from 3 days ago (NOT today) must still block (F2).
        ids.append(await _mk_late(pool, email, "AWAITING_REPLY", days_ago=3))
        result = await evaluate_gate_status(pool, user_email=email, is_admin=False)
        assert result["blocked"] is True
        assert result["sections"]["late_note"]["count"] == 1
    finally:
        await _cleanup_late(pool, ids)


# ── #7 probe endpoint ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gate_status_endpoint_reflects_blocked(pool):
    email = f"probe-{uuid.uuid4().hex[:8]}@balizero.com"
    ids: list[str] = []
    try:
        ids.append(await _mk_late(pool, email, "REMINDER_SENT", days_ago=1))
        app = make_app({"email": email, "role": "member"}, pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            r = await ac.get("/api/intake/gate/status")
        assert r.status_code == 200
        body = r.json()
        assert body["blocked"] is True
        assert body["sections"]["late_note"]["count"] == 1
        assert "as_of" in body
    finally:
        await _cleanup_late(pool, ids)


# ── #9 authenticated late-incident resolve ─────────────────────────────────


@pytest.mark.asyncio
async def test_my_late_incident_resolve_transitions_and_clears(pool):
    email = f"resolve-{uuid.uuid4().hex[:8]}@balizero.com"
    ids: list[str] = []
    try:
        ids.append(await _mk_late(pool, email, "AWAITING_REPLY", days_ago=2))
        app = make_app({"email": email, "role": "member"}, pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            r = await ac.post(
                "/api/hr/my-late-incident/resolve",
                json={"reason": "macet parah di Bypass"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["state"] == "RESOLVED"  # AWAITING_REPLY → RESOLVED

            # Idempotent: nothing pending now → clear.
            r2 = await ac.post("/api/hr/my-late-incident/resolve", json={"reason": "again"})
            assert r2.status_code == 200
            assert r2.json()["state"] == "clear"

        # Gate now clear for this user.
        result = await evaluate_gate_status(pool, user_email=email, is_admin=False)
        assert result["sections"]["late_note"]["count"] == 0
    finally:
        await _cleanup_late(pool, ids)


@pytest.mark.asyncio
async def test_my_late_incident_reminder_sent_goes_resolved_late(pool):
    email = f"late2-{uuid.uuid4().hex[:8]}@balizero.com"
    ids: list[str] = []
    try:
        ids.append(await _mk_late(pool, email, "REMINDER_SENT", days_ago=1))
        app = make_app({"email": email, "role": "member"}, pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            r = await ac.post("/api/hr/my-late-incident/resolve", json={"reason": "ban kempes"})
        assert r.status_code == 200
        assert r.json()["state"] == "RESOLVED_LATE"  # REMINDER_SENT → RESOLVED_LATE
    finally:
        await _cleanup_late(pool, ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_status", ["pending", "sent"])
async def test_acknowledged_deadline_clears_gate(pool, initial_status):
    """A pending or sent alert clears only after its persisted acknowledgement."""
    email = f"deadline-{uuid.uuid4().hex[:8]}@balizero.com"
    client_id, alert_id = await _mk_deadline(pool, email, initial_status)
    try:
        before = await evaluate_gate_status(
            pool,
            user_email=email,
            is_admin=False,
        )
        assert before["blocked"] is True
        assert before["sections"]["deadlines"]["count"] == 1

        app = make_app({"email": email, "role": "member"}, pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            response = await ac.post(
                f"/api/compliance/alerts/{alert_id}/outcome",
                json={"outcome": "acknowledged"},
            )

        assert response.status_code == 200, response.text
        assert response.json() == {
            "alert_id": alert_id,
            "outcome": "acknowledged",
            "status": "acknowledged",
        }

        after = await evaluate_gate_status(
            pool,
            user_email=email,
            is_admin=False,
        )
        assert after["sections"]["deadlines"]["count"] == 0
        assert after["blocked"] is False
    finally:
        await _cleanup_deadline(pool, client_id, alert_id)


# ── #10 require_gate_cleared dependency ─────────────────────────────────────


@pytest.mark.asyncio
async def test_guarded_endpoint_423_when_blocked(pool):
    email = f"guard-{uuid.uuid4().hex[:8]}@balizero.com"
    ids: list[str] = []
    try:
        ids.append(await _mk_late(pool, email, "AWAITING_REPLY", days_ago=0))
        app = make_app({"email": email, "role": "member"}, pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            r = await ac.post("/api/clients/_test_guarded")
        assert r.status_code == 423
        assert r.json()["detail"]["error"] == "gate_blocked"
    finally:
        await _cleanup_late(pool, ids)


@pytest.mark.asyncio
async def test_guarded_endpoint_passes_when_clear(pool):
    email = f"guard2-{uuid.uuid4().hex[:8]}@balizero.com"
    app = make_app({"email": email, "role": "member"}, pool)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/api/clients/_test_guarded")
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_clearing_endpoint_not_gated_even_when_blocked(pool):
    """F1: the late-resolve endpoint must work WHILE the user is blocked."""
    email = f"f1-{uuid.uuid4().hex[:8]}@balizero.com"
    ids: list[str] = []
    try:
        ids.append(await _mk_late(pool, email, "AWAITING_REPLY", days_ago=0))
        app = make_app({"email": email, "role": "member"}, pool)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            # Even though blocked, the clearing endpoint resolves (not 423).
            r = await ac.post("/api/hr/my-late-incident/resolve", json={"reason": "clearing"})
        assert r.status_code == 200
        assert r.json()["state"] == "RESOLVED"
    finally:
        await _cleanup_late(pool, ids)

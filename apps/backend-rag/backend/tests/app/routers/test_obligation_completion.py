"""Completion contract, including real PostgreSQL locking and rollback.

TEST_DATABASE_URL must name a test database (including xdist workers). Each test owns an
isolated schema; no production or pre-existing client tables are touched.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers import compliance_alerts, compliance_obligations
from backend.services.compliance.obligations_repository import ObligationsRepository

ADMIN = {"email": "ZeRo@balizero.com", "role": "admin"}
BODY = {"evidence_ref": "  internal-document:test-receipt  ", "declaration": True}
URL = "/api/compliance/obligations/1/complete"


def is_test_database(name: str) -> bool:
    """Accept the suite base, pre-push clones and their xdist workers only."""
    return re.search(r"_test(?:_run_[0-9]+_[0-9]+)?(?:_gw[0-9]+)?$", name) is not None


@pytest.mark.parametrize(
    ("name", "allowed"),
    [
        ("nuzantara_test", True),
        ("nuzantara_test_gw0", True),
        ("nuzantara_test_run_123_456", True),
        ("nuzantara_test_run_123_456_gw1", True),
        ("nuzantara_dev", False),
        ("nuzantara", False),
        ("nuzantara_test_production", False),
        ("nuzantara_test_run_123", False),
        ("nuzantara_test_gw0_extra", False),
    ],
)
def test_database_guard_covers_repository_test_names(name, allowed):
    assert is_test_database(name) is allowed


def client(pool=None, user=None):
    app = FastAPI()
    app.include_router(compliance_obligations.router)
    app.include_router(compliance_alerts.router)
    app.dependency_overrides[get_current_user] = lambda: ADMIN if user is None else user
    app.dependency_overrides[get_database_pool] = lambda: pool
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    )


@pytest_asyncio.fixture
async def db():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL required for PostgreSQL completion proof")
    conn = await asyncpg.connect(dsn)
    name = await conn.fetchval("SELECT current_database()")
    if not is_test_database(name):
        await conn.close()
        pytest.fail("Completion tests require a test database, pre-push clone or xdist worker")
    schema = "ros_completion_" + uuid4().hex
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, server_settings={"search_path": schema}
    )
    try:
        async with pool.acquire() as c:
            await c.execute("""
                CREATE TABLE clients (id integer PRIMARY KEY, assigned_to text);
                CREATE TABLE compliance_alerts (
                    alert_id text PRIMARY KEY, client_id integer REFERENCES clients(id),
                    category text, severity text DEFAULT 'warning', status text DEFAULT 'pending',
                    deadline date DEFAULT CURRENT_DATE, days_until integer DEFAULT 0,
                    dedup_key text, resolved_at timestamptz, acknowledged_at timestamptz);
                CREATE UNIQUE INDEX active_dedup ON compliance_alerts (dedup_key)
                    WHERE status IN ('pending','sent','acknowledged');
                CREATE TABLE client_obligations (
                    id integer PRIMARY KEY, client_id integer REFERENCES clients(id), rule_id text,
                    period_key text, due_date date DEFAULT CURRENT_DATE, status text,
                    needs_review_reason text, reviewer_email text, reviewed_at timestamptz,
                    review_note text, alert_id text, created_at timestamptz DEFAULT NOW(),
                    updated_at timestamptz DEFAULT NOW(),
                    CONSTRAINT ck_client_obligations_status
                        CHECK (status IN ('proposed','approved','rejected','alerted','done')));
                CREATE TABLE alert_outcomes (
                    outcome_id bigserial PRIMARY KEY, alert_id text REFERENCES compliance_alerts(alert_id),
                    outcome text, actioned_by text, actioned_at timestamptz DEFAULT NOW(),
                    note text, metadata jsonb DEFAULT '{}',
                    CONSTRAINT ck_alert_outcomes_outcome
                        CHECK (outcome IN ('dismissed','acted','expired','acknowledged')));
                INSERT INTO clients VALUES (1,'member@example.test'),(2,'other@example.test');
                INSERT INTO compliance_alerts (alert_id,client_id,category,dedup_key)
                    VALUES ('alert-test',1,'obligation','obligation:1:test-rule:test-period');
                INSERT INTO client_obligations
                    (id,client_id,rule_id,period_key,status,alert_id,reviewer_email,review_note)
                    VALUES (1,1,'test-rule','test-period','alerted','alert-test',
                            'approver@example.test','original approval');
            """)
        yield pool
    finally:
        await pool.close()
        await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await conn.close()


async def state(db):
    async with db.acquire() as conn:
        return (
            await conn.fetchval("SELECT status FROM client_obligations WHERE id=1"),
            await conn.fetchval("SELECT status FROM compliance_alerts WHERE alert_id='alert-test'"),
            await conn.fetchval("SELECT COUNT(*) FROM alert_outcomes"),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("user", [{"email": "member@example.test"}, {"role": "admin"}])
async def test_admin_and_actor_required_before_database_access(user):
    async with client(user=user) as c:
        assert (await c.post(URL, json=BODY)).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "evidence_ref": ""},
        {**BODY, "evidence_ref": "   "},
        {**BODY, "evidence_ref": "x" * 501},
        {"evidence_ref": "test"},
        {**BODY, "declaration": False},
        {**BODY, "declaration": 1},
        {**BODY, "declaration": "true"},
    ],
)
async def test_invalid_declaration_or_reference_never_reaches_database(body):
    async with client() as c:
        assert (await c.post(URL, json=body)).status_code == 422


@pytest.mark.asyncio
async def test_completion_preserves_approval_and_records_exact_audit(db):
    async with client(db) as c:
        response = await c.post(URL, json=BODY)
        assert response.status_code == 200, response.text
        assert response.json()["obligation"]["status"] == "done"
        assert (await c.post(URL, json=BODY)).status_code == 409
    assert await state(db) == ("done", "resolved", 1)
    async with db.acquire() as conn:
        outcome = await conn.fetchrow("SELECT * FROM alert_outcomes")
        assert outcome["note"] == BODY["evidence_ref"].strip()
        assert outcome["actioned_by"] == "zero@balizero.com"
        assert outcome["actioned_at"] is not None
        assert json.loads(outcome["metadata"]) == {
            "kind": "obligation_completed",
            "obligation_id": 1,
        }
        original = await conn.fetchrow("SELECT reviewer_email,review_note FROM client_obligations")
        assert tuple(original.values()) == ("approver@example.test", "original approval")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["proposed", "approved", "rejected", "done"])
async def test_only_alerted_obligations_can_complete(db, status):
    async with db.acquire() as conn:
        await conn.execute("UPDATE client_obligations SET status=$1", status)
    async with client(db) as c:
        assert (await c.post(URL, json=BODY)).status_code == 409
        assert (await c.post(URL.replace("/1/", "/999/"), json=BODY)).status_code == 404
    assert await state(db) == (status, "pending", 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "UPDATE compliance_alerts SET client_id=2",
        "UPDATE compliance_alerts SET category='visa'",
        "UPDATE compliance_alerts SET dedup_key='unrelated'",
        "UPDATE client_obligations SET alert_id='missing'",
        "UPDATE client_obligations SET alert_id=NULL",
    ],
)
async def test_link_must_identify_this_obligation(db, change):
    async with db.acquire() as conn:
        await conn.execute(change)
    async with client(db) as c:
        assert (await c.post(URL, json=BODY)).status_code == 409
    assert await state(db) == ("alerted", "pending", 0)


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_both_state_changes(db):
    async with db.acquire() as conn:
        await conn.execute("ALTER TABLE alert_outcomes ADD CHECK (note <> 'fail-write')")
    async with client(db) as c:
        assert (await c.post(URL, json={**BODY, "evidence_ref": "fail-write"})).status_code == 500
    assert await state(db) == ("alerted", "pending", 0)


@pytest.mark.asyncio
async def test_concurrent_completions_append_one_outcome(db):
    async with client(db) as c:
        results = await asyncio.wait_for(
            asyncio.gather(c.post(URL, json=BODY), c.post(URL, json=BODY)), 5
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert await state(db) == ("done", "resolved", 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["acted", "dismissed", "acknowledged"])
async def test_generic_outcome_does_not_complete_and_cannot_reopen(db, outcome):
    async with client(db) as c:
        url = "/api/compliance/alerts/alert-test/outcome"
        assert (await c.post(url, json={"outcome": outcome})).status_code == 200
        assert (await state(db))[0] == "alerted"
        assert (await c.post(URL, json=BODY)).status_code == 200
        assert (await c.post(url, json={"outcome": outcome})).status_code == 409
    assert await state(db) == ("done", "resolved", 2)


@pytest.mark.asyncio
async def test_waiting_acknowledgment_observes_committed_completion(db, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    original = ObligationsRepository.mark_done

    async def pause(self, obligation_id):
        result = await original(self, obligation_id)
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return result

    monkeypatch.setattr(ObligationsRepository, "mark_done", pause)
    async with client(db) as c:
        completion = asyncio.create_task(c.post(URL, json=BODY))
        await asyncio.wait_for(entered.wait(), 5)
        acknowledgment = asyncio.create_task(
            c.post("/api/compliance/alerts/alert-test/outcome", json={"outcome": "acknowledged"})
        )
        await asyncio.sleep(0.05)
        assert not acknowledgment.done()
        release.set()
        results = await asyncio.wait_for(asyncio.gather(completion, acknowledgment), 5)
    assert [r.status_code for r in results] == [200, 409]
    assert await state(db) == ("done", "resolved", 1)

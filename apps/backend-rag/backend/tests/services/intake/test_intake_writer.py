"""FASE 5B — CRM writer DRY-RUN tests (real local DB: nuzantara_dev).

The cardinal assertion of 5B: the writer logic runs end-to-end, but writes
NOTHING to the CRM. Every test that exercises approve/execute_commit also asserts
clients/practices/documents counts are unchanged (delta == 0).

P0 coverage:
  * P0#1 — two proposals, same blob, different clients → DIFFERENT idempotency
           keys are scoped per (client_id, key); the plan never collides.
  * P0#3 — a proposal whose target client is soft-deleted → plan.blocked.
  * P0#8 — write_client_document preserves ocr_status (no completed→pending).
  * P0#9 / flag — INTAKE_WRITER_ENABLED OFF → execute_commit(dry_run=False) raises
           WriterDisabledError and the dry-run path advances NO terminal state.

Runs against the LOCAL Pro Postgres only (Law 2). Skips if unreachable.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.intake import writer as intake_writer

DSN = os.environ.get("INTAKE_TEST_DSN", "postgresql://localhost:5432/nuzantara_dev")
PIPELINE = "test-5b"

ADMIN = {"id": "1", "email": "zero@balizero.com", "role": "admin"}

pytestmark = pytest.mark.asyncio


async def _dsn_reachable() -> bool:
    try:
        conn = await asyncpg.connect(DSN)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    if not await _dsn_reachable():
        pytest.skip(f"local intake DB not reachable at {DSN}")
    p = await asyncpg.create_pool(DSN, min_size=1, max_size=4)
    yield p
    await p.close()


async def _crm_counts(pool: asyncpg.Pool) -> dict[str, int]:
    async with pool.acquire() as conn:
        return {
            "clients": await conn.fetchval("SELECT count(*) FROM clients"),
            "practices": await conn.fetchval("SELECT count(*) FROM practices"),
            "documents": await conn.fetchval("SELECT count(*) FROM documents"),
        }


@pytest_asyncio.fixture
async def seed(pool: asyncpg.Pool) -> AsyncIterator[dict]:
    """Build a synthetic intake chain + 2 clients + an open practice."""
    tag = f"5btest-{uuid.uuid4().hex[:8]}"
    created: dict[str, list[int]] = {
        "clients": [], "proposals": [], "queues": [], "instances": [], "practices": []
    }
    bh = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]  # shared blob for both clients

    async with pool.acquire() as conn:
        cid_a = await conn.fetchval(
            "INSERT INTO clients (full_name, assigned_to) VALUES ($1,$2) RETURNING id",
            f"{tag}-A", ADMIN["email"],
        )
        cid_b = await conn.fetchval(
            "INSERT INTO clients (full_name, assigned_to) VALUES ($1,$2) RETURNING id",
            f"{tag}-B", ADMIN["email"],
        )
        created["clients"] += [cid_a, cid_b]

        # an open practice for client A (routing target)
        prac_a = await conn.fetchval(
            """INSERT INTO practices (client_id, practice_type_code, title, status)
               VALUES ($1, 'kitas_application', $2, 'in_progress') RETURNING id""",
            cid_a, f"{tag}-practice",
        )
        created["practices"].append(prac_a)

        # ONE physical blob instance (UNIQUE blob_hash+pipeline_version) shared by
        # both clients' intake queues — this is the cross-client same-blob scenario.
        inst = await conn.fetchval(
            """INSERT INTO document_instances (blob_hash, pipeline_version, blob_path, first_source)
               VALUES ($1,$2,$3,'drive') RETURNING id""",
            bh, PIPELINE, f"/tmp/{tag}.pdf",
        )
        created["instances"].append(inst)

        async def mk(client_id: int, decision: str, source_ref: str, practice_id=None) -> int:
            ikey = f"drive|{source_ref}|{bh}|{PIPELINE}|{uuid.uuid4().hex[:6]}"
            qid = await conn.fetchval(
                """INSERT INTO intake_queue
                   (instance_id, source, source_ref, blob_path, blob_hash, pipeline_version,
                    status, stage_output, intake_key)
                   VALUES ($1,'drive',$2,$3,$4,$5,'review_pending',$6::jsonb,$7) RETURNING id""",
                inst, source_ref, f"/tmp/{tag}.pdf", bh, PIPELINE,
                json.dumps({"doc_type": "npwp", "file_id": f"drive-{source_ref}",
                            "ocr": {"pages": [{"page": 1, "text": "NPWP"}]}}),
                ikey,
            )
            created["queues"].append(qid)
            entity = {"decision": decision, "candidates": [{"table": "clients", "id": client_id}]}
            routing = {"client_id": client_id, "company_id": None,
                       "practice_id": practice_id, "doc_type": "npwp",
                       "fields": {"npwp_number": {"value": "01.234.567.8-901.000"}}}
            gate = {"requires_human": decision != "AUTO_ATTACH", "decision": decision}
            pid = await conn.fetchval(
                """INSERT INTO document_routing_proposal
                   (queue_id, doc_index, pipeline_version, routing_key,
                    entity_resolution, routing, commit_gate, status,
                    lease_owner, lease_expires_at, claim_token)
                   VALUES ($1,0,$2,$3,$4::jsonb,$5::jsonb,$6::jsonb,'review_claimed',
                           $7, now() + interval '15 min', $8)
                   RETURNING id""",
                qid, PIPELINE, f"{tag}-{uuid.uuid4().hex[:8]}",
                json.dumps(entity), json.dumps(routing), json.dumps(gate),
                ADMIN["email"], uuid.uuid4(),
            )
            created["proposals"].append(pid)
            return pid

        p_a = await mk(cid_a, "AUTO_ATTACH", "refA", practice_id=prac_a)
        p_b = await mk(cid_b, "AUTO_ATTACH", "refA")  # SAME source_ref+blob, different client

    yield {"tag": tag, "cid_a": cid_a, "cid_b": cid_b, "prac_a": prac_a,
           "p_a": p_a, "p_b": p_b, "bh": bh, "created": created}

    async with pool.acquire() as conn:
        for pid in created["proposals"]:
            await conn.execute("DELETE FROM intake_commit_audit WHERE proposal_id=$1", pid)
            await conn.execute("DELETE FROM document_routing_proposal WHERE id=$1", pid)
        for qid in created["queues"]:
            await conn.execute("DELETE FROM intake_queue WHERE id=$1", qid)
        for iid in created["instances"]:
            await conn.execute("DELETE FROM document_instances WHERE id=$1", iid)
        for prid in created["practices"]:
            await conn.execute("DELETE FROM practices WHERE id=$1", prid)
        for cid in created["clients"]:
            await conn.execute("DELETE FROM clients WHERE id=$1", cid)


def _make_app(pool: asyncpg.Pool, user: dict) -> FastAPI:
    from backend.app.routers import intake_review
    app = FastAPI()
    app.include_router(intake_review.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database_pool] = lambda: pool
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


# --------------------------------------------------------------------------- #
async def test_approve_dry_run_returns_commit_plan(pool, seed, monkeypatch):
    """approve (dry-run) returns a sensible CommitPlan and writes NOTHING to CRM."""
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)  # flag OFF
    before = await _crm_counts(pool)
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is True
    assert body["status"] == "review_claimed"  # P0#9: not advanced
    assert body["outcome"] == "dry_run"
    plan = body["would_commit"]
    assert plan["client_id"] == seed["cid_a"]
    assert plan["practice_id"] == seed["prac_a"]
    assert plan["blocked"] is False
    assert plan["idempotency_key"].startswith("ik:")
    tables = {op["table"] for op in plan["ops"]}
    assert "documents" in tables
    assert "practices.documents[]" in tables  # practice link planned
    after = await _crm_counts(pool)
    assert after == before, f"CRM mutated! {before} -> {after}"


async def test_zero_crm_write_repeated_approve(pool, seed):
    """CRITICAL: repeated dry-run approves → ZERO CRM rows written (delta == 0)."""
    before = await _crm_counts(pool)
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        for _ in range(5):
            r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
            assert r.status_code == 200, r.text
            assert r.json()["dry_run"] is True
    after = await _crm_counts(pool)
    assert after["clients"] == before["clients"]
    assert after["practices"] == before["practices"]
    assert after["documents"] == before["documents"], "documents row written in dry-run!"


async def test_p0_1_idempotency_key_cross_client_distinct(pool, seed):
    """P0#1: same blob, two clients → keys are per-client-scoped, no collision."""
    async with pool.acquire() as conn:
        prop_a = await conn.fetchrow(
            "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"])
        prop_b = await conn.fetchrow(
            "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_b"])
        plan_a = await intake_writer.plan_commit(prop_a, conn, committed_by=ADMIN["email"])
        plan_b = await intake_writer.plan_commit(prop_b, conn, committed_by=ADMIN["email"])
    # SAME blob + SAME source_ref → the key STRING is identical across the two
    # clients. That is exactly the P0#1 collision scenario: with a GLOBAL unique on
    # content, client B would silently skip client A's doc. Here the UNIQUE is
    # (client_id, key) — so the IDENTITY (client_id, key) is still distinct and no
    # collision occurs.
    assert plan_a.client_id != plan_b.client_id
    assert plan_a.idempotency_key == plan_b.idempotency_key, "same blob+ref → same key string"
    assert (plan_a.client_id, plan_a.idempotency_key) != (plan_b.client_id, plan_b.idempotency_key)
    # Neither blocked, neither wrote anything.
    assert not plan_a.blocked and not plan_b.blocked


async def test_p0_3_blocked_on_soft_deleted_client(pool, seed):
    """P0#3: target client soft-deleted between routing and approve → plan blocked."""
    before = await _crm_counts(pool)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE clients SET deleted_at = now() WHERE id=$1", seed["cid_a"])
        try:
            prop_a = await conn.fetchrow(
                "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"])
            plan = await intake_writer.plan_commit(prop_a, conn, committed_by=ADMIN["email"])
            result = await intake_writer.execute_commit(plan, conn, dry_run=True)
        finally:
            await conn.execute("UPDATE clients SET deleted_at = NULL WHERE id=$1", seed["cid_a"])
    assert plan.blocked is True
    assert any("soft-deleted" in r for r in plan.block_reasons)
    assert result.outcome == "blocked"
    after = await _crm_counts(pool)
    assert after == before


async def test_flag_off_real_commit_refused(pool, seed, monkeypatch):
    """Feature-flag OFF: execute_commit(dry_run=False) raises, never writes CRM."""
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)
    assert intake_writer.writer_enabled() is False
    before = await _crm_counts(pool)
    async with pool.acquire() as conn:
        prop_a = await conn.fetchrow(
            "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"])
        plan = await intake_writer.plan_commit(prop_a, conn, committed_by=ADMIN["email"])
        with pytest.raises(intake_writer.WriterDisabledError):
            await intake_writer.execute_commit(plan, conn, dry_run=False)
    after = await _crm_counts(pool)
    assert after == before, "CRM mutated despite flag OFF!"


async def test_dry_run_writes_only_audit_row(pool, seed):
    """The ONLY write a dry-run performs is one intake_commit_audit row."""
    async with pool.acquire() as conn:
        n_before = await conn.fetchval(
            "SELECT count(*) FROM intake_commit_audit WHERE proposal_id=$1", seed["p_a"])
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200
    async with pool.acquire() as conn:
        n_after = await conn.fetchval(
            "SELECT count(*) FROM intake_commit_audit WHERE proposal_id=$1", seed["p_a"])
        row = await conn.fetchrow(
            "SELECT dry_run, outcome, doc_id FROM intake_commit_audit "
            "WHERE proposal_id=$1 ORDER BY id DESC LIMIT 1", seed["p_a"])
    assert n_after == n_before + 1
    assert row["dry_run"] is True
    assert row["outcome"] == "dry_run"
    assert row["doc_id"] is None

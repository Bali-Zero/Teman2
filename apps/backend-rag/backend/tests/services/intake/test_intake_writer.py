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
        "clients": [],
        "proposals": [],
        "queues": [],
        "instances": [],
        "practices": [],
    }
    bh = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]  # shared blob for both clients
    # Unique per-seed npwp: the tests run against the REAL dev book, so a fixed
    # synthetic value could collide with a live client and flip a strong-id
    # revalidation to duplicate (Codex round-2 NIT).
    npwp_digits = str(uuid.uuid4().int)[:15].rjust(15, "7")

    async with pool.acquire() as conn:
        cid_a = await conn.fetchval(
            "INSERT INTO clients (full_name, assigned_to) VALUES ($1,$2) RETURNING id",
            f"{tag}-A",
            ADMIN["email"],
        )
        cid_b = await conn.fetchval(
            "INSERT INTO clients (full_name, assigned_to) VALUES ($1,$2) RETURNING id",
            f"{tag}-B",
            ADMIN["email"],
        )
        created["clients"] += [cid_a, cid_b]

        # an open practice for client A (routing target)
        prac_a = await conn.fetchval(
            """INSERT INTO practices (client_id, practice_type_code, title, status)
               VALUES ($1, 'kitas_application', $2, 'in_progress') RETURNING id""",
            cid_a,
            f"{tag}-practice",
        )
        created["practices"].append(prac_a)

        # ONE physical blob instance (UNIQUE blob_hash+pipeline_version) shared by
        # both clients' intake queues — this is the cross-client same-blob scenario.
        inst = await conn.fetchval(
            """INSERT INTO document_instances (blob_hash, pipeline_version, blob_path, first_source)
               VALUES ($1,$2,$3,'drive') RETURNING id""",
            bh,
            PIPELINE,
            f"/tmp/{tag}.pdf",
        )
        created["instances"].append(inst)

        async def mk(client_id: int, decision: str, source_ref: str, practice_id=None) -> int:
            ikey = f"drive|{source_ref}|{bh}|{PIPELINE}|{uuid.uuid4().hex[:6]}"
            qid = await conn.fetchval(
                """INSERT INTO intake_queue
                   (instance_id, source, source_ref, blob_path, blob_hash, pipeline_version,
                    status, stage_output, intake_key)
                   VALUES ($1,'drive',$2,$3,$4,$5,'review_pending',$6::jsonb,$7) RETURNING id""",
                inst,
                source_ref,
                f"/tmp/{tag}.pdf",
                bh,
                PIPELINE,
                json.dumps(
                    {
                        "doc_type": "npwp",
                        "file_id": f"drive-{source_ref}",
                        "ocr": {"pages": [{"page": 1, "text": "NPWP"}]},
                    }
                ),
                ikey,
            )
            created["queues"].append(qid)
            # Candidates mirror the REAL m248 resolver shape (method + score +
            # matched_value) — the auto-attach gates re-verify strong-id
            # ownership from matched_value at commit time.
            entity = {
                "decision": decision,
                "candidates": [
                    {
                        "table": "clients",
                        "id": client_id,
                        "method": "npwp",
                        "score": 0.99,
                        "matched_value": npwp_digits,
                    }
                ],
            }
            routing = {
                "client_id": client_id,
                "company_id": None,
                "practice_id": practice_id,
                "doc_type": "npwp",
                "fields": {"npwp_number": {"value": npwp_digits}},
            }
            gate = {"requires_human": decision != "AUTO_ATTACH", "decision": decision}
            pid = await conn.fetchval(
                """INSERT INTO document_routing_proposal
                   (queue_id, doc_index, pipeline_version, routing_key,
                    entity_resolution, routing, commit_gate, status,
                    lease_owner, lease_expires_at, claim_token)
                   VALUES ($1,0,$2,$3,$4::jsonb,$5::jsonb,$6::jsonb,'review_claimed',
                           $7, now() + interval '15 min', $8)
                   RETURNING id""",
                qid,
                PIPELINE,
                f"{tag}-{uuid.uuid4().hex[:8]}",
                json.dumps(entity),
                json.dumps(routing),
                json.dumps(gate),
                ADMIN["email"],
                uuid.uuid4(),
            )
            created["proposals"].append(pid)
            return pid

        p_a = await mk(cid_a, "AUTO_ATTACH", "refA", practice_id=prac_a)
        p_b = await mk(cid_b, "AUTO_ATTACH", "refA")  # SAME source_ref+blob, different client

    yield {
        "tag": tag,
        "cid_a": cid_a,
        "cid_b": cid_b,
        "prac_a": prac_a,
        "p_a": p_a,
        "p_b": p_b,
        "bh": bh,
        "npwp_digits": npwp_digits,
        "created": created,
    }

    async with pool.acquire() as conn:
        # Real-write tests (flag ON) may have INSERTed documents for these clients —
        # remove them first so the FK to clients doesn't block teardown.
        for cid in created["clients"]:
            await conn.execute("DELETE FROM documents WHERE client_id=$1", cid)
            await conn.execute("DELETE FROM intake_commit_audit WHERE client_id=$1", cid)
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
            "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
        prop_b = await conn.fetchrow(
            "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_b"]
        )
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
                "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"]
            )
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
            "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
        plan = await intake_writer.plan_commit(prop_a, conn, committed_by=ADMIN["email"])
        with pytest.raises(intake_writer.WriterDisabledError):
            await intake_writer.execute_commit(plan, conn, dry_run=False)
    after = await _crm_counts(pool)
    assert after == before, "CRM mutated despite flag OFF!"


async def test_dry_run_writes_only_audit_row(pool, seed):
    """The ONLY write a dry-run performs is one intake_commit_audit row."""
    async with pool.acquire() as conn:
        n_before = await conn.fetchval(
            "SELECT count(*) FROM intake_commit_audit WHERE proposal_id=$1", seed["p_a"]
        )
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200
    async with pool.acquire() as conn:
        n_after = await conn.fetchval(
            "SELECT count(*) FROM intake_commit_audit WHERE proposal_id=$1", seed["p_a"]
        )
        row = await conn.fetchrow(
            "SELECT dry_run, outcome, doc_id FROM intake_commit_audit "
            "WHERE proposal_id=$1 ORDER BY id DESC LIMIT 1",
            seed["p_a"],
        )
    assert n_after == n_before + 1
    assert row["dry_run"] is True
    assert row["outcome"] == "dry_run"
    assert row["doc_id"] is None


# --------------------------------------------------------------------------- #
# FASE 5C — REAL-WRITE PATH (flag ON). Mirror image of the 5B assertions: here
# the writer DOES write, the proposal IS advanced, and the audit says committed.
# Every test flips INTAKE_WRITER_ENABLED=1 for its own process only (monkeypatch)
# and relies on the `seed` fixture teardown to delete any documents it inserts.
# --------------------------------------------------------------------------- #
def _parse_docs(value) -> list:  # noqa: ANN001
    """Decode a practices.documents jsonb cell — the pool has no json codec, so a
    jsonb column comes back as a TEXT string; list(str) would iterate characters."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    return []


async def _docs_for_client(pool: asyncpg.Pool, client_id: int) -> list[asyncpg.Record]:
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM documents WHERE client_id = $1 ORDER BY id", client_id
        )


async def _proposal_status(pool: asyncpg.Pool, proposal_id: int) -> str:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id = $1", proposal_id
        )


async def test_real_commit_writes_document_and_advances(pool, seed, monkeypatch):
    """Flag ON: approve writes ONE document, links the practice, advances proposal."""
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    assert intake_writer.writer_enabled() is True

    docs_before = await _docs_for_client(pool, seed["cid_a"])
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dry_run"] is False
    assert body["outcome"] == "committed"
    assert body["status"] == "routed"  # proposal advanced (real path)
    assert body["result"]["doc_id"] is not None

    docs_after = await _docs_for_client(pool, seed["cid_a"])
    assert len(docs_after) == len(docs_before) + 1, "exactly one document written"
    new_doc = docs_after[-1]
    assert new_doc["intake_proposal_id"] == seed["p_a"]
    assert new_doc["intake_idempotency_key"].startswith("ik:")

    # Proposal moved to terminal 'routed' and the claim was released.
    async with pool.acquire() as conn:
        prop = await conn.fetchrow(
            "SELECT status, claim_token, lease_owner FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
    assert prop["status"] == "routed"
    assert prop["claim_token"] is None
    assert prop["lease_owner"] is None

    # Practice membership now lists the document (P0#6 dual-link).
    async with pool.acquire() as conn:
        prac = await conn.fetchrow("SELECT documents FROM practices WHERE id=$1", seed["prac_a"])
    members = _parse_docs(prac["documents"])
    assert any(isinstance(d, dict) and d.get("doc_id") == new_doc["id"] for d in members)

    # Audit row says committed, not dry_run.
    async with pool.acquire() as conn:
        audit = await conn.fetchrow(
            "SELECT dry_run, outcome, doc_id FROM intake_commit_audit "
            "WHERE proposal_id=$1 ORDER BY id DESC LIMIT 1",
            seed["p_a"],
        )
    assert audit["dry_run"] is False
    assert audit["outcome"] == "committed"
    assert audit["doc_id"] == new_doc["id"]

    # The same atomic commit produces a local field-level ground-truth row.
    async with pool.acquire() as conn:
        correction = await conn.fetchrow(
            """
            SELECT field_name, ai_value, human_value, ai_confidence, outcome,
                   source, verified_by
            FROM intake_corrections
            WHERE queue_id = (
                SELECT queue_id FROM document_routing_proposal WHERE id = $1
            )
            ORDER BY id DESC
            LIMIT 1
            """,
            seed["p_a"],
        )
    assert correction["field_name"] == "npwp_number"
    assert correction["ai_value"] == seed["npwp_digits"]
    assert correction["human_value"] == correction["ai_value"]
    assert correction["outcome"] == "approved"
    assert correction["source"] == "drive"
    assert correction["verified_by"] == ADMIN["email"]


async def test_real_commit_idempotent_recommit(pool, seed, monkeypatch):
    """Flag ON: re-approving the same intake instance is a no-op (same doc, no dup).

    P0#2: the UPSERT on (client_id, intake_idempotency_key) returns the SAME doc_id;
    a second commit must not create a second documents row.
    """
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    app = _make_app(pool, ADMIN)

    async with _client(app) as cl:
        r1 = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r1.status_code == 200, r1.text
    doc_id_1 = r1.json()["result"]["doc_id"]
    assert doc_id_1 is not None
    docs_after_first = await _docs_for_client(pool, seed["cid_a"])
    async with pool.acquire() as conn:
        corrections_after_first = await conn.fetchval(
            """
            SELECT count(*) FROM intake_corrections
            WHERE queue_id = (
                SELECT queue_id FROM document_routing_proposal WHERE id = $1
            )
            """,
            seed["p_a"],
        )

    # The proposal is now 'routed' (terminal) — plan_commit would block it as "not
    # approvable". Re-arm it to 'review_claimed' so a SECOND execute_commit reaches
    # the UPSERT (the unit under test): same idempotency key → same canonical doc_id,
    # no duplicate row.
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE document_routing_proposal SET status='review_claimed' WHERE id=$1",
            seed["p_a"],
        )
        async with conn.transaction():
            prop = await conn.fetchrow(
                "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"]
            )
            plan = await intake_writer.plan_commit(prop, conn, committed_by=ADMIN["email"])
            # existing doc surfaced by the idempotency probe
            assert plan.existing_doc_id == doc_id_1
            assert plan.blocked is False
            result = await intake_writer.execute_commit(plan, conn, dry_run=False)
    assert result.outcome == "committed"
    assert result.doc_id == doc_id_1, "re-commit must reuse the same canonical doc_id"

    docs_after_second = await _docs_for_client(pool, seed["cid_a"])
    assert len(docs_after_second) == len(docs_after_first), "no duplicate document on re-commit"
    async with pool.acquire() as conn:
        corrections_after_second = await conn.fetchval(
            """
            SELECT count(*) FROM intake_corrections
            WHERE queue_id = (
                SELECT queue_id FROM document_routing_proposal WHERE id = $1
            )
            """,
            seed["p_a"],
        )
    assert corrections_after_second == corrections_after_first


async def test_blocked_plan_no_write_even_with_flag_on(pool, seed, monkeypatch):
    """Flag ON but plan blocked (soft-deleted client) → still zero CRM writes."""
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    before = await _crm_counts(pool)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE clients SET deleted_at = now() WHERE id=$1", seed["cid_a"])
        try:
            async with conn.transaction():
                prop = await conn.fetchrow(
                    "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"]
                )
                plan = await intake_writer.plan_commit(prop, conn, committed_by=ADMIN["email"])
                result = await intake_writer.execute_commit(plan, conn, dry_run=False)
        finally:
            await conn.execute("UPDATE clients SET deleted_at = NULL WHERE id=$1", seed["cid_a"])
    assert plan.blocked is True
    assert result.outcome == "blocked"
    after = await _crm_counts(pool)
    assert after == before, "blocked plan wrote to CRM despite being blocked"
    assert await _proposal_status(pool, seed["p_a"]) == "review_claimed", "blocked must not advance"


async def test_exception_mid_tx_rolls_back(pool, seed, monkeypatch):
    """Flag ON: a failure AFTER the document write rolls the whole approve back.

    We force the practice append to explode (practice vanishes mid-TX) and assert
    the document INSERT it preceded is also gone and the proposal is untouched.
    """
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    before = await _crm_counts(pool)

    async def _boom(conn, plan, doc_id):  # noqa: ANN001
        raise RuntimeError("simulated practice append failure mid-TX")

    monkeypatch.setattr(intake_writer, "_append_practice_document", _boom)

    async with pool.acquire() as conn:
        with pytest.raises(RuntimeError, match="simulated practice append failure"):
            async with conn.transaction():
                prop = await conn.fetchrow(
                    "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"]
                )
                plan = await intake_writer.plan_commit(prop, conn, committed_by=ADMIN["email"])
                await intake_writer.execute_commit(plan, conn, dry_run=False)

    after = await _crm_counts(pool)
    assert after == before, "TX did not roll back — orphan document survived the failure"
    assert await _proposal_status(pool, seed["p_a"]) == "review_claimed", (
        "proposal advanced despite rollback"
    )


async def test_rollback_commit_undoes_document(pool, seed, monkeypatch):
    """rollback_commit removes the document, re-opens the proposal, is idempotent."""
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200, r.text
    doc_id = r.json()["result"]["doc_id"]
    idem_key = r.json()["would_commit"]["idempotency_key"]
    assert await _proposal_status(pool, seed["p_a"]) == "routed"

    # First rollback — undoes the commit.
    async with pool.acquire() as conn:
        async with conn.transaction():
            res = await intake_writer.rollback_commit(
                conn,
                client_id=seed["cid_a"],
                idempotency_key=idem_key,
                committed_by=ADMIN["email"],
            )
    assert res.outcome == "rolled_back"
    assert res.doc_id == doc_id

    async with pool.acquire() as conn:
        gone = await conn.fetchval("SELECT count(*) FROM documents WHERE id=$1", doc_id)
        prac = await conn.fetchrow("SELECT documents FROM practices WHERE id=$1", seed["prac_a"])
    assert gone == 0, "document not deleted by rollback"
    assert not any(
        isinstance(d, dict) and d.get("doc_id") == doc_id for d in _parse_docs(prac["documents"])
    ), "practice link not detached by rollback"
    assert await _proposal_status(pool, seed["p_a"]) == "review_claimed", "proposal not re-opened"

    # Second rollback — safe no-op (idempotent).
    async with pool.acquire() as conn:
        async with conn.transaction():
            res2 = await intake_writer.rollback_commit(
                conn,
                client_id=seed["cid_a"],
                idempotency_key=idem_key,
                committed_by=ADMIN["email"],
            )
    assert res2.outcome == "rolled_back"
    assert res2.doc_id is None, "second rollback should find nothing to undo"


# --------------------------------------------------------------------------- #
# Company-document folder routing (regression: NIB/akta were filed to 99_Misc)
# Pure unit — no DB. Falsifies the company→folder mismatch end to end.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "doc_type, expected_category, expected_folder",
    [
        ("nib", "pma", "02_Company"),
        ("akta_pendirian", "pma", "02_Company"),
        ("profil_perseroan", "pma", "02_Company"),
        ("sk_kemenkumham", "pma", "02_Company"),
        ("oss", "pma", "02_Company"),
        ("passport", "immigration", "01_Immigration"),
        ("visa", "immigration", "01_Immigration"),
        ("kitas", "immigration", "01_Immigration"),
        ("itap", "immigration", "01_Immigration"),
        ("itk", "immigration", "01_Immigration"),
        ("ktp", "personal", "00_Profile"),
        ("family_card", "family", "04_Family"),
        ("birth_certificate", "family", "04_Family"),
        ("marriage_certificate", "family", "04_Family"),
        ("payment_receipt", "other", "99_Misc"),
        ("travel_ticket", "other", "99_Misc"),
        ("bank_statement", "other", "99_Misc"),
        ("medical_insurance", "other", "99_Misc"),
        ("npwp", "tax", "03_Tax"),
        ("skt", "tax", "03_Tax"),
    ],
)
def test_company_doc_category_maps_to_company_folder(doc_type, expected_category, expected_folder):
    """Intake-derived category must be the CANONICAL one that resolves to the
    right Drive folder. Before the fix, nib/akta produced category='company',
    which is absent from CATEGORY_TO_FOLDER → fell through to '99_Misc' (Drive
    'Misc' instead of '02_Company'). This test fails if either side drifts:
    the intake category map, OR the folder map.
    """
    from backend.services.crm.document_categorizer import CATEGORY_TO_FOLDER

    payload = intake_writer._document_payload(
        routing={"doc_type": doc_type},
        stage_output={},
        source_ref="test-ref",
    )
    category = payload["document_category"]
    assert category == expected_category, (
        f"{doc_type}: intake produced category={category!r}, "
        f"expected canonical {expected_category!r}"
    )
    # The category MUST be a real key (not a silent 99_Misc fallthrough).
    assert category in CATEGORY_TO_FOLDER, (
        f"category {category!r} missing from CATEGORY_TO_FOLDER → would file to 99_Misc"
    )
    assert CATEGORY_TO_FOLDER[category] == expected_folder


# --------------------------------------------------------------------------- #
# Difetto 3 — client-card enrichment from extracted document fields
# (passport_number/expiry/dob/nationality feed the client profile on approve).
# --------------------------------------------------------------------------- #
async def _set_passport_proposal(conn: asyncpg.Pool, proposal_id: int, client_id: int) -> None:
    """Rewrite a seeded proposal to a passport doc with nested {value} fields,
    mirroring the real FASE-3 extract shape (extract.py:252)."""
    routing = {
        "client_id": client_id,
        "company_id": None,
        "practice_id": None,
        "doc_type": "passport",
        "fields": {
            "passport_no": {"value": "YC0000001", "confidence": 0.99, "source_page": 1},
            "expiry": {"value": "2034-06-19", "confidence": 0.98, "source_page": 1},
            "dob": {"value": "1987-07-01", "confidence": 0.97, "source_page": 1},
            "nationality": {"value": "ITALIANA", "confidence": 0.95, "source_page": 1},
        },
    }
    entity = {"decision": "AUTO_ATTACH", "candidates": [{"table": "clients", "id": client_id}]}
    await conn.execute(
        "UPDATE document_routing_proposal SET routing=$1::jsonb, entity_resolution=$2::jsonb WHERE id=$3",
        json.dumps(routing),
        json.dumps(entity),
        proposal_id,
    )
    await conn.execute(
        "UPDATE intake_queue SET stage_output=$1::jsonb WHERE id="
        "(SELECT queue_id FROM document_routing_proposal WHERE id=$2)",
        json.dumps({"doc_type": "passport", "file_id": "drive-passport-enrich"}),
        proposal_id,
    )


async def test_approve_enriches_client_card_passport(pool, seed, monkeypatch):
    """Flag ON: approving a passport writes passport_number/expiry/dob/nationality
    onto the client card, atomically with the document — Difetto 3 fix."""
    from datetime import date

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    async with pool.acquire() as conn:
        await _set_passport_proposal(conn, seed["p_a"], seed["cid_a"])
        # baseline: card is empty for these identity columns
        before = await conn.fetchrow(
            "SELECT passport_number, passport_expiry, date_of_birth, nationality "
            "FROM clients WHERE id=$1",
            seed["cid_a"],
        )
    assert before["passport_number"] is None
    assert before["passport_expiry"] is None

    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "committed"

    async with pool.acquire() as conn:
        after = await conn.fetchrow(
            "SELECT passport_number, passport_expiry, date_of_birth, nationality "
            "FROM clients WHERE id=$1",
            seed["cid_a"],
        )
    assert after["passport_number"] == "YC0000001"
    assert after["passport_expiry"] == date(2034, 6, 19)
    assert after["date_of_birth"] == date(1987, 7, 1)
    assert after["nationality"] == "ITALIANA"


async def test_enrichment_skips_archive_only_no_client(pool, seed, monkeypatch):
    """Innocence test: archive-only (client_id None) must NOT attempt any client UPDATE."""
    from backend.services.intake.client_enricher import enrich_client_from_extracted_fields

    async with pool.acquire() as conn:
        written = await enrich_client_from_extracted_fields(
            conn,
            None,
            "passport",
            {"passport_no": {"value": "X"}, "expiry": {"value": "2030-01-01"}},
        )
    assert written == {}  # no-op, no exception


# --------------------------------------------------------------------------- #
# Wire proof (m248): the LEVA auto-commit tiers COMMIT on an npwp-matched doc.
# The gates are doc-type-agnostic by design (decision + client_id + concordance,
# no passport/kitas field allow-list) — these tests pin that: no future doc-type
# filter may silently unwire npwp. First commit-success coverage for try_* at
# all (previously only killswitch-off no-ops were tested).
# --------------------------------------------------------------------------- #
async def _reopen_for_auto(pool, proposal_id: int) -> None:
    """Seeded proposals are review_claimed; the auto gates only touch review_pending."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE document_routing_proposal SET status='review_pending', "
            "lease_owner=NULL, lease_expires_at=NULL, claim_token=NULL WHERE id=$1",
            proposal_id,
        )


def _stub_delivery(monkeypatch):
    from backend.services.intake import auto_attach as aa

    async def _no_delivery(**_kw):
        return {"status": "stubbed_in_test"}

    monkeypatch.setattr(aa.intake_crm_delivery, "deliver_committed_to_crm", _no_delivery)


async def test_leva2_auto_attach_commits_npwp_matched_doc(pool, seed, monkeypatch):
    """LEVA-2 wire proof: npwp doc, strong-id→client A, sender phone→same client
    → REAL commit: proposal auto_routed, audit row by system:auto-attach, and the
    enricher backfills the client's npwp key in the same TX (identity-backfill
    compounding, m248)."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        # ownership precondition: the strong-id revalidation requires the routed
        # client to STILL own the matched npwp at commit time
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1, npwp=$2 WHERE id=$3",
            phone,
            seed["npwp_digits"],
            seed["cid_a"],
        )
        proposal = await conn.fetchrow(
            "SELECT id, routing, entity_resolution FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        proposal = {
            "id": proposal["id"],
            "routing": json.loads(proposal["routing"]),
            "entity_resolution": json.loads(proposal["entity_resolution"]),
        }

    verdict = await aa.try_auto_attach(proposal, pool, sender_phone=phone)
    assert verdict["committed"] is True, verdict
    assert verdict["status"] == "auto_routed"

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
        audit = await conn.fetchrow(
            "SELECT committed_by, outcome, dry_run FROM intake_commit_audit "
            "WHERE proposal_id=$1 ORDER BY id DESC LIMIT 1",
            seed["p_a"],
        )
        npwp = await conn.fetchval("SELECT npwp FROM clients WHERE id=$1", seed["cid_a"])
    assert status == "auto_routed"
    assert audit["committed_by"] == "system:auto-attach"
    assert audit["outcome"] == "committed"
    assert audit["dry_run"] is False
    assert npwp == seed["npwp_digits"]


async def test_leva3_nameid_auto_attach_commits_npwp_matched_doc(pool, seed, monkeypatch):
    """LEVA-3 wire proof: npwp doc, NO sender phone, doc subject name (FASE-3
    {"value": ...} wrapped shape) concordant with client A → REAL commit by
    system:auto-nameid. Also exercises the _extracted_subject_name unwrap on the
    real dict shape."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    await _reopen_for_auto(pool, seed["p_b"])
    async with pool.acquire() as conn:
        client_name = await conn.fetchval(
            "SELECT full_name FROM clients WHERE id=$1", seed["cid_b"]
        )
        await conn.execute(
            "UPDATE clients SET npwp=$1 WHERE id=$2",
            seed["npwp_digits"],
            seed["cid_b"],
        )
        await conn.execute(
            "UPDATE intake_queue SET stage_output = stage_output || $1::jsonb "
            "WHERE id = (SELECT queue_id FROM document_routing_proposal WHERE id=$2)",
            json.dumps(
                {
                    "extract": {
                        "fields": {
                            "name": {"value": client_name, "confidence": 0.93, "source_page": 1}
                        }
                    }
                }
            ),
            seed["p_b"],
        )
        proposal = await conn.fetchrow(
            "SELECT id FROM document_routing_proposal WHERE id=$1", seed["p_b"]
        )

    verdict = await aa.try_nameid_auto_attach(dict(proposal), pool)
    assert verdict["committed"] is True, verdict
    assert verdict["status"] == "auto_routed"

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_b"]
        )
        audit = await conn.fetchrow(
            "SELECT committed_by, outcome FROM intake_commit_audit "
            "WHERE proposal_id=$1 ORDER BY id DESC LIMIT 1",
            seed["p_b"],
        )
    assert status == "auto_routed"
    assert audit["committed_by"] == "system:auto-nameid"
    assert audit["outcome"] == "committed"


async def test_m248_chain_resolver_to_leva2_commit(pool, seed, monkeypatch):
    """FULL-CHAIN wire proof (Codex 2026-07-19 finding 4): the AUTO_ATTACH decision
    and candidate come from the REAL m248 resolver (resolve_entity against the DB),
    not hand-seeded JSON — if npwp matching were unwired this test fails at the
    resolver assert, before the gate ever runs."""
    from backend.services.intake import auto_attach as aa
    from backend.services.intake.routing import resolve_entity

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    npwp_digits = str(uuid.uuid4().int)[:15].rjust(15, "3")  # collision-free per run
    npwp_formatted = (
        f"{npwp_digits[:2]}.{npwp_digits[2:5]}.{npwp_digits[5:8]}."
        f"{npwp_digits[8]}-{npwp_digits[9:12]}.{npwp_digits[12:15]}"
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET npwp=$1, phone_normalized=$2 WHERE id=$3",
            npwp_formatted,  # stored FORMATTED — resolver must normalize
            phone,
            seed["cid_a"],
        )

    entity = await resolve_entity(
        {"npwp_number": {"value": npwp_digits, "confidence": 0.9}}, "npwp", pool
    )
    npwp_cands = [c for c in entity["candidates"] if c.get("method") == "npwp"]
    assert entity["decision"] == "AUTO_ATTACH"
    assert [c["id"] for c in npwp_cands] == [seed["cid_a"]]

    # route-stage mapping: entity → routing (client_id from the single candidate)
    routing = {
        "client_id": seed["cid_a"],
        "company_id": None,
        "practice_id": None,
        "doc_type": "npwp",
        "fields": {"npwp_number": {"value": npwp_digits, "confidence": 0.9}},
    }
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE document_routing_proposal SET entity_resolution=$1::jsonb, "
            "routing=$2::jsonb WHERE id=$3",
            json.dumps(entity),
            json.dumps(routing),
            seed["p_a"],
        )

    verdict = await aa.try_auto_attach({"id": seed["p_a"]}, pool, sender_phone=phone)
    assert verdict["committed"] is True, verdict

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
        npwp_after = await conn.fetchval(
            "SELECT npwp FROM clients WHERE id=$1", seed["cid_a"]
        )
    assert status == "auto_routed"
    # enricher canonicalized the formatted card value to bare digits in the same TX
    assert npwp_after == npwp_digits


async def test_m248_chain_dup_npwp_degrades_and_gate_refuses(pool, seed, monkeypatch):
    """Guilt chain (Codex finding 4): duplicate npwp across two clients → the REAL
    resolver degrades to AMBIGUOUS, and even a hostile routing payload naming one
    of them cannot make the gate commit (persisted decision wins — lock-first)."""
    from backend.services.intake import auto_attach as aa
    from backend.services.intake.routing import resolve_entity

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    dup = str(uuid.uuid4().int)[:15].rjust(15, "5")  # collision-free per run
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET npwp=$1, phone_normalized=$2 WHERE id=$3",
            dup,
            phone,
            seed["cid_a"],
        )
        await conn.execute(
            "UPDATE clients SET npwp=$1 WHERE id=$2", dup, seed["cid_b"]
        )

    entity = await resolve_entity({"npwp_number": dup}, "npwp", pool)
    assert entity["decision"] == "AMBIGUOUS"

    routing = {"client_id": seed["cid_a"], "doc_type": "npwp", "fields": {}}
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE document_routing_proposal SET entity_resolution=$1::jsonb, "
            "routing=$2::jsonb WHERE id=$3",
            json.dumps(entity),
            json.dumps(routing),
            seed["p_a"],
        )

    verdict = await aa.try_auto_attach({"id": seed["p_a"]}, pool, sender_phone=phone)
    assert verdict["committed"] is False
    assert verdict["skipped"] == "not_concordant"
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
    assert status == "review_pending"


async def test_leva2_evaluates_persisted_row_not_caller_payload(pool, seed, monkeypatch):
    """Guilt for the lock-first fix (Codex finding 3): the caller's payload claims
    AUTO_ATTACH but the PERSISTED proposal says LINK_CANDIDATE — the gate must
    read the locked row and refuse, never trust the in-memory payload."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    await _reopen_for_auto(pool, seed["p_b"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", phone, seed["cid_b"]
        )
        await conn.execute(
            "UPDATE document_routing_proposal SET entity_resolution=$1::jsonb WHERE id=$2",
            json.dumps(
                {
                    "decision": "LINK_CANDIDATE",
                    "candidates": [{"table": "clients", "id": seed["cid_b"]}],
                }
            ),
            seed["p_b"],
        )

    hostile_payload = {
        "id": seed["p_b"],
        "routing": {"client_id": seed["cid_b"]},
        "entity_resolution": {"decision": "AUTO_ATTACH"},
    }
    verdict = await aa.try_auto_attach(hostile_payload, pool, sender_phone=phone)
    assert verdict["committed"] is False
    # fresh payload disagrees with the persisted row → the divergence guard
    # refuses BEFORE any concordance logic runs (neither side is trusted)
    assert verdict["skipped"] == "stale_row_divergence"
    assert "diverges" in verdict["reason"]


async def test_strongid_ownership_moved_refuses_commit(pool, seed, monkeypatch):
    """Guilt for the in-TX ownership revalidation (Codex round-2 BLOCKER): the
    persisted proposal says npwp→client A, but the CRM was corrected meanwhile
    and the npwp now belongs to client B. Phone still concords with A — yet the
    strong-id evidence is stale, so the gate must refuse (unbounded staleness:
    ON CONFLICT-preserved rows and the backlog bridge)."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        # phone concords with A, but the npwp the proposal matched on has MOVED to B
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1, npwp=NULL WHERE id=$2",
            phone,
            seed["cid_a"],
        )
        await conn.execute(
            "UPDATE clients SET npwp=$1 WHERE id=$2",
            seed["npwp_digits"],
            seed["cid_b"],
        )

    verdict = await aa.try_auto_attach({"id": seed["p_a"]}, pool, sender_phone=phone)
    assert verdict["committed"] is False
    assert verdict["skipped"] == "strong_id_stale"
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
    assert status == "review_pending"


async def test_npwp_company_collision_after_routing_refuses(pool, seed, monkeypatch):
    """Round-3 F1 guilt: the persisted proposal matched npwp→client A uniquely,
    but a COMPANY has acquired the same digits since — the live resolver would
    say cross-table AMBIGUOUS, so revalidation must refuse."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    company_name = f"{seed['tag']}-PT-Collision"
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1, npwp=$2 WHERE id=$3",
            phone,
            seed["npwp_digits"],
            seed["cid_a"],
        )
        await conn.execute(
            "INSERT INTO companies (company_name, npwp_company) VALUES ($1, $2)",
            company_name,
            seed["npwp_digits"],
        )
    try:
        verdict = await aa.try_auto_attach({"id": seed["p_a"]}, pool, sender_phone=phone)
        assert verdict["committed"] is False
        assert verdict["skipped"] == "strong_id_stale"
        assert "company" in verdict["reason"]
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM companies WHERE company_name=$1", company_name
            )


async def test_malformed_matched_value_fails_closed(pool, seed, monkeypatch):
    """Round-3 F4 guilt: a persisted candidate whose matched_value the matcher
    would reject today (14-digit npwp, pre-gate era) must fail closed — even
    when a client card still carries that exact malformed value."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    malformed = str(uuid.uuid4().int)[:14].rjust(14, "9")  # 14 digits: invalid
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1, npwp=$2 WHERE id=$3",
            phone,
            malformed,
            seed["cid_a"],
        )
        await conn.execute(
            "UPDATE document_routing_proposal SET entity_resolution=$1::jsonb WHERE id=$2",
            json.dumps(
                {
                    "decision": "AUTO_ATTACH",
                    "candidates": [
                        {
                            "table": "clients",
                            "id": seed["cid_a"],
                            "method": "npwp",
                            "score": 0.99,
                            "matched_value": malformed,
                        }
                    ],
                }
            ),
            seed["p_a"],
        )

    verdict = await aa.try_auto_attach({"id": seed["p_a"]}, pool, sender_phone=phone)
    assert verdict["committed"] is False
    assert verdict["skipped"] == "strong_id_stale"
    assert "reject" in verdict["reason"]


async def test_leva3_strongid_ownership_moved_refuses_commit(pool, seed, monkeypatch):
    """Round-3 coverage gap: the ownership revalidation must bite in LEVA-3 too
    — name concordant, no phone, but the npwp moved to the OTHER client."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    await _reopen_for_auto(pool, seed["p_b"])
    async with pool.acquire() as conn:
        client_name = await conn.fetchval(
            "SELECT full_name FROM clients WHERE id=$1", seed["cid_b"]
        )
        # doc subject name concords with B, but the npwp is now owned by A
        await conn.execute(
            "UPDATE clients SET npwp=$1 WHERE id=$2",
            seed["npwp_digits"],
            seed["cid_a"],
        )
        await conn.execute(
            "UPDATE intake_queue SET stage_output = stage_output || $1::jsonb "
            "WHERE id = (SELECT queue_id FROM document_routing_proposal WHERE id=$2)",
            json.dumps({"extract": {"fields": {"name": {"value": client_name}}}}),
            seed["p_b"],
        )

    verdict = await aa.try_nameid_auto_attach({"id": seed["p_b"]}, pool)
    assert verdict["committed"] is False
    assert verdict["skipped"] == "strong_id_stale"
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_b"]
        )
    assert status == "review_pending"


async def test_pre_m248_candidate_shape_fails_closed(pool, seed, monkeypatch):
    """A proposal whose candidates carry NO method/matched_value (pre-m248 shape,
    arbitrarily old backlog rows) cannot be ownership-revalidated → the gate
    fails CLOSED to human review instead of trusting stale evidence."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    phone = "62" + str(uuid.uuid4().int)[:9]
    await _reopen_for_auto(pool, seed["p_a"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", phone, seed["cid_a"]
        )
        await conn.execute(
            "UPDATE document_routing_proposal SET entity_resolution=$1::jsonb WHERE id=$2",
            json.dumps(
                {
                    "decision": "AUTO_ATTACH",
                    "candidates": [{"table": "clients", "id": seed["cid_a"]}],
                }
            ),
            seed["p_a"],
        )

    verdict = await aa.try_auto_attach({"id": seed["p_a"]}, pool, sender_phone=phone)
    assert verdict["committed"] is False
    assert verdict["skipped"] == "strong_id_stale"
    assert "needs human" in verdict["reason"]


async def test_delivery_resolves_by_selected_client_phone_not_sender(pool, seed, monkeypatch):
    """Round-6 F5 guilt: a forwarder A sends B's document; after review assigns
    it to B, Fly identity must be resolved by B's OWN canonical phone — never by
    the transport sender phone (which belongs to A)."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    client_phone = "62" + str(uuid.uuid4().int)[:9]
    sender_phone = "62" + str(uuid.uuid4().int + 7)[:9]
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2",
            client_phone,
            seed["cid_a"],
        )
        await conn.execute(
            "UPDATE intake_queue SET sender_phone=$1 "
            "WHERE id=(SELECT queue_id FROM document_routing_proposal WHERE id=$2)",
            sender_phone,
            seed["p_a"],
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f5")

    out = await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert captured["sender_phone"] == client_phone  # the SELECTED client's phone
    assert captured["sender_phone"] != sender_phone
    assert out["status"] == "identity_unresolved"


async def test_delivery_refuses_phone_shared_by_another_live_local_client(pool, seed, monkeypatch):
    """Round-7 F11 guilt: the selected client's phone is shared (same canonical
    digits, different formatting) with ANOTHER live local client. Fly may know
    only the other owner and report matched_count=1 — invisible ambiguity. The
    local uniqueness gate must fail CLOSED: no resolution phone flows."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    shared = "62" + str(uuid.uuid4().int)[:9]
    dup_cid: int | None = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE clients SET phone_normalized=$1 WHERE id=$2", shared, seed["cid_a"]
            )
            # Insert via `phone`: the trg_normalize_phone trigger computes
            # phone_normalized (digits) exactly as production does — a direct
            # phone_normalized INSERT would be silently wiped by that trigger.
            dup_cid = await conn.fetchval(
                "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                f"dup-owner-{uuid.uuid4().hex[:8]}",
                "+62 " + shared[2:],
            )
            locked = await conn.fetchrow(
                "SELECT id, queue_id, doc_index, pipeline_version, status, "
                "entity_resolution, routing, commit_gate "
                "FROM document_routing_proposal WHERE id=$1",
                seed["p_a"],
            )
            plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11")

        await crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=SimpleNamespace(doc_id=None, audit_id=None),
        )
        assert captured["sender_phone"] is None  # fail closed, never resolve by a shared phone
    finally:
        if dup_cid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM clients WHERE id=$1", dup_cid)


async def test_delivery_refuses_whatsapp_only_co_owner(pool, seed, monkeypatch):
    """Round-16 F24 guilt: a co-owner that knows the core ONLY through the
    whatsapp column was invisible to the sole-owner gate (2-of-3 columns) —
    on Fly that same core can resolve to THAT client, the exact wrong-attach
    vector. The widened gate must fail CLOSED."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    shared = "62" + str(uuid.uuid4().int)[:9]
    dup_cid: int | None = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE clients SET phone_normalized=$1 WHERE id=$2", shared, seed["cid_a"]
            )
            # The co-owner carries the core ONLY in whatsapp — phone and
            # phone_normalized both stay NULL (no trigger fires on whatsapp).
            dup_cid = await conn.fetchval(
                "INSERT INTO clients (full_name, whatsapp) VALUES ($1,$2) RETURNING id",
                f"wa-co-owner-{uuid.uuid4().hex[:8]}",
                "+62 " + shared[2:],
            )
            check = await conn.fetchrow(
                "SELECT phone, phone_normalized FROM clients WHERE id=$1", dup_cid
            )
            assert check["phone"] is None  # whatsapp-only shape is real
            locked = await conn.fetchrow(
                "SELECT id, queue_id, doc_index, pipeline_version, status, "
                "entity_resolution, routing, commit_gate "
                "FROM document_routing_proposal WHERE id=$1",
                seed["p_a"],
            )
            plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f24")

        await crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=SimpleNamespace(doc_id=None, audit_id=None),
        )
        assert captured["sender_phone"] is None  # whatsapp-only co-owner blocks too
    finally:
        if dup_cid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM clients WHERE id=$1", dup_cid)


async def test_delivery_soft_deleted_phone_duplicate_also_blocks(pool, seed, monkeypatch):
    """Round-8 F11 archive gap: a SOFT-DELETED phone duplicate still blocks —
    the Fly resolver searches archived rows and (by default) can restore one,
    so an archived local co-owner is a reachable wrong-attach vector. ANY other
    owner of the digits, live or archived, must fail CLOSED."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    shared = "62" + str(uuid.uuid4().int)[:9]
    dup_cid: int | None = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE clients SET phone_normalized=$1 WHERE id=$2", shared, seed["cid_a"]
            )
            dup_cid = await conn.fetchval(
                "INSERT INTO clients (full_name, phone, deleted_at) "
                "VALUES ($1,$2,NOW()) RETURNING id",
                f"dup-archived-{uuid.uuid4().hex[:8]}",
                shared,
            )
            locked = await conn.fetchrow(
                "SELECT id, queue_id, doc_index, pipeline_version, status, "
                "entity_resolution, routing, commit_gate "
                "FROM document_routing_proposal WHERE id=$1",
                seed["p_a"],
            )
            plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11b")

        await crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=SimpleNamespace(doc_id=None, audit_id=None),
        )
        assert captured["sender_phone"] is None  # archived co-owner ⇒ fail closed
    finally:
        if dup_cid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM clients WHERE id=$1", dup_cid)


async def test_delivery_blocks_on_stale_normalized_phone_duplicate(pool, seed, monkeypatch):
    """Round-8 F11 stale-normalization gap: a historical co-owner whose
    phone_normalized is MISSING (raw `phone` only) must still block — the CRM
    dedup code coalesces raw phone for exactly this population."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    shared = "62" + str(uuid.uuid4().int)[:9]
    dup_cid: int | None = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE clients SET phone_normalized=$1 WHERE id=$2", shared, seed["cid_a"]
            )
            dup_cid = await conn.fetchval(
                "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                f"dup-stale-{uuid.uuid4().hex[:8]}",
                "+62 " + shared[2:],
            )
            # Simulate the historical stale row: wipe phone_normalized directly
            # (trg_normalize_phone fires only ON UPDATE OF phone, so this sticks).
            await conn.execute(
                "UPDATE clients SET phone_normalized=NULL WHERE id=$1", dup_cid
            )
            locked = await conn.fetchrow(
                "SELECT id, queue_id, doc_index, pipeline_version, status, "
                "entity_resolution, routing, commit_gate "
                "FROM document_routing_proposal WHERE id=$1",
                seed["p_a"],
            )
            plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11c")

        await crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=SimpleNamespace(doc_id=None, audit_id=None),
        )
        assert captured["sender_phone"] is None  # raw-phone co-owner ⇒ fail closed
    finally:
        if dup_cid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM clients WHERE id=$1", dup_cid)


async def test_delivery_blocks_on_trunk_prefix_variant_duplicate(pool, seed, monkeypatch):
    """Round-9 F13 guilt: a co-owner stored with the 0-trunk form (`0812…`)
    of the selected client's 62-form number (`62812…`) is the SAME identity
    per the official CRM dedup — the sole-owner gate must block it."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    tail = str(uuid.uuid4().int)[:9]
    dup_cid: int | None = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE clients SET phone_normalized=$1 WHERE id=$2", "62" + tail, seed["cid_a"]
            )
            dup_cid = await conn.fetchval(
                "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                f"dup-trunk-{uuid.uuid4().hex[:8]}",
                "0" + tail,  # trunk-prefix variant of the SAME number
            )
            locked = await conn.fetchrow(
                "SELECT id, queue_id, doc_index, pipeline_version, status, "
                "entity_resolution, routing, commit_gate "
                "FROM document_routing_proposal WHERE id=$1",
                seed["p_a"],
            )
            plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f13")

        await crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=SimpleNamespace(doc_id=None, audit_id=None),
        )
        assert captured["sender_phone"] is None  # 0812… and 62812… are one owner
    finally:
        if dup_cid is not None:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM clients WHERE id=$1", dup_cid)


async def test_delivery_refuses_diverged_phone_columns(pool, seed, monkeypatch):
    """Round-9 F11 gap-1 guilt: the SELECTED client's own card carries a stale
    non-null phone_normalized that disagrees with raw `phone` — neither value
    can prove the identity, so resolution must fail CLOSED."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    raw_phone = "62" + str(uuid.uuid4().int)[:9]
    stale_norm = "62" + str(uuid.uuid4().int + 31)[:9]
    async with pool.acquire() as conn:
        # First set raw phone (trigger aligns phone_normalized)…
        await conn.execute(
            "UPDATE clients SET phone=$1 WHERE id=$2", "+" + raw_phone, seed["cid_a"]
        )
        # …then simulate the historical stale card: phone_normalized diverges
        # (direct update — the trigger fires only ON UPDATE OF phone).
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", stale_norm, seed["cid_a"]
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11d")

    await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert captured["sender_phone"] is None  # diverged card ⇒ fail closed


async def test_delivery_refuses_unusable_raw_phone(pool, seed, monkeypatch):
    """Round-10 F11 gap-1 residual guilt: raw phone PRESENT but UNUSABLE
    ("12345" — digits below the core threshold) cannot cross-check the
    normalized value; a possibly-stale phone_normalized must NOT be trusted."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    stale_norm = "62" + str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        # Raw first (trigger aligns normalized to '12345'), then the stale-valid
        # normalized via direct update (trigger fires only ON UPDATE OF phone).
        await conn.execute("UPDATE clients SET phone='12345' WHERE id=$1", seed["cid_a"])
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", stale_norm, seed["cid_a"]
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11e")

    await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert captured["sender_phone"] is None  # unusable raw ⇒ cannot cross-check ⇒ closed


async def test_delivery_digitfree_raw_phone_is_absent(pool, seed, monkeypatch):
    """Round-10 F11 gap-1 innocence: a digit-free raw value ("n/a") is not a
    phone CLAIM — normalized-only resolution proceeds."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    valid = "62" + str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        await conn.execute("UPDATE clients SET phone='n/a' WHERE id=$1", seed["cid_a"])
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", valid, seed["cid_a"]
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11f")

    await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert captured["sender_phone"] == valid


async def test_delivery_unicode_digit_raw_phone_is_unusable(pool, seed, monkeypatch):
    """Round-12 F11 Unicode variant guilt: a raw phone made of NON-ASCII digits
    (Arabic-Indic '١٢٣٤٥') is a phone CLAIM that yields no ASCII core — it must
    classify `unusable` and fail delivery closed, never `absent` (which would
    let a valid-but-stale phone_normalized resolve unchecked)."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push
    from backend.services.intake.crm_delivery import _raw_phone_state

    # Unit-level guilt+innocence for the classifier itself.
    assert _raw_phone_state("١٢٣٤٥") == ("unusable", None)
    assert _raw_phone_state("０８１２３") == ("unusable", None)  # full-width
    assert _raw_phone_state("n/a") == ("absent", None)  # digit-free stays absent

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    stale_norm = "62" + str(uuid.uuid4().int)[:9]
    async with pool.acquire() as conn:
        # Raw with Unicode digits (trigger's [^0-9] SQL strip empties it →
        # normalized recomputed empty), then a stale-valid normalized via
        # direct update (trigger fires only ON UPDATE OF phone).
        await conn.execute("UPDATE clients SET phone='١٢٣٤٥' WHERE id=$1", seed["cid_a"])
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", stale_norm, seed["cid_a"]
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f11u")

    await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert captured["sender_phone"] is None  # unicode-digit raw ⇒ unusable ⇒ closed


async def test_upsert_match_sql_finds_raw_only_owner(pool):
    """Round-12 F15: a historical row with a RAW phone and NULL/stale
    phone_normalized must still match by core — the predicate covers BOTH
    columns. Executed against the real SQL; the raw-only shape is built by
    nulling phone_normalized directly (the trigger fires only ON UPDATE OF
    phone, so the NULL sticks)."""
    from backend.app.routers.crm_clients import UPSERT_MATCH_SQL, _normalize_phone_digits

    tail = str(uuid.uuid4().int)[:9]
    cid = None
    try:
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                f"rawonly-{uuid.uuid4().hex[:6]}",
                "0" + tail,
            )
            await conn.execute(
                "UPDATE clients SET phone_normalized = NULL WHERE id=$1", cid
            )
            check = await conn.fetchrow(
                "SELECT phone, phone_normalized FROM clients WHERE id=$1", cid
            )
            assert check["phone_normalized"] is None  # raw-only shape is real
            core = _normalize_phone_digits("62" + tail)
            assert core == tail
            async with conn.transaction():
                rows = await conn.fetch(UPSERT_MATCH_SQL, core)
            assert cid in {r["id"] for r in rows}  # found via the raw column leg
    finally:
        async with pool.acquire() as conn:
            if cid is not None:
                await conn.execute("DELETE FROM clients WHERE id=$1", cid)


async def test_upsert_match_sql_equates_prefix_variants(pool):
    """Round-10 F15: the upsert-by-phone matcher must recognize 0812… and
    62812… as ONE identity — executed against the REAL matcher SQL, so a
    regression to exact-string matching fails here."""
    from backend.app.routers.crm_clients import UPSERT_MATCH_SQL, _normalize_phone_digits

    tail = str(uuid.uuid4().int)[:9]
    ids: list[int] = []
    try:
        async with pool.acquire() as conn:
            for variant in ("0" + tail, "62" + tail):
                ids.append(
                    await conn.fetchval(
                        "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                        f"variant-{variant[:2]}-{uuid.uuid4().hex[:6]}",
                        variant,
                    )
                )
            core = _normalize_phone_digits("62" + tail)
            assert core == tail
            async with conn.transaction():
                rows = await conn.fetch(UPSERT_MATCH_SQL, core)
            found = {r["id"] for r in rows}
            assert set(ids) <= found  # both prefix variants are the same identity
    finally:
        async with pool.acquire() as conn:
            for cid in ids:
                await conn.execute("DELETE FROM clients WHERE id=$1", cid)


def test_phone_core_parity_with_crm_dedup():
    """The delivery gate's `_phone_core` MUST stay behaviourally identical to
    the official CRM dedup `_normalize_phone_digits` (round-9 F13): a drift
    between the two silently re-opens the prefix-equivalence hole."""
    from backend.app.routers.crm_clients import _normalize_phone_digits
    from backend.services.intake.crm_delivery import _phone_core

    corpus = [
        "+62 821-3454-721",
        "0821 3454721",
        "8213454721",
        "62812345678",
        "0812345678",
        "812345678",
        "+62 (0)",
        "12345",  # <6 after strip → None
        "",
        None,
    ]
    for value in corpus:
        assert _phone_core(value) == _normalize_phone_digits(value), value
    # And the equivalence class itself:
    assert _phone_core("0821 3454721") == _phone_core("+62 821-3454-721")


async def test_delivery_holds_phone_advisory_lock_during_push(pool, seed, monkeypatch):
    """Round-8 F12: the resolve→push window must hold the LOCAL phone advisory
    lock (same hashtext key the upsert-by-phone endpoint takes) so
    lock-respecting phone writers are serialized against the cross-DB window."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    client_phone = "62" + str(uuid.uuid4().int)[:9]
    lock_free_during_push: list[bool] = []

    async def _probe_push(**kw):
        async with pool.acquire() as probe_conn:
            async with probe_conn.transaction():
                got = await probe_conn.fetchval(
                    "SELECT pg_try_advisory_xact_lock(hashtext($1))", client_phone
                )
                lock_free_during_push.append(bool(got))
                # The canonical core key must be held too (round-9 F12/F13:
                # this is the key prefix-variant writers converge on).
                got_core = await probe_conn.fetchval(
                    "SELECT pg_try_advisory_xact_lock(hashtext($1))",
                    "phonecore:" + client_phone[2:],
                )
                lock_free_during_push.append(bool(got_core))
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _probe_push)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", client_phone, seed["cid_a"]
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f12")

    await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert lock_free_during_push == [False, False]  # both keys held during push

    # And released afterwards:
    async with pool.acquire() as conn:
        async with conn.transaction():
            assert await conn.fetchval(
                "SELECT pg_try_advisory_xact_lock(hashtext($1))", client_phone
            )


async def test_delivery_flags_phone_owner_divergence_post_upload(pool, seed, monkeypatch, caplog):
    """Round-8 F12 detection layer: a lock-BYPASSING writer that mutates the
    selected client's phone mid-push cannot be prevented, but the post-upload
    re-check must flag the delivery loudly for HITL review."""
    import logging as _logging
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    client_phone = "62" + str(uuid.uuid4().int)[:9]
    hijack_phone = "62" + str(uuid.uuid4().int + 13)[:9]

    async def _mutating_push(**kw):
        # Simulate a writer that does NOT take the phone advisory lock.
        async with pool.acquire() as w_conn:
            await w_conn.execute(
                "UPDATE clients SET phone=$1 WHERE id=$2",
                "+" + hijack_phone,
                seed["cid_a"],
            )
        return crm_push.CrmPushResult(ok=True, status="uploaded", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _mutating_push)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=$1 WHERE id=$2", client_phone, seed["cid_a"]
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f12b")

    with caplog.at_level(_logging.ERROR, logger="zantara.intake.crm_delivery"):
        await crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=SimpleNamespace(doc_id=None, audit_id=None),
        )
    assert any("phone_owner_diverged_post_upload" in r.message for r in caplog.records)


async def test_delivery_fails_closed_when_selected_client_has_no_phone(pool, seed, monkeypatch):
    """Round-6 F5 innocence: selected client with NO phone on the card → the
    push receives sender_phone=None and delivery fails closed downstream —
    the transport sender phone is never used as a fallback."""
    from types import SimpleNamespace

    from backend.services.intake import crm_delivery, crm_push

    captured: dict = {}

    async def _capture_push(**kw):
        captured.update(kw)
        return crm_push.CrmPushResult(ok=False, status="identity_unresolved", detail="t")

    monkeypatch.setattr(crm_push, "push_committed_document", _capture_push)

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET phone_normalized=NULL WHERE id=$1", seed["cid_a"]
        )
        await conn.execute(
            "UPDATE intake_queue SET sender_phone=$1 "
            "WHERE id=(SELECT queue_id FROM document_routing_proposal WHERE id=$2)",
            "628123450000",
            seed["p_a"],
        )
        locked = await conn.fetchrow(
            "SELECT id, queue_id, doc_index, pipeline_version, status, "
            "entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE id=$1",
            seed["p_a"],
        )
        plan = await intake_writer.plan_commit(locked, conn, committed_by="test-f5b")

    await crm_delivery.deliver_committed_to_crm(
        pool=pool,
        queue_id=plan.queue_id,
        plan=plan,
        result=SimpleNamespace(doc_id=None, audit_id=None),
    )
    assert captured["sender_phone"] is None


async def test_enrichment_failure_never_rolls_back_document_commit(pool, seed, monkeypatch):
    """Savepoint proof (Codex finding 2): enrichment SQL blowing up mid-commit must
    NOT abort the document write — the enricher runs in a nested transaction and
    the commit proceeds without the card update."""
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")

    async def _boom(conn, client_id, doc_type, fields):
        # force a REAL Postgres error inside the TX (aborts it without a savepoint)
        await conn.execute("SELECT * FROM table_that_does_not_exist_xyz")
        return {}

    monkeypatch.setattr(intake_writer, "enrich_client_from_extracted_fields", _boom)

    async with pool.acquire() as conn:
        await _set_passport_proposal(conn, seed["p_a"], seed["cid_a"])
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.post(f"/api/intake/review/{seed['p_a']}/approve", json={})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "committed"

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_a"]
        )
        doc_count = await conn.fetchval(
            "SELECT count(*) FROM documents WHERE client_id=$1", seed["cid_a"]
        )
        passport_after = await conn.fetchval(
            "SELECT passport_number FROM clients WHERE id=$1", seed["cid_a"]
        )
    assert status == "routed"
    assert doc_count == 1
    assert passport_after is None  # enrichment rolled back alone, document survived


async def test_leva3_nameid_holds_on_name_contradiction(pool, seed, monkeypatch):
    """Guilt twin (the live 161274 class): npwp strong-id resolves uniquely but
    the doc subject name affirmatively contradicts the client (overlap 0) → the
    gate HOLDS: no commit, proposal stays review_pending, no committed audit row.
    A readable disagreeing name is a signal, not an absence."""
    from backend.services.intake import auto_attach as aa

    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    monkeypatch.setenv("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", "1")
    _stub_delivery(monkeypatch)

    await _reopen_for_auto(pool, seed["p_b"])
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE intake_queue SET stage_output = stage_output || $1::jsonb "
            "WHERE id = (SELECT queue_id FROM document_routing_proposal WHERE id=$2)",
            json.dumps(
                {
                    "extract": {
                        "fields": {
                            "name": {"value": "COMPLETELY DIFFERENT PERSON", "confidence": 0.95}
                        }
                    }
                }
            ),
            seed["p_b"],
        )

    verdict = await aa.try_nameid_auto_attach({"id": seed["p_b"]}, pool)
    assert verdict["committed"] is False
    assert verdict["skipped"] == "not_concordant"

    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", seed["p_b"]
        )
        committed_rows = await conn.fetchval(
            "SELECT count(*) FROM intake_commit_audit WHERE proposal_id=$1 AND outcome='committed'",
            seed["p_b"],
        )
    assert status == "review_pending"
    assert committed_rows == 0


async def test_enrichment_npwp_full_number_written_fragment_never(pool, seed, monkeypatch):
    """npwp identity-backfill wire (m248): a COMPLETE 15/16-digit npwp is written
    digits-canonical; a partial OCR fragment or an overlong garble must NEVER be
    stored — it would pollute the key book the strong-id matcher corroborates
    against (guilt AND innocence, cicatrix #3)."""
    from backend.services.intake.client_enricher import enrich_client_from_extracted_fields

    async with pool.acquire() as conn:
        # formatted legacy 15-digit → stored as bare digits (innocence: full read lands)
        written = await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "npwp", {"npwp_number": {"value": "01.234.567.8-901.234"}}
        )
        assert written.get("npwp") == "012345678901234"
        # 16-digit NIK-format → stored
        written16 = await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "npwp", {"npwp_number": {"value": "0123456789012345"}}
        )
        assert written16.get("npwp") == "0123456789012345"
        # 10-digit fragment → dropped (guilt), card keeps the previous full value
        frag = await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "npwp", {"npwp_number": {"value": "0123456789"}}
        )
        # 17-digit concatenation garble → dropped
        garble = await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "npwp", {"npwp_number": {"value": "01234567890123499"}}
        )
        # Unicode digits are NOT ASCII digits: the [^0-9] projection (mirror of the
        # matcher SQL class) strips them, leaving 13 ASCII digits → dropped
        unicode_mix = await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "npwp", {"npwp_number": {"value": "٠1234567890123٤5"}}
        )
        row = await conn.fetchrow("SELECT npwp FROM clients WHERE id=$1", seed["cid_a"])
    assert frag == {}
    assert garble == {}
    assert unicode_mix == {}
    assert row["npwp"] == "0123456789012345"


async def test_enrichment_skips_unknown_doctype_and_bad_date(pool, seed, monkeypatch):
    """Innocence test: unknown doc_type → no-op; a garbage date → that field skipped,
    others still written (never raises, never rolls back the document)."""
    from backend.services.intake.client_enricher import enrich_client_from_extracted_fields

    async with pool.acquire() as conn:
        # unknown doc_type → nothing
        assert (
            await enrich_client_from_extracted_fields(
                conn, seed["cid_a"], "akta_pendirian", {"x": {"value": "y"}}
            )
            == {}
        )
        # passport with a garbage expiry → expiry skipped, passport_number still written
        written = await enrich_client_from_extracted_fields(
            conn,
            seed["cid_a"],
            "passport",
            {"passport_no": {"value": "YC9999999"}, "expiry": {"value": "not-a-date"}},
        )
    assert written.get("passport_number") == "YC9999999"
    assert "passport_expiry" not in written


async def test_dup_owner_sql_sees_raw_phone_behind_stale_normalized(pool):
    """Round-13 F16 guilt 1: with raw phone=A and a stale non-null
    phone_normalized=B, the old COALESCE hid A entirely — DUP_OWNER_SQL must
    find the owner via the raw column independently."""
    from backend.db.repositories.client_repository import (
        DUP_OWNER_SQL,
        incoming_phone_cores,
    )

    tail_a = str(uuid.uuid4().int)[:9]
    stale_b = "62" + str(uuid.uuid4().int)[:9]
    cid = None
    try:
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                f"stalemask-{uuid.uuid4().hex[:6]}",
                "0" + tail_a,
            )
            # Stale divergent normalized via direct update (trigger fires only
            # ON UPDATE OF phone, so the bogus value sticks).
            await conn.execute(
                "UPDATE clients SET phone_normalized=$1 WHERE id=$2", stale_b, cid
            )
            cores = incoming_phone_cores("62" + tail_a, None)
            assert cores == [tail_a]
            dup = await conn.fetchrow(DUP_OWNER_SQL, cores)
            assert dup is not None and dup["id"] == cid  # raw leg found it
    finally:
        async with pool.acquire() as conn:
            if cid is not None:
                await conn.execute("DELETE FROM clients WHERE id=$1", cid)


async def test_dup_owner_sql_finds_whatsapp_only_owner(pool):
    """Round-13 F16 guilt 2: an owner known ONLY by whatsapp was invisible to
    the dedup search — the query must examine the whatsapp column too, and
    the incoming whatsapp core must participate in the lookup."""
    from backend.db.repositories.client_repository import (
        DUP_OWNER_SQL,
        incoming_phone_cores,
    )

    tail = str(uuid.uuid4().int)[:9]
    cid = None
    try:
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, whatsapp) VALUES ($1,$2) RETURNING id",
                f"waonly-{uuid.uuid4().hex[:6]}",
                "+62 " + tail,
            )
            # Incoming payload duplicates the number in the WHATSAPP field.
            cores = incoming_phone_cores(None, "0" + tail)
            dup = await conn.fetchrow(DUP_OWNER_SQL, cores)
            assert dup is not None and dup["id"] == cid
    finally:
        async with pool.acquire() as conn:
            if cid is not None:
                await conn.execute("DELETE FROM clients WHERE id=$1", cid)


async def test_upsert_match_sql_finds_whatsapp_only_owner(pool):
    """Round-15 F21: whatsapp is an OWNERSHIP column — an owner known only
    by whatsapp must be visible to the upsert-by-phone resolver, or two
    writers create a split identity that the dedup gates then treat as
    ambiguous forever. Executed against the real SQL's whatsapp leg."""
    from backend.app.routers.crm_clients import UPSERT_MATCH_SQL, _normalize_phone_digits

    tail = str(uuid.uuid4().int)[:9]
    cid = None
    try:
        async with pool.acquire() as conn:
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, whatsapp) VALUES ($1,$2) RETURNING id",
                f"waup-{uuid.uuid4().hex[:6]}",
                "0" + tail,
            )
            check = await conn.fetchrow(
                "SELECT phone, phone_normalized FROM clients WHERE id=$1", cid
            )
            assert check["phone"] is None  # whatsapp-only shape is real
            core = _normalize_phone_digits("62" + tail)
            assert core == tail
            async with conn.transaction():
                rows = await conn.fetch(UPSERT_MATCH_SQL, core)
            assert cid in {r["id"] for r in rows}  # found via the whatsapp leg
    finally:
        async with pool.acquire() as conn:
            if cid is not None:
                await conn.execute("DELETE FROM clients WHERE id=$1", cid)


async def test_core_owner_ids_sql_sees_archived_coowner(pool):
    """Round-15 F22: the sole-ownership resolver must see ARCHIVED co-owners
    too — the delivery resolver refuses an ambiguous core whether the other
    owner is live or soft-deleted (reject_ambiguous + restore_if_archived
    both key off existence, not liveness), so the upload re-proof must apply
    the same parity or a stale token slips through on an archived twin."""
    from backend.db.repositories.client_repository import CORE_OWNER_IDS_SQL

    tail = str(uuid.uuid4().int)[:9]
    ids: list[int] = []
    try:
        async with pool.acquire() as conn:
            ids.append(
                await conn.fetchval(
                    "INSERT INTO clients (full_name, phone) VALUES ($1,$2) RETURNING id",
                    f"live-{uuid.uuid4().hex[:6]}",
                    "0" + tail,
                )
            )
            ids.append(
                await conn.fetchval(
                    "INSERT INTO clients (full_name, phone, deleted_at)"
                    " VALUES ($1,$2, now()) RETURNING id",
                    f"arch-{uuid.uuid4().hex[:6]}",
                    "62" + tail,
                )
            )
            rows = await conn.fetch(CORE_OWNER_IDS_SQL, [tail])
            owners = {r["id"] for r in rows}
            assert set(ids) <= owners  # archived co-owner is NOT invisible
    finally:
        async with pool.acquire() as conn:
            for cid in ids:
                await conn.execute("DELETE FROM clients WHERE id=$1", cid)

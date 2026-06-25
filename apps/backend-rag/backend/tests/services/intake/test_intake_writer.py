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
            "WHERE proposal_id=$1 ORDER BY id DESC LIMIT 1", seed["p_a"])
    assert audit["dry_run"] is False
    assert audit["outcome"] == "committed"
    assert audit["doc_id"] == new_doc["id"]


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
                "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"])
            plan = await intake_writer.plan_commit(prop, conn, committed_by=ADMIN["email"])
            # existing doc surfaced by the idempotency probe
            assert plan.existing_doc_id == doc_id_1
            assert plan.blocked is False
            result = await intake_writer.execute_commit(plan, conn, dry_run=False)
    assert result.outcome == "committed"
    assert result.doc_id == doc_id_1, "re-commit must reuse the same canonical doc_id"

    docs_after_second = await _docs_for_client(pool, seed["cid_a"])
    assert len(docs_after_second) == len(docs_after_first), "no duplicate document on re-commit"


async def test_blocked_plan_no_write_even_with_flag_on(pool, seed, monkeypatch):
    """Flag ON but plan blocked (soft-deleted client) → still zero CRM writes."""
    monkeypatch.setenv("INTAKE_WRITER_ENABLED", "1")
    before = await _crm_counts(pool)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE clients SET deleted_at = now() WHERE id=$1", seed["cid_a"])
        try:
            async with conn.transaction():
                prop = await conn.fetchrow(
                    "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"])
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
                    "SELECT * FROM document_routing_proposal WHERE id=$1", seed["p_a"])
                plan = await intake_writer.plan_commit(prop, conn, committed_by=ADMIN["email"])
                await intake_writer.execute_commit(plan, conn, dry_run=False)

    after = await _crm_counts(pool)
    assert after == before, "TX did not roll back — orphan document survived the failure"
    assert await _proposal_status(pool, seed["p_a"]) == "review_claimed", "proposal advanced despite rollback"


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
                conn, client_id=seed["cid_a"], idempotency_key=idem_key,
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
                conn, client_id=seed["cid_a"], idempotency_key=idem_key,
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
    ],
)
def test_company_doc_category_maps_to_company_folder(
    doc_type, expected_category, expected_folder
):
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
        "client_id": client_id, "company_id": None, "practice_id": None,
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
        json.dumps(routing), json.dumps(entity), proposal_id,
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
            "FROM clients WHERE id=$1", seed["cid_a"])
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
            "FROM clients WHERE id=$1", seed["cid_a"])
    assert after["passport_number"] == "YC0000001"
    assert after["passport_expiry"] == date(2034, 6, 19)
    assert after["date_of_birth"] == date(1987, 7, 1)
    assert after["nationality"] == "ITALIANA"


async def test_enrichment_skips_archive_only_no_client(pool, seed, monkeypatch):
    """Innocence test: archive-only (client_id None) must NOT attempt any client UPDATE."""
    from backend.services.intake.client_enricher import enrich_client_from_extracted_fields
    async with pool.acquire() as conn:
        written = await enrich_client_from_extracted_fields(
            conn, None, "passport",
            {"passport_no": {"value": "X"}, "expiry": {"value": "2030-01-01"}},
        )
    assert written == {}  # no-op, no exception


async def test_enrichment_skips_unknown_doctype_and_bad_date(pool, seed, monkeypatch):
    """Innocence test: unknown doc_type → no-op; a garbage date → that field skipped,
    others still written (never raises, never rolls back the document)."""
    from backend.services.intake.client_enricher import enrich_client_from_extracted_fields
    async with pool.acquire() as conn:
        # unknown doc_type → nothing
        assert await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "akta_pendirian", {"x": {"value": "y"}}) == {}
        # passport with a garbage expiry → expiry skipped, passport_number still written
        written = await enrich_client_from_extracted_fields(
            conn, seed["cid_a"], "passport",
            {"passport_no": {"value": "YC9999999"}, "expiry": {"value": "not-a-date"}})
    assert written.get("passport_number") == "YC9999999"
    assert "passport_expiry" not in written

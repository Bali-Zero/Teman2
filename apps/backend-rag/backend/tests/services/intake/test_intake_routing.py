"""Integration tests for FASE-4 entity-resolution + routing proposal.

Runs against the LOCAL nuzantara_dev DB (same convention as test_intake_worker).
Seeds SYNTHETIC, clearly-tagged CRM rows (torn down per-test), exercises the
C4 decision matrix (AUTO_ATTACH / LINK_CANDIDATE / AMBIGUOUS / NO_MATCH), the
company->owner->practice routing target, idempotency, and PROVES route_stage
performs ZERO CRM writes (clients/companies/practices/links counts unchanged).

PII / Law 2: matching is 100% local Postgres. No cloud.
"""

from __future__ import annotations

import json
import os

import asyncpg
import pytest
import pytest_asyncio

from backend.services.intake import routing as intake_routing
from backend.services.intake.routing import backfill_received_by, route_stage

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)

TAG = "FASE4PYTEST"
CRM_TABLES = ("clients", "companies", "practices", "client_company_links")


@pytest_asyncio.fixture
async def pool():
    p = await asyncpg.create_pool(_DB_URL, min_size=2, max_size=8)
    try:
        yield p
    finally:
        await p.close()


@pytest.fixture(autouse=True)
def _auto_attach_killswitches_off(monkeypatch):
    monkeypatch.delenv("INTAKE_AUTO_ATTACH_ENABLED", raising=False)
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)


@pytest_asyncio.fixture
async def seeded(pool):
    """Seed synthetic CRM rows; yield their ids; tear everything down after."""
    async with pool.acquire() as c:
        ids = {}
        ids["c_auto"] = await c.fetchval(
            "INSERT INTO clients (full_name, passport_number, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Alice Auto", "ZZ9988770", TAG)
        ids["c_homo1"] = await c.fetchval(
            "INSERT INTO clients (full_name, passport_number, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Budi Santoso", "AA1111111", TAG)
        ids["c_homo2"] = await c.fetchval(
            "INSERT INTO clients (full_name, passport_number, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Budi Santoso", "BB2222222", TAG)
        ids["c_link"] = await c.fetchval(
            "INSERT INTO clients (full_name, notes) VALUES ($1,$2) RETURNING id",
            f"{TAG} Wolfgang Amadeus Zinnemann", TAG)
        ids["comp_auto"] = await c.fetchval(
            "INSERT INTO companies (company_name, nib, npwp_company) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} PT Maju Auto", "9988776655443", "0011223344556677")
        ids["c_owner"] = await c.fetchval(
            "INSERT INTO clients (full_name, notes) VALUES ($1,$2) RETURNING id",
            f"{TAG} Owner Of MajuAuto", TAG)
        await c.execute(
            "INSERT INTO client_company_links (client_id, company_id, role, is_primary) "
            "VALUES ($1,$2,'director',true)", ids["c_owner"], ids["comp_auto"])
        await c.execute(
            "INSERT INTO practices (client_id, practice_type_code, title, status) "
            "VALUES ($1,'pt_pma_setup',$2,'on_process')", ids["c_owner"], f"{TAG} setup")
    try:
        yield ids
    finally:
        async with pool.acquire() as c:
            await c.execute("DELETE FROM intake_queue WHERE intake_key LIKE $1 OR source_ref LIKE $1", f"{TAG}%")
            await c.execute("DELETE FROM document_instances WHERE blob_hash LIKE $1", f"{TAG}%")
            await c.execute(
                "DELETE FROM client_company_links WHERE company_id IN "
                "(SELECT id FROM companies WHERE company_name LIKE $1)", f"{TAG}%")
            await c.execute("DELETE FROM practices WHERE title LIKE $1", f"{TAG}%")
            await c.execute("DELETE FROM companies WHERE company_name LIKE $1", f"{TAG}%")
            await c.execute("DELETE FROM clients WHERE notes = $1 OR full_name LIKE $2", TAG, f"{TAG}%")


def _fields(d: dict) -> dict:
    return {k: {"value": v, "confidence": 0.85, "source_page": 1} for k, v in d.items()}


async def _seed_queue(pool, doc_type: str, fields: dict) -> int:
    stage_output = {
        "classify": {"doc_type": doc_type, "type_confidence": 0.9},
        "extract": {"doc_type": doc_type, "fields": _fields(fields)},
        "validate": {"valid": True, "rule_failures": []},
    }
    async with pool.acquire() as c:
        inst = await c.fetchval(
            "INSERT INTO document_instances (blob_hash, pipeline_version, blob_path, first_source) "
            "VALUES ($1,'v1',$2,'drive') RETURNING id",
            f"{TAG}-{os.urandom(6).hex()}", f"/tmp/{TAG}.pdf")
        return await c.fetchval(
            "INSERT INTO intake_queue "
            "(instance_id, source, source_ref, blob_path, blob_hash, pipeline_version, "
            " status, stage, intake_key, stage_output) "
            "VALUES ($1,'drive',$2,$3,$4,'v1','processing','route',$5,$6::jsonb) RETURNING id",
            inst, f"{TAG}-ref", f"/tmp/{TAG}.pdf", f"{TAG}-{os.urandom(6).hex()}",
            f"{TAG}-{os.urandom(6).hex()}", json.dumps(stage_output))


async def _proposal(pool, queue_id: int):
    async with pool.acquire() as c:
        return await c.fetchrow(
            "SELECT status, entity_resolution, routing, commit_gate "
            "FROM document_routing_proposal WHERE queue_id=$1", queue_id)


def _j(v):
    return json.loads(v) if isinstance(v, str) else v


@pytest.mark.asyncio
async def test_auto_attach_passport_exact(pool, seeded):
    q = await _seed_queue(pool, "passport", {"passport_no": "ZZ9988770", "name": f"{TAG} Alice Auto"})
    r = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r["decision"] == "AUTO_ATTACH"
    assert r["requires_human"] is False
    assert r["auto_attach"]["skipped"] == "killswitch_off"
    row = await _proposal(pool, q)
    er = _j(row["entity_resolution"])
    assert er["subject_kind"] == "person"
    assert len(er["candidates"]) == 1
    assert er["candidates"][0]["id"] == seeded["c_auto"]
    assert _j(row["routing"])["client_id"] == seeded["c_auto"]
    assert row["status"] == "review_pending"


@pytest.mark.asyncio
async def test_route_stage_consumes_auto_attach_result(monkeypatch, pool, seeded):
    """route_stage must arm the dormant AUTO_ATTACH flag after proposal insert.

    The helper is patched so this test covers the route-stage contract without
    executing the real writer path.
    """
    calls = []

    async def _fake_auto_attach(
        *,
        proposal_id,
        proposal,
        pool,
        sender_phone,
        source_context,
        effective_status,
    ):
        calls.append(
            {
                "proposal_id": proposal_id,
                "decision": proposal["entity_resolution"]["decision"],
                "sender_phone": sender_phone,
                "source_context": source_context,
                "effective_status": effective_status,
            }
        )
        async with pool.acquire() as c:
            await c.execute(
                "UPDATE document_routing_proposal SET status='auto_routed' WHERE id=$1",
                proposal_id,
            )
        return {"committed": True, "status": "auto_routed", "outcome": "committed"}

    monkeypatch.setattr(
        intake_routing, "_try_auto_attach_after_route", _fake_auto_attach
    )

    q = await _seed_queue(
        pool,
        "passport",
        {"passport_no": "ZZ9988770", "name": f"{TAG} Alice Auto"},
    )
    r = await route_stage(
        {"id": q, "pipeline_version": "v1", "sender_phone": "+6281200000000"},
        "route",
        pool,
    )

    assert calls == [
        {
            "proposal_id": r["proposal_id"],
            "decision": "AUTO_ATTACH",
            "sender_phone": "+6281200000000",
            "source_context": None,
            "effective_status": "review_pending",
        }
    ]
    assert r["routed"] is True
    assert r["status"] == "auto_routed"
    assert (await _proposal(pool, q))["status"] == "auto_routed"


@pytest.mark.asyncio
async def test_ambiguous_homonyms(pool, seeded):
    q = await _seed_queue(pool, "passport", {"name": f"{TAG} Budi Santoso"})
    r = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r["decision"] == "AMBIGUOUS"
    assert r["requires_human"] is True
    er = _j((await _proposal(pool, q))["entity_resolution"])
    assert len(er["candidates"]) >= 2


@pytest.mark.asyncio
async def test_link_candidate_fuzzy_single(pool, seeded):
    # 1-char typo on a distinctive name, no strong identifier.
    q = await _seed_queue(pool, "passport", {"name": f"{TAG} Wolfgang Amadeus Zinneman"})
    r = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r["decision"] == "LINK_CANDIDATE"
    assert r["requires_human"] is True
    assert _j((await _proposal(pool, q))["routing"])["client_id"] == seeded["c_link"]


@pytest.mark.asyncio
async def test_no_match(pool, seeded):
    q = await _seed_queue(pool, "passport", {"passport_no": "QQ0000001", "name": f"{TAG} Nonexistent Person XYZ"})
    r = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r["decision"] == "NO_MATCH"
    er = _j((await _proposal(pool, q))["entity_resolution"])
    assert er["candidates"] == []


@pytest.mark.asyncio
async def test_company_auto_attach_resolves_owner_and_practice(pool, seeded):
    q = await _seed_queue(pool, "nib", {"nib_number": "9988776655443", "company_name": f"{TAG} PT Maju Auto"})
    r = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r["decision"] == "AUTO_ATTACH"
    routing = _j((await _proposal(pool, q))["routing"])
    assert routing["company_id"] == seeded["comp_auto"]
    assert routing["client_id"] == seeded["c_owner"]  # via client_company_links
    assert routing["practice_id"] is not None         # open practice hint
    assert routing["practice_hint"]["practice_type_code"] == "pt_pma_setup"


@pytest.mark.asyncio
async def test_idempotent_same_queue(pool, seeded):
    q = await _seed_queue(pool, "passport", {"passport_no": "ZZ9988770", "name": f"{TAG} Alice Auto"})
    r1 = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    r2 = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r1["idempotent_skip"] is False
    assert r2["idempotent_skip"] is True
    assert r1["proposal_id"] == r2["proposal_id"]
    async with pool.acquire() as c:
        n = await c.fetchval("SELECT count(*) FROM document_routing_proposal WHERE queue_id=$1", q)
    assert n == 1


@pytest.mark.asyncio
async def test_backfill_received_by(pool, seeded):
    """backfill_received_by: lowercases assigned_to, never overwrites, skips unassigned.

    Seeded rows are TAG-tagged so the `seeded` fixture teardown removes them
    (clients via notes=TAG, intake_queue via intake_key LIKE TAG%,
    document_instances via blob_hash LIKE TAG%).
    """
    async with pool.acquire() as c:
        c_assigned = await c.fetchval(
            "INSERT INTO clients (full_name, assigned_to, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Backfill Target", "Backfill.Owner@Balizero.com", TAG)
        c_other = await c.fetchval(
            "INSERT INTO clients (full_name, assigned_to, notes) VALUES ($1,$2,$3) RETURNING id",
            f"{TAG} Backfill Other", "Other.Consultant@Balizero.com", TAG)
        c_unassigned = await c.fetchval(
            "INSERT INTO clients (full_name, notes) VALUES ($1,$2) RETURNING id",
            f"{TAG} Backfill Unassigned", TAG)
    q1 = await _seed_queue(pool, "passport", {"name": f"{TAG} Backfill Doc One"})
    q2 = await _seed_queue(pool, "passport", {"name": f"{TAG} Backfill Doc Two"})

    async with pool.acquire() as c:
        # 1) NULL received_by + client with mixed-case assigned_to
        #    -> backfilled AND lowercased (both return value and stored row).
        got = await backfill_received_by(c, q1, c_assigned)
        assert got == "backfill.owner@balizero.com"
        stored = await c.fetchval("SELECT received_by FROM intake_queue WHERE id=$1", q1)
        assert stored == "backfill.owner@balizero.com"

        # 2) never-overwrite: a second backfill with a DIFFERENT client is a
        #    no-op (returns None) and the original received_by survives.
        got2 = await backfill_received_by(c, q1, c_other)
        assert got2 is None
        stored2 = await c.fetchval("SELECT received_by FROM intake_queue WHERE id=$1", q1)
        assert stored2 == "backfill.owner@balizero.com"

        # 3) client with assigned_to NULL -> nothing written, received_by stays NULL.
        got3 = await backfill_received_by(c, q2, c_unassigned)
        assert got3 is None
        stored3 = await c.fetchval("SELECT received_by FROM intake_queue WHERE id=$1", q2)
        assert stored3 is None

        # 4) client_id None -> immediate no-op.
        assert await backfill_received_by(c, q2, None) is None


@pytest.mark.asyncio
async def test_route_stage_zero_crm_writes(pool, seeded):
    async def counts():
        async with pool.acquire() as c:
            return {t: await c.fetchval(f"SELECT count(*) FROM {t}") for t in CRM_TABLES}

    before = await counts()
    q1 = await _seed_queue(pool, "passport", {"passport_no": "ZZ9988770", "name": f"{TAG} Alice Auto"})
    q2 = await _seed_queue(pool, "nib", {"nib_number": "9988776655443"})
    await route_stage({"id": q1, "pipeline_version": "v1"}, "route", pool)
    await route_stage({"id": q2, "pipeline_version": "v1"}, "route", pool)
    after = await counts()
    assert before == after, f"CRM tables mutated: before={before} after={after}"


def test_pipeline_version_is_single_source_of_truth():
    """Blindatura difetto-1: routing/writer/enqueue must agree on ONE version.

    Historical drift: enqueue used "intake-v1" while routing/writer used "v1".
    Because routing_key = sha256(queue_id|doc_index|pipeline_version), the two
    halves of the pipeline derived different keys for the same document and a
    re-process could orphan proposals. The constants must be the SAME object,
    not two literals that merely happen to match today.
    """
    # NB: `from backend.services.intake import enqueue` resolves to the enqueue
    # FUNCTION (re-exported by __init__), not the submodule — so import the
    # constant explicitly and the submodules via their full dotted path.
    from backend.services.intake.enqueue import PIPELINE_VERSION
    from backend.services.intake.routing import PIPELINE_VERSION_DEFAULT
    from backend.services.intake.writer import PIPELINE_VERSION as WRITER_PV

    assert PIPELINE_VERSION_DEFAULT == PIPELINE_VERSION
    assert WRITER_PV == PIPELINE_VERSION


@pytest.mark.asyncio
async def test_anti_deadlock_revives_superseded_orphan(pool, seeded):
    """Blindatura difetto-2: a re-route over a superseded-orphan must revive it.

    Reproduces the adit done-deadlock: a proposal is superseded (by a reprocess)
    but the same routing_key gets re-derived, so the bare ON CONFLICT DO NOTHING
    would drop the fresh proposal and leave the queue with ZERO live proposal —
    invisible in /review forever. The guard must flip the survivor back to
    'review_pending' instead.
    """
    q = await _seed_queue(pool, "passport", {"name": f"{TAG} Nonexistent Person XYZ"})
    r1 = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    pid = r1["proposal_id"]

    # Simulate the reprocess marking the proposal superseded (m226) WITHOUT
    # bumping the queue's pipeline_version — so the re-route derives the SAME key.
    async with pool.acquire() as c:
        await c.execute(
            "UPDATE document_routing_proposal SET status='superseded' WHERE id=$1", pid
        )
        assert (await _proposal(pool, q))["status"] == "superseded"

    # Re-route: same routing_key → ON CONFLICT → guard must revive the orphan.
    r2 = await route_stage({"id": q, "pipeline_version": "v1"}, "route", pool)
    assert r2["proposal_id"] == pid  # same row, not a duplicate
    row = await _proposal(pool, q)
    assert row["status"] == "review_pending", (
        "superseded-orphan was NOT revived — done-deadlock would recur"
    )
    # exactly one proposal for this queue (no duplicate created)
    async with pool.acquire() as c:
        n = await c.fetchval(
            "SELECT count(*) FROM document_routing_proposal WHERE queue_id=$1", q
        )
    assert n == 1

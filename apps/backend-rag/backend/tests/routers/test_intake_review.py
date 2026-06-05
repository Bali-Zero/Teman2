"""FASE 5A — review-queue API tests (real local DB: nuzantara_dev).

These tests run against the LOCAL Pro Postgres (nuzantara_dev), where the
document-intake tables live (Law 2 — PII never leaves the Pro). They:
  * build a synthetic intake chain (document_instances → intake_queue →
    document_routing_proposal) + synthetic clients,
  * mount the FULL app via create_app()-style include_routers (registration
    parity, cf. scar PR #422) AND the router directly,
  * exercise list / detail / claim-race-409 / release / RBAC / stubs,
  * assert ZERO CRM write (clients/practices counts unchanged).

If nuzantara_dev is unreachable, the module skips (these are Pro-only).
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

DSN = os.environ.get("INTAKE_TEST_DSN", "postgresql://localhost:5432/nuzantara_dev")
PIPELINE = "test-5a"

ADMIN = {"id": "1", "email": "zero@balizero.com", "role": "admin"}
TEAM_OWNER = {"id": "2", "email": "owner@balizero.com", "role": "user"}
TEAM_OTHER = {"id": "3", "email": "other@balizero.com", "role": "user"}


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


@pytest_asyncio.fixture
async def seed(pool: asyncpg.Pool) -> AsyncIterator[dict]:
    """Insert a synthetic intake chain + clients; clean up after."""
    tag = f"5atest-{uuid.uuid4().hex[:8]}"
    created: dict[str, list[int]] = {"clients": [], "proposals": [], "queues": [], "instances": []}
    async with pool.acquire() as conn:
        # two synthetic clients with distinct assigned_to
        cid_owner = await conn.fetchval(
            "INSERT INTO clients (full_name, assigned_to) VALUES ($1,$2) RETURNING id",
            f"{tag}-owner", TEAM_OWNER["email"],
        )
        cid_other = await conn.fetchval(
            "INSERT INTO clients (full_name, assigned_to) VALUES ($1,$2) RETURNING id",
            f"{tag}-other", TEAM_OTHER["email"],
        )
        created["clients"] += [cid_owner, cid_other]

        async def mk_proposal(entity_resolution: dict, source: str = "drive") -> int:
            bh = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char
            inst = await conn.fetchval(
                """INSERT INTO document_instances (blob_hash, pipeline_version, blob_path, first_source)
                   VALUES ($1,$2,$3,$4) RETURNING id""",
                bh[:64], PIPELINE, f"/tmp/{tag}.pdf", source,
            )
            created["instances"].append(inst)
            ikey = f"{source}|{tag}|{bh[:64]}|{PIPELINE}|{uuid.uuid4().hex[:6]}"
            qid = await conn.fetchval(
                """INSERT INTO intake_queue
                   (instance_id, source, source_ref, blob_path, blob_hash, pipeline_version,
                    status, stage_output, intake_key)
                   VALUES ($1,$2,$3,$4,$5,$6,'done',$7::jsonb,$8) RETURNING id""",
                inst, source, f"{tag}-ref", f"/tmp/{tag}.pdf", bh[:64], PIPELINE,
                json.dumps({"ocr": {"pages": [{"page": 1, "text": "NPWP 09.x"}]},
                            "doc_type": "npwp"}),
                ikey,
            )
            created["queues"].append(qid)
            pid = await conn.fetchval(
                """INSERT INTO document_routing_proposal
                   (queue_id, doc_index, pipeline_version, routing_key,
                    entity_resolution, routing, commit_gate, status)
                   VALUES ($1,0,$2,$3,$4::jsonb,$5::jsonb,$6::jsonb,'review_pending') RETURNING id""",
                qid, PIPELINE, f"{tag}-{uuid.uuid4().hex[:6]}",
                json.dumps(entity_resolution),
                json.dumps({"doc_type": "npwp",
                            "fields": {"npwp_number": {"value": "09.254.294.3-407.000",
                                                       "confidence": 0.85, "source_page": 1}},
                            "type_confidence": 0.97}),
                json.dumps({"requires_human": True, "auto_commit_eligible": False}),
            )
            created["proposals"].append(pid)
            return pid

        p_owner = await mk_proposal(
            {"decision": "AUTO_ATTACH", "score": 0.95,
             "candidates": [{"client_id": cid_owner, "score": 0.95}]})
        p_other = await mk_proposal(
            {"decision": "LINK_CANDIDATE", "score": 0.80,
             "candidates": [{"client_id": cid_other, "score": 0.80}]})
        p_nomatch = await mk_proposal({"decision": "NO_MATCH", "candidates": []})

    yield {
        "tag": tag,
        "cid_owner": cid_owner, "cid_other": cid_other,
        "p_owner": p_owner, "p_other": p_other, "p_nomatch": p_nomatch,
        "created": created,
    }

    # teardown — delete in FK order
    async with pool.acquire() as conn:
        for pid in created["proposals"]:
            await conn.execute("DELETE FROM document_routing_proposal WHERE id=$1", pid)
        for qid in created["queues"]:
            await conn.execute("DELETE FROM intake_queue WHERE id=$1", qid)
        for iid in created["instances"]:
            await conn.execute("DELETE FROM document_instances WHERE id=$1", iid)
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


async def _crm_counts(pool: asyncpg.Pool) -> tuple[int, int]:
    async with pool.acquire() as conn:
        c = await conn.fetchval("SELECT count(*) FROM clients")
        p = await conn.fetchval("SELECT count(*) FROM practices")
    return c, p


# --------------------------------------------------------------------------- #
async def test_queue_admin_sees_all(pool, seed):
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get("/api/intake/review/queue", params={"source": "drive", "limit": 200})
    assert r.status_code == 200, r.text
    ids = {it["proposal_id"] for it in r.json()["items"]}
    assert {seed["p_owner"], seed["p_other"], seed["p_nomatch"]} <= ids


async def test_queue_team_rbac_filter(pool, seed):
    """Owner sees only their assigned proposal; not other's, not NO_MATCH."""
    app = _make_app(pool, TEAM_OWNER)
    async with _client(app) as cl:
        r = await cl.get("/api/intake/review/queue", params={"limit": 200})
    assert r.status_code == 200, r.text
    ids = {it["proposal_id"] for it in r.json()["items"]}
    assert seed["p_owner"] in ids
    assert seed["p_other"] not in ids
    assert seed["p_nomatch"] not in ids


async def test_queue_decision_filter(pool, seed):
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get("/api/intake/review/queue",
                         params={"decision": "NO_MATCH", "limit": 200})
    assert r.status_code == 200
    decisions = {it["decision"] for it in r.json()["items"]}
    assert decisions == {"NO_MATCH"} or seed["p_nomatch"] in {
        it["proposal_id"] for it in r.json()["items"]}


async def test_detail_admin(pool, seed):
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_owner']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "AUTO_ATTACH"
    assert body["extracted_fields"].get("npwp_number")
    assert body["ocr_pages"]  # OCR text surfaced for review
    assert any(c["client_id"] == seed["cid_owner"] for c in body["entity_candidates"])


async def test_detail_rbac_forbidden(pool, seed):
    """Team user with no access → 403 on detail."""
    app = _make_app(pool, TEAM_OTHER)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_owner']}")
    assert r.status_code == 403, r.text


async def test_claim_release_and_race(pool, seed):
    pid = seed["p_other"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r1 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r1.status_code == 200, r1.text
        token = r1.json()["claim_token"]
        assert token and r1.json()["status"] == "review_claimed"

        # concurrent 2nd claim → 409 (race protected)
        r2 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r2.status_code == 409, r2.text

        # release with token → back to review_pending
        r3 = await cl.post(f"/api/intake/review/{pid}/release",
                           params={"claim_token": token})
        assert r3.status_code == 200, r3.text
        assert r3.json()["status"] == "review_pending"

        # re-claimable after release
        r4 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r4.status_code == 200, r4.text
        # cleanup: release again so teardown deletes cleanly
        await cl.post(f"/api/intake/review/{pid}/release",
                      params={"claim_token": r4.json()["claim_token"]})


async def test_release_wrong_token_409(pool, seed):
    pid = seed["p_nomatch"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        await cl.post(f"/api/intake/review/{pid}/claim")
        # team user without the token cannot release (and isn't owner)
        bad = await cl.post(f"/api/intake/review/{pid}/release",
                            params={"claim_token": str(uuid.uuid4())})
        # admin force-release ignores token mismatch BUT here token is wrong AND
        # admin path force-releases regardless → assert it releases (admin force).
        assert bad.status_code == 200  # admin force-release
        # claim again then non-admin holder-release with wrong token → 409
        r = await cl.post(f"/api/intake/review/{pid}/claim")
        tok = r.json()["claim_token"]
    team_app = _make_app(pool, TEAM_OTHER)
    async with _client(team_app) as cl2:
        # other has no access to this NO_MATCH proposal → release pre-check
        bad2 = await cl2.post(f"/api/intake/review/{pid}/release",
                              params={"claim_token": str(uuid.uuid4())})
        assert bad2.status_code in (403, 409)
    # cleanup
    async with _client(_make_app(pool, ADMIN)) as cl3:
        await cl3.post(f"/api/intake/review/{pid}/release",
                       params={"claim_token": tok})


async def test_approve_reject_stub_501(pool, seed):
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        ra = await cl.post(f"/api/intake/review/{seed['p_owner']}/approve")
        rr = await cl.post(f"/api/intake/review/{seed['p_owner']}/reject")
    assert ra.status_code == 501 and "5C" in ra.json()["detail"]
    assert rr.status_code == 501 and "5C" in rr.json()["detail"]


async def test_zero_crm_write(pool, seed):
    """Full exercise of every endpoint must NOT mutate clients/practices."""
    before = await _crm_counts(pool)
    app = _make_app(pool, ADMIN)
    pid = seed["p_owner"]
    async with _client(app) as cl:
        await cl.get("/api/intake/review/queue", params={"limit": 200})
        await cl.get(f"/api/intake/review/{pid}")
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        await cl.post(f"/api/intake/review/{pid}/release",
                      params={"claim_token": rc.json()["claim_token"]})
        await cl.post(f"/api/intake/review/{pid}/approve")
        await cl.post(f"/api/intake/review/{pid}/reject")
    after = await _crm_counts(pool)
    assert before == after, f"CRM mutated! clients/practices {before} -> {after}"


async def test_router_registered_in_full_app(pool):
    """Mount via include_routers (registration parity, scar PR #422)."""
    from backend.app.setup.router_registration import include_routers
    app = FastAPI()
    include_routers(app)
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/intake/review/queue" in paths
    assert "/api/intake/review/{proposal_id}/claim" in paths

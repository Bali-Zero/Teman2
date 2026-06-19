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
from datetime import datetime, timedelta, timezone

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

        async def mk_proposal(
            entity_resolution: dict, source: str = "whatsapp", received_by: str | None = None,
            stage_output: dict | None = None,
        ) -> int:
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
                    status, stage_output, intake_key, received_by)
                   VALUES ($1,$2,$3,$4,$5,$6,'done',$7::jsonb,$8,$9) RETURNING id""",
                inst, source, f"{tag}-ref", f"/tmp/{tag}.pdf", bh[:64], PIPELINE,
                json.dumps(stage_output if stage_output is not None else
                           {"ocr": {"pages": [{"page": 1, "text": "NPWP 09.x"}]},
                            "doc_type": "npwp"}),
                ikey, received_by,
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

        # RBAC axis is OWN-CHAT (intake_queue.received_by), NOT the client's
        # assigned_to. Seed received_by independently of the resolved candidate:
        #   p_owner   → received_by=OWNER  (owner sees)
        #   p_other   → received_by=OTHER  (owner does NOT see)
        #   p_nomatch → received_by=OWNER  (NO_MATCH but OWNER's chat → owner sees)
        #   p_null    → received_by=NULL   (shared business line + Drive → admin-only)
        p_owner = await mk_proposal(
            {"decision": "AUTO_ATTACH", "score": 0.95,
             "candidates": [{"client_id": cid_owner, "score": 0.95}]},
            received_by=TEAM_OWNER["email"])
        p_other = await mk_proposal(
            # LIVE resolver shape (routing.py): {"table","id","name"} — NOT
            # "client_id". Regression for the dead radio-list bug: the reader
            # must resolve this shape into entity_candidates.
            {"decision": "LINK_CANDIDATE", "score": 0.80,
             "candidates": [{"table": "clients", "id": cid_other,
                             "name": f"{tag}-other", "score": 0.80}]},
            received_by=TEAM_OTHER["email"])
        p_nomatch = await mk_proposal(
            {"decision": "NO_MATCH", "candidates": []},
            received_by=TEAM_OWNER["email"])
        # p_null is a Drive doc on the shared line (received_by=NULL) — admin-only
        # AND now also source-gated OUT of the WhatsApp-only review queue.
        p_null = await mk_proposal(
            {"decision": "NO_MATCH", "candidates": []},
            source="drive", received_by=None)
        # CURRENT pipeline: OCR text lives in classify.ocr_text_per_page; the
        # ocr stage only writes a marker with NO pages. The detail reader must
        # still surface the text (regression for the empty-review-area bug).
        p_classify_ocr = await mk_proposal(
            {"decision": "NO_MATCH", "candidates": []},
            received_by=TEAM_OWNER["email"],
            stage_output={
                "ocr": {"deferred_to": "classify"},
                "classify": {"ocr_text_per_page": [
                    {"via": "response", "page": 0,
                     "text": "MINISTRY OF LAW AND HUMAN RIGHTS REPUBLIC OF INDONESIA"}]},
                "doc_type": "kitas"})
        # A genuinely OCR-less doc: neither ocr.pages nor classify text → None.
        p_no_ocr = await mk_proposal(
            {"decision": "NO_MATCH", "candidates": []},
            received_by=TEAM_OWNER["email"],
            stage_output={"ocr": {"deferred_to": "classify"},
                          "classify": {"ocr_text_per_page": []},
                          "doc_type": "unknown"})

    yield {
        "tag": tag,
        "cid_owner": cid_owner, "cid_other": cid_other,
        "p_owner": p_owner, "p_other": p_other, "p_nomatch": p_nomatch,
        "p_null": p_null,
        "p_classify_ocr": p_classify_ocr, "p_no_ocr": p_no_ocr,
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
    """Admin sees every WhatsApp doc — every worker's, incl. NULL-received_by —
    but NOT Drive docs (source-gated out of the WhatsApp-only review queue).

    Robust to nuzantara_dev size: the queue endpoint orders by ``created_at ASC``
    and caps ``limit`` at 200, so the freshly-seeded (newest) rows live at the
    TAIL of a live DB. We page through the WHOLE WhatsApp queue (the endpoint
    reports ``total``) and assert the three WhatsApp seeds appear SOMEWHERE in
    the admin's view, while the Drive seed (p_null) is absent — verifying both
    the RBAC scope (admin sees every worker's WhatsApp docs incl. NULL
    received_by) AND the source gate.
    """
    app = _make_app(pool, ADMIN)
    ids: set[int] = set()
    async with _client(app) as cl:
        offset = 0
        page_size = 200
        while True:
            # No explicit ?source= → the WhatsApp-only allowlist default applies.
            r = await cl.get(
                "/api/intake/review/queue",
                params={"limit": page_size, "offset": offset},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            items = body["items"]
            ids.update(it["proposal_id"] for it in items)
            offset += page_size
            # Stop when this page was the last (fewer than a full page returned)
            # or we have covered the reported total. ``total`` is the full count
            # BEFORE pagination, so it is the authoritative stop condition.
            if len(items) < page_size or offset >= body["total"]:
                break
    # The three WhatsApp seeds are visible to the admin…
    assert {seed["p_owner"], seed["p_other"], seed["p_nomatch"]} <= ids
    # …but the Drive doc is gated out of the review queue (still in the DB).
    assert seed["p_null"] not in ids


async def test_queue_drive_source_gated_out(pool, seed):
    """An explicit ?source=drive is OUTSIDE the WhatsApp-only allowlist → empty
    page, never the Drive proposal. The Dropbox→Drive archive stays catalogued in
    the DB but is kept out of the team/admin review list (Zero, 2026-06-19)."""
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get(
            "/api/intake/review/queue",
            params={"source": "drive", "limit": 200},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_queue_source_allowlist_env_readmits_drive(pool, seed, monkeypatch):
    """INTAKE_REVIEW_SOURCES re-admits a source without a code change ('for now'
    is a config, not a hardcode).

    Asserted by the GATE, not by finding the seed: against the live nuzantara_dev
    (thousands of real Drive rows), ?source=drive returns total=0 by DEFAULT and
    total>0 once drive is admitted. We never page the whole Drive backlog (that is
    slow and races the live drain cron); the total flip is the contract.
    """
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        # Default allowlist (whatsapp only): Drive is gated → empty.
        r_default = await cl.get(
            "/api/intake/review/queue", params={"source": "drive", "limit": 1}
        )
        assert r_default.status_code == 200, r_default.text
        assert r_default.json()["total"] == 0

        # Re-admit drive via env → the same query now reports the real backlog.
        monkeypatch.setenv("INTAKE_REVIEW_SOURCES", "whatsapp,drive")
        r_admitted = await cl.get(
            "/api/intake/review/queue", params={"source": "drive", "limit": 1}
        )
        assert r_admitted.status_code == 200, r_admitted.text
        # The seeded p_null (source=drive) guarantees at least one row exists.
        assert r_admitted.json()["total"] >= 1


async def test_queue_team_rbac_filter(pool, seed):
    """Own-chat axis: owner sees ONLY rows they received (incl. their NO_MATCH).

    received_by=OWNER → p_owner + p_nomatch visible.
    received_by=OTHER → p_other hidden.
    received_by=NULL  → p_null hidden (admin-only shared/Drive docs).
    """
    app = _make_app(pool, TEAM_OWNER)
    async with _client(app) as cl:
        r = await cl.get("/api/intake/review/queue", params={"limit": 200})
    assert r.status_code == 200, r.text
    ids = {it["proposal_id"] for it in r.json()["items"]}
    assert seed["p_owner"] in ids
    assert seed["p_nomatch"] in ids  # NO_MATCH from OWNER's own chat → now visible
    assert seed["p_other"] not in ids  # another worker's chat
    assert seed["p_null"] not in ids  # NULL received_by → admin-only


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


async def test_detail_ocr_from_classify_stage(pool, seed):
    """OCR ran in the *classify* stage (ocr stage = marker only). The detail
    reader must fall back to classify.ocr_text_per_page so the review text
    area is not empty (the empty-review-area bug)."""
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_classify_ocr']}")
    assert r.status_code == 200, r.text
    ocr_pages = r.json()["ocr_pages"]
    assert isinstance(ocr_pages, list) and len(ocr_pages) == 1
    assert ocr_pages[0]["page_number"] == 1
    assert "MINISTRY OF LAW" in ocr_pages[0]["text"]


async def test_detail_ocr_none_when_no_text(pool, seed):
    """A genuinely OCR-less doc (no ocr.pages, empty classify list) → ocr_pages
    stays None; an empty review area is correct here."""
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_no_ocr']}")
    assert r.status_code == 200, r.text
    assert r.json()["ocr_pages"] is None


async def test_detail_rbac_forbidden(pool, seed):
    """Non-admin who did NOT receive the doc → 403 (p_owner is OWNER's chat)."""
    app = _make_app(pool, TEAM_OTHER)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_owner']}")
    assert r.status_code == 403, r.text


async def test_detail_own_chat_nomatch_allowed(pool, seed):
    """Non-admin CAN open a doc from their own chat — even a NO_MATCH one."""
    app = _make_app(pool, TEAM_OWNER)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_nomatch']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "NO_MATCH"
    assert (body["received_by"] or "").lower() == TEAM_OWNER["email"]


async def test_detail_null_received_by_admin_only(pool, seed):
    """A NULL-received_by doc (shared business line / Drive) is admin-only."""
    team_app = _make_app(pool, TEAM_OWNER)
    async with _client(team_app) as cl:
        r = await cl.get(f"/api/intake/review/{seed['p_null']}")
    assert r.status_code == 403, r.text
    admin_app = _make_app(pool, ADMIN)
    async with _client(admin_app) as cl2:
        r2 = await cl2.get(f"/api/intake/review/{seed['p_null']}")
    assert r2.status_code == 200, r2.text


async def test_claim_rbac_own_chat(pool, seed):
    """Non-admin claim is gated by own-chat (received_by), not assigned_to.

    OWNER can claim p_nomatch (their NO_MATCH chat); OWNER cannot claim p_other
    (another worker's chat) nor p_null (NULL received_by → admin-only) → 403.
    """
    owner_app = _make_app(pool, TEAM_OWNER)
    async with _client(owner_app) as cl:
        # other worker's doc → 403, never reaches the atomic claim
        r_other = await cl.post(f"/api/intake/review/{seed['p_other']}/claim")
        assert r_other.status_code == 403, r_other.text
        # NULL received_by → admin-only → 403
        r_null = await cl.post(f"/api/intake/review/{seed['p_null']}/claim")
        assert r_null.status_code == 403, r_null.text
        # own NO_MATCH chat → claimable
        r_ok = await cl.post(f"/api/intake/review/{seed['p_nomatch']}/claim")
        assert r_ok.status_code == 200, r_ok.text
        # cleanup: release so teardown deletes cleanly
        await cl.post(f"/api/intake/review/{seed['p_nomatch']}/release",
                      params={"claim_token": r_ok.json()["claim_token"]})


async def test_claim_release_and_race(pool, seed):
    pid = seed["p_other"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r1 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r1.status_code == 200, r1.text
        token = r1.json()["claim_token"]
        assert token and r1.json()["status"] == "review_claimed"

        # P0#4: a 2nd claim by the SAME caller on a still-live lease is
        # IDEMPOTENT — it renews the lease and returns a fresh token (200),
        # NOT a 409. (Re-opening your own claimed document must succeed.)
        r2 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r2.status_code == 200, r2.text
        token2 = r2.json()["claim_token"]
        assert token2 and r2.json()["status"] == "review_claimed"
        # a fresh token is minted on re-claim; the new one supersedes the old.
        assert token2 != token
        token = token2  # subsequent release must present the CURRENT token

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


async def test_claim_idempotent_same_user_live_lease(pool, seed):
    """P0#4: same user re-claiming their OWN live claim -> 200 + fresh token.

    This is the exact live bug: adit opens a doc (claim #1, 200), the page
    re-claims on re-open (claim #2) -- that must return 200 with a usable token,
    not 409 'not claimable'. The lease is renewed and the row's claim_token is
    updated so a subsequent approve/reject with the latest token still validates.
    """
    pid = seed["p_nomatch"]  # OWNER's own-chat NO_MATCH proposal
    app = _make_app(pool, TEAM_OWNER)
    async with _client(app) as cl:
        r1 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r1.status_code == 200, r1.text
        tok1 = r1.json()["claim_token"]
        async with pool.acquire() as conn:
            exp1 = await conn.fetchval(
                "SELECT lease_expires_at FROM document_routing_proposal WHERE id=$1", pid)

        # re-open -> re-claim by the SAME user on a LIVE lease -> 200 (was 409)
        r2 = await cl.post(f"/api/intake/review/{pid}/claim")
        assert r2.status_code == 200, r2.text
        tok2 = r2.json()["claim_token"]
        assert tok2 and r2.json()["lease_owner"] == TEAM_OWNER["email"]
        assert tok2 != tok1  # a fresh token is minted

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT claim_token, lease_expires_at, lease_owner "
                "FROM document_routing_proposal WHERE id=$1", pid)
        assert str(row["claim_token"]) == tok2
        assert row["lease_expires_at"] >= exp1
        assert row["lease_owner"] == TEAM_OWNER["email"]

        # approve/reject still validate against the LATEST token the page holds
        ra = await cl.post(f"/api/intake/review/{pid}/approve",
                           json={"claim_token": tok2})
        assert ra.status_code == 200, ra.text  # dry-run, P0#5 token accepted
        # the OLD token is now stale -> reject with tok1 must be rejected
        rj_old = await cl.post(f"/api/intake/review/{pid}/reject",
                               json={"claim_token": tok1})
        assert rj_old.status_code == 403, rj_old.text
        # cleanup: release with the current token
        await cl.post(f"/api/intake/review/{pid}/release",
                      params={"claim_token": tok2})


async def test_claim_different_user_live_lease_409(pool, seed):
    """P0#4 guard: a DIFFERENT user must NOT steal another's live claim -> 409."""
    pid = seed["p_other"]
    admin_app = _make_app(pool, ADMIN)
    async with _client(admin_app) as cl_admin:
        r1 = await cl_admin.post(f"/api/intake/review/{pid}/claim")
        assert r1.status_code == 200, r1.text
        admin_token = r1.json()["claim_token"]

    # TEAM_OTHER owns this chat (received_by=other) so passes RBAC, but the
    # lease is live and owned by ADMIN -> must NOT steal it.
    other_app = _make_app(pool, TEAM_OTHER)
    async with _client(other_app) as cl_other:
        r2 = await cl_other.post(f"/api/intake/review/{pid}/claim")
        assert r2.status_code == 409, r2.text

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT lease_owner, claim_token FROM document_routing_proposal WHERE id=$1", pid)
    assert row["lease_owner"] == ADMIN["email"]
    assert str(row["claim_token"]) == admin_token
    async with _client(_make_app(pool, ADMIN)) as cl3:
        await cl3.post(f"/api/intake/review/{pid}/release",
                       params={"claim_token": admin_token})


async def test_claim_steal_expired_lease(pool, seed):
    """Expired-lease steal still works after the P0#4 change."""
    pid = seed["p_other"]
    admin_app = _make_app(pool, ADMIN)
    async with _client(admin_app) as cl_admin:
        r1 = await cl_admin.post(f"/api/intake/review/{pid}/claim")
        assert r1.status_code == 200, r1.text
        admin_token = r1.json()["claim_token"]

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE document_routing_proposal SET lease_expires_at=$2 WHERE id=$1",
            pid, datetime.now(timezone.utc) - timedelta(minutes=5))

    other_app = _make_app(pool, TEAM_OTHER)
    async with _client(other_app) as cl_other:
        r2 = await cl_other.post(f"/api/intake/review/{pid}/claim")
        assert r2.status_code == 200, r2.text
        new_token = r2.json()["claim_token"]
        assert new_token != admin_token
        assert r2.json()["lease_owner"] == TEAM_OTHER["email"]
        await cl_other.post(f"/api/intake/review/{pid}/release",
                            params={"claim_token": new_token})


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


async def _proposal_status(pool: asyncpg.Pool, pid: int) -> str:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT status FROM document_routing_proposal WHERE id=$1", pid)


async def test_reject_transitions_to_rejected(pool, seed):
    """Admin claim → reject → proposal terminal 'rejected', lease cleared."""
    pid = seed["p_owner"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        assert rc.status_code == 200, rc.text
        rr = await cl.post(
            f"/api/intake/review/{pid}/reject",
            json={"claim_token": rc.json()["claim_token"], "reason": "garbage scan"},
        )
    assert rr.status_code == 200, rr.text
    assert rr.json()["status"] == "rejected"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, lease_owner, lease_expires_at, claim_token, claimed_at "
            "FROM document_routing_proposal WHERE id=$1", pid)
    assert row["status"] == "rejected"
    assert row["lease_owner"] is None
    assert row["lease_expires_at"] is None
    assert row["claim_token"] is None
    assert row["claimed_at"] is None


async def test_reject_clears_lease_not_reclaimable(pool, seed):
    """After reject the proposal is terminal — claim must 409 (not review_pending)."""
    pid = seed["p_nomatch"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        await cl.post(f"/api/intake/review/{pid}/reject",
                      json={"claim_token": rc.json()["claim_token"]})
        # terminal 'rejected' is not 'review_pending' → claim's WHERE no longer matches
        rcl = await cl.post(f"/api/intake/review/{pid}/claim")
    assert rcl.status_code == 409, rcl.text
    assert await _proposal_status(pool, pid) == "rejected"


async def test_reject_requires_claim_409(pool, seed):
    """reject on an UNCLAIMED (review_pending) proposal → 409 (must be review_claimed)."""
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rr = await cl.post(f"/api/intake/review/{seed['p_owner']}/reject")
    assert rr.status_code == 409, rr.text
    assert await _proposal_status(pool, seed["p_owner"]) == "review_pending"


async def test_reject_non_admin_token_enforcement(pool, seed):
    """Non-admin must hold the lease + present the matching token (P0#5)."""
    pid = seed["p_owner"]  # assigned_to TEAM_OWNER → owner has access
    owner_app = _make_app(pool, TEAM_OWNER)
    async with _client(owner_app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        assert rc.status_code == 200, rc.text
        token = rc.json()["claim_token"]
        # no token → 400
        no_tok = await cl.post(f"/api/intake/review/{pid}/reject", json={})
        assert no_tok.status_code == 400, no_tok.text
        # wrong token → 403
        wrong = await cl.post(f"/api/intake/review/{pid}/reject",
                              json={"claim_token": str(uuid.uuid4())})
        assert wrong.status_code == 403, wrong.text
        # correct token → 200
        ok = await cl.post(f"/api/intake/review/{pid}/reject",
                           json={"claim_token": token})
        assert ok.status_code == 200, ok.text
    assert await _proposal_status(pool, pid) == "rejected"


async def test_reject_idempotent_noop(pool, seed):
    """Re-reject an already-rejected proposal → 409, status stays rejected."""
    pid = seed["p_other"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        r1 = await cl.post(f"/api/intake/review/{pid}/reject",
                           json={"claim_token": rc.json()["claim_token"]})
        assert r1.status_code == 200, r1.text
        # second reject — proposal is terminal, not review_claimed → 409
        r2 = await cl.post(f"/api/intake/review/{pid}/reject", json={})
    assert r2.status_code == 409, r2.text
    assert await _proposal_status(pool, pid) == "rejected"


async def test_reject_writes_no_crm_rows(pool, seed):
    """A full claim→reject mutates NO clients/practices.

    It DOES write exactly one forensic intake_commit_audit row (migration 224
    added outcome='rejected' for this) — that is an intake-side audit trail,
    not a CRM write. Detailed audit-row assertions live in
    test_reject_writes_audit_row.
    """
    before = await _crm_counts(pool)
    pid = seed["p_owner"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        rr = await cl.post(f"/api/intake/review/{pid}/reject",
                           json={"claim_token": rc.json()["claim_token"]})
    assert rr.status_code == 200, rr.text
    after = await _crm_counts(pool)
    assert after == before, f"CRM mutated by reject! {before} -> {after}"
    async with pool.acquire() as conn:
        n_audit = await conn.fetchval(
            "SELECT count(*) FROM intake_commit_audit WHERE proposal_id=$1", pid)
    assert n_audit == 1, "reject must write exactly ONE forensic audit row (outcome='rejected')"


async def test_reject_not_flag_gated(pool, seed, monkeypatch):
    """reject works with INTAKE_WRITER_ENABLED OFF — it is a queue-management op."""
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)
    pid = seed["p_nomatch"]
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        rr = await cl.post(f"/api/intake/review/{pid}/reject",
                           json={"claim_token": rc.json()["claim_token"]})
    assert rr.status_code == 200, rr.text
    assert rr.json()["status"] == "rejected"


async def test_approve_requires_claim_409(pool, seed):
    """FASE 5B: approve is wired (dry-run) but P0#5 requires an active claim.

    p_owner is review_pending (unclaimed) → approve must 409, NOT write the CRM.
    """
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        ra = await cl.post(f"/api/intake/review/{seed['p_owner']}/approve", json={})
    assert ra.status_code == 409, ra.text


async def test_approve_dry_run_after_claim(pool, seed):
    """FASE 5B: claim then approve → 200 dry-run, zero CRM write."""
    before = await _crm_counts(pool)
    app = _make_app(pool, ADMIN)
    pid = seed["p_owner"]
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        assert rc.status_code == 200, rc.text
        ra = await cl.post(
            f"/api/intake/review/{pid}/approve",
            json={"claim_token": rc.json()["claim_token"]},
        )
    assert ra.status_code == 200, ra.text
    body = ra.json()
    assert body["dry_run"] is True
    assert body["status"] == "review_claimed"  # P0#9: not advanced
    after = await _crm_counts(pool)
    assert after == before


async def test_approve_dry_run_never_calls_crm_pusher(pool, seed, monkeypatch):
    """Dry-run approve (writer OFF) must NOT call the Pro→Fly CRM pusher.

    The Fly delivery leg runs ONLY after a REAL committed write. A sentinel
    replaces push_committed_document: any call fails the test. The dry-run
    response also must NOT carry a crm_push key (response unchanged vs 5B).
    """
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)
    calls: list[dict] = []

    async def _sentinel(**kwargs):
        calls.append(kwargs)
        raise AssertionError("CRM pusher must not be called on a dry-run approve")

    from backend.services.intake import crm_push
    monkeypatch.setattr(crm_push, "push_committed_document", _sentinel)

    app = _make_app(pool, ADMIN)
    pid = seed["p_owner"]
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        assert rc.status_code == 200, rc.text
        ra = await cl.post(
            f"/api/intake/review/{pid}/approve",
            json={"claim_token": rc.json()["claim_token"]},
        )
    assert ra.status_code == 200, ra.text
    body = ra.json()
    assert body["dry_run"] is True
    assert "crm_push" not in body
    assert calls == []


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


async def test_blob_endpoint_rbac_and_content(pool, seed, tmp_path):
    """GET /{id}/blob: streams the original bytes with no-store; RBAC own-chat;
    404 when the blob is not on disk."""
    pid = seed["p_owner"]
    blob = tmp_path / "doc.pdf"
    payload = b"%PDF-1.4 test"
    blob.write_bytes(payload)
    async with pool.acquire() as conn:
        qrow = await conn.fetchrow(
            "SELECT q.id AS qid, q.instance_id FROM intake_queue q "
            "JOIN document_routing_proposal p ON p.queue_id = q.id WHERE p.id=$1",
            pid)
        await conn.execute(
            "UPDATE intake_queue SET blob_path=$2 WHERE id=$1", qrow["qid"], str(blob))
        # mime_type lives on document_instances (migration 212) and drives the
        # FileResponse media_type via the LEFT JOIN in _require_own_chat_or_admin.
        await conn.execute(
            "UPDATE document_instances SET mime_type='application/pdf' WHERE id=$1",
            qrow["instance_id"])

    # Own-chat receiver (non-admin) → 200, exact bytes, no-store, pdf media type.
    owner_app = _make_app(pool, TEAM_OWNER)
    async with _client(owner_app) as cl:
        r = await cl.get(f"/api/intake/review/{pid}/blob")
    assert r.status_code == 200, r.text
    assert r.content == payload
    assert "no-store" in r.headers.get("cache-control", "")
    assert r.headers["content-type"].startswith("application/pdf")

    # Non-admin who did NOT receive the doc → 403 (_require_own_chat_or_admin).
    other_app = _make_app(pool, TEAM_OTHER)
    async with _client(other_app) as cl2:
        r2 = await cl2.get(f"/api/intake/review/{pid}/blob")
    assert r2.status_code == 403, r2.text

    # p_nomatch passes RBAC (OWNER's chat) but its seed blob_path /tmp/{tag}.pdf
    # was never written to disk → 404 "Blob not on disk".
    async with _client(_make_app(pool, TEAM_OWNER)) as cl3:
        r3 = await cl3.get(f"/api/intake/review/{seed['p_nomatch']}/blob")
    assert r3.status_code == 404, r3.text


async def test_clients_search_endpoint(pool, seed):
    """clients/search finds seeded clients by name fragment; a query shorter
    than min_length=2 is rejected by FastAPI param validation (422)."""
    app = _make_app(pool, TEAM_OWNER)
    async with _client(app) as cl:
        r = await cl.get("/api/intake/review/clients/search",
                         params={"q": seed["tag"], "limit": 25})
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        ids = {it["client_id"] for it in items}
        assert seed["cid_owner"] in ids, f"seeded owner client not found: {items}"
        owner_item = next(it for it in items if it["client_id"] == seed["cid_owner"])
        assert owner_item["full_name"] == f"{seed['tag']}-owner"
        assert "assigned_to" in owner_item and "score" in owner_item

        # q="a" violates Query(min_length=2) → 422 validation error (not 400).
        r_short = await cl.get("/api/intake/review/clients/search", params={"q": "a"})
        assert r_short.status_code == 422, r_short.text


async def test_client_practices_endpoint(pool, seed):
    """clients/{id}/practices returns a list (empty for a fresh client). The
    router does no existence check: a nonexistent client id is simply an empty
    practice list (200), not a 404."""
    app = _make_app(pool, TEAM_OWNER)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/clients/{seed['cid_owner']}/practices")
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert isinstance(items, list)
        assert items == []  # the seed creates no practices for this client

        r2 = await cl.get("/api/intake/review/clients/999999999/practices")
        assert r2.status_code == 200, r2.text
        assert r2.json()["items"] == []


async def test_reject_writes_audit_row(pool, seed):
    """reject writes exactly ONE forensic intake_commit_audit row:
    outcome='rejected', dry_run=false, committed_by=the rejecting reviewer,
    and the reviewer's reason inside the plan jsonb.

    No extra cleanup needed: migration 217 FKs audit.proposal_id with
    ON DELETE CASCADE, so the seed teardown's proposal DELETE removes it.
    """
    pid = seed["p_owner"]
    app = _make_app(pool, TEAM_OWNER)  # own-chat receiver → non-admin claim path
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        assert rc.status_code == 200, rc.text
        rr = await cl.post(
            f"/api/intake/review/{pid}/reject",
            json={"claim_token": rc.json()["claim_token"], "reason": "wrong client"},
        )
    assert rr.status_code == 200, rr.text
    assert rr.json()["status"] == "rejected"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT committed_by, dry_run, outcome, plan "
            "FROM intake_commit_audit WHERE proposal_id=$1", pid)
    assert len(rows) == 1, f"expected exactly 1 audit row, got {len(rows)}"
    row = rows[0]
    assert row["outcome"] == "rejected"
    assert row["dry_run"] is False
    assert row["committed_by"] == TEAM_OWNER["email"]
    plan = row["plan"]
    if isinstance(plan, str):  # pool has no jsonb codec → raw TEXT
        plan = json.loads(plan)
    assert plan == {"reason": "wrong client"}


async def test_approve_practice_explicit_archive_only(pool, seed, monkeypatch):
    """approve with an EXPLICIT practice_id=null is archive-only: the plan must
    NOT fall back to routing's practice hint (writer.plan_commit honours
    practice_explicit=True even when the value is None).

    A poison practice hint (a nonexistent practice id) is injected into the
    proposal's routing jsonb: if practice_explicit were broken and fell back to
    the hint, P0#3 validation would block the plan ('practice ... does not
    exist') and outcome would flip to 'blocked' — so outcome=='dry_run' +
    practice_id None proves the explicit-null path end-to-end.
    """
    monkeypatch.delenv("INTAKE_WRITER_ENABLED", raising=False)  # dry-run (5B default)
    pid = seed["p_owner"]
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE document_routing_proposal "
            "SET routing = routing || '{\"practice_id\": 999999999}'::jsonb "
            "WHERE id=$1", pid)

    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        rc = await cl.post(f"/api/intake/review/{pid}/claim")
        assert rc.status_code == 200, rc.text
        ra = await cl.post(
            f"/api/intake/review/{pid}/approve",
            json={
                "claim_token": rc.json()["claim_token"],
                "client_id": seed["cid_owner"],
                "practice_id": None,  # key PRESENT → practice_explicit=True
            },
        )
    assert ra.status_code == 200, ra.text
    body = ra.json()
    assert body["dry_run"] is True
    assert body["outcome"] == "dry_run", body  # NOT 'blocked' → hint was ignored
    assert body["status"] == "review_claimed"  # P0#9: dry-run never advances
    plan = body["would_commit"]
    assert plan["blocked"] is False, plan["block_reasons"]
    assert plan["client_id"] == seed["cid_owner"]
    assert plan["practice_id"] is None  # explicit null honoured: archive-only
    op_tables = [op["table"] for op in plan["ops"]]
    assert "documents" in op_tables  # the archive (document UPSERT) is planned
    assert "practices.documents[]" not in op_tables  # NO practice-attach op


async def test_entity_candidates_resolve_live_resolver_shape(pool, seed):
    """The radio-list regression: candidates written as {"table","id","name"}
    (the shape the production resolver in routing.py ACTUALLY writes — every
    live proposal sampled 2026-06-11 used it) must resolve into a populated
    entity_candidates list. The reader previously recognised only "client_id"
    → entity_candidates was always [] and the UI's proposed-client radio list
    was dead code; the only resolvable proposals were test-seeded ones."""
    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        # p_other was seeded with the LIVE shape (id+table, no client_id).
        r = await cl.get(f"/api/intake/review/{seed['p_other']}")
        assert r.status_code == 200, r.text
        cands = r.json()["entity_candidates"]
        assert len(cands) == 1, f"live-shape candidate not resolved: {cands}"
        assert cands[0]["client_id"] == seed["cid_other"]
        assert cands[0]["full_name"] == f"{seed['tag']}-other"

        # p_owner keeps the legacy "client_id" shape — both must work.
        r = await cl.get(f"/api/intake/review/{seed['p_owner']}")
        assert r.status_code == 200, r.text
        cands = r.json()["entity_candidates"]
        assert len(cands) == 1
        assert cands[0]["client_id"] == seed["cid_owner"]


async def test_candidate_ids_routing_fallback_and_companies_excluded(pool, seed):
    """routing.client_id is a valid fallback source; companies-table candidate
    ids must NOT be looked up in the clients table (id collision hazard)."""
    pid = seed["p_nomatch"]  # seeded with zero candidates
    async with pool.acquire() as conn:
        # companies candidate (must be ignored) + routing resolved client.
        await conn.execute(
            "UPDATE document_routing_proposal SET "
            "entity_resolution = entity_resolution || "
            "  jsonb_build_object('candidates', jsonb_build_array("
            "    jsonb_build_object('table','companies','id',$2::int,'name','co'))), "
            "routing = routing || jsonb_build_object('client_id', $3::int) "
            "WHERE id=$1",
            pid, seed["cid_other"], seed["cid_owner"])

    app = _make_app(pool, ADMIN)
    async with _client(app) as cl:
        r = await cl.get(f"/api/intake/review/{pid}")
        assert r.status_code == 200, r.text
        cands = r.json()["entity_candidates"]
        ids = [c["client_id"] for c in cands]
        assert seed["cid_owner"] in ids, f"routing.client_id fallback missing: {cands}"
        assert seed["cid_other"] not in ids, (
            f"companies-table id leaked into clients lookup: {cands}")


# --------------------------------------------------------------------------- #
# Delivery-aware response status (intake message-journey TAC 2026-06-15)
# Pure unit — no DB, no app. The Pro→Fly/Drive push NEVER raises, so a failed
# delivery must be visible in the top-level approve status instead of a silent
# "routed" (committed locally but ABSENT from kita.balizero — superscar #2).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "push_status, expected",
    [
        # Delivered or intentionally-neutral → keep success status
        ("pushed", "routed"),
        ("disabled", "routed"),
        ("already_delivered", "routed"),
        # Every real delivery failure → operator-visible divergence status
        ("unreachable", "committed_local_delivery_failed"),
        ("server_error", "committed_local_delivery_failed"),
        ("denied_rbac", "committed_local_delivery_failed"),
        ("rejected", "committed_local_delivery_failed"),
        ("too_large", "committed_local_delivery_failed"),
        ("no_token", "committed_local_delivery_failed"),
        ("missing_blob", "committed_local_delivery_failed"),
        ("error", "committed_local_delivery_failed"),
    ],
)
def test_delivery_aware_status_committed_path(push_status, expected):
    from backend.app.routers.intake_review import _delivery_aware_status

    out = _delivery_aware_status("routed", {"status": push_status})
    assert out == expected, (
        f"push status {push_status!r}: got {out!r}, expected {expected!r}"
    )


def test_delivery_aware_status_leaves_non_routed_untouched():
    """A dry-run / blocked plan never reaches 'routed' — its status (and the
    absence of a delivery leg) must pass through unchanged."""
    from backend.app.routers.intake_review import _delivery_aware_status

    # review_claimed is the dry-run/blocked base — never rewritten even if a
    # (defensive) push_info were present.
    assert _delivery_aware_status("review_claimed", None) == "review_claimed"
    assert (
        _delivery_aware_status("review_claimed", {"status": "unreachable"})
        == "review_claimed"
    )


def test_delivery_aware_status_no_push_info_is_noop():
    """If the delivery leg never ran (push_info is None/empty), a committed
    'routed' stays 'routed' — we only downgrade on an OBSERVED failure."""
    from backend.app.routers.intake_review import _delivery_aware_status

    assert _delivery_aware_status("routed", None) == "routed"
    assert _delivery_aware_status("routed", {}) == "routed"

"""Real-DB tests for the drive-autocreate APPLY hardening (gate round 6).

Covers: R6-1 two-connection collision (competing committed writer between
pre-check and insert → in-TX re-count rolls the create back) · R6-3 the audit
assertion runs against the real schema (``committed_at``) · R6-4 the locked
evidence recheck fires on any predicate-bearing change · R6-7 rollback
schema-drift guard · R6-8 sweep violations never carry a canonical value.

Same discipline as test_intake_writer.py: runs against the LOCAL dev book,
skips cleanly when unreachable, every row is synthetic+unique and removed in
teardown.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

DSN = os.environ.get("INTAKE_TEST_DSN", "postgresql://localhost:5432/nuzantara_dev")

pytestmark = pytest.mark.asyncio

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "intake_drive_contact_autocreate.py"
_spec = importlib.util.spec_from_file_location("intake_drive_contact_autocreate", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("intake_drive_contact_autocreate", _mod)
_spec.loader.exec_module(_mod)


async def _dsn_reachable() -> bool:
    try:
        conn = await asyncpg.connect(DSN)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def pool():
    if not await _dsn_reachable():
        pytest.skip(f"local intake DB not reachable at {DSN}")
    p = await asyncpg.create_pool(DSN, min_size=1, max_size=4)
    yield p
    await p.close()


def _passport() -> str:
    # Valid ICAO shape (6-9 alnum with a digit), vanishingly collision-proof.
    return "Z" + str(uuid.uuid4().int)[:8]


def _name(tag: str) -> str:
    # Uppercase gibberish far from any live client name (trigram < 0.45).
    return f"ZZQX {tag.upper()} WVUT"


async def _mk_evidence(conn: asyncpg.Connection, tag: str, passport: str, name: str):
    """Minimal drive evidence chain: instance → queue → review_pending
    proposal, with validate.valid=true and an allowlisted root."""
    bh = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]
    inst = await conn.fetchval(
        """INSERT INTO document_instances (blob_hash, pipeline_version, blob_path, first_source)
           VALUES ($1,'test-r6',$2,'drive') RETURNING id""",
        bh,
        f"/tmp/{tag}.jpg",
    )
    qid = await conn.fetchval(
        """INSERT INTO intake_queue
           (instance_id, source, source_ref, source_path, blob_path, blob_hash,
            pipeline_version, status, stage_output, intake_key)
           VALUES ($1,'drive',$2,$3,$4,$5,'test-r6','review_pending',$6::jsonb,$7)
           RETURNING id""",
        inst,
        f"drive:{tag}",
        f"PEMEGANG KITAS/{tag}/file.jpg",
        f"/tmp/{tag}.jpg",
        bh,
        json.dumps(
            {
                "extract": {
                    "fields": {
                        "passport_no": {"value": passport},
                        "name": {"value": name},
                    }
                },
                "validate": {"valid": "true"},
            }
        ),
        f"drive|{tag}|{bh}|test-r6",
    )
    pid = await conn.fetchval(
        """INSERT INTO document_routing_proposal
           (queue_id, status, entity_resolution, routing, pipeline_version,
            routing_key, commit_gate)
           VALUES ($1,'review_pending',$2::jsonb,$3::jsonb,'test-r6',$4,$5::jsonb)
           RETURNING id""",
        qid,
        json.dumps({"doc_type": "passport", "candidates": []}),
        json.dumps({"doc_type": "passport"}),
        f"test-r6|{tag}|{uuid.uuid4().hex[:6]}",
        json.dumps({"requires_human": True, "decision": "NO_MATCH"}),
    )
    row = await conn.fetchrow(_mod.PERIMETER_ONE_SQL, qid, "passport_no")
    doc = _mod._doc_from_row(row, "passport")
    assert doc.pid == pid and doc.canonical == passport
    return inst, qid, pid, doc


async def _cleanup(conn: asyncpg.Connection, *, qids=(), insts=(), cids=(), keys=()):
    for qid in qids:
        await conn.execute("DELETE FROM document_routing_proposal WHERE queue_id=$1", qid)
        await conn.execute("DELETE FROM intake_queue WHERE id=$1", qid)
    for inst in insts:
        await conn.execute("DELETE FROM document_instances WHERE id=$1", inst)
    for cid in cids:
        if cid:
            await conn.execute("DELETE FROM clients WHERE id=$1", cid)
    for kind, canonical in keys:
        await conn.execute(
            "DELETE FROM intake_identity_ledger WHERE kind=$1 AND canonical_value=$2",
            kind,
            canonical,
        )


async def test_in_tx_collision_second_connection_rolls_back(pool, monkeypatch):
    """R6-1: a competing writer COMMITS the same key between the pre-check
    and the insert. The pre-check is forced blind (that is the race window,
    made deterministic); the in-TX post-insert re-count must raise
    CollisionDetected and roll the whole create back — no contact, no ledger
    row.

    SCHEDULE COVERAGE (declared per R7-1): this test exercises the
    committed-competitor schedule. The residual — a competitor whose TX is
    still uncommitted through ALL in-process counts and commits after the
    program exits — is undetectable in-process by construction; its detector
    is the `--verify-batch` delayed re-sweep the wave protocol runs at
    T+delay (and the consequence is bounded: dup key → AMBIGUOUS in the
    matcher, never auto-attach; reversible via --rollback-batch)."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    name = _name(tag)
    competitor = None
    inst = qid = None
    try:
        async with pool.acquire() as c2:
            # Second connection: the competitor lands and COMMITS.
            competitor = await c2.fetchval(
                "INSERT INTO clients (full_name, passport_number) VALUES ($1,$2) RETURNING id",
                f"competitor-{tag}",
                passport,
            )
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            inst, qid, _pid, doc = await _mk_evidence(conn, tag, passport, name)
            biz_cols = await _mod._business_columns(conn)

            async def _blind_precheck(*a, **k):
                return 0

            monkeypatch.setattr(_mod, "_key_owner_count", _blind_precheck)
            report = {"skipped": []}
            with pytest.raises(_mod.CollisionDetected):
                await _mod._apply_one(
                    conn,
                    kind="passport",
                    canonical=passport,
                    entry={"name": name, "docs": [doc]},
                    comp_col=None,
                    batch=f"test-{tag}",
                    biz_cols=biz_cols,
                    report=report,
                )
            # The TX rolled back: exactly the competitor owns the key, no
            # system-created contact, no ledger row survived.
            owners = await _mod._key_owners(conn, "passport", passport, None)
            assert owners["client_ids"] == [competitor]
            ghost = await conn.fetchval(
                "SELECT count(*) FROM clients WHERE created_by=$1 AND passport_number=$2",
                _mod.AUTOCREATE_CREATED_BY,
                passport,
            )
            assert ghost == 0
            led = await conn.fetchval(
                "SELECT count(*) FROM intake_identity_ledger WHERE kind='passport' AND canonical_value=$1",
                passport,
            )
            assert led == 0
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                cids=[competitor],
                keys=[("passport", passport)],
            )


async def test_sweep_reports_have_no_canonical_value(pool):
    """R6-8: a sweep violation names the kind and integer ids — the canonical
    strong-id value (PII) must never appear in the serialized report."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    cids = []
    try:
        async with pool.acquire() as conn:
            for i in range(2):
                cids.append(
                    await conn.fetchval(
                        "INSERT INTO clients (full_name, passport_number) VALUES ($1,$2) RETURNING id",
                        f"dupkey-{tag}-{i}",
                        passport,
                    )
                )
            bad = await _mod._sweep_keys(
                conn, [("passport", passport)], None, expect_max=1
            )
            assert len(bad) == 1
            assert sorted(bad[0]["client_ids"]) == sorted(cids)
            assert passport not in json.dumps(bad)
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, cids=cids)


async def test_rollback_schema_drift_guard(pool):
    """R6-7: business_columns stored at create ≠ current column set (a column
    was added later and may carry invisible human data) → guard, no delete."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    cid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                f"drift-{tag}",
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            stored = biz_cols[:-1]  # one column missing = drifted schema
            led_id = await conn.fetchval(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns)
                   VALUES ('passport',$1,$2,$3,'created',$4,'{}','{}','{}','{}','x',$5)
                   RETURNING id""",
                passport,
                f"drift-{tag}",
                f"test-{tag}",
                cid,
                stored,
            )
            led = await conn.fetchrow(
                "SELECT * FROM intake_identity_ledger WHERE id=$1", led_id
            )
            report = {"rolled_back": 0, "guarded": []}
            await _mod._rollback_one(conn, led, [], report)
            assert report["guarded"] and report["guarded"][0]["reason"] == "schema_drift"
            alive = await conn.fetchval(
                "SELECT deleted_at IS NULL FROM clients WHERE id=$1", cid
            )
            assert alive is True
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, cids=[cid], keys=[("passport", passport)])


async def test_audit_assertion_uses_committed_at(pool):
    """R6-3: the lot audit assertion must execute against the REAL schema —
    the query is extracted verbatim from the script (no drift twin) and run;
    intake_commit_audit has committed_at, not created_at."""
    src = _SCRIPT.read_text()
    m = re.search(
        r"SELECT count\(\*\) FROM intake_commit_audit.*?(?=\n\s*\"\"\")", src, re.S
    )
    assert m, "audit assertion query not found in script"
    query = m.group(0)
    assert "committed_at" in query and "created_at" not in query
    async with pool.acquire() as conn:
        from datetime import datetime, timezone

        n = await conn.fetchval(query, [], datetime.now(timezone.utc))
        assert n == 0


async def test_locked_evidence_matches_guilt_and_innocence(pool):
    """R6-4: the locked recheck passes on untouched evidence and fires on a
    validate flip AND on a superseding newer proposal."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    name = _name(tag)
    inst = qid = None
    try:
        async with pool.acquire() as conn:
            inst, qid, _pid, doc = await _mk_evidence(conn, tag, passport, name)
            async with conn.transaction():
                assert await _mod._locked_evidence_matches(conn, doc) is True
            await conn.execute(
                "UPDATE intake_queue SET stage_output = "
                "jsonb_set(stage_output, '{validate,valid}', '\"false\"') WHERE id=$1",
                qid,
            )
            async with conn.transaction():
                assert await _mod._locked_evidence_matches(conn, doc) is False
            await conn.execute(
                "UPDATE intake_queue SET stage_output = "
                "jsonb_set(stage_output, '{validate,valid}', '\"true\"') WHERE id=$1",
                qid,
            )
            async with conn.transaction():
                assert await _mod._locked_evidence_matches(conn, doc) is True
            await conn.execute(
                """INSERT INTO document_routing_proposal
                   (queue_id, status, entity_resolution, routing, pipeline_version,
                    routing_key, commit_gate)
                   VALUES ($1,'review_pending',$2::jsonb,$3::jsonb,'test-r6',$4,$5::jsonb)""",
                qid,
                json.dumps({"doc_type": "passport", "candidates": []}),
                json.dumps({"doc_type": "passport"}),
                f"test-r6b|{tag}|{uuid.uuid4().hex[:6]}",
                json.dumps({"requires_human": True, "decision": "NO_MATCH"}),
            )
            async with conn.transaction():
                assert await _mod._locked_evidence_matches(conn, doc) is False
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=[qid] if qid else [], insts=[inst] if inst else [])


# ---------------------------------------------------------------------------
# Round-8 behavioral coverage (R8-7): verify-batch, reroute atomicity +
# causality, rollback CAS, fatal-output redaction.
# ---------------------------------------------------------------------------


async def _mk_done_queue(conn, tag: str, passport: str, name: str):
    """Evidence chain whose queue row sits in the SETTLED book shape
    (status='done', stage='route') — the state the reroute fence requires."""
    inst, qid, pid, doc = await _mk_evidence(conn, tag, passport, name)
    await conn.execute(
        "UPDATE intake_queue SET status='done', stage='route' WHERE id=$1", qid
    )
    return inst, qid, pid, doc


async def test_verify_batch_unknown_is_error(pool):
    """R8-3: a mistyped/unknown batch id must be exit 2, never a clean 0."""
    rc = await _mod.run_verify(DSN, f"no-such-batch-{uuid.uuid4().hex[:8]}")
    assert rc == 2


async def test_verify_batch_owner_mismatch_flagged_and_clean_pass(pool):
    """R8-3: verify proves the sole owner IS the ledger's client (a key owned
    by somebody else must be an owner_violation even with exactly one owner);
    a genuinely clean batch (owner matches, reroute_verified) is rc 0."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    batch = f"test-verify-{tag}"
    cid = other = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            await conn.execute(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    reroute_verified)
                   VALUES ('passport',$1,$2,$3,'created',$4,'{}','{}','{}','{}',TRUE)""",
                passport,
                _name(tag),
                batch,
                cid,
            )
        rc = await _mod.run_verify(DSN, batch)
        assert rc == 0  # clean: sole owner == ledger client, rerouted

        # Move the key to a DIFFERENT client: still exactly one owner, but
        # not the ledger's — must be flagged.
        async with pool.acquire() as conn:
            other = await conn.fetchval(
                "INSERT INTO clients (full_name) VALUES ($1) RETURNING id",
                f"other-{tag}",
            )
            await conn.execute(
                "UPDATE clients SET passport_number=NULL WHERE id=$1", cid
            )
            await conn.execute(
                "UPDATE clients SET passport_number=$2 WHERE id=$1", other, passport
            )
        rc = await _mod.run_verify(DSN, batch)
        assert rc == 4
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, cids=[cid, other], keys=[("passport", passport)])


async def test_reroute_supersede_shortfall_rolls_back_atomically(pool):
    """R7-4/R8-4: a supersede cardinality shortfall must roll back the WHOLE
    reroute TX — the good proposal stays review_pending, the queue stays
    'done' (no half-mutation behind the freeze)."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    inst = qid = None
    try:
        async with pool.acquire() as conn:
            inst, qid, pid, _doc = await _mk_done_queue(conn, tag, passport, _name(tag))
            bogus_pid = 999999999
            from datetime import datetime, timezone

            freeze = await _mod._reroute_lot(
                conn,
                lot_qids={qid},
                sup_pids=[pid, bogus_pid],
                lot_ledger=[],
                started_at=datetime.now(timezone.utc),
                run_tag=_mod.run_tag_for(f"t-{tag}"),
                poll_seconds=0,
            )
            assert freeze and "supersede cardinality" in freeze
            state = await conn.fetchrow(
                "SELECT p.status AS pstatus, q.status AS qstatus, q.stage "
                "FROM document_routing_proposal p JOIN intake_queue q ON q.id=p.queue_id "
                "WHERE p.id=$1",
                pid,
            )
            assert state["pstatus"] == "review_pending"  # NOT superseded
            assert state["qstatus"] == "done" and state["stage"] == "route"  # NOT reset
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=[qid] if qid else [], insts=[inst] if inst else [])


async def test_reroute_drain_timeout_freezes(pool):
    """R6-2/R7-4: with no worker running, the drain must FREEZE (timeout is
    a failure), never pass vacuously."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    inst = qid = None
    try:
        async with pool.acquire() as conn:
            inst, qid, pid, _doc = await _mk_done_queue(conn, tag, passport, _name(tag))
            from datetime import datetime, timezone

            freeze = await _mod._reroute_lot(
                conn,
                lot_qids={qid},
                sup_pids=[pid],
                lot_ledger=[],
                started_at=datetime.now(timezone.utc),
                run_tag=_mod.run_tag_for(f"t-{tag}"),
                poll_seconds=0,
            )
            assert freeze and freeze.startswith("drain timeout")
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=[qid] if qid else [], insts=[inst] if inst else [])


async def test_freshness_rejects_pre_reset_tagged_proposal(pool):
    """R8-5 guilt+innocence: a same-tag proposal that PRE-dates the reset
    capture must fail freshness even though it is tagged and review_pending;
    a NEWER tagged proposal passes."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    inst = qid = None
    try:
        async with pool.acquire() as conn:
            inst, qid, pid, _doc = await _mk_done_queue(conn, tag, passport, _name(tag))
            run_tag = _mod.run_tag_for(f"t-{tag}")
            await conn.execute(
                "UPDATE document_routing_proposal SET pipeline_version=$2 WHERE id=$1",
                pid,
                run_tag,
            )
            from datetime import datetime, timezone

            t0 = datetime.now(timezone.utc)
            # Guilt: latest is the PRE-capture proposal itself.
            failure, fresh = await _mod._verify_lot_freshness(
                conn, [qid], {qid: pid}, t0, run_tag
            )
            assert failure is not None and not fresh
            # Innocence: a NEWER tagged review_pending proposal passes.
            new_pid = await conn.fetchval(
                """INSERT INTO document_routing_proposal
                   (queue_id, status, entity_resolution, routing, pipeline_version,
                    routing_key, commit_gate)
                   VALUES ($1,'review_pending',$2::jsonb,$3::jsonb,$4,$5,$6::jsonb)
                   RETURNING id""",
                qid,
                json.dumps({"doc_type": "passport", "candidates": []}),
                json.dumps({"doc_type": "passport"}),
                run_tag,
                f"test-r8fresh|{tag}",
                json.dumps({"requires_human": True, "decision": "NO_MATCH"}),
            )
            failure, fresh = await _mod._verify_lot_freshness(
                conn, [qid], {qid: pid}, t0, run_tag
            )
            assert failure is None and fresh == {qid: new_pid}
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=[qid] if qid else [], insts=[inst] if inst else [])


async def test_rollback_queue_moved_on_cas_aborts_everything(pool):
    """R8-4: if a queue's latest proposal is NOT one this batch recorded at
    reroute time, the WHOLE per-candidate rollback TX aborts — including the
    already-executed soft-delete. The client must remain alive."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    cid = inst = qid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            inst, qid, pid, _doc = await _mk_done_queue(conn, tag, passport, _name(tag))
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            led_id = await conn.fetchval(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns, reroute_proposal_ids)
                   VALUES ('passport',$1,$2,$3,'created',$4,'{}',$5,'{}','{}',$6,$7,$8)
                   RETURNING id""",
                passport,
                _name(tag),
                f"test-cas-{tag}",
                cid,
                [qid],
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
                [pid - 1],  # recorded generation does NOT include the current latest
            )
            led = await conn.fetchrow(
                "SELECT * FROM intake_identity_ledger WHERE id=$1", led_id
            )
            report = {"rolled_back": 0, "guarded": []}
            with pytest.raises(_mod._RerouteCardinality):
                await _mod._rollback_one(conn, led, [], report)
            alive = await conn.fetchval(
                "SELECT deleted_at IS NULL FROM clients WHERE id=$1", cid
            )
            assert alive is True  # the soft-delete was rolled back with the TX
            led_after = await conn.fetchval(
                "SELECT status FROM intake_identity_ledger WHERE id=$1", led_id
            )
            assert led_after == "created"
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                cids=[cid],
                keys=[("passport", passport)],
            )


async def _mk_npwp_evidence(conn, tag: str, fields: dict, name_field: object):
    """Evidence chain for an npwp doc with CALLER-CONTROLLED field shapes
    (R9-2 needs a malformed object with no 'value' member)."""
    bh = (uuid.uuid4().hex + uuid.uuid4().hex)[:64]
    inst = await conn.fetchval(
        """INSERT INTO document_instances (blob_hash, pipeline_version, blob_path, first_source)
           VALUES ($1,'test-r9',$2,'drive') RETURNING id""",
        bh,
        f"/tmp/{tag}.jpg",
    )
    qid = await conn.fetchval(
        """INSERT INTO intake_queue
           (instance_id, source, source_ref, source_path, blob_path, blob_hash,
            pipeline_version, status, stage_output, intake_key)
           VALUES ($1,'drive',$2,$3,$4,$5,'test-r9','review_pending',$6::jsonb,$7)
           RETURNING id""",
        inst,
        f"drive:{tag}",
        f"PEMEGANG KITAS/{tag}/file.jpg",
        f"/tmp/{tag}.jpg",
        bh,
        json.dumps(
            {
                "extract": {"fields": {**fields, "name": name_field}},
                "validate": {"valid": "true"},
            }
        ),
        f"drive|{tag}|{bh}|test-r9",
    )
    await conn.execute(
        """INSERT INTO document_routing_proposal
           (queue_id, status, entity_resolution, routing, pipeline_version,
            routing_key, commit_gate)
           VALUES ($1,'review_pending',$2::jsonb,$3::jsonb,'test-r9',$4,$5::jsonb)""",
        qid,
        json.dumps({"doc_type": "npwp", "candidates": []}),
        json.dumps({"doc_type": "npwp"}),
        f"test-r9|{tag}|{uuid.uuid4().hex[:6]}",
        json.dumps({"requires_human": True, "decision": "NO_MATCH"}),
    )
    return inst, qid


async def test_live_name_gates_guilt_and_innocence(pool):
    """R9-5: behavioral coverage of _live_name_gates. Innocence — a
    candidate's OWN evidence (same sid, same name) triggers neither arm.
    Guilt A — the same sid carrying a DIFFERENT valid name returns
    name_conflict_appeared. Guilt B — the same name on a DIFFERENT sid
    returns cluster_appeared."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    nm = _name(tag)
    insts, qids = [], []
    try:
        async with pool.acquire() as conn:
            inst, qid, _pid, _doc = await _mk_evidence(conn, tag, passport, nm)
            insts.append(inst)
            qids.append(qid)
            entry = {"name": nm}
            # Innocence: only the candidate's own doc exists.
            assert await _mod._live_name_gates(conn, "passport", passport, entry) is None

            # Guilt A: same passport, different valid name.
            inst2, qid2, _p2, _d2 = await _mk_evidence(
                conn, uuid.uuid4().hex[:8], passport, _name("othr")
            )
            insts.append(inst2)
            qids.append(qid2)
            assert (
                await _mod._live_name_gates(conn, "passport", passport, entry)
                == "name_conflict_appeared"
            )
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=qids, insts=insts)

    tag_b = uuid.uuid4().hex[:8]
    passport_b = _passport()
    nm_b = _name(tag_b)
    insts, qids = [], []
    try:
        async with pool.acquire() as conn:
            inst, qid, _pid, _doc = await _mk_evidence(conn, tag_b, passport_b, nm_b)
            insts.append(inst)
            qids.append(qid)
            # Guilt B: identical name under a DIFFERENT passport sid.
            inst2, qid2, _p2, _d2 = await _mk_evidence(
                conn, uuid.uuid4().hex[:8], _passport(), nm_b
            )
            insts.append(inst2)
            qids.append(qid2)
            assert (
                await _mod._live_name_gates(conn, "passport", passport_b, {"name": nm_b})
                == "cluster_appeared"
            )
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=qids, insts=insts)


async def test_malformed_value_member_fails_closed_everywhere(pool):
    """R9-2 → R10-4a: an id field stored as an object WITHOUT a 'value'
    member must fail CLOSED in the shared oracle — the old projection
    serialized the whole object and the npwp digit stripper could mint a
    'valid' SID out of {"confidence": 0.123456789012345}. Census and probes
    now share ONE fail-closed projection: the malformed shape yields NO id
    on either side (symmetry — divergence was the original R9-2), while a
    well-formed object still yields its value (innocence)."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    nm = _name(tag)
    insts, qids = [], []
    try:
        async with pool.acquire() as conn:
            inst, qid, _pid, _doc = await _mk_evidence(conn, tag, passport, nm)
            insts.append(inst)
            qids.append(qid)
            # Guilt shape: digits in OTHER members, no 'value'.
            inst2, qid2 = await _mk_npwp_evidence(
                conn,
                uuid.uuid4().hex[:8],
                {"npwp_number": {"confidence": 0.123456789012345}},
                {"value": nm},
            )
            insts.append(inst2)
            qids.append(qid2)
            r = await conn.fetchrow(_mod.PERIMETER_ONE_SQL, qid2, "npwp_number")
            assert r is not None and r["raw_id"] is None  # census refuses to mint
            # The probes see the same NOTHING — no phantom cluster either.
            assert (
                await _mod._live_name_gates(conn, "passport", passport, {"name": nm})
                is None
            )
            # Innocence: a WELL-FORMED object still yields its value.
            inst3, qid3 = await _mk_npwp_evidence(
                conn,
                uuid.uuid4().hex[:8],
                {"npwp_number": {"value": "12.345.678.9-012.345"}},
                {"value": nm},
            )
            insts.append(inst3)
            qids.append(qid3)
            r3 = await conn.fetchrow(_mod.PERIMETER_ONE_SQL, qid3, "npwp_number")
            assert r3 is not None and r3["raw_id"] == "12.345.678.9-012.345"
            assert (
                await _mod._live_name_gates(conn, "passport", passport, {"name": nm})
                == "cluster_appeared"
            )
            # R11-1 guilt: the 'value' member is ITSELF an object — ->>'value'
            # would serialize it to JSON text and the letter-accepting name
            # validator would take literal JSON as a person name. The typed
            # member CASE must fail BOTH sides closed (id and name).
            inst4, qid4 = await _mk_npwp_evidence(
                conn,
                uuid.uuid4().hex[:8],
                {"npwp_number": {"value": {"digits": "12.345.678.9-012.345"}}},
                {"value": {"label": nm}},
            )
            insts.append(inst4)
            qids.append(qid4)
            r4 = await conn.fetchrow(_mod.PERIMETER_ONE_SQL, qid4, "npwp_number")
            assert r4 is not None
            assert r4["raw_id"] is None, "nested id object must fail closed"
            assert r4["raw_name"] is None, "nested name object must fail closed"
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=qids, insts=insts)


async def test_rollback_succeeds_before_reroute_null_recorded_ids(pool):
    """R9-1: a candidate frozen BEFORE any reroute (reroute_proposal_ids
    NULL) must still be rollback-able — the CAS falls back to the ledger's
    source_proposal_ids. The original review_pending proposal is left
    untouched (it never saw the client); the client is soft-deleted."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    cid = inst = qid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            inst, qid, pid, _doc = await _mk_evidence(conn, tag, passport, _name(tag))
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            led_id = await conn.fetchval(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns, reroute_proposal_ids)
                   VALUES ('passport',$1,$2,$3,'created',$4,$5,$6,'{}','{}',$7,$8,NULL)
                   RETURNING id""",
                passport,
                _name(tag),
                f"test-r9a-{tag}",
                cid,
                [pid],
                [qid],
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
            )
            led = await conn.fetchrow(
                "SELECT * FROM intake_identity_ledger WHERE id=$1", led_id
            )
            report = {"rolled_back": 0, "guarded": []}
            await _mod._rollback_one(conn, led, [], report)
            assert report["rolled_back"] == 1 and not report["guarded"]
            gone = await conn.fetchval(
                "SELECT deleted_at IS NOT NULL FROM clients WHERE id=$1", cid
            )
            assert gone is True  # rollback DID happen pre-reroute
            p_status = await conn.fetchval(
                "SELECT status FROM document_routing_proposal WHERE id=$1", pid
            )
            assert p_status == "review_pending"  # original evidence untouched
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                cids=[cid],
                keys=[("passport", passport)],
            )


async def test_rollback_null_recorded_ids_foreign_latest_aborts(pool):
    """R9-1/R10-2a guilt companion: with reroute_proposal_ids NULL, a
    FOREIGN latest proposal still aborts the whole rollback TX — including
    the sharpest shape, ANOTHER batch's qualified autocreate tag (the bare
    global tag used to make two invocations indistinguishable)."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    cid = inst = qid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            inst, qid, pid, _doc = await _mk_evidence(conn, tag, passport, _name(tag))
            # A foreign writer adds a NEWER proposal on the same queue —
            # carrying ANOTHER batch's qualified autocreate tag.
            await conn.execute(
                """INSERT INTO document_routing_proposal
                   (queue_id, status, entity_resolution, routing, pipeline_version,
                    routing_key, commit_gate)
                   VALUES ($1,'review_pending','{}'::jsonb,'{}'::jsonb,
                           $3,$2,'{}'::jsonb)""",
                qid,
                f"foreign|{tag}",
                _mod.run_tag_for("x-deadbeef"),
            )
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            led_id = await conn.fetchval(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns, reroute_proposal_ids)
                   VALUES ('passport',$1,$2,$3,'created',$4,$5,$6,'{}','{}',$7,$8,NULL)
                   RETURNING id""",
                passport,
                _name(tag),
                f"test-r9b-{tag}",
                cid,
                [pid],
                [qid],
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
            )
            led = await conn.fetchrow(
                "SELECT * FROM intake_identity_ledger WHERE id=$1", led_id
            )
            report = {"rolled_back": 0, "guarded": []}
            with pytest.raises(_mod._RerouteCardinality):
                await _mod._rollback_one(conn, led, [], report)
            alive = await conn.fetchval(
                "SELECT deleted_at IS NULL FROM clients WHERE id=$1", cid
            )
            assert alive is True  # soft-delete rolled back with the TX
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                cids=[cid],
                keys=[("passport", passport)],
            )


async def test_drain_predicate_null_stage_stays_pending(pool):
    """R9-4: the drain predicate is extracted VERBATIM from the script
    source and executed — a queue with stage NULL / status done must count
    as PENDING (the old NOT(a AND b) form evaluated to NULL and silently
    dropped the row), while a route/done queue counts as drained."""
    src = _SCRIPT.read_text()
    m = re.search(
        r'"(SELECT count\(\*\) FROM intake_queue WHERE id = ANY\(\$1::bigint\[\]\) )"'
        r'\s*\n\s*"([^"]+)"',
        src,
    )
    assert m, "drain predicate not found in script source"
    drain_sql = m.group(1) + m.group(2)
    assert "IS DISTINCT FROM" in drain_sql  # the null-safe form is the live one
    tag = uuid.uuid4().hex[:8]
    insts, qids = [], []
    try:
        async with pool.acquire() as conn:
            inst, qid, _pid, _doc = await _mk_evidence(conn, tag, _passport(), _name(tag))
            insts.append(inst)
            qids.append(qid)
            await conn.execute(
                "UPDATE intake_queue SET stage = NULL, status = 'done' WHERE id=$1",
                qid,
            )
            pending = await conn.fetchval(drain_sql, [qid])
            assert pending == 1  # NULL stage is PENDING, never silently drained
            await conn.execute(
                "UPDATE intake_queue SET stage = 'route', status = 'done' WHERE id=$1",
                qid,
            )
            pending = await conn.fetchval(drain_sql, [qid])
            assert pending == 0  # the true terminal shape drains
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=qids, insts=insts)


async def test_verify_batch_flags_document_gate_conflict(pool):
    """R9-3/R9-5: the delayed verifier re-runs the DOCUMENT gates — a
    conflicting live doc (same sid, different name) committed after apply
    turns the batch verify into exit 4 with a document_gate violation;
    without it the same batch verifies clean (self-evidence never fires)."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    nm = _name(tag)
    cid = None
    insts, qids = [], []
    batch = f"test-r9v-{tag}"
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            inst, qid, pid, _doc = await _mk_evidence(conn, tag, passport, nm)
            insts.append(inst)
            qids.append(qid)
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                nm,
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            await conn.execute(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    reroute_verified)
                   VALUES ('passport',$1,$2,$3,'created',$4,$5,$6,'{}','{}',TRUE)""",
                passport,
                nm,
                batch,
                cid,
                [pid],
                [qid],
            )
        # Clean pass first: only self-evidence exists.
        assert await _mod.run_verify(DSN, batch) == 0
        async with pool.acquire() as conn:
            # A conflicting doc appears: same passport, different name.
            inst2, qid2, _p2, _d2 = await _mk_evidence(
                conn, uuid.uuid4().hex[:8], passport, _name("conf")
            )
            insts.append(inst2)
            qids.append(qid2)
        assert await _mod.run_verify(DSN, batch) == 4
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=qids,
                insts=insts,
                cids=[cid],
                keys=[("passport", passport)],
            )


async def test_post_insert_name_gate_rolls_back_create(pool, monkeypatch):
    """R10-6/R9-3: when the POST-insert document-gate re-run fires (a
    conflicting proposal committed inside the race window), the whole
    per-candidate TX must roll back — no contact, no ledger row. The race is
    made deterministic by flipping the gate's answer on its second call."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    name = _name(tag)
    inst = qid = None
    calls = {"n": 0}

    async def _flip(conn, kind, canonical, entry):
        calls["n"] += 1
        return None if calls["n"] == 1 else "cluster_appeared"

    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            inst, qid, _pid, doc = await _mk_evidence(conn, tag, passport, name)
            biz_cols = await _mod._business_columns(conn)
            monkeypatch.setattr(_mod, "_live_name_gates", _flip)
            with pytest.raises(_mod._PostInsertGuard, match="cluster_appeared_post"):
                await _mod._apply_one(
                    conn,
                    kind="passport",
                    canonical=passport,
                    entry={"name": name, "docs": [doc]},
                    comp_col=None,
                    batch=f"test-{tag}",
                    biz_cols=biz_cols,
                    report={"skipped": []},
                )
            assert calls["n"] == 2  # the gate DID run again after the insert
            ghost = await conn.fetchval(
                "SELECT count(*) FROM clients WHERE created_by=$1 AND passport_number=$2",
                _mod.AUTOCREATE_CREATED_BY,
                passport,
            )
            assert ghost == 0  # rolled back with the TX
            led = await conn.fetchval(
                "SELECT count(*) FROM intake_identity_ledger "
                "WHERE kind='passport' AND canonical_value=$1",
                passport,
            )
            assert led == 0
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                keys=[("passport", passport)],
            )


async def test_rollback_restores_unverified_own_tagged_fresh(pool):
    """R10-2a: a reroute that froze AFTER drain but BEFORE verify leaves a
    fresh proposal carrying OUR batch-qualified tag and a NULL
    reroute_proposal_ids. Rollback must recognize it as its own, supersede
    it and reset the queue (candidates were computed while the client was
    alive) — and stamp the reset with the ``-rb`` qualified tag."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    batch = f"test-r10a-{tag}"
    cid = inst = qid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            inst, qid, pid, _doc = await _mk_done_queue(conn, tag, passport, _name(tag))
            # Simulate the frozen-pre-verify shape: original superseded,
            # fresh OUR-batch-tagged proposal in review, queue drained.
            await conn.execute(
                "UPDATE document_routing_proposal SET status='superseded' WHERE id=$1",
                pid,
            )
            fresh_pid = await conn.fetchval(
                """INSERT INTO document_routing_proposal
                   (queue_id, status, entity_resolution, routing, pipeline_version,
                    routing_key, commit_gate)
                   VALUES ($1,'review_pending',$2::jsonb,$3::jsonb,$4,$5,$6::jsonb)
                   RETURNING id""",
                qid,
                json.dumps({"doc_type": "passport", "candidates": []}),
                json.dumps({"doc_type": "passport"}),
                _mod.run_tag_for(batch),
                f"test-r10a|{tag}",
                json.dumps({"requires_human": True, "decision": "NO_MATCH"}),
            )
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            led_id = await conn.fetchval(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns, reroute_proposal_ids)
                   VALUES ('passport',$1,$2,$3,'created',$4,$5,$6,'{}','{}',$7,$8,NULL)
                   RETURNING id""",
                passport,
                _name(tag),
                batch,
                cid,
                [pid],
                [qid],
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
            )
            led = await conn.fetchrow(
                "SELECT * FROM intake_identity_ledger WHERE id=$1", led_id
            )
            report = {"rolled_back": 0, "guarded": []}
            await _mod._rollback_one(conn, led, [], report)
            assert report["rolled_back"] == 1 and not report["guarded"]
            fresh_after = await conn.fetchval(
                "SELECT status FROM document_routing_proposal WHERE id=$1", fresh_pid
            )
            assert fresh_after == "superseded"  # our unverified product restored
            q = await conn.fetchrow(
                "SELECT status, pipeline_version FROM intake_queue WHERE id=$1", qid
            )
            assert q["status"] == "validated"
            assert q["pipeline_version"] == _mod.rb_tag_for(batch)
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                cids=[cid],
                keys=[("passport", passport)],
            )


async def test_rollback_revives_dead_queue_mid_reroute(pool):
    """R10-2b: mid-reroute (original superseded, no fresh product) with the
    queue exhausted to status='dead' — 'already headed back to review' is
    FALSE there. Rollback must revive the queue (validated, attempts=0,
    ``-rb`` tag), never report success over a dead evidence queue."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    batch = f"test-r10b-{tag}"
    cid = inst = qid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            inst, qid, pid, _doc = await _mk_evidence(conn, tag, passport, _name(tag))
            await conn.execute(
                "UPDATE document_routing_proposal SET status='superseded' WHERE id=$1",
                pid,
            )
            await conn.execute(
                "UPDATE intake_queue SET status='dead', attempts=5 WHERE id=$1", qid
            )
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            led_id = await conn.fetchval(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns, reroute_proposal_ids)
                   VALUES ('passport',$1,$2,$3,'created',$4,$5,$6,'{}','{}',$7,$8,NULL)
                   RETURNING id""",
                passport,
                _name(tag),
                batch,
                cid,
                [pid],
                [qid],
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
            )
            led = await conn.fetchrow(
                "SELECT * FROM intake_identity_ledger WHERE id=$1", led_id
            )
            report = {"rolled_back": 0, "guarded": []}
            await _mod._rollback_one(conn, led, [], report)
            assert report["rolled_back"] == 1 and not report["guarded"]
            q = await conn.fetchrow(
                "SELECT status, attempts, pipeline_version FROM intake_queue WHERE id=$1",
                qid,
            )
            assert q["status"] == "validated" and q["attempts"] == 0
            assert q["pipeline_version"] == _mod.rb_tag_for(batch)
    finally:
        async with pool.acquire() as conn:
            await _cleanup(
                conn,
                qids=[qid] if qid else [],
                insts=[inst] if inst else [],
                cids=[cid],
                keys=[("passport", passport)],
            )


async def test_run_rollback_partial_is_exit_4(pool, monkeypatch):
    """R10-6: a rollback where every row is GUARDED (here: content drift —
    a human touched the created card) must exit 4, never 0 — automation
    reading 0 would treat a still-alive contact as reverted."""
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    batch = f"test-r10c-{tag}"
    cid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            await conn.execute(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns)
                   VALUES ('passport',$1,$2,$3,'created',$4,'{}','{}','{}','{}',$5,$6)""",
                passport,
                _name(tag),
                batch,
                cid,
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
            )
            # A human edits the card AFTER creation → content drift.
            await conn.execute(
                "UPDATE clients SET notes='human touched this' WHERE id=$1", cid
            )
        monkeypatch.setenv(_mod.KILLSWITCH_ENV, "1")
        rc = await _mod.run_rollback(DSN, batch)
        assert rc == 4  # guarded-only rollback is NOT success
        async with pool.acquire() as conn:
            alive = await conn.fetchval(
                "SELECT deleted_at IS NULL FROM clients WHERE id=$1", cid
            )
            assert alive is True
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, cids=[cid], keys=[("passport", passport)])


async def test_fatal_output_is_redacted(pool):
    """R7-6/R8-7: an uncaught driver exception at top level must print only
    the exception TYPE, never the raw driver detail."""
    import subprocess
    import sys as _sys

    proc = subprocess.run(
        [
            _sys.executable,
            str(_SCRIPT),
            "--census",
            "--dsn",
            "postgresql://localhost:5432/db_that_does_not_exist_r8",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(_SCRIPT.parents[1]),
        env={**os.environ, "PYTHONPATH": str(_SCRIPT.parents[1])},
    )
    assert proc.returncode == 5
    assert "FATAL" in proc.stderr and "detail suppressed" in proc.stderr
    assert "does not exist" not in proc.stderr  # raw driver text suppressed

async def test_run_rollback_unknown_batch_is_exit_2(pool, monkeypatch):
    """R11-4: a mistyped batch id must not be a vacuous success — zero rows
    in ANY status is exit 2 'unknown_batch', never rolled_back:0 exit 0
    (automation would read the typo as 'reverted')."""
    monkeypatch.setenv(_mod.KILLSWITCH_ENV, "1")
    async with pool.acquire() as conn:
        await conn.execute(_mod.LEDGER_DDL)
    rc = await _mod.run_rollback(DSN, f"no-such-batch-{uuid.uuid4().hex[:12]}")
    assert rc == 2


async def test_etime_seconds_shapes():
    """R11-3: locale-free `ps -o etime=` parser, all documented shapes."""
    assert _mod._etime_seconds("05:03") == 303
    assert _mod._etime_seconds("1:02:03") == 3723
    assert _mod._etime_seconds("2-01:02:03") == 176523
    assert _mod._etime_seconds("  00:42  ") == 42
    assert _mod._etime_seconds("garbage") is None
    assert _mod._etime_seconds("") is None


async def test_worker_attestation_fails_visible_on_missing_or_wrong_bytes(
    tmp_path, monkeypatch
):
    """R11-3 guilt: a MISSING deploy tree is a failure (fail-visible, W84
    blind-scan class — zero files attested is never 'attested'), and wrong
    bytes are named per-file."""
    monkeypatch.setenv(_mod.DEPLOY_ROOT_ENV, str(tmp_path))
    header = dict.fromkeys(_mod._ATTESTED_DEPLOY_FILES.values(), "0" * 64)
    failures = _mod._worker_attestation(header)
    assert any(f.startswith("deploy_file_unreadable:") for f in failures)

    base = tmp_path / "apps" / "backend-rag" / "backend" / "services" / "intake"
    base.mkdir(parents=True)
    for fname in _mod._ATTESTED_DEPLOY_FILES:
        (base / fname).write_text("not the audited bytes")
    failures = _mod._worker_attestation(header)
    assert "deploy_bytes_mismatch:routing.py" in failures
    assert not any(f.startswith("deploy_file_unreadable:") for f in failures)


async def test_worker_attestation_innocence_and_env_guilt(tmp_path, monkeypatch):
    """R11-3 innocence: byte-identical deploy + worker booted after the
    newest attested mtime + clean daemon env = zero failures. Guilt: a
    forbidden env var (stub / attach arming) fails even with perfect
    bytes; a worker booted BEFORE the code fails too."""
    base = tmp_path / "apps" / "backend-rag" / "backend" / "services" / "intake"
    base.mkdir(parents=True)
    header = {}
    old = time.time() - 3600
    for fname, hkey in _mod._ATTESTED_DEPLOY_FILES.items():
        p = base / fname
        p.write_text(f"audited {fname}")
        os.utime(p, (old, old))
        header[hkey] = hashlib.sha256(f"audited {fname}".encode()).hexdigest()
    monkeypatch.setenv(_mod.DEPLOY_ROOT_ENV, str(tmp_path))

    def fake_run(cmd, **kw):
        class R:
            returncode = 0
            stdout = ""

        r = R()
        if cmd[0] == "launchctl":
            r.stdout = fake_run.launchctl_out
        elif cmd[0] == "ps" and "etime=" in cmd:
            r.stdout = "      00:05\n"  # booted 5s ago, after the 1h-old code
        elif cmd[0] == "ps" and "command=" in cmd:
            r.stdout = fake_run.worker_cmdline
        elif cmd[0] == "lsof":
            r.stdout = fake_run.lsof_out
        return r

    fake_run.launchctl_out = "\tstate = running\n\tpid = 4242\n"
    fake_run.worker_cmdline = f"{base}/worker.py --loop\n"
    fake_run.lsof_out = ""
    monkeypatch.setattr(_mod.subprocess, "run", fake_run)
    assert _mod._worker_attestation(header) == []

    fake_run.launchctl_out = (
        "\tstate = running\n\tpid = 4242\n"
        "\tenvironment = {\n\t\tINTAKE_WORKER_STUB => 1\n\t}\n"
    )
    failures = _mod._worker_attestation(header)
    assert "forbidden_daemon_env:INTAKE_WORKER_STUB" in failures

    fake_run.launchctl_out = "\tstate = running\n\tpid = 4242\n"
    fresh = time.time() + 3600  # code newer than any running worker
    for fname in _mod._ATTESTED_DEPLOY_FILES:
        os.utime(base / fname, (fresh, fresh))
    failures = _mod._worker_attestation(header)
    assert "worker_booted_before_code" in failures

    # R12-2 guilt: same hashes, same boot time — but the PID's command line
    # and cwd both resolve OUTSIDE the deploy root. A doppelganger checkout
    # (copy or retargeted symlink) must not attest.
    for fname in _mod._ATTESTED_DEPLOY_FILES:
        os.utime(base / fname, (old, old))
    fake_run.worker_cmdline = "/somewhere/else/checkout/worker.py --loop\n"
    failures = _mod._worker_attestation(header)
    assert "worker_not_running_from_deploy_root" in failures
    assert "worker_booted_before_code" not in failures

    # R13-2 guilt: an EXTERNAL worker whose executable is elsewhere must
    # not attest merely because SOME argument (e.g. --config) happens to
    # point under the deploy root — only the executable token counts.
    fake_run.worker_cmdline = f"/somewhere/else/worker.py --config {base}/config\n"
    failures = _mod._worker_attestation(header)
    assert "worker_not_running_from_deploy_root" in failures

    # R13-2 innocence: this repo's real launchd shape is a shell wrapper —
    # `/bin/bash <deploy_root>/…/worker-run.sh` — argv[0] is a known
    # interpreter, so argv[1] (the actual script) is the executable token.
    fake_run.worker_cmdline = f"/bin/bash {base}/worker-run.sh\n"
    failures = _mod._worker_attestation(header)
    assert "worker_not_running_from_deploy_root" not in failures

    # R14-1 guilt: an EXTERNAL absolute executable running with its cwd
    # merely SET to the deploy root must NOT attest — cwd is only a
    # fallback to resolve a RELATIVE executable token, never an
    # independent alternative to the executable's own location.
    fake_run.worker_cmdline = "/somewhere/else/worker.py --loop\n"
    fake_run.lsof_out = f"p4242\nn{base}\n"
    failures = _mod._worker_attestation(header)
    assert "worker_not_running_from_deploy_root" in failures

    # R14-1 innocence: a RELATIVE executable token resolved against a cwd
    # that IS under the deploy root still attests (the legitimate case cwd
    # exists to cover).
    fake_run.worker_cmdline = "worker.py --loop\n"
    fake_run.lsof_out = f"p4242\nn{base}\n"
    failures = _mod._worker_attestation(header)
    assert "worker_not_running_from_deploy_root" not in failures
    fake_run.lsof_out = ""


async def test_armed_apply_refuses_unattested_worker(monkeypatch, capsys):
    """R11-3: an ARMED apply with a failing worker attestation refuses
    (exit 3) BEFORE any ledger/client write; --skip-worker-attest is the
    only bypass and is a visible CLI choice."""
    monkeypatch.setenv(_mod.KILLSWITCH_ENV, "1")

    async def fake_census(conn):
        return {
            "digest": "d" * 64,
            "res": _mod.CensusResult(),
            "comp_col": None,
            "manifest_header": {},
        }

    monkeypatch.setattr(_mod, "_compute_census", fake_census)
    monkeypatch.setattr(
        _mod,
        "_worker_attestation",
        lambda header: ["deploy_bytes_mismatch:routing.py"],
    )
    rc = await _mod.run_apply(
        DSN, manifest="d" * 64, batch_size=1, max_batches=1, out_json=None
    )
    assert rc == 3
    assert "worker attestation failed" in capsys.readouterr().out


async def test_census_live_gate_preflight_demotes_live_collision(pool):
    """R11-2 guilt: a candidate whose name collides with a LIVE npwp
    proposal (census-parked in B_npwp_person_ambiguous, invisible to the
    census cluster pass) is demoted to B_live_gate_would_flag at census
    time — the manifest may not sell a candidate the apply-time gates
    would skip. Innocence: a collision-free candidate stays A_effective."""
    tag, tag2 = uuid.uuid4().hex[:8], uuid.uuid4().hex[:8]
    passport, passport2 = _passport(), _passport()
    nm, nm2 = _name(tag), _name(tag2)
    insts, qids = [], []
    try:
        async with pool.acquire() as conn:
            inst, qid, _pid, doc = await _mk_evidence(conn, tag, passport, nm)
            insts.append(inst)
            qids.append(qid)
            inst2, qid2, _pid2, doc2 = await _mk_evidence(
                conn, tag2, passport2, nm2
            )
            insts.append(inst2)
            qids.append(qid2)
            inst3, qid3 = await _mk_npwp_evidence(
                conn,
                uuid.uuid4().hex[:8],
                {"npwp_number": {"value": "98.765.432.1-098.765"}},
                {"value": nm},
            )
            insts.append(inst3)
            qids.append(qid3)

            res = _mod.CensusResult()
            res.a_sids = {
                f"passport:{passport}": nm,
                f"passport:{passport2}": nm2,
            }
            res.a_docs = [doc, doc2]
            res.buckets["A_effective"] = 2
            await _mod._live_gate_preflight(conn, res)

            assert f"passport:{passport}" not in res.a_sids
            assert f"passport:{passport2}" in res.a_sids
            assert res.buckets["B_live_gate_would_flag"] == 1
            assert res.buckets["A_effective"] == 1
            assert doc.bucket == "B_live_gate_would_flag"
            assert res.per_kind_a["passport"] == 1
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, qids=qids, insts=insts)

async def test_unarmed_rollback_over_live_rows_is_exit_6(pool, monkeypatch):
    """R12-4: killswitch OFF over a batch holding live 'created' rows must
    NOT exit 0 — nothing was touched, and automation reading 0 would treat
    a forgotten killswitch as a completed revert. Exit 6, rows intact."""
    monkeypatch.delenv(_mod.KILLSWITCH_ENV, raising=False)
    tag = uuid.uuid4().hex[:8]
    passport = _passport()
    batch = f"test-r12-{tag}"
    cid = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(_mod.LEDGER_DDL)
            await conn.execute(
                "ALTER TABLE intake_identity_ledger "
                "ADD COLUMN IF NOT EXISTS reroute_proposal_ids BIGINT[]"
            )
            cid = await conn.fetchval(
                "INSERT INTO clients (full_name, passport_number, created_by) "
                "VALUES ($1,$2,$3) RETURNING id",
                _name(tag),
                passport,
                _mod.AUTOCREATE_CREATED_BY,
            )
            biz_cols = await _mod._business_columns(conn)
            row = await conn.fetchrow("SELECT * FROM clients WHERE id=$1", cid)
            await conn.execute(
                """INSERT INTO intake_identity_ledger
                   (kind, canonical_value, full_name, batch_id, status, client_id,
                    source_proposal_ids, source_queue_ids, blob_hashes, fields_fps,
                    business_fingerprint, business_columns)
                   VALUES ('passport',$1,$2,$3,'created',$4,'{}','{}','{}','{}',$5,$6)""",
                passport,
                _name(tag),
                batch,
                cid,
                _mod._row_fingerprint(row, biz_cols),
                biz_cols,
            )
        rc = await _mod.run_rollback(DSN, batch)
        assert rc == 6
        async with pool.acquire() as conn:
            alive = await conn.fetchval(
                "SELECT deleted_at IS NULL FROM clients WHERE id=$1", cid
            )
            assert alive, "unarmed rollback must not touch the client"
    finally:
        async with pool.acquire() as conn:
            await _cleanup(conn, cids=[cid], keys=[("passport", passport)])


async def test_post_drain_attestation_failure_freezes_lot(pool):
    """R12-3 guilt+innocence: after a successful drain+freshness pass, a
    failing POST-DRAIN re-attestation freezes the lot (worker restart /
    deploy mutation during the drain window is detected in the same run);
    a passing one certifies. A fake worker on a second connection drains
    the queue and lands the fresh tagged proposal, exactly like the real
    daemon would."""
    from datetime import datetime, timezone

    async def _fake_worker(qid, run_tag, delay=1.5):
        await asyncio.sleep(delay)
        async with pool.acquire() as c2:
            await c2.execute(
                """INSERT INTO document_routing_proposal
                   (queue_id, status, entity_resolution, routing,
                    pipeline_version, routing_key, commit_gate)
                   VALUES ($1,'review_pending','{}'::jsonb,'{}'::jsonb,$2,$3,'{}'::jsonb)""",
                qid,
                run_tag,
                f"r12|{uuid.uuid4().hex[:12]}",
            )
            await c2.execute(
                "UPDATE intake_queue SET stage='route', status='done' WHERE id=$1",
                qid,
            )

    results = {}
    for label, attest in (
        ("guilt", lambda: ["deploy_bytes_mismatch:worker.py"]),
        ("innocence", lambda: []),
    ):
        tag = uuid.uuid4().hex[:8]
        passport = _passport()
        inst = qid = None
        try:
            async with pool.acquire() as conn:
                inst, qid, pid, _doc = await _mk_done_queue(
                    conn, tag, passport, _name(tag)
                )
                run_tag = _mod.run_tag_for(f"t-{tag}")
                worker = asyncio.ensure_future(_fake_worker(qid, run_tag))
                freeze = await _mod._reroute_lot(
                    conn,
                    lot_qids={qid},
                    sup_pids=[pid],
                    lot_ledger=[],
                    started_at=datetime.now(timezone.utc),
                    run_tag=run_tag,
                    poll_seconds=30,
                    attest=attest,
                )
                await worker
                results[label] = freeze
        finally:
            async with pool.acquire() as conn:
                await _cleanup(
                    conn, qids=[qid] if qid else [], insts=[inst] if inst else []
                )
    assert results["guilt"] and results["guilt"].startswith(
        "post_drain_attestation"
    )
    assert results["innocence"] is None

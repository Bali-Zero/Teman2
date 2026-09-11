"""`naga_persistence` acceptance tests, executed against a REAL `postgres:15` -- R2-build-spec.md
section 3, and the R2 lane C build mandate section A.

Every rejection test counts `research_os_objects` rows BEFORE and AFTER the rejected call and
asserts the count is unchanged -- a rule that is supposed to reject before any INSERT proves it
this way, not by inspecting SQL text (that is `test_naga_persistence_unit.py`'s job, against a
fake connection). This file is the real-connection counterpart: every write here goes through a
live `postgres:15` with migrations 279/280/312 applied, using the exact `db` fixture pattern
`test_migration_312_research_os_naga_claims.py` established (drop-then-rebuild ONLY the objects
279/280/312 create, guarded by an advisory lock keyed uniquely to this file so a concurrent test
run against the same database cannot race the rebuild).

Fixture provenance. The happy-path successor pair is R1's own canonical, committed
`fixtures/supersession/01_amendment_supersedes_original.json` (measured in this session:
`research_os.hashing.object_hash` recomputes to the SAME value the fixture already declares for
both claims and the edge -- it validates via `naga_persistence.validate_object` unmodified). Every
REJECTION test, by contrast, needs a payload that is deliberately broken one specific way, so
those build their own synthetic claim/edge pairs via `_claim_payload`/`_edge_payload` below (the
same convention `test_naga_persistence_unit.py`'s `_claim_payload`/`_edge_payload` use, ported
here because a rejection test must control exactly the one field under test -- reusing the
canonical fixture and then mutating it would leave two sources of hash truth to keep in sync).

Local run (docker, matching this lane's assigned container):
    TEST_DATABASE_URL=postgresql://test:test@localhost:55433/nuzantara_test \\
        PYTHONPATH=.:../.. pytest backend/tests/services/research_os/naga/test_naga_persistence_pg.py -q
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from research_os.hashing import object_hash as _object_hash
from research_os.version import CONTRACT_VERSION

from backend.db.migration_base import split_migration_sql
from backend.services.research_os import naga_persistence as np
from backend.services.research_os.naga_bitemporal_reader import registered_family_name

from .conftest import P06_BUNDLE

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations_v2"
SUPERSESSION_FIXTURE = (
    P06_BUNDLE / "fixtures" / "supersession" / "01_amendment_supersedes_original.json"
)

# --------------------------------------------------------------------------------------------
# Fixture plumbing -- exact pattern of test_migration_312_research_os_naga_claims.py::db, own
# advisory lock key so this file's schema rebuild cannot race that file's (or any sibling
# lane's) concurrent rebuild of the SAME 279/280/312 objects on a shared TEST_DATABASE_URL.
# --------------------------------------------------------------------------------------------


def _dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", "postgresql://test:test@localhost:55433/nuzantara_test"
    )


def _forward(name: str) -> str:
    forward, _ = split_migration_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
    return forward


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT pg_advisory_lock(hashtext('r2-lane-c-naga-persistence-pg'))")
        await conn.execute(
            """
            DROP TABLE IF EXISTS research_os_naga_admission, research_os_objects CASCADE;
            DROP FUNCTION IF EXISTS public.research_os_instant_key(text);
            DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
            """
        )
        async with conn.transaction():
            await conn.execute(_forward("279_research_os_contract_core.sql"))
            await conn.execute(_forward("280_research_os_objects_truncate_guard.sql"))
            await conn.execute(_forward("312_research_os_naga_claims.sql"))
        yield conn
    finally:
        await conn.execute("SELECT pg_advisory_unlock(hashtext('r2-lane-c-naga-persistence-pg'))")
        await conn.close()


async def _count_objects(conn: asyncpg.Connection) -> int:
    return await conn.fetchval("SELECT count(*) FROM research_os_objects")


# --------------------------------------------------------------------------------------------
# Payload builders.
# --------------------------------------------------------------------------------------------


def _load_supersession_fixture() -> tuple[np.ObjectWrite, np.ObjectWrite, np.ObjectWrite]:
    """R1's canonical, committed correction pair -- see module docstring."""

    objects = json.loads(SUPERSESSION_FIXTURE.read_text(encoding="utf-8"))["objects"]
    predecessor_payload, successor_payload = objects["claims"]
    edge_payload = objects["object_successor_edges"][0]
    predecessor = np.ObjectWrite(
        object_kind="claim", object_id=predecessor_payload["claim_id"], payload=predecessor_payload
    )
    successor = np.ObjectWrite(
        object_kind="claim", object_id=successor_payload["claim_id"], payload=successor_payload
    )
    edge = np.ObjectWrite(
        object_kind="object_successor_edge",
        object_id=edge_payload["object_successor_edge_id"],
        payload=edge_payload,
    )
    return predecessor, successor, edge


def _claim_payload(
    *,
    claim_id: str | None = None,
    claim_family_id: str,
    recorded_at: str,
    valid_from: str | None = "2026-01-01T00:00:00Z",
    valid_to: str | None = None,
    risk_class: str = "green",
    sensitivity: str = "public",
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "claim_id": claim_id or str(uuid.uuid4()),
        "claim_family_id": claim_family_id,
        "contract_version": CONTRACT_VERSION,
        "tenant": "bali-zero",
        "statement": {
            "subject_ref": {
                "object_kind": "regulation",
                "object_id": "reg-pg-1",
                "object_hash": "a" * 64,
            },
            "predicate": "naga.has-fee",
            "object_ref_or_value": 100.0,
        },
        "scope": {"domain": "tax"},
        "time": {"valid_from": valid_from, "valid_to": valid_to, "recorded_at": recorded_at},
        "status": "supported",
        "evidence_refs": [],
        "confidence": {"score": 0.9, "method": "manual"},
        "classification": {"risk_class": risk_class, "sensitivity": sensitivity},
        "review": {"state": "unreviewed"},
        "lineage": {
            "run_id": str(uuid.uuid4()),
            "extractor": "naga.legacy",
            "input_claim_refs": [],
        },
        "retention": {"retention_class": "operational", "legal_hold": False},
    }
    base["object_hash"] = _object_hash(base)
    return base


def _edge_payload(
    predecessor_id: str,
    predecessor_hash: str,
    successor_id: str,
    successor_hash: str,
    family_id: str,
    *,
    recorded_at: str,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "object_successor_edge_id": str(uuid.uuid4()),
        "contract_version": CONTRACT_VERSION,
        "tenant": "bali-zero",
        "object_kind": "claim",
        "family_id": family_id,
        "predecessor_ref": {
            "object_kind": "claim",
            "object_id": predecessor_id,
            "object_hash": predecessor_hash,
        },
        "successor_ref": {
            "object_kind": "claim",
            "object_id": successor_id,
            "object_hash": successor_hash,
        },
        "reason_code": "naga.correction",
        "recorded_at": recorded_at,
        "producer": {"name": "naga.pg-test", "version": "1.0.0"},
        "lineage": {"input_hashes": []},
        "retention": {"retention_class": "operational", "legal_hold": False},
    }
    base["object_hash"] = _object_hash(base)
    return base


def _write(kind: str, object_id: str, payload: dict[str, Any]) -> np.ObjectWrite:
    return np.ObjectWrite(object_kind=kind, object_id=object_id, payload=payload)


# --------------------------------------------------------------------------------------------
# 1. Happy path: successor + edge commit in ONE transaction.
# --------------------------------------------------------------------------------------------


async def test_successor_and_edge_commit_in_one_transaction(db: asyncpg.Connection) -> None:
    predecessor, successor, edge = _load_supersession_fixture()
    await np.write_objects(db, [predecessor])
    before = await _count_objects(db)

    result = await np.write_successor(
        db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
    )

    after = await _count_objects(db)
    assert set(result.inserted_ids) == {successor.object_id, edge.object_id}
    assert result.already_present_ids == ()
    assert after == before + 2
    assert (
        await db.fetchval(
            "SELECT 1 FROM research_os_objects WHERE object_id = $1", successor.object_id
        )
        == 1
    )
    assert (
        await db.fetchval("SELECT 1 FROM research_os_objects WHERE object_id = $1", edge.object_id)
        == 1
    )


# --------------------------------------------------------------------------------------------
# 2. Crash between the two inserts leaves NEITHER.
# --------------------------------------------------------------------------------------------


async def test_crash_between_successor_and_edge_insert_leaves_neither(
    db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    predecessor, successor, edge = _load_supersession_fixture()
    await np.write_objects(db, [predecessor])
    before = await _count_objects(db)

    real_insert = np._insert_object
    calls = {"n": 0}

    async def _flaky_insert(conn: asyncpg.Connection, write: np.ObjectWrite) -> str:
        calls["n"] += 1
        if calls["n"] == 2:  # the edge insert -- the successor's already went through
            raise RuntimeError("simulated crash between successor insert and edge insert")
        return await real_insert(conn, write)

    monkeypatch.setattr(np, "_insert_object", _flaky_insert)

    with pytest.raises(RuntimeError, match="simulated crash"):
        await np.write_successor(
            db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
        )

    after = await _count_objects(db)
    assert after == before, "a crash between the two inserts must leave the row count unchanged"
    assert (
        await db.fetchval(
            "SELECT 1 FROM research_os_objects WHERE object_id = $1", successor.object_id
        )
        is None
    )
    assert (
        await db.fetchval("SELECT 1 FROM research_os_objects WHERE object_id = $1", edge.object_id)
        is None
    )


# --------------------------------------------------------------------------------------------
# 3. A second, different successor for the same predecessor is rejected -- sequential, then
#    concurrent (two connections racing the SAME predecessor via the advisory xact lock).
# --------------------------------------------------------------------------------------------


async def test_second_different_successor_for_same_predecessor_is_rejected(
    db: asyncpg.Connection,
) -> None:
    predecessor, successor, edge = _load_supersession_fixture()
    await np.write_objects(db, [predecessor])
    await np.write_successor(
        db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
    )
    before = await _count_objects(db)

    family_id = predecessor.payload["claim_family_id"]
    rival_successor_payload = _claim_payload(
        claim_family_id=family_id, recorded_at="2026-06-01T00:00:00Z"
    )
    rival_edge_payload = _edge_payload(
        predecessor.object_id,
        predecessor.payload["object_hash"],
        rival_successor_payload["claim_id"],
        rival_successor_payload["object_hash"],
        registered_family_name(family_id),
        recorded_at="2026-06-01T00:00:00Z",
    )
    rival_successor = _write("claim", rival_successor_payload["claim_id"], rival_successor_payload)
    rival_edge = _write(
        "object_successor_edge",
        rival_edge_payload["object_successor_edge_id"],
        rival_edge_payload,
    )

    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_successor(
            db, predecessor_id=predecessor.object_id, successor=rival_successor, edge=rival_edge
        )
    assert excinfo.value.reason == "predecessor_already_superseded"
    after = await _count_objects(db)
    assert after == before


async def test_concurrent_successors_for_the_same_predecessor_exactly_one_wins(
    db: asyncpg.Connection,
) -> None:
    predecessor, _canonical_successor, _canonical_edge = _load_supersession_fixture()
    await np.write_objects(db, [predecessor])
    family_id = predecessor.payload["claim_family_id"]
    registered_name = registered_family_name(family_id)

    def _rival(month: str) -> tuple[np.ObjectWrite, np.ObjectWrite]:
        successor_payload = _claim_payload(
            claim_family_id=family_id, recorded_at=f"2026-{month}-01T00:00:00Z"
        )
        edge_payload = _edge_payload(
            predecessor.object_id,
            predecessor.payload["object_hash"],
            successor_payload["claim_id"],
            successor_payload["object_hash"],
            registered_name,
            recorded_at=f"2026-{month}-01T00:00:00Z",
        )
        return (
            _write("claim", successor_payload["claim_id"], successor_payload),
            _write(
                "object_successor_edge",
                edge_payload["object_successor_edge_id"],
                edge_payload,
            ),
        )

    successor_a, edge_a = _rival("06")
    successor_b, edge_b = _rival("07")

    conn_a = await asyncpg.connect(_dsn())
    conn_b = await asyncpg.connect(_dsn())
    try:
        results = await asyncio.gather(
            np.write_successor(
                conn_a, predecessor_id=predecessor.object_id, successor=successor_a, edge=edge_a
            ),
            np.write_successor(
                conn_b, predecessor_id=predecessor.object_id, successor=successor_b, edge=edge_b
            ),
            return_exceptions=True,
        )
    finally:
        await conn_a.close()
        await conn_b.close()

    successes = [r for r in results if isinstance(r, np.WriteResult)]
    failures = [r for r in results if isinstance(r, BaseException)]
    assert len(successes) == 1, results
    assert len(failures) == 1, results
    assert isinstance(failures[0], np.NagaWriteRejected), failures[0]
    assert failures[0].reason == "predecessor_already_superseded"

    edge_rows = await db.fetch(
        """SELECT object_id FROM research_os_objects
           WHERE object_kind = 'object_successor_edge'
             AND payload->'predecessor_ref'->>'object_id' = $1""",
        predecessor.object_id,
    )
    assert len(edge_rows) == 1


# --------------------------------------------------------------------------------------------
# 4. object_hash mismatch rejected before INSERT.
# --------------------------------------------------------------------------------------------


async def test_object_hash_mismatch_rejected_before_insert(db: asyncpg.Connection) -> None:
    payload = _claim_payload(claim_family_id=str(uuid.uuid4()), recorded_at="2026-01-01T00:00:00Z")
    payload["scope"] = {"domain": "mutated-after-hash-was-computed"}
    write = _write("claim", payload["claim_id"], payload)

    before = await _count_objects(db)
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_objects(db, [write])
    assert excinfo.value.reason == "object_hash_mismatch"
    after = await _count_objects(db)
    assert after == before == 0


# --------------------------------------------------------------------------------------------
# 5. Classification-lowering successor rejected.
# --------------------------------------------------------------------------------------------


async def test_classification_lowering_successor_rejected(db: asyncpg.Connection) -> None:
    family_id = str(uuid.uuid4())
    predecessor_payload = _claim_payload(
        claim_family_id=family_id,
        recorded_at="2026-01-01T00:00:00Z",
        risk_class="amber",
        sensitivity="confidential",
    )
    predecessor = _write("claim", predecessor_payload["claim_id"], predecessor_payload)
    await np.write_objects(db, [predecessor])
    before = await _count_objects(db)

    successor_payload = _claim_payload(
        claim_family_id=family_id,
        recorded_at="2026-02-01T00:00:00Z",
        risk_class="green",  # LOWER than the predecessor's "amber"
        sensitivity="confidential",
    )
    edge_payload = _edge_payload(
        predecessor.object_id,
        predecessor_payload["object_hash"],
        successor_payload["claim_id"],
        successor_payload["object_hash"],
        registered_family_name(family_id),
        recorded_at="2026-02-01T00:00:00Z",
    )
    successor = _write("claim", successor_payload["claim_id"], successor_payload)
    edge = _write("object_successor_edge", edge_payload["object_successor_edge_id"], edge_payload)

    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_successor(
            db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
        )
    assert excinfo.value.reason == "classification_lowered"
    after = await _count_objects(db)
    assert after == before


# --------------------------------------------------------------------------------------------
# 6. Instant strictness on the write path: >6 fractional digits, lowercase `t`.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "recorded_at",
    ["2026-01-01T00:00:00.1234567Z", "2026-01-01t00:00:00Z"],
    ids=["seven_fractional_digits", "lowercase_t_separator"],
)
async def test_malformed_write_path_instant_rejected_before_insert(
    db: asyncpg.Connection, recorded_at: str
) -> None:
    payload = _claim_payload(claim_family_id=str(uuid.uuid4()), recorded_at=recorded_at)
    write = _write("claim", payload["claim_id"], payload)

    before = await _count_objects(db)
    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_objects(db, [write])
    assert excinfo.value.reason == "malformed_instant"
    after = await _count_objects(db)
    assert after == before == 0


# --------------------------------------------------------------------------------------------
# 7. Edge family_id different from the members' own family rejected.
# --------------------------------------------------------------------------------------------


async def test_edge_family_id_mismatch_rejected(db: asyncpg.Connection) -> None:
    family_id = str(uuid.uuid4())
    predecessor_payload = _claim_payload(
        claim_family_id=family_id, recorded_at="2026-01-01T00:00:00Z"
    )
    predecessor = _write("claim", predecessor_payload["claim_id"], predecessor_payload)
    await np.write_objects(db, [predecessor])
    before = await _count_objects(db)

    successor_payload = _claim_payload(
        claim_family_id=family_id, recorded_at="2026-02-01T00:00:00Z"
    )
    wrong_family_name = registered_family_name(str(uuid.uuid4()))  # a DIFFERENT family entirely
    edge_payload = _edge_payload(
        predecessor.object_id,
        predecessor_payload["object_hash"],
        successor_payload["claim_id"],
        successor_payload["object_hash"],
        wrong_family_name,
        recorded_at="2026-02-01T00:00:00Z",
    )
    successor = _write("claim", successor_payload["claim_id"], successor_payload)
    edge = _write("object_successor_edge", edge_payload["object_successor_edge_id"], edge_payload)

    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_successor(
            db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
        )
    assert excinfo.value.reason == "family_identity_mismatch"
    after = await _count_objects(db)
    assert after == before


# --------------------------------------------------------------------------------------------
# 8. Successor recorded_at not strictly later rejected.
# --------------------------------------------------------------------------------------------


async def test_successor_recorded_at_not_strictly_later_rejected(db: asyncpg.Connection) -> None:
    family_id = str(uuid.uuid4())
    predecessor_payload = _claim_payload(
        claim_family_id=family_id, recorded_at="2026-03-01T00:00:00Z"
    )
    predecessor = _write("claim", predecessor_payload["claim_id"], predecessor_payload)
    await np.write_objects(db, [predecessor])
    before = await _count_objects(db)

    successor_payload = _claim_payload(
        claim_family_id=family_id,
        recorded_at="2026-03-01T00:00:00Z",  # SAME instant, not later
    )
    edge_payload = _edge_payload(
        predecessor.object_id,
        predecessor_payload["object_hash"],
        successor_payload["claim_id"],
        successor_payload["object_hash"],
        registered_family_name(family_id),
        recorded_at="2026-03-01T00:00:00Z",
    )
    successor = _write("claim", successor_payload["claim_id"], successor_payload)
    edge = _write("object_successor_edge", edge_payload["object_successor_edge_id"], edge_payload)

    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_successor(
            db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
        )
    assert excinfo.value.reason == "successor_recorded_at_not_later"
    after = await _count_objects(db)
    assert after == before


# --------------------------------------------------------------------------------------------
# 9. Replay: write_objects, write_successor, record_admissions.
# --------------------------------------------------------------------------------------------


async def test_write_objects_replay_inserts_zero_new_rows(db: asyncpg.Connection) -> None:
    predecessor, _successor, _edge = _load_supersession_fixture()

    first = await np.write_objects(db, [predecessor])
    assert first.inserted_ids == (predecessor.object_id,)
    assert first.already_present_ids == ()

    second = await np.write_objects(db, [predecessor])
    assert second.inserted_ids == ()
    assert second.already_present_ids == (predecessor.object_id,)
    assert await _count_objects(db) == 1


async def test_write_successor_replay_of_the_identical_edge_inserts_zero_new_rows(
    db: asyncpg.Connection,
) -> None:
    predecessor, successor, edge = _load_supersession_fixture()
    await np.write_objects(db, [predecessor])

    first = await np.write_successor(
        db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
    )
    assert set(first.inserted_ids) == {successor.object_id, edge.object_id}

    second = await np.write_successor(
        db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
    )
    assert second.inserted_ids == ()
    assert set(second.already_present_ids) == {successor.object_id, edge.object_id}
    assert await _count_objects(db) == 3


async def test_record_admissions_replay_returns_zero(db: asyncpg.Connection) -> None:
    row = np.AdmissionRow(
        run_id="a" * 64,
        legacy_claim_id="legacy-pg-1",
        family_id=None,
        claim_object_id="claim-pg-1",
        claim_object_hash="b" * 64,
        evidence_object_ids=(),
        evidence_object_hashes=(),
        source_snapshot_hash="c" * 64,
        decision="admitted",
        reason=None,
    )
    first = await np.record_admissions(db, [row])
    assert first == 1
    second = await np.record_admissions(db, [row])
    assert second == 0
    count = await db.fetchval("SELECT count(*) FROM research_os_naga_admission")
    assert count == 1


# --------------------------------------------------------------------------------------------
# 10. B1 invariant: the predecessor row is byte-identical before and after write_successor.
# --------------------------------------------------------------------------------------------


async def test_predecessor_row_is_byte_identical_before_and_after_successor_write(
    db: asyncpg.Connection,
) -> None:
    predecessor, successor, edge = _load_supersession_fixture()
    await np.write_objects(db, [predecessor])

    before = await db.fetchrow(
        "SELECT payload::text AS payload_text, object_hash, recorded_at "
        "FROM research_os_objects WHERE object_id = $1",
        predecessor.object_id,
    )
    await np.write_successor(
        db, predecessor_id=predecessor.object_id, successor=successor, edge=edge
    )
    after = await db.fetchrow(
        "SELECT payload::text AS payload_text, object_hash, recorded_at "
        "FROM research_os_objects WHERE object_id = $1",
        predecessor.object_id,
    )

    assert before["payload_text"] == after["payload_text"]
    assert before["object_hash"] == after["object_hash"]
    assert before["recorded_at"] == after["recorded_at"]


# --------------------------------------------------------------------------------------------
# 11. object_id hash collision rejected; stored row unchanged.
# --------------------------------------------------------------------------------------------


async def test_object_id_hash_collision_rejected_and_stored_row_unchanged(
    db: asyncpg.Connection,
) -> None:
    family_id = str(uuid.uuid4())
    original_payload = _claim_payload(claim_family_id=family_id, recorded_at="2026-01-01T00:00:00Z")
    claim_id = original_payload["claim_id"]
    original = _write("claim", claim_id, original_payload)
    await np.write_objects(db, [original])

    colliding_payload = _claim_payload(
        claim_id=claim_id,  # SAME object_id
        claim_family_id=family_id,
        recorded_at="2026-06-01T00:00:00Z",  # different content -> a genuinely different hash
    )
    assert colliding_payload["object_hash"] != original_payload["object_hash"]
    colliding = _write("claim", claim_id, colliding_payload)

    with pytest.raises(np.NagaWriteRejected) as excinfo:
        await np.write_objects(db, [colliding])
    assert excinfo.value.reason == "object_id_hash_collision"

    stored_hash = await db.fetchval(
        "SELECT object_hash FROM research_os_objects WHERE object_id = $1", claim_id
    )
    assert stored_hash == original_payload["object_hash"]
    count = await db.fetchval(
        "SELECT count(*) FROM research_os_objects WHERE object_id = $1", claim_id
    )
    assert count == 1

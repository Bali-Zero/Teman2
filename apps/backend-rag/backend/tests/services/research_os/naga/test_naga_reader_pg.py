"""`naga_bitemporal_reader.read()` EXECUTED over a real `postgres:15` -- R2-build-spec.md section
4, and the R2 lane C build mandate section B: the temporal case list, written via
`naga_persistence` (`write_objects`/`write_successor`), read back with `load_subject_objects`,
then answered by `read()` -- never a pure in-memory shortcut.

Every case also carries a PARITY assertion: `read()` over the PG round-trip must equal `read()`
over the exact same objects held in memory (`_assert_pg_matches_memory`), because
`naga_bitemporal_reader.read()` is a pure function of the `objects` mapping it is given --
`load_subject_objects` is the only thing under additional test here (JSON round-trip through
`jsonb`, subject_key filtering in SQL), so PG-path and in-memory-path disagreeing would name a
`load_subject_objects` defect specifically, not a `read()` one.

Claim builders are IMPORTED from `test_naga_bitemporal_reader.py` (`_claim`, `_scheduled_pair`,
`_SUBJECT`) rather than re-implemented, so the pure-path and PG-path corpora are the identical
objects, not look-alikes -- this is the "mirror the cases... so pure-path and PG-path agree"
instruction, applied literally. `_claim()` already produces write-path-STRICT instants
(uppercase `T`/`Z`, `research_os.hashing.object_hash`-computed) so every claim it returns is
directly insertable via `naga_persistence.write_objects` with no adaptation.

R1's canonical `fixtures/supersession/01_amendment_supersedes_original.json` (used by the sibling
`test_naga_persistence_pg.py` for the write-path happy path) is NOT reused here for the
correction-before/after-discovery case: measured in this session, that fixture's two claims carry
no `extensions.<SUBJECT_KEY_NAMESPACE>` block at all (P06 predates D3's subject_key namespace), so
`subject_key_of()` returns `None` for both and `load_subject_objects`'s own SQL filter on that
exact JSON path would also return zero rows for it. The correction-pair case below builds its own
pair via `_claim()` instead (subject-keyed, write-strict), with a FULL (write-path-compatible)
edge -- `_full_edge_payload` -- rather than `test_naga_bitemporal_reader.py`'s minimal `_edge()`,
which omits `object_hash`/`contract_version` and so cannot be committed through
`naga_persistence.write_successor`.

Local run (docker, matching this lane's assigned container):
    TEST_DATABASE_URL=postgresql://test:test@localhost:55433/nuzantara_test \\
        PYTHONPATH=.:../.. pytest backend/tests/services/research_os/naga/test_naga_reader_pg.py -q
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from research_os.hashing import object_hash as _object_hash
from research_os.version import CONTRACT_VERSION

from backend.db.migration_base import split_migration_sql
from backend.services.research_os import naga_persistence as np
from backend.services.research_os.naga_bitemporal_reader import (
    Abstain,
    Answer,
    Quarantine,
    ReadResult,
    read,
    registered_family_name,
)

from .test_naga_bitemporal_reader import _SUBJECT, _claim, _scheduled_pair

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "db" / "migrations_v2"


# --------------------------------------------------------------------------------------------
# Fixture plumbing -- same pattern as test_naga_persistence_pg.py::db, own advisory lock key.
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
        await conn.execute("SELECT pg_advisory_lock(hashtext('r2-lane-c-naga-reader-pg'))")
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
        await conn.execute("SELECT pg_advisory_unlock(hashtext('r2-lane-c-naga-reader-pg'))")
        await conn.close()


# --------------------------------------------------------------------------------------------
# Write-path helpers.
# --------------------------------------------------------------------------------------------


def _write(kind: str, object_id: str, payload: dict[str, Any]) -> np.ObjectWrite:
    return np.ObjectWrite(object_kind=kind, object_id=object_id, payload=payload)


def _claim_with_classification(
    claim_id: str,
    family_id: str,
    *,
    risk_class: str = "green",
    sensitivity: str = "public",
    **kwargs: Any,
) -> dict[str, Any]:
    """`test_naga_bitemporal_reader._claim()` carries no `classification` block -- the pure
    reader never looks at one. `naga_persistence.write_successor`'s own
    `_is_classification_lowered` rule requires both predecessor and successor to carry one
    (`classification_missing` otherwise), so any claim of this helper's that is committed via
    `write_successor` needs it added, with the hash recomputed AFTER the addition (adding a field
    after `_claim()` already computed `object_hash` would otherwise itself trip
    `object_hash_mismatch`)."""

    claim = _claim(claim_id, family_id, **kwargs)
    claim["classification"] = {"risk_class": risk_class, "sensitivity": sensitivity}
    claim["object_hash"] = _object_hash(claim)
    return claim


def _full_edge_payload(
    predecessor_id: str,
    predecessor_hash: str,
    successor_id: str,
    successor_hash: str,
    family_id: str,
    *,
    recorded_at: str,
) -> dict[str, Any]:
    """A write-path-compatible edge -- unlike `test_naga_bitemporal_reader._edge()`, which omits
    `object_hash`/`contract_version` (fine for the pure reader, not insertable via
    `naga_persistence`)."""

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
        "producer": {"name": "naga.pg-reader-test", "version": "1.0.0"},
        "lineage": {"input_hashes": []},
        "retention": {"retention_class": "operational", "legal_hold": False},
    }
    base["object_hash"] = _object_hash(base)
    return base


async def _direct_insert_object(conn: asyncpg.Connection, write: np.ObjectWrite) -> None:
    """Raw INSERT bypassing `naga_persistence`'s own validation/idempotency -- used ONLY to
    simulate a writer OTHER than `naga_persistence` (a manual repair, a second writer, a backfill
    bug): the one way this suite can put a forked edge into the table at all, since
    `write_successor` refuses a second edge for an already-superseded predecessor BY DESIGN (see
    `test_naga_persistence_pg.py::test_second_different_successor_for_same_predecessor_is_rejected`).
    Mirrors `naga_persistence._insert_object`'s own INSERT shape exactly, minus the
    idempotency/hash-collision read-back this test does not need."""

    payload = dict(write.payload)
    await conn.execute(
        """INSERT INTO research_os_objects
           (object_kind, object_id, object_hash, contract_version, tenant, payload)
           VALUES ($1, $2, $3, $4, $5, $6::text::jsonb)""",
        write.object_kind,
        write.object_id,
        payload["object_hash"],
        payload["contract_version"],
        payload.get("tenant", "bali-zero"),
        json.dumps(payload),
    )


async def _read_via_pg(
    conn: asyncpg.Connection, subject_key: str, valid_at: str, known_at: str
) -> ReadResult:
    objects = await np.load_subject_objects(conn, subject_key)
    return read(subject_key, valid_at, known_at, objects)


def _assert_pg_matches_memory(
    pg_result: ReadResult,
    memory_objects: Mapping[str, Sequence[Mapping[str, Any]]],
    subject_key: str,
    valid_at: str,
    known_at: str,
) -> None:
    memory_result = read(subject_key, valid_at, known_at, memory_objects)
    assert pg_result == memory_result, (pg_result, memory_result)


# --------------------------------------------------------------------------------------------
# Boundaries, microseconds, open bound, scheduled-change -- all over ONE written pair
# (test_naga_bitemporal_reader._scheduled_pair(): two INDEPENDENT families under one
# subject_key, disjoint valid intervals -- this is simultaneously the "scheduled change known in
# advance" case).
# --------------------------------------------------------------------------------------------


@pytest.fixture
async def scheduled_claims(db: asyncpg.Connection) -> list[dict[str, Any]]:
    claims, edges = _scheduled_pair()
    assert edges == []  # two independent families, no correction edge between them
    for claim in claims:
        await np.write_objects(db, [_write("claim", claim["claim_id"], claim)])
    return claims


async def test_the_lower_valid_from_boundary_is_included_over_pg(
    db: asyncpg.Connection, scheduled_claims: list[dict[str, Any]]
) -> None:
    memory_objects = {"claims": scheduled_claims, "object_successor_edges": []}
    pg_result = await _read_via_pg(db, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert isinstance(pg_result, Answer)
    assert pg_result.claim_id == scheduled_claims[1]["claim_id"]
    _assert_pg_matches_memory(
        pg_result, memory_objects, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )


async def test_the_upper_valid_to_boundary_is_excluded_over_pg(
    db: asyncpg.Connection, scheduled_claims: list[dict[str, Any]]
) -> None:
    memory_objects = {"claims": scheduled_claims, "object_successor_edges": []}
    # The interval boundary itself: claims[0].valid_to == claims[1].valid_from ==
    # "2026-07-01T00:00:00Z". At exactly that instant the FIRST interval must NOT answer.
    at_boundary = await _read_via_pg(db, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert isinstance(at_boundary, Answer)
    assert at_boundary.claim_id != scheduled_claims[0]["claim_id"]
    _assert_pg_matches_memory(
        at_boundary, memory_objects, _SUBJECT, "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )


async def test_zero_and_nonzero_microseconds_decide_the_answer_over_pg(
    db: asyncpg.Connection, scheduled_claims: list[dict[str, Any]]
) -> None:
    memory_objects = {"claims": scheduled_claims, "object_successor_edges": []}
    zero_frac = await _read_via_pg(
        db, _SUBJECT, "2026-07-01T00:00:00.000000Z", "2026-08-01T00:00:00Z"
    )
    nonzero_frac = await _read_via_pg(
        db, _SUBJECT, "2026-06-30T23:59:59.999999Z", "2026-08-01T00:00:00Z"
    )
    assert isinstance(zero_frac, Answer) and isinstance(nonzero_frac, Answer)
    assert zero_frac.claim_id == scheduled_claims[1]["claim_id"]
    assert nonzero_frac.claim_id == scheduled_claims[0]["claim_id"]
    assert zero_frac.claim_id != nonzero_frac.claim_id
    _assert_pg_matches_memory(
        zero_frac, memory_objects, _SUBJECT, "2026-07-01T00:00:00.000000Z", "2026-08-01T00:00:00Z"
    )
    _assert_pg_matches_memory(
        nonzero_frac,
        memory_objects,
        _SUBJECT,
        "2026-06-30T23:59:59.999999Z",
        "2026-08-01T00:00:00Z",
    )


async def test_an_open_upper_bound_answers_for_a_later_instant_over_pg(
    db: asyncpg.Connection, scheduled_claims: list[dict[str, Any]]
) -> None:
    memory_objects = {"claims": scheduled_claims, "object_successor_edges": []}
    for instant in ("2026-07-01T00:00:00Z", "2999-12-31T23:59:59Z"):
        pg_result = await _read_via_pg(db, _SUBJECT, instant, "2026-08-01T00:00:00Z")
        assert isinstance(pg_result, Answer), instant
        assert pg_result.claim_id == scheduled_claims[1]["claim_id"]
        _assert_pg_matches_memory(
            pg_result, memory_objects, _SUBJECT, instant, "2026-08-01T00:00:00Z"
        )


async def test_a_scheduled_change_known_in_advance_is_two_disjoint_families_over_pg(
    db: asyncpg.Connection, scheduled_claims: list[dict[str, Any]]
) -> None:
    assert len({c["claim_family_id"] for c in scheduled_claims}) == 2
    memory_objects = {"claims": scheduled_claims, "object_successor_edges": []}
    before_switch = await _read_via_pg(db, _SUBJECT, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z")
    after_switch = await _read_via_pg(db, _SUBJECT, "2026-09-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert isinstance(before_switch, Answer)
    assert before_switch.claim_id == scheduled_claims[0]["claim_id"]
    assert isinstance(after_switch, Answer)
    assert after_switch.claim_id == scheduled_claims[1]["claim_id"]
    _assert_pg_matches_memory(
        before_switch, memory_objects, _SUBJECT, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )
    _assert_pg_matches_memory(
        after_switch, memory_objects, _SUBJECT, "2026-09-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )


# --------------------------------------------------------------------------------------------
# Correction recorded before / after discovery -- a synthetic subject-keyed pair (see module
# docstring for why the canonical P06 supersession fixture cannot be used here), mirroring
# test_naga_bitemporal_reader.py::_corrected_pair()'s exact ids/instants.
# --------------------------------------------------------------------------------------------


def _correction_pair() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    family = "cccccccc-0000-4000-8000-00000000000c"
    original = _claim_with_classification(
        "33333333-0000-4000-8000-000000000003",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-01-10T00:00:00Z",
    )
    corrected = _claim_with_classification(
        "44444444-0000-4000-8000-000000000004",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-03-01T00:00:00Z",
    )
    edge = _full_edge_payload(
        original["claim_id"],
        original["object_hash"],
        corrected["claim_id"],
        corrected["object_hash"],
        registered_family_name(family),
        recorded_at="2026-03-01T00:00:00Z",
    )
    return original, corrected, edge


@pytest.fixture
async def correction_pair_written(
    db: asyncpg.Connection,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    original, corrected, edge = _correction_pair()
    await np.write_objects(db, [_write("claim", original["claim_id"], original)])
    await np.write_successor(
        db,
        predecessor_id=original["claim_id"],
        successor=_write("claim", corrected["claim_id"], corrected),
        edge=_write("object_successor_edge", edge["object_successor_edge_id"], edge),
    )
    return original, corrected, edge


async def test_a_correction_recorded_before_discovery_answers_the_predecessor_over_pg(
    db: asyncpg.Connection,
    correction_pair_written: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    original, corrected, edge = correction_pair_written
    memory_objects = {"claims": [original, corrected], "object_successor_edges": [edge]}
    pg_result = await _read_via_pg(db, _SUBJECT, "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z")
    assert isinstance(pg_result, Answer)
    assert pg_result.claim_id == original["claim_id"]
    _assert_pg_matches_memory(
        pg_result, memory_objects, _SUBJECT, "2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z"
    )


async def test_a_correction_recorded_after_discovery_answers_the_successor_over_pg(
    db: asyncpg.Connection,
    correction_pair_written: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    original, corrected, edge = correction_pair_written
    memory_objects = {"claims": [original, corrected], "object_successor_edges": [edge]}
    pg_result = await _read_via_pg(db, _SUBJECT, "2026-02-01T00:00:00Z", "2026-06-01T00:00:00Z")
    assert isinstance(pg_result, Answer)
    assert pg_result.claim_id == corrected["claim_id"]
    _assert_pg_matches_memory(
        pg_result, memory_objects, _SUBJECT, "2026-02-01T00:00:00Z", "2026-06-01T00:00:00Z"
    )


# --------------------------------------------------------------------------------------------
# Existing finite expiry, never extended by succession -- a single claim, no successor at all.
# --------------------------------------------------------------------------------------------


async def test_an_existing_finite_expiry_is_never_extended_over_pg(db: asyncpg.Connection) -> None:
    family = "dddddddd-0000-4000-8000-00000000000d"
    expiring = _claim(
        "55555555-0000-4000-8000-000000000005",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to="2026-06-01T00:00:00Z",
        recorded_at="2026-01-01T00:00:00Z",
    )
    await np.write_objects(db, [_write("claim", expiring["claim_id"], expiring)])
    memory_objects = {"claims": [expiring], "object_successor_edges": []}

    pg_result = await _read_via_pg(db, _SUBJECT, "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z")
    assert pg_result == Abstain("no_valid_interval_covers_valid_at")
    _assert_pg_matches_memory(
        pg_result, memory_objects, _SUBJECT, "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z"
    )


# --------------------------------------------------------------------------------------------
# A no-answer result, named reason: querying a subject_key with no family at all.
# --------------------------------------------------------------------------------------------


async def test_a_no_answer_result_abstains_with_its_named_reason_over_pg(
    db: asyncpg.Connection, scheduled_claims: list[dict[str, Any]]
) -> None:
    memory_objects = {"claims": scheduled_claims, "object_successor_edges": []}
    other_key = "id/no-such-instrument-pg/art-9"
    pg_result = await _read_via_pg(db, other_key, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z")
    assert pg_result == Abstain("no_family_for_subject_key")
    _assert_pg_matches_memory(
        pg_result, memory_objects, other_key, "2026-03-01T00:00:00Z", "2026-08-01T00:00:00Z"
    )


# --------------------------------------------------------------------------------------------
# A quarantined fork -- never a winner. write_successor REFUSES a second edge for an
# already-superseded predecessor by design, so the second edge is seeded by a DIRECT SQL INSERT
# (see `_direct_insert_object`'s docstring): this simulates a writer OTHER than
# `naga_persistence` putting a structurally-forked graph into the store, which is exactly the
# case integrity-checking at read time exists to catch.
# --------------------------------------------------------------------------------------------


async def test_a_quarantined_fork_is_never_a_winner_over_pg(db: asyncpg.Connection) -> None:
    family = "eeeeeeee-0000-4000-8000-00000000000e"
    predecessor = _claim_with_classification(
        "66666666-0000-4000-8000-000000000006",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-01-01T00:00:00Z",
    )
    left = _claim_with_classification(
        "77777777-0000-4000-8000-000000000007",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-02-01T00:00:00Z",
    )
    right = _claim(
        "88888888-0000-4000-8000-000000000008",
        family,
        valid_from="2026-01-01T00:00:00Z",
        valid_to=None,
        recorded_at="2026-02-02T00:00:00Z",
    )
    registered_name = registered_family_name(family)
    edge_left = _full_edge_payload(
        predecessor["claim_id"],
        predecessor["object_hash"],
        left["claim_id"],
        left["object_hash"],
        registered_name,
        recorded_at="2026-02-01T00:00:00Z",
    )
    edge_right = _full_edge_payload(
        predecessor["claim_id"],
        predecessor["object_hash"],
        right["claim_id"],
        right["object_hash"],
        registered_name,
        recorded_at="2026-02-02T00:00:00Z",
    )

    await np.write_objects(db, [_write("claim", predecessor["claim_id"], predecessor)])
    await np.write_successor(
        db,
        predecessor_id=predecessor["claim_id"],
        successor=_write("claim", left["claim_id"], left),
        edge=_write("object_successor_edge", edge_left["object_successor_edge_id"], edge_left),
    )
    # The "right" claim itself is an ordinary standalone object write -- no succession rule
    # forbids it. Only the SECOND EDGE is refused by write_successor (predecessor already
    # superseded by edge_left), so only the edge is seeded by direct SQL, per the module
    # docstring.
    await np.write_objects(db, [_write("claim", right["claim_id"], right)])
    await _direct_insert_object(
        db,
        _write("object_successor_edge", edge_right["object_successor_edge_id"], edge_right),
    )

    memory_objects = {
        "claims": [predecessor, left, right],
        "object_successor_edges": [edge_left, edge_right],
    }
    pg_result = await _read_via_pg(db, _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    assert isinstance(pg_result, Quarantine)
    assert "fork" in pg_result.reasons
    assert not isinstance(pg_result, Answer)
    _assert_pg_matches_memory(
        pg_result, memory_objects, _SUBJECT, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z"
    )

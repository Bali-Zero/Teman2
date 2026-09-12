"""Migration 312: apply/rollback/re-apply proof, plus the DDL contracts it must hold.

CI COLLECTION (measured, not assumed): `tests/migrations/` is not given its own CI job.
It is collected as part of `backend/tests/` -- `scripts/ci/shard_tests.py::DEFAULT_TARGETS`
(the unscoped, full-corpus target set) -- and run by the `Backend Shard N` matrix job in
`.github/workflows/tests.yml` (`services.postgres` at line ~931-944, `TEST_DATABASE_URL` set
at line ~1085 for the "Run unit tests (sharded)" step that actually invokes pytest with
`backend/tests/` in its target list, `-x --tb=short`). That job has a live `postgres:15`
service, so this file RUNS there rather than being skipped -- no `skip`, no `xfail` needed
for DB presence, matching the build mandate.

LOCAL RUN (docker, per the build mandate's own instructions):
    docker run -d --rm --name r2-lane-a-pg -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test \\
        -e POSTGRES_DB=nuzantara_test -p 55432:5432 public.ecr.aws/docker/library/postgres:15
    TEST_DATABASE_URL=postgresql://test:test@localhost:55432/nuzantara_test \\
        PYTHONPATH=.:../.. pytest backend/tests/migrations/test_migration_312_research_os_naga_claims.py -q

Every test drops-then-rebuilds ONLY the objects 279/280/312 create (never anything else in
whatever database `TEST_DATABASE_URL` names), mirroring the precedent in
`backend/tests/integration/test_dual_consul_postgres.py::dual_db`.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from backend.db.migration_base import split_migration_sql

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"
HEX64 = "0" * 64


def _dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", "postgresql://nuzantara@localhost:5432/nuzantara_test"
    )


def _forward(name: str) -> str:
    forward, _ = split_migration_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
    return forward


def _rollback(name: str) -> str:
    """The migration file's OWN rollback section -- never a copy of it kept in this test."""

    _, rollback = split_migration_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
    return rollback or ""


@pytest.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("SELECT pg_advisory_lock(hashtext('r2-migration-312-test'))")
        await conn.execute(
            """
            DROP TABLE IF EXISTS research_os_naga_admission, research_os_objects CASCADE;
            DROP FUNCTION IF EXISTS public.research_os_instant_key(text);
            DROP FUNCTION IF EXISTS public.reject_research_os_naga_admission_mutation();
            DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
            """
        )
        async with conn.transaction():
            await conn.execute(_forward("279_research_os_contract_core.sql"))
            await conn.execute(_forward("280_research_os_objects_truncate_guard.sql"))
            await conn.execute(_forward("312_research_os_naga_claims.sql"))
        yield conn
    finally:
        await conn.execute("SELECT pg_advisory_unlock(hashtext('r2-migration-312-test'))")
        await conn.close()


# ---------------------------------------------------------------------------
# research_os_instant_key: volatility, NULL-on-reject
# ---------------------------------------------------------------------------


async def test_research_os_instant_key_is_immutable(db: asyncpg.Connection) -> None:
    provolatile = await db.fetchval(
        "SELECT provolatile::text FROM pg_proc WHERE proname = 'research_os_instant_key'"
    )
    assert provolatile == "i"


@pytest.mark.parametrize(
    "bad_instant",
    ["", "2026-09-11", "2026-09-11T10:00:00+07:00", "not-an-instant"],
    ids=["empty", "date_only_no_zone", "plus_07_00_offset", "garbage"],
)
async def test_instant_key_null_on_non_matching_input(
    db: asyncpg.Connection, bad_instant: str
) -> None:
    result = await db.fetchval("SELECT public.research_os_instant_key($1)", bad_instant)
    assert result is None


# ---------------------------------------------------------------------------
# Expression indexes
# ---------------------------------------------------------------------------


async def test_expression_indexes_present(db: asyncpg.Connection) -> None:
    rows = await db.fetch(
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
        "AND tablename = 'research_os_objects' AND indexname = ANY($1::text[])",
        [
            "research_os_objects_valid_from_key_idx",
            "research_os_objects_valid_to_key_idx",
        ],
    )
    assert {r["indexname"] for r in rows} == {
        "research_os_objects_valid_from_key_idx",
        "research_os_objects_valid_to_key_idx",
    }


# ---------------------------------------------------------------------------
# research_os_naga_admission: CHECK constraints
# ---------------------------------------------------------------------------


async def _insert_admission_row(conn: asyncpg.Connection, **overrides: Any) -> int:
    values: dict[str, Any] = {
        "run_id": HEX64,
        "legacy_claim_id": "legacy-default",
        "family_id": None,
        "claim_object_id": "claim-default",
        "claim_object_hash": HEX64,
        "evidence_object_ids": [],
        "evidence_object_hashes": [],
        "source_snapshot_hash": HEX64,
        "decision": "admitted",
        "reason": None,
    }
    values.update(overrides)
    return await conn.fetchval(
        """
        INSERT INTO research_os_naga_admission
            (run_id, legacy_claim_id, family_id, claim_object_id, claim_object_hash,
             evidence_object_ids, evidence_object_hashes, source_snapshot_hash,
             decision, reason)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """,
        values["run_id"],
        values["legacy_claim_id"],
        values["family_id"],
        values["claim_object_id"],
        values["claim_object_hash"],
        values["evidence_object_ids"],
        values["evidence_object_hashes"],
        values["source_snapshot_hash"],
        values["decision"],
        values["reason"],
    )


async def test_admitted_and_excluded_rows_are_accepted(db: asyncpg.Connection) -> None:
    admitted_id = await _insert_admission_row(db, legacy_claim_id="legacy-admitted")
    excluded_id = await _insert_admission_row(
        db,
        legacy_claim_id="legacy-excluded",
        decision="excluded",
        claim_object_id=None,
        claim_object_hash=None,
        reason="statement_not_from_source",
    )
    assert admitted_id and excluded_id


BAD_ADMISSION_ROWS: list[tuple[str, dict[str, Any]]] = [
    (
        "admitted_with_a_reason",
        {"legacy_claim_id": "bad-1", "decision": "admitted", "reason": "oops"},
    ),
    (
        "admitted_without_claim_identity",
        {
            "legacy_claim_id": "bad-2",
            "decision": "admitted",
            "claim_object_id": None,
            "claim_object_hash": None,
        },
    ),
    (
        "excluded_without_reason",
        {
            "legacy_claim_id": "bad-3",
            "decision": "excluded",
            "claim_object_id": None,
            "claim_object_hash": None,
            "reason": None,
        },
    ),
    (
        "excluded_with_empty_reason",
        {
            "legacy_claim_id": "bad-4",
            "decision": "excluded",
            "claim_object_id": None,
            "claim_object_hash": None,
            "reason": "",
        },
    ),
    (
        "unknown_decision",
        {
            "legacy_claim_id": "bad-5",
            "decision": "pending",
            "claim_object_id": None,
            "claim_object_hash": None,
            "reason": None,
        },
    ),
    (
        "bad_run_id_format",
        {"legacy_claim_id": "bad-6", "run_id": "not-hex"},
    ),
    (
        "bad_source_snapshot_hash_format",
        {"legacy_claim_id": "bad-7", "source_snapshot_hash": "not-hex"},
    ),
    (
        "bad_claim_object_hash_format",
        {"legacy_claim_id": "bad-8", "claim_object_hash": "not-hex"},
    ),
    (
        "evidence_arity_mismatch",
        {
            "legacy_claim_id": "bad-9",
            "evidence_object_ids": ["e1", "e2"],
            "evidence_object_hashes": ["h1"],
        },
    ),
]


@pytest.mark.parametrize(
    "overrides",
    [c[1] for c in BAD_ADMISSION_ROWS],
    ids=[c[0] for c in BAD_ADMISSION_ROWS],
)
async def test_bad_admission_rows_rejected(
    db: asyncpg.Connection, overrides: dict[str, Any]
) -> None:
    with pytest.raises(asyncpg.PostgresError):
        async with db.transaction():
            await _insert_admission_row(db, **overrides)


# ---------------------------------------------------------------------------
# Append-only guard
# ---------------------------------------------------------------------------


async def test_update_on_naga_admission_raises(db: asyncpg.Connection) -> None:
    row_id = await _insert_admission_row(db, legacy_claim_id="update-me")
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        async with db.transaction():
            await db.execute(
                "UPDATE research_os_naga_admission SET family_id = 'x' WHERE id = $1",
                row_id,
            )


async def test_delete_on_naga_admission_raises(db: asyncpg.Connection) -> None:
    row_id = await _insert_admission_row(db, legacy_claim_id="delete-me")
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        async with db.transaction():
            await db.execute("DELETE FROM research_os_naga_admission WHERE id = $1", row_id)


async def test_truncate_on_naga_admission_raises(db: asyncpg.Connection) -> None:
    """Row triggers never fire for the wipe statement: only the STATEMENT-level guard stops it."""

    await _insert_admission_row(db, legacy_claim_id="truncate-me")
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        async with db.transaction():
            await db.execute("TRUNCATE research_os_naga_admission")
    assert await db.fetchval("SELECT count(*) FROM research_os_naga_admission") == 1


async def test_admission_guards_installed_at_row_and_statement_level(
    db: asyncpg.Connection,
) -> None:
    rows = await db.fetch(
        "SELECT tgname, (tgtype & 1) = 1 AS row_level FROM pg_trigger "
        "WHERE tgrelid = 'public.research_os_naga_admission'::regclass AND NOT tgisinternal "
        "ORDER BY tgname"
    )
    assert [(r["tgname"], r["row_level"]) for r in rows] == [
        ("research_os_naga_admission_immutable", True),
        ("research_os_naga_admission_no_wipe", False),
    ]


async def test_admission_guards_do_not_depend_on_migration_279s_function(
    db: asyncpg.Connection,
) -> None:
    """Both admission triggers must call THIS migration's own function.

    Not a style preference -- a regression test for a measured CI failure. While these two
    triggers were bound to 279's shared `reject_research_os_objects_mutation()`, the
    clean-slate fixture of `backend/tests/db/test_migration_280_...py` (which this migration
    does not touch, and which drops that function with no CASCADE after removing only 279's
    own triggers) failed with DependentObjectsStillExistError as soon as 312 existed in the
    same database. One red test out of 9132, invisible to the R2 acceptance set because it
    does not include 280's file. So the guard is asserted from BOTH directions: our triggers
    point at our function, and 279's function has no dependent of ours.
    """
    fns = await db.fetch(
        "SELECT t.tgname, p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
        "WHERE t.tgrelid = 'public.research_os_naga_admission'::regclass "
        "AND NOT t.tgisinternal ORDER BY t.tgname"
    )
    assert [(r["tgname"], r["proname"]) for r in fns] == [
        ("research_os_naga_admission_immutable", "reject_research_os_naga_admission_mutation"),
        ("research_os_naga_admission_no_wipe", "reject_research_os_naga_admission_mutation"),
    ]

    borrowed = await db.fetchval(
        "SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
        "WHERE p.proname = 'reject_research_os_objects_mutation' "
        "AND t.tgrelid = 'public.research_os_naga_admission'::regclass"
    )
    assert borrowed == 0, (
        "no trigger of this migration may depend on 279's function: 280's test fixture "
        "DROPs it without CASCADE"
    )


# ---------------------------------------------------------------------------
# Apply / rollback (exercised directly, see _312_ROLLBACK_SQL) / re-apply
# ---------------------------------------------------------------------------


async def test_migration_312_rollback_refuses_while_admission_rows_exist(
    db: asyncpg.Connection,
) -> None:
    await _insert_admission_row(db, legacy_claim_id="keep-me")
    with pytest.raises(asyncpg.PostgresError, match="rollback refused"):
        async with db.transaction():
            await db.execute(_rollback("312_research_os_naga_claims.sql"))
    assert await db.fetchval("SELECT count(*) FROM research_os_naga_admission") == 1


async def test_migration_312_rolls_back_cleanly_and_reapplies(db: asyncpg.Connection) -> None:
    rollback = _rollback("312_research_os_naga_claims.sql")
    assert rollback.strip(), "312's own rollback section is empty"
    await db.execute(rollback)

    guards_279_280 = await db.fetchval(
        "SELECT count(*) FROM pg_trigger WHERE tgname IN "
        "('research_os_objects_immutable', 'research_os_objects_no_wipe')"
    )
    assert guards_279_280 == 2

    gone = await db.fetchval(
        "SELECT NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'research_os_instant_key') "
        "AND NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = "
        "                'reject_research_os_naga_admission_mutation') "
        "AND NOT EXISTS (SELECT 1 FROM information_schema.tables "
        "                WHERE table_name = 'research_os_naga_admission') "
        "AND NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname IN "
        "                ('research_os_objects_valid_from_key_idx', "
        "                 'research_os_objects_valid_to_key_idx'))"
    )
    assert gone is True

    # 279/280 -- and their own table/function/triggers -- are untouched by 312's rollback.
    still_present = await db.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = "
        "               'reject_research_os_objects_mutation') "
        "AND EXISTS (SELECT 1 FROM information_schema.tables "
        "            WHERE table_name = 'research_os_objects')"
    )
    assert still_present is True

    # Re-apply from clean a second time.
    await db.execute(_forward("312_research_os_naga_claims.sql"))
    provolatile = await db.fetchval(
        "SELECT provolatile::text FROM pg_proc WHERE proname = 'research_os_instant_key'"
    )
    assert provolatile == "i"
    indexes_again = await db.fetchval(
        "SELECT count(*) FROM pg_indexes WHERE indexname IN "
        "('research_os_objects_valid_from_key_idx', 'research_os_objects_valid_to_key_idx')"
    )
    assert indexes_again == 2


# ---------------------------------------------------------------------------
# Ledger row 21 -- the load-bearing ordering proof.
# ---------------------------------------------------------------------------


async def test_ledger_row_21_key_ordering_and_half_open_predicate(
    db: asyncpg.Connection,
) -> None:
    """Two canonical instants inside one second, from the core's OWN serializer.

    `earlier_wire`/`later_wire` are produced by round-tripping a `UtcDateTime` field
    through Pydantic's JSON mode -- the same serialization every canonical object uses --
    not hand-written literals. Measured once (this exact pair, this exact JSON mode) to
    confirm the wire form really does use a bare `Z` terminator with no fraction when the
    microsecond is zero: `2026-09-11T10:00:00Z` vs `2026-09-11T10:00:00.500000Z`. Raw text
    comparison of these two disagrees with chronological order ('Z' 0x5A sorts after '.'
    0x2E), which is exactly ledger row 21 / `PENDING-ARMS.md:21`'s defect.
    """
    from datetime import datetime, timezone

    # The core is not an installed package: this bootstrap must run BEFORE `research_os` is
    # imported, or the test only passes when an earlier module happened to put it on sys.path.
    import backend.services.research_os._core_path  # noqa: F401

    # isort: split
    from pydantic import BaseModel
    from research_os.primitives import UtcDateTime

    class _InstantProbe(BaseModel):
        t: UtcDateTime

    zero_frac = _InstantProbe(t=datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc))
    half_frac = _InstantProbe(t=datetime(2026, 9, 11, 10, 0, 0, 500_000, tzinfo=timezone.utc))
    earlier_wire = zero_frac.model_dump(mode="json")["t"]
    later_wire = half_frac.model_dump(mode="json")["t"]
    assert earlier_wire != later_wire, "the core's serializer stopped varying the two probes"

    raw_text_order = earlier_wire < later_wire
    key_row = await db.fetchrow(
        "SELECT (public.research_os_instant_key($1) COLLATE \"C\") < "
        "       (public.research_os_instant_key($2) COLLATE \"C\") AS key_order, "
        "       ($1::timestamptz < $2::timestamptz) AS cast_order",
        earlier_wire,
        later_wire,
    )
    assert key_row["key_order"] is True
    assert key_row["key_order"] == key_row["cast_order"], (earlier_wire, later_wire)
    assert raw_text_order != key_row["key_order"], (
        "the wire form no longer reproduces the raw-text ordering defect for this pair -- "
        "re-measure earlier_wire/later_wire before trusting this test"
    )

    await db.execute(
        """
        INSERT INTO research_os_objects
            (object_kind, object_id, object_hash, contract_version, payload)
        VALUES (
            'claim', 'ledger-row-21', $2, 'research-os/v1.0.0',
            jsonb_build_object(
                'time', jsonb_build_object('valid_from', $1::text, 'recorded_at', $1::text)
            )
        )
        """,
        earlier_wire,
        HEX64,
    )
    row = await db.fetchrow(
        """
        SELECT
            (payload->'time'->>'valid_from') <= $1 AS raw_text_predicate,
            (public.research_os_instant_key(payload->'time'->>'valid_from') COLLATE "C")
                <= (public.research_os_instant_key($1) COLLATE "C") AS key_predicate
        FROM research_os_objects WHERE object_id = 'ledger-row-21'
        """,
        later_wire,
    )
    assert row["raw_text_predicate"] is False, (
        "raw-text predicate should DROP this row -- if this is now True, the wire form "
        "changed shape and this test's premise needs re-measuring"
    )
    assert row["key_predicate"] is True

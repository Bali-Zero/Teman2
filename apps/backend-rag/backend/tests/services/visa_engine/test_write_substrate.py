"""Integration tests for migration 252 (STEP-6b SHADOW write substrate) —
real Postgres, DDL only. No repository class exists yet for
``visa_decisions``/``visa_decision_payloads``/``visa_source_records`` (the
writer is a later step — see migration 252's header) so every INSERT below
is a raw SQL statement, exactly mirroring how ``test_repository.py`` proved
migration 250's activation triggers before ``activate_rule_pack`` existed
("this exercises exactly the RETAINED ledger structural triggers ... which
are unchanged by the PR4 split").

SIBLING ISOLATION (STEP-6b task's own explicit constraint): another agent is
simultaneously editing this DIRECTORY's ``conftest.py`` and migration 251 in
its OWN worktree. This file:

  * Does NOT import anything from ``conftest.py`` (no ``db_pool``,
    ``visa_schema``, ``repo`` fixture reused) — every fixture below is
    module-local and independently named (``w6b_*`` prefix) so there is zero
    chance of a name collision or accidental fixture override.
  * Does NOT modify ``repository.py`` (only imports and calls
    ``VisaEngineRepository.insert_rule_pack``, already-shipped PR4 code, to
    seed one valid ``visa_rule_packs`` row so ``visa_decisions.rule_pack_id``
    has something real to FK against).
  * Does NOT modify migration 250 or run its rollback/forward SQL against
    the SHARED ``nuzantara_test`` database the rest of this suite (and
    presumably the sibling's own concurrent test run) uses. Instead, every
    fixture here provisions its OWN throwaway, uniquely-named Postgres
    database per test (``CREATE DATABASE`` / ``DROP DATABASE`` against the
    ``postgres`` maintenance DB) and applies migration 250's forward SQL
    read directly off disk (same ``split_migration_sql`` helper
    ``conftest.py`` uses — read-only ``Path.read_text()``, no import from
    that module) followed by migration 252's own forward SQL, inside that
    private database. This is the literal "own pool ... on a throwaway DB"
    instruction: a DDL-heavy fixture (DROP/CREATE TABLE) run against the
    SAME shared ``nuzantara_test`` database while a sibling agent's own test
    run is concurrently exercising that database would be exactly the
    sibling-race hazard CLAUDE.md's cicatrix family #5 describes — a fresh,
    private, disposable database per test sidesteps it entirely rather than
    relying on timing.

Run manually (creates+drops its own throwaway DBs under the admin
connection below — never touches ``nuzantara_dev``/``nuzantara_test``):

    TEST_DATABASE_ADMIN_URL=postgresql://nuzantara@localhost:5432/postgres \\
    PYTHONPATH=. pytest backend/tests/services/visa_engine/test_write_substrate.py -v
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.services.visa_engine.repository import VisaEngineRepository

from ._builders import minimal_valid_envelope

pytestmark = pytest.mark.asyncio

GOLD_EVALUATED_AT = datetime(2026, 7, 19, 0, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Migration SQL — read directly off disk, same technique conftest.py's own
# ``_read_migration_250`` uses (``split_migration_sql``), duplicated here
# rather than imported so this file never touches conftest.py.
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_MIGRATION_250_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "250_visa_engine_core.sql"
_MIGRATION_252_PATH = _BACKEND_DIR / "db" / "migrations_v2" / "252_visa_engine_write_substrate.sql"


def _read_migration(path: Path) -> tuple[str, str]:
    sql = path.read_text(encoding="utf-8")
    forward, rollback = split_migration_sql(sql)
    assert rollback, f"{path.name} must carry a '-- === ROLLBACK ===' section"
    return forward, rollback


# ---------------------------------------------------------------------------
# Throwaway-database fixtures. Function-scoped: every test gets its own
# fresh Postgres database (created via the ``postgres`` maintenance DB),
# migrated, exercised, then dropped — never the shared nuzantara_test/
# nuzantara_dev databases the rest of the suite (and a concurrently-running
# sibling agent) may be using at the same time.
# ---------------------------------------------------------------------------

_ADMIN_URL = os.environ.get(
    "TEST_DATABASE_ADMIN_URL",
    "postgresql://nuzantara@localhost:5432/postgres",
)


def _db_url_for(db_name: str) -> str:
    base = _ADMIN_URL.rsplit("/", 1)[0]
    return f"{base}/{db_name}"


@pytest_asyncio.fixture
async def w6b_pool() -> AsyncIterator[asyncpg.Pool]:
    """A pool to a freshly CREATEd, uniquely-named throwaway database.

    Deliberately codec-less (no ``set_type_codec`` registered) — mirrors
    conftest.py's own plain ``db_pool`` fixture, the "other" pool shape
    ``insert_rule_pack`` must also stay correct against per its own
    docstring; this file's raw INSERTs use bare ``$N::jsonb`` casts (correct
    on a codec-less pool — the double-encode hazard PR4 FIX-FIRST documents
    is specific to a CODEC-registered pool, which this one is not).
    """

    db_name = f"nuzantara_test_visa_w6b_{uuid.uuid4().hex[:16]}"
    admin_conn = await asyncpg.connect(_ADMIN_URL)
    try:
        await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin_conn.close()

    pool = await asyncpg.create_pool(_db_url_for(db_name), min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
        admin_conn = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            await admin_conn.close()


@pytest_asyncio.fixture
async def w6b_schema(w6b_pool: asyncpg.Pool) -> AsyncIterator[None]:
    """Apply migration 250's forward SQL, then migration 252's, inside the
    throwaway database ``w6b_pool`` points at. The whole database is
    dropped by ``w6b_pool``'s own teardown, so no explicit rollback is run
    here — ``test_rollback_drops_cleanly_fk_safe`` below runs 252's
    rollback explicitly, in its own throwaway database, as a dedicated
    correctness test rather than as fixture teardown plumbing.
    """

    forward_250, _ = _read_migration(_MIGRATION_250_PATH)
    forward_252, _ = _read_migration(_MIGRATION_252_PATH)
    async with w6b_pool.acquire() as conn:
        await conn.execute(forward_250)
        await conn.execute(forward_252)
    yield


@pytest_asyncio.fixture
async def w6b_conn(w6b_pool: asyncpg.Pool, w6b_schema: None) -> AsyncIterator[asyncpg.Connection]:
    async with w6b_pool.acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Row builders — raw SQL (no repository layer exists for these 3 tables yet;
# see migration 252's header, "the writer code ... is a later step").
# ---------------------------------------------------------------------------


def _open_range(lower: datetime) -> asyncpg.Range:
    return asyncpg.Range(lower, None, lower_inc=True, upper_inc=False)


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


async def _insert_rule_pack(pool: asyncpg.Pool) -> uuid.UUID:
    """Seed exactly one valid ``visa_rule_packs`` row via the repository
    this package already ships (PR4, ``insert_rule_pack`` — read-only reuse,
    this file never edits ``repository.py``), so ``visa_decisions.rule_pack_id``
    has a real FK target. Uses ``_builders.minimal_valid_envelope()`` — the
    same fixture ``test_bundle_*``/``test_repository.py`` build on — rather
    than hand-rolling a payload shape that has to separately satisfy
    migration 250's ``reject_visa_pack_payload_mismatch`` trigger.
    """

    envelope = minimal_valid_envelope()
    payload = envelope["payload"]
    protected = envelope["protected"]
    rule_pack_id = uuid.UUID(payload["rule_pack_id"])
    payload_sha256 = bytes.fromhex(envelope["payload_sha256"])
    signature = hashlib.sha256(b"w6b-test-signature").digest() * 2  # 64 bytes, shape only

    valid_period = payload["valid_period"]
    lower = _parse_utc(valid_period["from"])
    upper = _parse_utc(valid_period["to"]) if valid_period.get("to") else None
    legal_period = asyncpg.Range(lower, upper, lower_inc=True, upper_inc=False)

    repo = VisaEngineRepository(pool)
    await repo.insert_rule_pack(
        id=rule_pack_id,
        environment=payload["environment"],
        sequence=payload["sequence"],
        pack_version=payload["version"],
        engine_contract_version=payload["engine_contract_version"],
        engine_min_version=payload["engine_min_version"],
        engine_max_version=payload["engine_max_version"],
        legal_period=legal_period,
        protected_header=protected,
        payload=payload,
        payload_sha256=payload_sha256,
        previous_payload_sha256=None,
        signature=signature,
        signing_key_id=protected["kid"],
        signed_at=_parse_utc(protected["signed_at"]),
    )
    return rule_pack_id


async def _insert_decision(
    conn: asyncpg.Connection,
    *,
    decision_id: uuid.UUID | None = None,
    environment: str = "TEST",
    engine_surface: str = "MATCH",
    engine_mode: str = "SHADOW",
    rule_pack_id: uuid.UUID | None,
    rule_pack_sha256: bytes | None = None,
    verdict: str = "NEEDS_INPUT",
    citations: str = "[]",
    engine_version: str = "0.1.0-test",
    evaluated_at: datetime | None = None,
) -> uuid.UUID:
    decision_id = decision_id or uuid.uuid4()
    row = await conn.fetchrow(
        """
        INSERT INTO visa_decisions (
            decision_id, environment, engine_surface, engine_mode,
            rule_pack_id, rule_pack_sha256, verdict, citations,
            engine_version, evaluated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
        RETURNING id
        """,
        decision_id,
        environment,
        engine_surface,
        engine_mode,
        rule_pack_id,
        rule_pack_sha256,
        verdict,
        citations,
        engine_version,
        evaluated_at or GOLD_EVALUATED_AT,
    )
    return row["id"]


async def _insert_decision_payload(
    conn: asyncpg.Connection,
    *,
    decision_id: uuid.UUID,
    encryption_key_id: str = "test-kek-1",
    nonce: bytes | None = None,
    ciphertext: bytes | None = None,
    aad: bytes | None = None,
    ciphertext_sha256: bytes | None = None,
    purge_after: datetime | None = None,
) -> None:
    nonce = nonce if nonce is not None else os.urandom(12)
    ciphertext = ciphertext if ciphertext is not None else b"opaque-ciphertext-bytes-only"
    aad = aad if aad is not None else b"decision-id-binding-context"
    ciphertext_sha256 = ciphertext_sha256 or hashlib.sha256(ciphertext).digest()
    purge_after = purge_after or (GOLD_EVALUATED_AT + timedelta(days=90))
    await conn.execute(
        """
        INSERT INTO visa_decision_payloads (
            decision_id, encryption_key_id, nonce, ciphertext, aad,
            ciphertext_sha256, purge_after
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        decision_id,
        encryption_key_id,
        nonce,
        ciphertext,
        aad,
        ciphertext_sha256,
        purge_after,
    )


async def _insert_source_record(
    conn: asyncpg.Connection,
    *,
    source_id: uuid.UUID | None = None,
    source_key: str = "test-source",
    version: int = 1,
    legal_period: asyncpg.Range | None = None,
    recorded_period: asyncpg.Range | None = None,
) -> uuid.UUID:
    source_id = source_id or uuid.uuid4()
    legal_period = legal_period or _open_range(GOLD_EVALUATED_AT)
    recorded_period = recorded_period or _open_range(GOLD_EVALUATED_AT)
    await conn.execute(
        """
        INSERT INTO visa_source_records (
            id, source_key, version, authority_type, status, jurisdiction,
            title, publisher, canonical_url, language, document_number,
            locators, content_sha256, legal_period, recorded_period,
            retrieved_at, verified_at, verified_by, supersedes_source_record_id
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
            $12::jsonb, $13, $14, $15, $16, $17, $18, $19
        )
        """,
        source_id,
        source_key,
        version,
        "PRIMARY_LAW",
        "VERIFIED",
        "ID",
        "Test Source Title",
        "Test Publisher",
        "https://example.com/source",
        "en",
        None,
        "[]",
        hashlib.sha256(b"source-content").digest(),
        legal_period,
        recorded_period,
        GOLD_EVALUATED_AT,
        GOLD_EVALUATED_AT,
        "test-verifier",
        None,
    )
    return source_id


# ---------------------------------------------------------------------------
# 1. Forward creates every object.
# ---------------------------------------------------------------------------


async def test_forward_creates_all_objects(w6b_conn: asyncpg.Connection) -> None:
    tables = await w6b_conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('visa_decisions', 'visa_decision_payloads', 'visa_source_records')
        """
    )
    assert {r["table_name"] for r in tables} == {
        "visa_decisions",
        "visa_decision_payloads",
        "visa_source_records",
    }

    triggers = await w6b_conn.fetch(
        """
        SELECT event_object_table, trigger_name FROM information_schema.triggers
        WHERE trigger_schema = 'public'
          AND event_object_table IN ('visa_decisions', 'visa_decision_payloads', 'visa_source_records')
        """
    )
    trigger_pairs = {(r["event_object_table"], r["trigger_name"]) for r in triggers}
    assert ("visa_decisions", "visa_decisions_immutable") in trigger_pairs
    assert ("visa_decision_payloads", "visa_decision_payloads_immutable") in trigger_pairs
    assert ("visa_source_records", "visa_source_records_immutable") in trigger_pairs

    fn = await w6b_conn.fetchval(
        "SELECT 1 FROM pg_proc WHERE proname = 'reject_visa_write_substrate_mutation'"
    )
    assert fn == 1


# ---------------------------------------------------------------------------
# 2. Append-only guilt + innocence, per table.
# ---------------------------------------------------------------------------


async def test_visa_decisions_insert_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    # `_insert_decision` returns the row's surrogate `id` (its RETURNING
    # clause), not the domain `decision_id` column — see that helper's
    # docstring-equivalent comment on `visa_decision_payloads.decision_id`
    # below, which FKs to this same surrogate `id`.
    row_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    count = await w6b_conn.fetchval("SELECT count(*) FROM visa_decisions WHERE id = $1", row_id)
    assert count == 1


async def test_visa_decisions_update_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute("UPDATE visa_decisions SET verdict = 'NO_SUPPORTED_PATH'")


async def test_visa_decisions_delete_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute("DELETE FROM visa_decisions")


async def test_visa_decision_payloads_insert_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id)
    count = await w6b_conn.fetchval(
        "SELECT count(*) FROM visa_decision_payloads WHERE decision_id = $1", decision_id
    )
    assert count == 1


async def test_visa_decision_payloads_update_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute("UPDATE visa_decision_payloads SET encryption_key_id = 'rotated'")


async def test_visa_decision_payloads_delete_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute("DELETE FROM visa_decision_payloads")


async def test_visa_source_records_insert_innocence(w6b_conn: asyncpg.Connection) -> None:
    source_id = await _insert_source_record(w6b_conn)
    count = await w6b_conn.fetchval(
        "SELECT count(*) FROM visa_source_records WHERE id = $1", source_id
    )
    assert count == 1


async def test_visa_source_records_update_guilt(w6b_conn: asyncpg.Connection) -> None:
    await _insert_source_record(w6b_conn)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute("UPDATE visa_source_records SET title = 'edited in place'")


async def test_visa_source_records_delete_guilt(w6b_conn: asyncpg.Connection) -> None:
    await _insert_source_record(w6b_conn)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute("DELETE FROM visa_source_records")


# ---------------------------------------------------------------------------
# 3. FK guilt — a decision referencing an unknown pack, and a payload
#    referencing an unknown decision, both raise.
# ---------------------------------------------------------------------------


async def test_decision_unknown_rule_pack_fk_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        await _insert_decision(w6b_conn, rule_pack_id=uuid.uuid4(), verdict="NEEDS_INPUT")


async def test_decision_payload_unknown_decision_fk_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
        await _insert_decision_payload(w6b_conn, decision_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# 4. Verdict CHECK — the exact DecisionState 5-value vocabulary; anything
#    else (including a plausible-sounding but non-real value) is rejected.
# ---------------------------------------------------------------------------


async def test_decision_verdict_check_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, verdict="ELIGIBLE")


@pytest.mark.parametrize(
    "verdict",
    [
        "NEEDS_INPUT",
        "SUPPORTED_CANDIDATES",
        "HUMAN_REVIEW_REQUIRED",
        "NO_SUPPORTED_PATH",
    ],
)
async def test_decision_verdict_check_innocence_requires_pack(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection, verdict: str
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, verdict=verdict)
    assert decision_id is not None


async def test_decision_temporarily_unavailable_allows_null_rule_pack_innocence(
    w6b_conn: asyncpg.Connection,
) -> None:
    decision_id = await _insert_decision(
        w6b_conn, rule_pack_id=None, verdict="TEMPORARILY_UNAVAILABLE"
    )
    assert decision_id is not None


async def test_decision_requires_rule_pack_unless_unavailable_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_decision(w6b_conn, rule_pack_id=None, verdict="NEEDS_INPUT")


async def test_decision_engine_mode_check_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, engine_mode="OFF")


async def test_decision_engine_surface_check_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, engine_surface="BOGUS_SURFACE")


# ---------------------------------------------------------------------------
# 5. citations must be a JSONB array — object/string rejected, array (incl.
#    empty) accepted.
# ---------------------------------------------------------------------------


async def test_decision_citations_object_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_decision(
            w6b_conn, rule_pack_id=rule_pack_id, citations='{"source_id": "not-an-array"}'
        )


async def test_decision_citations_string_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, citations='"a bare string"')


async def test_decision_citations_array_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(
        w6b_conn,
        rule_pack_id=rule_pack_id,
        citations='["11111111-1111-1111-1111-111111111111"]',
    )
    assert decision_id is not None


# ---------------------------------------------------------------------------
# 6. visa_source_records bitemporal guard — the same "-infinity lower bound
#    rejected" hardening migration 250 applies to its own legal_period.
# ---------------------------------------------------------------------------


async def test_source_record_legal_period_infinity_guard_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    bad_range = asyncpg.Range(None, None, lower_inc=True, upper_inc=False)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, legal_period=bad_range)


# ---------------------------------------------------------------------------
# 7. PII-discipline structural tripwire — no column on any of the three
#    tables may be a PII-shaped identifier (name/email/passport/phone/...).
#    Word-boundary (underscore-token) matching, NOT bare substring — a
#    column like ``authority_type`` or ``publisher`` must never trip this
#    (guard-over-match discipline, cicatrix family #3).
# ---------------------------------------------------------------------------

_PII_TOKENS = frozenset(
    {"name", "email", "passport", "phone", "address", "dob", "npwp", "nik", "ktp", "ssn"}
)


async def test_pii_structural_tripwire(w6b_conn: asyncpg.Connection) -> None:
    rows = await w6b_conn.fetch(
        """
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name IN ('visa_decisions', 'visa_decision_payloads', 'visa_source_records')
        """
    )
    assert rows, "expected columns for all three write-substrate tables"
    offenders = []
    for row in rows:
        tokens = row["column_name"].lower().split("_")
        if _PII_TOKENS.intersection(tokens):
            offenders.append(f"{row['table_name']}.{row['column_name']}")
    assert not offenders, f"PII-shaped column name(s) found: {offenders}"


# ---------------------------------------------------------------------------
# 8. Rollback drops cleanly, FK-safe, and leaves migration 250 untouched.
# ---------------------------------------------------------------------------


async def test_rollback_drops_cleanly_fk_safe(w6b_pool: asyncpg.Pool, w6b_schema: None) -> None:
    _, rollback_252 = _read_migration(_MIGRATION_252_PATH)

    async with w6b_pool.acquire() as conn:
        # Populate all three tables first — a clean rollback must succeed
        # even with rows present (FK-safe drop order), not just on empty
        # tables.
        rule_pack_id = await _insert_rule_pack(w6b_pool)
        decision_id = await _insert_decision(conn, rule_pack_id=rule_pack_id)
        await _insert_decision_payload(conn, decision_id=decision_id)
        await _insert_source_record(conn)

        await conn.execute(rollback_252)

        remaining = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'visa_decisions', 'visa_decision_payloads', 'visa_source_records'
              )
            """
        )
        assert remaining == []

        fn = await conn.fetchval(
            "SELECT 1 FROM pg_proc WHERE proname = 'reject_visa_write_substrate_mutation'"
        )
        assert fn is None

        # Migration 250's own objects must be completely untouched.
        still_there = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('visa_rule_packs', 'visa_ruleset_activations')
            """
        )
        assert {r["table_name"] for r in still_there} == {
            "visa_rule_packs",
            "visa_ruleset_activations",
        }
        pack_count = await conn.fetchval("SELECT count(*) FROM visa_rule_packs")
        assert pack_count == 1
        immutable_fn = await conn.fetchval(
            "SELECT 1 FROM pg_proc WHERE proname = 'reject_visa_immutable_mutation'"
        )
        assert immutable_fn == 1

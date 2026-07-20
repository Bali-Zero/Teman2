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

Run manually (creates+drops its own throwaway DBs via an admin connection
derived from ``TEST_DATABASE_URL`` — same env var conftest.py's
``db_pool``/``visa_schema`` fixtures read, swapped to the ``postgres``
maintenance DB; see ``_ADMIN_URL`` below — never touches
``nuzantara_dev``/``nuzantara_test`` themselves):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \\
    PYTHONPATH=. pytest backend/tests/services/visa_engine/test_write_substrate.py -v
"""

from __future__ import annotations

import hashlib
import json
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

# CI-gate fix (2026-07-20): this used to read a SECOND, never-provisioned
# env var (``TEST_DATABASE_ADMIN_URL``) whose hardcoded fallback
# (``postgresql://nuzantara@localhost:5432/postgres``) only resolves on a
# macOS dev box where the OS user ``nuzantara`` is itself a passwordless
# Postgres superuser -- CI's postgres service (tests.yml: ``postgres:15``
# with ``POSTGRES_USER=test`` / ``POSTGRES_PASSWORD=test`` /
# ``POSTGRES_DB=nuzantara_test``) has neither that user nor a trust-auth
# connection, so every CI run failed deterministically at fixture setup
# with ``InvalidPasswordError: password authentication failed for user
# "nuzantara"``. The sibling fixtures in this SAME suite (conftest.py's
# ``db_pool``/``visa_schema``, used by test_activation_writer.py /
# test_repository.py) already pass in CI by reading ``TEST_DATABASE_URL``
# instead -- the one env var CI actually exports (and
# ``backend/tests/conftest.py``, the root conftest, ``setdefault``s
# locally before any test module imports). Mirrored here (duplicated
# rather than imported, per this file's own "SIBLING ISOLATION" note
# above -- module-local, zero coupling to conftest.py's fixtures) rather
# than inventing a third convention: read that SAME env var, then swap
# its database name for ``postgres`` -- the maintenance DB every
# Postgres install ships, and the one CI's ``test`` role (superuser, per
# the official Docker postgres image's POSTGRES_USER contract) can always
# CREATE DATABASE / DROP DATABASE against.
_ADMIN_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
).rsplit("/", 1)[0] + "/postgres"


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


def _closed_range(lower: datetime, upper: datetime) -> asyncpg.Range:
    return asyncpg.Range(lower, upper, lower_inc=True, upper_inc=False)


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


async def _fetch_pack(pool: asyncpg.Pool, rule_pack_id: uuid.UUID) -> asyncpg.Record:
    """Read back a seeded pack's own environment/jurisdiction/decision_domain/
    legal_period/payload_sha256 -- used to build a MATCHING (or deliberately
    mismatching) ``visa_ruleset_activations`` row / decision row without
    hand-duplicating ``minimal_valid_envelope()``'s constants."""

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT environment, jurisdiction, decision_domain, legal_period, payload_sha256
            FROM visa_rule_packs WHERE id = $1
            """,
            rule_pack_id,
        )
    assert row is not None
    return row


async def _insert_activation(
    pool: asyncpg.Pool,
    *,
    rule_pack_id: uuid.UUID,
    legal_period: asyncpg.Range | None = None,
    system_period: asyncpg.Range | None = None,
    activated_by: str = "w6b-test",
    activation_reason: str = "w6b write-substrate test activation",
) -> uuid.UUID:
    """Seed exactly one ``visa_ruleset_activations`` row (migration 250) for
    the given pack, satisfying migration 250's own
    ``reject_visa_activation_insert`` trigger (scope/legal_period must equal
    the pack's own; bootstrap sequence/hash-chain requires this be the FIRST
    activation for the triple, true for every throwaway DB this file uses).
    """

    pack = await _fetch_pack(pool, rule_pack_id)
    legal_period = legal_period or pack["legal_period"]
    system_period = system_period or _open_range(GOLD_EVALUATED_AT)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO visa_ruleset_activations (
                rule_pack_id, environment, jurisdiction, decision_domain,
                legal_period, system_period, activated_by, activation_reason
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            rule_pack_id,
            pack["environment"],
            pack["jurisdiction"],
            pack["decision_domain"],
            legal_period,
            system_period,
            activated_by,
            activation_reason,
        )
    return row["id"]


async def _insert_decision(
    conn: asyncpg.Connection,
    *,
    decision_id: uuid.UUID | None = None,
    environment: str = "TEST",
    engine_surface: str = "MATCH",
    engine_mode: str = "SHADOW",
    rule_pack_id: uuid.UUID | None,
    ruleset_activation_id: uuid.UUID | None = None,
    rule_pack_sha256: bytes | None = None,
    verdict: str = "NEEDS_INPUT",
    citations: str = "[]",
    engine_version: str = "0.1.0-test",
    effective_at: datetime | None = None,
    observed_at: datetime | None = None,
    evaluated_at: datetime | None = None,
) -> uuid.UUID:
    decision_id = decision_id or uuid.uuid4()
    row = await conn.fetchrow(
        """
        INSERT INTO visa_decisions (
            decision_id, environment, engine_surface, engine_mode,
            rule_pack_id, ruleset_activation_id, rule_pack_sha256, verdict,
            citations, engine_version, effective_at, observed_at, evaluated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $12, $13)
        RETURNING id
        """,
        decision_id,
        environment,
        engine_surface,
        engine_mode,
        rule_pack_id,
        ruleset_activation_id,
        rule_pack_sha256,
        verdict,
        citations,
        engine_version,
        effective_at or GOLD_EVALUATED_AT,
        observed_at or GOLD_EVALUATED_AT,
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
    title: str = "Test Source Title",
    publisher: str = "Test Publisher",
    canonical_url: str = "https://example.com/source",
    locators: str = "[]",
    legal_period: asyncpg.Range | None = None,
    recorded_period: asyncpg.Range | None = None,
    supersedes_source_record_id: uuid.UUID | None = None,
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
        title,
        publisher,
        canonical_url,
        "en",
        None,
        locators,
        hashlib.sha256(b"source-content").digest(),
        legal_period,
        recorded_period,
        GOLD_EVALUATED_AT,
        GOLD_EVALUATED_AT,
        "test-verifier",
        supersedes_source_record_id,
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
    assert ("visa_decisions", "visa_decisions_pack_binding") in trigger_pairs
    # Renamed from *_immutable to *_guard (STEP-6b FIX-FIRST P1/P2): these two
    # tables are no longer strictly immutable (legal_hold-only update + expiry
    # delete on payloads; recorded_period-close-only update on source
    # records) -- a lying trigger name is its own bug class.
    assert ("visa_decision_payloads", "visa_decision_payloads_guard") in trigger_pairs
    assert ("visa_source_records", "visa_source_records_guard") in trigger_pairs
    assert ("visa_source_records", "visa_source_records_supersedes_binding") in trigger_pairs

    # information_schema.triggers does NOT list TRUNCATE triggers (documented
    # Postgres limitation -- empirically confirmed: a bare BEFORE TRUNCATE ...
    # FOR EACH STATEMENT trigger is invisible there but present in pg_trigger).
    # Query pg_trigger directly for the three *_no_wipe TRUNCATE guards.
    truncate_triggers = await w6b_conn.fetch(
        """
        SELECT c.relname AS table_name, t.tgname AS trigger_name
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        WHERE NOT t.tgisinternal
          AND c.relname IN ('visa_decisions', 'visa_decision_payloads', 'visa_source_records')
          AND t.tgname LIKE '%_no_wipe'
        """
    )
    truncate_pairs = {(r["table_name"], r["trigger_name"]) for r in truncate_triggers}
    assert ("visa_decisions", "visa_decisions_no_wipe") in truncate_pairs
    assert ("visa_decision_payloads", "visa_decision_payloads_no_wipe") in truncate_pairs
    assert ("visa_source_records", "visa_source_records_no_wipe") in truncate_pairs

    fn = await w6b_conn.fetchval(
        "SELECT 1 FROM pg_proc WHERE proname = 'reject_visa_write_substrate_mutation'"
    )
    assert fn == 1
    for fn_name in (
        "reject_visa_decision_pack_binding",
        "reject_visa_decision_payloads_mutation",
        "reject_visa_source_records_mutation",
        "reject_visa_source_record_supersedes_mismatch",
    ):
        fn = await w6b_conn.fetchval("SELECT 1 FROM pg_proc WHERE proname = $1", fn_name)
        assert fn == 1, f"missing function {fn_name}"


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
#
#    NOTE (STEP-6b FIX-FIRST): the decision case now raises via
#    reject_visa_decision_pack_binding()'s own existence check rather than
#    the bare FK — that BEFORE INSERT trigger runs before Postgres's
#    IMMEDIATE FK check and gives an earlier, clearer error for the exact
#    same "unknown rule_pack_id" condition. Intentional, disclosed behavior
#    change (not a regression): the FK still exists as defense-in-depth for
#    any future insert path that might bypass the trigger.
# ---------------------------------------------------------------------------


async def test_decision_unknown_rule_pack_fk_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.RaiseError, match="unknown rule_pack_id"):
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
# 8. visa_source_records GiST EXCLUDE (source_key WITH =, legal_period
#    WITH &&, recorded_period WITH &&) — STEP-6b verify-round P2 coverage
#    gap: the '-infinity' guard was tested above, but the EXCLUDE constraint
#    itself (the whole point of the bitemporal design — no two rows may
#    claim overlapping legal+recorded periods for the same source_key) was
#    never proven to actually reject an overlapping pair.
# ---------------------------------------------------------------------------


async def test_source_record_exclude_overlapping_pair_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    shared_key = "exclude-guilt-source"
    overlapping_legal = _closed_range(GOLD_EVALUATED_AT, GOLD_EVALUATED_AT + timedelta(days=365))
    overlapping_recorded = _open_range(GOLD_EVALUATED_AT)
    await _insert_source_record(
        w6b_conn,
        source_key=shared_key,
        version=1,
        legal_period=overlapping_legal,
        recorded_period=overlapping_recorded,
    )
    with pytest.raises(asyncpg.exceptions.ExclusionViolationError):
        await _insert_source_record(
            w6b_conn,
            source_key=shared_key,
            version=2,
            legal_period=overlapping_legal,
            recorded_period=overlapping_recorded,
        )


async def test_source_record_exclude_disjoint_legal_period_innocence(
    w6b_conn: asyncpg.Connection,
) -> None:
    shared_key = "exclude-innocence-source"
    first_legal = _closed_range(GOLD_EVALUATED_AT, GOLD_EVALUATED_AT + timedelta(days=365))
    second_legal = _open_range(GOLD_EVALUATED_AT + timedelta(days=365))
    # recorded_period stays open-ended (overlapping) for both rows — EXCLUDE
    # only fires when source_key AND legal_period AND recorded_period all
    # overlap simultaneously, so a disjoint legal_period alone is enough to
    # prove innocence even with everything else identical.
    await _insert_source_record(w6b_conn, source_key=shared_key, version=1, legal_period=first_legal)
    second_id = await _insert_source_record(
        w6b_conn, source_key=shared_key, version=2, legal_period=second_legal
    )
    assert second_id is not None


# ---------------------------------------------------------------------------
# 9. visa_decision_payloads UNIQUE (encryption_key_id, nonce) — STEP-6b
#    FIX-FIRST P0: an AEAD nonce must never repeat under the same key
#    (nonce reuse breaks GCM's confidentiality guarantee outright).
# ---------------------------------------------------------------------------


async def test_payload_duplicate_key_and_nonce_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id_1 = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    decision_id_2 = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    shared_nonce = os.urandom(12)
    await _insert_decision_payload(
        w6b_conn, decision_id=decision_id_1, encryption_key_id="shared-kek", nonce=shared_nonce
    )
    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        await _insert_decision_payload(
            w6b_conn, decision_id=decision_id_2, encryption_key_id="shared-kek", nonce=shared_nonce
        )


async def test_payload_same_key_different_nonce_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id_1 = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    decision_id_2 = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id_1, encryption_key_id="shared-kek-2")
    await _insert_decision_payload(w6b_conn, decision_id=decision_id_2, encryption_key_id="shared-kek-2")
    count = await w6b_conn.fetchval(
        "SELECT count(*) FROM visa_decision_payloads WHERE encryption_key_id = 'shared-kek-2'"
    )
    assert count == 2


# ---------------------------------------------------------------------------
# 10. Decision <-> rule_pack scope binding (STEP-6b FIX-FIRST P0/P1) — a
#     decision can never claim a scope/hash its referenced pack does not
#     have. Skips entirely when rule_pack_id IS NULL, already proven by
#     test_decision_temporarily_unavailable_allows_null_rule_pack_innocence
#     above.
# ---------------------------------------------------------------------------


async def test_decision_pack_binding_environment_mismatch_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)  # pack environment == "TEST"
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match referenced rule_pack"):
        await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, environment="PRODUCTION")


async def test_decision_pack_binding_wrong_sha_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    wrong_sha = hashlib.sha256(b"not-the-real-pack-bytes").digest()
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not match referenced rule_pack"):
        await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id, rule_pack_sha256=wrong_sha)


async def test_decision_pack_binding_correct_sha_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    pack = await _fetch_pack(w6b_pool, rule_pack_id)
    decision_id = await _insert_decision(
        w6b_conn, rule_pack_id=rule_pack_id, rule_pack_sha256=pack["payload_sha256"]
    )
    assert decision_id is not None


# ---------------------------------------------------------------------------
# 11. Decision <-> ruleset_activation containment (STEP-6b FIX-FIRST P1) —
#     when ruleset_activation_id is set, effective_at must fall within that
#     activation's legal_period and observed_at within its system_period.
# ---------------------------------------------------------------------------


async def test_decision_activation_containment_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    activation_id = await _insert_activation(w6b_pool, rule_pack_id=rule_pack_id)
    decision_id = await _insert_decision(
        w6b_conn,
        rule_pack_id=rule_pack_id,
        ruleset_activation_id=activation_id,
        effective_at=GOLD_EVALUATED_AT,
        observed_at=GOLD_EVALUATED_AT,
    )
    assert decision_id is not None


async def test_decision_activation_effective_at_outside_legal_period_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    activation_id = await _insert_activation(w6b_pool, rule_pack_id=rule_pack_id)
    before_legal_period = GOLD_EVALUATED_AT - timedelta(days=3650)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="outside referenced activation"):
        await _insert_decision(
            w6b_conn,
            rule_pack_id=rule_pack_id,
            ruleset_activation_id=activation_id,
            effective_at=before_legal_period,
            observed_at=GOLD_EVALUATED_AT,
        )


async def test_decision_activation_observed_at_outside_system_period_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    activation_id = await _insert_activation(w6b_pool, rule_pack_id=rule_pack_id)
    before_system_period = GOLD_EVALUATED_AT - timedelta(days=3650)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="outside referenced activation"):
        await _insert_decision(
            w6b_conn,
            rule_pack_id=rule_pack_id,
            ruleset_activation_id=activation_id,
            effective_at=GOLD_EVALUATED_AT,
            observed_at=before_system_period,
        )


async def test_decision_unknown_ruleset_activation_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="unknown ruleset_activation_id"):
        await _insert_decision(
            w6b_conn, rule_pack_id=rule_pack_id, ruleset_activation_id=uuid.uuid4()
        )


# ---------------------------------------------------------------------------
# 11b. STEP-6b gate round-2 fix (Codex gpt-5.6-sol FIX-FIRST, 2026-07-20):
#      reject_visa_decision_pack_binding() used to short-circuit its ENTIRE
#      body -- including the activation-containment block above -- the
#      moment rule_pack_id was NULL. Per the migration header's own
#      amendment, activation containment is gated SOLELY on
#      ruleset_activation_id IS NOT NULL, independent of rule_pack_id.
#      These tests prove the rule_pack_id=NULL case is no longer a
#      containment-check bypass: a TEMPORARILY_UNAVAILABLE decision
#      (rule_pack_id NULL) with a NOT NULL ruleset_activation_id still gets
#      the SAME containment/existence scrutiny as a pack-bearing decision.
# ---------------------------------------------------------------------------


async def test_decision_null_pack_activation_outside_legal_period_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    """rule_pack_id=NULL + ruleset_activation_id pointing at an activation
    whose legal_period does NOT contain effective_at -> still raises. Before
    the fix, the NULL rule_pack_id alone would have skipped this check
    entirely, admitting the row with zero validation of the reference."""
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    activation_id = await _insert_activation(w6b_pool, rule_pack_id=rule_pack_id)
    before_legal_period = GOLD_EVALUATED_AT - timedelta(days=3650)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="outside referenced activation"):
        await _insert_decision(
            w6b_conn,
            rule_pack_id=None,
            verdict="TEMPORARILY_UNAVAILABLE",
            ruleset_activation_id=activation_id,
            effective_at=before_legal_period,
            observed_at=GOLD_EVALUATED_AT,
        )


async def test_decision_null_pack_unknown_activation_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    """rule_pack_id=NULL + an unknown (nonexistent) ruleset_activation_id ->
    still raises. Same bypass class as the guilt test above, but for the
    "activation doesn't exist at all" branch rather than "exists but
    doesn't contain effective_at"."""
    with pytest.raises(asyncpg.exceptions.RaiseError, match="unknown ruleset_activation_id"):
        await _insert_decision(
            w6b_conn,
            rule_pack_id=None,
            verdict="TEMPORARILY_UNAVAILABLE",
            ruleset_activation_id=uuid.uuid4(),
        )


async def test_decision_null_pack_null_activation_innocence(
    w6b_conn: asyncpg.Connection,
) -> None:
    """rule_pack_id=NULL + ruleset_activation_id=NULL (the plain
    TEMPORARILY_UNAVAILABLE case, no pack and no activation to bind
    against) -> passes. Same case as
    test_decision_temporarily_unavailable_allows_null_rule_pack_innocence
    above; restated here alongside its guilt siblings so this section's
    guilt+innocence pair is self-contained (cicatrix family #3 discipline)."""
    decision_id = await _insert_decision(
        w6b_conn, rule_pack_id=None, verdict="TEMPORARILY_UNAVAILABLE", ruleset_activation_id=None
    )
    assert decision_id is not None


async def test_decision_null_pack_activation_containing_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    """rule_pack_id=NULL + ruleset_activation_id pointing at an activation
    that DOES contain effective_at/observed_at -> passes. Proves the fix
    isn't merely "skip the pack-binding block AND always reject" -- a
    legitimately-contained activation reference is still admitted even
    without a rule_pack_id, since the activation<->rule_pack cross-check is
    itself skipped when rule_pack_id is NULL (nothing to cross-check
    against)."""
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    activation_id = await _insert_activation(w6b_pool, rule_pack_id=rule_pack_id)
    decision_id = await _insert_decision(
        w6b_conn,
        rule_pack_id=None,
        verdict="TEMPORARILY_UNAVAILABLE",
        ruleset_activation_id=activation_id,
        effective_at=GOLD_EVALUATED_AT,
        observed_at=GOLD_EVALUATED_AT,
    )
    assert decision_id is not None


# ---------------------------------------------------------------------------
# 12. visa_decision_payloads guard carve-out (STEP-6b FIX-FIRST P1/P2) — the
#     ONLY legal UPDATE flips legal_hold; the ONLY legal DELETE requires an
#     elapsed purge_after AND legal_hold=false.
# ---------------------------------------------------------------------------


async def test_payload_legal_hold_only_update_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id)
    await w6b_conn.execute(
        "UPDATE visa_decision_payloads SET legal_hold = TRUE WHERE decision_id = $1", decision_id
    )
    legal_hold = await w6b_conn.fetchval(
        "SELECT legal_hold FROM visa_decision_payloads WHERE decision_id = $1", decision_id
    )
    assert legal_hold is True


async def test_payload_update_other_column_alongside_legal_hold_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="legal_hold-only carve-out"):
        await w6b_conn.execute(
            "UPDATE visa_decision_payloads SET legal_hold = TRUE, encryption_key_id = 'rotated' "
            "WHERE decision_id = $1",
            decision_id,
        )


async def test_payload_delete_after_purge_elapsed_and_no_legal_hold_innocence(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    past_purge = datetime.now(timezone.utc) - timedelta(days=1)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id, purge_after=past_purge)
    await w6b_conn.execute("DELETE FROM visa_decision_payloads WHERE decision_id = $1", decision_id)
    count = await w6b_conn.fetchval(
        "SELECT count(*) FROM visa_decision_payloads WHERE decision_id = $1", decision_id
    )
    assert count == 0


async def test_payload_delete_with_legal_hold_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    past_purge = datetime.now(timezone.utc) - timedelta(days=1)
    await _insert_decision_payload(w6b_conn, decision_id=decision_id, purge_after=past_purge)
    await w6b_conn.execute(
        "UPDATE visa_decision_payloads SET legal_hold = TRUE WHERE decision_id = $1", decision_id
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        await w6b_conn.execute(
            "DELETE FROM visa_decision_payloads WHERE decision_id = $1", decision_id
        )


# ---------------------------------------------------------------------------
# 13. visa_source_records guard carve-out (STEP-6b FIX-FIRST P1/P2) — the
#     ONLY legal UPDATE closes an open recorded_period (upper NULL -> finite)
#     with every other column, including the lower bound, unchanged.
# ---------------------------------------------------------------------------


async def test_source_record_close_recorded_period_innocence(
    w6b_conn: asyncpg.Connection,
) -> None:
    source_id = await _insert_source_record(w6b_conn)
    closed_at = GOLD_EVALUATED_AT + timedelta(days=1)
    await w6b_conn.execute(
        """
        UPDATE visa_source_records
        SET recorded_period = tstzrange(lower(recorded_period), $2, '[)')
        WHERE id = $1
        """,
        source_id,
        closed_at,
    )
    upper = await w6b_conn.fetchval(
        "SELECT upper(recorded_period) FROM visa_source_records WHERE id = $1", source_id
    )
    assert upper == closed_at


async def test_source_record_reclose_guilt(w6b_conn: asyncpg.Connection) -> None:
    source_id = await _insert_source_record(w6b_conn)
    closed_at = GOLD_EVALUATED_AT + timedelta(days=1)
    await w6b_conn.execute(
        """
        UPDATE visa_source_records
        SET recorded_period = tstzrange(lower(recorded_period), $2, '[)')
        WHERE id = $1
        """,
        source_id,
        closed_at,
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="already closed"):
        await w6b_conn.execute(
            """
            UPDATE visa_source_records
            SET recorded_period = tstzrange(lower(recorded_period), $2, '[)')
            WHERE id = $1
            """,
            source_id,
            closed_at + timedelta(days=1),
        )


async def test_source_record_close_must_be_finite_guilt(w6b_conn: asyncpg.Connection) -> None:
    source_id = await _insert_source_record(w6b_conn)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="finite recorded_period"):
        await w6b_conn.execute(
            "UPDATE visa_source_records SET recorded_period = recorded_period WHERE id = $1",
            source_id,
        )


async def test_source_record_close_infinity_upper_guilt(w6b_conn: asyncpg.Connection) -> None:
    """STEP-6b gate round-2 fix (Codex gpt-5.6-sol FIX-FIRST, 2026-07-20):
    ``upper(...) IS NULL`` alone (the check the guilt test above proves)
    does NOT reject a non-finite close via the explicit 'infinity'
    sentinel -- Postgres treats an upper bound literally set to
    'infinity'::timestamptz as a present (non-NULL) value distinct from an
    unbounded range end, so this used to slip past the old NULL-only guard
    while remaining functionally open-ended forever (a supersession
    dead-end: the row could never be re-closed, and the GiST EXCLUDE
    constraint would still treat it as overlapping). The literal SQL
    'infinity'::timestamptz below is constructed entirely server-side
    (never round-tripped through a Python datetime), matching exactly how
    a raw/hand-written UPDATE could attempt this."""
    source_id = await _insert_source_record(w6b_conn)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="finite recorded_period"):
        await w6b_conn.execute(
            """
            UPDATE visa_source_records
            SET recorded_period = tstzrange(lower(recorded_period), 'infinity'::timestamptz, '[)')
            WHERE id = $1
            """,
            source_id,
        )


async def test_source_record_insert_infinity_recorded_period_upper_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    """STEP-6b gate round-2 fix: the trigger-level guard above only fires
    on UPDATE/DELETE (``visa_source_records_guard`` is ``BEFORE UPDATE OR
    DELETE`` only -- INSERT is structurally unrestricted, this being an
    append-only table). A direct INSERT setting recorded_period's upper
    bound to the literal 'infinity'::timestamptz sentinel must still be
    rejected -- by the mirroring table CHECK added alongside the trigger
    fix, since the trigger itself never runs on INSERT and so cannot be
    what catches this path."""
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await w6b_conn.execute(
            """
            INSERT INTO visa_source_records (
                id, source_key, version, authority_type, status, jurisdiction,
                title, publisher, canonical_url, language, document_number,
                locators, content_sha256, legal_period, recorded_period,
                retrieved_at, verified_at, verified_by, supersedes_source_record_id
            ) VALUES (
                $1, $2, 1, 'PRIMARY_LAW', 'VERIFIED', 'ID',
                'Test Source Title', 'Test Publisher', 'https://example.com/source', 'en', NULL,
                '[]'::jsonb, $3, tstzrange($4, NULL, '[)'),
                tstzrange($4, 'infinity'::timestamptz, '[)'),
                $4, $4, 'test-verifier', NULL
            )
            """,
            uuid.uuid4(),
            "infinity-upper-check-source",
            hashlib.sha256(b"source-content").digest(),
            GOLD_EVALUATED_AT,
        )


async def test_source_record_shift_recorded_period_lower_bound_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    source_id = await _insert_source_record(w6b_conn)
    shifted_lower = GOLD_EVALUATED_AT + timedelta(days=1)
    with pytest.raises(asyncpg.exceptions.RaiseError, match="recorded_period-close carve-out"):
        await w6b_conn.execute(
            "UPDATE visa_source_records SET recorded_period = tstzrange($2, NULL, '[)') WHERE id = $1",
            source_id,
            shifted_lower,
        )


# ---------------------------------------------------------------------------
# 14. supersedes_source_record_id integrity (STEP-6b FIX-FIRST P2) — self-
#     reference rejected, a genuinely missing referent rejected (by the
#     trigger's own existence check, which runs BEFORE Postgres's IMMEDIATE
#     FK check since this is a BEFORE INSERT row trigger), and a
#     cross-source_key supersession rejected. Valid same-lineage supersession
#     succeeds.
# ---------------------------------------------------------------------------


async def test_source_record_supersedes_self_reference_guilt(w6b_conn: asyncpg.Connection) -> None:
    self_id = uuid.uuid4()
    with pytest.raises(asyncpg.exceptions.RaiseError, match="cannot reference its own row"):
        await _insert_source_record(w6b_conn, source_id=self_id, supersedes_source_record_id=self_id)


async def test_source_record_supersedes_missing_referent_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    with pytest.raises(asyncpg.exceptions.RaiseError, match="does not reference an existing row"):
        await _insert_source_record(w6b_conn, supersedes_source_record_id=uuid.uuid4())


async def test_source_record_supersedes_cross_source_key_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    original_id = await _insert_source_record(w6b_conn, source_key="lineage-a")
    with pytest.raises(asyncpg.exceptions.RaiseError, match="must share the same source_key"):
        await _insert_source_record(
            w6b_conn, source_key="lineage-b", supersedes_source_record_id=original_id
        )


async def test_source_record_supersedes_same_source_key_innocence(
    w6b_conn: asyncpg.Connection,
) -> None:
    # Disjoint legal_period on the new row -- same source_key + overlapping
    # legal_period would instead trip the EXCLUDE constraint (section 8
    # above), which is a DIFFERENT guard than the one this test targets.
    first_legal = _closed_range(GOLD_EVALUATED_AT, GOLD_EVALUATED_AT + timedelta(days=365))
    second_legal = _open_range(GOLD_EVALUATED_AT + timedelta(days=365))
    original_id = await _insert_source_record(
        w6b_conn, source_key="lineage-c", version=1, legal_period=first_legal
    )
    new_id = await _insert_source_record(
        w6b_conn,
        source_key="lineage-c",
        version=2,
        legal_period=second_legal,
        supersedes_source_record_id=original_id,
    )
    assert new_id != original_id


# ---------------------------------------------------------------------------
# 15. Cheap CHECKs mirroring models.py::SourceRecord's own Pydantic bounds,
#     plus encryption_algorithm pinning and the recorded_period -infinity
#     guard (STEP-6b FIX-FIRST P2).
# ---------------------------------------------------------------------------


async def test_payload_encryption_algorithm_check_guilt(
    w6b_pool: asyncpg.Pool, w6b_conn: asyncpg.Connection
) -> None:
    rule_pack_id = await _insert_rule_pack(w6b_pool)
    decision_id = await _insert_decision(w6b_conn, rule_pack_id=rule_pack_id)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await w6b_conn.execute(
            """
            INSERT INTO visa_decision_payloads (
                decision_id, encryption_algorithm, encryption_key_id, nonce,
                ciphertext, aad, ciphertext_sha256, purge_after
            ) VALUES ($1, 'AES-256-CBC', 'test-kek-1', $2, $3, $4, $5, $6)
            """,
            decision_id,
            os.urandom(12),
            b"opaque-ciphertext-bytes-only",
            b"decision-id-binding-context",
            hashlib.sha256(b"opaque-ciphertext-bytes-only").digest(),
            GOLD_EVALUATED_AT + timedelta(days=90),
        )


async def test_source_record_recorded_period_infinity_guard_guilt(
    w6b_conn: asyncpg.Connection,
) -> None:
    bad_range = asyncpg.Range(None, None, lower_inc=True, upper_inc=False)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, recorded_period=bad_range)


async def test_source_record_title_too_long_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, title="x" * 513)


async def test_source_record_title_empty_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, title="")


async def test_source_record_publisher_too_long_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, publisher="x" * 257)


async def test_source_record_canonical_url_too_long_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, canonical_url="https://example.com/" + "x" * 2048)


async def test_source_record_locators_too_many_guilt(w6b_conn: asyncpg.Connection) -> None:
    too_many = json.dumps([{"page": i} for i in range(65)])
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, locators=too_many)


async def test_source_record_locators_at_limit_innocence(w6b_conn: asyncpg.Connection) -> None:
    at_limit = json.dumps([{"page": i} for i in range(64)])
    source_id = await _insert_source_record(w6b_conn, locators=at_limit)
    assert source_id is not None


async def test_source_record_version_upper_bound_guilt(w6b_conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_source_record(w6b_conn, version=9_007_199_254_740_992)


# ---------------------------------------------------------------------------
# 16. Rollback drops cleanly, FK-safe, and leaves migration 250 untouched.
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
        for fn_name in (
            "reject_visa_decision_pack_binding",
            "reject_visa_decision_payloads_mutation",
            "reject_visa_source_records_mutation",
            "reject_visa_source_record_supersedes_mismatch",
        ):
            dropped = await conn.fetchval("SELECT 1 FROM pg_proc WHERE proname = $1", fn_name)
            assert dropped is None, f"{fn_name} should have been dropped by rollback"

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

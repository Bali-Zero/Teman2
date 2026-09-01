"""Real-database integration tests for ``PostgresDocumentStore`` (migration 304).

Mirrors ``backend/tests/scripts/visa_engine/test_security_definer_owner_invariant.py``'s
throwaway-database-plus-uuid-suffixed-roles pattern rather than pointing at the shared
``nuzantara_test``/``INTAKE_TEST_DSN`` database the way
``garuda_portal/test_magic_link_store_integration.py`` does. Reason, measured before
writing this file rather than assumed: the shared local ``nuzantara_test`` database on
this machine is migrated only through 288 (`_schema_versions` max, checked live) and has
no ``visa_ledger_owner`` role at all -- it predates migrations 289-304 and cannot exercise
requirement 4 (the SECURITY DEFINER ownership transfer) honestly. `migrations_v2/*.sql`
also assumes a much older, pre-``migrations_v2`` legacy `.py`-based schema baseline
(`migration_base.py`'s ``LEGACY_NO_ROLLBACK_WHITELIST``, migration_number <= 111) that this
suite has no way to reconstruct from scratch. So this file does what
``test_security_definer_owner_invariant.py`` already does for the same shape: build ONLY
the minimal prerequisite migration 304 actually needs (a `visa_decision_retention_policies`
table matching production's CURRENT `264`+`285`-widened shape, verified live against that
same `nuzantara_test` database's `pg_get_constraintdef` before this file was written) in a
bare throwaway database, apply 304's forward SQL directly with `visa_ledger_owner`
substituted for a uuid-suffixed role (a privilege boundary is cluster-wide; a test may not
create a role literally named `visa_ledger_owner`), and run every test against that.

Run manually (creates+drops its own throwaway database and two roles via an admin
connection derived from ``GARUDA_DOCUMENTS_TEST_DSN``/``INTAKE_TEST_DSN``, swapped to the
``postgres`` maintenance database; never touches ``nuzantara_dev``/``nuzantara_test``):

    PYTHONPATH=. pytest backend/tests/services/garuda_documents/test_postgres_store.py -v
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest

asyncpg = pytest.importorskip("asyncpg")

from backend.db.migration_base import split_migration_sql
from backend.services.garuda_documents.models import (
    LowConfidenceOutcome,
    PassportReviewFieldName,
    ProcessingOutcome,
    ReadyOutcome,
    ReviewField,
    UncertainReviewField,
    UnreadableOutcome,
)
from backend.services.garuda_documents.ports import IdempotencyConflictError
from backend.services.garuda_documents.postgres_store import (
    PostgresDocumentStore,
    ReadyOutcomeValueNotPersisted,
)
from backend.services.garuda_flow.public_api import PersistencePolicyUnavailable
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get("GARUDA_DOCUMENTS_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
).rsplit("/", 1)[0] + "/postgres"

_MIGRATION_304 = (
    Path(__file__).resolve().parents[3] / "db" / "migrations_v2" / "304_garuda_documents.sql"
)

# Verbatim shape of `public.visa_decision_retention_policies` as migrations 264+285 leave
# it on the real chain -- verified live against the shared `nuzantara_test` database
# (`pg_get_constraintdef`) before writing this file, not assumed. Only the ONE table
# migration 304 depends on; `guard_visa_decision_retention_policy_mutation` (264) is
# deliberately NOT recreated here because it only fires on UPDATE/DELETE, which this
# suite never performs against this table (append-only, matching production use).
_RETENTION_POLICIES_DDL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE public.visa_decision_retention_policies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment         TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    policy_scope        TEXT NOT NULL
        CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK')),
    policy_version      TEXT NOT NULL
        CHECK (policy_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
    retention_interval  INTERVAL NOT NULL
        CHECK (retention_interval > INTERVAL '0 seconds'),
    idempotency_retention_interval INTERVAL NOT NULL,
    legal_hold_review_interval INTERVAL NOT NULL
        CHECK (legal_hold_review_interval > INTERVAL '0 seconds'),
    retention_anchor    TEXT NOT NULL
        CHECK (retention_anchor IN ('EVALUATED_AT', 'CREATED_AT')),
    effective_period    TSTZRANGE NOT NULL,
    approved_by         TEXT NOT NULL
        CHECK (approved_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'),
    approval_reference  TEXT NOT NULL
        CHECK (length(approval_reference) BETWEEN 1 AND 2048),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (NOT isempty(effective_period)),
    CHECK (lower(effective_period) IS NOT NULL),
    CHECK (lower_inc(effective_period)),
    CHECK (upper(effective_period) IS NULL OR NOT upper_inc(effective_period)),
    CHECK (
        idempotency_retention_interval > INTERVAL '0 seconds'
        AND idempotency_retention_interval <= retention_interval
    ),
    UNIQUE (environment, policy_version)
);
"""

_ENV = "TEST"


def _doc_id(label: str) -> str:
    """A valid `document_id` (migration 304's CHECK requires 32 lowercase hex chars,
    matching `service.py`'s real `uuid4().hex`) derived deterministically from a
    human-readable test label, so failure output stays legible without hand-picking
    hex noise per test."""
    return hashlib.sha256(label.encode()).hexdigest()[:32]


def _db_url_for(db_name: str) -> str:
    return _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"


def _migration_304_forward(ledger_role: str) -> str:
    forward_sql, _rollback_sql = split_migration_sql(_MIGRATION_304.read_text(encoding="utf-8"))
    # The migration names `visa_ledger_owner` literally, as it must in production. A
    # cluster role cannot be scoped to one database, so this test substitutes a
    # uuid-suffixed name (same discipline as
    # `test_security_definer_owner_invariant.py::_migration_300_forward`).
    return forward_sql.replace("visa_ledger_owner", ledger_role)


@dataclass(frozen=True, slots=True)
class _Sandbox:
    dsn: str
    ledger: str
    app: str


@pytest.fixture
async def sandbox() -> AsyncIterator[_Sandbox]:
    suffix = uuid.uuid4().hex[:12]
    db_name = f"nuzantara_test_gdoc_{suffix}"
    ledger = f"gdoc_ledger_{suffix}"
    app = f"gdoc_app_{suffix}"

    admin = await asyncpg.connect(_ADMIN_URL)
    try:
        is_superuser = await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        if not is_superuser:
            pytest.skip(
                f"connecting role for {_ADMIN_URL!r} is not a superuser -- this suite "
                "creates cluster roles and cannot proceed"
            )
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        await admin.execute(f'CREATE ROLE "{ledger}" NOLOGIN')
        await admin.execute(f'CREATE ROLE "{app}" NOLOGIN')
    except (OSError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable/superuser Postgres for GARUDA_DOCUMENTS_TEST_DSN "
                f"(or INTAKE_TEST_DSN override) -- {_ADMIN_URL!r}: {exc}. This file gates "
                f"a persistence layer that touches the shared retention authority; it "
                f"must never silently pass by skipping."
            )
        pytest.skip(f"no local superuser Postgres reachable at {_ADMIN_URL}: {exc}")
    finally:
        await admin.close()

    try:
        # Build ONLY what migration 304 needs (module docstring explains why not the
        # real chain), owned by the ledger role -- mirrors production, where
        # `visa_decision_retention_policies` is owned by `visa_ledger_owner` and the
        # app role holds only SELECT (301's header, verbatim).
        conn = await asyncpg.connect(_db_url_for(db_name))
        try:
            await conn.execute(_RETENTION_POLICIES_DDL)
            await conn.execute(f'ALTER TABLE public.visa_decision_retention_policies OWNER TO "{ledger}"')
            await conn.execute(f'GRANT SELECT ON TABLE public.visa_decision_retention_policies TO "{app}"')
            await conn.execute(_migration_304_forward(ledger))
            await conn.execute(f'GRANT SELECT, INSERT ON TABLE public.garuda_documents TO "{app}"')
            await conn.execute(f'GRANT SELECT, INSERT ON TABLE public.garuda_document_review_fields TO "{app}"')
            await conn.execute(
                """
                INSERT INTO public.visa_decision_retention_policies (
                    environment, policy_scope, policy_version, retention_interval,
                    idempotency_retention_interval, legal_hold_review_interval,
                    retention_anchor, effective_period, approved_by, approval_reference
                ) VALUES (
                    'TEST', 'GARUDA_DOCUMENT', $1, INTERVAL '30 days',
                    INTERVAL '1 hour', INTERVAL '30 days',
                    'CREATED_AT', tstzrange(clock_timestamp(), NULL, '[)'),
                    'zero-test-approver', 'ZERO-GARUDA-DOCUMENT-RETENTION-TEST-APPROVAL'
                )
                """,
                f"gdoc-test-policy-{suffix}",
            )
        finally:
            await conn.close()

        yield _Sandbox(dsn=_db_url_for(db_name), ledger=ledger, app=app)
    finally:
        admin = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            for role in (app, ledger):
                await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        finally:
            await admin.close()


@pytest.fixture
async def pool(sandbox: _Sandbox) -> AsyncIterator[asyncpg.Pool]:
    p = await create_prod_shaped_pool(dsn=sandbox.dsn, min_size=1, max_size=4)
    yield p
    await p.close()


@pytest.fixture
def store(pool: asyncpg.Pool) -> PostgresDocumentStore:
    return PostgresDocumentStore(pool, environment=_ENV)


def _low_confidence(document_id: str) -> LowConfidenceOutcome:
    return LowConfidenceOutcome(
        document_id=document_id,
        uncertain_fields=(
            UncertainReviewField(field_path=PassportReviewFieldName.FULL_NAME),
            UncertainReviewField(field_path=PassportReviewFieldName.PASSPORT_NUMBER),
        ),
    )


def _ready(document_id: str) -> ReadyOutcome:
    return ReadyOutcome(
        document_id=document_id,
        review_fields=(
            ReviewField(
                field_path=PassportReviewFieldName.FULL_NAME,
                value="JANE TEST TRAVELER",
                confirmation_required=True,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Behaviour 1 — exact key + exact payload replays the original outcome,
# no second row (innocence), including the READY_FOR_REVIEW value gap
# (requirement 8's design tension, made loud rather than silently wrong).
# ---------------------------------------------------------------------------


async def test_exact_replay_returns_the_original_low_confidence_outcome(store: PostgresDocumentStore):
    outcome = _low_confidence(_doc_id("doc-replay-0000000000000001"))
    won = await store.commit("key-replay-1", "aa" * 32, outcome)
    assert won is True

    replayed = await store.get_existing("key-replay-1", "aa" * 32)
    assert replayed == outcome


async def test_exact_replay_does_not_create_a_second_row(store: PostgresDocumentStore, pool: asyncpg.Pool):
    outcome = _low_confidence(_doc_id("doc-replay-0000000000000002"))
    await store.commit("key-replay-2", "bb" * 32, outcome)
    # A second commit call under the identical key+payload — the shape
    # `service.py` takes when `get_existing` is skipped or races.
    won_again = await store.commit("key-replay-2", "bb" * 32, outcome)
    assert won_again is False

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM public.garuda_documents WHERE key_sha256 = $1",
            hashlib.sha256(b"key-replay-2").digest(),
        )
    assert count == 1, "a replayed commit must never create a second row"


async def test_ready_outcome_replay_raises_documented_value_gap_instead_of_fabricating_data(
    store: PostgresDocumentStore,
):
    """The one outcome kind this store cannot faithfully replay (module docstring /
    requirement 8): `ReviewField.value` is never persisted, so a replay must raise
    loudly rather than return a placeholder that looks like real passport data.
    """
    outcome = _ready(_doc_id("doc-ready-0000000000000001"))
    won = await store.commit("key-ready-1", "cc" * 32, outcome)
    assert won is True

    with pytest.raises(ReadyOutcomeValueNotPersisted):
        await store.get_existing("key-ready-1", "cc" * 32)


async def test_processing_and_unreadable_outcomes_replay_faithfully(store: PostgresDocumentStore):
    """Innocence companions to the READY gap above — these two outcome kinds carry no
    review fields at all, so nothing is lost persisting or rehydrating them."""
    processing = ProcessingOutcome(document_id=_doc_id("doc-processing-000000000001"))
    await store.commit("key-processing-1", "dd" * 32, processing)
    assert await store.get_existing("key-processing-1", "dd" * 32) == processing

    unreadable = UnreadableOutcome(document_id=_doc_id("doc-unreadable-000000000001"))
    await store.commit("key-unreadable-1", "ee" * 32, unreadable)
    assert await store.get_existing("key-unreadable-1", "ee" * 32) == unreadable


# ---------------------------------------------------------------------------
# Behaviour 2 — same key + DIFFERENT payload raises IdempotencyConflictError
# (guilt), same key + SAME payload never does (innocence, covered above).
# ---------------------------------------------------------------------------


async def test_commit_with_a_different_payload_under_the_same_key_raises_conflict(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    first = _low_confidence(_doc_id("doc-conflict-0000000000000001"))
    await store.commit("key-conflict-1", "11" * 32, first)

    second = _low_confidence(_doc_id("doc-conflict-0000000000000002"))
    with pytest.raises(IdempotencyConflictError):
        await store.commit("key-conflict-1", "22" * 32, second)

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM public.garuda_documents")
    assert count == 1, "a rejected conflicting commit must not leave a second row behind"


async def test_get_existing_with_a_different_payload_under_the_same_key_raises_conflict(
    store: PostgresDocumentStore,
):
    outcome = _low_confidence(_doc_id("doc-conflict-0000000000000003"))
    await store.commit("key-conflict-2", "33" * 32, outcome)

    with pytest.raises(IdempotencyConflictError):
        await store.get_existing("key-conflict-2", "44" * 32)


# ---------------------------------------------------------------------------
# Behaviour 3 — commit() returns True for the winner and False for a
# concurrent loser (real interleaving, not sequential calls).
# ---------------------------------------------------------------------------


async def test_two_concurrent_commits_same_key_exactly_one_wins(
    pool: asyncpg.Pool, sandbox: _Sandbox
):
    """A SEPARATE store instance per coroutine (own pool connection each), racing a
    genuinely NEW key — `SELECT ... FOR UPDATE` locks nothing for a not-yet-existing
    row, so the PRIMARY KEY on `key_sha256` is the real atomicity boundary this test
    exercises (see `commit()`'s own comment on this).
    """
    store_a = PostgresDocumentStore(pool, environment=_ENV)
    store_b = PostgresDocumentStore(pool, environment=_ENV)
    outcome_a = _low_confidence(_doc_id("doc-race-a-00000000000001"))
    outcome_b = _low_confidence(_doc_id("doc-race-b-00000000000001"))

    results = await asyncio.gather(
        store_a.commit("key-race-1", "55" * 32, outcome_a),
        store_b.commit("key-race-1", "55" * 32, outcome_b),
    )

    assert sorted(results) == [False, True], f"expected exactly one winner: {results!r}"

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM public.garuda_documents")
    assert count == 1, "a genuine race for a brand-new key must still leave exactly one row"


async def test_second_sequential_commit_of_an_already_committed_key_returns_false(
    store: PostgresDocumentStore,
):
    outcome = _low_confidence(_doc_id("doc-sequential-0000000000001"))
    first = await store.commit("key-sequential-1", "66" * 32, outcome)
    second = await store.commit("key-sequential-1", "66" * 32, outcome)
    assert first is True
    assert second is False


# ---------------------------------------------------------------------------
# Behaviour 4 — PersistencePolicyUnavailable when no active policy covers
# the clock (guilt: STAGING has no policy row in this fixture); the
# innocence companion is every other test in this file succeeding under
# TEST, which DOES have one.
# ---------------------------------------------------------------------------


async def test_commit_fails_closed_with_no_active_policy_for_the_environment(pool: asyncpg.Pool):
    staging_store = PostgresDocumentStore(pool, environment="STAGING")
    outcome = _low_confidence(_doc_id("doc-nopolicy-00000000000001"))

    with pytest.raises(PersistencePolicyUnavailable):
        await staging_store.commit("key-nopolicy-1", "77" * 32, outcome)

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM public.garuda_documents WHERE environment = 'STAGING'"
        )
    assert count == 0, "a fail-closed commit must not write a row"


# ---------------------------------------------------------------------------
# Bonus — proves requirement 4 (the SECURITY DEFINER ownership transfer)
# actually fixes the exact production outage class migration 301 documents,
# under a low-privilege application role shaped like `backend_rag_v2`
# (SELECT-only on `visa_decision_retention_policies`, matching 301's header
# verbatim). GUILT/INNOCENCE pair, both against the SAME real migration file
# and the SAME live-fixture-created function (never a hand-written stand-in):
#
#   INNOCENCE (below): after migration 304 applies for real, the trigger
#   function is owned by the ledger role (the DO block ran), and the
#   low-priv INSERT succeeds.
#
#   GUILT (next test): this suite then does the ONE thing migration 285
#   originally did wrong -- `ALTER FUNCTION ... OWNER TO <app role>`,
#   putting the function back in the exact mis-owned state 301's header
#   describes -- and the SAME low-priv INSERT now fails with
#   `asyncpg.exceptions.InsufficientPrivilegeError: permission denied for
#   table visa_decision_retention_policies`, reproducing the 2026-08-30
#   incident shape verbatim. This isolates the causal claim ("SECURITY
#   DEFINER owned by the app role buys nothing") from the unrelated
#   question of which role's connection is allowed to run the migration's
#   own DDL (`ALTER TABLE ... DROP/ADD CONSTRAINT` on
#   `visa_decision_retention_policies` requires table ownership either way,
#   a pre-existing wrinkle across the whole GARUDA_* migration family, not
#   something migration 304 introduces or this pair is about).
# ---------------------------------------------------------------------------

_LOW_PRIV_INSERT_SQL = """
    INSERT INTO public.garuda_documents
        (key_sha256, canonical_payload_sha256, document_id, environment, processing_state)
    VALUES (digest($1, 'sha256'), digest($2, 'sha256'), $3, 'TEST', 'PROCESSING')
"""


async def test_low_privilege_role_can_insert_thanks_to_the_ownership_transfer(sandbox: _Sandbox):
    conn = await asyncpg.connect(sandbox.dsn)
    try:
        async with conn.transaction():
            await conn.execute(f'SET LOCAL ROLE "{sandbox.app}"')
            await conn.execute(
                _LOW_PRIV_INSERT_SQL,
                "key-lowpriv-1",
                "payload-lowpriv-1",
                _doc_id("doc-lowpriv-00000000000001"),
            )
        row = await conn.fetchrow(
            "SELECT document_id FROM public.garuda_documents WHERE document_id = $1",
            _doc_id("doc-lowpriv-00000000000001"),
        )
    finally:
        await conn.close()
    assert row is not None


async def test_low_privilege_role_insert_fails_once_the_function_is_mis_owned_again(sandbox: _Sandbox):
    """GUILT half of the pair above — see its docstring for the full argument."""
    conn = await asyncpg.connect(sandbox.dsn)
    try:
        # Reproduce migration 285's original defect by hand: the function is
        # SECURITY DEFINER (migration 304 made it so) but now owned by the
        # low-privilege application role instead of the ledger role.
        await conn.execute(
            f'ALTER FUNCTION public.bind_garuda_document_retention_policy() OWNER TO "{sandbox.app}"'
        )
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError) as raised:
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{sandbox.app}"')
                await conn.execute(
                    _LOW_PRIV_INSERT_SQL,
                    "key-lowpriv-guilt-1",
                    "payload-lowpriv-guilt-1",
                    _doc_id("doc-lowpriv-guilt-00000000001"),
                )
        assert "visa_decision_retention_policies" in str(raised.value)
    finally:
        await conn.close()

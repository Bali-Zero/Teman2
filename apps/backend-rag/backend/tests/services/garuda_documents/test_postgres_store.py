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
from urllib.parse import urlsplit, urlunsplit

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
    _OPERATION_UPLOAD_INTAKE_DOCUMENT,
    PostgresDocumentStore,
    ReadyOutcomeValueNotPersisted,
    _scoped_key_sha256,
)
from backend.services.garuda_flow.public_api import PersistencePolicyUnavailable
from backend.tests.fixtures.prod_shaped_pool import create_prod_shaped_pool

pytestmark = pytest.mark.asyncio

_CONFIGURED_DSN = (
    os.environ.get("GARUDA_DOCUMENTS_TEST_DSN")
    or os.environ.get("INTAKE_TEST_DSN")
    or "postgresql://localhost:5432/nuzantara_test"
)


def _with_database(dsn: str, database: str) -> str:
    """Replace ONLY the database component of a DSN.

    Not `rsplit("/", 1)`. That splits on the last slash ANYWHERE in the string, and a
    perfectly legal DSN can carry one after the database name -- e.g.
    `postgresql://host/nuzantara_test?application_name=garuda/ci`, where the last slash is
    inside the query. `rsplit` then rewrites `application_name` and leaves the database
    untouched, so a suite that believes it is building a disposable database would run its
    DDL against the SHARED one and drop something else in teardown. Parsing the URL makes
    the substitution structural instead of textual.
    """
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _redacted(dsn: str) -> str:
    """A DSN safe to put in a skip/fail message, a pytest report or a CI log.

    `_ADMIN_URL` can carry a password (CI's does: `postgresql://test:test@...`), and an
    f-string -- `!r` included -- prints it verbatim. Skip and fail reasons end up in JUnit
    XML and in job logs, so interpolating the raw DSN publishes the credential to anyone
    who can read a build. Only scheme, user, host and database survive here; the password
    is replaced by a fixed marker, never by a length-revealing mask.
    """
    parts = urlsplit(dsn)
    user = f"{parts.username}:***@" if parts.password else (f"{parts.username}@" if parts.username else "")
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{user}{host}{port}{parts.path}"


_ADMIN_URL = _with_database(_CONFIGURED_DSN, "postgres")

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

# Real actors are `result_id`s: 32 hex characters, and two of a customer's sessions can
# share a long prefix. Short literals like "actor-1"/"actor-2" let a length-truncating
# mutation -- `actor_id[:8]` in the hash -- keep every key in this suite byte-identical
# and stay GREEN while cross-actor isolation is gone.
#
# A pair sharing SOME prefix only pins the cuts shorter than it: the first version of
# these constants shared 16 characters, caught `actor_id[:8]`, and survived
# `actor_id[:17]` (Sol, round O2, finding 2 -- the mutation moved, the suite stayed
# green). A longer hand-picked prefix would have the same shape one cut further out. So
# the prefix here is MAXIMAL rather than long: the two ids differ only in their final
# character, which makes "every truncation collides them" a property of the pair instead
# of a claim about one chosen n, and
# `test_every_truncation_of_the_actor_id_collides_the_two_fixture_actors` asserts it for
# all 31 cuts.
_ACTOR_COMMON_PREFIX = "0123456789abcdef" + "0" * 15  # 31 of the 32 characters
_ACTOR_1 = _ACTOR_COMMON_PREFIX + "1"
_ACTOR_2 = _ACTOR_COMMON_PREFIX + "2"


def _doc_id(label: str) -> str:
    """A valid `document_id` (migration 304's CHECK requires 32 lowercase hex chars,
    matching `service.py`'s real `uuid4().hex`) derived deterministically from a
    human-readable test label, so failure output stays legible without hand-picking
    hex noise per test."""
    return hashlib.sha256(label.encode()).hexdigest()[:32]


def _db_url_for(db_name: str) -> str:
    return _with_database(_ADMIN_URL, db_name)


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

    # The connect itself is INSIDE the try, and `asyncpg.InterfaceError` is in the tuple.
    # Outside it, a DSN that asyncpg's own parser rejects -- a bad `sslmode`, say -- raises
    # `ClientConfigurationError` (an `InterfaceError`, which is neither `OSError` nor
    # `PostgresError`) before any socket is opened, so it escaped both the redaction below
    # and the CI-must-not-skip branch, and a `--tb=long` traceback renders the connect's
    # arguments -- the DSN, password included (Sol, round O2, finding 5).
    admin: asyncpg.Connection | None = None
    try:
        admin = await asyncpg.connect(_ADMIN_URL)
        is_superuser = await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        if not is_superuser:
            # In CI this is a FAILURE, not a skip. `pytest.skip` raises `Skipped`, which is
            # neither `OSError` nor `PostgresError`, so it flies straight past the CI branch
            # in the `except` below: the reachable-but-unprivileged case would leave 12
            # database tests skipped, 2 pure tests passing, and pytest exiting 0 -- a green
            # check for a persistence layer nothing exercised. That is exactly the outcome
            # the `except` branch's own message says must never happen, so the same rule is
            # enforced here where the case actually arises.
            unprivileged = (
                f"the connecting role for {_redacted(_ADMIN_URL)} is not a superuser -- this "
                "suite creates cluster roles and cannot proceed"
            )
            if os.environ.get("CI"):
                pytest.fail(
                    f"{unprivileged}. In CI this must not be skipped: this file is the only "
                    "thing exercising the store against a real database."
                )
            pytest.skip(unprivileged)
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        await admin.execute(f'CREATE ROLE "{ledger}" NOLOGIN')
        await admin.execute(f'CREATE ROLE "{app}" NOLOGIN')
    except (OSError, asyncpg.InterfaceError, asyncpg.PostgresError) as exc:
        if os.environ.get("CI"):
            pytest.fail(
                f"CI has no reachable Postgres for GARUDA_DOCUMENTS_TEST_DSN "
                f"(or INTAKE_TEST_DSN override) -- {_redacted(_ADMIN_URL)}: {exc}. This file "
                f"gates a persistence layer that touches the shared retention authority; it "
                f"must never silently pass by skipping."
            )
        pytest.skip(f"no local superuser Postgres reachable at {_redacted(_ADMIN_URL)}: {exc}")
    finally:
        if admin is not None:
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
    won = await store.commit("key-replay-1", "aa" * 32, outcome, actor_id=_ACTOR_1)
    assert won is True

    replayed = await store.get_existing("key-replay-1", "aa" * 32, actor_id=_ACTOR_1)
    assert replayed == outcome


async def test_exact_replay_does_not_create_a_second_row(store: PostgresDocumentStore, pool: asyncpg.Pool):
    outcome = _low_confidence(_doc_id("doc-replay-0000000000000002"))
    await store.commit("key-replay-2", "bb" * 32, outcome, actor_id=_ACTOR_1)
    # A second commit call under the identical key+payload — the shape
    # `service.py` takes when `get_existing` is skipped or races.
    won_again = await store.commit("key-replay-2", "bb" * 32, outcome, actor_id=_ACTOR_1)
    assert won_again is False

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM public.garuda_documents WHERE key_sha256 = $1",
            _scoped_key_sha256(
                actor_id=_ACTOR_1,
                operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
                environment=_ENV,
                idempotency_key="key-replay-2",
            ),
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
    won = await store.commit("key-ready-1", "cc" * 32, outcome, actor_id=_ACTOR_1)
    assert won is True

    with pytest.raises(ReadyOutcomeValueNotPersisted) as raised:
        await store.get_existing("key-ready-1", "cc" * 32, actor_id=_ACTOR_1)

    # The TYPE alone proves almost nothing: an implementation raising
    # `ReadyOutcomeValueNotPersisted("0" * 32, ())` -- wrong document, no fields --
    # satisfies `pytest.raises` and is useless to the caller this payload exists for.
    # The exception is the only channel through which the persisted STRUCTURE reaches a
    # caller that cannot be given the values, so the structure is what gets asserted.
    assert raised.value.document_id == outcome.document_id
    assert raised.value.persisted_fields == tuple(
        (field.field_path, field.confirmation_required) for field in outcome.review_fields
    )
    for field_path, confirmation_required in raised.value.persisted_fields:
        assert isinstance(field_path, PassportReviewFieldName), "field_path stays the enum member"
        assert isinstance(confirmation_required, bool)


async def test_processing_and_unreadable_outcomes_replay_faithfully(store: PostgresDocumentStore):
    """Innocence companions to the READY gap above — these two outcome kinds carry no
    review fields at all, so nothing is lost persisting or rehydrating them."""
    processing = ProcessingOutcome(document_id=_doc_id("doc-processing-000000000001"))
    await store.commit("key-processing-1", "dd" * 32, processing, actor_id=_ACTOR_1)
    assert await store.get_existing("key-processing-1", "dd" * 32, actor_id=_ACTOR_1) == processing

    unreadable = UnreadableOutcome(document_id=_doc_id("doc-unreadable-000000000001"))
    await store.commit("key-unreadable-1", "ee" * 32, unreadable, actor_id=_ACTOR_1)
    assert await store.get_existing("key-unreadable-1", "ee" * 32, actor_id=_ACTOR_1) == unreadable


# ---------------------------------------------------------------------------
# Behaviour 2 — same key + DIFFERENT payload raises IdempotencyConflictError
# (guilt), same key + SAME payload never does (innocence, covered above).
# ---------------------------------------------------------------------------


async def test_commit_with_a_different_payload_under_the_same_key_raises_conflict(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    first = _low_confidence(_doc_id("doc-conflict-0000000000000001"))
    await store.commit("key-conflict-1", "11" * 32, first, actor_id=_ACTOR_1)

    second = _low_confidence(_doc_id("doc-conflict-0000000000000002"))
    with pytest.raises(IdempotencyConflictError):
        await store.commit("key-conflict-1", "22" * 32, second, actor_id=_ACTOR_1)

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM public.garuda_documents")
    assert count == 1, "a rejected conflicting commit must not leave a second row behind"


async def test_get_existing_with_a_different_payload_under_the_same_key_raises_conflict(
    store: PostgresDocumentStore,
):
    outcome = _low_confidence(_doc_id("doc-conflict-0000000000000003"))
    await store.commit("key-conflict-2", "33" * 32, outcome, actor_id=_ACTOR_1)

    with pytest.raises(IdempotencyConflictError):
        await store.get_existing("key-conflict-2", "44" * 32, actor_id=_ACTOR_1)


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

    # `asyncio.gather` alone does NOT even get both racers to a shared starting point: if
    # acquiring the second pool connection delays B past A's INSERT, B never observed the
    # key absent at all. The barrier fixes that much -- both coroutines must have seen the
    # key ABSENT before either inserts -- and no more.
    #
    # DECLARED LIMIT (Sol, round O2, finding 1) -- and it is the reason this file does not
    # claim to pin the PK branch. The barrier synchronises the EXTERNAL probes, not the
    # lookups the two `commit()` calls make INTERNALLY. Both racers can see the key absent,
    # pass the barrier, and then A can still run its whole transaction -- internal `SELECT
    # ... FOR UPDATE`, INSERT, commit -- before B reaches its own `SELECT ... FOR UPDATE`.
    # B then finds the row and takes the ordinary replay branch, every assertion below
    # still passes, and so does a mutant with the `UniqueViolationError` handler deleted:
    # Sol reproduced exactly that schedule against this candidate and got two PASSes with
    # zero primary-key violations. What this test therefore proves is the OUTCOME (exactly
    # one winner, exactly one row) under a schedule where both racers start from an empty
    # key -- not that the loser travelled through the PK-violation branch. Forcing that
    # branch needs the store to expose a test-only seam between its lookup and its INSERT,
    # or two connections holding an explicit lock; it is specified, with the assertion it
    # must carry, in SPEC-PR2b-interleaving.md.
    both_looked = asyncio.Barrier(2)
    original_scoped_key = _scoped_key_sha256

    async def commit_after_both_saw_nothing(store, outcome):
        async with pool.acquire() as probe:
            found = await probe.fetchval(
                "SELECT count(*) FROM public.garuda_documents WHERE key_sha256 = $1",
                original_scoped_key(
                    actor_id=_ACTOR_1,
                    operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
                    environment=_ENV,
                    idempotency_key="key-race-1",
                ),
            )
        assert found == 0, "the barrier must open with the key still absent for both racers"
        await both_looked.wait()
        return await store.commit("key-race-1", "55" * 32, outcome, actor_id=_ACTOR_1)

    results = await asyncio.gather(
        commit_after_both_saw_nothing(store_a, outcome_a),
        commit_after_both_saw_nothing(store_b, outcome_b),
    )

    assert sorted(results) == [False, True], f"expected exactly one winner: {results!r}"

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM public.garuda_documents")
    assert count == 1, "a genuine race for a brand-new key must still leave exactly one row"


async def test_second_sequential_commit_of_an_already_committed_key_returns_false(
    store: PostgresDocumentStore,
):
    outcome = _low_confidence(_doc_id("doc-sequential-0000000000001"))
    first = await store.commit("key-sequential-1", "66" * 32, outcome, actor_id=_ACTOR_1)
    second = await store.commit("key-sequential-1", "66" * 32, outcome, actor_id=_ACTOR_1)
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
        await staging_store.commit("key-nopolicy-1", "77" * 32, outcome, actor_id=_ACTOR_1)

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM public.garuda_documents WHERE environment = 'STAGING'"
        )
    assert count == 0, "a fail-closed commit must not write a row"


# ---------------------------------------------------------------------------
# Behaviour 5 — the idempotency key is scoped to actor (contract's
# `IdempotencyKey` parameter: "Scoped to actor and operation"). GUILT would be
# a bare `sha256(idempotency_key)`: two different actors reusing the same
# literal key would collide on the same `key_sha256` PRIMARY KEY row, so one
# actor's `commit` could clobber or be read back by another. INNOCENCE is
# every other test in this file, which all use one actor and never exercise
# this dimension at all.
# ---------------------------------------------------------------------------


async def test_same_idempotency_key_different_actor_does_not_collide(
    store: PostgresDocumentStore, pool: asyncpg.Pool
):
    outcome_first = _low_confidence(_doc_id("doc-actor-alice-0000000001"))
    outcome_second = _low_confidence(_doc_id("doc-actor-bob-00000000001"))

    won_first = await store.commit("shared-literal-key", "aa" * 32, outcome_first, actor_id=_ACTOR_1)
    won_second = await store.commit("shared-literal-key", "aa" * 32, outcome_second, actor_id=_ACTOR_2)

    # Both actors' commits win -- a real collision would have made bob's
    # commit a replay (won=False) or, worse, an IdempotencyConflictError
    # (same key bound to what bob's INSERT would see as "another" payload
    # under alice's row).
    assert won_first is True
    assert won_second is True

    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM public.garuda_documents")
    assert count == 2, "two different actors reusing the same literal key must get two rows, not one"


async def test_same_idempotency_key_different_actor_cannot_read_the_other_actors_document(
    store: PostgresDocumentStore,
):
    outcome_first = _low_confidence(_doc_id("doc-actor-alice-0000000002"))
    await store.commit("another-shared-key", "bb" * 32, outcome_first, actor_id=_ACTOR_1)

    # bob has never submitted anything under this key -- get_existing for bob
    # must see a first-time submission (None), never alice's row.
    second_actor_view = await store.get_existing("another-shared-key", "bb" * 32, actor_id=_ACTOR_2)
    assert second_actor_view is None

    # alice's own replay still works, unaffected by bob's absent binding.
    first_actor_view = await store.get_existing("another-shared-key", "bb" * 32, actor_id=_ACTOR_1)
    assert first_actor_view == outcome_first


async def test_same_actor_same_key_same_environment_replay_still_hits_the_same_row(
    store: PostgresDocumentStore,
):
    """Innocence companion to the two guilt tests above: fixing the collision must not
    also break the ordinary single-actor replay every other test in this file relies on.
    """
    outcome = _low_confidence(_doc_id("doc-actor-replay-000000001"))
    won = await store.commit("actor-replay-key", "cc" * 32, outcome, actor_id=_ACTOR_1)
    assert won is True

    replayed = await store.get_existing("actor-replay-key", "cc" * 32, actor_id=_ACTOR_1)
    assert replayed == outcome


def test_scoped_key_hash_is_not_ambiguous_across_component_boundaries():
    """The whole point of scoping is defeated if the encoding let two DIFFERENT tuples
    collide. `("actorab", "c")` and `("actora", "bc")` must never hash the same.

    That pair alone is NOT enough, and this docstring used to claim it "proves the
    length-prefixing" when it does not: measured here, replacing the length-prefixed
    encoding with `"|".join(...)` leaves this test GREEN, because `"actorab|c"` and
    `"actora|bc"` are genuinely different strings. A separator-joined encoding is
    ambiguous only when a COMPONENT CONTAINS THE SEPARATOR -- `("a|b", "c")` and
    `("a", "b|c")` both render as `"a|b|c"`. The parametrized block below exhibits
    exactly that collision for every separator a shortcut implementation would plausibly
    reach for, which is what actually pins the length-prefixing.
    """
    same_key = "idem-key-1"
    same_env = "TEST"
    same_op = _OPERATION_UPLOAD_INTAKE_DOCUMENT

    hash_1 = _scoped_key_sha256(actor_id="actorab", operation="c", environment=same_env, idempotency_key=same_key)
    hash_2 = _scoped_key_sha256(actor_id="actora", operation="bc", environment=same_env, idempotency_key=same_key)
    assert hash_1 != hash_2, "different component boundaries must never hash identically"

    # Same shift, one boundary over, across the operation/environment pair.
    hash_3 = _scoped_key_sha256(actor_id=_ACTOR_1, operation="opTEST", environment="", idempotency_key=same_key)
    hash_4 = _scoped_key_sha256(actor_id=_ACTOR_1, operation="op", environment="TEST", idempotency_key=same_key)
    assert hash_3 != hash_4, "different component boundaries must never hash identically"

    # THE CASE THAT ACTUALLY KILLS A SEPARATOR-JOINED ENCODING: a component that
    # CONTAINS the separator. Under any `sep.join(...)` both of these render to the
    # identical string; under length-prefixing they cannot.
    for separator in ("|", "\x00", ":", "-", "/", ",", "\n"):
        split_left = _scoped_key_sha256(
            actor_id=f"a{separator}b", operation="c", environment=same_env, idempotency_key=same_key
        )
        split_right = _scoped_key_sha256(
            actor_id="a", operation=f"b{separator}c", environment=same_env, idempotency_key=same_key
        )
        assert split_left != split_right, (
            f"components joined on {separator!r} collide: the encoding is separator-joined, not "
            "length-prefixed, and any actor able to put that byte in its id can forge another's key"
        )

    # And the un-shifted baseline really is deterministic and stable.
    hash_5 = _scoped_key_sha256(actor_id=_ACTOR_1, operation=same_op, environment=same_env, idempotency_key=same_key)
    hash_6 = _scoped_key_sha256(actor_id=_ACTOR_1, operation=same_op, environment=same_env, idempotency_key=same_key)
    assert hash_5 == hash_6


def test_scoped_key_hash_differs_by_actor_and_matches_for_the_same_tuple():
    hash_alice = _scoped_key_sha256(
        actor_id=_ACTOR_1, operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT, environment="TEST", idempotency_key="k"
    )
    hash_bob = _scoped_key_sha256(
        actor_id=_ACTOR_2, operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT, environment="TEST", idempotency_key="k"
    )
    assert hash_alice != hash_bob

    hash_alice_again = _scoped_key_sha256(
        actor_id=_ACTOR_1, operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT, environment="TEST", idempotency_key="k"
    )
    assert hash_alice == hash_alice_again, "same (actor, operation, environment, key) must replay to the same hash"


@pytest.mark.parametrize("cut", range(1, 32))
def test_every_truncation_of_the_actor_id_collides_the_two_fixture_actors(cut: int):
    """The PROPERTY the cross-actor tests depend on, asserted for every cut instead of one.

    A hash that truncates the actor before mixing it -- `actor_id[:n]` for any n short of
    the full id -- destroys cross-actor isolation. Every isolation test in this file can
    only NOTICE that if the two fixture actors collide under the truncation, and that is a
    fact about the FIXTURE, not about the store: with the previous pair (16 shared
    characters) `[:8]` was caught and `[:17]` was not, so the guard held for one chosen n
    and the mutation simply moved (Sol, round O2, finding 2).

    So this asserts the fact directly, for all 31 cuts: under `actor_id[:cut]` the two
    actors produce the SAME scoped hash. Combined with
    `test_scoped_key_hash_differs_by_actor_and_matches_for_the_same_tuple` -- which says
    the untruncated ids do NOT collide -- no truncating mutation of this hash can survive
    the isolation tests, whatever n it picks.
    """
    assert len(_ACTOR_1) == len(_ACTOR_2) == 32
    assert _ACTOR_1 != _ACTOR_2, "the pair must stay distinct at full length, or nothing is proved"

    truncated_alice = _scoped_key_sha256(
        actor_id=_ACTOR_1[:cut], operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT, environment="TEST", idempotency_key="k"
    )
    truncated_bob = _scoped_key_sha256(
        actor_id=_ACTOR_2[:cut], operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT, environment="TEST", idempotency_key="k"
    )

    assert truncated_alice == truncated_bob, (
        f"the fixture actors diverge at or before character {cut}, so a hash truncating at "
        f"{cut} would keep them distinct and every cross-actor test here would survive that "
        "mutation while isolation is actually gone"
    )


# ---------------------------------------------------------------------------
# DEFERRED TO THE NEXT PR, on purpose, not forgotten:
#   - the SECURITY DEFINER ownership-transfer pair (a low-privilege application
#     role shaped like `backend_rag_v2` inserting through the binder, and the
#     same insert failing once the function is mis-owned again), and
#   - the lost-race recovery on a READY document, which needs
#     `service.py::_reconcile_lost_race_ready_replay` to exist first.
# Both are one concern each and each carries its own mutations; splitting them
# out keeps THIS PR to the adapter and the idempotency/race contract it owns.
# ---------------------------------------------------------------------------


async def test_lost_race_with_a_different_payload_is_a_conflict_not_a_lost_race(
    pool: asyncpg.Pool,
):
    """Losing the INSERT race says NOTHING about whose payload won.

    Two callers, same actor and key, DIFFERENT payloads, each having observed the key
    absent before either inserts. One wins. If the loser's INSERT reaches the primary key
    -- which is what happens when it looked before the winner's row existed -- it has
    never compared payloads, because there was nothing to compare against. Reporting
    `False` there tells the caller "you merely lost a race, the committed outcome is yours
    to read", which is a lie: the committed outcome belongs to a DIFFERENT document. The
    contract's answer is IDEMPOTENCY_CONFLICT, and it is the answer this test pins.

    DECLARED LIMIT (Sol, round O2, finding 1), same one as
    `test_two_concurrent_commits_same_key_exactly_one_wins`: the barrier coordinates the
    two EXTERNAL probes, not the lookups the two `commit()` calls make internally. Nothing
    here forces the loser through the `UniqueViolationError` branch rather than through the
    ordinary sequential `SELECT ... FOR UPDATE` comparison -- Sol showed both tests pass,
    with zero primary-key violations, against a candidate with that handler deleted. Both
    routes owe the caller IDEMPOTENCY_CONFLICT, which is why the assertion is still worth
    making; making WHICH route ran observable is what SPEC-PR2b-interleaving.md specifies.
    """
    store_a = PostgresDocumentStore(pool, environment=_ENV)
    store_b = PostgresDocumentStore(pool, environment=_ENV)
    key_hash = _scoped_key_sha256(
        actor_id=_ACTOR_1,
        operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
        environment=_ENV,
        idempotency_key="key-conflict-race",
    )

    both_looked = asyncio.Barrier(2)

    async def commit_after_both_saw_nothing(store, payload_hash, outcome):
        async with pool.acquire() as probe:
            assert await probe.fetchval(
                "SELECT count(*) FROM public.garuda_documents WHERE key_sha256 = $1", key_hash
            ) == 0
        await both_looked.wait()
        return await store.commit("key-conflict-race", payload_hash, outcome, actor_id=_ACTOR_1)

    results = await asyncio.gather(
        commit_after_both_saw_nothing(store_a, "aa" * 32, _low_confidence(_doc_id("doc-conflict-a"))),
        commit_after_both_saw_nothing(store_b, "bb" * 32, _low_confidence(_doc_id("doc-conflict-b"))),
        return_exceptions=True,
    )

    winners = [r for r in results if r is True]
    conflicts = [r for r in results if isinstance(r, IdempotencyConflictError)]
    assert len(winners) == 1, f"exactly one caller must win: {results!r}"
    assert len(conflicts) == 1, (
        f"the loser carried a DIFFERENT payload and must be told IDEMPOTENCY_CONFLICT, "
        f"never False: {results!r}"
    )


async def test_a_duplicate_document_id_is_not_reported_as_a_lost_race(store: PostgresDocumentStore):
    """Migration 304 carries TWO unique constraints, and only one of them means "someone
    won your key".

    `UNIQUE(document_id)` firing means the document id this call minted already exists
    under some OTHER key. Nobody won THIS key. Returning False would send `service.py` to
    re-read a key that was never committed, where its `assert winning_outcome is not None`
    fires — a 500 whose stack trace names the wrong thing entirely. It must propagate.
    """
    shared_document = _doc_id("doc-shared-across-two-keys")
    assert await store.commit("key-first-0000000001", "aa" * 32, _low_confidence(shared_document), actor_id=_ACTOR_1)

    with pytest.raises(asyncpg.UniqueViolationError) as raised:
        await store.commit("key-second-000000001", "bb" * 32, _low_confidence(shared_document), actor_id=_ACTOR_1)
    assert raised.value.constraint_name == "garuda_documents_document_id_key"

    # And the key really was never committed — which is exactly why False would have lied.
    assert await store.get_existing("key-second-000000001", "bb" * 32, actor_id=_ACTOR_1) is None


async def test_low_confidence_replay_returns_the_fields_in_the_original_order(
    store: PostgresDocumentStore,
):
    """"Replays the original outcome" has to include the ORDER.

    `confidence.py` emits uncertain fields by iterating `PassportReviewFieldName`, so the
    enum's declaration order is the original. The store reads them back `ORDER BY
    field_path`, which is deterministic but alphabetical — a different sequence, and a
    different serialized body for the customer. This pair is chosen so the two orders
    DISAGREE: in the enum `passport_number` precedes `nationality`, alphabetically it does
    not. A fixture whose fields happen to be alphabetical hides the whole defect.

    DECLARED LIMIT (Sol, round O2, finding 4). What this proves is the CANONICAL case:
    the store returns the enum's declaration order, and for outcomes `confidence.py`
    produces that IS the order they were sent in. It does NOT prove the stronger sentence
    "a replay preserves the order received", which is false for a `LowConfidenceOutcome`
    assembled in any other order -- nothing in the port constrains the caller to the enum
    order, and the store has no column to remember a different one in. The port docstring
    now promises the canonical order explicitly rather than the received one; making the
    received order survivable is a schema change, specified in SPEC-PR2b-interleaving.md.
    """
    fields = (
        UncertainReviewField(field_path=PassportReviewFieldName.PASSPORT_NUMBER, confirmation_required=True),
        UncertainReviewField(field_path=PassportReviewFieldName.NATIONALITY, confirmation_required=True),
    )
    enum_order = [f.value for f in PassportReviewFieldName]
    assert enum_order.index(PassportReviewFieldName.PASSPORT_NUMBER.value) < enum_order.index(
        PassportReviewFieldName.NATIONALITY.value
    ), "this test is only meaningful while the enum disagrees with alphabetical order"
    assert PassportReviewFieldName.NATIONALITY.value < PassportReviewFieldName.PASSPORT_NUMBER.value

    outcome = LowConfidenceOutcome(document_id=_doc_id("doc-order-0000000000001"), uncertain_fields=fields)
    assert await store.commit("key-order-000000001", "dd" * 32, outcome, actor_id=_ACTOR_1)

    replayed = await store.get_existing("key-order-000000001", "dd" * 32, actor_id=_ACTOR_1)

    assert replayed == outcome, "a replay must equal the original, order included"


def test_a_dsn_password_never_reaches_a_skip_or_fail_message():
    """Skip and fail reasons land in JUnit XML and in CI job logs. CI's own DSN carries a
    password (`postgresql://test:test@...`), and an f-string — `!r` included — prints it
    verbatim. A synthetic sentinel proves the redaction rather than trusting the shape.
    """
    sentinel = "s3ntinel-never-log-this"
    dsn = f"postgresql://ci_user:{sentinel}@db.internal:5432/nuzantara_test"

    redacted = _redacted(dsn)

    assert sentinel not in redacted
    assert "ci_user" in redacted and "db.internal" in redacted and "nuzantara_test" in redacted


def test_the_database_component_is_replaced_structurally_not_textually():
    """`rsplit("/", 1)` on a DSN whose QUERY contains a slash rewrites the query and leaves
    the database in place — the isolation promise silently inverted, DDL landing on the
    shared database while teardown drops a disposable one created elsewhere.
    """
    dsn = "postgresql://host:5432/nuzantara_test?application_name=garuda/ci"

    swapped = _with_database(dsn, "nuzantara_test_gdoc_abc123")

    assert "/nuzantara_test_gdoc_abc123" in swapped
    assert "application_name=garuda/ci" in swapped, "the query must survive untouched"
    assert "/nuzantara_test?" not in swapped

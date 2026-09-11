"""Integration tests for migration 289 -- the Visa Oracle's two retention
binders must resolve their OWN scope.

Reproduces the 2026-08-26 production outage against a real, throwaway
Postgres database, in the same spirit as test_garuda_voa_retention.py /
test_retention_binding_security_definer.py's throwaway-database pattern:
migration 281 widened ``visa_decision_retention_policies`` into the ONE
retention authority for four data classes (VISA_DECISION, GARUDA_CHECK,
GARUDA_ORDER, GARUDA_MAGIC_LINK) and partitioned its exclusion constraint on
``policy_scope`` -- but the two pre-existing Visa Oracle binder triggers
(``bind_visa_decision_retention_policy`` /
``bind_visa_evaluate_idempotency_retention_policy``, both migration 264) kept
resolving "the" active policy with no scope predicate at all. The moment a
GARUDA_CHECK policy went active in PRODUCTION alongside the VISA_DECISION
policy, both triggers' ``INTO STRICT`` matched two rows and raised
TOO_MANY_ROWS ("decision retention policy authority is ambiguous" /
"idempotency retention policy authority is ambiguous"). Migration 289 adds
``AND policy_scope = 'VISA_DECISION'`` to both.

Applies the same self-contained Visa Engine + GARUDA VOA migration subset
test_garuda_voa_retention.py already proved standalone-applicable to an empty
database (250-257, 261-268, 276, 281), plus 289 itself -- 289 has no
dependency on anything migrations 282-288 add (garuda_orders/magic_link/
check_results/practices), so this is the real boundary for this migration's
proof, not an arbitrary cut.

Run manually (creates+drops its own throwaway database via an admin
connection derived from ``TEST_DATABASE_URL``, swapped to the ``postgres``
maintenance database; never touches ``nuzantara_dev``/``nuzantara_test``
themselves):

    TEST_DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \\
    PYTHONPATH=. pytest \\
      backend/tests/scripts/visa_engine/test_retention_binders_scope_to_visa_decision.py -v
"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.scripts.visa_engine import fullstack_smoke, retention_worker
from backend.services.visa_engine import retention

pytestmark = pytest.mark.asyncio

_ADMIN_URL = (
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://nuzantara@localhost:5432/nuzantara_test",
    ).rsplit("/", 1)[0]
    + "/postgres"
)

# Same self-contained subset test_garuda_voa_retention.py proved standalone-
# applicable to an empty database, plus 289 itself.
MIGRATION_NUMBERS: tuple[int, ...] = (
    250, 251, 252, 253, 254, 255, 256, 257,
    261, 262, 263, 264, 265, 266, 267, 268,
    276, 281, 289,
)


def _db_url_for(db_name: str) -> str:
    return _ADMIN_URL.rsplit("/", 1)[0] + f"/{db_name}"


def _resolve_migration(number: int):
    backend_root = fullstack_smoke._backend_root()
    migrations_dir = backend_root / "backend" / "db" / "migrations_v2"
    matches = sorted(migrations_dir.glob(f"{number}_*.sql"))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one migration {number}, found {[p.name for p in matches]}"
        )
    return matches[0]


async def _apply_migrations_through(database_dsn: str, *, through: int) -> None:
    connection = await asyncpg.connect(database_dsn)
    try:
        for number in MIGRATION_NUMBERS:
            if number > through:
                continue
            migration_path = _resolve_migration(number)
            forward_sql, _rollback_sql = split_migration_sql(
                migration_path.read_text(encoding="utf-8")
            )
            async with connection.transaction():
                await connection.execute(forward_sql)
    finally:
        await connection.close()


class _Sandbox(NamedTuple):
    database_dsn: str


@pytest_asyncio.fixture
async def retention_scope_sandbox() -> AsyncIterator[_Sandbox]:
    db_name = f"nuzantara_test_visa_m289_{uuid.uuid4().hex[:16]}"
    admin_conn = await asyncpg.connect(_ADMIN_URL)
    try:
        await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin_conn.close()

    try:
        yield _Sandbox(database_dsn=_db_url_for(db_name))
    finally:
        admin_conn = await asyncpg.connect(_ADMIN_URL)
        try:
            await admin_conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                db_name,
            )
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            await admin_conn.close()


async def _insert_policy(
    connection: asyncpg.Connection,
    *,
    scope: str,
    policy_version: str,
    environment: str = "PRODUCTION",
) -> None:
    """Insert an active retention policy for ``scope``.

    281's ``visa_decision_retention_policies_scope_anchor`` CHECK constraint
    requires ``retention_anchor = 'CREATED_AT'`` when ``policy_scope =
    'GARUDA_CHECK'`` -- picked automatically here so callers never need to
    know that detail to reproduce the two-scope coexistence this migration
    is about.
    """

    anchor = "CREATED_AT" if scope == "GARUDA_CHECK" else "EVALUATED_AT"
    await connection.execute(
        f"""
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_scope, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor, effective_period, approved_by, approval_reference
        ) VALUES (
            '{environment}', '{scope}', $1, INTERVAL '90 days',
            INTERVAL '1 hour', INTERVAL '30 days',
            '{anchor}', tstzrange(clock_timestamp() - INTERVAL '1 day', NULL, '[)'),
            'zero-test-approver', 'ZERO-RETENTION-TEST-APPROVAL'
        )
        """,
        policy_version,
    )


async def _insert_visa_decision(
    connection: asyncpg.Connection, *, environment: str = "PRODUCTION"
) -> uuid.UUID:
    decision_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    await connection.execute(
        """
        INSERT INTO public.visa_decisions (
            decision_id, environment, engine_surface, engine_mode, verdict,
            citations, engine_version, effective_at, observed_at, evaluated_at,
            request_fingerprint, request_category, candidate_summary, grounding_summary
        ) VALUES (
            $1, $2, 'MATCH', 'SHADOW', 'TEMPORARILY_UNAVAILABLE',
            '[]'::jsonb, 'visa-engine/test-m289', $3, $3, $3, $4, 'other',
            '[]'::jsonb, '[]'::jsonb
        )
        """,
        decision_id,
        environment,
        now,
        hashlib.sha256(f"m289-test-{decision_id}".encode()).digest(),
    )
    return decision_id


async def _insert_idempotency_reservation(
    connection: asyncpg.Connection, *, environment: str = "PRODUCTION"
) -> bytes:
    """Reserve one replay key, letting the DB own every clock and the deadline.

    The key id carries no ``/``: 264's
    ``visa_evaluate_idempotency_request_hmac_key_id_check`` regex is
    ``^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$``, and a slash fails it -- which
    surfaced only on the GREEN path, because on the RED path the BEFORE
    trigger raises before any CHECK is evaluated.

    ``reserved_at``/``created_at`` are omitted deliberately: the binder rejects
    any value that is not ``statement_timestamp()``, and the column DEFAULTs
    already supply exactly that. ``expires_at`` is NOT NULL with no default and
    is also omitted -- the BEFORE trigger fills it from the policy, and a BEFORE
    trigger runs ahead of constraint checking, so the row is complete by the
    time NOT NULL is evaluated. Supplying either by hand would test this test's
    arithmetic instead of the binder's.
    """

    key_sha256 = hashlib.sha256(f"m289-idem-{uuid.uuid4()}".encode()).digest()
    await connection.execute(
        """
        INSERT INTO public.visa_evaluate_idempotency (
            key_sha256, request_hmac, request_hmac_key_id, environment
        ) VALUES ($1, $2, 'visa-engine.test-m289-key', $3)
        """,
        key_sha256,
        hashlib.sha256(b"m289-idem-request").digest(),
        environment,
    )
    return key_sha256


async def test_decision_insert_fails_ambiguous_before_289_when_garuda_check_also_active(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """RED: reproduces the 2026-08-26 outage's second stage. With only 281
    applied (289 NOT applied), the unscoped ``INTO STRICT`` in
    ``bind_visa_decision_retention_policy`` matches both the VISA_DECISION
    and the GARUDA_CHECK policy and raises TOO_MANY_ROWS.
    """

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(connection, scope="VISA_DECISION", policy_version="pre289-visa-v1")
        await _insert_policy(connection, scope="GARUDA_CHECK", policy_version="pre289-garuda-v1")
        with pytest.raises(
            asyncpg.RaiseError, match="decision retention policy authority is ambiguous"
        ):
            await _insert_visa_decision(connection)
    finally:
        await connection.close()


async def test_decision_binder_binds_to_visa_decision_policy_when_garuda_check_also_active(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """GREEN: with 289 applied, the binder resolves ONLY the VISA_DECISION
    policy even though a GARUDA_CHECK policy is simultaneously active for the
    same environment -- the exact shape that broke production on
    2026-08-26."""

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=289)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(connection, scope="VISA_DECISION", policy_version="post289-visa-v1")
        await _insert_policy(connection, scope="GARUDA_CHECK", policy_version="post289-garuda-v1")

        decision_id = await _insert_visa_decision(connection)

        row = await connection.fetchrow(
            "SELECT retention_policy_id FROM public.visa_decisions WHERE decision_id = $1",
            decision_id,
        )
        visa_decision_policy_id = await connection.fetchval(
            "SELECT id FROM public.visa_decision_retention_policies WHERE policy_version = $1",
            "post289-visa-v1",
        )
        garuda_check_policy_id = await connection.fetchval(
            "SELECT id FROM public.visa_decision_retention_policies WHERE policy_version = $1",
            "post289-garuda-v1",
        )
        assert row["retention_policy_id"] == visa_decision_policy_id
        assert row["retention_policy_id"] != garuda_check_policy_id
    finally:
        await connection.close()


async def test_289_rollback_restores_the_ambiguous_error(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """The rollback half of 289 is not decoration: applying it against a
    database that still holds a foreign-scope active policy must reproduce
    the exact 2026-08-26 outage shape, not merely "some" error. Proves the
    marker's contract (migration_base.py requires ``-- === ROLLBACK ===`` on
    every migration > 111) actually rolls back to the DEFECTIVE behaviour,
    which is what a rollback of a bugfix migration necessarily means here --
    289's own header says so explicitly.
    """

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=289)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(connection, scope="VISA_DECISION", policy_version="rollback-visa-v1")
        await _insert_policy(connection, scope="GARUDA_CHECK", policy_version="rollback-garuda-v1")

        # GREEN, confirmed before rolling back: with 289 applied, the insert
        # succeeds and binds to the VISA_DECISION policy.
        first_decision_id = await _insert_visa_decision(connection)
        row = await connection.fetchrow(
            "SELECT retention_policy_id FROM public.visa_decisions WHERE decision_id = $1",
            first_decision_id,
        )
        assert row["retention_policy_id"] is not None

        _forward_289, rollback_289 = split_migration_sql(
            _resolve_migration(289).read_text(encoding="utf-8")
        )
        assert rollback_289, "289 must carry a '-- === ROLLBACK ===' section"
        async with connection.transaction():
            await connection.execute(rollback_289)

        # RED restored: the same two active policies, but the binder is back
        # to its pre-289 unscoped INTO STRICT and raises TOO_MANY_ROWS again.
        with pytest.raises(
            asyncpg.RaiseError, match="decision retention policy authority is ambiguous"
        ):
            await _insert_visa_decision(connection)
    finally:
        await connection.close()


async def test_retention_worker_active_policy_resolves_with_foreign_scope_policy_present(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """GREEN: with 289 applied, ``retention_worker._active_policy`` resolves
    the VISA_DECISION policy even though a GARUDA_CHECK policy is
    simultaneously active for PRODUCTION."""

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=289)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(connection, scope="VISA_DECISION", policy_version="post289-worker-visa-v1")
        await _insert_policy(connection, scope="GARUDA_CHECK", policy_version="post289-worker-garuda-v1")
    finally:
        await connection.close()

    pool = await asyncpg.create_pool(retention_scope_sandbox.database_dsn, min_size=1, max_size=2)
    try:
        active = await retention_worker._active_policy(pool)
        assert active.policy_version == "post289-worker-visa-v1"
    finally:
        await pool.close()


async def test_active_policy_available_stays_true_when_garuda_check_also_active(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """GREEN: ``retention.active_policy_available`` (the Python evaluate
    gate -- the first reader that broke in production, symptom users
    actually saw as HTTP 200 TEMPORARILY_UNAVAILABLE) stays True when a
    foreign-scope (GARUDA_CHECK) policy coexists with the VISA_DECISION one.

    This behaviour does not depend on migration 289 (289 touches only the two
    SQL trigger binders) -- ``active_policy_available``'s own scope predicate
    is what makes this pass, and it is exercised here against the full
    289-applied schema for parity with the rest of this file.
    """

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=289)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(
            connection, scope="VISA_DECISION", policy_version="post289-available-visa-v1"
        )
        await _insert_policy(
            connection, scope="GARUDA_CHECK", policy_version="post289-available-garuda-v1"
        )
    finally:
        await connection.close()

    pool = await asyncpg.create_pool(retention_scope_sandbox.database_dsn, min_size=1, max_size=2)
    try:
        assert await retention.active_policy_available(
            pool,
            environment="PRODUCTION",
            evaluated_at=datetime.now(timezone.utc),
        )
    finally:
        await pool.close()


async def test_idempotency_insert_fails_ambiguous_before_289_when_garuda_check_also_active(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """RED, for the SECOND binder 289 repairs.

    ``bind_visa_evaluate_idempotency_retention_policy`` has the same unscoped
    ``INTO STRICT`` as the decision binder, and fires FIRST on a real request
    path -- a reservation is taken before a decision is written. Without this
    test the migration would ship with behavioural proof for one of its two
    functions and structural proof for the other, which is how a half-cure
    reads as a whole one (scar #2 / W107, "curato 1 wrapper su 5").
    """

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=281)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(connection, scope="VISA_DECISION", policy_version="pre289-idem-visa-v1")
        await _insert_policy(
            connection, scope="GARUDA_CHECK", policy_version="pre289-idem-garuda-v1"
        )
        with pytest.raises(
            asyncpg.RaiseError,
            match="idempotency retention policy authority is ambiguous",
        ):
            await _insert_idempotency_reservation(connection)
    finally:
        await connection.close()


async def test_idempotency_binder_binds_to_visa_decision_policy_when_garuda_check_also_active(
    retention_scope_sandbox: _Sandbox,
) -> None:
    """GREEN for the second binder: it resolves the VISA_DECISION policy and
    binds to ITS id, never the coexisting GARUDA_CHECK one. Asserted in both
    directions -- equal to the right id AND unequal to the wrong one -- because
    an assertion that only checks non-NULL would pass on either policy."""

    await _apply_migrations_through(retention_scope_sandbox.database_dsn, through=289)
    connection = await asyncpg.connect(retention_scope_sandbox.database_dsn)
    try:
        await _insert_policy(
            connection, scope="VISA_DECISION", policy_version="post289-idem-visa-v1"
        )
        await _insert_policy(
            connection, scope="GARUDA_CHECK", policy_version="post289-idem-garuda-v1"
        )

        key_sha256 = await _insert_idempotency_reservation(connection)

        row = await connection.fetchrow(
            "SELECT retention_policy_id, expires_at, reserved_at "
            "FROM public.visa_evaluate_idempotency WHERE key_sha256 = $1",
            key_sha256,
        )
        visa_decision_policy_id = await connection.fetchval(
            "SELECT id FROM public.visa_decision_retention_policies WHERE policy_version = $1",
            "post289-idem-visa-v1",
        )
        garuda_check_policy_id = await connection.fetchval(
            "SELECT id FROM public.visa_decision_retention_policies WHERE policy_version = $1",
            "post289-idem-garuda-v1",
        )
        assert row["retention_policy_id"] == visa_decision_policy_id
        assert row["retention_policy_id"] != garuda_check_policy_id
        # The deadline must come from the VISA_DECISION policy's own interval
        # (1 hour, per _insert_policy), not merely be non-NULL: binding to the
        # right row and then deriving the wrong deadline would still be a bug.
        assert row["expires_at"] == row["reserved_at"] + timedelta(hours=1)
    finally:
        await connection.close()

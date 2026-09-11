"""Execute migration 312's retention binder and guard trigger against a live
Postgres -- same discipline as `test_migration_310_practice_status_log_
trigger.py`: the defect PENDING-ARMS row 1847 names ("the staff transition
engine records OPAQUE evidence/artifact ids and never verifies their
content nor serves the artifact") is a missing OBJECT, and a test that only
greps this migration's SQL for the right keywords would prove nothing about
whether the retention binder actually fires or the guard trigger actually
blocks a DELETE. So this file applies the real DDL and drives it with real
INSERT/UPDATE/DELETE.

Idempotent re-application (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE
FUNCTION`, `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER`) is what makes this
safe to run BOTH against CI's freshly-`apply-all`'d database (where 312 is
already live) and against a developer machine whose local copy is behind --
same reasoning 310's own test gives for why applying is deliberate rather
than skipped.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import split_migration_sql

MIGRATION = (
    Path(__file__).resolve().parents[2] / "db" / "migrations_v2" / "312_garuda_practice_artifacts.sql"
)

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DSN, reason="TEST_DATABASE_URL is unset — no live Postgres to drive"
)

_SYNTHETIC_DIGEST = hashlib.sha256(b"%PDF-1.4 synthetic fixture, no real document").hexdigest()


def test_the_migration_file_exists_and_declares_a_rollback() -> None:
    """Cheap structural guard: the runner refuses a file with no ROLLBACK marker."""
    assert MIGRATION.is_file(), f"{MIGRATION} is missing"
    forward, rollback = split_migration_sql(MIGRATION.read_text())
    assert "garuda_practice_artifacts" in forward
    assert rollback is not None, "migration runner requires the ROLLBACK marker"

    executable = [
        line for line in rollback.splitlines() if line.strip() and not line.strip().startswith("--")
    ]
    assert executable, "the ROLLBACK section contains no executable statement"
    joined = " ".join(executable).upper()
    assert "DROP TRIGGER" in joined
    assert "DROP FUNCTION" in joined
    assert "DROP TABLE" in joined


#: Same guard as 310's own suite, same reasoning: this fixture applies 312
#: PERMANENTLY (outside any transaction) against whatever TEST_DATABASE_URL
#: resolves to, so a mistyped DSN must never be allowed to reach a real
#: database.
_FORBIDDEN_DB_SUBSTRINGS = ("nuzantara_rag", "prod", "production")


def _forbidden(dbname: str) -> str | None:
    lowered = dbname.lower()
    return next((bad for bad in _FORBIDDEN_DB_SUBSTRINGS if bad in lowered), None)


@pytest.fixture
async def conn():
    if (bad := _forbidden((TEST_DSN or "").split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1])):
        pytest.fail(
            f"refusing to apply migration DDL — TEST_DATABASE_URL names a real "
            f"database (matched {bad!r})."
        )

    connection = await asyncpg.connect(TEST_DSN)
    try:
        actual = await connection.fetchval("SELECT current_database()")
        if (bad := _forbidden(actual or "")):
            pytest.fail(
                f"refusing to apply migration DDL to database {actual!r} — matched {bad!r}."
            )
        forward, _ = split_migration_sql(MIGRATION.read_text())
        await connection.execute(forward)
        # Seeded HERE, autocommitted before any test's own transaction
        # starts -- not inside a test's `tx`, or the policy row's
        # `clock_timestamp()`-derived effective_period lower bound and the
        # artifact row's `NOW()` (frozen at the SAME transaction's start,
        # therefore EARLIER) would race, and the retention binder would
        # measure the artifact as created before its own policy began.
        policy_version = await _ensure_test_retention_policy(connection)
        try:
            yield connection
        finally:
            await _close_garuda_document_test_policy(connection, policy_version)
    finally:
        await connection.close()


async def _ensure_test_retention_policy(conn: asyncpg.Connection) -> str:
    """One `GARUDA_DOCUMENT` / `TEST` policy, open-ended, 30 days -- shared
    across every test in this file (idempotent: `ON CONFLICT DO NOTHING`
    keyed by the table's own `UNIQUE (environment, policy_scope,
    policy_version)`, widened by 281)."""
    # Self-heal first, the same shape `test_garuda_orders_ownership.py`'s
    # `_ensure_garuda_order_test_policy` uses for GARUDA_ORDER. An
    # `ON CONFLICT (environment, policy_scope, policy_version)` target only
    # absorbs an IDENTICAL version: a second, differently-named open-ended
    # policy for the same (environment, scope) violates the EXCLUDE constraint
    # `visa_decision_retention_policies_scope_period_excl` instead, which no
    # ON CONFLICT target covers. Measured, not assumed: run in ONE process
    # (as CI does) with the migration-312 suite, the previous fixture's
    # policy was still open and 8 tests errored on exactly that constraint.
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
           AND upper(effective_period) IS NULL
        """
    )
    policy_version = f"w3a-312-fixture-{uuid.uuid4().hex[:16]}"
    await conn.execute(
        """
        INSERT INTO visa_decision_retention_policies (
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
        policy_version,
    )
    return policy_version


async def _close_garuda_document_test_policy(conn: asyncpg.Connection, policy_version: str) -> None:
    """Teardown twin: close the policy this module opened, so the next module's
    self-heal has nothing left to close and no open row outlives the run."""
    await conn.execute(
        """
        UPDATE public.visa_decision_retention_policies
           SET effective_period = tstzrange(lower(effective_period), clock_timestamp(), '[)')
         WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
           AND policy_version = $1 AND upper(effective_period) IS NULL
        """,
        policy_version,
    )


async def _seed_practice(conn: asyncpg.Connection, *, suffix: str) -> str:
    """A real `garuda_orders` -> `garuda_order_journal` (OP-02) ->
    `garuda_practices` chain, matching the FK this table hangs off. Returns
    the minted `practice_id`."""
    order_id = f"order_312fx_{suffix}"
    event_id = f"evt_312fx_{suffix}"
    practice_id = f"prc_312fx_{suffix}"
    await conn.execute(
        """
        INSERT INTO garuda_orders (
            order_id, result_id_ref, case_type, applicant_full_name,
            applicant_email, applicant_phone, applicant_passport_number,
            price_idr, price_catalogue_key, state
        ) VALUES ($1, $2, 'issuance', 'Test User', 't@example.com', '+10000000',
                  'P1234567', 790000, 'B1_VOA_ISSUANCE', 'paid')
        """,
        order_id,
        f"result_312fx_{suffix}",
    )
    await conn.execute(
        """
        INSERT INTO garuda_order_journal (event_id, event_name, aggregate_type, aggregate_id, transition_id, customer_visible)
        VALUES ($1, 'payment.paid', 'order', $2, 'OP-02', true)
        """,
        event_id,
        order_id,
    )
    await conn.execute(
        """
        INSERT INTO garuda_practices (practice_id, order_id, source_paid_journal_event_id)
        VALUES ($1, $2, $3)
        """,
        practice_id,
        order_id,
        event_id,
    )
    return practice_id


async def _insert_artifact(
    conn: asyncpg.Connection,
    *,
    artifact_id: str,
    practice_id: str,
    environment: str = "TEST",
    content_type: str = "application/pdf",
    byte_length: int = 42,
    digest: str = _SYNTHETIC_DIGEST,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        INSERT INTO garuda_practice_artifacts
            (artifact_id, practice_id, storage_key, artifact_digest, byte_length, content_type, produced_by, environment)
        VALUES ($1, $2, $3, $4, $5, $6, 'staff@balizero.com', $7)
        RETURNING artifact_id, retention_policy_id, retention_until, created_at, superseded_at
        """,
        artifact_id,
        practice_id,
        f"artifacts/{environment}/{practice_id}/{artifact_id}",
        digest,
        byte_length,
        content_type,
        environment,
    )


class TestRetentionBinding:
    @pytest.mark.asyncio
    async def test_insert_derives_retention_until_from_the_active_policy(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            row = await _insert_artifact(
                conn, artifact_id=f"art_{uuid.uuid4().hex[:20]}", practice_id=practice_id
            )
            assert row["retention_policy_id"] is not None
            assert (row["retention_until"] - row["created_at"]).days == 30
            assert row["superseded_at"] is None
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_insert_fails_closed_with_no_active_policy_for_the_environment(self, conn) -> None:
        """No `GARUDA_DOCUMENT` policy is ever seeded for `STAGING` in this
        suite -- the write must fail closed, not default to forever."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            with pytest.raises(asyncpg.PostgresError, match="no active Zero-approved retention policy"):
                await _insert_artifact(
                    conn,
                    artifact_id=f"art_{uuid.uuid4().hex[:20]}",
                    practice_id=practice_id,
                    environment="STAGING",
                )
        finally:
            await tx.rollback()


class TestGuardTriggerAppendOnly:
    @pytest.mark.asyncio
    async def test_a_second_live_insert_for_the_same_practice_is_refused(self, conn) -> None:
        """`ux_garuda_practice_artifacts_live` -- one live artifact per
        practice is a database fact (spec SS2), not a caller convention."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            await _insert_artifact(
                conn, artifact_id=f"art_{uuid.uuid4().hex[:20]}", practice_id=practice_id
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await _insert_artifact(
                    conn, artifact_id=f"art_{uuid.uuid4().hex[:20]}", practice_id=practice_id
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_delete_is_refused_unconditionally(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            with pytest.raises(asyncpg.PostgresError, match="cannot be removed by this role"):
                await conn.execute(
                    "DELETE FROM garuda_practice_artifacts WHERE artifact_id = $1", artifact_id
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_update_with_no_superseded_at_at_all_is_refused(self, conn) -> None:
        """The only-permitted-shape branch: an UPDATE that never touches
        `superseded_at` (leaving it NULL) is refused regardless of what
        column it DOES touch."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            with pytest.raises(asyncpg.PostgresError, match="the only permitted UPDATE sets superseded_at"):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts SET produced_by = 'someone-else@balizero.com' "
                    "WHERE artifact_id = $1",
                    artifact_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_update_setting_superseded_at_alongside_another_column_is_refused(
        self, conn
    ) -> None:
        """The immutable-columns branch: setting `superseded_at` does not
        license changing anything else in the SAME UPDATE."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            with pytest.raises(asyncpg.PostgresError, match="only superseded_at may change"):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts "
                    "SET superseded_at = clock_timestamp(), produced_by = 'someone-else@balizero.com' "
                    "WHERE artifact_id = $1",
                    artifact_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_setting_superseded_at_succeeds_and_frees_the_practice_for_a_new_live_row(
        self, conn
    ) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            first_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=first_id, practice_id=practice_id)

            await conn.execute(
                "UPDATE garuda_practice_artifacts SET superseded_at = clock_timestamp() "
                "WHERE artifact_id = $1",
                first_id,
            )
            superseded_at = await conn.fetchval(
                "SELECT superseded_at FROM garuda_practice_artifacts WHERE artifact_id = $1",
                first_id,
            )
            assert superseded_at is not None

            # The partial unique index only binds LIVE rows -- a fresh
            # insert for the same practice must now succeed.
            second_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=second_id, practice_id=practice_id)
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_superseded_at_is_immutable_once_set(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            await conn.execute(
                "UPDATE garuda_practice_artifacts SET superseded_at = clock_timestamp() "
                "WHERE artifact_id = $1",
                artifact_id,
            )
            with pytest.raises(asyncpg.PostgresError, match="immutable once set"):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts SET superseded_at = clock_timestamp() "
                    "WHERE artifact_id = $1",
                    artifact_id,
                )
        finally:
            await tx.rollback()


class TestColumnChecks:
    @pytest.mark.asyncio
    async def test_byte_length_over_ceiling_is_rejected(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_artifact(
                    conn,
                    artifact_id=f"art_{uuid.uuid4().hex[:20]}",
                    practice_id=practice_id,
                    byte_length=26214401,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_non_pdf_content_type_is_rejected(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_artifact(
                    conn,
                    artifact_id=f"art_{uuid.uuid4().hex[:20]}",
                    practice_id=practice_id,
                    content_type="image/png",
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_non_hex_digest_is_rejected(self, conn) -> None:
        """The contract's `^[a-f0-9]{64}$` (spec fact 17's cure) -- an
        uppercase or non-hex 64-char string must never reach this row."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_artifact(
                    conn,
                    artifact_id=f"art_{uuid.uuid4().hex[:20]}",
                    practice_id=practice_id,
                    digest="A" * 64,
                )
        finally:
            await tx.rollback()

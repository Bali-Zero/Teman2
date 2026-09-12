"""Execute migration 313's retention binder and guard trigger against a live
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
safe to run BOTH against CI's freshly-`apply-all`'d database (where 313 is
already live) and against a developer machine whose local copy is behind --
same reasoning 310's own test gives for why applying is deliberate rather
than skipped.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import uuid
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import split_migration_sql

MIGRATION = (
    Path(__file__).resolve().parents[2] / "db" / "migrations_v2" / "313_garuda_practice_artifacts.sql"
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


def test_the_rollback_never_touches_the_policy_scope_check() -> None:
    """Gate-6287d mutation (c), made red. 313 did not widen the policy_scope
    CHECK -- GARUDA_DOCUMENT is 304's -- so its rollback has nothing to
    narrow, and any `DROP`/`ADD CONSTRAINT ..._policy_scope_check` in it is
    285's shape smuggled in: an unconditional narrowing that raises
    CheckViolationError whenever a GARUDA_DOCUMENT row exists. The migration
    suite could not see that mutation (its seed is rolled back, so there was
    no row for the ALTER to refuse); the text can. The repo-wide shape rule
    for rollbacks that DO rebuild the CHECK is test_policy_scope_rollback_guard.py."""
    _, rollback = split_migration_sql(MIGRATION.read_text())
    assert rollback is not None
    executable = "\n".join(
        line for line in rollback.splitlines() if not line.strip().startswith("--")
    ).upper()
    for verb in ("ADD CONSTRAINT", "DROP CONSTRAINT"):
        assert f"{verb} VISA_DECISION_RETENTION_POLICIES_POLICY_SCOPE_CHECK" not in executable, (
            f"313's rollback must not {verb.lower()} the policy_scope CHECK: it never widened it"
        )


def test_both_halves_carry_the_ownership_privilege_bracket() -> None:
    """Structural guard for Sol findings F8/F9, cured under Imperatore
    decision #16 (2026-09-12). STRUCTURAL is the honest word: it reads the
    file, not a database. The behavioural proof needs a shape-D fixture
    (PG17, both roles provisioned, a non-superuser migrator) that this
    suite does not have -- ledgered as S1's own gear-3 precondition, not
    silently assumed here.

    What it does catch is the drift that actually happened: a forward half
    that hands objects to `visa_ledger_owner` and a rollback half that
    tries to remove them while the session has assumed `backend_rag_v2`,
    which owns none of them. Every removal then fails with "must be owner
    of", the rollback transaction aborts, and the operator is told an undo
    ran that did nothing.
    """
    forward, rollback = split_migration_sql(MIGRATION.read_text())

    # Forward: the table and the guard function leave backend_rag_v2.
    assert "ALTER TABLE %s OWNER TO %I" in forward
    assert "guard_garuda_practice_artifacts_mutation" in forward
    assert "$garuda_313_table_owner_transfer$" in forward
    # ... and the session is handed back to the runtime role afterwards, so
    # the migration does not leave the connection on a role nobody chose.
    assert "$garuda_313_resume_runtime_role_after_grants$" in forward

    # Neither half may name the role it returns to. `assume_runtime_role`
    # is an unconditional no-op in the single-DSN shape, so the session was
    # never on `backend_rag_v2` there -- and a superuser is a member of
    # every role, so a resume that ASKS whether it may become the runtime
    # role is answered yes and leaves the session somewhere it never was
    # (Sol O2 new finding 2). The role restored must be the one measured
    # before the reset.
    assert "set_config('garuda313.prior_role', current_role, false)" in forward
    assert "current_setting('garuda313.prior_role'" in forward
    assert "SET ROLE %I', target_role" not in forward, (
        "a resume block must restore the measured prior role, never a named one"
    )

    # Rollback: assume the owner BEFORE the removals, resume after.
    assert rollback is not None
    assert "$garuda_313_rollback_assume_owner$" in rollback
    assert "$garuda_313_rollback_resume_runtime_role$" in rollback
    assume_at = rollback.index("$garuda_313_rollback_assume_owner$")
    first_removal = min(
        i for i in (rollback.find("DROP TRIGGER"), rollback.find("DROP FUNCTION"), rollback.find("DROP TABLE"))
        if i != -1
    )
    assert assume_at < first_removal, (
        "the rollback's privilege bracket must open before the first removal statement"
    )


#: Same guard as 310's own suite, same reasoning: this fixture applies 313
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
        async with _seeded_test_retention_policy(connection):
            yield connection
    finally:
        await connection.close()


@contextlib.asynccontextmanager
async def _seeded_test_retention_policy(conn: asyncpg.Connection):
    """One `GARUDA_DOCUMENT` / `TEST` policy, open-ended, 30 days, seeded
    INSIDE a transaction this context rolls back -- so the database leaves
    exactly as it entered, which is the property gate-6287c found missing.

    The row cannot be deleted: `visa_decision_retention_policies` is
    append-only by 264's guard trigger (`RAISE EXCEPTION ... is append-only`
    on DELETE), which is why the first shape of this fixture CLOSED the row
    at teardown instead. Closing satisfied the EXCLUDE constraint and left the
    row behind -- and every visa_engine file that later calls
    `unwind_garuda_voa_retention_fk` on the same database rolls the registered
    dependents back in reverse order, and one of them re-narrows the
    `policy_scope` CHECK to a list without GARUDA_DOCUMENT -- NOT 304's own
    rollback, which sees the rows and leaves the CHECK widened, but 285's,
    which guards only GARUDA_MAGIC_LINK rows and on a clean database rebuilds
    the four-scope CHECK (round O5 corrected this attribution). Postgres
    refuses that ALTER while rows with the scope exist
    (`CheckViolationError: ..._policy_scope_check ... violated by some row`). CI was green only because xdist `--dist loadfile` happened to put
    this file and those on different database clones. A row that was never
    committed satisfies the re-narrowed CHECK, the EXCLUDE constraint and the
    append-only guard alike.

    Clock discipline, because the earlier shape's comment warned about it and
    the warning was right for the shape it described: the binder demands
    `created_at = transaction_timestamp()` and resolves the policy with
    `effective_period @> created_at`. Inside this outer transaction every
    test's own `conn.transaction()` is a savepoint, so `transaction_timestamp()`
    is ONE frozen instant for the seed and for every artifact row -- the
    policy's lower bound is therefore that same instant (not
    `clock_timestamp()`, which would run AHEAD of it and make the binder find
    no policy active at `created_at`). `[lower, NULL)` contains its own lower
    bound; the binder finds the policy.

    The self-heal that closes any still-open TEST/GARUDA_DOCUMENT row is
    kept, inside the same transaction: it is what lets the seed satisfy the
    EXCLUDE constraint on a database dirtied by an OLDER run of this file (the
    closed-not-deleted rows that run left cannot be removed by anyone). On a
    fresh database -- CI clones one per worker -- it is a no-op.

    The tripwire at exit compares the row count to the count at entry, so a
    shape that ever commits again fails HERE, where the causal chain is one
    function long, rather than in another product's file three shards away.
    """
    baseline = await conn.fetchval(
        "SELECT count(*) FROM public.visa_decision_retention_policies "
        "WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'"
    )
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute(
            """
            UPDATE public.visa_decision_retention_policies
               SET effective_period = tstzrange(lower(effective_period), transaction_timestamp(), '[)')
             WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'
               AND upper(effective_period) IS NULL
               AND lower(effective_period) < transaction_timestamp()
            """
        )
        await conn.execute(
            """
            INSERT INTO visa_decision_retention_policies (
                environment, policy_scope, policy_version, retention_interval,
                idempotency_retention_interval, legal_hold_review_interval,
                retention_anchor, effective_period, approved_by, approval_reference
            ) VALUES (
                'TEST', 'GARUDA_DOCUMENT', $1, INTERVAL '30 days',
                INTERVAL '1 hour', INTERVAL '30 days',
                'CREATED_AT', tstzrange(transaction_timestamp(), NULL, '[)'),
                'zero-test-approver', 'ZERO-GARUDA-DOCUMENT-RETENTION-TEST-APPROVAL'
            )
            """,
            f"w3a-313-fixture-{uuid.uuid4().hex[:16]}",
        )
        yield
    finally:
        await tx.rollback()
        residue = await conn.fetchval(
            "SELECT count(*) FROM public.visa_decision_retention_policies "
            "WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'"
        )
        assert residue == baseline, (
            f"this file's fixture left {residue - baseline} TEST/GARUDA_DOCUMENT retention "
            "policy row(s) behind; the next visa_engine file to call "
            "unwind_garuda_voa_retention_fk on this database will fail a dependent's "
            "rollback (285's, on a clean database) with CheckViolationError on the "
            "policy_scope CHECK"
        )


async def _seed_practice(conn: asyncpg.Connection, *, suffix: str) -> str:
    """A real `garuda_orders` -> `garuda_order_journal` (OP-02) ->
    `garuda_practices` chain, matching the FK this table hangs off. Returns
    the minted `practice_id`."""
    order_id = f"order_313fx_{suffix}"
    event_id = f"evt_313fx_{suffix}"
    practice_id = f"prc_313fx_{suffix}"
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
        f"result_313fx_{suffix}",
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
        `superseded_at`/`superseded_by` (leaving both NULL) is refused
        regardless of what column it DOES touch."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            with pytest.raises(
                asyncpg.PostgresError,
                match="the only permitted UPDATE sets superseded_at and superseded_by together",
            ):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts SET produced_by = 'someone-else@balizero.com' "
                    "WHERE artifact_id = $1",
                    artifact_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_update_setting_only_superseded_at_without_superseded_by_is_refused(
        self, conn
    ) -> None:
        """The pair-together rule (decision #13-revision): `superseded_at`
        alone, with `superseded_by` left NULL, is refused -- same branch,
        different half of the pair than the symmetric case below."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            with pytest.raises(
                asyncpg.PostgresError,
                match="the only permitted UPDATE sets superseded_at and superseded_by together",
            ):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts SET superseded_at = clock_timestamp() "
                    "WHERE artifact_id = $1",
                    artifact_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_update_setting_only_superseded_by_without_superseded_at_is_refused(
        self, conn
    ) -> None:
        """Symmetric half of the pair-together rule: `superseded_by` alone
        is refused too, even though it names a real row."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            other_practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            other_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=other_id, practice_id=other_practice_id)
            with pytest.raises(
                asyncpg.PostgresError,
                match="the only permitted UPDATE sets superseded_at and superseded_by together",
            ):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts SET superseded_by = $2 WHERE artifact_id = $1",
                    artifact_id,
                    other_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_a_row_cannot_name_itself_as_its_own_superseded_by(self, conn) -> None:
        """`CHECK (superseded_by IS NULL OR superseded_by <> artifact_id)`
        -- a row can never claim to have replaced itself."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts "
                    "SET superseded_at = clock_timestamp(), superseded_by = $1 "
                    "WHERE artifact_id = $1",
                    artifact_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_update_setting_the_pair_alongside_another_column_is_refused(
        self, conn
    ) -> None:
        """The immutable-columns branch: setting the pair does not license
        changing anything else in the SAME UPDATE."""
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            other_practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            other_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=other_id, practice_id=other_practice_id)
            with pytest.raises(
                asyncpg.PostgresError, match="only superseded_at and superseded_by may change"
            ):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts "
                    "SET superseded_at = clock_timestamp(), superseded_by = $2, "
                    "    produced_by = 'someone-else@balizero.com' "
                    "WHERE artifact_id = $1",
                    artifact_id,
                    other_id,
                )
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_setting_the_pair_succeeds_and_frees_the_practice_for_a_new_live_row(
        self, conn
    ) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            first_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=first_id, practice_id=practice_id)

            # Drive the REAL order the service uses: mark the old row
            # first, insert the successor for the SAME practice after
            # (postgres_repository.py::insert_superseding). An earlier
            # version of this test took a shortcut -- it pointed
            # `superseded_by` at an artifact of a DIFFERENT practice, purely
            # to have some real artifact_id on hand -- and passed, because
            # the composite FK is DEFERRABLE INITIALLY DEFERRED and this
            # test ends in `tx.rollback()`: the check never ran. Sol's O1
            # refutation (finding F7) named that exact line as the proof
            # that a cross-practice successor was accepted. The shortcut is
            # gone, and `SET CONSTRAINTS ALL IMMEDIATE` below makes the
            # deferred check happen HERE rather than at a COMMIT this test
            # deliberately never reaches.
            second_id = f"art_{uuid.uuid4().hex[:20]}"
            await conn.execute(
                "UPDATE garuda_practice_artifacts "
                "SET superseded_at = clock_timestamp(), superseded_by = $2 "
                "WHERE artifact_id = $1",
                first_id,
                second_id,
            )
            await _insert_artifact(conn, artifact_id=second_id, practice_id=practice_id)
            await conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            row = await conn.fetchrow(
                "SELECT superseded_at, superseded_by FROM garuda_practice_artifacts "
                "WHERE artifact_id = $1",
                first_id,
            )
            assert row["superseded_at"] is not None
            assert row["superseded_by"] == second_id

            # The successor is now the practice's one live row: the partial
            # unique index counts exactly one, and it is the new id. (The
            # older assertion here inserted a THIRD live row for the same
            # practice, which only worked while the successor belonged to
            # someone else -- with the successor on this practice, that
            # insert is the two-live-rows case `test_a_second_live_insert_
            # for_the_same_practice_is_refused` already owns.)
            live = await conn.fetch(
                "SELECT artifact_id FROM garuda_practice_artifacts "
                " WHERE practice_id = $1 AND superseded_at IS NULL",
                practice_id,
            )
            assert [r["artifact_id"] for r in live] == [second_id]
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_a_successor_from_another_practice_is_refused(self, conn) -> None:
        """Sol O1 finding F7 (BLOCKER, 2026-09-11), cured by the composite
        deferred FK `(superseded_by, practice_id) -> (artifact_id,
        practice_id)`.

        Before the cure every structure in 313 waved this through: the
        single-column FK resolved (the target row exists), the guard
        trigger checked only that OLD.practice_id did not CHANGE, and the
        partial unique index counts live rows and so cannot see it. The
        result was a Delivered practice with ZERO live artifacts and a
        `garuda_practices.artifact_id` still naming the row just retired --
        a customer GET answering 404 forever with no error anywhere.

        The check is deferred, so it lands at constraint-check time and not
        at statement time: `SET CONSTRAINTS ALL IMMEDIATE` is what forces
        it here instead of at a COMMIT this test never reaches. A caller
        who never asks for it gets the same refusal at COMMIT.
        """
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            first_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=first_id, practice_id=practice_id)

            other_practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            stranger_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(
                conn, artifact_id=stranger_id, practice_id=other_practice_id
            )

            # The UPDATE itself is accepted -- the guard trigger has no
            # opinion on WHERE superseded_by points, and cannot have one:
            # the successor row does not exist yet in the real flow.
            await conn.execute(
                "UPDATE garuda_practice_artifacts "
                "SET superseded_at = clock_timestamp(), superseded_by = $2 "
                "WHERE artifact_id = $1",
                first_id,
                stranger_id,
            )
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_the_pair_is_immutable_once_set_a_second_supersession_is_refused(
        self, conn
    ) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            artifact_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=artifact_id, practice_id=practice_id)
            other_practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            other_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=other_id, practice_id=other_practice_id)
            await conn.execute(
                "UPDATE garuda_practice_artifacts "
                "SET superseded_at = clock_timestamp(), superseded_by = $2 "
                "WHERE artifact_id = $1",
                artifact_id,
                other_id,
            )
            third_practice_id = await _seed_practice(conn, suffix=uuid.uuid4().hex[:12])
            third_id = f"art_{uuid.uuid4().hex[:20]}"
            await _insert_artifact(conn, artifact_id=third_id, practice_id=third_practice_id)
            with pytest.raises(
                asyncpg.PostgresError,
                match="superseded_at/superseded_by are immutable once set",
            ):
                await conn.execute(
                    "UPDATE garuda_practice_artifacts "
                    "SET superseded_at = clock_timestamp(), superseded_by = $2 "
                    "WHERE artifact_id = $1",
                    artifact_id,
                    third_id,
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


@pytest.mark.asyncio
async def test_the_next_file_can_still_unwind_this_database() -> None:
    """The defect gate-6287c measured, reproduced on one database in one
    process: run this file's fixture lifecycle (seed the TEST/GARUDA_DOCUMENT
    policy, tear down), then do what every visa_engine file does before
    rolling 264 back -- `unwind_garuda_voa_retention_fk`, whose reverse walk
    reaches 285's rollback, which re-narrows the `policy_scope` CHECK. With
    the earlier teardown (CLOSE the row, leave it) this raised
    `CheckViolationError: visa_decision_retention_policies_policy_scope_check
    ... violated by some row`; with a rolled-back seed it passes. `restore`
    then puts the MIGRATION STACK back, in a `finally` so a failed assertion
    cannot leave the next file without 281..313.

    What "back" does and does not mean, stated because round O5 caught the
    docstring overclaiming: the shared unwind/restore pair is not
    state-preserving for OTHER fixtures' committed rows -- 281's rollback
    drops the `policy_scope` column and restore re-adds it with its default,
    so a closed GARUDA_ORDER or GARUDA_MAGIC_LINK row another file left
    behind comes back as VISA_DECISION. That is the mechanism's property,
    identical for the three visa_engine consumers that call it, and this
    test adds nothing to it; it is recorded here, not fixed here.

    Deliberately NOT using the `conn` fixture: the point is the state AFTER
    its teardown, and this test must own the connection to observe it. It
    enters the fixture's own seeding context, not a copy, so it measures the
    shipped code path.

    Premise, asserted rather than assumed: the database carries no
    TEST/GARUDA_DOCUMENT row before this test. Nothing else on this database
    seeds that scope today, and a worker's clone starts empty -- but a
    worker reuses one clone across files, so this is a pollution tripwire,
    not a law. On a database dirtied by an OLDER run of this file the rows
    cannot be removed (append-only), and this test says so instead of
    blaming the cure.
    """
    from backend.tests.services.visa_engine.conftest import (
        restore_garuda_voa_retention_fk,
        unwind_garuda_voa_retention_fk,
    )

    if (bad := _forbidden((TEST_DSN or "").split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1])):
        pytest.fail(f"refusing to unwind migrations — TEST_DATABASE_URL names a real database ({bad!r}).")
    connection = await asyncpg.connect(TEST_DSN)
    try:
        forward, _ = split_migration_sql(MIGRATION.read_text())
        await connection.execute(forward)
        pre_existing = await connection.fetchval(
            "SELECT count(*) FROM public.visa_decision_retention_policies "
            "WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'"
        )
        assert pre_existing == 0, (
            f"{pre_existing} TEST/GARUDA_DOCUMENT row(s) pre-date this test on this database "
            "(an older run of this file left them; they are append-only and cannot be removed) "
            "-- this reproduction needs a fresh database, as CI provides"
        )

        async with _seeded_test_retention_policy(connection):
            assert await connection.fetchval(
                "SELECT count(*) FROM public.visa_decision_retention_policies "
                "WHERE environment = 'TEST' AND policy_scope = 'GARUDA_DOCUMENT'"
            ) == 1

        # What the next file does. Before the cure: CheckViolationError here.
        try:
            unwound = await unwind_garuda_voa_retention_fk(connection)
            assert unwound, "unwind found nothing to roll back — 313 was not applied, so this proved nothing"
            assert await connection.fetchval("SELECT to_regclass('public.garuda_practice_artifacts')") is None
        finally:
            await restore_garuda_voa_retention_fk(connection)
        assert await connection.fetchval("SELECT to_regclass('public.garuda_practice_artifacts')") is not None
    finally:
        await connection.close()

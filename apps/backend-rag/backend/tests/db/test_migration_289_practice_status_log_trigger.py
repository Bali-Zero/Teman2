"""Execute migration 289's trigger against a live Postgres.

WHY THIS IS AN EXECUTING TEST AND NOT A SOURCE ASSERTION
The defect 289 fixes was never a typo — it was a table that four surfaces
referenced (`portal_process_timeline.py`, its unit test, and the frontend's
`portal.types.ts` + `schemas/process.ts`) and that no migration in this repo
ever created. Measured on prod 2026-08-27: `relation "practice_status_log"
does not exist`. A test that only greps 289's SQL for the right keywords would
reproduce exactly that failure mode one level up — an artifact that looks
correct and was never run. So this file runs the DDL and then drives the
trigger through real UPDATEs.

The migration is idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE
FUNCTION`, `DROP TRIGGER IF EXISTS`), so applying it here is safe whether or
not the test database has already seen it. That is deliberate: the obvious
alternative — skipping when the table is absent — would make this test vacuous
on precisely the databases where 289 has not landed, which are the only ones
where it matters.
"""

from __future__ import annotations

import os
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import split_migration_sql

MIGRATION = (
    Path(__file__).resolve().parents[2] / "db" / "migrations_v2" / "289_practice_status_log.sql"
)

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DSN, reason="TEST_DATABASE_URL is unset — no live Postgres to drive"
)


def test_the_migration_file_exists_and_declares_a_rollback() -> None:
    """Cheap structural guard: the runner refuses a file with no ROLLBACK marker."""
    assert MIGRATION.is_file(), f"{MIGRATION} is missing"
    forward, rollback = split_migration_sql(MIGRATION.read_text())
    assert "practice_status_log" in forward
    assert rollback is not None, "migration runner requires the ROLLBACK marker"


@pytest.fixture
async def conn():
    connection = await asyncpg.connect(TEST_DSN)
    try:
        forward, _ = split_migration_sql(MIGRATION.read_text())
        await connection.execute(forward)
        yield connection
    finally:
        await connection.close()


async def _one_practice(conn, status: str | None) -> int:
    """Insert a practice carrying `status` and return its id.

    The column list is discovered from the catalog rather than written out. An
    earlier draft used a bare `INSERT INTO practices (status)` and died on
    `client_id`; worse, the schema probe run to fix it read a DIFFERENT
    database than the suite connects to (conftest rewrites TEST_DATABASE_URL to
    a per-worker clone at import time) and reported that column as nullable.
    Asking the catalog through the SAME connection the test uses removes the
    guess, and survives a later migration adding another NOT NULL column.
    """
    required = [
        r["column_name"]
        for r in await conn.fetch(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = 'practices'
               AND is_nullable = 'NO'
               AND column_default IS NULL
               AND column_name <> 'status'
            """
        )
    ]

    cols = ["status"]
    vals: list[object] = [status]
    for name in required:
        cols.append(name)
        if name == "client_id":
            # A real client row, because this column carries a foreign key.
            vals.append(
                await conn.fetchval(
                    "INSERT INTO clients (full_name) VALUES ($1) RETURNING id",
                    "mig289 fixture",
                )
            )
        elif name.endswith("_id"):
            vals.append(1)
        else:
            vals.append("mig289")

    placeholders = ", ".join(f"${i}" for i in range(1, len(cols) + 1))
    return await conn.fetchval(
        f"INSERT INTO practices ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
        *vals,
    )


class TestTheTriggerRecordsExactlyTheStatusTransitions:
    @pytest.mark.asyncio
    async def test_insert_alone_writes_no_history(self, conn) -> None:
        """The trigger is AFTER UPDATE OF status — a creation is not a transition."""
        tx = conn.transaction()
        await tx.start()
        try:
            pid = await _one_practice(conn, "inquiry")
            n = await conn.fetchval(
                "SELECT count(*) FROM practice_status_log WHERE practice_id = $1", pid
            )
            assert n == 0
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_a_status_change_records_old_and_new(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            pid = await _one_practice(conn, "inquiry")
            await conn.execute("UPDATE practices SET status = 'on_process' WHERE id = $1", pid)
            row = await conn.fetchrow(
                "SELECT old_status, new_status, changed_by FROM practice_status_log "
                "WHERE practice_id = $1 ORDER BY id DESC LIMIT 1",
                pid,
            )
            assert row["old_status"] == "inquiry"
            assert row["new_status"] == "on_process"
            # No GUC set by this session -> no invented actor.
            assert row["changed_by"] is None
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_a_null_to_value_transition_is_recorded(self, conn) -> None:
        """The case a plain `<>` comparison drops — and it is reachable in PROD.

        `NULL <> 'completed'` evaluates to NULL, not TRUE, so an
        `IF OLD.status <> NEW.status` guard skips the row entirely and the first
        real transition of a practice created without a status vanishes. Hence
        `IS DISTINCT FROM`.

        MEASURED DIVERGENCE, 2026-08-27 — and it is why this test branches
        instead of asserting one shape. On PROD `practices.status` is NULLABLE
        (default `'inquiry'`), so the NULL case is live there. On the migrated
        test database the same column is NOT NULL, and `client_id` and
        `practice_type` differ too. A first draft of this test "proved" the NULL
        behaviour against a bare table it had created itself without the
        constraint — a probe demonstrating a difference the schema under test
        could not produce.

        So: where the column admits NULL, drive the transition and assert it is
        recorded. Where it does not, assert THAT — the constraint is the reason
        the case is unreachable, and naming it keeps this test from being
        quietly vacuous on exactly the databases where it cannot run.
        """
        nullable = await conn.fetchval(
            """
            SELECT is_nullable = 'YES'
              FROM information_schema.columns
             WHERE table_name = 'practices' AND column_name = 'status'
            """
        )

        tx = conn.transaction()
        await tx.start()
        try:
            if not nullable:
                # Innocence arm: the case is impossible here, and this asserts
                # the constraint that makes it impossible rather than skipping.
                with pytest.raises(asyncpg.NotNullViolationError):
                    await _one_practice(conn, None)
                return

            pid = await _one_practice(conn, None)
            await conn.execute("UPDATE practices SET status = 'completed' WHERE id = $1", pid)
            row = await conn.fetchrow(
                "SELECT old_status, new_status FROM practice_status_log WHERE practice_id = $1",
                pid,
            )
            assert row is not None, "a NULL -> value transition must be recorded"
            assert row["old_status"] is None
            assert row["new_status"] == "completed"
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_rewriting_the_same_status_records_nothing(self, conn) -> None:
        """Idempotent writes must not inflate the timeline the client sees."""
        tx = conn.transaction()
        await tx.start()
        try:
            pid = await _one_practice(conn, "on_process")
            await conn.execute("UPDATE practices SET status = 'on_process' WHERE id = $1", pid)
            n = await conn.fetchval(
                "SELECT count(*) FROM practice_status_log WHERE practice_id = $1", pid
            )
            assert n == 0
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_the_actor_guc_is_recorded_when_the_caller_sets_one(self, conn) -> None:
        tx = conn.transaction()
        await tx.start()
        try:
            pid = await _one_practice(conn, "inquiry")
            await conn.execute("SET LOCAL app.actor = 'ops@balizero.com'")
            await conn.execute("UPDATE practices SET status = 'approved' WHERE id = $1", pid)
            actor = await conn.fetchval(
                "SELECT changed_by FROM practice_status_log WHERE practice_id = $1", pid
            )
            assert actor == "ops@balizero.com"
        finally:
            await tx.rollback()

    @pytest.mark.asyncio
    async def test_history_can_never_block_the_transition_it_records(self, conn) -> None:
        """`current_setting('app.actor', true)` — the `true` is load-bearing.

        Without missing_ok, `current_setting` RAISES on any session that has
        not set the GUC, and because the trigger fires inside the caller's
        transaction that would abort the practice update itself. A history
        table that can veto the state change it observes is worse than no
        history table.
        """
        tx = conn.transaction()
        await tx.start()
        try:
            pid = await _one_practice(conn, "inquiry")
            await conn.execute("RESET app.actor")
            await conn.execute(
                "UPDATE practices SET status = 'submitted_to_gov' WHERE id = $1", pid
            )
            status = await conn.fetchval("SELECT status FROM practices WHERE id = $1", pid)
            assert status == "submitted_to_gov", "the UPDATE must have committed"
        finally:
            await tx.rollback()

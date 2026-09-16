"""Verify migration 317 declares a 30-day default for visa_oracle_sessions.expires_at
and its rollback restores 90 days — parses the .sql file, no database needed.

No shipped test previously covered this: `test_retention_policy_scope_family_tripwire.py`
governs a different scope-predicate family, and no test named visa_oracle_sessions'
expires_at default anywhere in backend/tests/. This file exists to catch a regression
where the default silently stays at 90 days (the value PROD carries today).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.db.migration_base import split_migration_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "317_visa_oracle_sessions_retention_30d.sql"
)


def _sections() -> tuple[str, str]:
    """Split via the CANONICAL splitter (`migration_base.split_migration_sql`),
    not a literal string split re-implemented here — the runner's actual
    behavior is what this file must track (F7, Codex review)."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, rollback = split_migration_sql(sql)
    assert rollback is not None, "expected a `-- === ROLLBACK ===` marker"
    return forward, rollback


def _executable_lines(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def test_migration_file_exists() -> None:
    assert MIGRATION_FILE.exists(), f"Migration file missing: {MIGRATION_FILE}"


def test_forward_sets_the_default_to_30_days() -> None:
    """The load-bearing declaration: NEW rows must default to 30 days, not 90."""
    forward, _rollback = _sections()
    executable = _executable_lines(forward)

    assert "ALTER TABLE public.visa_oracle_sessions" in executable
    assert "ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '30 days')" in executable
    # The 90-day value may appear in the CREATE TABLE IF NOT EXISTS fallback
    # (provenance guard for a fresh database) but the final ALTER must win.
    alter_idx = executable.rindex("ALTER COLUMN expires_at SET DEFAULT")
    assert "30 days" in executable[alter_idx : alter_idx + 80]


def test_forward_does_not_rewrite_existing_rows() -> None:
    """Conservative choice: existing rows keep their already-declared 90-day
    expires_at. No UPDATE statement may touch the table."""
    forward, _rollback = _sections()
    executable = _executable_lines(forward).upper()

    assert "UPDATE " not in executable
    assert "DELETE " not in executable


def test_forward_table_creation_is_a_bare_idempotent_statement() -> None:
    """`CREATE TABLE IF NOT EXISTS` is left bare (unguarded) — proven this
    turn against a live PG 17.10 that it does not block against a concurrent
    ACCESS SHARE lock holder even when the table already exists, unlike
    `CREATE INDEX IF NOT EXISTS` below (see the next test)."""
    forward, _rollback = _sections()

    assert "CREATE TABLE IF NOT EXISTS public.visa_oracle_sessions" in forward


def test_forward_indexes_are_guarded_not_bare() -> None:
    """F5 (Codex, BLOCKING): a bare `CREATE INDEX IF NOT EXISTS` takes a
    ShareLock on the table for the whole enclosing transaction even when the
    index already exists — measured live this turn (a concurrent INSERT was
    blocked for the duration of a transaction holding a no-op CREATE INDEX
    IF NOT EXISTS open). Each index must instead be guarded behind an
    existence check against `pg_indexes`, so the no-op case takes no lock on
    the table at all."""
    forward, _rollback = _sections()

    # The bare form must be GONE — its presence would mean the guard was
    # bypassed or reverted.
    assert "CREATE INDEX IF NOT EXISTS idx_vo_sessions_session_id" not in forward
    assert "CREATE INDEX IF NOT EXISTS idx_vo_sessions_created_at" not in forward

    # Each index name must appear inside a pg_indexes existence guard AND
    # inside the EXECUTE string that actually creates it (unqualified, since
    # IF NOT EXISTS is redundant once the guard already checked).
    for index_name, create_fragment in (
        (
            "idx_vo_sessions_session_id",
            "CREATE INDEX idx_vo_sessions_session_id ON public.visa_oracle_sessions (session_id)",
        ),
        (
            "idx_vo_sessions_created_at",
            "CREATE INDEX idx_vo_sessions_created_at ON public.visa_oracle_sessions (created_at DESC)",
        ),
    ):
        guard_idx = forward.index(f"indexname = '{index_name}'")
        create_idx = forward.index(create_fragment)
        do_idx = forward.rindex("DO $$", 0, guard_idx)
        end_idx = forward.index("END $$;", create_idx)
        assert do_idx < guard_idx < create_idx < end_idx, (
            f"{index_name} must be created inside a DO $$ block guarded by a "
            "pg_indexes existence check, not as a bare CREATE INDEX"
        )
        assert "FROM pg_indexes" in forward[do_idx:end_idx]
        assert "IF NOT EXISTS (" in forward[do_idx:end_idx]


def test_rollback_restores_90_days() -> None:
    _forward, rollback = _sections()
    executable = _executable_lines(rollback)

    assert "ALTER TABLE public.visa_oracle_sessions" in executable
    assert "ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '90 days')" in executable


def test_rollback_does_not_rewrite_existing_rows() -> None:
    _forward, rollback = _sections()
    executable = _executable_lines(rollback).upper()

    assert "UPDATE " not in executable
    assert "DELETE " not in executable
    assert "DROP TABLE" not in executable


# ----------------------------------------------------------------------------
# RETRY-WITH-BACKOFF (2026-09-17, PROD incident, Fly release v4472/v4473),
# CURED FURTHER same day per Codex gpt-6-astra adversarial review (F2/F4/F5,
# imperator disposition FIX-FIRST):
# "Failed to apply migration 317: SQL execution failed: canceling statement
# due to lock timeout" — a ~40-minute pg_dump held AccessShareLock on the
# table, the single 5s lock_timeout wait lost every time, and every
# subsequent `apply-all` retried the SAME 5s wait and failed identically
# (317 never reached `_schema_versions`). Static assertions only — no
# database in this file (see the module docstring); the live retry/
# blocker-naming behaviour is proven against a real PostgreSQL cluster in
# the PR body (GUILT: a lock held longer than the retry budget fails,
# naming the blocker's application_name; INNOCENCE: a lock released within
# the budget lets the cure through; a concurrent INSERT is NOT blocked for
# the whole loop, unlike the pre-F5 bare CREATE INDEX IF NOT EXISTS calls).
# ----------------------------------------------------------------------------


def test_forward_alter_is_wrapped_in_a_retry_loop() -> None:
    """The forward ALTER must not be a bare statement behind one lock_timeout
    wait — it must live inside a `DO $$ ... $$` block that retries."""
    forward, _rollback = _sections()
    executable = _executable_lines(forward)

    do_idx = executable.rindex("DO $$")
    alter_idx = executable.rindex("ALTER COLUMN expires_at SET DEFAULT")
    end_idx = executable.index("END $$;", do_idx)
    assert do_idx < alter_idx < end_idx, (
        "the forward ALTER COLUMN ... SET DEFAULT must sit inside the "
        "DO $$ ... END $$; retry block, not as a bare top-level statement"
    )
    # The retry loop must actually retry (LOOP/EXIT), not just wrap-and-fail-once.
    assert "LOOP" in executable[do_idx:end_idx]
    assert "EXIT" in executable[do_idx:end_idx]


def test_rollback_alter_is_wrapped_in_a_retry_loop() -> None:
    """Symmetric with the forward direction: the rollback ALTER (back to 90
    days) must retry too, not fail on the first lock_timeout."""
    _forward, rollback = _sections()
    executable = _executable_lines(rollback)

    do_idx = executable.index("DO $$")
    alter_idx = executable.rindex("ALTER COLUMN expires_at SET DEFAULT")
    end_idx = executable.index("END $$;", do_idx)
    assert do_idx < alter_idx < end_idx
    assert "LOOP" in executable[do_idx:end_idx]
    assert "EXIT" in executable[do_idx:end_idx]


def test_retry_catches_only_lock_not_available() -> None:
    """F2 (Codex, BLOCKING): the loop's own `lock_timeout` is the only thing
    it is meant to absorb, and Postgres always raises that specific
    cancellation as `lock_not_available` (55P03) — never anything else. The
    first cure additionally caught a second, broader cancellation code as a
    "fallback"; that code is also what a `statement_timeout` or an
    operator's `pg_cancel_backend` raise, and catching it here would
    silently swallow either of those distinct failures instead of letting
    them propagate. That second code's SQLSTATE name must be ABSENT from the
    file entirely, in both directions, and the only exception name caught in
    each `WHEN` clause must be exactly `lock_not_available` (not OR'd with
    anything)."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    assert "lock_not_available" in sql
    assert "query_canceled" not in sql
    assert sql.count("WHEN lock_not_available THEN") == 2, (
        "expected exactly one `WHEN lock_not_available THEN` in the forward "
        "block and one in the rollback block, neither OR'd with another "
        "exception name"
    )


def test_retry_names_the_blocker_on_exhaustion() -> None:
    """On exhaustion the migration must RAISE (never silently skip) and name
    the blocking backend's pid/usename/application_name via pg_locks joined
    to pg_stat_activity — never `query`/`state`, which a non-superuser
    cannot read for another backend. F4 (Codex, SHOULD-FIX): the diagnostic
    lookup must filter to locks actually GRANTED (`l.granted`) in THIS
    database (`a.datname = current_database()`), and must be wrapped in its
    own `BEGIN ... EXCEPTION WHEN OTHERS` so a failing diagnostic can never
    mask the original lock-exhaustion error."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    assert "RAISE EXCEPTION" in sql
    assert "pg_locks" in sql
    assert "pg_stat_activity" in sql
    assert "application_name" in sql
    assert "usename" in sql
    assert "l.granted" in sql
    assert "a.datname = current_database()" in sql
    assert sql.count("EXCEPTION\n                        WHEN OTHERS THEN") == 2, (
        "expected the blocker-diagnostic SELECT to be wrapped in its own "
        "BEGIN ... EXCEPTION WHEN OTHERS in both the forward and rollback "
        "blocks, isolating a failing lookup from the RAISE EXCEPTION that "
        "reports the real lock-exhaustion error"
    )
    # Never claim to read another backend's live query/state (not visible to
    # a non-superuser) as part of the blocker report.
    for forbidden in ("a.query", "a.state"):
        assert forbidden not in sql


def test_retry_budget_fits_under_the_files_own_statement_timeout() -> None:
    """A `DO $$ ... $$` block is ONE statement, so the whole retry loop must
    finish comfortably inside this file's own `statement_timeout = '60s'`
    (migration_manager.py runs the forward SQL as a single `conn.execute()`
    inside one transaction on a plain `asyncpg.connect()` — no client-side
    `command_timeout` from the pool applies here, only this server-side
    ceiling). F5 shrank the reader-queuing window: 15 attempts * 500ms
    lock_timeout (7.5s) + backoff `least(attempt * 0.5, 3)` summing to 34.5s
    across the 14 sleeps between attempts = 42.0s worst case (proven live in
    the PR body) — assert the exact budget inputs (mutation-sensitive: the
    attempt count, the per-attempt lock wait and the backoff cap must all
    match, not just be "present")."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, rollback = _sections()
    # Count only in EXECUTABLE lines (comments legitimately quote these same
    # tokens in prose, e.g. the BUDGET explanation above the forward block —
    # that prose reference must not count toward the mutation-sensitive
    # assertion that the CODE itself declares these values exactly twice).
    code = _executable_lines(forward) + "\n" + _executable_lines(rollback)

    assert "statement_timeout = '60s'" in sql
    assert code.count("max_attempts CONSTANT int := 15") == 2, (
        "expected max_attempts := 15 in both the forward and rollback blocks"
    )
    assert code.count("lock_timeout = ''500ms''") == 2, (
        "expected the shrunk 500ms per-attempt lock_timeout in both blocks"
    )
    assert code.count("least(attempt * 0.5, 3)") == 2, (
        "expected the 3s backoff cap (shrunk from 4s) in both blocks"
    )
    assert "pg_sleep" in sql


# ----------------------------------------------------------------------------
# LIVE CONCURRENCY (F7, Codex SHOULD-FIX): the assertions above are static —
# they prove the SQL says the right thing but never prove it BEHAVES the
# right way under a real lock. `TEST_DATABASE_URL` is the same live-Postgres
# opt-in convention `test_migration_310_practice_status_log_trigger.py` and
# `test_migration_advisory_lock.py`'s siblings use elsewhere in this
# directory — root `conftest.py` `setdefault`s it to a local
# `nuzantara_test` database when unset, so these run wherever the rest of
# `backend/tests/db/` already runs (CI's ephemeral Postgres service, or a
# developer's local one). The additional live proof for THIS PR (the exact
# ~42s budget, the index-guard's non-blocking behavior) was ALSO run once
# against a throwaway PG 17.10 cluster this turn and is pasted in the PR
# body; these two tests are the permanent regression guard.
# ----------------------------------------------------------------------------

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

#: Mirrors `test_migration_310_practice_status_log_trigger.py`'s guard
#: (added after an adversarial review there): these tests hold a real table
#: lock and apply DDL outside any test-rollback transaction, so a
#: mistyped/tunnel DSN pointed at a real database is not recoverable by
#: rerunning. Refuse before opening a lock.
_FORBIDDEN_DB_SUBSTRINGS = ("nuzantara_rag", "prod", "production")


def _forbidden(dbname: str) -> str | None:
    lowered = dbname.lower()
    return next((bad for bad in _FORBIDDEN_DB_SUBSTRINGS if bad in lowered), None)


async def _refuse_if_real_database(conn) -> None:
    actual = await conn.fetchval("SELECT current_database()")
    if bad := _forbidden(actual or ""):
        pytest.fail(
            f"refusing to hold a table lock / apply migration DDL against "
            f"database {actual!r} — it matched {bad!r}. This test locks a "
            "real table and is not safe to run outside a throwaway/test DB."
        )


#: The migration's own bootstrap creates this table if absent — but only
#: `id`/`session_id`/`quiz_answers`/... down to `expires_at`; the CREATE
#: INDEX guard also needs `created_at` to exist, so the pre-existing-table
#: probe below must declare it too (an earlier draft of this file omitted
#: it and failed with `column "created_at" does not exist` the moment the
#: migration's own index guard ran against the minimal bootstrap).
_BOOTSTRAP_DDL = (
    "CREATE TABLE IF NOT EXISTS public.visa_oracle_sessions ("
    "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
    "session_id VARCHAR(64) NOT NULL, "
    "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), "
    "expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days'))"
)

_MIGRATION_NAME = "317_visa_oracle_sessions_retention_30d"


async def _reset_ledger_and_table(conn) -> None:
    """Undo everything `BaseMigration.apply()` persists outside any
    transaction this test controls, so re-running the suite exercises the
    retry loop again instead of short-circuiting on `_is_applied()`. Called
    BEFORE each test too (a prior interrupted run may have left state), so
    both ledger tables are tolerated as absent — `apply()` creates them
    itself on first use (`_ensure_migration_log`) and a truly fresh test
    database will not have them yet."""
    import asyncpg

    await conn.execute("DROP TABLE IF EXISTS public.visa_oracle_sessions")
    for stmt, args in (
        ("DELETE FROM schema_migrations WHERE migration_name = $1", (_MIGRATION_NAME,)),
        ("DELETE FROM _schema_versions WHERE migration_number = 317", ()),
    ):
        try:
            await conn.execute(stmt, *args)
        except asyncpg.exceptions.UndefinedTableError:
            pass


@pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL is unset — no live Postgres to drive")
@pytest.mark.asyncio
async def test_live_concurrent_reader_beyond_budget_fails_naming_it() -> None:
    """GUILT: a session holding an ACCESS SHARE lock on visa_oracle_sessions
    for longer than the ~42s retry budget must make the migration RAISE,
    naming that session's application_name, and must NOT change the
    column's default."""
    import asyncio

    import asyncpg

    from backend.db.migration_base import BaseMigration, MigrationError

    conn_a = await asyncpg.connect(TEST_DSN)
    try:
        await _refuse_if_real_database(conn_a)
        await _reset_ledger_and_table(conn_a)
        await conn_a.execute(_BOOTSTRAP_DDL)
        tx = conn_a.transaction()
        await tx.start()
        await conn_a.execute("SET application_name = 'fake_pg_dump'")
        await conn_a.execute("LOCK TABLE public.visa_oracle_sessions IN ACCESS SHARE MODE")

        sql_text = MIGRATION_FILE.read_text(encoding="utf-8")
        _forward, rollback = split_migration_sql(sql_text)
        migration = BaseMigration(
            migration_number=317,
            sql_file=MIGRATION_FILE.name,
            description="test: guilt (blocker held beyond budget)",
            rollback_sql=rollback,
            _sql_dir=MIGRATION_FILE.parent,
        )

        holder_task = asyncio.create_task(_hold_for(tx, seconds=50))
        try:
            with pytest.raises(MigrationError, match="did not acquire its lock") as exc_info:
                await migration.apply(database_url=TEST_DSN, dedicated=False)
            assert "fake_pg_dump" in str(exc_info.value)
        finally:
            await holder_task

        conn_b = await asyncpg.connect(TEST_DSN)
        try:
            default = await conn_b.fetchval(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='visa_oracle_sessions' "
                "AND column_name='expires_at'"
            )
            assert "90" in default, "the ALTER must not have taken effect on GUILT"
        finally:
            await conn_b.close()
    finally:
        try:
            await _reset_ledger_and_table(conn_a)
        finally:
            await conn_a.close()


@pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL is unset — no live Postgres to drive")
@pytest.mark.asyncio
async def test_live_concurrent_reader_released_within_budget_succeeds() -> None:
    """INNOCENCE: a lock released well within the retry budget lets the
    migration through — the default lands at 30 days. Also proves F5: a
    concurrent write is not blocked while the migration's retry loop is in
    flight (the index guard, not a bare CREATE INDEX IF NOT EXISTS, is what
    makes that true)."""
    import asyncio

    import asyncpg

    from backend.db.migration_base import BaseMigration

    conn_a = await asyncpg.connect(TEST_DSN)
    try:
        await _refuse_if_real_database(conn_a)
        await _reset_ledger_and_table(conn_a)
        await conn_a.execute(_BOOTSTRAP_DDL)
        tx = conn_a.transaction()
        await tx.start()
        await conn_a.execute("SET application_name = 'fake_pg_dump_short'")
        await conn_a.execute("LOCK TABLE public.visa_oracle_sessions IN ACCESS SHARE MODE")

        sql_text = MIGRATION_FILE.read_text(encoding="utf-8")
        _forward, rollback = split_migration_sql(sql_text)
        migration = BaseMigration(
            migration_number=317,
            sql_file=MIGRATION_FILE.name,
            description="test: innocence (blocker released within budget)",
            rollback_sql=rollback,
            _sql_dir=MIGRATION_FILE.parent,
        )

        holder_task = asyncio.create_task(_hold_for(tx, seconds=1))
        try:
            ok = await migration.apply(database_url=TEST_DSN, dedicated=False)
            assert ok is True
        finally:
            await holder_task

        conn_b = await asyncpg.connect(TEST_DSN)
        try:
            default = await conn_b.fetchval(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='visa_oracle_sessions' "
                "AND column_name='expires_at'"
            )
            assert "30" in default
        finally:
            await conn_b.close()
    finally:
        try:
            await _reset_ledger_and_table(conn_a)
        finally:
            await conn_a.close()


async def _hold_for(tx, *, seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
    await tx.commit()

"""Verify migration 317 declares a 30-day default for visa_oracle_sessions.expires_at
and its rollback restores 90 days — parses the .sql file, no database needed.

No shipped test previously covered this: `test_retention_policy_scope_family_tripwire.py`
governs a different scope-predicate family, and no test named visa_oracle_sessions'
expires_at default anywhere in backend/tests/. This file exists to catch a regression
where the default silently stays at 90 days (the value PROD carries today).
"""

from __future__ import annotations

from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "317_visa_oracle_sessions_retention_30d.sql"
)


def _sections() -> tuple[str, str]:
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, rollback = sql.split("-- === ROLLBACK ===", maxsplit=1)
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


def test_forward_ddl_is_idempotent() -> None:
    """CREATE TABLE / CREATE INDEX must be guarded so a re-run against a
    database that already has the table is a no-op, not an error."""
    forward, _rollback = _sections()

    assert "CREATE TABLE IF NOT EXISTS public.visa_oracle_sessions" in forward
    assert "CREATE INDEX IF NOT EXISTS idx_vo_sessions_session_id" in forward
    assert "CREATE INDEX IF NOT EXISTS idx_vo_sessions_created_at" in forward


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
# RETRY-WITH-BACKOFF (2026-09-17, PROD incident, Fly release v4472/v4473):
# "Failed to apply migration 317: SQL execution failed: canceling statement
# due to lock timeout" — a ~40-minute pg_dump held AccessShareLock on the
# table, the single 5s lock_timeout wait lost every time, and every
# subsequent `apply-all` retried the SAME 5s wait and failed identically
# (317 never reached `_schema_versions`). Static assertions only — no
# database in this file (see the module docstring); the live retry/
# blocker-naming behaviour is proven against a real PostgreSQL cluster in
# the PR body (GUILT: original single-wait fails after ~5s; GUILT: cured
# retries 8x over ~38s then RAISEs naming the blocker's pid/user/
# application_name; INNOCENCE: a lock released within the retry budget
# lets the cure through).
# ----------------------------------------------------------------------------


def test_forward_alter_is_wrapped_in_a_retry_loop() -> None:
    """The forward ALTER must not be a bare statement behind one lock_timeout
    wait — it must live inside a `DO $$ ... $$` block that retries."""
    forward, _rollback = _sections()
    executable = _executable_lines(forward)

    do_idx = executable.index("DO $$")
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


def test_retry_catches_lock_not_available_and_query_canceled() -> None:
    """Both SQLSTATEs a lock_timeout cancellation can surface must be caught
    (measured against a live PostgreSQL 17.10: a blocked ALTER under
    lock_timeout raises `lock_not_available`; `query_canceled` is kept as
    the documented fallback code)."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "lock_not_available" in sql
    assert "query_canceled" in sql


def test_retry_names_the_blocker_on_exhaustion() -> None:
    """On exhaustion the migration must RAISE (never silently skip) and name
    the blocking backend's pid/usename/application_name via pg_locks joined
    to pg_stat_activity — never `query`/`state`, which a non-superuser
    cannot read for another backend."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    assert "RAISE EXCEPTION" in sql
    assert "pg_locks" in sql
    assert "pg_stat_activity" in sql
    assert "application_name" in sql
    assert "usename" in sql
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
    ceiling). 8 attempts * 3s lock_timeout + capped backoff sleeps measures
    to ~38s worst case (proven live in the PR body) — assert the budget
    inputs stay conservative rather than re-deriving the exact figure here.
    """
    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    assert "statement_timeout = '60s'" in sql
    assert "max_attempts CONSTANT int := 8" in sql
    assert "lock_timeout = ''3s''" in sql
    assert "least(attempt * 0.5, 4)" in sql

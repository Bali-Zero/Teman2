"""Contract tests for migration 244 compliance_alerts runtime grants."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import split_migration_sql
from backend.db.migration_manager import _extract_rollback_sql

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "244_compliance_alerts_runtime_grants.sql"
)

COMPLIANCE_ALERTS_MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations_v2"
    / "114_compliance_alerts.sql"
)

WRITE_OBJECTS = ("public.compliance_alerts",)

RUNTIME_ROLE = "backend_rag_v2"


def _forward(sql: str) -> str:
    """Return the forward section applied by the migration runner."""
    return sql.split("-- === ROLLBACK ===", maxsplit=1)[0]


def test_migration_244_file_exists() -> None:
    assert MIGRATION_FILE.exists()


def test_migration_244_has_rollback_marker() -> None:
    sql = MIGRATION_FILE.read_text()

    assert "-- === ROLLBACK ===" in sql
    assert _extract_rollback_sql(sql) is not None


def test_migration_244_targets_runtime_role_conditionally() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "runtime_role constant text := 'backend_rag_v2'" in forward
    assert "pg_roles WHERE rolname = runtime_role" in forward
    assert "GRANT USAGE ON SCHEMA public TO backend_rag_v2" in forward


def test_migration_244_is_safe_when_object_is_missing() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "to_regclass(object_name)" in forward
    assert "IF object_reg IS NULL THEN" in forward
    assert "CONTINUE;" in forward


def test_migration_244_checks_existing_privileges_before_granting() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "has_schema_privilege(runtime_role, 'public', 'USAGE')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'SELECT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'INSERT')" in forward
    assert "has_table_privilege(runtime_role, object_reg, 'UPDATE')" in forward
    assert "WHEN insufficient_privilege THEN" in forward
    assert "manual grant required: GRANT SELECT, INSERT, UPDATE ON TABLE" in forward
    assert "apply manual grant with an owner/admin role" in forward


def test_migration_244_grants_live_error_object() -> None:
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT SELECT, INSERT, UPDATE ON TABLE" in forward
    for object_name in WRITE_OBJECTS:
        assert object_name in forward


def test_migration_244_does_not_over_grant_delete() -> None:
    """Least-privilege guard: no runtime code path DELETEs compliance_alerts
    rows (backend/services/compliance/alert_repository.py is INSERT/SELECT/
    UPDATE only) — only test-fixture teardown does, under the local `test`
    role. This migration must never grant DELETE to backend_rag_v2; a future
    edit that copy-pastes the 207/209/211 four-privilege bundle onto this
    table would silently regress that guarantee.

    Checks the actual SQL verbs/privilege-check calls, not a bare substring
    scan of the whole file — the header comment legitimately discusses
    DELETE in prose (why it's excluded), and a blind "DELETE not in forward"
    assertion would false-positive on that prose (guard over-match, cicatrix
    family #3) instead of checking the grant itself.
    """
    forward = _forward(MIGRATION_FILE.read_text())

    assert "GRANT SELECT, INSERT, UPDATE, DELETE" not in forward
    assert "has_table_privilege(runtime_role, object_reg, 'DELETE')" not in forward
    assert "REVOKE SELECT, INSERT, UPDATE, DELETE" not in forward


def test_migration_244_rollback_revokes_same_grants() -> None:
    rollback = _extract_rollback_sql(MIGRATION_FILE.read_text())

    assert rollback is not None
    assert "REVOKE SELECT, INSERT, UPDATE ON TABLE" in rollback
    assert "DELETE" not in rollback
    for object_name in WRITE_OBJECTS:
        assert object_name in rollback


def _strip_sql_line_comments(sql: str) -> str:
    """Drop lines that are pure `--` comments.

    Guard-over-match note (cicatrix family #3): a bare
    `"needle" not in forward` substring check is exactly the trap this
    repo's own guardrail doctrine warns about — this migration file's own
    explanatory prose is allowed to *discuss* a removed function call
    (as it does, in the NOTE comment above the FOREACH loop's tail) without
    that meaning the call is still executable. Every comment line in this
    file's style starts with `--` on its own line (no trailing inline
    comments), so filtering by line-prefix is precise here — this checks
    the entity (executable code), not the substring (any occurrence at
    all, including prose).
    """
    return "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )


def test_migration_244_forward_sql_has_no_serial_sequence_lookup() -> None:
    """Structural guard against regressing the 2026-07-17 fix.

    compliance_alerts.alert_id is TEXT PRIMARY KEY (no `id` column — see
    114_compliance_alerts.sql), so any future edit that reintroduces
    `pg_get_serial_sequence(object_name, 'id')` (or an equivalent
    per-column-name sequence lookup) inside the FOREACH loop would
    reintroduce the exact bug: that call RAISES "column ... does not
    exist" when the table has no `id` column, uncaught by any exception
    handler in this DO-block, aborting the whole migration on every real
    apply attempt (i.e. whenever `backend_rag_v2` exists — prod). This is
    a cheap static tripwire alongside the dynamic proof below, not a
    replacement for it — see
    test_migration_244_applies_cleanly_with_runtime_role_present for the
    bug this guards against (which this line-only check cannot itself
    catch: the text-contract tests in this file existed BEFORE the fix and
    never ran the SQL, which is why the bug reached prod in the first
    place).

    Checks executable code only (comment lines stripped) — the migration's
    own NOTE comment legitimately mentions `pg_get_serial_sequence` in
    prose explaining why it's gone; a bare substring scan of the whole
    file would false-positive on that prose instead of checking for the
    live call (same over-match class the existing
    test_migration_244_does_not_over_grant_delete docstring already
    warns about).
    """
    forward_code = _strip_sql_line_comments(_forward(MIGRATION_FILE.read_text()))
    assert "pg_get_serial_sequence" not in forward_code


# ---------------------------------------------------------------------------
# Real-DB regression tests for the 2026-07-17 prod outage.
#
# Root cause: `pg_get_serial_sequence(object_name, 'id')` (previously at
# line ~119) does not return NULL for a table with no `id` column — it
# RAISEs `UndefinedColumnError: column "id" of relation "compliance_alerts"
# does not exist`, uncaught by any exception handler in this DO-block. Every
# text-contract test above reads the file and asserts on substrings; none of
# them ever EXECUTE the SQL, so none could catch a runtime-only failure mode.
#
# The bug was invisible locally/CI because the whole DO-block is guarded by
# `IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = runtime_role) THEN
# RETURN; END IF;` — `backend_rag_v2` is never created locally or in CI, so
# the guard RETURNs before the FOREACH loop ever reaches the crashing line.
# In prod, the role exists, the guard passes through, and the migration
# aborted on every `apply_all_pending()` call (i.e. every `flyctl deploy`
# release_command) from 2026-07-16 19:47Z onward.
#
# These tests create `backend_rag_v2` for real (inside the transaction-
# scoped `db_tx` fixture, which is always rolled back at teardown — nothing
# persists, no manual cleanup needed) so the FOREACH loop's grant logic
# actually executes, exercising the exact code path that broke prod.
# ---------------------------------------------------------------------------


async def _ensure_role(conn: asyncpg.Connection, role: str) -> None:
    """Create `role` if it doesn't already exist (e.g. a CI/staging DB where
    the runtime role is provisioned out-of-band). Runs inside the caller's
    transaction — `db_tx` rolls it back at teardown either way, so this
    never leaves cluster-wide state behind when it's this function that
    created the role."""
    exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = $1)",
        role,
    )
    if not exists:
        await conn.execute(f'CREATE ROLE "{role}"')


async def _can_exercise_migration_244(conn: asyncpg.Connection) -> tuple[bool, str]:
    """Return (can_run, reason) for whether `conn` can exercise migration
    244's happy path (self-grant actually succeeding, not just hitting its
    "manual grant required" fallback).

    That needs the connecting role to be able to (a) `CREATE ROLE
    backend_rag_v2` if absent, and (b) `GRANT` on compliance_alerts —
    which Postgres requires being a superuser, the table's owner, or a
    member of the owning role for. In prod this is trivially true: the
    SAME role (backend_rag_v2) runs the whole migration chain in one
    `apply_all_pending()` pass, so it already owns every table earlier
    migrations created (114 creates compliance_alerts unconditionally, no
    role guard). CI's `postgres:15` service container's bootstrap
    `POSTGRES_USER` is a superuser, so both hold there too. A given local
    Postgres install may have neither — e.g. a restricted `test` role
    connecting to a database whose tables were bootstrapped, at some
    point in that machine's history, under a different admin account.
    That is an environment precondition this migration's SQL does not
    control, so callers should skip rather than assert a false negative
    that reflects local ambient state instead of a bug in the fix.

    Uses Postgres's own authority (`pg_has_role`, `pg_tables.tableowner`,
    `pg_roles.rolcreaterole`, `pg_user.usesuper`) rather than pattern-
    matching a caught exception's message — the entity, not a substring
    (see the guard-over-match note on
    test_migration_244_forward_sql_has_no_serial_sequence_lookup above).
    """
    is_super = await conn.fetchval(
        "SELECT usesuper FROM pg_user WHERE usename = current_user"
    )
    if is_super:
        return True, ""

    has_createrole = await conn.fetchval(
        "SELECT rolcreaterole FROM pg_roles WHERE rolname = current_user"
    )
    if not has_createrole:
        return False, f"current_user lacks CREATEROLE (needed to provision {RUNTIME_ROLE})"

    owner = await conn.fetchval(
        "SELECT tableowner FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename = 'compliance_alerts'"
    )
    if owner is None:
        # Table doesn't exist yet — this connection will create (and thus
        # own) it via _ensure_compliance_alerts_table.
        return True, ""

    current_user = await conn.fetchval("SELECT current_user")
    if owner == current_user:
        return True, ""

    is_member = await conn.fetchval("SELECT pg_has_role($1, $2, 'MEMBER')", current_user, owner)
    if is_member:
        return True, ""

    return False, (
        f"current_user ('{current_user}') is not a superuser, does not own "
        f"compliance_alerts (owned by '{owner}'), and is not a member of "
        f"'{owner}' — cannot GRANT on it"
    )


async def _ensure_compliance_alerts_table(conn: asyncpg.Connection) -> None:
    """Idempotently ensure compliance_alerts exists (114's forward SQL is
    itself `CREATE TABLE IF NOT EXISTS`). In both local dev and CI this
    table is already present by the time this test file runs, but building
    it defensively keeps this test self-sufficient rather than relying on
    ambient ordering."""
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'compliance_alerts')"
    )
    if not exists:
        sql = COMPLIANCE_ALERTS_MIGRATION_FILE.read_text(encoding="utf-8")
        forward, _ = split_migration_sql(sql)
        await conn.execute(forward)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_244_applies_cleanly_with_runtime_role_present(
    db_tx: asyncpg.Connection,
) -> None:
    """The forward SQL must complete without raising, and must grant exactly
    SELECT/INSERT/UPDATE (never DELETE) to backend_rag_v2 on
    compliance_alerts, when the runtime role actually exists — the prod
    code path. Pre-fix, `db_tx.execute(forward)` below raised
    `asyncpg.exceptions.UndefinedColumnError`.
    """
    can_run, reason = await _can_exercise_migration_244(db_tx)
    if not can_run:
        pytest.skip(f"environment precondition not met: {reason}")

    await _ensure_role(db_tx, RUNTIME_ROLE)
    await _ensure_compliance_alerts_table(db_tx)

    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, _ = split_migration_sql(sql)

    # Must not raise. This is the exact statement the Fly release_command
    # (`python -m backend.db.migrate apply-all` -> apply_all_pending() ->
    # BaseMigration.apply() -> conn.execute(sql_forward)) executes in prod.
    await db_tx.execute(forward)

    for priv in ("SELECT", "INSERT", "UPDATE"):
        granted = await db_tx.fetchval(
            "SELECT has_table_privilege($1, 'public.compliance_alerts', $2)",
            RUNTIME_ROLE,
            priv,
        )
        assert granted, f"{RUNTIME_ROLE} missing {priv} after migration 244 applied"

    delete_granted = await db_tx.fetchval(
        "SELECT has_table_privilege($1, 'public.compliance_alerts', 'DELETE')",
        RUNTIME_ROLE,
    )
    assert not delete_granted, "migration 244 must never grant DELETE (least privilege)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_244_idempotent_when_reapplied(
    db_tx: asyncpg.Connection,
) -> None:
    """The forward SQL must be safe to execute twice in a row. Matters for
    manual remediation / a re-run after a stuck deploy, and mirrors the
    file's own `has_table_privilege(...)` re-check-before-grant contract.
    """
    can_run, reason = await _can_exercise_migration_244(db_tx)
    if not can_run:
        pytest.skip(f"environment precondition not met: {reason}")

    await _ensure_role(db_tx, RUNTIME_ROLE)
    await _ensure_compliance_alerts_table(db_tx)

    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    forward, _ = split_migration_sql(sql)

    await db_tx.execute(forward)
    await db_tx.execute(forward)  # must not raise the second time either

    granted = await db_tx.fetchval(
        "SELECT has_table_privilege($1, 'public.compliance_alerts', 'SELECT')",
        RUNTIME_ROLE,
    )
    assert granted

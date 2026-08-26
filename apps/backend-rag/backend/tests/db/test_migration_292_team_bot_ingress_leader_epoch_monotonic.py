"""Live-DB proof of migration 292's epoch-rollback guard (F9 refutation
finding #7, F9-CALLBACK-WRITE-FENCE-SPEC.md).

Migration 291's own COMMENT ON TABLE claims "Written ONLY via
compare-and-swap ... never a bare UPDATE" -- a comment, not a constraint.
Migration 292's trigger makes it a schema-level guarantee: any UPDATE that
decreases leader_epoch is rejected, independent of whether the application
code calling it stays correct. Applied here against a REAL Postgres
connection -- this file lives OUTSIDE backend/tests/duebot/ specifically
because that package's network_guard.py blocks every real socket
connection at the os.socket layer; a genuine trigger-behavior test needs a
real one.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import ROLLBACK_MARKER_RE, split_migration_sql

_MIG_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"
MIGRATION_291 = _MIG_DIR / "291_team_bot_ingress_leader.sql"
MIGRATION_292 = _MIG_DIR / "292_team_bot_ingress_leader_epoch_monotonic.sql"


def test_migration_file_exists():
    assert MIGRATION_292.exists(), f"Migration file missing: {MIGRATION_292}"


def test_migration_has_rollback_marker_exactly_once():
    sql = MIGRATION_292.read_text()
    matches = ROLLBACK_MARKER_RE.findall(sql)
    assert len(matches) == 1, (
        f"Migration must include exactly one `-- === ROLLBACK ===` marker LINE, found {len(matches)}"
    )


def test_forward_and_rollback_are_both_non_empty():
    sql = MIGRATION_292.read_text()
    forward, rollback = split_migration_sql(sql)
    assert forward.strip() != ""
    assert rollback is not None
    assert rollback.strip() != ""


_CLEAN_SLATE_SQL = """
DROP TRIGGER IF EXISTS team_bot_ingress_leader_forbid_epoch_rollback_trg ON public.team_bot_ingress_leader;
DROP FUNCTION IF EXISTS public.team_bot_ingress_leader_forbid_epoch_rollback();
DROP TABLE IF EXISTS public.team_bot_ingress_leader;
"""


async def _apply_291_only(conn: asyncpg.Connection) -> None:
    await conn.execute(_CLEAN_SLATE_SQL)
    forward_291, _ = split_migration_sql(MIGRATION_291.read_text())
    await conn.execute(forward_291)


async def _apply_291_and_292(conn: asyncpg.Connection) -> None:
    await _apply_291_only(conn)
    forward_292, _ = split_migration_sql(MIGRATION_292.read_text())
    await conn.execute(forward_292)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_RED_before_292_a_bare_epoch_rollback_succeeds(db_tx: asyncpg.Connection) -> None:
    """RED-before-the-fix control: with ONLY migration 291 applied (no
    292), a bare UPDATE that DECREASES leader_epoch succeeds -- proving
    291's own "written ONLY via CAS" claim was a comment, not a
    constraint, exactly as the refutation named. This test documents that
    fact permanently rather than only proving it once during development.
    """
    await _apply_291_only(db_tx)
    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 5 WHERE record_id = 'team_wa_default'"
    )
    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 4 WHERE record_id = 'team_wa_default'"
    )
    rolled_back = await db_tx.fetchval(
        "SELECT leader_epoch FROM team_bot_ingress_leader WHERE record_id = 'team_wa_default'"
    )
    assert rolled_back == 4, "without 292, nothing stops an epoch rollback"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_epoch_rollback_is_rejected(db_tx: asyncpg.Connection) -> None:
    """GUILT: with 292 applied, any UPDATE decreasing leader_epoch is
    rejected -- even a bare UPDATE that never went through
    ingress_state_repo.py's CAS at all.
    """
    await _apply_291_and_292(db_tx)
    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 5 WHERE record_id = 'team_wa_default'"
    )
    # The failing UPDATE must run inside its OWN nested transaction
    # (asyncpg promotes a nested `transaction()` to a SAVEPOINT
    # automatically): a bare RAISE EXCEPTION aborts the ENTIRE enclosing
    # `db_tx` transaction in Postgres, not just the one statement, so
    # asserting anything afterward in the same transaction would raise
    # InFailedSQLTransactionError instead of proving the intended point.
    with pytest.raises(asyncpg.exceptions.RaiseError, match="may never decrease"):
        async with db_tx.transaction():
            await db_tx.execute(
                "UPDATE team_bot_ingress_leader SET leader_epoch = 4 WHERE record_id = 'team_wa_default'"
            )
    unchanged = await db_tx.fetchval(
        "SELECT leader_epoch FROM team_bot_ingress_leader WHERE record_id = 'team_wa_default'"
    )
    assert unchanged == 5, "the rejected UPDATE must not have partially applied"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_epoch_increase_and_unchanged_are_both_allowed(db_tx: asyncpg.Connection) -> None:
    """INNOCENCE: an increase (try_promote's shape) and an UNCHANGED epoch
    (renew()'s shape -- only lease_expires_at moves) must both still
    succeed with the guard in place.
    """
    await _apply_291_and_292(db_tx)

    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 2 WHERE record_id = 'team_wa_default'"
    )
    after_increase = await db_tx.fetchval(
        "SELECT leader_epoch FROM team_bot_ingress_leader WHERE record_id = 'team_wa_default'"
    )
    assert after_increase == 2

    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET lease_expires_at = now() + interval '30 seconds' "
        "WHERE record_id = 'team_wa_default' AND leader_epoch = 2"
    )
    after_renew_shape = await db_tx.fetchval(
        "SELECT leader_epoch FROM team_bot_ingress_leader WHERE record_id = 'team_wa_default'"
    )
    assert after_renew_shape == 2, "an UPDATE that leaves leader_epoch unchanged must succeed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rollback_of_292_removes_the_guard_then_reapply_reguards(
    db_tx: asyncpg.Connection,
) -> None:
    """Guilt-arm: prove the NEW trigger, not something else, is what
    blocks the rollback.
    """
    await _apply_291_and_292(db_tx)
    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 5 WHERE record_id = 'team_wa_default'"
    )

    _, rollback_292 = split_migration_sql(MIGRATION_292.read_text())
    assert rollback_292 is not None
    await db_tx.execute(rollback_292)

    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 1 WHERE record_id = 'team_wa_default'"
    )
    reverted = await db_tx.fetchval(
        "SELECT leader_epoch FROM team_bot_ingress_leader WHERE record_id = 'team_wa_default'"
    )
    assert reverted == 1

    forward_292, _ = split_migration_sql(MIGRATION_292.read_text())
    await db_tx.execute(forward_292)
    await db_tx.execute(
        "UPDATE team_bot_ingress_leader SET leader_epoch = 3 WHERE record_id = 'team_wa_default'"
    )
    with pytest.raises(asyncpg.exceptions.RaiseError, match="may never decrease"):
        await db_tx.execute(
            "UPDATE team_bot_ingress_leader SET leader_epoch = 2 WHERE record_id = 'team_wa_default'"
        )

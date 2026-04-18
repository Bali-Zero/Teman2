"""
Integration test: apply migrations 114/115/116 against real Postgres, then
rollback each, ensuring schema state matches pre/post expectations.

Uses the `db_tx` fixture from conftest.py — transaction-scoped, rolled back
at teardown. Requires local Postgres running on the default URL.
"""
from __future__ import annotations

import pathlib

import pytest
import asyncpg

from backend.db.migration_manager import _extract_rollback_sql


pytestmark = pytest.mark.integration


_MIG_DIR = pathlib.Path(__file__).parent.parent.parent / "db" / "migrations_v2"


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=$1)",
        name,
    )


async def _ensure_clean_slate(conn: asyncpg.Connection) -> None:
    """Drop our tables if they exist from outside this transaction.

    Integration tests in other suites commit data into these tables
    during the test session; this test exercises the raw migration
    semantics from scratch, so start clean.
    """
    await conn.execute("DROP TABLE IF EXISTS alert_outcomes CASCADE")
    await conn.execute("DROP TABLE IF EXISTS compliance_alerts CASCADE")
    await conn.execute("DROP TABLE IF EXISTS intel_validator_log CASCADE")


def _forward_and_rollback(sql_text: str) -> tuple[str, str]:
    """Split a migration file into (forward_sql, rollback_sql)."""
    rollback = _extract_rollback_sql(sql_text) or ""
    forward = sql_text.split("-- === ROLLBACK ===")[0].strip()
    return forward, rollback


@pytest.mark.asyncio
async def test_migration_114_roundtrip(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    sql = (_MIG_DIR / "114_compliance_alerts.sql").read_text(encoding="utf-8")
    forward, rollback = _forward_and_rollback(sql)
    assert rollback, "114 must have a non-empty ROLLBACK block"

    await db_tx.execute(forward)
    assert await _table_exists(db_tx, "compliance_alerts")

    await db_tx.execute(rollback)
    assert not await _table_exists(db_tx, "compliance_alerts")


@pytest.mark.asyncio
async def test_migration_115_requires_114(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    # 115 FK-references compliance_alerts; applying alone must fail
    sql = (_MIG_DIR / "115_alert_outcomes.sql").read_text(encoding="utf-8")
    forward, _ = _forward_and_rollback(sql)
    with pytest.raises(asyncpg.PostgresError):
        await db_tx.execute(forward)


@pytest.mark.asyncio
async def test_migration_114_115_chain(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    for name in ("114_compliance_alerts.sql", "115_alert_outcomes.sql"):
        sql = (_MIG_DIR / name).read_text(encoding="utf-8")
        forward, _ = _forward_and_rollback(sql)
        await db_tx.execute(forward)

    assert await _table_exists(db_tx, "compliance_alerts")
    assert await _table_exists(db_tx, "alert_outcomes")


@pytest.mark.asyncio
async def test_migration_116_standalone(db_tx: asyncpg.Connection) -> None:
    await _ensure_clean_slate(db_tx)
    sql = (_MIG_DIR / "116_intel_validator_log.sql").read_text(encoding="utf-8")
    forward, _ = _forward_and_rollback(sql)
    await db_tx.execute(forward)
    assert await _table_exists(db_tx, "intel_validator_log")


def test_rollback_marker_present_in_all_three() -> None:
    for name in (
        "114_compliance_alerts.sql",
        "115_alert_outcomes.sql",
        "116_intel_validator_log.sql",
    ):
        sql = (_MIG_DIR / name).read_text(encoding="utf-8")
        rollback = _extract_rollback_sql(sql)
        assert rollback is not None, f"{name} missing ROLLBACK block"
        assert rollback.strip() != "", f"{name} has empty ROLLBACK block"

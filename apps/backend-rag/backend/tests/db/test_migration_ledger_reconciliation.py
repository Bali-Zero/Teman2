"""Unit coverage for migration ledger reconciliation.

These tests pin the failure mode where ``schema_migrations`` says a migration
ran, ``_schema_versions`` is missing the row, and physical DB state still needs
an idempotent remediation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db.migration_manager import MigrationManager


class _FakeAcquireCtx:
    def __init__(self, conn: AsyncMock) -> None:
        self.conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self.conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _manager_with_conn(conn: AsyncMock) -> MigrationManager:
    mgr = MigrationManager.__new__(MigrationManager)
    mgr.database_url = "postgresql://fake/fake"
    pool = MagicMock()
    pool.acquire = lambda: _FakeAcquireCtx(conn)
    mgr.pool = pool
    return mgr


def _migration_info(number: int, filename: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "db" / "migrations_v2" / filename
    return {
        "number": number,
        "file": filename,
        "path": path,
        "rollback_sql": "SELECT 1",
    }


def _canonical_row(number: int, name: str) -> dict[str, Any]:
    return {
        "migration_name": name,
        "migration_number": number,
        "executed_at": None,
        "checksum": f"canonical-checksum-{number}",
        "description": f"Migration {number}",
        "execution_time_ms": 12,
        "rollback_sql": "SELECT 1",
    }


@pytest.mark.asyncio
async def test_canonical_only_migration_with_bad_physical_state_is_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [
        _canonical_row(140, "140_drop_crm_guardian_events_no_update_delete_rules"),
    ]
    # For migration 140, True means the blocking rules still exist.
    conn.fetchval.return_value = True

    mgr = _manager_with_conn(conn)
    monkeypatch.setattr(
        mgr,
        "discover_migrations",
        AsyncMock(
            return_value=[
                _migration_info(140, "140_drop_crm_guardian_events_no_update_delete_rules.sql"),
            ],
        ),
    )
    monkeypatch.setattr(mgr, "get_applied_migrations", AsyncMock(return_value=[]))
    apply_migration = AsyncMock(return_value=True)
    monkeypatch.setattr(mgr, "apply_migration", apply_migration)

    result = await mgr._apply_all_pending_locked(dry_run=False)

    assert result["applied"] == [140]
    assert result["reconciled"] == [140]
    assert result["failed"] == []
    apply_migration.assert_awaited_once()
    assert apply_migration.await_args.kwargs["force"] is True


@pytest.mark.asyncio
async def test_canonical_only_migration_with_good_physical_state_is_backfilled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [
        _canonical_row(140, "140_drop_crm_guardian_events_no_update_delete_rules"),
    ]
    # For migration 140, False means no blocking rules remain.
    conn.fetchval.return_value = False

    mgr = _manager_with_conn(conn)
    monkeypatch.setattr(
        mgr,
        "discover_migrations",
        AsyncMock(
            return_value=[
                _migration_info(140, "140_drop_crm_guardian_events_no_update_delete_rules.sql"),
            ],
        ),
    )
    monkeypatch.setattr(mgr, "get_applied_migrations", AsyncMock(return_value=[]))
    apply_migration = AsyncMock(return_value=True)
    monkeypatch.setattr(mgr, "apply_migration", apply_migration)

    result = await mgr._apply_all_pending_locked(dry_run=False)

    assert result["applied"] == []
    assert result["reconciled"] == [140]
    assert result["failed"] == []
    apply_migration.assert_not_awaited()


@pytest.mark.asyncio
async def test_historical_canonical_rows_without_files_are_backfilled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [_canonical_row(7, "007_create_clients")],
        [],
    ]

    mgr = _manager_with_conn(conn)
    monkeypatch.setattr(mgr, "discover_migrations", AsyncMock(return_value=[]))
    monkeypatch.setattr(mgr, "get_applied_migrations", AsyncMock(return_value=[]))
    apply_migration = AsyncMock(return_value=True)
    monkeypatch.setattr(mgr, "apply_migration", apply_migration)

    result = await mgr._apply_all_pending_locked(dry_run=False)

    assert result["applied"] == []
    assert result["reconciled"] == [7]
    assert result["failed"] == []
    apply_migration.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_only_discovered_rows_are_backfilled_to_canonical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [],
        [
            {
                "migration_name": "108_lkpm_receipts.sql",
                "migration_number": 108,
                "executed_at": None,
                "checksum": "legacy-checksum",
                "description": "pre-applied",
                "execution_time_ms": 0,
                "rollback_sql": None,
            },
        ],
    ]

    mgr = _manager_with_conn(conn)
    monkeypatch.setattr(
        mgr,
        "discover_migrations",
        AsyncMock(return_value=[_migration_info(108, "108_lkpm_receipts.sql")]),
    )
    monkeypatch.setattr(
        mgr,
        "get_applied_migrations",
        AsyncMock(
            return_value=[
                {"migration_name": "108_lkpm_receipts.sql", "migration_number": 108},
            ],
        ),
    )
    apply_migration = AsyncMock(return_value=True)
    monkeypatch.setattr(mgr, "apply_migration", apply_migration)

    result = await mgr._apply_all_pending_locked(dry_run=False)

    assert result["applied"] == []
    assert result["reconciled"] == [108]
    assert result["failed"] == []
    apply_migration.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_status_counts_only_discovered_applied_migrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = MigrationManager.__new__(MigrationManager)
    monkeypatch.setattr(
        mgr,
        "discover_migrations",
        AsyncMock(
            return_value=[
                {"number": 1, "file": "001_baseline_v2.sql"},
                {"number": 2, "file": "002_example.sql"},
            ],
        ),
    )
    monkeypatch.setattr(
        mgr,
        "get_applied_migrations",
        AsyncMock(
            return_value=[
                {"migration_number": 0},
                {"migration_number": 1},
                {"migration_number": 2},
                {"migration_number": 7},
            ],
        ),
    )

    status = await mgr.get_status()

    assert status["total"] == 2
    assert status["applied"] == 2
    assert status["pending"] == 0
    assert status["applied_list"] == [1, 2]
    assert status["pending_list"] == []

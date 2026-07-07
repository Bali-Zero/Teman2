from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from backend.db.migration_base import MigrationError
from backend.services.misc import migration_runner as module
from backend.services.misc.migration_runner import MigrationRunner


class FakeMigrationManager:
    def __init__(self) -> None:
        self.connected = False
        self.closed = False
        self.applied_rows: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def get_applied_migrations(self) -> list[dict[str, Any]]:
        return self.applied_rows


def write_migration(
    migrations_dir: Path,
    stem: str,
    migration_number: int,
    description: str,
    *,
    dependencies: list[int] | None = None,
    apply_body: str = "return True",
) -> None:
    sql_name = f"{migration_number:03d}_{stem}.sql"
    (migrations_dir / sql_name).write_text("SELECT 1;\n")
    class_name = "".join(part.title() for part in stem.split("_")) + "Migration"
    deps = dependencies or []
    (migrations_dir / f"migration_{migration_number:03d}_{stem}.py").write_text(
        f"""
from pathlib import Path

from backend.db.migration_base import BaseMigration


class {class_name}(BaseMigration):
    def __init__(self) -> None:
        super().__init__(
            migration_number={migration_number},
            sql_file={sql_name!r},
            description={description!r},
            dependencies={deps!r},
            _sql_dir=Path(__file__).parent,
        )

    async def apply(self) -> bool:
        {apply_body}
""",
    )


@pytest.fixture(autouse=True)
def clear_dynamic_migration_modules() -> None:
    for name in list(sys.modules):
        if name.startswith("migrations.migration_") or name.startswith("migration_"):
            sys.modules.pop(name, None)


@pytest.mark.asyncio
async def test_initialize_and_close_delegate_to_migration_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeMigrationManager()
    monkeypatch.setattr(module, "MigrationManager", lambda: manager)

    runner = MigrationRunner(tmp_path)
    await runner.initialize()
    await runner.close()

    assert runner.migration_manager is manager
    assert manager.connected is True
    assert manager.closed is True


def test_discover_migrations_loads_base_migration_subclasses(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first migration")
    write_migration(tmp_path, "second", 2, "second migration", dependencies=[1])

    runner = MigrationRunner(tmp_path)

    migrations = runner.discover_migrations()

    assert sorted(migrations) == [1, 2]
    assert migrations[1]().description == "first migration"
    assert migrations[2]().dependencies == [1]
    assert runner.discover_migrations() is migrations


def test_resolve_dependencies_orders_dependencies_before_dependents(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first")
    write_migration(tmp_path, "second", 2, "second", dependencies=[1])
    write_migration(tmp_path, "third", 3, "third", dependencies=[2])
    runner = MigrationRunner(tmp_path)

    ordered = runner.resolve_dependencies(runner.discover_migrations())

    assert ordered == [1, 2, 3]


def test_resolve_dependencies_rejects_circular_graph(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first", dependencies=[2])
    write_migration(tmp_path, "second", 2, "second", dependencies=[1])
    runner = MigrationRunner(tmp_path)

    with pytest.raises(MigrationError, match="Circular dependency"):
        runner.resolve_dependencies(runner.discover_migrations())


@pytest.mark.asyncio
async def test_get_applied_migrations_filters_blank_numbers(tmp_path: Path) -> None:
    manager = FakeMigrationManager()
    manager.applied_rows = [
        {"migration_number": 1},
        {"migration_number": 0},
        {"migration_number": None},
        {"migration_number": 3},
    ]
    runner = MigrationRunner(tmp_path)
    runner.migration_manager = manager

    assert await runner.get_applied_migrations() == {1, 3}


@pytest.mark.asyncio
async def test_get_pending_migrations_uses_dry_run_without_database(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first")
    write_migration(tmp_path, "second", 2, "second", dependencies=[1])
    runner = MigrationRunner(tmp_path)

    pending = await runner.get_pending_migrations(dry_run=True)

    assert [number for number, _ in pending] == [1, 2]
    assert runner.migration_manager is None


@pytest.mark.asyncio
async def test_get_pending_migrations_excludes_applied_numbers(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first")
    write_migration(tmp_path, "second", 2, "second", dependencies=[1])
    manager = FakeMigrationManager()
    manager.applied_rows = [{"migration_number": 1}]
    runner = MigrationRunner(tmp_path)
    runner.migration_manager = manager

    pending = await runner.get_pending_migrations()

    assert [number for number, _ in pending] == [2]


@pytest.mark.asyncio
async def test_apply_all_dry_run_reports_would_apply(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first")
    write_migration(tmp_path, "second", 2, "second")
    runner = MigrationRunner(tmp_path)
    runner.migration_manager = FakeMigrationManager()

    result = await runner.apply_all(dry_run=True)

    assert result == {
        "success": True,
        "applied": 2,
        "skipped": 0,
        "errors": [],
        "applied_migrations": [1, 2],
    }


@pytest.mark.asyncio
async def test_apply_all_records_errors_and_continues_when_configured(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first", apply_body="return False")
    write_migration(tmp_path, "second", 2, "second")
    runner = MigrationRunner(tmp_path)
    runner.migration_manager = FakeMigrationManager()

    result = await runner.apply_all(dry_run=False, stop_on_error=False)

    assert result["success"] is False
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert result["errors"] == [
        {"migration": 1, "error": "Migration 1 failed to apply"},
    ]
    assert result["applied_migrations"] == [2]


@pytest.mark.asyncio
async def test_status_reports_applied_and_pending_migrations(tmp_path: Path) -> None:
    write_migration(tmp_path, "first", 1, "first")
    write_migration(tmp_path, "second", 2, "second")
    manager = FakeMigrationManager()
    manager.applied_rows = [{"migration_number": 1}]
    runner = MigrationRunner(tmp_path)
    runner.migration_manager = manager

    status = await runner.status()

    assert status["total_migrations"] == 2
    assert status["applied"] == 1
    assert status["pending"] == 1
    assert status["applied_numbers"] == [1]
    assert status["pending_numbers"] == [2]
    assert status["migrations"][1] == {"applied": True, "description": "first"}
    assert status["migrations"][2] == {"applied": False, "description": "second"}

"""Tests for the `-- depends: N` inter-migration dependency convention.

`discover_migrations()` extracts declared dependencies from each
migrations_v2/*.sql header comment and `_apply_all_pending_locked()` passes
them to BaseMigration(dependencies=...), where the existing
`_check_dependencies()` refuses to apply a migration whose dependency has
not been applied yet. These tests cover the parser, the discovery plumbing,
and the guilt/innocence behaviour of the check itself with a synthetic
migration fixture (no database involved).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.db.migration_base import (
    BaseMigration,
    MigrationError,
    extract_dependencies,
)
from backend.db.migration_manager import MigrationManager


class TestExtractDependencies:
    def test_no_marker_returns_empty(self) -> None:
        assert extract_dependencies("CREATE TABLE foo (id INT);\n") == []

    def test_single_dependency(self) -> None:
        sql = "-- depends: 277\nCREATE TABLE foo (id INT);\n"
        assert extract_dependencies(sql) == [277]

    def test_multiple_dependencies_sorted_and_deduped(self) -> None:
        sql = "-- depends: 300, 277 299, 277\nCREATE TABLE foo (id INT);\n"
        assert extract_dependencies(sql) == [277, 299, 300]

    def test_marker_is_case_insensitive(self) -> None:
        sql = "-- DEPENDS: 277\nCREATE TABLE foo (id INT);\n"
        assert extract_dependencies(sql) == [277]

    def test_ignores_unparseable_tokens(self) -> None:
        sql = "-- depends: 27x, , 277\nCREATE TABLE foo (id INT);\n"
        assert extract_dependencies(sql) == [277]

    def test_prose_dependency_note_is_not_a_declaration(self) -> None:
        # 155_asset_provenance_trigger.sql carries a prose line
        # "-- Depends:   migration 154 (asset_provenance table)"; prose must
        # not be parsed as a machine declaration.
        sql = "-- Depends:   migration 154 (asset_provenance table)\nCREATE TABLE foo (id INT);\n"
        assert extract_dependencies(sql) == []


class TestDiscoverMigrationsPlumbing:
    """Integration: discover_migrations attaches dependencies to each dict."""

    @pytest.mark.asyncio
    async def test_dependencies_are_propagated_to_dict(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        v2_dir = tmp_path / "migrations_v2"
        v2_dir.mkdir()
        (v2_dir / "149_base.sql").write_text(
            "CREATE TABLE base_tbl (id INT);\n-- === ROLLBACK ===\nDROP TABLE base_tbl;\n",
            encoding="utf-8",
        )
        (v2_dir / "150_dependent.sql").write_text(
            "-- depends: 149\nCREATE TABLE dependent_tbl (id INT);\n"
            "-- === ROLLBACK ===\nDROP TABLE dependent_tbl;\n",
            encoding="utf-8",
        )

        # discover_migrations builds its dir via
        # `Path(__file__).parent / "migrations_v2"`, so shim the module's
        # __file__ to a sibling of tmp_path (same trick as the
        # rollback-extraction plumbing tests).
        import backend.db.migration_manager as mm

        fake_parent = tmp_path / "db"
        fake_parent.mkdir()
        fake_file = fake_parent / "migration_manager.py"
        fake_file.write_text("")
        (fake_parent / "migrations_v2").symlink_to(v2_dir)
        monkeypatch.setattr(mm, "__file__", str(fake_file))

        mgr = MigrationManager(database_url="postgresql://fake/fake")
        discovered = await mgr.discover_migrations()

        by_number = {d["number"]: d for d in discovered}
        assert by_number[149]["dependencies"] == []
        assert by_number[150]["dependencies"] == [149]


class _DepCheckConnection:
    """asyncpg-like fake whose ledger answers from a set of applied numbers."""

    def __init__(self, applied_numbers: set[int]) -> None:
        self.applied_numbers = applied_numbers

    async def execute(self, _sql: str, *_args: Any) -> None:
        return None

    async def fetch(self, _sql: str, *_args: Any) -> list[dict[str, Any]]:
        return [
            {
                "migration_name": f"{n:03d}_probe.sql",
                "migration_number": n,
                "executed_at": None,
                "description": "",
            }
            for n in sorted(self.applied_numbers)
        ]

    async def fetchval(self, _sql: str, *args: Any) -> bool:
        return args[0] in self.applied_numbers


def _dependent_migration(tmp_path: Path) -> BaseMigration:
    sql_file = tmp_path / "278_synthetic_dependent.sql"
    sql_file.write_text(
        "-- depends: 277\nCREATE TABLE dep_probe (id INT);\n",
        encoding="utf-8",
    )
    return BaseMigration(
        migration_number=278,
        sql_file=sql_file.name,
        description="synthetic dependency probe",
        dependencies=[277],
        rollback_sql="DROP TABLE dep_probe;",
        _sql_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_check_dependencies_refuses_unapplied_dependency(tmp_path: Path) -> None:
    """GUILT: a declared dependency that is not applied yet must refuse."""
    migration = _dependent_migration(tmp_path)
    conn = _DepCheckConnection(applied_numbers=set())

    with pytest.raises(MigrationError, match="depends on migration 277"):
        await migration._check_dependencies(conn)  # noqa: SLF001


@pytest.mark.asyncio
async def test_check_dependencies_proceeds_when_dependency_applied(tmp_path: Path) -> None:
    """INNOCENCE: a declared dependency that IS applied must not refuse."""
    migration = _dependent_migration(tmp_path)
    conn = _DepCheckConnection(applied_numbers={277})

    await migration._check_dependencies(conn)  # noqa: SLF001 — no raise


@pytest.mark.asyncio
async def test_check_dependencies_noops_without_declaration(tmp_path: Path) -> None:
    sql_file = tmp_path / "279_no_deps.sql"
    sql_file.write_text("CREATE TABLE no_deps (id INT);\n", encoding="utf-8")
    migration = BaseMigration(
        migration_number=279,
        sql_file=sql_file.name,
        description="no declared dependencies",
        rollback_sql="DROP TABLE no_deps;",
        _sql_dir=tmp_path,
    )
    conn = _DepCheckConnection(applied_numbers=set())

    await migration._check_dependencies(conn)  # noqa: SLF001 — no raise


class _FakePool:
    """Minimal pool double: acquire() returns an async context manager."""

    def __init__(self, conn: _DepCheckConnection) -> None:
        self._conn = conn

    def acquire(self) -> _FakePool:
        return self

    async def __aenter__(self) -> _DepCheckConnection:
        return self._conn

    async def __aexit__(self, *_args: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_apply_all_pending_passes_dependencies_to_base_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wiring: the dependency declared in the SQL header must reach the
    BaseMigration instance that _apply_all_pending_locked constructs."""
    v2_dir = tmp_path / "migrations_v2"
    v2_dir.mkdir()
    (v2_dir / "149_base.sql").write_text(
        "CREATE TABLE base_tbl (id INT);\n-- === ROLLBACK ===\nDROP TABLE base_tbl;\n",
        encoding="utf-8",
    )
    (v2_dir / "150_dependent.sql").write_text(
        "-- depends: 149\nCREATE TABLE dependent_tbl (id INT);\n"
        "-- === ROLLBACK ===\nDROP TABLE dependent_tbl;\n",
        encoding="utf-8",
    )

    import backend.db.migration_manager as mm

    fake_parent = tmp_path / "db"
    fake_parent.mkdir()
    fake_file = fake_parent / "migration_manager.py"
    fake_file.write_text("")
    (fake_parent / "migrations_v2").symlink_to(v2_dir)
    monkeypatch.setattr(mm, "__file__", str(fake_file))
    # BaseMigration resolves SQL files against its class-level MIGRATIONS_DIR.
    monkeypatch.setattr(BaseMigration, "MIGRATIONS_DIR", v2_dir)

    captured: list[BaseMigration] = []

    async def fake_apply(self: MigrationManager, migration: BaseMigration) -> bool:
        captured.append(migration)
        return True

    monkeypatch.setattr(MigrationManager, "apply_migration", fake_apply)

    mgr = MigrationManager(database_url="postgresql://fake/fake")
    mgr.pool = _FakePool(_DepCheckConnection(applied_numbers=set()))

    result = await mgr._apply_all_pending_locked()  # noqa: SLF001

    assert result["failed"] == []
    dependent = next(m for m in captured if m.migration_number == 150)
    assert dependent.dependencies == [149]

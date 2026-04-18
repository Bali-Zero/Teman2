"""
Tests for migration_manager.py rollback_sql extraction from SQL files.

A SQL migration file may include a trailing `-- === ROLLBACK ===` marker line;
everything after it is the rollback SQL. The manager must pass that string
into BaseMigration(rollback_sql=...) for post-111 migrations.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.db.migration_manager import (
    MigrationManager,
    _extract_rollback_sql,
)


class TestExtractRollbackSql:
    def test_no_marker_returns_none(self) -> None:
        sql = "CREATE TABLE foo (id INT);\n"
        assert _extract_rollback_sql(sql) is None

    def test_marker_splits_content(self) -> None:
        sql = (
            "CREATE TABLE foo (id INT);\n"
            "-- === ROLLBACK ===\n"
            "DROP TABLE foo;\n"
        )
        assert _extract_rollback_sql(sql) == "DROP TABLE foo;"

    def test_marker_is_case_insensitive(self) -> None:
        sql = (
            "CREATE TABLE foo (id INT);\n"
            "-- === rollback ===\n"
            "DROP TABLE foo;\n"
        )
        assert _extract_rollback_sql(sql) == "DROP TABLE foo;"

    def test_empty_rollback_section_returns_empty_string(self) -> None:
        sql = (
            "CREATE TABLE foo (id INT);\n"
            "-- === ROLLBACK ===\n"
        )
        assert _extract_rollback_sql(sql) == ""

    def test_multiline_rollback_preserved(self) -> None:
        sql = (
            "CREATE TABLE foo (id INT);\n"
            "CREATE TABLE bar (id INT);\n"
            "-- === ROLLBACK ===\n"
            "DROP TABLE bar;\n"
            "DROP TABLE foo;\n"
        )
        assert _extract_rollback_sql(sql) == "DROP TABLE bar;\nDROP TABLE foo;"


class TestDiscoverMigrationsPlumbing:
    """Integration: verify discover_migrations attaches rollback_sql to each dict."""

    @pytest.mark.asyncio
    async def test_rollback_sql_is_propagated_to_dict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange: create a temp migrations_v2 dir with two files:
        # one without marker (rollback_sql=None), one with marker.
        v2_dir = tmp_path / "migrations_v2"
        v2_dir.mkdir()
        (v2_dir / "050_legacy.sql").write_text(
            "CREATE TABLE legacy (id INT);\n",
            encoding="utf-8",
        )
        (v2_dir / "200_new.sql").write_text(
            "CREATE TABLE foo (id INT);\n"
            "-- === ROLLBACK ===\n"
            "DROP TABLE foo;\n",
            encoding="utf-8",
        )

        # Patch only the one attribute the method reads, without touching the
        # global Path symbol. discover_migrations builds its dir via
        # `Path(__file__).parent / "migrations_v2"`, so we shim that by
        # monkey-patching the module's __file__ to a sibling of tmp_path.
        import backend.db.migration_manager as mm
        fake_parent = tmp_path / "db"
        fake_parent.mkdir()
        fake_file = fake_parent / "migration_manager.py"
        fake_file.write_text("")
        # Symlink the migrations_v2 dir where the code expects it
        (fake_parent / "migrations_v2").symlink_to(v2_dir)
        monkeypatch.setattr(mm, "__file__", str(fake_file))

        # Act
        mgr = MigrationManager(database_url="postgresql://fake/fake")
        discovered = await mgr.discover_migrations()

        # Assert
        discovered_sorted = sorted(discovered, key=lambda d: d["number"])
        assert len(discovered_sorted) == 2
        assert discovered_sorted[0]["number"] == 50
        assert discovered_sorted[0]["rollback_sql"] is None
        assert discovered_sorted[1]["number"] == 200
        assert discovered_sorted[1]["rollback_sql"] == "DROP TABLE foo;"

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

"""Tests for the ROLLBACK marker helper added alongside migration 112."""

from __future__ import annotations

from backend.db.migration_base import ROLLBACK_MARKER, _split_rollback_marker


def test_no_marker_returns_whole_sql_as_forward():
    sql = "CREATE TABLE foo (id INT);"
    fwd, rb = _split_rollback_marker(sql)
    assert fwd == sql
    assert rb is None


def test_marker_splits_forward_and_rollback():
    sql = (
        "CREATE TABLE foo (id INT);\n\n"
        f"{ROLLBACK_MARKER}\n"
        "DROP TABLE foo;\n"
    )
    fwd, rb = _split_rollback_marker(sql)
    assert "CREATE TABLE foo" in fwd
    assert ROLLBACK_MARKER not in fwd
    assert rb is not None and "DROP TABLE foo" in rb
    # No leading/trailing whitespace noise.
    assert rb == rb.strip()


def test_empty_rollback_body_is_none():
    sql = f"SELECT 1;\n{ROLLBACK_MARKER}\n   \n"
    fwd, rb = _split_rollback_marker(sql)
    assert fwd.startswith("SELECT 1")
    assert rb is None

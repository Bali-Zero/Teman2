"""P0-7 (zero-crash audit 2026-04-29) — duplicate migration prefix guard.

Two files sharing the same NNN_ prefix in `migrations_v2/` produce
undefined apply order: the runner picks one alphabetically and silently
skips the other. `_assert_unique_migration_numbers` turns that silent
skip into a `MigrationError`, both at deploy time and at runtime if a
future PR slips one in.

These tests don't touch the database — they exercise the disk-walking
helper in isolation, plus a smoke test against the real
`migrations_v2/` directory to catch regressions.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.db.migration_base import MigrationError
from backend.db.migration_manager import _assert_unique_migration_numbers


def _touch(dir_path: Path, name: str) -> Path:
    """Create an empty `.sql` file (assert helper only inspects filenames)."""
    p = dir_path / name
    p.touch()
    return p


def test_duplicate_prefix_raises(tmp_path):
    """Two files sharing the `001_` prefix → MigrationError with details."""
    files = [
        _touch(tmp_path, "001_first.sql"),
        _touch(tmp_path, "001_second.sql"),
        _touch(tmp_path, "002_unique.sql"),
    ]

    with pytest.raises(MigrationError) as excinfo:
        _assert_unique_migration_numbers(sorted(files))

    msg = str(excinfo.value)
    assert "Duplicate migration numbers" in msg
    assert "1:" in msg
    assert "001_first.sql" in msg
    assert "001_second.sql" in msg
    assert "P0-7" in msg


def test_unique_prefixes_pass(tmp_path):
    """Three files with distinct prefixes → no error."""
    files = [
        _touch(tmp_path, "001_a.sql"),
        _touch(tmp_path, "002_b.sql"),
        _touch(tmp_path, "003_c.sql"),
    ]

    # Should not raise.
    _assert_unique_migration_numbers(sorted(files))


def test_non_numeric_prefix_ignored(tmp_path):
    """Files without an `NNN_` prefix are not counted as duplicates."""
    files = [
        _touch(tmp_path, "001_real.sql"),
        _touch(tmp_path, "README.sql"),
        _touch(tmp_path, "stray.sql"),
    ]

    # Two non-numeric stems exist alongside one numeric — no collision.
    _assert_unique_migration_numbers(sorted(files))


def test_real_migrations_v2_has_no_duplicates():
    """Smoke test: the actual migrations_v2/ directory must stay clean.

    Canary that fails fast if a future PR ever lands a duplicate prefix
    without going through the CI guardrail (e.g. a direct push, or a
    force-push past branch protection).
    """
    real_dir = (
        Path(__file__).resolve().parents[2]
        / "db"
        / "migrations_v2"
    )
    if not real_dir.is_dir():
        pytest.skip(f"migrations_v2 dir not found at {real_dir}")

    sql_files = sorted(real_dir.glob("*.sql"))
    # Should not raise on the real directory after P0-7 cleanup.
    _assert_unique_migration_numbers(sql_files)

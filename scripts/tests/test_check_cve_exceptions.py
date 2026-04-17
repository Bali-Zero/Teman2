"""Tests for scripts/check_cve_exceptions.py — the pre-deploy CVE gate."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import check_cve_exceptions as mod  # type: ignore[import-not-found]


def _write(path: Path, content: str) -> None:
    path.write_text(dedent(content).lstrip())


@pytest.fixture
def today() -> date:
    return date(2026, 4, 18)


def test_empty_list_passes(tmp_path: Path, today: date) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(path, "exceptions: []\n")
    assert mod.check(path, today=today) == 0


def test_missing_file_fails(tmp_path: Path, today: date) -> None:
    path = tmp_path / "does_not_exist.yaml"
    assert mod.check(path, today=today) == 1


def test_expired_entry_fails(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00001
            package: example
            version: "1.0.0"
            reason: Upstream fix blocked on breaking change
            approved_by: zero
            approved_at: 2026-01-18
            expires_at: 2026-04-10
        """,
    )
    assert mod.check(path, today=today) == 1
    captured = capsys.readouterr()
    assert "CVE-2025-00001" in captured.err
    assert "expired" in captured.err


def test_non_expired_entry_passes(tmp_path: Path, today: date) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00002
            package: example
            version: "1.0.0"
            reason: Upstream fix blocked on breaking change
            approved_by: zero
            approved_at: 2026-04-01
            expires_at: 2026-06-01
        """,
    )
    assert mod.check(path, today=today) == 0


def test_missing_required_field_fails(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00003
            package: example
            version: "1.0.0"
            approved_by: zero
            approved_at: 2026-04-01
            expires_at: 2026-06-01
        """,
    )
    assert mod.check(path, today=today) == 1
    assert "reason" in capsys.readouterr().err


def test_window_exceeding_cap_fails(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00004
            package: example
            version: "1.0.0"
            reason: Deliberately abusive
            approved_by: zero
            approved_at: 2026-01-01
            expires_at: 2026-09-01
        """,
    )
    assert mod.check(path, today=today) == 1
    err = capsys.readouterr().err
    assert "cap" in err.lower() or "90" in err


def test_duplicate_cve_fails(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00005
            package: example
            version: "1.0.0"
            reason: Fix in progress
            approved_by: zero
            approved_at: 2026-04-01
            expires_at: 2026-06-01
          - cve_id: CVE-2025-00005
            package: example
            version: "1.0.0"
            reason: Fix in progress (second copy)
            approved_by: zero
            approved_at: 2026-04-01
            expires_at: 2026-06-01
        """,
    )
    assert mod.check(path, today=today) == 1
    assert "duplicate" in capsys.readouterr().err.lower()


def test_expires_before_approved_fails(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00006
            package: example
            version: "1.0.0"
            reason: Typo in dates
            approved_by: zero
            approved_at: 2026-04-10
            expires_at: 2026-04-01
        """,
    )
    assert mod.check(path, today=today) == 1
    assert "before" in capsys.readouterr().err.lower()


def test_warning_for_soon_to_expire(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    _write(
        path,
        """
        exceptions:
          - cve_id: CVE-2025-00007
            package: example
            version: "1.0.0"
            reason: Fix landing Monday
            approved_by: zero
            approved_at: 2026-03-01
            expires_at: 2026-04-20
        """,
    )
    assert mod.check(path, today=today) == 0  # warning only
    err = capsys.readouterr().err
    assert "CVE-2025-00007" in err


def test_malformed_yaml_fails(tmp_path: Path, today: date, capsys) -> None:
    path = tmp_path / "exceptions.yaml"
    path.write_text("exceptions: [this is: not valid\n")
    assert mod.check(path, today=today) == 1

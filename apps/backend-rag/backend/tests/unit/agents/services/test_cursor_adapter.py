"""Tests for CursorAdapter (S11 solidification).

Covers:
- narrow exception classes caught by subprocess wrappers
- graceful degradation when cursor CLI absent
- update/read .cursorrules file roundtrip
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.agents.services.cursor_adapter import CursorAdapter, get_cursor_adapter


@pytest.fixture
def tmp_adapter(tmp_path: Path) -> CursorAdapter:
    return CursorAdapter(project_root=tmp_path)


class TestCursorAdapterSubprocessFailures:
    """subprocess failures must be caught with narrow, typed exceptions and degrade gracefully."""

    def test_open_file_handles_file_not_found(self, tmp_adapter: CursorAdapter) -> None:
        with patch(
            "backend.agents.services.cursor_adapter.subprocess.run",
            side_effect=FileNotFoundError("cursor not installed"),
        ):
            assert tmp_adapter.open_file("/tmp/x.py") is False

    def test_open_file_handles_timeout(self, tmp_adapter: CursorAdapter) -> None:
        with patch(
            "backend.agents.services.cursor_adapter.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="cursor", timeout=10),
        ):
            assert tmp_adapter.open_file("/tmp/x.py") is False

    def test_open_folder_handles_oserror(self, tmp_adapter: CursorAdapter) -> None:
        with patch(
            "backend.agents.services.cursor_adapter.subprocess.run",
            side_effect=OSError("permission denied"),
        ):
            assert tmp_adapter.open_folder("/tmp") is False

    def test_diff_files_handles_subprocess_error(self, tmp_adapter: CursorAdapter) -> None:
        with patch(
            "backend.agents.services.cursor_adapter.subprocess.run",
            side_effect=subprocess.SubprocessError("generic"),
        ):
            assert tmp_adapter.diff_files("a", "b") is None

    def test_is_available_false_when_cursor_missing(self, tmp_adapter: CursorAdapter) -> None:
        with patch(
            "backend.agents.services.cursor_adapter.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            assert tmp_adapter.is_available() is False

    def test_open_file_does_not_swallow_keyboard_interrupt(self, tmp_adapter: CursorAdapter) -> None:
        """KeyboardInterrupt must propagate — it's not a subprocess error."""
        with patch(
            "backend.agents.services.cursor_adapter.subprocess.run",
            side_effect=KeyboardInterrupt(),
        ):
            with pytest.raises(KeyboardInterrupt):
                tmp_adapter.open_file("/tmp/x.py")


class TestCursorAdapterRulesIO:
    """.cursorrules file I/O failures must be caught narrowly and logged."""

    def test_update_rules_writes_file(self, tmp_adapter: CursorAdapter) -> None:
        ok = tmp_adapter.update_cursor_rules("- be precise\n")
        assert ok is True
        assert tmp_adapter.cursor_rules_file.read_text() == "- be precise\n"

    def test_update_rules_handles_oserror(self, tmp_adapter: CursorAdapter) -> None:
        with patch("builtins.open", side_effect=OSError("disk full")):
            assert tmp_adapter.update_cursor_rules("x") is False

    def test_read_rules_returns_none_if_missing(self, tmp_adapter: CursorAdapter) -> None:
        assert tmp_adapter.read_cursor_rules() is None

    def test_read_rules_handles_oserror(self, tmp_adapter: CursorAdapter) -> None:
        tmp_adapter.cursor_rules_file.write_text("hi")
        with patch("builtins.open", side_effect=OSError("i/o error")):
            assert tmp_adapter.read_cursor_rules() is None


def test_singleton_reused(tmp_path: Path) -> None:
    import backend.agents.services.cursor_adapter as mod

    mod._cursor_adapter = None  # reset
    first = get_cursor_adapter(tmp_path)
    second = get_cursor_adapter(tmp_path)
    assert first is second

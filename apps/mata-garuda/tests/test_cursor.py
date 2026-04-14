"""Tests for bridge cursor — atomic file read/write."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mata_garuda.bridge.cursor import BridgeCursor


def test_cursor_read_missing_file_returns_zero(tmp_path: Path):
    """Reading a non-existent cursor file returns 0 (start from beginning)."""
    cursor = BridgeCursor(tmp_path / "cursor.json")
    assert cursor.read() == 0


def test_cursor_write_then_read(tmp_path: Path):
    """Write then read returns the value."""
    cursor = BridgeCursor(tmp_path / "cursor.json")
    cursor.write(1234)
    assert cursor.read() == 1234


def test_cursor_write_overwrites(tmp_path: Path):
    """Subsequent writes overwrite the value."""
    cursor = BridgeCursor(tmp_path / "cursor.json")
    cursor.write(1234)
    cursor.write(5678)
    assert cursor.read() == 5678


def test_cursor_write_creates_parent_dir(tmp_path: Path):
    """Write creates parent directories if missing."""
    cursor = BridgeCursor(tmp_path / "deep" / "nested" / "cursor.json")
    cursor.write(42)
    assert cursor.read() == 42


def test_cursor_atomic_write_no_partial_file(tmp_path: Path):
    """Atomic write uses tmp file + rename — no partial files visible."""
    cursor_path = tmp_path / "cursor.json"
    cursor = BridgeCursor(cursor_path)
    cursor.write(999)
    # No .tmp file left behind
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []
    # Final file is valid JSON
    data = json.loads(cursor_path.read_text())
    assert data == {"last_id": 999}


def test_cursor_corrupt_file_returns_zero(tmp_path: Path):
    """A corrupt cursor file returns 0 (safe degradation)."""
    cursor_path = tmp_path / "cursor.json"
    cursor_path.write_text("not valid json {{{")
    cursor = BridgeCursor(cursor_path)
    assert cursor.read() == 0

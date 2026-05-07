"""Tests for ActiveFlag — file-based kill switch for W2 dispatch."""
from pathlib import Path

import pytest

from organism.supervisor.active_flag import ActiveFlag


def test_active_flag_default_is_inactive(tmp_path: Path) -> None:
    flag = ActiveFlag(path=tmp_path / "active.flag")
    assert flag.is_active() is False


def test_active_flag_file_with_one_is_active(tmp_path: Path) -> None:
    p = tmp_path / "active.flag"
    p.write_text("1")
    flag = ActiveFlag(path=p)
    assert flag.is_active() is True


def test_active_flag_file_with_zero_is_inactive(tmp_path: Path) -> None:
    p = tmp_path / "active.flag"
    p.write_text("0")
    flag = ActiveFlag(path=p)
    assert flag.is_active() is False


def test_active_flag_file_empty_is_inactive(tmp_path: Path) -> None:
    p = tmp_path / "active.flag"
    p.write_text("")
    flag = ActiveFlag(path=p)
    assert flag.is_active() is False


def test_active_flag_file_with_whitespace_one_is_active(tmp_path: Path) -> None:
    p = tmp_path / "active.flag"
    p.write_text(" 1\n")
    flag = ActiveFlag(path=p)
    assert flag.is_active() is True


def test_active_flag_re_reads_on_each_call(tmp_path: Path) -> None:
    """Operator flips the file with `echo 1 >`; daemon must NOT cache."""
    p = tmp_path / "active.flag"
    flag = ActiveFlag(path=p)
    assert flag.is_active() is False
    p.write_text("1")
    assert flag.is_active() is True
    p.write_text("0")
    assert flag.is_active() is False

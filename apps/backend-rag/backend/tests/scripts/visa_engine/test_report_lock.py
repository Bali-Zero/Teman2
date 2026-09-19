"""Guilt tests for Slice B2''-a: the exclusive report lock + atomic JSON write.

Every clause about PROCESSES (two writers racing, a SIGKILL mid-write) is proved with real
subprocesses, synchronised through sentinel files on disk -- never a bare sleep as the only
sync. Clauses about the context manager's own mechanics (release on normal exit / on an
exception) run in-process, since no second process is needed to observe them.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from backend.scripts.visa_engine.report_lock import ReportLock, ReportLockError, atomic_write_json

_REPO_ROOT_ENV = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[4])}

_WINNER_SCRIPT = """
import sys, time
from pathlib import Path
from backend.scripts.visa_engine.report_lock import ReportLock, atomic_write_json

report = Path(sys.argv[1])
ready_file = Path(sys.argv[2])
go_file = Path(sys.argv[3])

with ReportLock(report):
    atomic_write_json(report, {"owner": "winner", "stage": "start"})
    ready_file.write_text("ready")
    while not go_file.exists():
        time.sleep(0.02)
    atomic_write_json(report, {"owner": "winner", "stage": "done"})
"""

_LOSER_SCRIPT = """
import json, sys
from pathlib import Path
from backend.scripts.visa_engine.report_lock import ReportLock, ReportLockError

report = Path(sys.argv[1])
out_file = Path(sys.argv[2])
try:
    with ReportLock(report):
        out_file.write_text(json.dumps({"acquired": True}))
except ReportLockError as exc:
    out_file.write_text(json.dumps({"acquired": False, "message": str(exc)}))
"""

_HOLD_AND_WRITE_SCRIPT = """
import sys, time
from pathlib import Path
from backend.scripts.visa_engine.report_lock import ReportLock, atomic_write_json

report = Path(sys.argv[1])
ready_file = Path(sys.argv[2])

with ReportLock(report):
    atomic_write_json(report, {"stage": "first", "rows": 1})
    ready_file.write_text("ready")
    time.sleep(30)
    atomic_write_json(report, {"stage": "second", "rows": 2})
"""

_SLEEP_SCRIPT = "import time; time.sleep(30)"


def _wait_for(path: Path, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {path} to appear")
        time.sleep(0.02)


def _run_script(script: str, *args: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-c", script, *args],
        env=_REPO_ROOT_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _spawn_dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=10)
    return proc.pid


# ---------------------------------------------------------------------------
# Process clauses -- real subprocesses, sentinel-file synchronised
# ---------------------------------------------------------------------------


def test_two_processes_race_the_loser_refuses_and_the_winners_file_is_intact(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    ready_file = tmp_path / "winner-ready"
    go_file = tmp_path / "winner-go"
    loser_out = tmp_path / "loser-out.json"

    winner = _run_script(_WINNER_SCRIPT, str(report), str(ready_file), str(go_file))
    try:
        _wait_for(ready_file)

        loser = _run_script(_LOSER_SCRIPT, str(report), str(loser_out))
        loser_rc = loser.wait(timeout=10)
        assert loser_rc == 0

        result = json.loads(loser_out.read_text())
        assert result["acquired"] is False
        assert result["message"].count("\n") == 0  # ONE line, never a traceback
        assert "another run owns" in result["message"]
        assert str(winner.pid) in result["message"]

        go_file.write_text("go")
        winner_rc = winner.wait(timeout=10)
        assert winner_rc == 0
    finally:
        if winner.poll() is None:
            winner.kill()
            winner.wait(timeout=10)

    assert not report.with_name(report.name + ".lock").exists()
    assert json.loads(report.read_text()) == {"owner": "winner", "stage": "done"}


def test_sigkill_of_the_holder_mid_write_leaves_a_parseable_prior_file_and_the_stale_path(
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.json"
    ready_file = tmp_path / "holder-ready"

    holder = _run_script(_HOLD_AND_WRITE_SCRIPT, str(report), str(ready_file))
    try:
        _wait_for(ready_file)
        os.kill(holder.pid, signal.SIGKILL)
        rc = holder.wait(timeout=10)
        assert rc == -signal.SIGKILL
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=10)

    # The prior write survives intact -- no partial/truncated file, no leftover temp
    # replacing it, because atomic_write_json only ever replaces via a completed rename.
    assert json.loads(report.read_text()) == {"stage": "first", "rows": 1}

    lock_path = report.with_name(report.name + ".lock")
    assert lock_path.exists()  # SIGKILL bypasses __exit__: the lock is left behind

    # A fresh lock attempt takes the STALE path (dead pid), never the live-owner refusal,
    # and never a deadlock: an explicit, one-line, breakable refusal.
    with pytest.raises(ReportLockError, match="stale lock"):
        ReportLock(report).acquire()


# ---------------------------------------------------------------------------
# Context-manager mechanics -- no second process needed to observe these
# ---------------------------------------------------------------------------


def test_lock_is_released_on_normal_exit(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")

    with ReportLock(report):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_lock_is_released_on_an_exception_inside_the_locked_section(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")

    with pytest.raises(RuntimeError, match="boom"):
        with ReportLock(report):
            assert lock_path.exists()
            raise RuntimeError("boom")

    assert not lock_path.exists()


def test_stale_lock_is_refused_without_break_stale(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")
    dead_pid = _spawn_dead_pid()
    lock_path.write_text(json.dumps({"pid": dead_pid, "started_at": "then"}), encoding="utf-8")

    with pytest.raises(ReportLockError) as excinfo:
        ReportLock(report).acquire()

    assert "stale lock" in str(excinfo.value)
    assert "--break-stale-lock" in str(excinfo.value)
    assert lock_path.exists()  # untouched -- refusal doesn't remove it


def test_break_stale_lock_removes_it_and_proceeds(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")
    dead_pid = _spawn_dead_pid()
    lock_path.write_text(json.dumps({"pid": dead_pid, "started_at": "then"}), encoding="utf-8")

    lock = ReportLock(report, break_stale=True)
    lock.acquire()
    try:
        saved = json.loads(lock_path.read_text())
        assert saved["pid"] == os.getpid()
        assert saved["pid"] != dead_pid
    finally:
        lock.release()

    assert not lock_path.exists()


def test_break_stale_lock_is_refused_when_the_pid_is_alive(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    lock_path = report.with_name(report.name + ".lock")

    holder = subprocess.Popen([sys.executable, "-c", _SLEEP_SCRIPT])
    try:
        lock_path.write_text(json.dumps({"pid": holder.pid, "started_at": "now"}), encoding="utf-8")

        with pytest.raises(ReportLockError) as excinfo:
            ReportLock(report, break_stale=True).acquire()

        assert "another run owns" in str(excinfo.value)
        assert str(holder.pid) in str(excinfo.value)
        assert lock_path.exists()  # a live pid trumps break_stale -- never stolen
    finally:
        holder.kill()
        holder.wait(timeout=10)


# ---------------------------------------------------------------------------
# atomic_write_json -- basic correctness, no leftover temp file
# ---------------------------------------------------------------------------


def test_atomic_write_json_writes_readable_json_and_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "report.json"

    atomic_write_json(target, {"b": 2, "a": 1})

    assert json.loads(target.read_text()) == {"b": 2, "a": 1}
    leftovers = [p for p in target.parent.iterdir() if p != target]
    assert leftovers == []

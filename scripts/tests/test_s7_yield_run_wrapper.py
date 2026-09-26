"""Every exit path of scripts/s7-yield-run.sh writes the heartbeat it promises.

The wrapper runs in a sandbox: HOME and the repo root point at tmp_path, and the
payload is a stub that exits with a chosen code. Nothing touches the real
~/.organism, the database or Ollama.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "scripts" / "s7-yield-run.sh"
HEARTBEAT_LIB = REPO / "scripts" / "lib" / "heartbeat.sh"
ORGAN_ID = "pro.s7_yield_weekly"


def _sandbox(tmp_path: Path, payload_rc: int | None, with_lib: bool = True) -> tuple[Path, Path]:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    (repo / "scripts" / "lib").mkdir(parents=True)
    home.mkdir()
    if with_lib:
        shutil.copy(HEARTBEAT_LIB, repo / "scripts" / "lib" / "heartbeat.sh")
    if payload_rc is not None:
        (repo / "scripts" / "s7_yield_draft_local.py").write_text(
            f"import sys\nsys.exit({payload_rc})\n", encoding="utf-8"
        )
    return home, repo


def _run(home: Path, repo: Path, **extra: str) -> tuple[int, dict | None]:
    env = {"HOME": str(home), "S7_YIELD_REPO_ROOT": str(repo), **extra}
    proc = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True)
    hb_path = home / ".organism" / "last_seen" / f"{ORGAN_ID}.json"
    hb = json.loads(hb_path.read_text(encoding="utf-8")) if hb_path.exists() else None
    return proc.returncode, hb


@pytest.mark.parametrize(
    "extra",
    [{"S7_YIELD_ENABLED": "false"}, {"S7_YIELD_OFF": "1"}],
    ids=["enabled-false", "legacy-off"],
)
def test_kill_switch_writes_disabled_and_never_runs_payload(tmp_path, extra):
    home, repo = _sandbox(tmp_path, payload_rc=7)
    rc, hb = _run(home, repo, **extra)
    assert rc == 0
    assert hb is not None and hb["status"] == "disabled"


def test_enabled_true_is_not_a_kill_switch(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=0)
    rc, hb = _run(home, repo, S7_YIELD_ENABLED="true", S7_YIELD_OFF="0")
    assert rc == 0
    assert hb is not None and hb["status"] == "ok"


def test_payload_success_writes_ok(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=0)
    rc, hb = _run(home, repo)
    assert rc == 0
    assert hb is not None and hb["status"] == "ok" and hb["note"] == "rc=0"


def test_payload_failure_writes_error_and_propagates_rc(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=3)
    rc, hb = _run(home, repo)
    assert rc == 3
    assert hb is not None and hb["status"] == "error" and hb["note"] == "rc=3"


def test_missing_payload_writes_error(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=None)
    rc, hb = _run(home, repo)
    assert rc == 1
    assert hb is not None and hb["status"] == "error"


def test_missing_heartbeat_library_is_logged_and_keeps_the_exit_code(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=3, with_lib=False)
    env = {"HOME": str(home), "S7_YIELD_REPO_ROOT": str(repo)}
    proc = subprocess.run(["/bin/bash", str(WRAPPER)], env=env, capture_output=True, text=True)
    assert proc.returncode == 3
    assert "heartbeat library missing" in proc.stderr
    assert not (home / ".organism" / "last_seen" / f"{ORGAN_ID}.json").exists()


def _pidfile(home: Path) -> Path:
    return home / ".organism" / "run" / f"{ORGAN_ID}.pid"


def test_live_previous_run_is_skipped_with_a_warning(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=None)
    marker = tmp_path / "payload-ran"
    (repo / "scripts" / "s7_yield_draft_local.py").write_text(
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('1')\n", encoding="utf-8"
    )
    _pidfile(home).parent.mkdir(parents=True)
    _pidfile(home).write_text(str(os.getpid()), encoding="utf-8")
    rc, hb = _run(home, repo)
    assert rc == 0
    assert hb is not None and hb["status"] == "warning"
    assert not marker.exists()
    assert _pidfile(home).read_text(encoding="utf-8") == str(os.getpid())


def test_stale_pidfile_is_reclaimed_and_released(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=0)
    dead = subprocess.Popen(["/bin/sh", "-c", "exit 0"])
    dead.wait()
    _pidfile(home).parent.mkdir(parents=True)
    _pidfile(home).write_text(str(dead.pid), encoding="utf-8")
    rc, hb = _run(home, repo)
    assert rc == 0
    assert hb is not None and hb["status"] == "ok"
    assert not _pidfile(home).exists()


def test_sigterm_stops_the_payload_and_writes_error(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=None)
    started = tmp_path / "started"
    ended = tmp_path / "ended"
    (repo / "scripts" / "s7_yield_draft_local.py").write_text(
        "import os, pathlib, time\n"
        f"pathlib.Path({str(started)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(20)\n"
        f"pathlib.Path({str(ended)!r}).write_text('1')\n",
        encoding="utf-8",
    )
    env = {"HOME": str(home), "S7_YIELD_REPO_ROOT": str(repo)}
    wrapper = subprocess.Popen(["/bin/bash", str(WRAPPER)], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    while not started.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert started.exists(), "payload never started"
    payload_pid = int(started.read_text(encoding="utf-8"))
    wrapper.send_signal(signal.SIGTERM)
    assert wrapper.wait(timeout=10) == 143
    with pytest.raises(ProcessLookupError):
        os.kill(payload_pid, 0)
    assert not ended.exists()
    hb = json.loads((home / ".organism" / "last_seen" / f"{ORGAN_ID}.json").read_text(encoding="utf-8"))
    assert hb["status"] == "error" and hb["note"] == "signal TERM"
    assert not _pidfile(home).exists()

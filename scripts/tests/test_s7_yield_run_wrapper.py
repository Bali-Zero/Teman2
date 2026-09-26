"""Every exit path of scripts/s7-yield-run.sh writes the heartbeat it promises.

The wrapper runs in a sandbox: HOME and the repo root point at tmp_path, and the
payload is a stub that exits with a chosen code. Nothing touches the real
~/.organism, the database or Ollama.
"""
from __future__ import annotations

import json
import shutil
import subprocess
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


def test_missing_heartbeat_library_does_not_change_the_exit_code(tmp_path):
    home, repo = _sandbox(tmp_path, payload_rc=3, with_lib=False)
    rc, hb = _run(home, repo)
    assert rc == 3
    assert hb is None

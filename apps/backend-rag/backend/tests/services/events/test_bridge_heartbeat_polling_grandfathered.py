"""Polling-based watchdog tests for pg-organism-bridge.

Symbiosis L3 grandfathered exception: watchdog uses 5min polling instead
of durable XADD heartbeat consumer. Heartbeat-based watchdog = follow-up PR.

The watchdog itself lives outside the Python backend, as a launchd-run
shell script (``infra/scripts/pg-organism-bridge-watchdog.sh``) — there is
no Python implementation to import. These tests exercise the REAL script
(copied byte-for-byte into an isolated sandbox, never modified) via
``subprocess``, with:

- ``HOME`` pointed at a throwaway tmp dir, so nothing touches the real
  ``~/.organism``/``~/logs``/``~/.agent`` state.
- ``PATH`` prepended with a fake ``redis-cli`` stub, so no live Redis
  connection is required and the stream-lag branch is deterministic.
- no real Telegram credentials anywhere in the sandboxed environment, and
  the script's own ``tg_notify.py`` gateway lookup (relative to its own
  path) is made to fail closed by copying the script into a directory tree
  that does not contain that gateway — so ``telegram_backup`` can only ever
  hit its "gateway not found, alert NOT sent" branch, never the network.

The script writes its primary alert to ``$HOME/.organism/alerts/
bridge-watchdog.jsonl`` (Telegram is explicitly a "best-effort backup, not
the primary path" per the script's own header) — that JSONL file is what
these tests assert on.

Test: apps/backend-rag/backend/tests/services/events/test_bridge_heartbeat_polling_grandfathered.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[6]
_WATCHDOG_SCRIPT = _REPO_ROOT / "infra/scripts/pg-organism-bridge-watchdog.sh"
_BRIDGE_MARKER = "pg-to-organism-bridge.py"  # substring pgrep -f matches against

_FAKE_REDIS_CLI = """#!/bin/bash
# Test stub: always report the last organism:events entry as ~40min old,
# regardless of the real XREVRANGE args passed to it — deterministic,
# no live Redis required.
NOW_MS=$(( $(date +%s) * 1000 ))
LAG_MS=$(( 40 * 60 * 1000 ))
echo "$((NOW_MS - LAG_MS))-0"
"""

pytestmark = pytest.mark.skipif(
    not (shutil.which("bash") and shutil.which("pgrep") and _WATCHDOG_SCRIPT.is_file()),
    reason="requires bash + pgrep + the pg-organism-bridge-watchdog.sh script on disk",
)


def _sandbox(tmp_path: Path) -> Path:
    """Copy the real watchdog script (unmodified) into an isolated tree."""
    script_dir = tmp_path / "infra/scripts"
    script_dir.mkdir(parents=True)
    copy = script_dir / _WATCHDOG_SCRIPT.name
    shutil.copy(_WATCHDOG_SCRIPT, copy)
    copy.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_redis_cli = fake_bin / "redis-cli"
    fake_redis_cli.write_text(_FAKE_REDIS_CLI)
    fake_redis_cli.chmod(0o755)

    return copy


def _run_watchdog(copy: Path, fake_bin: Path, fake_home: Path) -> Path:
    fake_home.mkdir(parents=True)
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    subprocess.run(["bash", str(copy)], env=env, capture_output=True, text=True, timeout=30)
    return fake_home / ".organism/alerts/bridge-watchdog.jsonl"


def test_watchdog_alerts_when_bridge_pid_missing(tmp_path: Path) -> None:
    """Polling watchdog detects missing bridge PID and raises a critical alert."""
    copy = _sandbox(tmp_path)
    alerts_path = _run_watchdog(copy, tmp_path / "bin", tmp_path / "home")

    assert alerts_path.exists(), "expected an organism alert to be written"
    alert = json.loads(alerts_path.read_text().splitlines()[0])
    assert alert["severity"] == "critical"
    assert "NOT RUNNING" in alert["message"]


def test_watchdog_alerts_when_redis_stream_lag_exceeds_30min(tmp_path: Path) -> None:
    """Polling watchdog alerts when organism:events stream stale > 30min."""
    copy = _sandbox(tmp_path)

    # Fake bridge process: its argv contains the marker pgrep -f matches on.
    fake_bridge = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(8)", _BRIDGE_MARKER]
    )
    try:
        time.sleep(0.5)  # let it register with the process table
        alerts_path = _run_watchdog(copy, tmp_path / "bin", tmp_path / "home")
    finally:
        fake_bridge.terminate()
        try:
            fake_bridge.wait(timeout=5)
        except subprocess.TimeoutExpired:
            fake_bridge.kill()

    assert alerts_path.exists(), "expected an organism alert to be written"
    alert = json.loads(alerts_path.read_text().splitlines()[0])
    assert alert["severity"] == "warning"
    assert "STALE" in alert["message"]

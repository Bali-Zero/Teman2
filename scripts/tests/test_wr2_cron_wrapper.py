"""Tests for scripts/wr2-cron-wrapper.sh's pre-flight guards.

Context (2026-07-17 diagnostic): the two guards below (DATABASE_URL_LOCAL
missing, pg-proxy unreachable) used to die with an honest stderr line but NO
heartbeat sidecar — a reconciler/monitor reading only
~/.organism/last_seen/*.json would never learn the guard tripped, while the
launchd log for that job DID get the line. Log and sidecar could disagree
(cicatrix family #2, "esiste != armato"). The fix makes both guards write an
organism_heartbeat (via scripts/lib/heartbeat.sh) in the same breath as the
stderr echo, so they always agree.

Isolation: HOME is redirected to tmp_path so the heartbeat file lands there,
never touching the real ~/.organism/last_seen/ on the machine running the
test (W96 lesson: tests must never write production state).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _REPO_ROOT / "scripts" / "wr2-cron-wrapper.sh"


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "NUZANTARA_REPO_ROOT": str(_REPO_ROOT),
            # Point at a file that does not exist so the wrapper's own
            # secrets-sourcing step is a deterministic no-op regardless of
            # what exists on the machine actually running this test.
            "NUZANTARA_SECRETS": str(tmp_path / "no-such-secrets.env"),
        }
    )
    # Guard 1 is keyed on DATABASE_URL_LOCAL specifically — make sure the
    # real environment (if this test runs on a dev machine with it exported)
    # cannot leak in and mask the condition under test.
    env.pop("DATABASE_URL_LOCAL", None)
    env.pop("DATABASE_URL", None)
    return env


def _heartbeat(tmp_path: Path, organ_id: str) -> dict:
    path = tmp_path / ".organism" / "last_seen" / f"{organ_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_database_url_local_writes_heartbeat_matching_log(tmp_path) -> None:
    result = subprocess.run(
        ["bash", str(_WRAPPER), "test.fake.module"],
        cwd=_REPO_ROOT,
        env=_base_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 74
    assert "DATABASE_URL_LOCAL not set" in result.stderr

    hb = _heartbeat(tmp_path, "pro.wr2_wrapper_guard.test.fake.module")
    assert hb["status"] == "error"
    # Same wording as the stderr line above — log and sidecar must agree.
    assert "DATABASE_URL_LOCAL not set" in hb["note"]


def test_missing_module_arg_still_fails_usage_before_any_heartbeat(tmp_path) -> None:
    """Sanity: the pre-existing usage guard (line 27-30) is untouched by the
    heartbeat addition — no organ id can even be computed without a module
    argument, so nothing should be written."""
    result = subprocess.run(
        ["bash", str(_WRAPPER)],
        cwd=_REPO_ROOT,
        env=_base_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 64
    assert "usage:" in result.stderr
    assert not (tmp_path / ".organism").exists()


def _port_15432_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 15432), timeout=0.5):
            return True
    except OSError:
        return False


def test_pg_proxy_unreachable_writes_heartbeat_matching_log(tmp_path) -> None:
    """Guard 2 (pg-proxy down) — only meaningful when 15432 is genuinely
    closed on the machine running the test. This repo's own pg-proxy may be
    up on a dev box (Pro), and forcing it down as a side effect of a unit
    test would disrupt other live crons sharing that proxy — so this test
    self-skips rather than faking network state."""
    if _port_15432_reachable():
        pytest.skip("127.0.0.1:15432 is reachable on this machine — cannot "
                     "safely simulate pg-proxy-down without disrupting a "
                     "real proxy other crons may depend on")

    env = _base_env(tmp_path)
    # Bypass guard 1 directly (no secrets file needed — set it straight in
    # the child's env) so guard 2 is the one actually exercised.
    env["DATABASE_URL_LOCAL"] = "postgres://user:pass@127.0.0.1:15432/db?sslmode=disable"

    result = subprocess.run(
        ["bash", str(_WRAPPER), "test.fake.module"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 74
    assert "cannot reach 127.0.0.1:15432" in result.stderr

    hb = _heartbeat(tmp_path, "pro.wr2_wrapper_guard.test.fake.module")
    assert hb["status"] == "error"
    assert "15432" in hb["note"]


def test_repo_root_is_exported_before_either_guard_can_exit(tmp_path) -> None:
    """Regression pin for the 2026-07-27 finding (task #64): REPO_ROOT was
    resolved for the wrapper's own `cd` but never re-exported, so every
    python module reading NUZANTARA_REPO_ROOT via os.environ always fell
    through to its own file-relative guess — confirmed live on
    m13_weekly.py, which wrote its weekly report to apps/research/... instead
    of research/... for weeks.

    Both existing guards above (DATABASE_URL_LOCAL missing, pg-proxy down)
    can exit the wrapper before it ever reaches `exec ... python -m
    $MODULE`, so there is no way to observe the export by inspecting the
    child process's environment through a real end-to-end run without a live
    Postgres proxy. This is a static check instead: the export must appear
    in the source BEFORE both guard blocks, so the fix holds regardless of
    which guard (if any) later exits — the exact invariant this fix needs.
    A guard reordered above the export in the future would fail this test
    even though every existing behavioral test above would still pass."""
    lines = _WRAPPER.read_text(encoding="utf-8").splitlines()

    export_idx = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("export NUZANTARA_REPO_ROOT=")),
        None,
    )
    guard1_idx = next(
        (i for i, line in enumerate(lines) if "DATABASE_URL_LOCAL not set" in line), None
    )
    guard2_idx = next(
        (i for i, line in enumerate(lines) if "cannot reach 127.0.0.1:15432" in line), None
    )

    assert export_idx is not None, "export NUZANTARA_REPO_ROOT= line not found in the wrapper"
    assert guard1_idx is not None and guard2_idx is not None, (
        "one of the two known guards moved or was renamed — update this test's anchors"
    )
    assert export_idx < guard1_idx
    assert export_idx < guard2_idx

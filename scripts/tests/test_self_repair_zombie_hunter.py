"""Self-repair blind-spot #3 — zombie-hunter must persist exit-code history.

Audit 2026-04-19 finding: the current zombie-hunter only detects an agent as
zombie when it is *currently stuck* (running with CPU ~0%). A LaunchAgent that
crashes, restarts, crashes again (crash-loop) was missed because each snapshot
looked healthy — the process WAS running, the bug was in the exit history.

New rule: any agent whose last 3 runs returned `exit_code != 0` is a zombie,
even if it's running right now. State lives in
`~/.agent/decisions/state/launchd_bad_exits.json` — zombie-hunter already
writes here; this patch teaches it to READ the file and accumulate a rolling
window.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Make scripts/ importable so `from sentinel_lib.zombie_hunter import ...` works.
import sys
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "scripts"))

from sentinel_lib import zombie_hunter  # noqa: E402


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    """Redirect launchd_bad_exits.json into tmp_path for isolation."""
    path = tmp_path / "launchd_bad_exits.json"
    monkeypatch.setattr(zombie_hunter, "STATE_FILE", path)
    return path


def test_record_run_accumulates_history(state_file: Path) -> None:
    """Each call records the exit code into a bounded rolling window per label."""
    zombie_hunter.record_run("com.example.alpha", exit_code=1)
    zombie_hunter.record_run("com.example.alpha", exit_code=2)
    zombie_hunter.record_run("com.example.alpha", exit_code=0)

    data = json.loads(state_file.read_text())
    alpha_history = data["history"]["com.example.alpha"]
    assert [e["exit_code"] for e in alpha_history] == [1, 2, 0]


def test_rolling_window_caps_at_n(state_file: Path) -> None:
    """History must be capped (default N=10) so the state file doesn't grow
    unbounded — this is the whole reason a historical criterion is viable."""
    for code in range(15):
        zombie_hunter.record_run("com.example.beta", exit_code=code)
    data = json.loads(state_file.read_text())
    assert len(data["history"]["com.example.beta"]) == zombie_hunter.HISTORY_WINDOW


def test_zombie_by_three_consecutive_bad_exits_even_if_running(
    state_file: Path,
) -> None:
    """Core criterion: 3 consecutive non-zero exits = zombie, independent of
    current state (`running`, `paused`, anything)."""
    zombie_hunter.record_run("com.example.gamma", exit_code=2)
    zombie_hunter.record_run("com.example.gamma", exit_code=3)
    zombie_hunter.record_run("com.example.gamma", exit_code=1)

    zombies = zombie_hunter.detect_zombies(current_state={"com.example.gamma": "running"})
    labels = [z.label for z in zombies]
    assert "com.example.gamma" in labels
    z = next(z for z in zombies if z.label == "com.example.gamma")
    assert z.reason.startswith("3 consecutive bad exits")
    assert z.consecutive_bad_exits == 3
    assert z.currently_running is True  # new: flags crash-loop, not stuck proc


def test_success_resets_bad_streak(state_file: Path) -> None:
    """A single exit_code=0 must break the bad-exit streak (otherwise a long
    healthy service with one past flake would stay flagged forever)."""
    zombie_hunter.record_run("com.example.delta", exit_code=1)
    zombie_hunter.record_run("com.example.delta", exit_code=1)
    zombie_hunter.record_run("com.example.delta", exit_code=0)  # recovery
    zombie_hunter.record_run("com.example.delta", exit_code=1)

    zombies = zombie_hunter.detect_zombies()
    labels = [z.label for z in zombies]
    assert "com.example.delta" not in labels, (
        "A successful run must reset the bad-exit streak"
    )


def test_missing_state_file_is_low_severity_not_crash(
    tmp_path: Path, monkeypatch
) -> None:
    """If the state file doesn't exist yet (first run, fresh machine), calls
    must return empty — never raise. Backward-compat for the self-repair
    pipeline."""
    monkeypatch.setattr(
        zombie_hunter, "STATE_FILE", tmp_path / "never-created.json"
    )
    # Neither call should raise.
    assert zombie_hunter.detect_zombies() == []
    # And `record_run` should create the file lazily.
    zombie_hunter.record_run("com.example.fresh", exit_code=0)
    assert (tmp_path / "never-created.json").exists()

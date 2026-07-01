"""Tests for the flock + operating-window gates in run_with_heartbeat.

These gates absorb the W7 flock single-instance + gap_consumer 06-22 window that
the 7 class-C ~/scripts shell wrappers carried, so those crons can drop the
wrapper and run the venv python directly (W84 TCC-safe + repo-tracked).
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

from mata_garuda.workers import heartbeat as hb


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    # never touch a real ~/.organism sidecar dir; never inherit MG_* from the shell
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path / "last_seen"))
    monkeypatch.delenv("MG_WINDOW", raising=False)
    monkeypatch.delenv("MG_FLOCK", raising=False)
    yield


def test_no_gates_runs_normally():
    """No MG_* env → fn runs, exit code passed through (full back-compat)."""
    calls = []
    rc = hb.run_with_heartbeat("t.nogate", lambda: (calls.append(1), 0)[1])
    assert rc == 0
    assert calls == [1]


def test_window_open_runs(monkeypatch):
    monkeypatch.setenv("MG_WINDOW", "0-24")  # always open
    calls = []
    rc = hb.run_with_heartbeat("t.winopen", lambda: (calls.append(1), 0)[1])
    assert rc == 0 and calls == [1]


def test_window_closed_skips(monkeypatch):
    monkeypatch.setenv("MG_WINDOW", "0-0")  # always closed
    calls = []
    rc = hb.run_with_heartbeat("t.winclosed", lambda: (calls.append(1), 0)[1])
    assert rc == 0
    assert calls == []  # fn NEVER invoked


def test_window_malformed_fails_open(monkeypatch):
    monkeypatch.setenv("MG_WINDOW", "garbage")  # unparsable → no gate
    calls = []
    rc = hb.run_with_heartbeat("t.winbad", lambda: (calls.append(1), 0)[1])
    assert rc == 0 and calls == [1]


def test_window_closed_helper():
    with mock.patch.object(hb, "datetime") as dt:
        dt.now.return_value.hour = 23
        assert hb._window_closed("6-22") is True   # 23 outside [6,22)
        dt.now.return_value.hour = 10
        assert hb._window_closed("6-22") is False  # 10 inside


def test_flock_free_runs(monkeypatch):
    monkeypatch.setenv("MG_FLOCK", "test-free-lock")
    calls = []
    rc = hb.run_with_heartbeat("t.flockfree", lambda: (calls.append(1), 0)[1])
    assert rc == 0 and calls == [1]


def test_flock_held_skips_75(monkeypatch):
    """A second run while the lock is held returns 75 and never runs fn."""
    monkeypatch.setenv("MG_FLOCK", "test-held-lock")
    holder = hb._acquire_flock("test-held-lock")
    assert holder is not None  # first acquire succeeds
    try:
        calls = []
        rc = hb.run_with_heartbeat("t.flockheld", lambda: (calls.append(1), 0)[1])
        assert rc == 75
        assert calls == []  # fn NEVER invoked while lock held
    finally:
        holder.close()


def test_flock_released_after_run(monkeypatch):
    """After a gated run completes, the lock is free for the next run."""
    monkeypatch.setenv("MG_FLOCK", "test-serial-lock")
    rc1 = hb.run_with_heartbeat("t.serial1", lambda: 0)
    rc2 = hb.run_with_heartbeat("t.serial2", lambda: 0)
    assert rc1 == 0 and rc2 == 0  # second run got the lock (first released it)

"""Healer tick 2026-07-10: LastExitStatus is STICKY — launchd keeps reporting a
job's PREVIOUS incarnation's exit code for as long as the CURRENT incarnation
keeps running. Live proof the same tick: mlx-server (4d11h uptime, serving
/v1/models), fly-pg-tunnel.local (16d uptime, port 15432 accepting
connections), local-livekit-server (16d uptime, port 7880 answering 200) were
ALL reported FAILING-HONESTLY off an exit code that predates their current run.

Contract under test (_classify / _parse_etime / _process_uptime_seconds):
  - a non-zero exit with a currently-running PID, long uptime, AND a quiet
    (stale) log -> RECOVERED (both signals required)
  - short uptime (just restarted, could still be crash-looping) -> stays
    FAILING-HONESTLY
  - fresh log (actively re-writing errors) -> stays FAILING-HONESTLY even with
    long uptime — a genuinely still-broken long-lived job is never masked
  - no PID (not currently running) -> stays FAILING-HONESTLY, can't claim
    "alive since"
  - a launch-failure marker still wins DEAD-GREEN/DEAD-NONZERO regardless of
    uptime — this change only touches the marker-less branch
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "launchd_liveness_detector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launchd_liveness_detector", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- _parse_etime

def test_parse_etime_seconds_only():
    mod = _load_module()
    assert mod._parse_etime("45") == 45.0


def test_parse_etime_mmss():
    mod = _load_module()
    assert mod._parse_etime("02:30") == 150.0


def test_parse_etime_hhmmss():
    mod = _load_module()
    assert mod._parse_etime("01:02:03") == 3723.0


def test_parse_etime_days():
    mod = _load_module()
    # observed live output for mlx-server this tick
    assert mod._parse_etime("04-11:26:47") == 4 * 86400 + 11 * 3600 + 26 * 60 + 47


def test_parse_etime_invalid_is_none():
    mod = _load_module()
    assert mod._parse_etime("") is None
    assert mod._parse_etime("not-a-time") is None
    assert mod._parse_etime("1-2-3") is None


# ---------------------------------------------------------- _process_uptime_seconds

def test_process_uptime_seconds_live_process():
    import os

    mod = _load_module()
    uptime = mod._process_uptime_seconds(os.getpid())
    assert uptime is not None
    assert uptime >= 0


def test_process_uptime_seconds_unknown_pid_is_none():
    mod = _load_module()
    assert mod._process_uptime_seconds(999999) is None


# --------------------------------------------------------------------- _classify

def test_recovers_when_uptime_and_log_both_stable(monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "UPTIME_STABLE_SEC", 3600)
    verdict = mod._classify(
        status={"LastExitStatus": 15, "PID": 12345},
        marker=None, prog_exists=True,
        stale_green=True, uptime_sec=7200,
    )
    assert verdict == "RECOVERED"


def test_stays_failing_honestly_when_uptime_too_short(monkeypatch):
    """A job that JUST restarted could still be crash-looping — short uptime
    is not proof of recovery even with a quiet log."""
    mod = _load_module()
    monkeypatch.setattr(mod, "UPTIME_STABLE_SEC", 3600)
    verdict = mod._classify(
        status={"LastExitStatus": 15, "PID": 12345},
        marker=None, prog_exists=True,
        stale_green=True, uptime_sec=60,
    )
    assert verdict == "FAILING-HONESTLY"


def test_stays_failing_honestly_when_log_not_stale(monkeypatch):
    """A genuinely still-broken long-lived job (actively re-writing fresh
    errors) must never be masked, no matter how long its PID has run."""
    mod = _load_module()
    monkeypatch.setattr(mod, "UPTIME_STABLE_SEC", 3600)
    verdict = mod._classify(
        status={"LastExitStatus": 15, "PID": 12345},
        marker=None, prog_exists=True,
        stale_green=False, uptime_sec=999999,
    )
    assert verdict == "FAILING-HONESTLY"


def test_stays_failing_honestly_when_no_pid(monkeypatch):
    """Not currently running (no PID in launchctl list) — can't claim
    'provably alive since', even with a stale log."""
    mod = _load_module()
    monkeypatch.setattr(mod, "UPTIME_STABLE_SEC", 3600)
    verdict = mod._classify(
        status={"LastExitStatus": 15},
        marker=None, prog_exists=True,
        stale_green=True, uptime_sec=None,
    )
    assert verdict == "FAILING-HONESTLY"


def test_marker_still_wins_dead_nonzero_regardless_of_uptime(monkeypatch):
    """A proven launch-failure marker is a real finding even on a long-lived
    PID — this change only touches the marker-less branch."""
    mod = _load_module()
    monkeypatch.setattr(mod, "UPTIME_STABLE_SEC", 3600)
    verdict = mod._classify(
        status={"LastExitStatus": 1, "PID": 12345},
        marker="bash: /x/y: Operation not permitted", prog_exists=True,
        stale_green=True, uptime_sec=999999,
    )
    assert verdict == "DEAD-NONZERO"


def test_marker_still_wins_dead_green_regardless_of_uptime(monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(mod, "UPTIME_STABLE_SEC", 3600)
    verdict = mod._classify(
        status={"LastExitStatus": 0, "PID": 12345},
        marker="bash: /x/y: Operation not permitted", prog_exists=True,
        stale_green=True, uptime_sec=999999,
    )
    assert verdict == "DEAD-GREEN"


def test_not_loaded_when_status_none():
    mod = _load_module()
    assert mod._classify(
        status=None, marker=None, prog_exists=True,
        stale_green=True, uptime_sec=None,
    ) == "NOT-LOADED"


def test_ok_unaffected_by_zero_exit():
    mod = _load_module()
    assert mod._classify(
        status={"LastExitStatus": 0, "PID": 12345},
        marker=None, prog_exists=True,
        stale_green=False, uptime_sec=10,
    ) == "OK"


def test_armed_to_nothing_unaffected():
    mod = _load_module()
    assert mod._classify(
        status={"LastExitStatus": 0, "PID": 12345},
        marker=None, prog_exists=False,
        stale_green=False, uptime_sec=10,
    ) == "ARMED-TO-NOTHING"

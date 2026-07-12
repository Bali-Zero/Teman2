"""Healer tick 2026-07-12: LastExitStatus from `launchctl list <label>` is the
raw POSIX wait() status word, not a decoded exit code — a plain `exit 1` shows
up as 256 (exit codes are packed into the wait-status high byte) while a
SIGKILL death shows up as 9 (signal deaths aren't shifted). Live proof:
`launchctl list com.nuzantara.overlap-detector.daily` returned
`LastExitStatus = 256` for a script whose entire body is `exit 1` on a real
detection — confusing in the ledger/Telegram output, though `_classify()`'s
zero/non-zero checks were never actually wrong (both 256 and 1 are non-zero).

Contract under test (_decode_wait_status / _launchctl_status):
  - a normal-exit raw status (256 = exit 1 shifted into the high byte)
    decodes to the plain exit code (1)
  - a signal-death raw status (9 = SIGKILL, unshifted) decodes to the negative
    signal convention `subprocess`/`launchctl print` use (-9)
  - a clean exit (0) stays 0
  - an unparseable value never crashes the detector — falls back to the raw
    value
  - `_launchctl_status()` applies the decode to the LastExitStatus key it
    parses out of live `launchctl list` output, leaving other keys untouched
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


def test_normal_exit_is_unshifted():
    mod = _load_module()
    assert mod._decode_wait_status(256) == 1


def test_signal_death_becomes_negative_signal():
    mod = _load_module()
    assert mod._decode_wait_status(9) == -9


def test_clean_exit_stays_zero():
    mod = _load_module()
    assert mod._decode_wait_status(0) == 0


def test_unparseable_status_falls_back_to_raw(monkeypatch):
    mod = _load_module()

    def _raise(_status):
        raise ValueError("boom")

    monkeypatch.setattr(mod.os, "waitstatus_to_exitcode", _raise)
    assert mod._decode_wait_status(999) == 999


def test_launchctl_status_decodes_last_exit_status(monkeypatch):
    """Innocence: other keys parsed from `launchctl list` output pass through
    untouched — only LastExitStatus is decoded."""
    mod = _load_module()

    class _FakeCompleted:
        returncode = 0
        stdout = (
            '{\n'
            '\t"Label" = "com.nuzantara.overlap-detector.daily";\n'
            '\t"LastExitStatus" = 256;\n'
            '\t"PID" = 12345;\n'
            '};\n'
        )

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FakeCompleted())
    status = mod._launchctl_status("com.nuzantara.overlap-detector.daily")
    assert status["LastExitStatus"] == 1
    assert status["PID"] == 12345


def test_launchctl_status_not_loaded_returns_none(monkeypatch):
    mod = _load_module()

    class _FakeCompleted:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FakeCompleted())
    assert mod._launchctl_status("com.nonexistent") is None

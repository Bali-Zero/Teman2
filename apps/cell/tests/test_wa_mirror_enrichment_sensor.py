"""Tests for WaMirrorEnrichmentSensor (W57 2026-05-26).

Self-healing wa-mirror enrichment Layer B-3 sensor probe tests:
  - launchctl print parsing (exit code, runs, state)
  - stderr log parsing (ModuleNotFoundError vs other exceptions)
  - status aggregation (green / yellow / repairable flag)
  - exit code 75 (EX_TEMPFAIL) treated as transient, not yellow
"""
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cell.sensors.wa_mirror_enrichment_sensor import (
    WaMirrorEnrichmentSensor,
    WaMirrorEnrichmentReading,
    LabelStatus,
    _MODULE_NOT_FOUND_RE,
    _EXCEPTION_LINE_RE,
)


# ---------------------------------------------------------------------------
# launchctl probe parsing
# ---------------------------------------------------------------------------

def _make_launchctl_output(exit_code=0, runs=5, state="not running"):
    """Build a synthetic launchctl print output for parsing tests."""
    return (
        f"gui/501/com.test = {{\n"
        f"\tactive count = 0\n"
        f"\tpath = /tmp/test.plist\n"
        f"\ttype = LaunchAgent\n"
        f"\tstate = {state}\n"
        f"\tprogram = /tmp/test.sh\n"
        f"\tdomain = gui/501\n"
        f"\truns = {runs}\n"
        f"\tlast exit code = {exit_code}\n"
        f"}}\n"
    )


def test_launchctl_exit_code_parse_success(monkeypatch):
    """Sensor parses exit_code, runs, state from launchctl print output."""
    sensor = WaMirrorEnrichmentSensor()
    fake_proc = MagicMock()
    fake_proc.stdout = _make_launchctl_output(exit_code=0, runs=5, state="not running")
    fake_proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake_proc)

    exit_code, runs, state = sensor._launchctl_exit_code("com.test")
    assert exit_code == 0
    assert runs == 5
    assert state == "not running"


def test_launchctl_exit_code_parse_failed(monkeypatch):
    """Non-zero exit_code parsed correctly."""
    sensor = WaMirrorEnrichmentSensor()
    fake_proc = MagicMock()
    fake_proc.stdout = _make_launchctl_output(exit_code=1, runs=3)
    fake_proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake_proc)
    exit_code, runs, state = sensor._launchctl_exit_code("com.test")
    assert exit_code == 1
    assert runs == 3


def test_launchctl_no_match_returns_none(monkeypatch):
    """Output missing fields → None values returned (no crash)."""
    sensor = WaMirrorEnrichmentSensor()
    fake_proc = MagicMock()
    fake_proc.stdout = "empty\n"
    fake_proc.stderr = ""
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: fake_proc)
    exit_code, runs, state = sensor._launchctl_exit_code("com.test")
    assert exit_code is None
    assert runs is None
    # state stays at default "unknown" when no "state = " line in output
    assert state == "unknown"


def test_launchctl_timeout_returns_probe_failed(monkeypatch):
    """subprocess timeout → state='probe_failed', does not crash."""
    import subprocess
    sensor = WaMirrorEnrichmentSensor(launchctl_timeout=0.1)

    def _raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="launchctl", timeout=0.1)
    monkeypatch.setattr("subprocess.run", _raise_timeout)

    exit_code, runs, state = sensor._launchctl_exit_code("com.test")
    assert state == "probe_failed"


# ---------------------------------------------------------------------------
# stderr log parsing
# ---------------------------------------------------------------------------

def test_parse_error_class_module_not_found(tmp_path):
    """ModuleNotFoundError + missing_module extracted from stderr tail."""
    log_path = tmp_path / "err.log"
    log_path.write_text(
        "some stuff before\n"
        "Traceback (most recent call last):\n"
        "  File '/foo.py', line 1, in <module>\n"
        "    import asyncpg\n"
        "ModuleNotFoundError: No module named 'asyncpg'\n"
    )
    sensor = WaMirrorEnrichmentSensor(log_paths={"com.test": str(log_path)})
    cls, mod = sensor._parse_error_class("com.test")
    assert cls == "ModuleNotFoundError"
    assert mod == "asyncpg"


def test_parse_error_class_invalid_password(tmp_path):
    """InvalidPasswordError (yellow-but-unactionable) extracted, no module."""
    log_path = tmp_path / "err.log"
    log_path.write_text(
        "Traceback (most recent call last):\n"
        "  File '/foo.py', line 100, in <module>\n"
        "asyncpg.exceptions.InvalidPasswordError: password authentication failed for user 'nuzantara'\n"
    )
    sensor = WaMirrorEnrichmentSensor(log_paths={"com.test": str(log_path)})
    cls, mod = sensor._parse_error_class("com.test")
    assert cls == "InvalidPasswordError"
    assert mod is None


def test_parse_error_class_connection_refused(tmp_path):
    """ConnectionRefusedError extracted."""
    log_path = tmp_path / "err.log"
    log_path.write_text(
        "Traceback (most recent call last):\n"
        "ConnectionRefusedError: [Errno 61] Connection refused\n"
    )
    sensor = WaMirrorEnrichmentSensor(log_paths={"com.test": str(log_path)})
    cls, mod = sensor._parse_error_class("com.test")
    assert cls == "ConnectionRefusedError"
    assert mod is None


def test_parse_error_class_missing_log_returns_none(tmp_path):
    """Log file doesn't exist → (None, None), no crash."""
    sensor = WaMirrorEnrichmentSensor(log_paths={"com.test": str(tmp_path / "nope.log")})
    cls, mod = sensor._parse_error_class("com.test")
    assert cls is None
    assert mod is None


def test_parse_error_class_truncates_large_log(tmp_path):
    """Sensor reads only _STDERR_TAIL_BYTES (8KB) — not full multi-MB log."""
    log_path = tmp_path / "huge.log"
    # 20KB of noise + a final ModuleNotFoundError that should still be caught
    log_path.write_text(
        ("garbage\n" * 2000)
        + "ModuleNotFoundError: No module named 'httpx'\n"
    )
    sensor = WaMirrorEnrichmentSensor(log_paths={"com.test": str(log_path)})
    cls, mod = sensor._parse_error_class("com.test")
    assert cls == "ModuleNotFoundError"
    assert mod == "httpx"


# ---------------------------------------------------------------------------
# Status aggregation via read()
# ---------------------------------------------------------------------------

def test_read_all_green_returns_green(monkeypatch, tmp_path):
    """All 3 labels exit code 0 → status green, not repairable."""
    sensor = WaMirrorEnrichmentSensor(
        labels=("a", "b", "c"),
        log_paths={"a": str(tmp_path / "a"), "b": str(tmp_path / "b"), "c": str(tmp_path / "c")},
    )
    monkeypatch.setattr(
        sensor, "_launchctl_exit_code",
        lambda label: (0, 5, "not running"),
    )
    reading = sensor.read()
    assert reading.status == "green"
    assert reading.repairable is False
    assert len(reading.labels) == 3
    assert all(ls.last_exit_code == 0 for ls in reading.labels)


def test_read_exit_75_is_transient_stays_green(monkeypatch, tmp_path):
    """Exit code 75 (EX_TEMPFAIL) doesn't escalate to yellow.

    Layer A wrapper emits 75 when pip install fails AND launchd will retry
    on next StartInterval — no Organism action needed. Sensor treats as transient.
    """
    sensor = WaMirrorEnrichmentSensor(
        labels=("a",), log_paths={"a": str(tmp_path / "a")},
    )
    monkeypatch.setattr(sensor, "_launchctl_exit_code", lambda label: (75, 5, "not running"))
    reading = sensor.read()
    assert reading.status == "green"
    assert reading.repairable is False


def test_read_module_not_found_marks_repairable(monkeypatch, tmp_path):
    """ModuleNotFoundError → status=yellow + repairable=True + missing_module set."""
    log = tmp_path / "err.log"
    log.write_text("ModuleNotFoundError: No module named 'asyncpg'\n")
    sensor = WaMirrorEnrichmentSensor(labels=("a",), log_paths={"a": str(log)})
    monkeypatch.setattr(sensor, "_launchctl_exit_code", lambda label: (1, 3, "not running"))
    reading = sensor.read()
    assert reading.status == "yellow"
    assert reading.repairable is True
    assert reading.metadata["repair_missing_module"] == "asyncpg"
    assert reading.metadata["repair_python_path"] is not None


def test_read_invalid_password_yellow_not_repairable(monkeypatch, tmp_path):
    """InvalidPasswordError → status=yellow but NOT repairable (operator)."""
    log = tmp_path / "err.log"
    log.write_text("asyncpg.exceptions.InvalidPasswordError: bad pwd\n")
    sensor = WaMirrorEnrichmentSensor(labels=("a",), log_paths={"a": str(log)})
    monkeypatch.setattr(sensor, "_launchctl_exit_code", lambda label: (1, 3, "not running"))
    reading = sensor.read()
    assert reading.status == "yellow"
    assert reading.repairable is False
    assert reading.metadata["repair_missing_module"] is None
    # error_class still extracted into the LabelStatus for observability
    assert reading.labels[0].error_class == "InvalidPasswordError"


def test_read_mixed_one_repairable_marks_repairable(monkeypatch, tmp_path):
    """If ANY label is repairable, repairable=True (we'll fix what we can)."""
    log_a = tmp_path / "a.log"
    log_a.write_text("ModuleNotFoundError: No module named 'httpx'\n")
    log_b = tmp_path / "b.log"
    log_b.write_text("InvalidPasswordError: foo\n")

    sensor = WaMirrorEnrichmentSensor(
        labels=("a", "b"),
        log_paths={"a": str(log_a), "b": str(log_b)},
    )
    exit_codes = {"a": 1, "b": 1}
    monkeypatch.setattr(
        sensor, "_launchctl_exit_code",
        lambda label: (exit_codes[label], 1, "not running"),
    )
    reading = sensor.read()
    assert reading.status == "yellow"
    assert reading.repairable is True
    # First repairable target wins (label 'a' processed first)
    assert reading.metadata["repair_missing_module"] == "httpx"


def test_read_sensor_does_not_crash_on_unexpected_exception(monkeypatch, tmp_path):
    """Exception in launchctl path → label gets state='probe_error', read() returns."""
    sensor = WaMirrorEnrichmentSensor(labels=("a",), log_paths={"a": str(tmp_path / "a")})

    def _boom(label):
        raise RuntimeError("boom")
    monkeypatch.setattr(sensor, "_launchctl_exit_code", _boom)
    reading = sensor.read()
    # No raise; sensor downgrades to yellow + state=probe_error
    assert reading.status == "yellow"
    assert reading.labels[0].state == "probe_error"


# ---------------------------------------------------------------------------
# Regex unit checks
# ---------------------------------------------------------------------------

def test_module_not_found_re_matches_standard_form():
    m = _MODULE_NOT_FOUND_RE.search("ModuleNotFoundError: No module named 'asyncpg'")
    assert m is not None
    assert m.group(1) == "asyncpg"


def test_module_not_found_re_handles_double_quotes():
    m = _MODULE_NOT_FOUND_RE.search('ModuleNotFoundError: No module named "httpx"')
    assert m is not None
    assert m.group(1) == "httpx"


def test_exception_line_re_dotted_class():
    m = _EXCEPTION_LINE_RE.match("asyncpg.exceptions.InvalidPasswordError: failed")
    assert m is not None
    assert m.group(1).endswith("InvalidPasswordError")


# ---------------------------------------------------------------------------
# Wave 4 code-reviewer finding #2: sensor allowlist defense-in-depth
# ---------------------------------------------------------------------------

def test_read_module_not_found_for_non_allowlist_module_not_repairable(monkeypatch, tmp_path):
    """Code-reviewer finding #2: missing_module NOT in sensor allowlist →
    repairable=False even if ModuleNotFoundError. Defense-in-depth before
    taint reaches PG outbox subscribers.
    """
    log = tmp_path / "err.log"
    # Inject a NON-allowlist module name (e.g. attacker-controlled stderr log)
    log.write_text("ModuleNotFoundError: No module named 'malicious_pkg'\n")
    sensor = WaMirrorEnrichmentSensor(labels=("a",), log_paths={"a": str(log)})
    monkeypatch.setattr(sensor, "_launchctl_exit_code", lambda label: (1, 3, "not running"))
    reading = sensor.read()
    # Yellow status (real failure) but NOT repairable
    assert reading.status == "yellow"
    assert reading.repairable is False
    assert reading.metadata["repair_missing_module"] is None
    # The label's error_class + missing_module still get recorded for
    # observability (operator can see "we knew but didn't act")
    assert reading.labels[0].error_class == "ModuleNotFoundError"
    assert reading.labels[0].missing_module == "malicious_pkg"


def test_sensor_allowlist_includes_known_deps():
    """Sanity check: sensor allowlist contains the known wa-mirror deps."""
    from cell.sensors.wa_mirror_enrichment_sensor import _SENSOR_REPAIR_ALLOWLIST
    assert "asyncpg" in _SENSOR_REPAIR_ALLOWLIST
    assert "httpx" in _SENSOR_REPAIR_ALLOWLIST

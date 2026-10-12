"""Executes qwen_quota_watch.py's offline selftest under pytest (CI sweep).

The selftest embeds guilt AND innocence for the window sum, month straddle,
WARN/CRIT thresholds, missed-host declaration, and stale-calibration
declaration — all offline (no ssh, no real logs). This wrapper makes the
sweep RUN it (W81: a selftest nobody executes is suspended, not armed).
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "qwen_quota_watch.py"


def test_selftest_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--selftest"],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"selftest failed:\n{proc.stdout}\n{proc.stderr}"
    assert "selftest OK" in proc.stdout


def test_cannot_measure_is_exit_4_not_zero_pct(tmp_path, monkeypatch) -> None:
    """No readable log anywhere must be CANNOT-MEASURE (4), never '0% used'."""
    monkeypatch.setenv("HOME", str(tmp_path))  # empty HOME: no ~/.qwen at all
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--hosts", ""],
        capture_output=True, text=True, timeout=60,
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 4, f"rc={proc.returncode} out={proc.stdout} err={proc.stderr}"
    assert "CANNOT-MEASURE" in proc.stderr
    assert "0.0%" not in proc.stdout


def _load_module():
    """Import the watcher by path under a throwaway name (no production hook)."""
    spec = importlib.util.spec_from_file_location("qwen_quota_watch_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass string-annotation lookup needs this
    spec.loader.exec_module(module)
    return module


def test_run_main_guard(monkeypatch, capsys) -> None:
    """Crash → 3 with a CRASH line on stderr (a bare exception exit 1 reads as
    GREEN to the cron wrapper); clean returns pass through; SystemExit propagates."""
    module = _load_module()

    def _boom() -> int:
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(module, "main", _boom)
    assert module._run_main() == 3
    assert "CRASH: RuntimeError: simulated crash" in capsys.readouterr().err
    monkeypatch.setattr(module, "main", lambda: 2)
    assert module._run_main() == 2

    def _exit() -> int:
        raise SystemExit(2)

    monkeypatch.setattr(module, "main", _exit)
    assert module._run_main() == 3  # argparse usage error must not read as CRIT
    assert "CRASH: SystemExit(2)" in capsys.readouterr().err

    def _help() -> int:
        raise SystemExit(0)

    monkeypatch.setattr(module, "main", _help)
    with pytest.raises(SystemExit) as excinfo:
        module._run_main()
    assert excinfo.value.code == 0

    def _no_stderr() -> None:
        raise OSError("stderr gone")

    monkeypatch.setattr(module, "main", _boom)
    monkeypatch.setattr(module.traceback, "print_exc", _no_stderr)
    assert module._run_main() == 3


def test_send_alert_timeout_returns_false(monkeypatch, capsys) -> None:
    """A hung gateway fails the alert (main turns it into exit 4) instead of
    hanging cron — and the subprocess call must carry ALERT_TIMEOUT_S."""
    seen = {}

    def _hung(*args, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(cmd="tg_notify", timeout=kwargs.get("timeout"))

    module = _load_module()
    monkeypatch.setattr(module.subprocess, "run", _hung)
    assert module.send_alert("report", 90.0, SCRIPT.parent) is False
    err = capsys.readouterr().err
    assert "tg_notify TIMEOUT" in err and "ALERT NOT DELIVERED" in err
    assert seen["timeout"] == module.ALERT_TIMEOUT_S


def test_cron_wrapper_maps_only_0_1_2_to_success() -> None:
    text = SCRIPT.with_name("qwen_quota_watch_cron.sh").read_text(encoding="utf-8")
    assert "0|1|2) exit 0 ;;" in text

"""Executes qwen_quota_watch.py's offline selftest under pytest (CI sweep).

The selftest embeds guilt AND innocence for the window sum, month straddle,
WARN/CRIT thresholds, missed-host declaration, and stale-calibration
declaration — all offline (no ssh, no real logs). This wrapper makes the
sweep RUN it (W81: a selftest nobody executes is suspended, not armed).
"""

import subprocess
import sys
from pathlib import Path

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

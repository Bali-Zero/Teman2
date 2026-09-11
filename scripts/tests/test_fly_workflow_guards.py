"""Regression tests for Fly.io workflow honesty and standby handling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _embedded_python(workflow: str) -> str:
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    marker = "python3 <<'PY'"
    start = text.index(marker) + len(marker)
    lines = text[start:].splitlines()[1:]
    body = []
    for line in lines:
        if line.strip() == "PY":
            break
        body.append(line[10:] if line.startswith("          ") else line)
    return "\n".join(body) + "\n"


def test_restart_detector_treats_configured_standby_as_expected() -> None:
    script = _embedded_python("cron-fly-restart-detector.yml")
    machines = {
        "Machines": [
            {"id": "active", "state": "started", "config": {}, "events": []},
            {
                "id": "standby",
                "state": "stopped",
                "config": {"standbys": ["active"]},
                "events": [
                    {"request": {"exit_event": {"exit_code": 1}}},
                ],
            },
        ]
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "RAW": json.dumps(machines)},
    )

    assert "expected_stopped=1" in result.stdout
    assert "unexpected_stopped=0" in result.stdout
    assert "bad=none" in result.stdout
    assert "crashed=none" in result.stdout


def test_restart_detector_keeps_unexpected_crash_recovery() -> None:
    script = _embedded_python("cron-fly-restart-detector.yml")
    machines = {
        "Machines": [
            {
                "id": "crashed",
                "state": "stopped",
                "config": {},
                "events": [
                    {"request": {"exit_event": {"exit_code": 1}}},
                ],
            }
        ]
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "RAW": json.dumps(machines)},
    )

    assert "expected_stopped=0" in result.stdout
    assert "unexpected_stopped=1" in result.stdout
    assert "crashed=crashed" in result.stdout



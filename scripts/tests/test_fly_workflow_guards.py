"""Regression tests for Fly.io workflow honesty and standby handling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
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


def test_cost_guard_reports_resource_drift_without_fake_billing(tmp_path: Path) -> None:
    workflow = (WORKFLOWS / "cron-fly-cost-alert.yml").read_text(encoding="utf-8")
    assert "flyctl bills view" not in workflow
    assert "Current month cost" not in workflow

    fake_flyctl = tmp_path / "flyctl"
    fake_flyctl.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
app = args[args.index("--app") + 1] if "--app" in args else None
if args[:2] == ["apps", "list"]:
    data = [
        {"Name": "nuzantara-rag"},
        {"Name": "nuzantara-postgres"},
        {"Name": "fly-builder-legacy"},
    ]
elif args[0] == "status":
    counts = {
        "nuzantara-rag": ["started", "started", "started", "stopped"],
        "nuzantara-postgres": ["started", "started"],
        "fly-builder-legacy": ["stopped"],
    }
    data = {"Machines": [{"state": state} for state in counts[app]]}
elif args[:2] == ["volumes", "list"]:
    sizes = {"nuzantara-rag": [1, 1], "nuzantara-postgres": [25, 25], "fly-builder-legacy": [50]}
    data = [{"size_gb": size} for size in sizes[app]]
elif args[:2] == ["ips", "list"]:
    data = [{"Type": "v4"}] if app == "nuzantara-rag" else []
else:
    raise SystemExit(f"unexpected flyctl args: {args}")
print(json.dumps(data))
""",
        encoding="utf-8",
    )
    fake_flyctl.chmod(fake_flyctl.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "github-output"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "EXPECTED_APPS": "nuzantara-rag,nuzantara-postgres",
        "MAX_TOTAL_MACHINES": "6",
        "MAX_TOTAL_VOLUME_GB": "60",
        "MAX_DEDICATED_IPV4": "1",
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(
        [sys.executable, "-c", _embedded_python("cron-fly-cost-alert.yml")],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    github_output = output.read_text(encoding="utf-8")

    assert "Apps: 3 | Machines: 5/7 started | Volumes: 102 GB" in result.stdout
    assert "unexpected apps=fly-builder-legacy" in github_output
    assert "machines 7>6" in github_output
    assert "volumes 102GB>60GB" in github_output

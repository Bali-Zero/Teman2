from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CRON_RUNNER = ROOT / "scripts/cron-runner.sh"
CRON_STATE = ROOT / "scripts/cron-state.sh"


def _env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    return env


def test_cron_runner_emits_state_for_script_with_args(tmp_path: Path) -> None:
    script = tmp_path / "sample-job.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(CRON_RUNNER), str(script), "--layer-a"],
        env=_env(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    state_path = tmp_path / ".agent/decisions/state/sample_job_layer_a.last.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["job"] == "sample_job_layer_a"
    assert payload["status"] == "ok"
    assert payload["source"] == "cron-runner"
    assert payload["argv"] == ["--layer-a"]


def test_cron_runner_emits_failed_state_for_missing_script(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sh"

    result = subprocess.run(
        ["bash", str(CRON_RUNNER), str(missing)],
        env=_env(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    state_path = tmp_path / ".agent/decisions/state/missing.last.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 1


def test_cron_state_emits_state_for_arbitrary_command(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(CRON_STATE), "heartbeat-pro", "bash", "-lc", "exit 0"],
        env=_env(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    state_path = tmp_path / ".agent/decisions/state/heartbeat_pro.last.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["job"] == "heartbeat_pro"
    assert payload["status"] == "ok"
    assert payload["source"] == "cron-state"


def test_cron_state_preserves_exit_code(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(CRON_STATE), "failing-job", "bash", "-lc", "exit 7"],
        env=_env(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    state_path = tmp_path / ".agent/decisions/state/failing_job.last.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert result.returncode == 7
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 7

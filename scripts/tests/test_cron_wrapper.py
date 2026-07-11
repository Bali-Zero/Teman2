import json
import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WRAPPER = _REPO_ROOT / "scripts" / "cron-wrapper.sh"


def _wrapper_env(tmp_path: Path, timeout_s: int = 5) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "CRON_LOG_DIR": str(tmp_path / "logs"),
            "CRON_MAX_RETRIES": "0",
            "CRON_TIMEOUT": str(timeout_s),
            "CRON_WRAPPER_DISABLE_EXTERNAL_TIMEOUT": "1",
        }
    )
    return env


def _state(home: Path, job_name: str) -> dict:
    path = home / ".agent" / "decisions" / "state" / f"{job_name}.last.json"
    return json.loads(path.read_text())


def test_cron_wrapper_runs_with_native_timeout_fallback(tmp_path) -> None:
    result = subprocess.run(
        [
            "bash",
            str(_WRAPPER),
            "unit-success",
            "bash",
            "-c",
            "printf fallback-ok",
        ],
        cwd=_REPO_ROOT,
        env=_wrapper_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    heartbeat = _state(tmp_path, "unit_success")
    assert heartbeat["status"] == "ok"
    assert heartbeat["source"] == "cron-wrapper"
    assert "fallback-ok" in (tmp_path / "logs" / "unit-success.log").read_text()


def test_cron_wrapper_native_timeout_fallback_returns_124(tmp_path) -> None:
    result = subprocess.run(
        [
            "bash",
            str(_WRAPPER),
            "unit-timeout",
            "bash",
            "-c",
            "printf started; sleep 5",
        ],
        cwd=_REPO_ROOT,
        env=_wrapper_env(tmp_path, timeout_s=1),
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 124
    heartbeat = _state(tmp_path, "unit_timeout")
    assert heartbeat["status"] == "failed"
    assert "timeout after 1s" in heartbeat["last_error"]

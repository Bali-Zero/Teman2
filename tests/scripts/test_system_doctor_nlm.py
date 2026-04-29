"""Tests for system_doctor.check_nlm_pipelines_stuck() — P1-7 NLM auto-recovery."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import system_doctor as sd  # noqa: E402


def _write_state(state_dir: Path, name: str, ts: int, status: str = "ok") -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / f"{name}.last.json"
    p.write_text(json.dumps({
        "job": name.replace("_", "-"),
        "ts": ts,
        "status": status,
        "host": "test-host",
    }))
    return p


def _ok_run(stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)


def _fail_run(stderr: str = "boom", returncode: int = 1) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)


@pytest.fixture
def now_ts() -> int:
    return 1_800_000_000


def test_healthy_pipeline_skipped(tmp_path, now_ts):
    """ts within 24h AND status=ok → skipped, no rerun, no telegram."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", now_ts - 3600, status="ok")

    with patch.object(sd, "subprocess") as mock_sub, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["skipped"]
    assert result["stuck"] == []
    assert result["recovered"] == []
    assert result["failed"] == []
    mock_sub.run.assert_not_called()
    mock_tg.assert_not_called()


def test_stuck_pipeline_rerun_succeeds(tmp_path, now_ts):
    """age > 24h triggers rerun; returncode=0 → recovered, no telegram."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", now_ts - 48 * 3600, status="ok")

    with patch.object(sd.subprocess, "run", return_value=_ok_run()) as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["stuck"]
    assert "nlm_nb6_ops_compliance" in result["recovered"]
    assert result["failed"] == []
    mock_run.assert_called_once()
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == sys.executable
    assert "-m" in cmd
    assert "apps.evaluator.nlm_deep_research.nb6_pipeline" in cmd
    mock_tg.assert_not_called()


def test_failed_status_triggers_rerun(tmp_path, now_ts):
    """status=='failed' triggers rerun even within 24h."""
    _write_state(tmp_path, "nlm_nb7_editorial", now_ts - 600, status="failed")

    with patch.object(sd.subprocess, "run", return_value=_ok_run()) as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb7_editorial" in result["stuck"]
    assert "nlm_nb7_editorial" in result["recovered"]
    mock_run.assert_called_once()
    mock_tg.assert_not_called()


def test_rerun_failure_triggers_telegram(tmp_path, now_ts):
    """rerun returncode != 0 → counted as failed AND telegram alert sent."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", now_ts - 48 * 3600, status="ok")

    with patch.object(sd.subprocess, "run",
                      return_value=_fail_run(stderr="ModuleNotFoundError", returncode=2)), \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["failed"]
    assert "nlm_nb6_ops_compliance" not in result["recovered"]
    mock_tg.assert_called_once()
    args = mock_tg.call_args
    msg_arg = args.kwargs.get("message") or args.args[0]
    assert "nlm_nb6_ops_compliance" in msg_arg
    assert "ModuleNotFoundError" in msg_arg


def test_subprocess_timeout_treated_as_failure(tmp_path, now_ts):
    """subprocess.TimeoutExpired → failed + telegram with timeout marker."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", now_ts - 30 * 3600, status="ok")

    def _raise_timeout(*args, **kwargs):
        raise sd.subprocess.TimeoutExpired(cmd=args[0], timeout=300)

    with patch.object(sd.subprocess, "run", side_effect=_raise_timeout), \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["failed"]
    mock_tg.assert_called_once()
    msg = mock_tg.call_args.args[0] if mock_tg.call_args.args else mock_tg.call_args.kwargs.get("message", "")
    assert "timeout" in msg.lower()


def test_missing_state_dir_returns_empty(tmp_path, now_ts):
    """state_dir not present → empty result, no errors raised."""
    missing = tmp_path / "does-not-exist"

    with patch.object(sd.subprocess, "run") as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=missing, now_fn=lambda: now_ts,
        )

    assert result == {"stuck": [], "recovered": [], "failed": [], "skipped": [], "errors": {}}
    mock_run.assert_not_called()
    mock_tg.assert_not_called()


def test_malformed_json_recorded_as_error(tmp_path, now_ts):
    """Invalid JSON in state file → error entry, not crash."""
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "nlm_nb6_ops_compliance.last.json").write_text("{ not json")

    with patch.object(sd.subprocess, "run") as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["errors"]
    assert "json" in result["errors"]["nlm_nb6_ops_compliance"].lower() or \
           "decode" in result["errors"]["nlm_nb6_ops_compliance"].lower() or \
           "expecting" in result["errors"]["nlm_nb6_ops_compliance"].lower()
    mock_run.assert_not_called()
    mock_tg.assert_not_called()


def test_pipeline_with_no_module_mapping_skipped(tmp_path, now_ts):
    """nlm_bridge has no rerun module (None in table) → skipped even if stuck."""
    _write_state(tmp_path, "nlm_bridge", now_ts - 100 * 3600, status="ok")

    with patch.object(sd.subprocess, "run") as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_bridge" in result["skipped"]
    assert "nlm_bridge" not in result["stuck"]
    mock_run.assert_not_called()
    mock_tg.assert_not_called()


def test_unknown_pipeline_in_state_dir_ignored(tmp_path, now_ts):
    """nlm_*.last.json with unknown name → not in mapping → skipped silently."""
    _write_state(tmp_path, "nlm_unknown_future_pipeline", now_ts - 100 * 3600, status="failed")

    with patch.object(sd.subprocess, "run") as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_unknown_future_pipeline" in result["skipped"]
    mock_run.assert_not_called()
    mock_tg.assert_not_called()


def test_ts_zero_treated_as_never_run_skipped(tmp_path, now_ts):
    """ts <= 0 → no usable signal → skip."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", 0, status="ok")

    with patch.object(sd.subprocess, "run") as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["skipped"]
    mock_run.assert_not_called()
    mock_tg.assert_not_called()


def test_multiple_pipelines_independent(tmp_path, now_ts):
    """Mix of healthy/stuck/failed across multiple pipelines — partial outcomes."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", now_ts - 1 * 3600, status="ok")  # healthy
    _write_state(tmp_path, "nlm_nb7_editorial", now_ts - 48 * 3600, status="ok")     # stuck → recover
    _write_state(tmp_path, "nlm_nb8_expat_life", now_ts - 30 * 3600, status="ok")    # stuck → fail

    runs: list = []

    def _alternate_run(cmd, **kwargs):
        runs.append(cmd)
        # nb7 succeeds, nb8 fails
        module = next((c for c in cmd if "nlm_deep_research" in c), "")
        if "nb8_pipeline" in module:
            return _fail_run(stderr="boom", returncode=1)
        return _ok_run()

    with patch.object(sd.subprocess, "run", side_effect=_alternate_run), \
         patch.object(sd, "_nlm_send_telegram_warning") as mock_tg:
        result = sd.check_nlm_pipelines_stuck(
            state_dir=tmp_path, now_fn=lambda: now_ts,
        )

    assert "nlm_nb6_ops_compliance" in result["skipped"]
    assert "nlm_nb7_editorial" in result["recovered"]
    assert "nlm_nb8_expat_life" in result["failed"]
    assert mock_tg.call_count == 1
    msg = mock_tg.call_args.args[0]
    assert "nlm_nb8_expat_life" in msg


def test_cli_check_nlm_short_circuits_main(tmp_path, now_ts, monkeypatch, capsys):
    """`python system_doctor.py --check-nlm` runs ONLY this function and prints JSON."""
    _write_state(tmp_path, "nlm_nb6_ops_compliance", now_ts - 1 * 3600, status="ok")

    monkeypatch.setattr(sys, "argv", ["system_doctor.py", "--check-nlm"])
    monkeypatch.setenv("NLM_STATE_DIR", str(tmp_path))

    with patch.object(sd, "time") as mock_time, \
         patch.object(sd.subprocess, "run") as mock_run, \
         patch.object(sd, "_nlm_send_telegram_warning"):
        mock_time.time.return_value = now_ts
        sd.main()

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "skipped" in payload
    assert "nlm_nb6_ops_compliance" in payload["skipped"]
    mock_run.assert_not_called()

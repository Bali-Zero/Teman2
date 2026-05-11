from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_sentinel_aggregate() -> ModuleType:
    path = Path(__file__).parents[1] / "sentinel-aggregate.py"
    spec = importlib.util.spec_from_file_location("sentinel_aggregate", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_running_launchd_daemon_with_stale_last_exit_is_ok() -> None:
    module = _load_sentinel_aggregate()

    result = module._classify(
        {
            "id": "pro.federation_alert_dispatcher",
            "runtime": "pro_launchd",
            "type": "daemon",
            "severity_on_silence": "error",
            "owner_module": "scripts/federation-alert-dispatcher.sh",
        },
        hb=None,
        launchctl_entry={"pid": 5304, "last_exit": 1},
        now=1_778_320_000.0,
    )

    assert result["status"] == "ok"
    assert result["severity"] == "info"
    assert result["pid"] == 5304
    assert result["last_exit"] == 1


def test_disabled_registry_entry_is_reported_as_disabled() -> None:
    module = _load_sentinel_aggregate()

    result = module._classify(
        {
            "id": "backend.crm.drive_poll",
            "runtime": "pro_launchd",
            "type": "cron",
            "enabled": False,
            "disabled_reason": "disabled by cicatrix",
            "severity_on_silence": "warning",
            "owner_module": "scripts/openclaw-cron/drive-poll.sh",
        },
        hb=None,
        launchctl_entry=None,
        now=1_778_320_000.0,
    )

    assert result["status"] == "disabled"
    assert result["severity"] == "info"
    assert result["disabled_reason"] == "disabled by cicatrix"


def test_state_file_contract_still_reports_noheartbeat_when_running() -> None:
    module = _load_sentinel_aggregate()

    result = module._classify(
        {
            "id": "cell.observatory",
            "runtime": "pro_launchd",
            "type": "daemon",
            "bridge_source": {"type": "state_file", "path": "~/.organism/last_seen/cell.observatory.json"},
        },
        hb=None,
        launchctl_entry={"pid": 1256, "last_exit": 0},
        now=1_778_320_000.0,
    )

    assert result["status"] == "noheartbeat"
    assert result["pid"] == 1256


def test_running_cron_with_stale_previous_heartbeat_is_ok() -> None:
    module = _load_sentinel_aggregate()

    result = module._classify(
        {
            "id": "pro.dlq_autopilot",
            "runtime": "pro_launchd",
            "type": "cron",
            "expected_hb_seconds": 2700,
            "severity_on_silence": "warning",
        },
        hb={"ts": 1_778_300_000.0, "status": "degraded"},
        launchctl_entry={"pid": 1883, "last_exit": 0},
        now=1_778_320_000.0,
    )

    assert result["status"] == "ok"
    assert result["pid"] == 1883
    assert result["hb_source"] == "launchctl_running"


def test_parse_launchctl_list_handles_remote_mini_output() -> None:
    module = _load_sentinel_aggregate()

    result = module._parse_launchctl_list(
        "PID\tStatus\tLabel\n"
        "-\t0\tcom.matagaruda.ner-worker.hourly\n"
        "123\t1\tcom.example.running\n"
    )

    assert result["com.matagaruda.ner-worker.hourly"] == {"pid": None, "last_exit": 0}
    assert result["com.example.running"] == {"pid": 123, "last_exit": 1}

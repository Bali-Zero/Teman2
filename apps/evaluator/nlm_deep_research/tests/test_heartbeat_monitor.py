"""Tests for Pipeline Heartbeat Monitor (ARCH-9).

Covers: record_success, check_all_heartbeats (various states),
        classification logic, memory pressure parsing, send_alert,
        send_daily_digest.

Run: PYTHONPATH=. pytest apps/evaluator/nlm_deep_research/tests/test_heartbeat_monitor.py -v
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from apps.evaluator.nlm_deep_research.heartbeat_monitor import (
    STATUS_CRITICAL,
    STATUS_DEAD,
    STATUS_NEVER_RAN,
    STATUS_OK,
    STATUS_WARNING,
    WITA,
    _classify_staleness,
    _format_last_run,
    _read_heartbeat_state,
    check_all_heartbeats,
    check_memory_pressure,
    load_registry,
    record_success,
    send_alert,
    send_daily_digest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def tmp_registry(tmp_path: Path) -> Path:
    """Temporary registry file with two pipelines."""
    registry = {
        "test_daily": {"schedule": "daily", "max_age_hours": 26},
        "test_weekday": {"schedule": "weekday", "max_age_hours": 26},
        "test_weekly": {"schedule": "weekly_sun", "max_age_hours": 170},
    }
    path = tmp_path / "test_registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_registry
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    def test_load_existing(self, tmp_registry: Path) -> None:
        reg = load_registry(tmp_registry)
        assert "test_daily" in reg
        assert reg["test_daily"]["max_age_hours"] == 26

    def test_load_missing_file(self, tmp_path: Path) -> None:
        reg = load_registry(tmp_path / "nonexistent.json")
        assert reg == {}


# ---------------------------------------------------------------------------
# record_success
# ---------------------------------------------------------------------------


class TestRecordSuccess:
    def test_creates_state_file(self, tmp_state_dir: Path) -> None:
        record_success("nb2_pipeline", duration_seconds=45.3, state_dir=tmp_state_dir)
        state_file = tmp_state_dir / "heartbeat_nb2_pipeline.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["pipeline"] == "nb2_pipeline"
        assert data["duration_seconds"] == 45.3
        assert "last_success" in data

    def test_overwrites_existing(self, tmp_state_dir: Path) -> None:
        record_success("nb2_pipeline", duration_seconds=10.0, state_dir=tmp_state_dir)
        record_success("nb2_pipeline", duration_seconds=20.0, state_dir=tmp_state_dir)

        state_file = tmp_state_dir / "heartbeat_nb2_pipeline.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["duration_seconds"] == 20.0

    def test_none_duration(self, tmp_state_dir: Path) -> None:
        record_success("test_pipe", state_dir=tmp_state_dir)
        state_file = tmp_state_dir / "heartbeat_test_pipe.json"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert data["duration_seconds"] is None

    def test_creates_state_dir(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "nested" / "state"
        record_success("test_pipe", state_dir=new_dir)
        assert (new_dir / "heartbeat_test_pipe.json").exists()


# ---------------------------------------------------------------------------
# _read_heartbeat_state
# ---------------------------------------------------------------------------


class TestReadHeartbeatState:
    def test_existing_file(self, tmp_state_dir: Path) -> None:
        record_success("nb2_pipeline", duration_seconds=30, state_dir=tmp_state_dir)
        state = _read_heartbeat_state("nb2_pipeline", state_dir=tmp_state_dir)
        assert state is not None
        assert state["pipeline"] == "nb2_pipeline"

    def test_missing_file(self, tmp_state_dir: Path) -> None:
        state = _read_heartbeat_state("nonexistent", state_dir=tmp_state_dir)
        assert state is None

    def test_corrupt_file(self, tmp_state_dir: Path) -> None:
        corrupt = tmp_state_dir / "heartbeat_corrupt.json"
        corrupt.write_text("not json{{", encoding="utf-8")
        state = _read_heartbeat_state("corrupt", state_dir=tmp_state_dir)
        assert state is None


# ---------------------------------------------------------------------------
# _classify_staleness
# ---------------------------------------------------------------------------


class TestClassifyStaleness:
    def test_ok(self) -> None:
        assert _classify_staleness(10, 26) == STATUS_OK

    def test_ok_at_boundary(self) -> None:
        assert _classify_staleness(26, 26) == STATUS_OK

    def test_warning(self) -> None:
        # 1x-2x missed: e.g., 30h with max 26h => ratio ~1.15
        assert _classify_staleness(30, 26) == STATUS_WARNING

    def test_warning_at_boundary(self) -> None:
        # Exactly 2x should still be WARNING (ratio <= 2.0)
        assert _classify_staleness(52, 26) == STATUS_WARNING

    def test_critical(self) -> None:
        # 2x-3x missed: e.g., 60h with max 26h => ratio ~2.3
        assert _classify_staleness(60, 26) == STATUS_CRITICAL

    def test_critical_at_boundary(self) -> None:
        # Exactly 3x should still be CRITICAL (ratio <= 3.0)
        assert _classify_staleness(78, 26) == STATUS_CRITICAL

    def test_dead(self) -> None:
        # >3x missed: e.g., 100h with max 26h => ratio ~3.8
        assert _classify_staleness(100, 26) == STATUS_DEAD

    def test_zero_age(self) -> None:
        assert _classify_staleness(0, 26) == STATUS_OK


# ---------------------------------------------------------------------------
# check_all_heartbeats
# ---------------------------------------------------------------------------


class TestCheckAllHeartbeats:
    def test_all_ok(
        self, tmp_registry: Path, tmp_state_dir: Path
    ) -> None:
        """All pipelines ran recently -> all OK."""
        for name in ("test_daily", "test_weekday", "test_weekly"):
            record_success(name, duration_seconds=30, state_dir=tmp_state_dir)

        statuses = check_all_heartbeats(
            registry_path=tmp_registry, state_dir=tmp_state_dir
        )
        assert len(statuses) == 3
        assert all(s["status"] == STATUS_OK for s in statuses)

    def test_never_ran(
        self, tmp_registry: Path, tmp_state_dir: Path
    ) -> None:
        """No state files -> all NEVER_RAN."""
        statuses = check_all_heartbeats(
            registry_path=tmp_registry, state_dir=tmp_state_dir
        )
        assert len(statuses) == 3
        assert all(s["status"] == STATUS_NEVER_RAN for s in statuses)

    def test_stale_pipeline(
        self, tmp_registry: Path, tmp_state_dir: Path
    ) -> None:
        """One pipeline stale, others OK."""
        # Record recent success for two pipelines
        record_success("test_daily", duration_seconds=30, state_dir=tmp_state_dir)
        record_success("test_weekly", duration_seconds=30, state_dir=tmp_state_dir)

        # Manually write a stale timestamp for test_weekday (50 hours ago)
        stale_time = datetime.now(tz=WITA) - timedelta(hours=50)
        stale_file = tmp_state_dir / "heartbeat_test_weekday.json"
        stale_file.write_text(
            json.dumps({
                "pipeline": "test_weekday",
                "last_success": stale_time.isoformat(),
                "duration_seconds": 15,
            }),
            encoding="utf-8",
        )

        statuses = check_all_heartbeats(
            registry_path=tmp_registry, state_dir=tmp_state_dir
        )
        by_name = {s["pipeline"]: s for s in statuses}
        assert by_name["test_daily"]["status"] == STATUS_OK
        assert by_name["test_weekly"]["status"] == STATUS_OK
        # 50h / 26h max = ~1.92 -> WARNING
        assert by_name["test_weekday"]["status"] == STATUS_WARNING

    def test_dead_pipeline(
        self, tmp_registry: Path, tmp_state_dir: Path
    ) -> None:
        """Pipeline dead (3x+ missed)."""
        stale_time = datetime.now(tz=WITA) - timedelta(hours=100)
        stale_file = tmp_state_dir / "heartbeat_test_daily.json"
        stale_file.write_text(
            json.dumps({
                "pipeline": "test_daily",
                "last_success": stale_time.isoformat(),
                "duration_seconds": None,
            }),
            encoding="utf-8",
        )

        statuses = check_all_heartbeats(
            registry_path=tmp_registry, state_dir=tmp_state_dir
        )
        by_name = {s["pipeline"]: s for s in statuses}
        # 100h / 26h max = ~3.85 -> DEAD
        assert by_name["test_daily"]["status"] == STATUS_DEAD

    def test_empty_registry(self, tmp_path: Path) -> None:
        """Missing registry -> empty result."""
        statuses = check_all_heartbeats(
            registry_path=tmp_path / "nope.json",
            state_dir=tmp_path / "state",
        )
        assert statuses == []


# ---------------------------------------------------------------------------
# check_memory_pressure
# ---------------------------------------------------------------------------


class TestCheckMemoryPressure:
    @patch("apps.evaluator.nlm_deep_research.heartbeat_monitor.subprocess.run")
    def test_ok_pressure(self, mock_run: MagicMock) -> None:
        """Normal swap usage -> ok."""
        # Mock sysctl response
        sysctl_result = MagicMock()
        sysctl_result.returncode = 0
        sysctl_result.stdout = (
            "vm.swapusage: total = 2048.00M  used = 128.00M  free = 1920.00M"
        )

        vmstat_result = MagicMock()
        vmstat_result.returncode = 0
        vmstat_result.stdout = "Mach Virtual Memory Statistics:\nSwapins: 0\nSwapouts: 0\n"

        mock_run.side_effect = [sysctl_result, vmstat_result]

        result = check_memory_pressure()
        assert result["swap_used_mb"] == 128.0
        assert result["pressure"] == "ok"

    @patch("apps.evaluator.nlm_deep_research.heartbeat_monitor.subprocess.run")
    def test_warning_pressure(self, mock_run: MagicMock) -> None:
        """Elevated swap -> warning."""
        sysctl_result = MagicMock()
        sysctl_result.returncode = 0
        sysctl_result.stdout = (
            "vm.swapusage: total = 4096.00M  used = 768.00M  free = 3328.00M"
        )

        vmstat_result = MagicMock()
        vmstat_result.returncode = 0
        vmstat_result.stdout = ""

        mock_run.side_effect = [sysctl_result, vmstat_result]

        result = check_memory_pressure()
        assert result["swap_used_mb"] == 768.0
        assert result["pressure"] == "warning"

    @patch("apps.evaluator.nlm_deep_research.heartbeat_monitor.subprocess.run")
    def test_critical_pressure(self, mock_run: MagicMock) -> None:
        """High swap -> critical."""
        sysctl_result = MagicMock()
        sysctl_result.returncode = 0
        sysctl_result.stdout = (
            "vm.swapusage: total = 4096.00M  used = 2048.00M  free = 2048.00M"
        )

        vmstat_result = MagicMock()
        vmstat_result.returncode = 0
        vmstat_result.stdout = ""

        mock_run.side_effect = [sysctl_result, vmstat_result]

        result = check_memory_pressure()
        assert result["swap_used_mb"] == 2048.0
        assert result["pressure"] == "critical"

    @patch("apps.evaluator.nlm_deep_research.heartbeat_monitor.subprocess.run")
    def test_command_failure(self, mock_run: MagicMock) -> None:
        """sysctl fails -> returns 0 swap, ok."""
        mock_run.side_effect = FileNotFoundError("sysctl not found")
        result = check_memory_pressure()
        assert result["swap_used_mb"] == 0.0
        assert result["pressure"] == "ok"


# ---------------------------------------------------------------------------
# send_alert
# ---------------------------------------------------------------------------


class TestSendAlert:
    def test_no_alert_when_all_ok(self, capsys: pytest.CaptureFixture) -> None:
        """No Telegram message when all pipelines OK."""
        statuses = [
            {"pipeline": "nb2", "status": STATUS_OK, "last_success": "2026-04-03T01:15:00+08:00"},
        ]
        send_alert(statuses, dry_run=True)
        captured = capsys.readouterr()
        assert captured.out == ""  # No output because no alert

    def test_alert_on_warning(self, capsys: pytest.CaptureFixture) -> None:
        """Sends alert when WARNING present."""
        statuses = [
            {"pipeline": "nb2", "status": STATUS_OK, "last_success": "2026-04-03T01:15:00+08:00"},
            {"pipeline": "nb3", "status": STATUS_WARNING, "last_success": "2026-04-01T01:00:00+08:00"},
        ]
        send_alert(statuses, dry_run=True)
        captured = capsys.readouterr()
        assert "Pipeline Alert" in captured.out
        assert "nb3" in captured.out
        assert "WARNING" in captured.out

    def test_alert_on_dead(self, capsys: pytest.CaptureFixture) -> None:
        """Sends alert when DEAD present."""
        statuses = [
            {"pipeline": "nb2", "status": STATUS_DEAD, "last_success": "2026-03-20T01:00:00+08:00"},
        ]
        send_alert(statuses, dry_run=True)
        captured = capsys.readouterr()
        assert "DEAD" in captured.out

    def test_alert_on_never_ran(self, capsys: pytest.CaptureFixture) -> None:
        """Sends alert when NEVER_RAN present."""
        statuses = [
            {"pipeline": "nb99", "status": STATUS_NEVER_RAN, "last_success": None},
        ]
        send_alert(statuses, dry_run=True)
        captured = capsys.readouterr()
        assert "NEVER_RAN" in captured.out


# ---------------------------------------------------------------------------
# send_daily_digest
# ---------------------------------------------------------------------------


class TestSendDailyDigest:
    def test_digest_output(self, capsys: pytest.CaptureFixture) -> None:
        """Digest includes all pipelines and memory info."""
        statuses = [
            {"pipeline": "nb2", "status": STATUS_OK, "last_success": "2026-04-03T01:15:00+08:00", "duration_seconds": 45},
            {"pipeline": "nb3", "status": STATUS_WARNING, "last_success": "2026-04-01T01:00:00+08:00", "duration_seconds": None},
        ]
        memory = {"swap_used_mb": 256.0, "pressure": "ok"}

        send_daily_digest(statuses, memory=memory, dry_run=True)
        captured = capsys.readouterr()
        assert "Daily Digest" in captured.out
        assert "nb2" in captured.out
        assert "nb3" in captured.out
        assert "Swap" in captured.out
        assert "256" in captured.out


# ---------------------------------------------------------------------------
# _format_last_run
# ---------------------------------------------------------------------------


class TestFormatLastRun:
    def test_none(self) -> None:
        assert _format_last_run(None) == "never"

    def test_recent(self) -> None:
        recent = (datetime.now(tz=WITA) - timedelta(minutes=15)).isoformat()
        result = _format_last_run(recent)
        assert "m ago" in result

    def test_hours(self) -> None:
        hours_ago = (datetime.now(tz=WITA) - timedelta(hours=5)).isoformat()
        result = _format_last_run(hours_ago)
        assert "h ago" in result

    def test_days(self) -> None:
        days_ago = (datetime.now(tz=WITA) - timedelta(days=3)).isoformat()
        result = _format_last_run(days_ago)
        assert "d ago" in result

    def test_invalid(self) -> None:
        assert _format_last_run("not-a-date") == "invalid"

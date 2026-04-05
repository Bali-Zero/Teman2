"""Tests for new CELL sensors and components (Items 1-7)."""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── OllamaSensor ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ollama_sensor_green():
    from cell.sensors.ollama_sensor import OllamaSensor
    sensor = OllamaSensor(required_models=["qwen3.5:9b"])
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "qwen3.5:9b"}, {"name": "qwen3.5:27b"}]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        reading = await sensor.read()

    assert reading.status == "green"
    assert reading.reachable is True
    assert reading.missing_models == []


@pytest.mark.asyncio
async def test_ollama_sensor_yellow_missing_model():
    from cell.sensors.ollama_sensor import OllamaSensor
    sensor = OllamaSensor(required_models=["qwen3.5:9b", "qwen3.5:27b"])
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "qwen3.5:9b"}]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        reading = await sensor.read()

    assert reading.status == "yellow"
    assert "qwen3.5:27b" in reading.missing_models


@pytest.mark.asyncio
async def test_ollama_sensor_red_unreachable():
    from cell.sensors.ollama_sensor import OllamaSensor
    sensor = OllamaSensor()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        reading = await sensor.read()

    assert reading.status == "red"
    assert reading.reachable is False


# ── BackupSensor ──────────────────────────────────────────────────────────────

def test_backup_sensor_green_fresh_file():
    from cell.sensors.backup_sensor import BackupSensor
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fresh backup file (just now)
        backup_file = os.path.join(tmpdir, "nuzantara_2026-04-01.sql.gz")
        with open(backup_file, "w") as f:
            f.write("fake")
        sensor = BackupSensor(backup_dir=tmpdir, green_hours=26.0)
        reading = sensor.read()
    assert reading.status == "green"
    assert reading.last_backup_age_hours is not None
    assert reading.last_backup_age_hours < 1.0


def test_backup_sensor_red_no_files():
    from cell.sensors.backup_sensor import BackupSensor
    with tempfile.TemporaryDirectory() as tmpdir:
        sensor = BackupSensor(backup_dir=tmpdir, log_path="/nonexistent.log")
        reading = sensor.read()
    assert reading.status == "red"
    assert reading.last_backup_age_hours is None


def test_backup_sensor_yellow_old_file():
    from cell.sensors.backup_sensor import BackupSensor
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_file = os.path.join(tmpdir, "nuzantara_old.sql.gz")
        with open(backup_file, "w") as f:
            f.write("fake")
        # Backdate mtime by 30 hours
        old_time = time.time() - 30 * 3600
        os.utime(backup_file, (old_time, old_time))
        sensor = BackupSensor(backup_dir=tmpdir, green_hours=26.0, red_hours=50.0)
        reading = sensor.read()
    assert reading.status == "yellow"
    assert 28 < reading.last_backup_age_hours < 32  # type: ignore[operator]


# ── CronSensor ────────────────────────────────────────────────────────────────

def test_cron_sensor_green():
    from cell.sensors.cron_sensor import CronSensor
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "intel_scraper.last.json")
        with open(state_file, "w") as f:
            json.dump({"job": "intel_scraper", "ts": int(time.time()), "status": "ok"}, f)
        sensor = CronSensor(state_dir=tmpdir, job_periods={"intel_scraper": 24.0})
        reading = sensor.read()
        job = next(j for j in reading.jobs if j.name == "intel_scraper")
        assert job.status == "green"


def test_cron_sensor_red_stale():
    from cell.sensors.cron_sensor import CronSensor
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "intel_scraper.last.json")
        old_ts = int(time.time()) - 80 * 3600
        with open(state_file, "w") as f:
            json.dump({"job": "intel_scraper", "ts": old_ts, "status": "ok"}, f)
        sensor = CronSensor(state_dir=tmpdir, job_periods={"intel_scraper": 24.0})
        reading = sensor.read()
        job = next(j for j in reading.jobs if j.name == "intel_scraper")
        assert job.status == "red"
        assert reading.status == "red"


def test_cron_sensor_yellow_failed_status():
    from cell.sensors.cron_sensor import CronSensor
    import time
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "intel_scraper.last.json")
        with open(state_file, "w") as f:
            json.dump({"job": "intel_scraper", "ts": int(time.time()), "status": "failed"}, f)
        sensor = CronSensor(state_dir=tmpdir, job_periods={"intel_scraper": 24.0})
        reading = sensor.read()
        job = next(j for j in reading.jobs if j.name == "intel_scraper")
        # Recent but failed → yellow
        assert job.status == "yellow"
        assert reading.metadata["failed_jobs"] == ["intel_scraper"]


def test_cron_sensor_unknown_no_file():
    from cell.sensors.cron_sensor import CronSensor
    with tempfile.TemporaryDirectory() as tmpdir:
        sensor = CronSensor(state_dir=tmpdir, job_periods={"some_job": 6.0})
        reading = sensor.read()
        assert reading.jobs[0].status == "unknown"


# ── TrendDetector ─────────────────────────────────────────────────────────────

def test_trend_detector_monotonic_drift():
    from cell.fast.trend_detector import TrendDetector
    td = TrendDetector(drift_window=4)
    pulses = [
        {"health_status": "yellow", "response_time_ms": 100},
        {"health_status": "yellow", "response_time_ms": 200},
        {"health_status": "yellow", "response_time_ms": 300},
        {"health_status": "yellow", "response_time_ms": 400},
    ]
    result = td.detect(pulses)
    assert result.monotonic_drift is True
    assert result.flapping is False


def test_trend_detector_flapping():
    from cell.fast.trend_detector import TrendDetector
    td = TrendDetector(flap_window=6, flap_threshold=3)
    pulses = [
        {"health_status": "green", "response_time_ms": 100},
        {"health_status": "red", "response_time_ms": 500},
        {"health_status": "green", "response_time_ms": 100},
        {"health_status": "yellow", "response_time_ms": 300},
        {"health_status": "green", "response_time_ms": 100},
        {"health_status": "red", "response_time_ms": 500},
    ]
    result = td.detect(pulses)
    assert result.flapping is True


def test_trend_detector_sustained_degraded():
    from cell.fast.trend_detector import TrendDetector
    td = TrendDetector(sustained_window=3)
    pulses = [
        {"health_status": "red", "response_time_ms": 500},
        {"health_status": "yellow", "response_time_ms": 400},
        {"health_status": "red", "response_time_ms": 600},
    ]
    result = td.detect(pulses)
    assert result.sustained_degraded is True


def test_trend_detector_no_trends():
    from cell.fast.trend_detector import TrendDetector
    td = TrendDetector()
    pulses = [
        {"health_status": "green", "response_time_ms": 100},
        {"health_status": "green", "response_time_ms": 90},
    ]
    result = td.detect(pulses)
    assert result.monotonic_drift is False
    assert result.flapping is False
    assert result.sustained_degraded is False


# ── VercelSensor ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vercel_sensor_all_green():
    from cell.sensors.vercel_sensor import VercelSensor
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client.head = AsyncMock(return_value=mock_response)
    sensor = VercelSensor(client=mock_client, urls=["https://kita.balizero.com"])
    reading = await sensor.read()
    assert reading.status == "green"
    assert reading.subdomains[0].status == "green"


@pytest.mark.asyncio
async def test_vercel_sensor_redirect_green():
    """SSO redirects (301/302/307/308) are treated as green — site is alive and auth is working."""
    from cell.sensors.vercel_sensor import VercelSensor
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 307
    mock_client.head = AsyncMock(return_value=mock_response)
    sensor = VercelSensor(client=mock_client, urls=["https://kita.balizero.com"])
    reading = await sensor.read()
    assert reading.subdomains[0].status == "green"


@pytest.mark.asyncio
async def test_vercel_sensor_error_red():
    from cell.sensors.vercel_sensor import VercelSensor
    import httpx
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    sensor = VercelSensor(client=mock_client, urls=["https://kita.balizero.com"])
    reading = await sensor.read()
    assert reading.subdomains[0].status == "red"
    assert reading.status == "red"


# ── LocalEffector ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_local_effector_unknown_action():
    from cell.effectors.local_effector import LocalEffector
    eff = LocalEffector()
    result = await eff.execute("nonexistent_action")
    assert result.success is False
    assert "Unknown" in result.detail


@pytest.mark.asyncio
async def test_local_effector_ollama_restart_success():
    from cell.effectors.local_effector import LocalEffector
    import asyncio
    eff = LocalEffector()

    async def fake_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"Service restarted", b""))
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await eff.execute("ollama_restart")

    assert result.success is True
    assert result.action == "ollama_restart"


# ── Allowlist — new actions present ──────────────────────────────────────────

def test_allowlist_has_ollama_restart():
    from cell.effectors.allowlist import ActionRegistry
    reg = ActionRegistry()
    action = reg.get("ollama_restart")
    assert action.name == "ollama_restart"
    assert action.cooldown_seconds == 1800
    assert action.max_per_day == 3


def test_allowlist_has_run_backup():
    from cell.effectors.allowlist import ActionRegistry
    reg = ActionRegistry()
    action = reg.get("run_backup")
    assert action.name == "run_backup"
    assert action.cooldown_seconds == 3600
    assert action.max_per_day == 3

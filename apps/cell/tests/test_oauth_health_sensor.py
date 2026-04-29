"""Tests for OAuthHealthSensor (P1-11, zero-crash audit 2026-04-29).

The sensor consumes the JSON state file written by
`scripts/drive_token_watchdog.py`. We don't run the watchdog here; we
write fixture state files and assert the sensor classifies them correctly.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cell.sensors.oauth_health_sensor import OAuthHealthSensor


def _write_state(tmp_path: Path, **kwargs) -> str:
    """Write a watchdog-style state file and return its path."""
    p = tmp_path / "drive_oauth_watchdog.state.json"
    p.write_text(json.dumps(kwargs))
    return str(p)


class TestOAuthHealthSensor:
    def test_missing_state_file_is_unknown(self, tmp_path: Path) -> None:
        sensor = OAuthHealthSensor(state_path=str(tmp_path / "does_not_exist.json"))
        reading = sensor.read()
        assert reading.status == "unknown"
        assert "not found" in reading.metadata["reason"]

    def test_corrupt_state_file_is_unknown(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.json"
        p.write_text("not valid json {{{")
        sensor = OAuthHealthSensor(state_path=str(p))
        reading = sensor.read()
        assert reading.status == "unknown"

    def test_tier_ok_classifies_green(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="ok",
            last_oauth_check_iso=now.isoformat(),
            last_oauth_days_left=60,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "green"
        assert reading.tier == "ok"
        assert reading.days_left == 60

    def test_tier_info_30d_classifies_green(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="info_30d",
            last_oauth_check_iso=now.isoformat(),
            last_oauth_days_left=25,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        # 30d window is still "green" in Cell terms — heads-up only,
        # nothing actionable. Yellow/red kicks in at 14d/7d.
        assert reading.status == "green"
        assert reading.tier == "info_30d"

    def test_tier_warning_14d_classifies_yellow(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="warning_14d",
            last_oauth_check_iso=now.isoformat(),
            last_oauth_days_left=10,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "yellow"
        assert reading.tier == "warning_14d"

    def test_tier_urgent_7d_classifies_red(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="urgent_7d",
            last_oauth_check_iso=now.isoformat(),
            last_oauth_days_left=5,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "red"
        assert reading.tier == "urgent_7d"
        assert reading.days_left == 5

    def test_tier_critical_1d_classifies_red(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="critical_1d",
            last_oauth_check_iso=now.isoformat(),
            last_oauth_days_left=0,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "red"

    def test_tier_expired_classifies_red(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="critical_expired",
            last_oauth_check_iso=now.isoformat(),
            last_oauth_days_left=-3,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "red"
        assert reading.tier == "critical_expired"

    def test_stale_state_classifies_yellow(self, tmp_path: Path) -> None:
        # Watchdog last ran 25h ago — stale (>18h threshold).
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        old = now - timedelta(hours=25)
        path = _write_state(
            tmp_path,
            last_oauth_tier="ok",  # would be green if fresh
            last_oauth_check_iso=old.isoformat(),
            last_oauth_days_left=60,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        # Even though tier=ok, staleness pushes it to yellow.
        assert reading.status == "yellow"
        assert "stale" in reading.metadata["reason"]

    def test_fresh_state_within_threshold_uses_tier(self, tmp_path: Path) -> None:
        # Watchdog ran 6h ago — fresh.
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        recent = now - timedelta(hours=6)
        path = _write_state(
            tmp_path,
            last_oauth_tier="ok",
            last_oauth_check_iso=recent.isoformat(),
            last_oauth_days_left=60,
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "green"

    def test_state_with_no_tier_is_unknown(self, tmp_path: Path) -> None:
        # State file exists but watchdog hasn't classified yet
        # (e.g. backend was unreachable last run).
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_check_iso=now.isoformat(),
            # NO last_oauth_tier
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "unknown"

    def test_unknown_tier_value_returns_unknown(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
        path = _write_state(
            tmp_path,
            last_oauth_tier="some_future_tier_we_dont_know",
            last_oauth_check_iso=now.isoformat(),
        )
        sensor = OAuthHealthSensor(state_path=path)
        reading = sensor.read(now=now)
        assert reading.status == "unknown"

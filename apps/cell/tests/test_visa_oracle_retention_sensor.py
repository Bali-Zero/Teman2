from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cell.sensors.cron_sensor import CronSensor, _JOB_PERIODS, _JOB_THRESHOLDS


def _write_state(directory: Path, *, age_minutes: float, status: str = "ok") -> None:
    state = {
        "job": "visa_oracle_retention",
        "ts": time.time() - (age_minutes * 60),
        "status": status,
        "host": "test-host",
    }
    (directory / "visa_oracle_retention.last.json").write_text(
        json.dumps(state),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("age_minutes", "expected"),
    [(29, "green"), (31, "yellow"), (61, "red")],
)
def test_visa_oracle_missed_run_thresholds(
    tmp_path: Path,
    age_minutes: float,
    expected: str,
) -> None:
    _write_state(tmp_path, age_minutes=age_minutes)

    reading = CronSensor(
        state_dir=str(tmp_path),
        job_periods={"visa_oracle_retention": 0.25},
        job_thresholds={"visa_oracle_retention": (0.5, 1.0)},
    ).read()

    assert reading.jobs[0].status == expected


def test_default_inventory_arms_visa_oracle_retention_sensor() -> None:
    assert _JOB_PERIODS["visa_oracle_retention"] == 0.25
    assert _JOB_THRESHOLDS["visa_oracle_retention"] == (0.5, 1.0)

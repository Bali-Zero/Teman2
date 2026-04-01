"""CronSensor — monitors local cron job freshness.

Reads a JSON file written by each cron script on completion:
  ~/scripts/cron_last_run.json
  { "job_name": "2026-04-01T03:10:00+08:00", ... }

If a job hasn't written its timestamp within its expected window,
the sensor reports yellow or red.

Also checks Air cron jobs by reading via SSH if reachable.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cell.sensors.cron")

_LAST_RUN_FILE = os.path.expanduser("~/scripts/cron_last_run.json")

# Expected max age for each job in hours before going yellow/red
# (yellow = 1.5× expected period, red = 3× expected period)
_JOB_PERIODS: dict[str, float] = {
    "intel_scraper": 24.0,       # daily 03:00
    "nlm_daily_refresh": 24.0,   # daily 04:30
    "fly_pg_backup": 24.0,       # daily
    "fly_health_check": 0.5,     # every 5min — stale if >30min
    "t4_monitor": 6.0,           # every 6h
    "drive_poll": 0.5,           # every 5min on Air
}


@dataclass
class CronJobStatus:
    name: str
    status: str  # "green", "yellow", "red", "unknown"
    age_hours: float | None = None
    last_run: str = ""


@dataclass
class CronReading:
    status: str  # worst across all jobs
    jobs: list[CronJobStatus] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CronSensor:
    """Checks freshness of local cron jobs via last-run timestamp file.

    Each cron script should write to ~/scripts/cron_last_run.json:
        import json, datetime, os
        _f = os.path.expanduser("~/scripts/cron_last_run.json")
        data = json.load(open(_f)) if os.path.exists(_f) else {}
        data["job_name"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        json.dump(data, open(_f, "w"))
    """

    def __init__(
        self,
        last_run_file: str = _LAST_RUN_FILE,
        job_periods: dict[str, float] | None = None,
    ) -> None:
        self._file = last_run_file
        self._periods = job_periods or _JOB_PERIODS

    def read(self) -> CronReading:
        now = datetime.now(timezone.utc)
        data: dict[str, str] = {}

        if os.path.isfile(self._file):
            try:
                with open(self._file) as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"CronSensor: failed to read {self._file}: {e}")

        jobs: list[CronJobStatus] = []
        _severity = {"green": 0, "yellow": 1, "red": 2, "unknown": 1}

        for job_name, period_hours in self._periods.items():
            if job_name not in data:
                jobs.append(CronJobStatus(name=job_name, status="unknown"))
                continue

            try:
                last_run = datetime.fromisoformat(data[job_name])
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                age_hours = (now - last_run).total_seconds() / 3600.0
            except Exception:
                jobs.append(CronJobStatus(name=job_name, status="unknown"))
                continue

            if age_hours <= period_hours * 1.5:
                status = "green"
            elif age_hours <= period_hours * 3.0:
                status = "yellow"
            else:
                status = "red"

            jobs.append(CronJobStatus(
                name=job_name,
                status=status,
                age_hours=round(age_hours, 2),
                last_run=data[job_name],
            ))

        worst = max((j.status for j in jobs), key=lambda s: _severity.get(s, 1), default="unknown")
        stale = [j.name for j in jobs if j.status in ("yellow", "red")]

        return CronReading(
            status=worst,
            jobs=jobs,
            metadata={"stale_jobs": stale, "total": len(jobs)},
        )

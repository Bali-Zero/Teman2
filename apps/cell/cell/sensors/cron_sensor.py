"""CronSensor — monitors cron/agent job freshness.

Reads ~/.agent/decisions/state/*.last.json files written by every
OpenClaw agent and cron script on completion. Format:
  {"job": "fly_pg_backup", "ts": 1774521542, "status": "ok", "host": "..."}

ts is a Unix timestamp (seconds). status is "ok" or "failed".
"""
import glob
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cell.sensors.cron")

_STATE_DIR = os.path.expanduser("~/.agent/decisions/state")

# Expected max period in hours for each watched job.
# (yellow = 1.5× period, red = 3× period)
_JOB_PERIODS: dict[str, float] = {
    "fly_pg_backup":       24.0,   # daily
    "intel_scraper":       24.0,   # daily 03:00
    "nlm_deep_research":   24.0,   # daily 04:30
    "t4_monitor_daily":     6.0,   # every 6h
    # "war_room" removed 2026-04-27: WR1 was decommissioned by PR #171
    # (apps/war-room/pipeline.sh deleted). The intel-nightly LaunchAgent
    # already logs "skip" for it, but the watcher kept marking it failed
    # and flooded Cell pulses with red. WR2 has its own supervisor.
    # "fly_health_check" removed 2026-04-30 (renaissance follow-up):
    # MIGRATED to fly-watcher 2026-04-14 (see crontab Pro). The state
    # file ~/.agent/decisions/state/fly_health_check.last.json hasn't
    # been updated since the migration — it's frozen at 373h+ and was
    # flooding Cell pulses red post-PR-C5.
    # "core_guardian" removed 2026-04-30 (renaissance follow-up):
    # PR #367 (PR-C5) deleted the cron line `0 */3 * * * core-guardian`
    # because 30 weeks of runs always reported `candidates=0 fixed=0`
    # — pure dead code. The cron sensor was still expecting a 4h
    # heartbeat and flooding Cell pulses red every minute.
    "system_doctor":       24.0,   # daily 08:00
    "expiry_alerter":      24.0,   # daily
    "knowledge_graph_builder": 24.0,
    "metabolic_rollup":        24.0,   # daily 23:30
}


@dataclass
class CronJobStatus:
    name: str
    status: str          # "green", "yellow", "red", "unknown", "failed"
    age_hours: float | None = None
    last_run: str = ""
    last_job_status: str = ""  # "ok" / "failed" as reported by the job


@dataclass
class CronReading:
    status: str          # worst across watched jobs
    jobs: list[CronJobStatus] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CronSensor:
    """Reports freshness of watched cron jobs from state files.

    Reads ~/.agent/decisions/state/<job>.last.json for each watched job.
    A job is classified:
      green   — ran within 1.5× expected period AND status=ok
      yellow  — ran within 3× period, OR status=failed
      red     — not run in 3× period
      unknown — state file missing
    """

    def __init__(
        self,
        state_dir: str = _STATE_DIR,
        job_periods: dict[str, float] | None = None,
    ) -> None:
        self._dir = state_dir
        self._periods = job_periods or _JOB_PERIODS

    def read(self) -> CronReading:
        now = datetime.now(timezone.utc)
        _severity = {"green": 0, "yellow": 1, "red": 2, "unknown": 1, "failed": 2}
        jobs: list[CronJobStatus] = []

        for job_name, period_hours in self._periods.items():
            # State file may use hyphens or underscores interchangeably
            candidates = [
                os.path.join(self._dir, f"{job_name}.last.json"),
                os.path.join(self._dir, f"{job_name.replace('_', '-')}.last.json"),
            ]
            state: dict[str, Any] | None = None
            for path in candidates:
                if os.path.isfile(path):
                    try:
                        with open(path) as f:
                            state = json.load(f)
                        break
                    except Exception as e:
                        logger.debug(f"CronSensor: failed to read {path}: {e}")

            if state is None:
                jobs.append(CronJobStatus(name=job_name, status="unknown"))
                continue

            ts = state.get("ts")
            job_ok = state.get("status", "ok") == "ok"

            if not ts:
                jobs.append(CronJobStatus(name=job_name, status="unknown"))
                continue

            age_hours = (now.timestamp() - float(ts)) / 3600.0
            last_run_iso = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()

            if not job_ok:
                # Job ran but reported failure
                cron_status = "yellow" if age_hours <= period_hours * 3.0 else "red"
            elif age_hours <= period_hours * 1.5:
                cron_status = "green"
            elif age_hours <= period_hours * 3.0:
                cron_status = "yellow"
            else:
                cron_status = "red"

            jobs.append(CronJobStatus(
                name=job_name,
                status=cron_status,
                age_hours=round(age_hours, 2),
                last_run=last_run_iso,
                last_job_status=state.get("status", "?"),
            ))

        worst = max(
            (j.status for j in jobs),
            key=lambda s: _severity.get(s, 1),
            default="unknown",
        )
        stale = [j.name for j in jobs if j.status in ("yellow", "red")]
        failed = [j.name for j in jobs if j.last_job_status == "failed"]

        return CronReading(
            status=worst,
            jobs=jobs,
            metadata={"stale_jobs": stale, "failed_jobs": failed, "total": len(jobs)},
        )

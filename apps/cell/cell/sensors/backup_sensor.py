"""BackupSensor — checks recency of the last Fly.io Postgres backup.

Reads the most recent .sql.gz file in the Tigris backup bucket
via the local backup script's output directory, or queries the
fly-pg-backup.sh log to find the last success timestamp.

Strategy: look for the newest *.sql.gz under ~/backups/nuzantara/
and compare its mtime against max_age_hours. Fallback: check
fly-pg-backup.log for the last "BACKUP_COMPLETE" line.
"""
import glob
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cell.sensors.backup")

_DEFAULT_BACKUP_DIR = os.path.expanduser("~/backups/nuzantara")
_DEFAULT_LOG = os.path.expanduser("~/scripts/fly-pg-backup.log")
_COMPLETE_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")


@dataclass
class BackupReading:
    status: str  # "green", "yellow", "red"
    last_backup_age_hours: float | None = None
    last_backup_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BackupSensor:
    """Reports how fresh the most recent PG backup is.

    green  — backup younger than green_hours (default 26h)
    yellow — backup between green_hours and red_hours (default 50h)
    red    — backup older than red_hours or no backup found
    """

    def __init__(
        self,
        backup_dir: str = _DEFAULT_BACKUP_DIR,
        log_path: str = _DEFAULT_LOG,
        green_hours: float = 26.0,
        red_hours: float = 50.0,
    ) -> None:
        self._backup_dir = backup_dir
        self._log_path = log_path
        self._green = green_hours
        self._red = red_hours

    def read(self) -> BackupReading:
        now = datetime.now(timezone.utc)

        # Primary: scan backup directory for newest .sql.gz
        newest_path, newest_mtime = self._scan_dir()

        if newest_path:
            age_hours = (now.timestamp() - newest_mtime) / 3600.0
            return self._classify(age_hours, newest_path)

        # Fallback: parse log file for last BACKUP_COMPLETE timestamp
        log_ts = self._parse_log()
        if log_ts:
            age_hours = (now - log_ts).total_seconds() / 3600.0
            return self._classify(age_hours, self._log_path)

        return BackupReading(
            status="red",
            last_backup_age_hours=None,
            metadata={"reason": "no backup file or log entry found"},
        )

    def _scan_dir(self) -> tuple[str, float]:
        if not os.path.isdir(self._backup_dir):
            return "", 0.0
        files = glob.glob(os.path.join(self._backup_dir, "*.sql.gz"))
        if not files:
            return "", 0.0
        newest = max(files, key=os.path.getmtime)
        return newest, os.path.getmtime(newest)

    def _parse_log(self) -> datetime | None:
        if not os.path.isfile(self._log_path):
            return None
        try:
            with open(self._log_path) as f:
                lines = f.readlines()
            # Scan backwards for last BACKUP_COMPLETE line
            for line in reversed(lines):
                if "BACKUP_COMPLETE" in line or "uploaded" in line.lower():
                    m = _COMPLETE_RE.search(line)
                    if m:
                        return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.debug(f"BackupSensor log parse failed: {e}")
        return None

    def _classify(self, age_hours: float, path: str) -> BackupReading:
        if age_hours <= self._green:
            status = "green"
        elif age_hours <= self._red:
            status = "yellow"
        else:
            status = "red"
        return BackupReading(
            status=status,
            last_backup_age_hours=round(age_hours, 1),
            last_backup_path=path,
            metadata={"age_hours": round(age_hours, 1), "path": os.path.basename(path)},
        )

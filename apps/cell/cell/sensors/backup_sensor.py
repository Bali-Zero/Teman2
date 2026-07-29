"""BackupSensor — is there a PROVEN OFF-SITE Postgres backup, and how old is it?

Rewritten 2026-07-27 after an audit found this sensor structurally unable to see the
failure it exists to catch.

It used to report the age of the newest ``*.sql.gz`` in the LOCAL backup directory. But
the local dump is written on the way to Tigris and survives every failure downstream of
it — so on 2026-07-15, when neither nightly run put an object in the bucket, the local
file was there (369 MB, integrity-checked) and this sensor would have been **green over a
night with no backup at all**. Same shape as the bug in ``fly-pg-backup.sh`` itself, which
declared success by reaching its own last line: a proxy standing in for the artifact.

So the primary signal is now the receipt ``.offsite-verified.json``, written by
``fly-pg-backup.sh`` **only** after ``verify_offsite_object`` has listed the object in the
bucket. No receipt means no proof, and no proof is never green:

    green  — receipt younger than green_hours (default 26h)
    yellow — receipt between green_hours and red_hours, OR a fresh local dump with no
             receipt at all (we have bytes, we cannot prove they left the machine)
    red    — receipt older than red_hours, or nothing to go on

The yellow-without-receipt rung matters for rollout: until the next nightly runs, no
receipt exists yet, and turning that into red would cry wolf on day one. It is also the
honest reading of a machine where the gate is not running.
"""
import glob
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cell.sensors.backup")

_DEFAULT_BACKUP_DIR = os.path.expanduser("~/backups/fly-postgres")
# 2026-07-27: was ~/scripts/fly-pg-backup.log, which does not exist — the log lives under
# ~/logs/cron/. A fallback pointed at a missing file is not a fallback.
_DEFAULT_LOG = os.path.expanduser("~/logs/cron/fly-pg-backup.log")
_RECEIPT_NAME = ".offsite-verified.json"
# The log stamps "[2026-07-27 03:20:39]" with a SPACE; the old pattern demanded a "T" and
# therefore never matched a real line, so this branch could not fire either.
_COMPLETE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})")


@dataclass
class BackupReading:
    status: str  # "green", "yellow", "red"
    last_backup_age_hours: float | None = None
    last_backup_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BackupSensor:
    """Reports how fresh the most recent PROVEN OFF-SITE PG backup is."""

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

        # Primary: the off-site receipt. This is the only signal that means "an object
        # was listed in the bucket", which is the only thing that makes a backup a backup.
        receipt_ts, receipt_obj, receipt_path = self._read_receipt()
        if receipt_ts is not None:
            age_hours = (now.timestamp() - receipt_ts) / 3600.0
            return self._classify(
                age_hours,
                receipt_path,
                offsite="proven",
                extra={"object": receipt_obj} if receipt_obj else None,
            )

        # No receipt. A local dump still tells us the dump machinery ran, but says nothing
        # about whether the copy left this machine — so it can never be green.
        newest_path, newest_mtime = self._scan_dir()
        if newest_path:
            age_hours = (now.timestamp() - newest_mtime) / 3600.0
            reading = self._classify(age_hours, newest_path, offsite="unproven")
            if reading.status == "green":
                reading.status = "yellow"
                reading.metadata["downgraded"] = "local dump only — no off-site receipt"
            return reading

        log_ts = self._parse_log()
        if log_ts:
            age_hours = (now - log_ts).total_seconds() / 3600.0
            reading = self._classify(age_hours, self._log_path, offsite="unproven")
            if reading.status == "green":
                reading.status = "yellow"
                reading.metadata["downgraded"] = "log line only — no off-site receipt"
            return reading

        return BackupReading(
            status="red",
            last_backup_age_hours=None,
            metadata={"reason": "no off-site receipt, no local backup, no log entry", "offsite": "unknown"},
        )

    def _read_receipt(self) -> tuple[float | None, str, str]:
        path = os.path.join(self._backup_dir, _RECEIPT_NAME)
        if not os.path.isfile(path):
            return None, "", path
        try:
            with open(path) as fh:
                payload = json.load(fh)
            obj = str(payload.get("object", ""))
            raw = payload.get("verified_at")
            if raw:
                ts = datetime.fromisoformat(str(raw))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts.timestamp(), obj, path
            # A receipt whose timestamp we cannot parse still proves an upload happened;
            # fall back to its mtime rather than discarding the only real evidence.
            return os.path.getmtime(path), obj, path
        except Exception as e:
            logger.debug(f"BackupSensor receipt parse failed: {e}")
            return None, "", path

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
            for line in reversed(lines):
                low = line.lower()
                if "backup_complete" in low or "uploaded" in low or "verified off-site" in low:
                    m = _COMPLETE_RE.search(line)
                    if m:
                        return datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}").replace(
                            tzinfo=timezone.utc
                        )
        except Exception as e:
            logger.debug(f"BackupSensor log parse failed: {e}")
        return None

    def _classify(
        self,
        age_hours: float,
        path: str,
        offsite: str = "unknown",
        extra: dict[str, Any] | None = None,
    ) -> BackupReading:
        if age_hours <= self._green:
            status = "green"
        elif age_hours <= self._red:
            status = "yellow"
        else:
            status = "red"
        meta: dict[str, Any] = {
            "age_hours": round(age_hours, 1),
            "path": os.path.basename(path),
            "offsite": offsite,
        }
        if extra:
            meta.update(extra)
        return BackupReading(
            status=status,
            last_backup_age_hours=round(age_hours, 1),
            last_backup_path=path,
            metadata=meta,
        )

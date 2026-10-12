"""fly_pg_backup is a retired job key: freshness must follow fly_backup.last.json."""
import json
import time

from cell.sensors.cron_sensor import CronSensor


def _write(d, name, age_h):
    (d / name).write_text(json.dumps({"ts": time.time() - age_h * 3600, "status": "ok"}))


def _job(tmp_path):
    r = CronSensor(state_dir=str(tmp_path), job_periods={"fly_pg_backup": 24.0}).read()
    return r.jobs[0]


def test_fresh_fly_backup_receipt_beats_stale_retired_receipt(tmp_path):
    _write(tmp_path, "fly_pg_backup.last.json", 500)
    _write(tmp_path, "fly_backup.last.json", 2)
    assert _job(tmp_path).status == "green"


def test_both_stale_is_red(tmp_path):
    _write(tmp_path, "fly_pg_backup.last.json", 500)
    _write(tmp_path, "fly_backup.last.json", 500)
    assert _job(tmp_path).status == "red"


def test_legacy_receipt_still_read_when_new_absent(tmp_path):
    _write(tmp_path, "fly_pg_backup.last.json", 2)
    assert _job(tmp_path).status == "green"

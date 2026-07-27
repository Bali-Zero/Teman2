"""Proof that BackupSensor judges the OFF-SITE artifact, not the local dump.

The sensor exists to notice "we have no backup". Before 2026-07-27 it reported the age of
the newest local ``*.sql.gz`` — a file that is written on the way to Tigris and survives
every failure after it. On 2026-07-15 neither nightly run put an object in the bucket and
the local dump was perfectly fine, so the sensor was green over a night with no backup.

GUILT here is therefore the 15/7 world: a fresh local dump and NO receipt must not be
green. INNOCENCE is the ordinary good night: a fresh receipt is green, and a machine that
genuinely has nothing is red rather than silently absent.

Everything runs against ``tmp_path``. Nothing in this file may touch ~/backups (W96: a
test that writes production state is worse than no test).
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from cell.sensors.backup_sensor import BackupSensor


def _dump(dirpath, name="nuzantara-fly-20260727-0300.sql.gz", age_hours=0.0):
    p = os.path.join(dirpath, name)
    with open(p, "w") as fh:
        fh.write("x")
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(p, (old, old))
    return p


def _receipt(dirpath, age_hours=0.0, obj="nuzantara-fly-20260727-0300.sql.gz"):
    ts = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    p = os.path.join(dirpath, ".offsite-verified.json")
    with open(p, "w") as fh:
        json.dump({"object": obj, "verified_at": ts.strftime("%Y-%m-%dT%H:%M:%S"), "bucket": "b"}, fh)
    return p


@pytest.fixture
def sensor_dir(tmp_path):
    d = tmp_path / "fly-postgres"
    d.mkdir()
    return str(d)


def _sensor(d, log="/nonexistent/fly-pg-backup.log"):
    return BackupSensor(backup_dir=d, log_path=log)


# ── INNOCENCE — a real good night must stay green, or the gate gets ignored ──────────
def test_fresh_receipt_is_green(sensor_dir):
    _dump(sensor_dir)
    _receipt(sensor_dir, age_hours=1.0)
    r = _sensor(sensor_dir).read()
    assert r.status == "green"
    assert r.metadata["offsite"] == "proven"
    assert r.metadata["object"] == "nuzantara-fly-20260727-0300.sql.gz"


# ── GUILT — the 2026-07-15 world: local dump present, nothing off-site ───────────────
def test_fresh_local_dump_without_receipt_is_not_green(sensor_dir):
    _dump(sensor_dir, age_hours=0.5)
    r = _sensor(sensor_dir).read()
    assert r.status != "green", "a local dump alone proved nothing on 15/7 and proves nothing now"
    assert r.status == "yellow"
    assert r.metadata["offsite"] == "unproven"
    assert "downgraded" in r.metadata


def test_stale_receipt_goes_red(sensor_dir):
    _dump(sensor_dir)
    _receipt(sensor_dir, age_hours=72.0)
    assert _sensor(sensor_dir).read().status == "red"


def test_receipt_between_thresholds_is_yellow(sensor_dir):
    _receipt(sensor_dir, age_hours=30.0)
    assert _sensor(sensor_dir).read().status == "yellow"


def test_nothing_at_all_is_red(sensor_dir):
    r = _sensor(sensor_dir).read()
    assert r.status == "red"
    assert r.last_backup_age_hours is None


def test_receipt_wins_over_a_newer_local_dump(sensor_dir):
    """A dump written after the last successful upload must not mask a stale off-site copy."""
    _dump(sensor_dir, age_hours=0.0)
    _receipt(sensor_dir, age_hours=72.0)
    r = _sensor(sensor_dir).read()
    assert r.status == "red"
    assert r.metadata["offsite"] == "proven"


def test_unparseable_receipt_falls_back_to_its_mtime(sensor_dir):
    p = os.path.join(sensor_dir, ".offsite-verified.json")
    with open(p, "w") as fh:
        fh.write("{not json")
    _dump(sensor_dir, age_hours=0.5)
    # Broken receipt => treated as absent => local-dump path => never green.
    assert _sensor(sensor_dir).read().status == "yellow"


# ── the log fallback used to point at a missing file AND demand a "T" separator ──────
def test_log_fallback_accepts_the_real_space_separated_stamp(tmp_path, sensor_dir):
    log = tmp_path / "fly-pg-backup.log"
    stamp = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    log.write_text(f"[{stamp}] Uploaded to Tigris: s3://b/postgres/x.sql.gz\n")
    r = BackupSensor(backup_dir=sensor_dir, log_path=str(log)).read()
    assert r.last_backup_age_hours is not None, "the real log format must be parseable"
    assert r.status == "yellow", "a log line is not proof of the artifact either"

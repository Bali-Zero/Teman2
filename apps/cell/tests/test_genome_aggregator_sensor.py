"""Tests for `cell.sensors.genome_aggregator_sensor`.

The aggregator merges three sources — genome.yaml, ~/.organism/last_seen.db
(SQLite, per-machine, written by Supervisor in Wave 2), and bridge_source
state files (per organ, optional override) — into a single SensorReading
with green/yellow/red aggregate status.

Six cases per 99c_w0a_bis_kickoff.md §3.1:

1. all alive → green
2. some stale → yellow
3. some dead → red
4. genome.yaml missing → red + error metadata
5. last_seen.db missing → all (non-bridged) organi treated as dead, status reported
6. bridge_source override → bridge timestamp wins over last_seen.db lookup
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

import yaml

from cell.sensors.genome_aggregator_sensor import (
    GenomeAggregatorSensor,
    SensorReading,
)


# ---------- helpers ---------------------------------------------------------


def _write_genome(path: Path, organs: list[dict]) -> None:
    payload = {
        "version": 1,
        "checksum_algo": "sha256",
        "checksum": "0" * 64,  # not validated by the sensor
        "organs": organs,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def _write_last_seen_db(path: Path, rows: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE organ_last_seen (organ_id TEXT PRIMARY KEY, last_seen REAL)"
        )
        conn.executemany(
            "INSERT INTO organ_last_seen (organ_id, last_seen) VALUES (?, ?)",
            list(rows.items()),
        )
        conn.commit()
    finally:
        conn.close()


def _organ(
    organ_id: str,
    *,
    expected_hb_seconds: int = 60,
    bridge_path: Path | None = None,
) -> dict:
    out = {
        "id": organ_id,
        "runtime": "pro_launchd",
        "type": "cron",
        "expected_hb_seconds": expected_hb_seconds,
        "owner_module": f"fake/{organ_id}",
        "dependencies": [],
        "recovery_action": "noop",
        "recovery_params": {},
        "severity_on_silence": "warning",
        "cicatrix_refs": [],
    }
    if bridge_path is not None:
        out["bridge_source"] = {
            "type": "state_file",
            "path": str(bridge_path),
            "timestamp_field": "ts",
            "status_field": "status",
        }
    return out


def _run(sensor: GenomeAggregatorSensor) -> SensorReading:
    """Drive the async API for parity with PulseEngine wiring."""
    return asyncio.run(sensor.read())


# ---------- tests -----------------------------------------------------------


def test_all_alive_returns_green(tmp_path):
    """Three organi, all heartbeated within 1.5x expected → green."""
    genome = tmp_path / "genome.yaml"
    db = tmp_path / "last_seen.db"
    now = time.time()

    _write_genome(
        genome,
        [
            _organ("organ.a", expected_hb_seconds=60),
            _organ("organ.b", expected_hb_seconds=60),
            _organ("organ.c", expected_hb_seconds=120),
        ],
    )
    _write_last_seen_db(
        db,
        {
            "organ.a": now - 10,
            "organ.b": now - 30,
            "organ.c": now - 90,  # 0.75x of 120 → alive
        },
    )

    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    reading = _run(sensor)

    assert reading.status == "green"
    assert reading.metadata["total_organs"] == 3
    assert reading.metadata["alive"] == 3
    assert reading.metadata["stale"] == 0
    assert reading.metadata["dead"] == 0
    assert reading.metadata["dead_organs"] == []


def test_some_stale_returns_yellow_with_count(tmp_path):
    """One organ between 1.5x and 3x expected → stale → yellow aggregate."""
    genome = tmp_path / "genome.yaml"
    db = tmp_path / "last_seen.db"
    now = time.time()

    _write_genome(
        genome,
        [
            _organ("organ.a", expected_hb_seconds=60),  # alive
            _organ("organ.b", expected_hb_seconds=60),  # stale (120s > 1.5*60)
        ],
    )
    _write_last_seen_db(
        db,
        {
            "organ.a": now - 30,
            "organ.b": now - 120,  # 2x of 60 → stale band
        },
    )

    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    reading = _run(sensor)

    assert reading.status == "yellow"
    assert reading.metadata["alive"] == 1
    assert reading.metadata["stale"] == 1
    assert reading.metadata["dead"] == 0
    assert "organ.b" in reading.metadata["stale_organs"]


def test_some_dead_returns_red_with_dead_organs_list(tmp_path):
    """An organ with last_seen ≥ 3x expected (or no entry) → dead → red."""
    genome = tmp_path / "genome.yaml"
    db = tmp_path / "last_seen.db"
    now = time.time()

    _write_genome(
        genome,
        [
            _organ("organ.a", expected_hb_seconds=60),  # alive
            _organ("organ.b", expected_hb_seconds=60),  # dead (300s > 3*60)
        ],
    )
    _write_last_seen_db(
        db,
        {
            "organ.a": now - 10,
            "organ.b": now - 300,
        },
    )

    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    reading = _run(sensor)

    assert reading.status == "red"
    assert reading.metadata["dead"] == 1
    assert reading.metadata["dead_organs"] == ["organ.b"]


def test_missing_genome_yaml_reports_error_metadata(tmp_path):
    """Missing genome → red + error metadata."""
    genome = tmp_path / "does_not_exist.yaml"
    db = tmp_path / "last_seen.db"

    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    reading = _run(sensor)

    assert reading.status == "red"
    assert reading.metadata["error"] == "genome_missing"
    assert "does_not_exist.yaml" in reading.metadata["genome_path"]


def test_missing_last_seen_db_treats_organi_as_dead(tmp_path):
    """No last_seen.db → all non-bridge organi go dead, status reports it."""
    genome = tmp_path / "genome.yaml"
    db = tmp_path / "last_seen.db"  # NOT created

    _write_genome(
        genome,
        [
            _organ("organ.a", expected_hb_seconds=60),
            _organ("organ.b", expected_hb_seconds=60),
        ],
    )

    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    reading = _run(sensor)

    assert reading.status == "red"
    assert reading.metadata["dead"] == 2
    assert set(reading.metadata["dead_organs"]) == {"organ.a", "organ.b"}
    assert reading.metadata["last_seen_db_status"] == "missing"


def test_bridge_source_override_wins_over_last_seen_db(tmp_path):
    """Organ with a bridge_source uses bridge timestamp, NOT last_seen.db.

    Wires together both inputs in one merge: organ.a has BOTH a stale
    last_seen.db entry AND a fresh bridge state file. The fresh bridge
    must win → alive.
    """
    genome = tmp_path / "genome.yaml"
    db = tmp_path / "last_seen.db"
    bridge_state = tmp_path / "organ_a.last.json"
    now = time.time()

    bridge_state.write_text(json.dumps({"ts": now - 10, "status": "ok"}))

    _write_genome(
        genome,
        [
            _organ(
                "organ.a",
                expected_hb_seconds=60,
                bridge_path=bridge_state,
            ),
        ],
    )
    _write_last_seen_db(
        db,
        {
            # Stale from the SQLite point of view (300s > 3*60). If the
            # sensor incorrectly preferred this over the bridge, status
            # would be red.
            "organ.a": now - 300,
        },
    )

    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    reading = _run(sensor)

    assert reading.status == "green"
    assert reading.metadata["alive"] == 1
    assert reading.metadata["dead"] == 0


# ---------- W1.1 enrollment tests -------------------------------------------
#
# Every Tier-1 Critical Pro infra organ enrolled in genome.yaml during W1.1
# emits a sidecar at ~/.organism/last_seen/<organ_id>.json with the standard
# schema (ts, status, organ_id, metadata). The aggregator already supports
# this via bridge_source: state_file. The tests here use tmp_path bridge
# files (not the real ~/.organism/) and assert two cases per organ:
#
#   - happy path: sidecar present + ts recent → state alive (aggregate green)
#   - dead path:  sidecar missing            → state dead (aggregate red),
#                 with bridge error surfaced via the aggregator's classification
#                 (BridgeReading.error populated by BridgeStateReader._read_one).
#
# Spec ref: ScratchPad: docs/innervation-2026-04-29/07_innervation_protocol.md §1.1.


def _w1_organ(
    organ_id: str,
    bridge_path: Path,
    expected_hb_seconds: int,
    *,
    severity: str = "warning",
) -> dict:
    """Build a genoma entry mirroring the W1.1 enrollment shape."""
    out = _organ(
        organ_id,
        expected_hb_seconds=expected_hb_seconds,
        bridge_path=bridge_path,
    )
    out["severity_on_silence"] = severity
    return out


def _write_w1_sidecar(path: Path, *, status: str, age_s: float, organ_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ts": time.time() - age_s,
                "status": status,
                "organ_id": organ_id,
                "metadata": {},
            }
        )
    )


def _w1_happy_dead_pair(
    tmp_path: Path,
    organ_id: str,
    expected_hb_seconds: int,
    *,
    severity: str = "warning",
) -> tuple[SensorReading, SensorReading]:
    """Run the aggregator twice for one organ: once happy, once dead."""
    genome = tmp_path / f"{organ_id}_genome.yaml"
    db = tmp_path / f"{organ_id}_last_seen.db"
    bridge = tmp_path / f"{organ_id}.json"

    _write_genome(genome, [_w1_organ(organ_id, bridge, expected_hb_seconds, severity=severity)])

    # Happy: sidecar fresh (age ≪ 1.5x expected)
    _write_w1_sidecar(bridge, status="ok", age_s=max(1.0, expected_hb_seconds * 0.1), organ_id=organ_id)
    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    happy = _run(sensor)

    # Dead: sidecar absent. (Use a fresh sensor instance to be explicit, even
    # though read() reloads I/O each call.)
    bridge.unlink()
    sensor = GenomeAggregatorSensor(genome_path=genome, last_seen_db_path=db)
    dead = _run(sensor)

    return happy, dead


def test_w1_pro_fly_restart_loop_detector_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.fly_restart_loop_detector",
        expected_hb_seconds=1350,
        severity="critical",
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.fly_restart_loop_detector"]


def test_w1_pro_cpu_monitor_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.cpu_monitor",
        expected_hb_seconds=1350,
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.cpu_monitor"]


def test_w1_pro_disk_monitor_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.disk_monitor",
        expected_hb_seconds=1350,
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.disk_monitor"]


def test_w1_pro_zombie_hunter_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.zombie_hunter",
        expected_hb_seconds=90,
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.zombie_hunter"]


def test_w1_pro_dlq_autopilot_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.dlq_autopilot",
        expected_hb_seconds=2700,
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.dlq_autopilot"]


def test_w1_pro_sentinel_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.sentinel",
        expected_hb_seconds=90000,
        severity="critical",
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.sentinel"]


def test_w1_cell_organism_enrolled(tmp_path):
    """cell.organism daemon: recovery_action=human_only but sidecar still
    feeds the aggregator so the Supervisor can see liveness/status without
    being able to act on silence (operator wakes it up by hand)."""
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "cell.organism",
        expected_hb_seconds=90,
        severity="critical",
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["cell.organism"]


def test_w1_pro_metabolic_rollup_enrolled(tmp_path):
    happy, dead = _w1_happy_dead_pair(
        tmp_path,
        "pro.metabolic_rollup",
        expected_hb_seconds=5400,
    )
    assert happy.status == "green"
    assert happy.metadata["alive"] == 1
    assert dead.status == "red"
    assert dead.metadata["dead_organs"] == ["pro.metabolic_rollup"]

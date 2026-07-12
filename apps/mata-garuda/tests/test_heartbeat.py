"""Tests for the mata_garuda heartbeat emitter (Stage 1, 2026-06-29).

The emitter writes the SAME ~/.organism/last_seen sidecar schema the receptor
reads, so a green-but-dead singleton surfaces as unhealthy. Contract:
  - schema parity with the organism convention (ts/status/organ_id/metadata)
  - atomic write (never a half sidecar)
  - best-effort (never raises back to the producer)
  - status_from_stats encodes the green-but-dead signature (read>0, progressed=0)
"""
from __future__ import annotations

import json
import os

from mata_garuda.workers import heartbeat


def test_emit_writes_schema(tmp_path):
    ok = heartbeat.emit_heartbeat(
        "mata_garuda.gap_consumer", "ok", {"read": 10, "resolved": 4}, out_dir=str(tmp_path)
    )
    assert ok is True
    p = tmp_path / "mata_garuda.gap_consumer.json"
    assert p.exists()
    payload = json.loads(p.read_text())
    assert payload["organ_id"] == "mata_garuda.gap_consumer"
    assert payload["status"] == "ok"
    assert payload["metadata"] == {"read": 10, "resolved": 4}
    assert isinstance(payload["ts"], float)


def test_emit_is_atomic_no_tmp_left(tmp_path):
    heartbeat.emit_heartbeat("mata_garuda.x", "ok", out_dir=str(tmp_path))
    leftovers = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
    assert leftovers == [], f"atomic write left a tmp file: {leftovers}"


def test_emit_never_raises_on_bad_dir(tmp_path):
    # point at a path whose parent is a file → mkdir fails → must NOT raise
    afile = tmp_path / "afile"
    afile.write_text("x")
    ok = heartbeat.emit_heartbeat("mata_garuda.y", "ok", out_dir=str(afile / "sub"))
    assert ok is False


def test_emit_honors_env_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    heartbeat.emit_heartbeat("mata_garuda.z", "degraded")
    assert (tmp_path / "mata_garuda.z.json").exists()


def test_status_ok_when_progress(tmp_path):
    assert heartbeat.status_from_stats({"read": 10, "resolved": 8, "errors": 0}) == "ok"


def test_status_degraded_is_green_but_dead(tmp_path):
    """read a backlog but moved nothing → degraded (the gap_consumer 95%-unacked case)."""
    assert heartbeat.status_from_stats(
        {"read": 1149, "resolved": 0, "skipped": 0, "failed": 0, "errors": 0}
    ) == "degraded"


def test_status_ok_when_idle(tmp_path):
    """no items read at all is a healthy idle, not degraded."""
    assert heartbeat.status_from_stats({"read": 0, "resolved": 0, "errors": 0}) == "ok"


def test_status_fail_when_all_errors(tmp_path):
    assert heartbeat.status_from_stats({"read": 5, "errors": 5}) == "fail"


# --- Stage 2 (2026-06-30): run_with_heartbeat wrapper for main()->int workers ---
# The 10 repo-direct mata_garuda crons have `main() -> int` (an exit code), not a
# stats dict. run_with_heartbeat wraps such a callable: it ALWAYS emits a sidecar
# at the end (even on crash), deriving status from the exit code / exception, and
# preserves the original return code / re-raises — the cron's contract is unchanged.


def test_run_with_heartbeat_ok_on_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    rc = heartbeat.run_with_heartbeat("mata_garuda.sentinel_cell", lambda: 0)
    assert rc == 0
    payload = json.loads((tmp_path / "mata_garuda.sentinel_cell.json").read_text())
    assert payload["status"] == "ok"


def test_run_with_heartbeat_fail_on_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    rc = heartbeat.run_with_heartbeat("mata_garuda.sentinel_cell", lambda: 1)
    assert rc == 1
    payload = json.loads((tmp_path / "mata_garuda.sentinel_cell.json").read_text())
    assert payload["status"] == "fail"
    assert payload["metadata"]["exit_code"] == 1


def test_run_with_heartbeat_fail_and_reraise_on_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))

    def boom():
        raise RuntimeError("worker exploded")

    try:
        heartbeat.run_with_heartbeat("mata_garuda.kg_linker", boom)
        raised = False
    except RuntimeError:
        raised = True
    assert raised, "run_with_heartbeat must re-raise — it wraps, it does not swallow"
    payload = json.loads((tmp_path / "mata_garuda.kg_linker.json").read_text())
    assert payload["status"] == "fail"
    assert "worker exploded" in payload["metadata"].get("error", "")


def test_run_with_heartbeat_none_return_is_ok(tmp_path, monkeypatch):
    # a worker whose main() returns None (no explicit exit code) = success
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path))
    rc = heartbeat.run_with_heartbeat("mata_garuda.wr2_bridge", lambda: None)
    assert rc == 0
    payload = json.loads((tmp_path / "mata_garuda.wr2_bridge.json").read_text())
    assert payload["status"] == "ok"

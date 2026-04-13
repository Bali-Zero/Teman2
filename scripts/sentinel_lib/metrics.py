"""Sentinel self-measurement — Pillar 7: Numeri Prima.

Tracks per-run stats: failures, recoveries, auto-heal success rate.
Persisted to ~/.agent/decisions/sentinel_metrics.json.
"""
import json
import time
from pathlib import Path

METRICS_FILE = Path.home() / ".agent" / "decisions" / "sentinel_metrics.json"


def load_metrics() -> dict:
    try:
        return json.loads(METRICS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "runs": 0,
            "total_failures": 0,
            "total_recoveries": 0,
            "auto_heal_attempts": 0,
            "auto_heal_successes": 0,
            "incidents_detected": 0,
            "history": [],
        }


def record_run(
    checked: int,
    failed: int,
    recovered: int,
    auto_heal_ok: int,
    auto_heal_fail: int,
    incidents: int,
) -> None:
    m = load_metrics()
    m["runs"] += 1
    m["total_failures"] += failed
    m["total_recoveries"] += recovered
    m["auto_heal_attempts"] += auto_heal_ok + auto_heal_fail
    m["auto_heal_successes"] += auto_heal_ok
    m["incidents_detected"] += incidents

    # Keep last 100 runs for MTTR calculation
    m["history"].append({
        "ts": time.time(),
        "checked": checked,
        "failed": failed,
        "recovered": recovered,
        "auto_heal_ok": auto_heal_ok,
    })
    m["history"] = m["history"][-100:]

    # Compute rolling stats
    if m["auto_heal_attempts"] > 0:
        m["auto_heal_success_pct"] = round(
            m["auto_heal_successes"] / m["auto_heal_attempts"] * 100, 1
        )
    if m["runs"] > 0:
        m["avg_failures_per_run"] = round(m["total_failures"] / m["runs"], 2)

    tmp = str(METRICS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(m, indent=2))
    Path(tmp).replace(METRICS_FILE)

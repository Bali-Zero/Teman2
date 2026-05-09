#!/usr/bin/env python3
"""sentinel-aggregate.py — single pane of glass for the Innervation Genoma.

Reads the organs_registry.yaml and aggregates per-organ status by combining:
  1. ~/.organism/last_seen/<id>.json (heartbeat written by the organ itself
     or by its wrapper script).
  2. `launchctl list` output for `runtime: pro_launchd` organs (PID + last
     exit code, gives liveness when no last_seen file exists).
  3. `expected_hb_seconds` from the registry to classify silence as
     ok / stale / dead based on age vs threshold.

Output:
  - Writes a JSON snapshot to ~/.organism/aggregate.json (atomic via
    write-then-rename) for dashboard / Telegram consumers.
  - Prints a human-readable summary table to stdout, grouped by severity.

Status classification (per organ):
  ok        last_seen age <= expected_hb_seconds, status field = ok
  stale     expected_hb_seconds < age <= 3 * expected_hb_seconds
  dead      age > 3 * expected_hb_seconds  OR  status field != ok
  unknown   no heartbeat file AND no launchctl entry (or registry-only fly_machine)
  noheartbeat  organ has no bridge_source AND launchctl shows it loaded
               (registry coverage exists but no liveness signal)

Schedule: ~/Library/LaunchAgents/com.nuzantara.sentinel-aggregate.plist
  StartInterval = 300 seconds (5 min).

Exit codes:
  0  successful aggregation
  1  registry parse error
  2  cannot write aggregate.json
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REGISTRY_PATH = Path.home() / "Desktop" / "nuzantara" / "apps" / "organism" / "organism" / "organs_registry.yaml"
LAST_SEEN_DIR = Path.home() / ".organism" / "last_seen"
AGGREGATE_PATH = Path.home() / ".organism" / "aggregate.json"

STALE_MULTIPLIER = 1.0
DEAD_MULTIPLIER = 3.0


def _now_epoch() -> float:
    return time.time()


def _parse_ts(ts: Any) -> float | None:
    """Accept ISO-8601 string OR float epoch seconds. Returns epoch float."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            try:
                return float(ts)
            except ValueError:
                return None
    return None


def _read_last_seen(organ_id: str) -> dict[str, Any] | None:
    path = LAST_SEEN_DIR / f"{organ_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _launchctl_loaded() -> dict[str, dict[str, Any]]:
    """Return {label: {pid, last_exit}} from `launchctl list`."""
    try:
        out = subprocess.check_output(
            ["launchctl", "list"], text=True, timeout=10
        )
    except (subprocess.SubprocessError, OSError):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        pid_str, exit_str, label = parts[0].strip(), parts[1].strip(), parts[2].strip()
        try:
            pid = int(pid_str) if pid_str != "-" else None
        except ValueError:
            pid = None
        try:
            last_exit = int(exit_str)
        except ValueError:
            last_exit = None
        result[label] = {"pid": pid, "last_exit": last_exit}
    return result


def _classify(
    organ: dict[str, Any],
    hb: dict[str, Any] | None,
    launchctl_entry: dict[str, Any] | None,
    now: float,
) -> dict[str, Any]:
    organ_id = organ["id"]
    runtime = organ.get("runtime", "")
    expected_hb = organ.get("expected_hb_seconds", 0)
    severity_on_silence = organ.get("severity_on_silence", "warning")

    # fly_machine: no local launchctl, status comes from health endpoint —
    # out of scope for this aggregator. Mark as remote.
    if runtime == "fly_machine":
        return {
            "id": organ_id,
            "runtime": runtime,
            "status": "remote",
            "age_seconds": None,
            "severity": "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
        }

    # Heartbeat present: compute freshness.
    if hb is not None:
        ts = _parse_ts(hb.get("ts"))
        age = (now - ts) if ts is not None else None
        hb_status = str(hb.get("status", "ok")).lower()

        if age is None:
            status = "unknown"
        elif hb_status not in ("ok", "success", "healthy"):
            status = "dead"
        elif expected_hb > 0 and age > expected_hb * DEAD_MULTIPLIER:
            status = "dead"
        elif expected_hb > 0 and age > expected_hb * STALE_MULTIPLIER:
            status = "stale"
        else:
            status = "ok"

        return {
            "id": organ_id,
            "runtime": runtime,
            "status": status,
            "age_seconds": int(age) if age is not None else None,
            "severity": severity_on_silence if status in ("dead", "stale") else "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "hb_status": hb_status,
        }

    # No heartbeat. Fall back to launchctl liveness.
    if launchctl_entry is not None:
        pid = launchctl_entry.get("pid")
        last_exit = launchctl_entry.get("last_exit")
        # Loaded but no PID = idle (cron between ticks). Acceptable for cron.
        # Loaded with non-zero last_exit = recent failure.
        if last_exit is not None and last_exit != 0:
            return {
                "id": organ_id,
                "runtime": runtime,
                "status": "dead",
                "age_seconds": None,
                "severity": severity_on_silence,
                "owner_module": organ.get("owner_module"),
                "recovery_action": organ.get("recovery_action"),
                "last_exit": last_exit,
            }
        return {
            "id": organ_id,
            "runtime": runtime,
            "status": "noheartbeat",
            "age_seconds": None,
            "severity": "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "pid": pid,
        }

    # Not loaded in launchctl AND no heartbeat = unknown / not running.
    return {
        "id": organ_id,
        "runtime": runtime,
        "status": "unknown",
        "age_seconds": None,
        "severity": severity_on_silence,
        "owner_module": organ.get("owner_module"),
        "recovery_action": organ.get("recovery_action"),
    }


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")
    os.replace(tmp, path)


def _print_summary(rollup: dict[str, list[dict[str, Any]]]) -> None:
    print(
        f"=== Sentinel Aggregate @ {datetime.now(timezone.utc).isoformat(timespec='seconds')} ==="
    )
    for status in ("dead", "stale", "noheartbeat", "unknown", "remote", "ok"):
        items = rollup.get(status, [])
        if not items:
            continue
        print(f"\n[{status.upper()}] {len(items)} organ(s):")
        for item in items:
            age_str = (
                f"age={item['age_seconds']}s" if item.get("age_seconds") is not None else "age=n/a"
            )
            print(f"  - {item['id']:50s} {age_str:20s} severity={item.get('severity')}")


def main() -> int:
    if not REGISTRY_PATH.exists():
        print(f"ERROR: registry not found at {REGISTRY_PATH}", file=sys.stderr)
        return 1

    try:
        registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"ERROR: registry parse failed: {exc}", file=sys.stderr)
        return 1

    organs = registry.get("organs", [])
    if not isinstance(organs, list):
        print("ERROR: registry has no organs list", file=sys.stderr)
        return 1

    launchctl_map = _launchctl_loaded()
    now = _now_epoch()

    results: list[dict[str, Any]] = []
    for organ in organs:
        if not isinstance(organ, dict) or "id" not in organ:
            continue
        organ_id = organ["id"]
        hb = _read_last_seen(organ_id)
        label = (organ.get("recovery_params") or {}).get("label")
        launchctl_entry = launchctl_map.get(label) if label else None
        results.append(_classify(organ, hb, launchctl_entry, now))

    rollup: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        rollup.setdefault(r["status"], []).append(r)

    aggregate = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "registry_organ_count": len(organs),
        "classified_count": len(results),
        "by_status": {k: len(v) for k, v in rollup.items()},
        "organs": results,
    }

    try:
        _atomic_write(AGGREGATE_PATH, aggregate)
    except OSError as exc:
        print(f"ERROR: cannot write aggregate.json: {exc}", file=sys.stderr)
        return 2

    # Heartbeat for self.
    self_hb = LAST_SEEN_DIR / "pro.sentinel_aggregate.json"
    try:
        _atomic_write(
            self_hb,
            {
                "ts": aggregate["ts"],
                "status": "ok",
                "by_status": aggregate["by_status"],
            },
        )
    except OSError:
        pass

    _print_summary(rollup)
    return 0


if __name__ == "__main__":
    sys.exit(main())

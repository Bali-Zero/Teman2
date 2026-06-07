#!/usr/bin/env python3
"""sentinel-aggregate.py — single pane of glass for the Innervation Genoma.

Reads the organs_registry.yaml and aggregates per-organ status by combining:
  1. ~/.organism/last_seen/<id>.json (heartbeat written by the organ itself
     or by its wrapper script).
  2. `launchctl list` output for `runtime: pro_launchd` / `mini_launchd`
     organs (PID + last exit code, gives liveness when no last_seen file
     exists).
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
  noheartbeat  organ declares a state_file bridge_source, launchctl shows it
               loaded, but the state file is missing

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
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REGISTRY_PATH = Path.home() / "Desktop" / "nuzantara" / "apps" / "organism" / "organism" / "organs_registry.yaml"
LAST_SEEN_DIR = Path.home() / ".organism" / "last_seen"
AGGREGATE_PATH = Path.home() / ".organism" / "aggregate.json"
EVENTS_JSONL = Path.home() / ".organism" / "events" / "sentinel.jsonl"
ORGANISM_STREAM_KEY = "organism:events"

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


def _extract_dotted(data: dict[str, Any], path: str) -> Any:
    cur: Any = data
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return None
        cur = cur[seg]
    return cur


def _map_bridge_status(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in {"up", "ok", "healthy", "green", "connected", "operational", "true"}:
        return "ok"
    if v in {"degraded", "partial", "yellow", "warning", "warn", "initializing", "loading"}:
        return "degraded"
    if v in {"down", "fail", "failed", "failure", "red", "false", "unhealthy", "unavailable", "error", "critical"}:
        return "fail"
    return "degraded"


def _read_http_bridge(bridge_source: dict[str, Any]) -> dict[str, Any]:
    url = str(bridge_source.get("path", ""))
    timeout = float(bridge_source.get("http_timeout_s", 5.0))
    now = _now_epoch()
    if not url:
        return {"ts": now, "status": "error", "error": "http bridge path missing"}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nuzantara-sentinel-aggregate/1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = int(getattr(resp, "status", resp.getcode()))
            body = resp.read().decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return {
            "ts": now,
            "status": "error",
            "error": f"http request failed: {type(exc).__name__}: {exc}",
            "source": url,
        }

    if status_code != 200:
        return {
            "ts": now,
            "status": "error",
            "error": f"http {status_code}: body={body[:200]!r}",
            "source": url,
        }

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        return {
            "ts": now,
            "status": "error",
            "error": f"http body json parse error: {exc.msg}",
            "source": url,
        }
    if not isinstance(data, dict):
        return {
            "ts": now,
            "status": "error",
            "error": f"http body must be JSON object, got {type(data).__name__}",
            "source": url,
        }

    ts_field = str(bridge_source.get("timestamp_field", "ts"))
    ts = _parse_ts(data.get(ts_field)) if ts_field in data else now
    if ts is None:
        return {
            "ts": now,
            "status": "error",
            "error": f"could not coerce http timestamp field {ts_field!r}",
            "source": url,
        }

    json_path = str(bridge_source.get("json_path", ""))
    if json_path:
        raw_status = _extract_dotted(data, json_path)
    else:
        raw_status = data.get(str(bridge_source.get("status_field", "status")), "")
    if raw_status is None:
        return {
            "ts": ts,
            "status": "error",
            "error": f"http body missing json_path {json_path!r}",
            "source": url,
        }

    return {
        "ts": ts,
        "status": _map_bridge_status(raw_status),
        "raw_status": raw_status,
        "source": url,
    }


def _read_last_seen(organ_id: str, organ: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Read heartbeat for an organ. Honours bridge_source.path if declared,
    falls back to ~/.organism/last_seen/<organ_id>.json convention."""
    candidates: list[Path] = []
    if organ is not None:
        bs = organ.get("bridge_source") or {}
        if isinstance(bs, dict) and bs.get("type") == "http":
            return _read_http_bridge(bs)
        if isinstance(bs, dict) and bs.get("type") == "state_file":
            raw = bs.get("path")
            if isinstance(raw, str) and raw:
                candidates.append(Path(os.path.expanduser(raw)))
    candidates.append(LAST_SEEN_DIR / f"{organ_id}.json")

    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _parse_launchctl_list(out: str) -> dict[str, dict[str, Any]]:
    """Return {label: {pid, last_exit}} from `launchctl list` text."""
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


def _launchctl_loaded(command: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Return {label: {pid, last_exit}} from local or remote launchctl list."""
    cmd = command or ["launchctl", "list"]
    try:
        out = subprocess.check_output(cmd, text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return {}
    return _parse_launchctl_list(out)


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

    if organ.get("enabled") is False:
        return {
            "id": organ_id,
            "runtime": runtime,
            "status": "disabled",
            "age_seconds": None,
            "severity": "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "disabled_reason": organ.get("disabled_reason", ""),
        }

    # Heartbeat present: compute freshness.
    if hb is not None:
        ts = _parse_ts(hb.get("ts"))
        age = (now - ts) if ts is not None else None
        hb_status = str(hb.get("status", "ok")).lower()

        if age is None:
            status = "unknown"
        else:
            # Apply freshness gate FIRST — a stale "degraded" or stale "fail"
            # is just as serious as a stale "ok" (organ might be dead, last
            # write recorded its dying state). Codex P1a fix.
            stale_age = expected_hb > 0 and age > expected_hb * STALE_MULTIPLIER
            dead_age = expected_hb > 0 and age > expected_hb * DEAD_MULTIPLIER

            if hb_status in ("ok", "success", "healthy", "starting"):
                # "starting" is a transient — fresh starting=ok, stale starting=stuck.
                if dead_age:
                    status = "dead"
                elif stale_age:
                    status = "stale"
                else:
                    status = "ok"
            elif hb_status in ("degraded", "warning"):
                # Degraded is a real-but-acceptable signal IF fresh. A stale
                # degraded is worse: organ may have died right after writing.
                if dead_age:
                    status = "dead"
                elif stale_age:
                    status = "stale"
                else:
                    status = "warning"
            else:
                # fail / error / unknown / anything else: always dead.
                status = "dead"

        if (
            organ.get("type") == "cron"
            and status in ("stale", "dead")
            and hb_status in ("ok", "success", "healthy", "starting", "degraded", "warning")
            and launchctl_entry is not None
            and launchctl_entry.get("pid") is not None
        ):
            status = "ok"

        result = {
            "id": organ_id,
            "runtime": runtime,
            "status": status,
            "age_seconds": int(age) if age is not None else None,
            "severity": severity_on_silence if status in ("dead", "stale") else "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "hb_status": hb_status,
        }
        if launchctl_entry is not None and launchctl_entry.get("pid") is not None:
            result["pid"] = launchctl_entry.get("pid")
            result["last_exit"] = launchctl_entry.get("last_exit")
            result["hb_source"] = "launchctl_running"
        if hb.get("error"):
            result["error"] = hb.get("error")
        if hb.get("source"):
            result["hb_source"] = hb.get("source")
        return result

    # fly_machine without an http bridge reading: no local launchctl fallback.
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

    # No heartbeat. Fall back to launchctl liveness.
    # Convention (2026-05-09 wave 2): launchd-loaded + last_exit==0 is the
    # baseline "alive" signal — a missing last_seen file is NOT a problem
    # by itself. Only mark noheartbeat for organs that DECLARE bridge_source
    # in registry but don't write it (broken contract); the rest get "ok".
    if launchctl_entry is not None:
        pid = launchctl_entry.get("pid")
        last_exit = launchctl_entry.get("last_exit")
        # launchctl keeps the previous exit code even after KeepAlive has
        # restarted a daemon. If a current PID exists, liveness wins over the
        # stale last_exit stamp; otherwise running daemons can be reported as
        # dead forever after one historical boot race.
        bs = organ.get("bridge_source") or {}
        declares_state_file = isinstance(bs, dict) and bs.get("type") == "state_file"
        if declares_state_file:
            return {
                "id": organ_id,
                "runtime": runtime,
                "status": "noheartbeat",
                "age_seconds": None,
                "severity": "warning",
                "owner_module": organ.get("owner_module"),
                "recovery_action": organ.get("recovery_action"),
                "pid": pid,
                "last_exit": last_exit,
            }
        if pid is not None:
            return {
                "id": organ_id,
                "runtime": runtime,
                "status": "ok",
                "age_seconds": None,
                "severity": "info",
                "owner_module": organ.get("owner_module"),
                "recovery_action": organ.get("recovery_action"),
                "pid": pid,
                "last_exit": last_exit,
                "hb_source": "launchctl",
            }
        # Treat SIGTERM (-15) and SIGINT (-2) as graceful — not failure.
        # These happen on normal restart cycles or manual kickstart.
        graceful_signals = {-15, -2}
        if last_exit is not None and last_exit != 0 and last_exit not in graceful_signals:
            # last_exit!=0 on a non-critical organ is often "exit-code drift"
            # (script ran fine but exited 1 — e.g. wr2.image_generator logs
            # "Done: 1/1 drafts imaged" then exits 2). Downgrade to
            # "exit_drift" unless the registry says critical/error severity.
            organ_type = organ.get("type", "")
            severity = organ.get("severity_on_silence", "warning")
            if organ_type in ("cron", "daemon") and severity not in ("critical", "error"):
                return {
                    "id": organ_id,
                    "runtime": runtime,
                    "status": "exit_drift",
                    "age_seconds": None,
                    "severity": "info",
                    "owner_module": organ.get("owner_module"),
                    "recovery_action": organ.get("recovery_action"),
                    "last_exit": last_exit,
                }
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
        # Did the organ declare a state_file bridge_source? If yes, missing
        # file is a broken contract → noheartbeat. http-type bridge_source
        # is not implemented yet (Codex P1c fix): fall through to "ok"
        # rather than spuriously flagging http-source organs as noheartbeat.
        return {
            "id": organ_id,
            "runtime": runtime,
            "status": "ok",
            "age_seconds": None,
            "severity": "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "pid": pid,
            "hb_source": "launchctl",
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


def _emit_organism_event(event: dict[str, Any]) -> None:
    """Emit an Event onto the local organism bus (Redis stream + JSONL mirror).

    JSONL first (durable), Redis second (best-effort). Never raises.
    Mirrors apps/organism/organism/redis_bus.EventBus.emit semantics so
    the Supervisor's existing consumer can pick these up unchanged.
    """
    try:
        EVENTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, separators=(",", ":"), default=str)
        with EVENTS_JSONL.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        return  # never propagate

    # Best-effort Redis XADD via redis-cli (no Python redis dep needed).
    try:
        subprocess.run(
            [
                "redis-cli", "XADD", ORGANISM_STREAM_KEY, "*",
                "data", json.dumps(event, separators=(",", ":"), default=str),
            ],
            capture_output=True, timeout=2, check=False,
        )
    except Exception:
        pass


def _emit_dead_organs_to_supervisor(results: list[dict[str, Any]]) -> int:
    """For every organ classified as dead with critical/error severity,
    emit a heartbeat_silent Event onto the organism bus. Returns count
    of events emitted. Wave-5 closes Layer 3 (sentinel→supervisor)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    emitted = 0
    for o in results:
        if o.get("status") != "dead":
            continue
        sev = (o.get("severity") or "warning").lower()
        # Only escalate the ones the registry wants escalated.
        if sev not in ("critical", "error"):
            continue
        organ_id = o.get("id", "")
        if not organ_id:
            continue
        event = {
            "ts": now,
            "severity": sev,
            "source": "sentinel.aggregate",
            "kind": "heartbeat_silent",
            "payload": {
                "organ_id": organ_id,
                "age_seconds": o.get("age_seconds"),
                "hb_status": o.get("hb_status"),
                "last_exit": o.get("last_exit"),
                "recovery_action": o.get("recovery_action"),
                "owner_module": o.get("owner_module"),
            },
            "correlation_id": f"sentinel-{organ_id}-{now}",
            "is_actuation": False,
            "host": "Pro",
        }
        _emit_organism_event(event)
        emitted += 1
    return emitted


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")
    os.replace(tmp, path)


def _print_summary(rollup: dict[str, list[dict[str, Any]]]) -> None:
    print(
        f"=== Sentinel Aggregate @ {datetime.now(timezone.utc).isoformat(timespec='seconds')} ==="
    )
    for status in ("dead", "stale", "warning", "exit_drift", "noheartbeat", "unknown", "disabled", "remote", "ok"):
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

    pro_launchctl_map = _launchctl_loaded()
    mini_launchctl_map = _launchctl_loaded([
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=3",
        "mini",
        "launchctl",
        "list",
    ])
    now = _now_epoch()

    results: list[dict[str, Any]] = []
    for organ in organs:
        if not isinstance(organ, dict) or "id" not in organ:
            continue
        organ_id = organ["id"]
        hb = _read_last_seen(organ_id, organ)
        label = (organ.get("recovery_params") or {}).get("label")
        if organ.get("runtime") == "mini_launchd":
            launchctl_map = mini_launchctl_map
        else:
            launchctl_map = pro_launchctl_map
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

    # Wave-5: emit heartbeat_silent events for dead+critical/error organs
    # so the Supervisor (organism:events stream consumer) can drive recovery.
    emitted = _emit_dead_organs_to_supervisor(results)
    if emitted:
        print(f"[organism-bus] emitted {emitted} heartbeat_silent event(s)")

    _print_summary(rollup)
    return 0


if __name__ == "__main__":
    sys.exit(main())

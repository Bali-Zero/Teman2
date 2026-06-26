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

import hashlib
import json
import math
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
EVENTS_JSONL = Path.home() / ".organism" / "events" / "sentinel.jsonl"
ORGANISM_STREAM_KEY = "organism:events"

STALE_MULTIPLIER = 1.0
DEAD_MULTIPLIER = 3.0

# A2 — Heartbeat Semantico (self-loop Anello 2). The classic axes (timestamp, status
# string, launchctl PID) answer "did the organ RUN?". A2 adds the missing axis: "did the
# organ's OUTPUT advance?" — green-but-no-delta = starved (superscar #2 "Esiste != Armato"
# at the output level). An organ is STARVED when its ts is fresh and its status is ok, but
# a registry-declared progress field is byte-identical across the last N ticks.
# HOW from the study (effective-harnesses-for-long-running-agents + StuckLoopDetection):
# the validated default for "unchanged across N ticks" is N≈3.
STARVED_TICKS = 3  # consecutive no-delta ticks before flagging starved (frequency-blind floor)

# A2 frequency-aware threshold (Opzione A, 2026-06-27 census fix). The bare STARVED_TICKS
# counts SENTINEL ticks (this aggregator runs every SENTINEL_INTERVAL_SECONDS), NOT the
# organ's own work-occasions. For a daemon (hb 60-300s) 3 ticks ≈ 15 min = many occasions —
# fine. For a weekly cron (hb ≈ 8 days) 3 ticks = 15 min → it would be flagged 'starved' 15
# minutes after a run while legitimately idle until the NEXT run a week later: a structural
# false positive (census 2026-06-27 found 7/8 candidate loops in this trap). The cure: an
# organ MAY declare `starved_after_periods: N` and, with a known expected_hb_seconds, the
# tick-threshold becomes N work-periods expressed in sentinel ticks. Never drops BELOW the
# frequency-blind floor (so high-frequency daemons keep the validated N≈3). Opt-in: organs
# that don't declare it are classified exactly as before.
SENTINEL_INTERVAL_SECONDS = 300  # this aggregator's StartInterval (see module docstring)
DEFAULT_STARVED_AFTER_PERIODS = 2  # missed work-occasions before starved, when declared


def _starved_threshold_ticks(organ: dict[str, Any]) -> int:
    """How many consecutive no-delta sentinel ticks before this organ is 'starved'.

    Default = STARVED_TICKS (frequency-blind floor, unchanged behaviour). If the organ
    declares `starved_after_periods: N` AND has a positive expected_hb_seconds, translate
    N work-periods into sentinel ticks: ceil(N * expected_hb / SENTINEL_INTERVAL). The
    result is floored at STARVED_TICKS so the cure can only ever RAISE the bar for slow
    crons, never lower it for fast daemons. Fail-safe: any bad/missing value → the floor."""
    floor = STARVED_TICKS
    n = organ.get("starved_after_periods")
    if n is None:
        return floor
    try:
        periods = float(n)
    except (TypeError, ValueError):
        return floor
    if periods <= 0:
        return floor
    expected_hb = organ.get("expected_hb_seconds") or 0
    try:
        expected_hb = float(expected_hb)
    except (TypeError, ValueError):
        return floor
    if expected_hb <= 0:
        return floor  # no period to scale against → frequency-blind floor
    ticks = math.ceil(periods * expected_hb / SENTINEL_INTERVAL_SECONDS)
    return max(floor, int(ticks))


def _read_prior_snapshot() -> dict[str, dict[str, Any]]:
    """A2: read the PREVIOUS aggregate.json so we can compute a per-organ output-delta.
    Was structurally impossible before — the file was write-only. Returns {organ_id: prior
    result dict}, empty on first run / unreadable (fail-open: no prior = never starved)."""
    try:
        prev = json.loads(AGGREGATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for r in (prev.get("organs") or []):
        if isinstance(r, dict) and r.get("id"):
            out[r["id"]] = r
    return out


def _progress_value(hb: dict[str, Any] | None, organ: dict[str, Any]) -> Any:
    """A2: the organ's OUTPUT-progress signal — what must ADVANCE for the organ to be alive,
    not merely fresh. Two declaration modes (registry-driven, both OPT-IN, additive #9):

      1. progress_field — read a value off the already-loaded heartbeat dict. Use when the
         organ ALREADY emits a monotone counter in its payload (no writer-change needed).

      2. output_artifact — a filesystem path the organ PRODUCES. We return a [size, sha256]
         pair: "did output advance?" becomes "did the artifact's CONTENT change?". This needs
         ZERO writer-change to any H24 organ — A2 observes the artifact, not the heartbeat.

         CRITICAL (anti-false-alarm, the trap this design corrects): we hash CONTENT, NOT
         mtime. Many writers REWRITE the file every run unconditionally even when nothing
         changed (e.g. run_intel_pipeline.py re-serialises published_articles.json on a
         zero-article night) — mtime would advance every tick and the organ could NEVER be
         flagged starved (the "green != working" disease applied to the detector itself).
         A content hash is identical across an unchanged rewrite, so a frozen output is seen
         as frozen regardless of how often the writer touches the file. The remaining
         contract: declare output_artifact only when the CONTENT is meant to grow/change on
         real work (a content-rotated dated filename or an in-place per-run shuffle would
         still misfire — those organs have no honest content-progress signal).

    Returns None when neither is declared / the artifact is missing → organ opts out of A2,
    classified the classic way. NEVER raises (a read failure = opt-out, not a crash)."""
    field = organ.get("progress_field")
    if field and hb is not None:
        return hb.get(field)
    artifact = organ.get("output_artifact")
    if artifact:
        try:
            data = Path(os.path.expanduser(str(artifact))).read_bytes()
        except OSError:
            return None  # missing/unreadable artifact → opt out, not a false starve
        # [size, sha256]: content-based, immune to unconditional re-stamps (mtime would not
        # be). JSON-serialisable list → survives the aggregate.json round-trip so the
        # prior-snapshot equality check in _classify holds byte-identically across ticks.
        return [len(data), hashlib.sha256(data).hexdigest()]
    return None


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


def _read_last_seen(organ_id: str, organ: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Read heartbeat for an organ. Honours bridge_source.path if declared,
    falls back to ~/.organism/last_seen/<organ_id>.json convention."""
    candidates: list[Path] = []
    if organ is not None:
        bs = organ.get("bridge_source") or {}
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


def _apply_starved_axis(
    result: dict[str, Any],
    organ: dict[str, Any],
    hb: dict[str, Any] | None,
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    """A2 Heartbeat Semantico, branch-independent. Given a result dict that the
    classifier has already scored as 'ok', downgrade it to 'starved' iff the organ
    declares a progress signal (progress_field / output_artifact) whose value is
    byte-identical to the prior snapshot across STARVED_TICKS consecutive ticks.

    Extracted so EVERY 'ok' path can apply it — not only the heartbeat branch. An
    organ with NO last_seen heartbeat (hb=None) lands in the launchctl-liveness
    branch; before this helper that branch returned 'ok' WITHOUT ever computing the
    output-delta, so a declared output_artifact was silently ignored (the
    green!=working trap applied to A2 itself: wr2.fact_extractor armed but
    progress_value=None on the live Pro run, 2026-06-23).

    Mutates `result` in place (adds progress_value/starved_streak, may flip status)
    and returns it. Fail-open: only ever downgrades ok->starved, never raises."""
    if result.get("status") != "ok":
        return result
    prog = _progress_value(hb, organ)
    if prog is None:
        return result  # organ opts out of A2 → classic ok, untouched
    prior_prog = (prior or {}).get("progress_value") if prior else None
    prior_streak = int((prior or {}).get("starved_streak") or 0) if prior else 0
    if prior is not None and "progress_value" in (prior or {}) and prog == prior_prog:
        starved_streak = prior_streak + 1
    else:
        starved_streak = 0  # output advanced (or first observation) → not starved
    result["progress_value"] = prog
    result["starved_streak"] = starved_streak
    if starved_streak >= _starved_threshold_ticks(organ):
        result["status"] = "starved"
        # raise visibility: a starved organ must not stay 'info'
        if result.get("severity") in (None, "info"):
            result["severity"] = organ.get("severity_on_silence", "warning")
    return result


def _classify(
    organ: dict[str, Any],
    hb: dict[str, Any] | None,
    launchctl_entry: dict[str, Any] | None,
    now: float,
    prior: dict[str, Any] | None = None,
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

        # A2 Heartbeat Semantico: a FRESH + OK organ can still be STARVED — running on
        # schedule but its output never advances (green != working at the output level).
        # Only downgrade ok→starved (never override a real stale/dead/warning); compute the
        # delta against the prior snapshot's recorded progress_value over STARVED_TICKS.
        prog = _progress_value(hb, organ)
        starved_streak = 0
        if status == "ok" and prog is not None:
            prior_prog = (prior or {}).get("progress_value") if prior else None
            prior_streak = int((prior or {}).get("starved_streak") or 0) if prior else 0
            if prior is not None and "progress_value" in (prior or {}) and prog == prior_prog:
                starved_streak = prior_streak + 1
            else:
                starved_streak = 0  # output advanced (or first observation) → not starved
            if starved_streak >= _starved_threshold_ticks(organ):
                status = "starved"

        result = {
            "id": organ_id,
            "runtime": runtime,
            "status": status,
            "age_seconds": int(age) if age is not None else None,
            "severity": (severity_on_silence if status in ("dead", "stale", "starved")
                        else "info"),
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "hb_status": hb_status,
        }
        if prog is not None:
            result["progress_value"] = prog
            result["starved_streak"] = starved_streak
        if launchctl_entry is not None and launchctl_entry.get("pid") is not None:
            result["pid"] = launchctl_entry.get("pid")
            result["last_exit"] = launchctl_entry.get("last_exit")
            result["hb_source"] = "launchctl_running"
        return result

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
            # A2: a launchctl-ok organ with NO heartbeat can still be starved at the
            # output level — apply the starved axis here too (was heartbeat-only before).
            return _apply_starved_axis({
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
            }, organ, hb, prior)
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
        # A2: apply the starved axis here too (heartbeatless + no-pid-but-loaded).
        return _apply_starved_axis({
            "id": organ_id,
            "runtime": runtime,
            "status": "ok",
            "age_seconds": None,
            "severity": "info",
            "owner_module": organ.get("owner_module"),
            "recovery_action": organ.get("recovery_action"),
            "pid": pid,
            "hb_source": "launchctl",
        }, organ, hb, prior)

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
    for status in ("dead", "starved", "stale", "warning", "exit_drift", "noheartbeat", "unknown", "disabled", "remote", "ok"):
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

    # A2 Heartbeat Semantico: read the PRIOR aggregate before we overwrite it,
    # so _classify can compare each organ's progress_value across ticks and
    # detect a "starved" organ (fresh ts, ok status, but frozen output).
    prior_snapshot = _read_prior_snapshot()

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
        results.append(
            _classify(organ, hb, launchctl_entry, now, prior_snapshot.get(organ_id))
        )

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

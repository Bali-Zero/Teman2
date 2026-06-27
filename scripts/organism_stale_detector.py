#!/usr/bin/env python3
"""organism_stale_detector — the heartbeat-channel watcher (the RECEPTOR).

Born 2026-06-28 to end a 28-day blindness: five CORE organs (pro.sentinel,
pro.dlq_autopilot, cell.observatory, infra.pg_organism_bridge_watchdog,
pro.federation_alert_dispatcher) ran green (launchd exit 0) while their
heartbeat sidecar (~/.organism/last_seen/<organ>.json) froze for 18-28 days.
Nobody noticed because the bridge-watchdog that should have alarmed was itself
NOT LOADED, and no SessionStart hook read any alert channel.

This module answers ONE question honestly: which organs have stopped breathing?
It does NOT act (restart is the wrong cure for a dead heartbeat channel — that
lesson is why W2 was disarmed). It emits findings to ~/.organism/alerts/open.jsonl
which the SessionStart hook injects into every session's context.

green (launchd exit 0) != working (heartbeat written). This reads the breath,
not the pulse. (cicatrix-superscar #2)

CLI:
    python3 scripts/organism_stale_detector.py            # human report
    python3 scripts/organism_stale_detector.py --emit     # write alerts file
    python3 scripts/organism_stale_detector.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

# Organs whose absence is itself an alarm (the breath channel must exist).
# Kept deliberately small: only the organism's own core guardians, because a
# MISSING sidecar for a leaf organ is noise, but for a guardian it is the W2 bug.
CORE_ORGANS_EXPECTED: tuple[str, ...] = (
    "pro.sentinel",
    "pro.dlq_autopilot",
    "infra.pg_organism_bridge_watchdog",
    "pro.federation_alert_dispatcher",
    "cell.observatory",
)

DEFAULT_SIDECAR_DIR = os.path.expanduser("~/.organism/last_seen")
DEFAULT_ALERTS_FILE = os.path.expanduser("~/.organism/alerts/open.jsonl")
DEFAULT_STALE_DAYS = 7


@dataclass
class StaleFinding:
    organ_id: str
    kind: str  # "stale" | "dead_channel" | "corrupt"
    age_days: float = field(default=-1.0)
    status: str = field(default="?")
    detail: str = field(default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "organ_id": self.organ_id,
            "kind": self.kind,
            "age_days": round(self.age_days, 1),
            "status": self.status,
            "detail": self.detail,
        }


def _parse_ts(raw: Any, fallback_mtime: float) -> float:
    """Parse both sidecar schemas (superscar #9 tolerance).

    A) float epoch  (~/scripts/_organism_lib.sh)
    B) ISO8601 'Z'  (scripts/lib/heartbeat.sh)
    Fall back to file mtime if the field is absent but the file parsed.
    """
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str) and raw:
        try:
            from datetime import datetime, timezone

            s = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            pass
    return fallback_mtime


def scan_sidecars(
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
    stale_days: float = DEFAULT_STALE_DAYS,
    now: float | None = None,
    expect_core: tuple[str, ...] | None = None,
) -> list[StaleFinding]:
    """Return findings for organs whose heartbeat is stale, missing, or corrupt.

    Pure: takes a directory, returns a list. No side effects (so it is testable
    and the CLI decides whether to emit). now is injectable for determinism.

    expect_core lists organs whose ABSENT sidecar is itself an alarm. It defaults
    to CORE_ORGANS_EXPECTED only when scanning the real organism dir; tests pass
    () so an isolated tmp dir does not spuriously flag the production core organs.
    """
    if expect_core is None:
        expect_core = (
            CORE_ORGANS_EXPECTED
            if os.path.abspath(sidecar_dir) == os.path.abspath(DEFAULT_SIDECAR_DIR)
            else ()
        )
    now = time.time() if now is None else now
    findings: list[StaleFinding] = []

    if not os.path.isdir(sidecar_dir):
        return findings

    seen: set[str] = set()
    for fname in sorted(os.listdir(sidecar_dir)):
        if not fname.endswith(".json"):
            continue
        organ_id = fname[: -len(".json")]
        seen.add(organ_id)
        path = os.path.join(sidecar_dir, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="corrupt",
                    detail=f"unparseable sidecar: {type(exc).__name__}",
                )
            )
            continue

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = now
        ts = _parse_ts(
            payload.get("ts") or payload.get("timestamp"), fallback_mtime=mtime
        )
        age_days = (now - ts) / 86400.0
        if age_days > stale_days:
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="stale",
                    age_days=age_days,
                    status=str(payload.get("status", "?")),
                    detail=f"heartbeat frozen {age_days:.1f}d (threshold {stale_days}d)",
                )
            )

    # A core guardian with NO sidecar at all is the worst case (W2 root): flag it.
    for organ_id in expect_core:
        if organ_id not in seen:
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="dead_channel",
                    detail="expected core organ has NO heartbeat sidecar",
                )
            )

    return findings


def emit_alerts(findings: list[StaleFinding], alerts_file: str = DEFAULT_ALERTS_FILE) -> str:
    """Overwrite the open-alerts file with current findings (idempotent snapshot).

    The file is a SNAPSHOT of currently-open alerts, not an append log — so a
    cured organ disappears from it on the next run (no stale-alert graveyard,
    the exact failure mode that killed claude_tasks).
    """
    os.makedirs(os.path.dirname(alerts_file), exist_ok=True)
    tmp = f"{alerts_file}.tmp.{os.getpid()}"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(tmp, "w", encoding="utf-8") as fh:
        for f in findings:
            rec = f.to_dict()
            rec["detected_at"] = stamp
            fh.write(json.dumps(rec) + "\n")
    os.replace(tmp, alerts_file)
    return alerts_file


def _human_report(findings: list[StaleFinding]) -> str:
    if not findings:
        return "✅ organism heartbeat: all organs breathing (no stale/dead channels)"
    lines = [f"⚠️ ORGANISM: {len(findings)} organ(s) not breathing:"]
    for f in sorted(findings, key=lambda x: x.age_days, reverse=True):
        if f.kind == "dead_channel":
            lines.append(f"  💀 {f.organ_id}: NO heartbeat sidecar (core guardian)")
        elif f.kind == "corrupt":
            lines.append(f"  ❓ {f.organ_id}: corrupt sidecar — {f.detail}")
        else:
            lines.append(
                f"  🫥 {f.organ_id}: stale {f.age_days:.1f}d (status={f.status})"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DEFAULT_SIDECAR_DIR)
    ap.add_argument("--stale-days", type=float, default=DEFAULT_STALE_DAYS)
    ap.add_argument("--emit", action="store_true", help="write alerts file")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    findings = scan_sidecars(args.dir, stale_days=args.stale_days)

    if args.emit:
        path = emit_alerts(findings)
        if not args.json:
            print(f"alerts written: {path} ({len(findings)} open)")

    if args.json:
        print(json.dumps([f.to_dict() for f in findings]))
    elif not args.emit:
        print(_human_report(findings))

    # exit 1 if any core guardian has a dead channel — that is actionable now.
    return 1 if any(f.kind == "dead_channel" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())

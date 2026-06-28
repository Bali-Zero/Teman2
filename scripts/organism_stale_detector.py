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

# Statuses that mean "the organ is breathing but reporting trouble".
UNHEALTHY_STATUSES: frozenset[str] = frozenset({"failed", "fail", "degraded", "error"})

# Organs whose status=failed/degraded is a KNOWN false-positive — do NOT surface
# them (would cause alert-fatigue = the next blindness). Established by the
# 2026-06-28 triage of all 14 fresh-but-failed organs. Each entry is here because
# the failure is benign, with the documented reason:
#   - codex.spark_*        : intentionally disabled by the W81 firebreak (runaway loop)
#   - wr2.telegram_gate    : decommissioned 2026-06-11 (.removed-*), genome not pruned
#   - wr2.carousel_dispatcher: decommissioned 2026-06-11 (.removed-*), genome not pruned
#   - wr3.reflexion_weekly : launchctl-disabled on purpose (the dead twin of wr2's)
#   - pro.agent_library_evolver_* : intentionally disabled (deploy-drift quarantine)
#   - pro.audit_launchd_daily : exit 1 BY DESIGN = "N unhealthy jobs found" (a true report)
#   - infra.ollama_pro : launchd job exits 1 because the real `ollama serve` already
#       owns :11434 (port collision, two program paths) — the daemon is ALIVE and serving
#       (6 models on :11434). The bridge reads the launchd exit code, not the live socket.
#       (Live triage 2026-06-28. NOTE: pro.curiosity_weekly was triaged the same day as a
#       REAL failure — W84 TCC-dead on ~/Desktop — and is deliberately NOT suppressed here:
#       it must stay visible as an operator-boundary finding, not be hidden.)
# The bridge tags all of these "failed" because it has no `disabled`/`expected_exit`
# concept (HEALTHY_EXIT_CODES={0}). Curing the bridge is a separate hot-zone PR;
# this allow-list is the safe downstream filter. Audit this list when an organ is
# re-enabled — a re-enabled organ that genuinely fails must NOT stay suppressed.
KNOWN_BENIGN_FAILED: frozenset[str] = frozenset({
    "codex.spark_loop",
    "codex.spark_harvester",
    "codex.spark_alarm",
    "wr2.telegram_gate",
    "wr2.carousel_dispatcher",
    "wr3.reflexion_weekly",
    "pro.agent_library_evolver_daily",
    "pro.agent_library_evolver_weekly",
    "pro.audit_launchd_daily",
    "infra.ollama_pro",
})


@dataclass
class StaleFinding:
    organ_id: str
    kind: str  # "stale" | "dead_channel" | "corrupt" | "unhealthy"
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


def scan_sidecars_status(
    sidecar_dir: str = DEFAULT_SIDECAR_DIR,
    stale_days: float = DEFAULT_STALE_DAYS,
    now: float | None = None,
    benign: frozenset[str] = KNOWN_BENIGN_FAILED,
    expect_core: tuple[str, ...] | None = None,
) -> list[StaleFinding]:
    """Full receptor scan: stale/dead/corrupt (via scan_sidecars) PLUS unhealthy.

    An "unhealthy" finding is a FRESH organ (it IS breathing) whose status is in
    UNHEALTHY_STATUSES and which is NOT in the benign allow-list. Stale dominates:
    a stale organ is reported once as stale, never also as unhealthy (the frozen
    channel is the headline, not its last-reported status).

    This is the status-aware extension (2026-06-28): the prior receptor saw the
    mute organs but ignored the ones crying for help.
    """
    now = time.time() if now is None else now
    findings = scan_sidecars(
        sidecar_dir, stale_days=stale_days, now=now, expect_core=expect_core
    )
    already = {f.organ_id for f in findings}  # don't double-count stale/corrupt

    if not os.path.isdir(sidecar_dir):
        return findings

    for fname in sorted(os.listdir(sidecar_dir)):
        if not fname.endswith(".json"):
            continue
        organ_id = fname[: -len(".json")]
        if organ_id in already or organ_id in benign:
            continue
        path = os.path.join(sidecar_dir, fname)
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue  # corrupt already handled by scan_sidecars
        status = str(payload.get("status", "")).lower()
        if status in UNHEALTHY_STATUSES:
            note = ""
            md = payload.get("metadata") or {}
            if isinstance(md, dict):
                note = str(md.get("note") or md.get("last_error") or "")
            findings.append(
                StaleFinding(
                    organ_id=organ_id,
                    kind="unhealthy",
                    age_days=0.0,
                    status=status,
                    detail=f"breathing but status={status}"
                    + (f" — {note[:120]}" if note else ""),
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
        return "✅ organism heartbeat: all organs breathing + healthy (no findings)"
    not_breathing = [f for f in findings if f.kind != "unhealthy"]
    unhealthy = [f for f in findings if f.kind == "unhealthy"]
    lines = [f"⚠️ ORGANISM: {len(findings)} organ finding(s):"]
    if not_breathing:
        lines.append(f"  — not breathing ({len(not_breathing)}):")
        for f in sorted(not_breathing, key=lambda x: x.age_days, reverse=True):
            if f.kind == "dead_channel":
                lines.append(f"    💀 {f.organ_id}: NO heartbeat sidecar (core guardian)")
            elif f.kind == "corrupt":
                lines.append(f"    ❓ {f.organ_id}: corrupt sidecar — {f.detail}")
            else:
                lines.append(
                    f"    🫥 {f.organ_id}: stale {f.age_days:.1f}d (status={f.status})"
                )
    if unhealthy:
        lines.append(f"  — breathing but unhealthy ({len(unhealthy)}):")
        for f in sorted(unhealthy, key=lambda x: x.organ_id):
            lines.append(f"    🤒 {f.organ_id}: {f.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=DEFAULT_SIDECAR_DIR)
    ap.add_argument("--stale-days", type=float, default=DEFAULT_STALE_DAYS)
    ap.add_argument("--emit", action="store_true", help="write alerts file")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    findings = scan_sidecars_status(args.dir, stale_days=args.stale_days)

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

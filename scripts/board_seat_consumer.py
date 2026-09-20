#!/usr/bin/env python3
"""board_seat_consumer.py — drains the rows tg_notify routed to the seat lane.

PR #6973 gave the gateway a fourth tier: a p0 whose dedup-key is not an
OWNER_FAMILY stops reaching Telegram and lands on the escalation board as
``type=gateway_routed, cure_lane.owner=seat, priority=NORMAL``. Measured on Pro
over the 30 days to 2026-09-21: 286 of 314 p0 take that path. NOTHING drained
them — so until this file, #6973 had moved the noise from Telegram to the board
rather than removed it, and the board is read by every session at SessionStart.

What it will NOT do, decided from the measured distribution and not from taste:

  - It does not kickstart on a whim. `organs_registry.yaml` declares a
    `recovery_action` for 170 organs (109 of them `launchctl_kickstart`) and no
    loop has ever executed one; every healer tick that met a `dead` organ
    root-caused it and refused the restart, correctly — `iqoo_radar_relay` was
    failing on `Permission denied (publickey)` and a kickstart reproduces the
    identical outcome. A restart that does not cure is a green run that fixed
    nothing (superscar #2).
  - It does not close a row it cannot PROVE is over. Every cure below re-probes
    the condition live in this run. The alert text is evidence of what was true
    when it was written, never of what is true now (superscar #6).
  - It never touches a row belonging to another machine. The board is one
    git-tracked file shared by three checkouts; curing Pro's pidfile from Mini
    is superscar #10 with extra steps.

Cures are matched on the dedup-key's ENTITY — the family before the first ':',
compared by equality against CURES — never by substring (superscar #3).

    cron-fail:<job>     the cron has ALREADY recovered: its own run-state file
                        (~/.agent/decisions/state/<job>.last.json, written by
                        the cron runner) says status=ok with a ts newer than the
                        alert. No action is taken; the row is stale, and saying
                        so is the cure. 65 of the 124 cron-fail alerts on Pro
                        read that way at the time of writing.
    healer-*:stale-lock the healer's pidfile survived its run and its pid was
                        recycled: every 4h tick since has skipped and reported
                        itself GREEN. The alert text already names the cure
                        (`rm -f /tmp/nuzantara-healer.pid`) and Zero has run it
                        by hand 13 times in 30 days. Removed here ONLY after
                        this process confirms no live healer holds that pid.

A family with no cure is left pending and COUNTED. That count is the honest
measure of what still needs a session, and it must never be closed to make a
number look better.

Exit 0 always (fail-open: a launchd organ that crashes stops draining and
nobody notices). Kill switch: BOARD_SEAT_CONSUMER_ENABLED=false.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sentinel_lib.escalations import (  # noqa: E402
    mark_resolved,
    read_all_escalations,
    ts_epoch,
)

ROUTED_TYPE = "gateway_routed"
SEAT_OWNER = "seat"
DEFAULT_MAX = 20

RESOLVED = "resolved"
NOT_CURABLE = "not_curable"
FOREIGN = "foreign_machine"


def _enabled() -> bool:
    return os.environ.get("BOARD_SEAT_CONSUMER_ENABLED", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _state_dir() -> Path:
    return Path(
        os.environ.get("BOARD_CONSUMER_STATE_DIR", str(Path.home() / ".agent" / "decisions" / "state"))
    )


def _healer_pidfile() -> Path:
    return Path(os.environ.get("BOARD_CONSUMER_HEALER_PIDFILE", "/tmp/nuzantara-healer.pid"))


def _this_machine() -> str:
    return os.environ.get("BOARD_CONSUMER_MACHINE", socket.gethostname())


# ------------------------------------------------------------------ cures
def cure_cron_fail(row: dict) -> tuple[str, str]:
    """A cron-fail row is over when the job's own next run said ok.

    The run-state file is written by the cron runner itself, not by the alert
    path, so it is an INDEPENDENT witness — which is the whole reason it is
    trusted here and the alert text is not.
    """
    job = str(row.get("job", ""))
    name = job.split(":", 1)[1] if ":" in job else ""
    if not name:
        return NOT_CURABLE, "dedup-key carries no job name"
    path = _state_dir() / f"{name}.last.json"
    if not path.is_file():
        return NOT_CURABLE, f"no run-state file for {name} (job is invisible to this probe)"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return NOT_CURABLE, f"run-state unreadable: {exc}"
    status = str(state.get("status", "?"))
    state_ts = ts_epoch(state.get("ts"))
    row_ts = ts_epoch(row.get("ts"))
    if status == "ok" and state_ts > row_ts:
        return RESOLVED, (
            f"{name}.last.json status=ok ts={state_ts:.0f} > alert ts={row_ts:.0f} "
            f"(exit_code={state.get('exit_code')})"
        )
    return NOT_CURABLE, f"{name}.last.json status={status} ts={state_ts:.0f} vs alert ts={row_ts:.0f}"


def _pid_is_a_live_healer(pid: int) -> bool | None:
    """True/False, or None when this process cannot tell — and None never cures.

    A pidfile whose pid is ALIVE is not automatically a live healer: the alert
    that produces these rows says so in its own words ("il pid e stato
    RICICLATO"). Removing the pidfile of a genuinely running healer would let a
    second 4h session start beside it, so the ambiguous case refuses.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive and not ours — do not touch it
    except OSError:
        return None
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return "healer" in out.stdout


def cure_healer_stale_lock(row: dict, dry_run: bool) -> tuple[str, str]:
    job = str(row.get("job", ""))
    if not job.endswith(":stale-lock"):
        return NOT_CURABLE, "healer row that is not the stale-lock condition"
    pidfile = _healer_pidfile()
    if not pidfile.exists():
        return RESOLVED, f"{pidfile} is already gone — the lock condition is over"
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        return NOT_CURABLE, f"pidfile unreadable, refusing to remove it blind: {exc}"
    live = _pid_is_a_live_healer(pid)
    if live is None:
        return NOT_CURABLE, f"cannot tell whether pid {pid} is a healer — refusing"
    if live:
        return NOT_CURABLE, f"pid {pid} IS a live healer — the lock is legitimate"
    if dry_run:
        return RESOLVED, f"would remove {pidfile} (pid {pid} is not a healer) [dry-run]"
    try:
        pidfile.unlink()
    except OSError as exc:
        return NOT_CURABLE, f"could not remove {pidfile}: {exc}"
    if pidfile.exists():
        return NOT_CURABLE, f"{pidfile} survived its own removal"
    return RESOLVED, f"removed {pidfile} holding recycled pid {pid}; next healer tick can start"


CURES = {
    "cron-fail": lambda row, dry: cure_cron_fail(row),
    "healer-pro": cure_healer_stale_lock,
    "healer-mini": cure_healer_stale_lock,
}


# ------------------------------------------------------------------ board
def open_seat_rows() -> list[dict]:
    """Net-pending gateway_routed rows owned by the seat lane, oldest first.

    The board is append-only: mark_resolved appends a NEW row rather than
    rewriting the pending one, so a per-line status filter reports a healed job
    open forever. Collapse to the newest record per job first — the same shape
    sentinel_lib.is_job_open and the SessionStart receptor already use.
    """
    latest: dict[str, dict] = {}
    for row in read_all_escalations(include_resolved=True):
        job = row.get("job")
        if not job:
            continue
        known = latest.get(job)
        if known is None or ts_epoch(row.get("ts")) > ts_epoch(known.get("ts")):
            latest[job] = row
    rows = [
        r for r in latest.values()
        if r.get("type") == ROUTED_TYPE
        and r.get("status") != RESOLVED
        and isinstance(r.get("cure_lane"), dict)
        and r["cure_lane"].get("owner") == SEAT_OWNER
    ]
    return sorted(rows, key=lambda r: ts_epoch(r.get("ts")))


def consume(max_rows: int, dry_run: bool) -> dict:
    machine = _this_machine()
    report = {"machine": machine, "dry_run": dry_run, "seen": 0, "resolved": [], "left": []}
    rows = open_seat_rows()
    report["seen"] = len(rows)
    for row in rows[:max_rows]:
        job = str(row.get("job", ""))
        family = job.split(":", 1)[0]
        if row.get("machine") != machine:
            report["left"].append({"job": job, "why": FOREIGN, "detail": str(row.get("machine"))})
            continue
        cure = CURES.get(family)
        if cure is None:
            report["left"].append({"job": job, "why": NOT_CURABLE, "detail": f"no cure registered for family {family!r}"})
            continue
        verdict, proof = cure(row, dry_run)
        if verdict != RESOLVED:
            report["left"].append({"job": job, "why": verdict, "detail": proof})
            continue
        if not dry_run:
            mark_resolved(job)
        report["resolved"].append({"job": job, "proof": proof})
    report["skipped_by_cap"] = max(0, len(rows) - max_rows)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max", type=int, default=DEFAULT_MAX, help=f"rows per run (default {DEFAULT_MAX})")
    ap.add_argument("--dry-run", action="store_true", help="probe and report, mutate nothing")
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = ap.parse_args(argv)

    if not _enabled():
        print("board_seat_consumer: disabled by BOARD_SEAT_CONSUMER_ENABLED", file=sys.stderr)
        return 0

    lock_dir = Path(os.environ.get("BOARD_CONSUMER_LOCK_DIR", str(Path.home() / ".agent" / "locks")))
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = open(lock_dir / "board_seat_consumer.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("board_seat_consumer: another run holds the lock — skipping", file=sys.stderr)
        return 0

    try:
        report = consume(args.max, args.dry_run)
    except Exception as exc:  # noqa: BLE001 — a launchd organ must not die on a bad row
        print(f"board_seat_consumer: run failed ({exc}) — board untouched", file=sys.stderr)
        return 0
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            f"board_seat_consumer: {len(report['resolved'])} closed, "
            f"{len(report['left'])} left open, {report['seen']} seat rows seen"
        )
        for item in report["resolved"]:
            print(f"  closed {item['job']}: {item['proof']}")
        for item in report["left"]:
            print(f"  left   {item['job']}: {item['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

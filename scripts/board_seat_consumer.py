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
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sentinel_lib.escalations import (  # noqa: E402
    mark_resolved,
    read_all_escalations,
    ts_epoch,
)

_SAFE_JOB_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
#: a run-state clock may drift; a run-state FUTURE is a broken clock.
_FUTURE_TOLERANCE_S = 300

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


# Each healer owns its OWN lock, and they are not the same file: healer-run.sh
# (Mini, TG_SOURCE=healer-mini) holds /tmp/nuzantara-healer.pid while
# pro-healer.sh (TG_SOURCE=healer-pro) holds /tmp/nuzantara-pro-healer.pid. One
# shared default would read "the lock is already gone" on the machine that does
# not own that path and close a row whose healer is still stuck — the exact
# false cure this file exists to refuse.
_HEALER_PIDFILES = {
    "healer-mini": "/tmp/nuzantara-healer.pid",
    "healer-pro": "/tmp/nuzantara-pro-healer.pid",
}


def _healer_pidfile(family: str) -> Path | None:
    override = os.environ.get("BOARD_CONSUMER_HEALER_PIDFILE", "")
    if override:
        return Path(override)
    path = _HEALER_PIDFILES.get(family)
    return Path(path) if path else None


def _this_machine() -> str:
    """The machine name EXACTLY as the producer writes it.

    tg_notify.py stamps `socket.gethostname().split(".")[0]`. A consumer that
    compares against the unsplit name matches only while macOS happens to
    return a bare hostname: the day it returns `Nuzantara.local` instead — a
    reboot, a network change, HostName unset — every row reads as foreign and
    this organ runs hourly, heartbeats `ok` and closes nothing. Green and
    inert is the failure this file exists to drain, so the normalisation is
    copied from the producer rather than re-invented.
    """
    return os.environ.get("BOARD_CONSUMER_MACHINE", socket.gethostname()).split(".")[0]


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
    # The dedup-key comes from ~204 callers and becomes a PATH on the next line.
    # `cron-fail:../../somewhere/else` would read a file outside the state dir and
    # could close a row against a stranger's status. The runner's own job names are
    # this shape; anything else is refused rather than normalised.
    if not _SAFE_JOB_NAME.match(name):
        return NOT_CURABLE, f"job name {name!r} is not a plain state-file name — refusing to build a path from it"
    path = _state_dir() / f"{name}.last.json"
    if not path.is_file():
        return NOT_CURABLE, f"no run-state file for {name} (job is invisible to this probe)"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return NOT_CURABLE, f"run-state unreadable: {exc}"
    # The state file must be THIS job's, on THIS host. A file whose own `job`
    # or `host` names someone else is a stranger's witness: it says nothing
    # about the row being closed, and it reads `ok` just as convincingly.
    state_job = state.get("job")
    if state_job is not None and str(state_job) != name:
        return NOT_CURABLE, f"{name}.last.json says job={state_job!r} — a stranger's witness"
    state_host = state.get("host")
    if state_host is not None and str(state_host) != socket.gethostname():
        return NOT_CURABLE, f"{name}.last.json was written by {state_host!r}, not this host"
    status = str(state.get("status", "?"))
    raw_ts = state.get("ts")
    # ts_epoch parses ISO strings and assumes UTC for a naive one. Every runner
    # here writes epoch seconds (checked on Pro), and the day one does not, a
    # naive local timestamp would read 8h into the future in WITA and close a row
    # whose run PRECEDED the alarm. The witness only counts when it is a number.
    if isinstance(raw_ts, bool) or not isinstance(raw_ts, (int, float)):
        return NOT_CURABLE, f"{name}.last.json ts is {type(raw_ts).__name__}, not epoch seconds — refusing to compare"
    state_ts = ts_epoch(raw_ts)
    # A state run dated in the FUTURE is a clock, not a recovery: it beats every
    # alert ts there will ever be, so it would close this row and each of its
    # successors forever.
    if state_ts > time.time() + _FUTURE_TOLERANCE_S:
        return NOT_CURABLE, f"{name}.last.json ts={state_ts:.0f} is in the future — a clock, not a recovery"
    # And the alert's OWN ts must be readable. ts_epoch orders junk as 0.0 —
    # deliberately, so a bad ts hides a line's age and never the line — but 0.0
    # is smaller than every state ts, which would turn "unreadable" into
    # "recovered" for the entire class.
    raw_row_ts = row.get("ts")
    if isinstance(raw_row_ts, bool) or not isinstance(raw_row_ts, (int, float)):
        return NOT_CURABLE, f"the alert's own ts is {type(raw_row_ts).__name__}, not epoch seconds — nothing to compare against"
    row_ts = ts_epoch(raw_row_ts)
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
    # An empty successful ps is not "not a healer": the process table simply had
    # nothing to say about a pid os.kill(pid, 0) just accepted. Undecidable, and
    # undecidable never cures.
    if not out.stdout.strip():
        return None
    return "healer" in out.stdout.lower()


def cure_healer_stale_lock(row: dict, dry_run: bool) -> tuple[str, str]:
    job = str(row.get("job", ""))
    if not job.endswith(":stale-lock"):
        return NOT_CURABLE, "healer row that is not the stale-lock condition"
    pidfile = _healer_pidfile(job.split(":", 1)[0])
    if pidfile is None:
        return NOT_CURABLE, f"no lock path known for {job.split(':', 1)[0]!r}"
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
    # Between the liveness probe above and the unlink below, a healer may have
    # started and rewritten this file. Removing it then would unlock a LIVE run.
    try:
        if int(pidfile.read_text(encoding="utf-8").strip()) != pid:
            return NOT_CURABLE, f"{pidfile} changed under us — a run started since the probe"
    except (OSError, ValueError):
        return NOT_CURABLE, f"{pidfile} became unreadable between the probe and the cure"
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


def _same_job_pending_elsewhere(row: dict, machine: str) -> str:
    """The machine name of a peer holding an open row with this exact job, if any."""
    job = row.get("job")
    latest: dict[str, dict] = {}
    for candidate in read_all_escalations(include_resolved=True):
        if candidate.get("job") != job:
            continue
        host = str(candidate.get("machine", "?"))
        known = latest.get(host)
        if known is None or ts_epoch(candidate.get("ts")) > ts_epoch(known.get("ts")):
            latest[host] = candidate
    for host, newest in latest.items():
        if host != machine and newest.get("status") != RESOLVED:
            return host
    return ""


def _still_the_row_we_probed(row: dict) -> bool:
    """Re-read the board and confirm nothing newer landed for this job.

    Between open_seat_rows() and the close, the condition can re-fire: the cron
    fails again, the gateway appends a FRESH pending row, and a resolution
    written now would carry a newer ts and collapse that live alarm into
    silence. The probe proved the OLD row was over, never the new one.
    """
    job = row.get("job")
    newest = None
    for candidate in read_all_escalations(include_resolved=True):
        if candidate.get("job") != job:
            continue
        if newest is None or ts_epoch(candidate.get("ts")) > ts_epoch(newest.get("ts")):
            newest = candidate
    return newest is not None and ts_epoch(newest.get("ts")) == ts_epoch(row.get("ts"))


def consume(max_rows: int, dry_run: bool) -> dict:
    machine = _this_machine()
    report = {"machine": machine, "dry_run": dry_run, "seen": 0, "resolved": [], "left": []}
    rows = open_seat_rows()
    report["seen"] = len(rows)
    attempted = 0
    skipped_by_cap = 0
    for row in rows:
        job = str(row.get("job", ""))
        family = job.split(":", 1)[0]
        # A foreign row and a family with no cure are decided at zero cost, so
        # they must NOT consume the cap. Slicing first starves the queue: these
        # rows never leave the board, they sort oldest-first forever, and within
        # weeks the cap is spent entirely on rows that were never curable while
        # every curable row behind them goes untouched — an organ reporting a
        # green run every hour and closing nothing (superscar #2).
        if row.get("machine") != machine:
            report["left"].append({"job": job, "why": FOREIGN, "detail": str(row.get("machine"))})
            continue
        cure = CURES.get(family)
        if cure is None:
            report["left"].append({"job": job, "why": NOT_CURABLE, "detail": f"no cure registered for family {family!r}"})
            continue
        if attempted >= max_rows:
            skipped_by_cap += 1
            continue
        attempted += 1
        verdict, proof = cure(row, dry_run)
        if verdict != RESOLVED:
            report["left"].append({"job": job, "why": verdict, "detail": proof})
            continue
        if not dry_run:
            # A resolution is keyed on `job` ALONE — every reader on this board
            # collapses by job, so closing Pro's `cron-fail:fly-pg-backup` also
            # silences Mini's pending row of the same name. The locality guard
            # above protects the CURE; this protects the RESOLUTION.
            elsewhere = _same_job_pending_elsewhere(row, machine)
            if elsewhere:
                report["left"].append({"job": job, "why": "pending_on_another_machine", "detail": elsewhere})
                continue
            if not _still_the_row_we_probed(row):
                report["left"].append({"job": job, "why": "re_fired_since_the_probe", "detail": proof})
                continue
            # 0 means a peer resolved it between this run's read and now. Saying
            # "closed" anyway would make the organ's own note a small lie.
            if not mark_resolved(job):
                report["left"].append({"job": job, "why": "already_closed_by_a_peer", "detail": proof})
                continue
        report["resolved"].append({"job": job, "proof": proof})
    report["attempted"] = attempted
    report["skipped_by_cap"] = skipped_by_cap
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
            f"{len(report['left'])} left open, {report['seen']} seat rows seen, "
            f"{report['attempted']} cure(s) attempted"
        )
        for item in report["resolved"]:
            print(f"  closed {item['job']}: {item['proof']}")
        for item in report["left"]:
            print(f"  left   {item['job']}: {item['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

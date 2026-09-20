#!/usr/bin/env python3
"""board_seat_consumer.py — drains the rows tg_notify routed to the seat lane.

PR #6973 gave the gateway a fourth tier: a p0 whose dedup-key is not an
OWNER_FAMILY stops reaching Telegram and lands on the escalation board as
``type=gateway_routed, cure_lane.owner=seat, priority=NORMAL``. That tier went
live on Pro and the board held ONE such row when this was written (2026-09-21
04:06 WITA) — this is a tap that has just been opened, not a backlog, and the
distinction is stated here because the first run of this organ closes zero and
must not be read as a broken one.

What the tap will carry is measurable from the gateway's OWN p0 archive rather
than from the board, and that is the number this file is sized against. Over
the 30 days to 2026-09-21 on Pro: 313 p0, of which 285 are not owner-reserved
and therefore route here. `cron-fail` is 123 of those 285 — the largest routed
family by a factor of 7.7 over the next one — across 34 distinct jobs.

What it will NOT do, decided from that distribution and not from taste:

  - It does not kickstart on a whim. `organs_registry.yaml` declares a
    `recovery_action` for 170 organs (109 of them `launchctl_kickstart`) and no
    loop has ever executed one; every healer tick that met a `dead` organ
    root-caused it and refused the restart, correctly — `iqoo_radar_relay` was
    failing on `Permission denied (publickey)` and a kickstart reproduces the
    identical outcome. A restart that does not cure is a green run that fixed
    nothing (superscar #2).
  - It does not close a row it cannot PROVE is over. The cure below re-probes
    the condition live in this run. The alert text is evidence of what was true
    when it was written, never of what is true now (superscar #6).
  - It never touches a row belonging to another machine. The board is one
    git-tracked file shared by three checkouts; curing Pro's state from Mini is
    superscar #10 with extra steps.
  - It carries ONE cure, and the narrowness is a correction, not modesty. Its
    predecessor (#6992, closed on the gate's REWORK-BUILD) shipped a second one
    — `healer-*:stale-lock`, which removes a pidfile — on a count of 13 that
    turned out to be the whole `healer-mini` FAMILY: the stale-lock ENTITY
    itself had fired once in 74 days of archive, and the only code that emits
    that key is `infra/healer/healer-run.sh:160`, which runs on Mini. Armed on
    Pro, behind the locality guard above, that cure was unreachable by
    construction. A cure belongs here when its own entity is measured where the
    organ runs; until then it is dead code with tests around it.

Cures are matched on the dedup-key's ENTITY — the family before the first ':',
compared by equality against CURES — never by substring (superscar #3).

    cron-fail:<job>     the cron has ALREADY recovered: its own run-state file
                        (~/.agent/decisions/state/<job>.last.json, written by
                        the cron runner) says status=ok with a ts newer than the
                        alert. No action is taken; the row is stale, and saying
                        so is the cure. Replayed against Pro's live state dir,
                        18 of the 34 distinct cron-fail jobs in that window read
                        that way — 73 of the 123 alerts. The other 16 refuse for
                        a reason the report names, one job at a time: 10 have no
                        run-state file at all and 6 are still failing.

A family with no cure is left pending and COUNTED. That count is the honest
measure of what still needs a session, and it must never be closed to make a
number look better. The one row on the board today is such a case: its key is a
bare hash with no family, so it is reported, not closed.

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


def _short_host(name: str) -> str:
    """The bare host, for comparing two producers that disagree on the suffix.

    `cron-state.sh` writes the run-state `host` as `hostname -s` — already bare.
    `socket.gethostname()` is not: the day macOS returns `Nuzantara.local` the
    two stop matching and every cron-fail row is refused, on an organ that still
    runs hourly and still heartbeats `ok`. The same mismatch was fixed one
    function below for the BOARD's `machine` field and left standing here, which
    is why it is a named function now instead of a `.split(".")[0]` a reader has
    to notice twice.
    """
    return name.split(".")[0]


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
    if state_host is not None and _short_host(str(state_host)) != _short_host(socket.gethostname()):
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


CURES = {
    "cron-fail": lambda row, dry: cure_cron_fail(row),
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
            # mark_resolved's return is NOT a peer check and must not be read
            # as one: it counts rows from read_all_escalations(), which filters
            # per LINE on status, so the original pending row this cure was
            # built from is always among them and the count is always >= 1. The
            # real race — the condition re-firing — is caught by
            # _still_the_row_we_probed above, which reads the board again.
            mark_resolved(job)
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

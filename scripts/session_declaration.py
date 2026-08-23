#!/usr/bin/env python3
"""session_declaration.py — two-phase commit for autonomous runs.

THE DISEASE (measured 2026-08-23, superscar #2). A cron wrapper spawns an
autonomous session, the session dies, launchd records exit 0, and no organ
anywhere raises a hand. The work did not happen and every gauge reads green.

THE FALSE CURE, and why it is worth writing down. The first attempt read the
session's own PROSE and asked "did it run as long as it declared?" — that
detector accused TEN healer ticks out of ten, every one healthy. Two reasons,
both structural:

  1. "loop 4h" in a mandate's TITLE is the cron CADENCE (StartInterval 14400),
     not the session's runtime. No amount of regex narrowing separates "this
     document declares its own runtime" from "this document's title names a
     schedule" — three narrowing passes traded one error direction for the
     other (PR #4646, retired verdict DECLARED-SPAN-UNMET).
  2. Even with a perfect parse, the number a wrapper actually holds is a CAP
     (healer: MAX_WALL_S=3300), not an expectation. A tick that finishes its
     work in 11 minutes against a 55-minute cap is CORRECT. Measuring duration
     against a cap rebuilds the same false positive in new clothes.

THE REAL SIGNAL is not duration at all. It is whether the runner came BACK.

  open()   the wrapper writes a declaration BEFORE the work: its own pid, its
           own cap, and — in a SEPARATE field so the two can never again be
           conflated — the cron cadence it runs on.
  close()  the wrapper stamps an outcome on the way out, whatever the outcome
           is, including when its own watchdog killed the child.
  scan()   a declaration still OPEN past its own cap, whose recorded process is
           no longer alive, means the runner never came back. That is an
           OBSERVATION, not an inference.

It cannot fire on a healthy short tick, because a healthy tick closes its own
declaration. It catches machine reboots, -9 kills, wrapper crashes, and the
class that cost us a build lane the same day: a spawned tool that exits 0
having done nothing — declaration opened, no work, no stamp.

INDEPENDENCE OF THE CHECK (the lesson this repo paid for four times in one PR:
a check that derives its reference from its subject always agrees). Liveness is
read from the OS process table, never from anything the dying process wrote.
PID reuse is defeated by storing the process START TIME alongside the pid: a
rebooted machine's pid 1234 has a different lstart, so a recycled pid can never
resurrect a dead declaration.

CLI
    session_declaration.py open  --spawner NAME --cap-sec N [--cadence-sec N]
                                 [--mandate REF] [--session-id UUID]  -> run_id
    session_declaration.py close --run-id ID --outcome OUTCOME [--exit-code N]
    session_declaration.py scan  [--json] [--grace-sec N]
    session_declaration.py --selftest

Exit codes for scan: 0 = nothing abandoned, 1 = at least one ABANDONED row,
2 = the scan itself could not see (unreadable store) — blind is never clean.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- constants

OPEN = "OPEN"
CLOSED = "CLOSED"
ABANDONED = "ABANDONED"
# Abandoned, but past the reporting window: still true, no longer actionable.
ABANDONED_STALE = "ABANDONED-STALE"
# Alive, but far past its own cap: the wrapper's watchdog did not reap it.
# A DIFFERENT disease from abandonment and it must not be folded into it — but
# it is just as actionable, and nothing else can see it. Measured 2026-08-23:
# the healer's watchdog sends ONE SIGTERM and never escalates to SIGKILL, and a
# wrapper stuck in `wait` keeps holding the PIDFILE lock — so a single hang
# makes every later tick exit at "previous run still alive" before reaching ANY
# receptor. One hang blinds the whole healer, silently, forever.
HUNG = "HUNG"

# A declaration is only suspicious once it has outlived the runner's OWN cap.
# The grace exists because a wrapper's last act — stamping the outcome — happens
# after the cap has already elapsed in the watchdog-kill path.
DEFAULT_GRACE_SEC = 300

# An abandonment is ACTIONABLE only while it is fresh. Without this window a
# single dead run would keep the healer permanently non-idle: REASONS would never
# be empty, so every 4h tick would spawn an LLM session forever over a fact that
# was already reported on the first one. The record stays on disk for forensics —
# it simply stops driving the alarm. The healer's own cadence (4h) is far inside
# this window, so nothing real is missed before it is seen at least once.
DEFAULT_REPORT_WINDOW_SEC = 172800  # 48h

# The watchdog fires AT the cap. Still alive this long after it is unambiguous —
# generous on purpose, so a slow shutdown is never called a hang.
DEFAULT_HUNG_MARGIN_SEC = 1800  # 30 min past the cap

# Retention, applied at open() — one bounded sweep per run, never on the read
# path. A scan that silently deleted what it reports would be a probe with a side
# effect on its own subject.
RETAIN_CLOSED_SEC = 604800     # 7d: a closed run has no diagnostic value after
RETAIN_ABANDONED_SEC = 2592000 # 30d: findings outlive their reporting window

# Outcomes a wrapper may stamp. Free-form is deliberately NOT allowed: an
# outcome vocabulary that anyone can extend stops being comparable across
# organs, and the healer routes on these exact strings.
OUTCOMES = frozenset(
    {
        "completed",          # the runner finished its work and exited
        "killed-by-watchdog", # the wrapper's own wall-clock cap fired
        "failed",             # the runner exited non-zero on its own
        "skipped",            # the wrapper decided not to spawn (kill switch, lock)
    }
)

SCHEMA_VERSION = 1


def store_dir() -> str:
    """Sibling of ~/.organism/last_seen (the heartbeat sidecars), same family."""
    return os.environ.get(
        "SESSION_DECLARATION_DIR",
        os.path.join(os.path.expanduser("~"), ".organism", "session_declarations"),
    )


# ---------------------------------------------------------------- liveness

# Absolute path, not a PATH lookup. This codebase has repeatedly been bitten by
# a bare binary name being unresolvable under launchd/ssh (the wrapper's own
# telegram() carries an absolute-path fallback for exactly that reason). If `ps`
# went missing, EVERY liveness answer would fail closed at once and every live
# run past its cap would be called abandoned — a fleet-wide false positive.
_PS_BIN = "/bin/ps" if os.path.exists("/bin/ps") else "ps"


def process_start(pid: int) -> Optional[str]:
    """Return the process's start time as reported by ps, or None if it is gone.

    `ps -o lstart=` is used rather than a bare existence test because a pid is
    reused: over the hours a declaration can stay open, pid N may belong to an
    entirely unrelated process, and after a reboot it certainly does. The start
    time makes the identity check exact without needing any cooperation from
    the process itself.
    """
    try:
        out = subprocess.run(
            [_PS_BIN, "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    started = out.stdout.strip()
    return started or None


def runner_alive(decl: Dict[str, Any]) -> bool:
    """True only if the RECORDED process is still the one running.

    Absent/garbled pid data reads as NOT alive: a declaration we cannot check is
    exactly the state this tool exists to surface, and treating it as alive
    would silence the alarm on the malformed case.
    """
    pid = decl.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    now = process_start(pid)
    if now is None:
        return False
    recorded = decl.get("pid_start")
    if not recorded:
        # An older declaration without the start stamp: fall back to bare
        # existence. Declared narrowing — it can only produce a MISSED
        # abandonment (pid reuse hiding a dead runner), never a false accusation.
        return True
    return now == recorded


# ---------------------------------------------------------------- store I/O

def _path_for(run_id: str) -> str:
    return os.path.join(store_dir(), f"{run_id}.json")


def _write_atomic(path: str, payload: Dict[str, Any]) -> None:
    """Write via tmp + replace so a reader never sees a half-written record.

    A torn declaration would be read as malformed and — per read_all's contract
    — surfaced rather than skipped, which would turn every concurrent scan into
    a false alarm.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def prune(now: Optional[float] = None) -> int:
    """Delete records that can no longer inform anything. Returns the count.

    Called from open() — one bounded sweep per run, at the moment a wrapper is
    already writing. Deliberately NOT called from scan(): a read that mutates
    what it reports is a probe with a side effect on its own subject, and the
    next reader would see a different store than the one that produced the
    verdict it was handed.

    OPEN records are NEVER pruned at any age: an open declaration is either a
    live run or an abandonment, and deleting it would erase exactly the finding
    this module exists to make.
    """
    ts = time.time() if now is None else now
    removed = 0
    decls, _, readable = read_all()
    if not readable:
        return 0
    for d in decls:
        opened = d.get("opened_at")
        if not isinstance(opened, (int, float)):
            continue
        age = ts - opened
        closed = d.get("closed_at") is not None
        if closed and age > RETAIN_CLOSED_SEC:
            pass
        elif not closed and age > RETAIN_ABANDONED_SEC:
            pass
        else:
            continue
        try:
            os.remove(_path_for(d["run_id"]))
            removed += 1
        except OSError:
            # A record we cannot delete is not an error worth failing a run for.
            pass
    return removed


def open_declaration(
    spawner: str,
    cap_sec: int,
    cadence_sec: Optional[int] = None,
    mandate: Optional[str] = None,
    session_id: Optional[str] = None,
    pid: Optional[int] = None,
    host: Optional[str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Record a run as started. Returns the declaration (its run_id is the key).

    cap_sec and cadence_sec are SEPARATE fields on purpose. Collapsing them into
    one number is the original defect: the healer's cap is 3300s and its cadence
    is 14400s, and a reader with only one of them cannot tell which it holds.
    """
    if not spawner:
        raise ValueError("spawner is required — an anonymous declaration names no organ")
    if cap_sec <= 0:
        raise ValueError("cap_sec must be > 0 — without a cap nothing ever becomes abandoned")

    pid = os.getppid() if pid is None else pid
    ts = time.time() if now is None else now
    decl = {
        "schema": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "spawner": spawner,
        "host": host or os.uname().nodename,
        "pid": pid,
        "pid_start": process_start(pid),
        "cap_sec": int(cap_sec),
        "cadence_sec": int(cadence_sec) if cadence_sec else None,
        "mandate": mandate,
        # Optional join to a transcript. NOT load-bearing: the cascade passes
        # the same extra args to every seat attempt, so a caller-supplied
        # --session-id would collide across retries. Left null by the healer.
        "session_id": session_id,
        "opened_at": ts,
        "closed_at": None,
        "outcome": None,
        "exit_code": None,
    }
    _write_atomic(_path_for(decl["run_id"]), decl)
    try:
        prune(now=ts)
    except OSError:
        # Retention is housekeeping: never let it stop a run from being declared.
        pass
    return decl


def close_declaration(
    run_id: str,
    outcome: str,
    exit_code: Optional[int] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Stamp the outcome. Idempotent: re-closing keeps the FIRST outcome.

    Idempotence matters because the healer closes from an EXIT trap, and a trap
    can fire twice (normal return then signal). Overwriting would let a generic
    trap-close erase the specific 'killed-by-watchdog' the wrapper knew about.
    """
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r} — allowed: {sorted(OUTCOMES)}")
    path = _path_for(run_id)
    with open(path, "r") as fh:
        decl = json.load(fh)
    if decl.get("closed_at") is not None:
        return decl
    decl["closed_at"] = time.time() if now is None else now
    decl["outcome"] = outcome
    decl["exit_code"] = exit_code
    _write_atomic(path, decl)
    return decl


def read_all() -> Tuple[List[Dict[str, Any]], List[str], bool]:
    """Return (declarations, malformed_names, store_readable).

    A malformed file is REPORTED, never silently skipped: 'the store had a file
    I could not parse' and 'the store was empty' must not produce the same
    clean-looking answer (W97/W84 discipline).
    """
    d = store_dir()
    if not os.path.isdir(d):
        # An absent store is a legitimately empty state, not blindness: no
        # wrapper has opened a declaration yet.
        return [], [], True
    try:
        names = os.listdir(d)
    except OSError:
        return [], [], False

    decls: List[Dict[str, Any]] = []
    malformed: List[str] = []
    for name in sorted(names):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), "r") as fh:
                obj = json.load(fh)
        except (OSError, ValueError):
            malformed.append(name)
            continue
        if not isinstance(obj, dict) or "run_id" not in obj:
            malformed.append(name)
            continue
        decls.append(obj)
    return decls, malformed, True


# ---------------------------------------------------------------- the verdict

def classify(
    decl: Dict[str, Any],
    now: float,
    grace_sec: int = DEFAULT_GRACE_SEC,
    alive: Optional[bool] = None,
    report_window_sec: int = DEFAULT_REPORT_WINDOW_SEC,
    hung_margin_sec: int = DEFAULT_HUNG_MARGIN_SEC,
    alive_fn: Optional[Any] = None,
) -> str:
    """CLOSED | OPEN | HUNG | ABANDONED | ABANDONED-STALE — the whole detector.

    Deliberately NOT a function of how long the run lasted. A run that closes
    after 30 seconds is CLOSED; a run still inside its own cap is OPEN however
    long it has been going.
    """
    if decl.get("closed_at") is not None:
        return CLOSED
    opened = decl.get("opened_at")
    if not isinstance(opened, (int, float)):
        # No open timestamp: cannot age it, so it can never be proven abandoned.
        # Surfaced as OPEN rather than guessed — never guess (mandate 2026-08-23).
        return OPEN
    cap = decl.get("cap_sec")
    cap = int(cap) if isinstance(cap, (int, float)) and cap > 0 else 0
    if now - opened <= cap + grace_sec:
        return OPEN
    # Resolved HERE and nowhere earlier: every branch above returns without ever
    # needing it, so a CLOSED or still-inside-cap record never costs a `ps` spawn.
    if alive is not None:
        is_alive = alive
    else:
        is_alive = (alive_fn or runner_alive)(decl)
    if is_alive:
        # Just past the cap and still there: the wrapper is shutting down. Only
        # once it is FAR past does this become a hang worth naming.
        if now - opened > cap + hung_margin_sec:
            return HUNG
        return OPEN
    if now - opened > report_window_sec:
        return ABANDONED_STALE
    return ABANDONED


def scan(
    grace_sec: int = DEFAULT_GRACE_SEC,
    now: Optional[float] = None,
    alive_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Classify the whole store.

    alive_fn is a TEST SEAM (same family as the healer's FLEET_HOSTS_OVERRIDE):
    without it, the abandoned branch can only be exercised by forging pid data
    inside the store, which tests the forgery rather than the scan. Production
    never passes it, so the default path is the one that ships.
    """
    decls, malformed, readable = read_all()
    ts = time.time() if now is None else now
    liveness = runner_alive if alive_fn is None else alive_fn
    rows = []
    for d in decls:
        # alive_fn is HANDED DOWN, never called here: liveness costs a `ps`
        # spawn per record, and classify() reaches it only on the one branch
        # that needs it. Calling it eagerly made scan cost grow with every run
        # ever recorded, CLOSED ones included.
        state = classify(d, ts, grace_sec, alive_fn=liveness)
        age = ts - d["opened_at"] if isinstance(d.get("opened_at"), (int, float)) else None
        rows.append(
            {
                "run_id": d.get("run_id"),
                "spawner": d.get("spawner"),
                "host": d.get("host"),
                "state": state,
                "outcome": d.get("outcome"),
                "cap_sec": d.get("cap_sec"),
                "cadence_sec": d.get("cadence_sec"),
                "age_sec": round(age) if age is not None else None,
                "session_id": d.get("session_id"),
            }
        )
    rows.sort(key=lambda r: (r["state"] not in (ABANDONED, HUNG), r["spawner"] or "", r["run_id"] or ""))
    abandoned = [r for r in rows if r["state"] == ABANDONED]
    hung = [r for r in rows if r["state"] == HUNG]
    return {
        "rows": rows,
        "summary": {
            "total": len(rows),
            "abandoned": len(abandoned),
            "open": sum(1 for r in rows if r["state"] == OPEN),
            "closed": sum(1 for r in rows if r["state"] == CLOSED),
            "hung": len(hung),
            "hung_spawners": sorted({r["spawner"] for r in hung if r["spawner"]}),
            "abandoned_spawners": sorted({r["spawner"] for r in abandoned if r["spawner"]}),
            "malformed": malformed,
            "store_readable": readable,
        },
    }


def render_table(report: Dict[str, Any]) -> str:
    rows = report["rows"]
    s = report["summary"]
    if not s["store_readable"]:
        return "BLIND — the declaration store could not be read; this is not a clean result."
    if not rows:
        return "no declarations (store empty) — 0 abandoned"
    head = f"{'STATE':<10} {'SPAWNER':<26} {'HOST':<14} {'AGE':>8} {'CAP':>7} {'OUTCOME'}"
    lines = [head, "-" * len(head)]
    for r in rows:
        age = f"{r['age_sec']}s" if r["age_sec"] is not None else "?"
        cap = f"{r['cap_sec']}s" if r["cap_sec"] else "?"
        lines.append(
            f"{r['state']:<10} {(r['spawner'] or '?')[:26]:<26} "
            f"{(r['host'] or '?')[:14]:<14} {age:>8} {cap:>7} {r['outcome'] or '-'}"
        )
    lines.append("")
    lines.append(
        f"{s['total']} declaration(s): {s['abandoned']} ABANDONED, "
        f"{s.get('hung', 0)} HUNG, {s['open']} open, {s['closed']} closed"
    )
    if s["malformed"]:
        lines.append(f"WARNING — {len(s['malformed'])} unparseable file(s): {', '.join(s['malformed'])}")
    return "\n".join(lines)


# ---------------------------------------------------------------- selftest

def _selftest() -> int:
    """In-process proof of guilt AND innocence, on a temp store."""
    import tempfile

    failures = []

    def check(name: str, cond: bool) -> None:
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["SESSION_DECLARATION_DIR"] = tmp
        t0 = 1_000_000.0

        # INNOCENCE 1 — the exact shape that produced ten false positives:
        # a healthy healer tick, 11 minutes of work against a 55-minute cap,
        # on a 4-hour cadence. It closes, so it is CLOSED forever after.
        healthy = open_declaration(
            "healer-run.sh", cap_sec=3300, cadence_sec=14400, pid=os.getpid(), now=t0
        )
        close_declaration(healthy["run_id"], "completed", 0, now=t0 + 671)
        check(
            "healthy short tick is CLOSED",
            classify(json.load(open(_path_for(healthy["run_id"]))), t0 + 999_999) == CLOSED,
        )

        # INNOCENCE 2 — still running, well inside its own cap.
        running = open_declaration("healer-run.sh", cap_sec=3300, pid=os.getpid(), now=t0)
        check("run inside its cap is OPEN", classify(running, t0 + 600) == OPEN)

        # INNOCENCE 3 — just past the cap and still alive: the wrapper is
        # shutting down, that is not a hang and not an abandonment.
        check(
            "just past cap but alive is OPEN",
            classify(running, t0 + 3300 + 60, alive=True) == OPEN,
        )

        # GUILT 3 — FAR past its cap and still alive: the watchdog never reaped
        # it. Measured: that wrapper still holds the PIDFILE, so every later tick
        # exits before reaching any receptor — one hang blinds the whole healer.
        check(
            "far past cap but alive is HUNG",
            classify(running, t0 + 3300 + DEFAULT_HUNG_MARGIN_SEC + 1, alive=True) == HUNG,
        )

        # An abandonment past the reporting window stops driving the alarm but
        # stays on disk: otherwise one dead run spawns an LLM session every 4h
        # forever over a fact already reported on the first tick.
        check(
            "abandonment past the window goes STALE",
            classify(running, t0 + DEFAULT_REPORT_WINDOW_SEC + 10_000, alive=False)
            == ABANDONED_STALE,
        )

        # GUILT 1 — past its own cap, runner gone: the runner never came back.
        check(
            "past cap and dead is ABANDONED",
            classify(running, t0 + 3300 + DEFAULT_GRACE_SEC + 1, alive=False) == ABANDONED,
        )

        # GUILT 2 — the build-lane class: opened, exited 0 having done nothing,
        # never stamped. Indistinguishable from a crash, and correctly accused.
        check(
            "opened-but-never-stamped is ABANDONED",
            classify(
                open_declaration("codex-builder", cap_sec=60, pid=os.getpid(), now=t0),
                t0 + 60 + DEFAULT_GRACE_SEC + 1,
                alive=False,
            )
            == ABANDONED,
        )

        # The cadence must never be readable as the cap — the original defect.
        check("cap and cadence stay separate", healthy["cap_sec"] == 3300 and healthy["cadence_sec"] == 14400)

        # close() is idempotent and keeps the FIRST outcome (double trap fire).
        dbl = open_declaration("x", cap_sec=10, pid=os.getpid(), now=t0)
        close_declaration(dbl["run_id"], "killed-by-watchdog", 137, now=t0 + 1)
        again = close_declaration(dbl["run_id"], "completed", 0, now=t0 + 2)
        check("close is idempotent, first outcome wins", again["outcome"] == "killed-by-watchdog")

        # A malformed file is reported, not swallowed.
        with open(os.path.join(tmp, "garbage.json"), "w") as fh:
            fh.write("{not json")
        _, malformed, readable = read_all()
        check("malformed file is surfaced", malformed == ["garbage.json"] and readable)

        # An unknown outcome is refused rather than recorded.
        try:
            close_declaration(dbl["run_id"], "vibes", None)
            check("unknown outcome rejected", False)
        except ValueError:
            pass

    if failures:
        print("selftest FAILED: " + "; ".join(failures), file=sys.stderr)
        return 1
    print("selftest PASSED")
    return 0


# ---------------------------------------------------------------- main

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p_open = sub.add_parser("open", help="record a run as started; prints the run_id")
    p_open.add_argument("--spawner", required=True)
    p_open.add_argument("--cap-sec", type=int, required=True)
    p_open.add_argument("--cadence-sec", type=int)
    p_open.add_argument("--mandate")
    p_open.add_argument("--session-id")
    p_open.add_argument("--pid", type=int)

    p_close = sub.add_parser("close", help="stamp the outcome of a run")
    p_close.add_argument("--run-id", required=True)
    p_close.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    p_close.add_argument("--exit-code", type=int)

    p_scan = sub.add_parser("scan", help="classify every declaration in the store")
    p_scan.add_argument("--json", action="store_true")
    p_scan.add_argument("--grace-sec", type=int, default=DEFAULT_GRACE_SEC)

    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.cmd == "open":
        decl = open_declaration(
            spawner=args.spawner,
            cap_sec=args.cap_sec,
            cadence_sec=args.cadence_sec,
            mandate=args.mandate,
            session_id=args.session_id,
            pid=args.pid,
        )
        print(decl["run_id"])
        return 0

    if args.cmd == "close":
        try:
            close_declaration(args.run_id, args.outcome, args.exit_code)
        except (OSError, ValueError) as exc:
            # A close that cannot find its declaration must not kill the wrapper
            # that is on its way out — it degrades to a visible warning.
            print(f"close failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "scan":
        report = scan(grace_sec=args.grace_sec)
        print(json.dumps(report, indent=2) if args.json else render_table(report))
        if not report["summary"]["store_readable"]:
            return 2
        return 1 if (report["summary"]["abandoned"] or report["summary"]["hung"]) else 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""queue_doctor.py — the three queues, one probe each, on demand.

Born as a hand-written HTML snapshot (2026-08-09, "Queue Doctor — tre code, una
capacità ciascuna") whose numbers were dead within hours. This is its promotion
to structure: the same three sections, regenerated from live probes each run.

The three queues are the same shape at three scales — a capacity, a waiting
line, and something deciding the order:

  1. MERGE QUEUE   (github)  — PRs queued on main, plus armed-but-unqueued ones.
  2. PRE-PUSH LOCK (local)   — the single-flight backend-suite lock on THIS
                               machine (scripts/prepush_suite_lock.sh).
  3. P0 SPOOL      (Pro)     — the rationed Telegram P0 lane: pending backlog,
                               last flush age, today's archived P0 count.
                               Counts only — no message body ever leaves Pro.

Design constraints (blood-bought, see cicatrix families #2/#9):
  * READ-ONLY. This is a segnalatore: it never mutates a queue, never flushes,
    never reaps. Prescriptions are for the reader.
  * A probe that cannot measure says CANNOT-VERIFY and sets exit bit 4 — it
    never fabricates a zero (W104: the guard that read a refusal as "no keys";
    W106b: offline is a natural state, not a drift).
  * No cron, no daemon, no heartbeat. Run it when a queue feels slow. A
    scheduled copy would be one more green-that-lies surface to guard.

Exit code: 0 = all probes measured; bit 4 (=4) = at least one CANNOT-VERIFY.
The verdict text, not the exit code, is the product.

Env overrides (test seams + fleet variance):
  QUEUE_DOCTOR_REPO   default "Bali-Zero/Teman2"
  QUEUE_DOCTOR_LOCK   default "/tmp/nuzantara-prepush-backend-suite.lock"
  QUEUE_DOCTOR_SSH    default "pro" (ssh alias for the spool host; "" = skip).
                      If the alias resolves back to THIS machine, the probe runs
                      locally instead — see _spool_is_this_machine().
  QUEUE_DOCTOR_SPOOL  default "~/.organism/tg_spool" (path on the spool host)
"""

from __future__ import annotations

import datetime as _dt
import getpass
import json
import math
import os
import re
import socket
import subprocess
import sys
import time

REPO = os.environ.get("QUEUE_DOCTOR_REPO", "Bali-Zero/Teman2")
LOCK = os.environ.get("QUEUE_DOCTOR_LOCK", "/tmp/nuzantara-prepush-backend-suite.lock")
SSH_HOST = os.environ.get("QUEUE_DOCTOR_SSH", "pro")
SPOOL = os.environ.get("QUEUE_DOCTOR_SPOOL", "~/.organism/tg_spool")

CANNOT_VERIFY = False


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    """Run a command; never raises. Returns (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def _cannot_verify(section: str, why: str) -> None:
    global CANNOT_VERIFY
    CANNOT_VERIFY = True
    print(f"  CANNOT-VERIFY — {why}")
    print(f"  (a probe that cannot measure must say so, not report a zero — {section} unmeasured)")


def probe_merge_queue() -> None:
    print("== 1. MERGE QUEUE ==")
    query = (
        'query($owner:String!,$name:String!){repository(owner:$owner,name:$name){'
        'mergeQueue(branch:"main"){entries(first:20){totalCount nodes{position '
        'pullRequest{number title}}}}'
        'pullRequests(states:OPEN,first:50){nodes{number autoMergeRequest{enabledAt}}}}}'
    )
    owner, name = REPO.split("/", 1)
    rc, out, err = _run([
        "gh", "api", "graphql",
        "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"name={name}",
    ])
    if rc != 0:
        _cannot_verify("merge queue", f"gh api failed rc={rc}: {err.strip()[:160]}")
        return
    try:
        repo = json.loads(out)["data"]["repository"]
        mq = repo.get("mergeQueue") or {}
        entries = (mq.get("entries") or {}).get("nodes") or []
        total = (mq.get("entries") or {}).get("totalCount", 0)
        armed = [
            pr["number"]
            for pr in (repo.get("pullRequests", {}).get("nodes") or [])
            if pr.get("autoMergeRequest")
        ]
    except (KeyError, ValueError, TypeError) as exc:
        _cannot_verify("merge queue", f"unexpected GraphQL shape: {exc}")
        return
    print(f"  in queue: {total}")
    for e in entries:
        pr = e.get("pullRequest") or {}
        print(f"    #{pr.get('number')} pos {e.get('position')} — {(pr.get('title') or '')[:60]}")
    print(f"  armed but not yet queued: {len(armed)} {armed if armed else ''}")
    # The trap this section exists to teach (verified live twice): once a PR
    # enters the queue, autoMergeRequest reads null — "auto=false" on a queued
    # PR means CONSUMED, not disarmed. Neither field alone is the state.


def probe_prepush_lock() -> None:
    print(f"== 2. PRE-PUSH SUITE LOCK ({LOCK}) ==")
    if not os.path.isdir(LOCK):
        print("  free — no holder, no queue")
        return
    holder_pid = ""
    pid_path = os.path.join(LOCK, "pid")
    try:
        with open(pid_path, encoding="utf-8") as fh:
            holder_pid = fh.read().strip()
    except OSError as exc:
        _cannot_verify(
            "pre-push lock",
            f"could not read holder pid {pid_path}: {type(exc).__name__}: {str(exc)[:160]}",
        )
        return
    age_min = -1.0
    try:
        age_min = (
            _dt.datetime.now() - _dt.datetime.fromtimestamp(os.stat(LOCK).st_mtime)
        ).total_seconds() / 60
    except OSError as exc:
        _cannot_verify(
            "pre-push lock",
            f"could not stat lock directory {LOCK}: {type(exc).__name__}: {str(exc)[:160]}",
        )
        return
    alive = False
    if holder_pid.isdigit():
        try:
            os.kill(int(holder_pid), 0)
            alive = True
        except (OSError, ProcessLookupError):
            alive = False
    rc, out, _ = _run(["pgrep", "-fl", "prepush_suite_lock.sh"])
    # every waiter (and the holder's own wrapper) is a live prepush_suite_lock.sh
    wrappers = [ln for ln in out.splitlines() if ln.strip()] if rc == 0 else []
    waiters = max(0, len(wrappers) - (1 if alive else 0))
    state = "ALIVE" if alive else "STALE (next waiter reclaims on poll)"
    print(f"  held for {age_min:.0f} min by pid {holder_pid or '?'} — {state}")
    print(f"  waiters on this machine: {waiters}")
    if not alive and holder_pid:
        print("  note: stale holder is self-healing by design; do NOT rm the lockdir by hand")


_INET_RE = re.compile(r"\binet\s+([0-9]+(?:\.[0-9]+){3})")


def _local_addresses() -> set[str]:
    """Every name and IPv4 address this machine answers to, lowercased.

    Only ever used to decide whether an ssh alias points back at us. An empty
    or partial result is SAFE by construction: the caller treats "not proven
    local" as remote, so a missing ifconfig/ip degrades to the ssh path — never
    to a local read attributed to another host.
    """
    names: set[str] = set()
    try:
        host = socket.gethostname()
        names.add(host.lower())
        names.add(host.split(".")[0].lower())
    except OSError:
        pass
    for cmd in (["ifconfig"], ["ip", "-4", "-o", "addr"]):
        rc, out, _ = _run(cmd, timeout=8)
        if rc == 0 and out:
            names.update(_INET_RE.findall(out))
            break
    return names


def _resolve_ssh_alias(alias: str) -> tuple[str, str]:
    """(hostname, user) exactly as ssh itself resolves `alias`, or ("", "").

    `ssh -G` is the only honest way to turn an alias into an address: it applies
    the same config, Match blocks and defaults the real connection would.
    """
    rc, out, _ = _run(["ssh", "-G", alias], timeout=8)
    if rc != 0:
        return "", ""
    host = user = ""
    for line in out.splitlines():
        key, _, value = line.partition(" ")
        if key == "hostname" and not host:
            host = value.strip()
        elif key == "user" and not user:
            user = value.strip()
    return host, user


def _spool_is_this_machine(alias: str) -> tuple[bool, str]:
    """Is the spool host US? Returns (verdict, the reason to print).

    The tempting shortcut — "the spool directory exists locally, so read it" —
    is WRONG and would be a worse defect than the one this replaces: every
    organism machine has a ~/.organism/tg_spool, so on Mini that shortcut would
    measure MINI's spool while the report still claimed the alias's host. The
    discriminator therefore compares resolved ADDRESSES, and abstains (=> ssh)
    whenever identity cannot be established.
    """
    host, user = _resolve_ssh_alias(alias)
    if not host:
        return False, f"ssh -G {alias} resolved no hostname"
    if host.lower() not in _local_addresses():
        return False, f"{alias} resolves to {host}, not an address of this machine"
    me = getpass.getuser()
    if user and user != me:
        return False, f"{alias} resolves here but as user {user!r}, not {me!r}"
    return True, f"{alias} resolves to {host}, an address of this machine"


def probe_p0_spool() -> None:
    print(f"== 3. P0 SPOOL ({SSH_HOST}:{SPOOL}) ==")
    if not SSH_HOST:
        _cannot_verify("P0 spool", "QUEUE_DOCTOR_SSH is empty — spool host not probed")
        return
    today = _dt.date.today().isoformat()
    # Counts only: wc/grep -c on the spool host; no message body crosses the wire.
    # Test every source before reading it. A missing archive is not the same as
    # an archive containing zero P0 events.
    #
    # A missing pending.jsonl, however, IS a measurement, and a healthy one --
    # corrected 2026-08-31 against the producer rather than against intuition.
    # tg_digest_flush.py claims the spool by RENAMING pending.jsonl to
    # .flushing-<pid>.jsonl (line 68), archives it, unlinks the claim, and only
    # recreates pending.jsonl if the send FAILED (_restore, line 81). So on a
    # machine whose digest is delivering, no pending.jsonl exists between
    # flushes: absence means DRAINED, which is strictly stronger than "zero
    # lines". Reading it as unmeasurable made the probe red in exactly the
    # healthy case -- an alarm that is wrong when nothing is wrong teaches its
    # reader to skip the line.
    script = (
        f'P={SPOOL}; '
        # The spool DIRECTORY is what must exist to measure anything. Its absence
        # is unmeasurable; the absence of a file inside it is a state.
        'if [ ! -d "$P" ]; then printf "spool_dir MISSING\\n"; exit 0; fi; '
        'printf "spool_dir OK\\n"; '
        'if [ -f "$P/pending.jsonl" ]; then '
        'printf "pending %s\\n" "$(wc -l < "$P/pending.jsonl")"; '
        'else printf "pending DRAINED\\n"; fi; '
        'if [ -f "$P/last_flush.json" ]; then '
        'printf "last_flush %s\\n" "$(cat "$P/last_flush.json")"; '
        'else printf "last_flush MISSING\\n"; fi; '
        'if [ -f "$P/archive-p0.jsonl" ]; then '
        f'printf "p0_today %s\\n" "$(grep -c "{today}" "$P/archive-p0.jsonl" || true)"; '
        'else printf "p0_today MISSING\\n"; fi'
    )
    # One measurement, two transports: the script above is the single source of
    # truth for WHAT is counted; this only chooses HOW to reach it. Naming the
    # transport in the output is part of the measurement -- a reader must never
    # have to guess which machine a number came from.
    is_local, why = _spool_is_this_machine(SSH_HOST)
    if is_local:
        argv, source = ["/bin/sh", "-c", script], f"local ({why})"
    else:
        argv, source = ["ssh", "-o", "ConnectTimeout=8", SSH_HOST, script], f"ssh {SSH_HOST} ({why})"
    print(f"  source: {source}")
    rc, out, err = _run(argv, timeout=25)
    if rc != 0:
        _cannot_verify("P0 spool", f"{source} failed rc={rc}: {err.strip()[:160]}")
        return
    fields = dict(
        line.split(None, 1) for line in out.splitlines() if " " in line
    )
    if fields.get("spool_dir", "MISSING").strip() != "OK":
        _cannot_verify("P0 spool", f"spool directory {SPOOL} does not exist on the measured host")
        return
    pending = fields.get("pending", "MISSING").strip()
    pending_drained = pending == "DRAINED"
    if pending_drained:
        pending = "0"
    p0_today = fields.get("p0_today", "MISSING").strip()
    last_flush_raw = fields.get("last_flush", "MISSING").strip()
    if not pending.isdigit() or not p0_today.isdigit() or last_flush_raw == "MISSING":
        invalid = [
            name
            for name, value in (
                ("pending", pending),
                ("last_flush", last_flush_raw),
                ("p0_today", p0_today),
            )
            if value == "MISSING" or (name != "last_flush" and not value.isdigit())
        ]
        _cannot_verify("P0 spool", f"missing or invalid counters: {', '.join(invalid)}")
        return
    try:
        last_flush = json.loads(last_flush_raw)
        last_flush_ts = float(last_flush["ts"])
        if not math.isfinite(last_flush_ts) or last_flush_ts <= 0:
            raise ValueError("ts must be a positive finite epoch")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        _cannot_verify("P0 spool", f"invalid last_flush metadata: {type(exc).__name__}")
        return
    age_min = max(0.0, (time.time() - last_flush_ts) / 60)
    if pending_drained:
        print("  pending (waiting for digest flush): 0 — DRAINED (no pending.jsonl; the")
        print("    flusher renames it away on success and recreates it only if a send fails)")
    else:
        print(f"  pending (waiting for digest flush): {pending}")
    print(f"  last flush age: {age_min:.0f} min")
    print(f"  P0 archived today: {p0_today}")
    if int(pending) > 50:
        print("  ATTENTION: pending should DRAIN at each flush — a growing file means the")
        print("  digest sender is failing (its _restore_pending() re-queues on failure).")


def main() -> int:
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"queue_doctor — {stamp} — repo {REPO} — snapshot, not a monitor")
    print()
    probe_merge_queue()
    print()
    probe_prepush_lock()
    print()
    probe_p0_spool()
    print()
    if CANNOT_VERIFY:
        print("verdict: INCOMPLETE — one or more queues unmeasured (exit 4)")
        return 4
    print("verdict: all three queues measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())

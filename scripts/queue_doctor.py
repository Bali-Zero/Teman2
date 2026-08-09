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
  QUEUE_DOCTOR_SSH    default "pro" (ssh alias for the spool host; "" = skip)
  QUEUE_DOCTOR_SPOOL  default "~/.organism/tg_spool" (path on the spool host)
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys

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
    except OSError:
        pass
    age_min = -1.0
    try:
        age_min = (
            _dt.datetime.now() - _dt.datetime.fromtimestamp(os.stat(LOCK).st_mtime)
        ).total_seconds() / 60
    except OSError:
        pass
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


def probe_p0_spool() -> None:
    print(f"== 3. P0 SPOOL ({SSH_HOST}:{SPOOL}) ==")
    if not SSH_HOST:
        _cannot_verify("P0 spool", "QUEUE_DOCTOR_SSH is empty — spool host not probed")
        return
    today = _dt.date.today().isoformat()
    # counts only: wc/grep -c on the spool host; no message body crosses the wire.
    script = (
        f'P={SPOOL}; '
        f'printf "pending %s\\n" "$(wc -l < "$P/pending.jsonl" 2>/dev/null || echo MISSING)"; '
        f'printf "last_flush %s\\n" "$(cat "$P/last_flush.json" 2>/dev/null || echo MISSING)"; '
        f'printf "p0_today %s\\n" "$(grep -c "{today}" "$P/archive-p0.jsonl" 2>/dev/null || echo 0)"'
    )
    rc, out, err = _run(["ssh", "-o", "ConnectTimeout=8", SSH_HOST, script], timeout=25)
    if rc != 0:
        _cannot_verify("P0 spool", f"ssh {SSH_HOST} failed rc={rc}: {err.strip()[:160]}")
        return
    fields = dict(
        line.split(None, 1) for line in out.splitlines() if " " in line
    )
    pending = fields.get("pending", "MISSING").strip()
    print(f"  pending (waiting for digest flush): {pending}")
    print(f"  last flush: {fields.get('last_flush', 'MISSING').strip()[:120]}")
    print(f"  P0 archived today: {fields.get('p0_today', '?').strip()}")
    if pending.isdigit() and int(pending) > 50:
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

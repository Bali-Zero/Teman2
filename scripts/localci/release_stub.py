#!/usr/bin/env python3
"""Inert release stub — journals a PROPOSED release, never executes one.

This module itself imports no process-spawning module and calls no deploy, publish or merge tool: the only
thing it writes is `state/release_journal.jsonl` (the runner's read-only git/pip probes for `status` aside). A candidate is ALLOW_PROPOSED only when the runner's
overall verdict is exactly PASS (SUBSET_PASS, BLOCKED, FAIL, STALE, INTERRUPTED are all DENY),
the independent review is PASS, the worktree still matches the bound identity, and no earlier
ALLOW_PROPOSED row carries the same idempotency key (candidate_sha, tree_sha, artifact_digest|"none").

WHAT THE LOCK GUARANTEES — and what it does not.
`state/release.lock` is an exclusive flock. That is a SINGLE-HOST mutual exclusion between processes
on one machine. It is NOT a distributed fence and NOT an ownership guarantee: two hosts, or two
run dirs on different filesystems, each hold their own lock and can both ALLOW. Fencing across hosts
would come from scripts/agent_lease.py — Redis SET-NX leases with a token-owned release — which this
stub deliberately does not depend on. The owner {hostname, pid, token} is recorded so a human or a
reconciler can see who decided; it is evidence, not enforcement.

DELIVERY SEMANTICS. A real releaser would journal, then act. An interruption between the journal
write and the side effect leaves an ALLOW_PROPOSED row with no outcome: delivery is AT-LEAST-ONCE
and requires an idempotent side effect plus reconciliation — never exactly-once. `reconcile` lists
the ALLOW_PROPOSED rows lacking a later ACKED row; an ack is recorded only by an explicit
`reconcile --ack <request>` call made after the outcome was observed.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path

try:
    from . import runner
except ImportError:  # executed as a script: sys.path[0] is this directory
    import runner  # type: ignore[no-redef]

SECRET_ENV = ("FLY_API_TOKEN", "VERCEL_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Locked:
    """Exclusive flock on state/release.lock + owner record. Single-host only (see module docstring)."""

    def __init__(self, run_dir: Path):
        (run_dir / "state").mkdir(parents=True, exist_ok=True)
        self.path = run_dir / "state" / "release.lock"
        self.owner = {"hostname": platform.node(), "pid": os.getpid(), "token": uuid.uuid4().hex}
        self.waited = 0.0
        self.fd = -1

    def __enter__(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)  # no O_TRUNC: a waiter must not wipe the holder's record
        t0 = time.monotonic()
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.waited = round(time.monotonic() - t0, 3)
        os.ftruncate(self.fd, 0)
        os.write(self.fd, json.dumps(self.owner).encode())
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def read_journal(run_dir: Path) -> tuple[list[dict], int]:
    jp = run_dir / "state" / "release_journal.jsonl"
    rows, corrupt = [], 0
    if jp.exists():
        for line in jp.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                corrupt += 1  # a torn append is reported, never silently ignored
    return rows, corrupt


def append(run_dir: Path, rec: dict) -> None:
    with open(run_dir / "state" / "release_journal.jsonl", "a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def idempotency_key(candidate_sha: str, tree_sha: str, artifact_digest: str | None) -> str:
    return f"{candidate_sha}:{tree_sha}:{artifact_digest or 'none'}"


def propose(run_dir: Path, request: str, candidate: str, artifact_digest: str | None = None, hold_s: float = 0.0) -> dict:
    run_dir = Path(run_dir).resolve()
    for k in SECRET_ENV:
        if os.environ.get(k):
            sys.exit(f"refusing to run with {k} present in env — release credentials stay outside the gate")
    with Locked(run_dir) as lk:
        status = runner.compute_status(run_dir)
        fresh = status["freshness"]["worktree_now"]
        reasons = []
        if candidate != status["candidate_sha"]:
            reasons.append(f"requested {candidate[:12]} != bound candidate {status['candidate_sha'][:12]}")
        if fresh["candidate_sha"] != status["candidate_sha"] or fresh["tree_sha"] != status["tree_sha"] or fresh["dirty"]:
            reasons.append("worktree no longer matches bound candidate (stale)")
        if status["overall"] != "PASS":
            extra = " (all executed checks are green but the required set is not fully covered — not PASS)" if status["overall"] == "SUBSET_PASS" else ""
            reasons.append(f"overall={status['overall']}{extra}")
        bad = {n: v["status"] for n, v in status["checks"].items() if v["status"] not in ("PASS", "NOT_APPLICABLE")}
        if bad:
            reasons.append(f"non-green checks: {bad}")
        if status["checks"].get("review.independent", {}).get("status") != "PASS":
            reasons.append("independent review not PASS")
        key = idempotency_key(status["candidate_sha"], status["tree_sha"], artifact_digest)
        rows, corrupt = read_journal(run_dir)
        for j in rows:
            if j.get("verdict") == "ALLOW_PROPOSED" and j.get("idempotency_key") == key:
                reasons.append(f"duplicate: key already proposed by request {j['request']} at {j['at']}")
                break
        time.sleep(hold_s)
        rec = {"at": now(), "request": request, "owner": lk.owner, "lock_wait_s": lk.waited, "requested_candidate": candidate,
               "bound_candidate": status["candidate_sha"], "tree_sha": status["tree_sha"], "artifact_digest": artifact_digest or "none",
               "idempotency_key": key, "plan_hash": status["plan_hash"], "overall": status["overall"], "corrupt_journal_lines": corrupt,
               "verdict": "ALLOW_PROPOSED" if not reasons else "DENY", "reasons": reasons,
               "proposed_action": {"kind": "INERT_STUB", "would": "release the artifact for the bound candidate (owner-only, not wired)", "executed": False}}
        append(run_dir, rec)
        return rec


def pending(run_dir: Path) -> tuple[list[dict], int]:
    """ALLOW_PROPOSED rows with no later ACKED row for the same request."""
    rows, corrupt = read_journal(run_dir)
    open_: dict[str, dict] = {}
    for j in rows:
        if j.get("verdict") == "ALLOW_PROPOSED":
            open_[j["request"]] = j
        elif j.get("verdict") == "ACKED":
            open_.pop(j.get("request"), None)
    return list(open_.values()), corrupt


def ack(run_dir: Path, request: str, note: str = "") -> dict:
    run_dir = Path(run_dir).resolve()
    with Locked(run_dir) as lk:
        open_, _ = pending(run_dir)
        if request not in {j["request"] for j in open_}:
            sys.exit(f"nothing to ack: no un-acked ALLOW_PROPOSED row for request {request!r}")
        rec = {"at": now(), "request": request, "owner": lk.owner, "verdict": "ACKED", "note": note}
        append(run_dir, rec)
        return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="release_stub")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--artifact-digest")
    p.add_argument("--hold-s", type=float, default=0.0)
    r = sub.add_parser("reconcile")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--ack", metavar="REQUEST")
    r.add_argument("--note", default="")
    r.add_argument("--strict", action="store_true", help="exit 1 when un-acked proposals remain")
    a = ap.parse_args(argv)
    if a.cmd == "propose":
        rec = propose(Path(a.run_dir), a.request, a.candidate, a.artifact_digest, a.hold_s)
        print(json.dumps(rec))
        return 0 if rec["verdict"] == "ALLOW_PROPOSED" else 2
    if a.ack:
        print(json.dumps(ack(Path(a.run_dir), a.ack, a.note)))
    open_, corrupt = pending(Path(a.run_dir).resolve())
    print(json.dumps({"unacked": [{k: j[k] for k in ("request", "at", "idempotency_key")} for j in open_], "corrupt_journal_lines": corrupt}, indent=1))
    return 1 if (a.strict and open_) else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Redis Lease Registry for multi-agent file coordination (SOTA wave 2026-05-24).

Closes the cicatrix family W40/W50/W51/W52 (Session-A vs Session-B concurrent
mutations of shared LaunchAgent wrappers, migration_v2 SQL files, and other
hot-zone paths). Provides atomic SET-NX leases with TTL + heartbeat extension
+ token-owned release, backed by Redis.

CLI:
    agent-lease acquire <RESOURCE> --task-id <ID> [--ttl-s 300] [--lane <LANE>]
    agent-lease release <RESOURCE> --task-id <ID>
    agent-lease heartbeat <RESOURCE> --task-id <ID> [--extend-s 300]
    agent-lease list [--lane <LANE>] [--json]
    agent-lease check <PATH>           # exit 0 if free or owned by $TASK_ID,
                                       # exit 1 if claimed by another task

Redis key:  agent_lock:<resource>
Value:      JSON {task_id, host, pid, lane, created_at, ttl_s}

Connection: env REDIS_HOST (default 127.0.0.1) + REDIS_PORT (default 6379).
            Tailscale Mini: REDIS_HOST=100.93.236.6.

Audit trail: every acquire / release / heartbeat / expired-detection appends
one JSON line to ~/.agent/leases.jsonl with timestamp.

Graceful degradation: any Redis error from `check` returns exit 0 + WARN log,
so the pre-commit hook stays a tooling concern, never a Redis-outage gate.
Kill-switch env: AGENT_LEASE_ENFORCEMENT=false → check always exits 0.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover — soft fail for envs without redis-py
    redis = None  # type: ignore


__all__ = [
    "AgentLease",
    "LeaseInfo",
    "LeaseAlreadyHeld",
    "LeaseNotOwned",
    "RedisUnavailable",
    "build_key",
    "AUDIT_PATH",
    "main",
]


LOG = logging.getLogger("agent_lease")
if not LOG.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    LOG.addHandler(_h)
    LOG.setLevel(os.environ.get("AGENT_LEASE_LOG_LEVEL", "INFO"))

AUDIT_PATH = Path(os.path.expanduser("~/.agent/leases.jsonl"))
KEY_PREFIX = "agent_lock:"
DEFAULT_TTL_S = 300
DEFAULT_LANE = "default"


# ── Exceptions ────────────────────────────────────────────────────────────────

class RedisUnavailable(RuntimeError):
    """Redis connection failed (down, network, missing client lib)."""


class LeaseAlreadyHeld(RuntimeError):
    """SET NX failed — another task holds the lease."""

    def __init__(self, resource: str, holder: "LeaseInfo"):
        super().__init__(f"resource '{resource}' is held by task_id={holder.task_id} (host={holder.host}, pid={holder.pid}, lane={holder.lane})")
        self.resource = resource
        self.holder = holder


class LeaseNotOwned(RuntimeError):
    """release/heartbeat called by a task_id that doesn't match the holder."""


# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class LeaseInfo:
    task_id: str
    host: str
    pid: int
    lane: str
    created_at: float
    ttl_s: int
    resource: str = ""

    def to_json(self) -> str:
        d = {
            "task_id": self.task_id,
            "host": self.host,
            "pid": self.pid,
            "lane": self.lane,
            "created_at": self.created_at,
            "ttl_s": self.ttl_s,
        }
        return json.dumps(d, separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_json(cls, raw: str, resource: str = "") -> "LeaseInfo":
        d = json.loads(raw)
        return cls(
            task_id=str(d["task_id"]),
            host=str(d.get("host", "")),
            pid=int(d.get("pid", 0)),
            lane=str(d.get("lane", DEFAULT_LANE)),
            created_at=float(d.get("created_at", 0.0)),
            ttl_s=int(d.get("ttl_s", DEFAULT_TTL_S)),
            resource=resource,
        )


# Atomicity for release/heartbeat uses WATCH/MULTI/EXEC (optimistic locking).
# We deliberately avoid Lua EVAL so the same code path works against:
#   - real Redis (full Lua support)
#   - fakeredis (limited / no Lua support depending on version)
#   - Redis clusters with EVAL restrictions
#
# Sentinel return values from _tx_release / _tx_heartbeat:
#   1  → committed (release deleted / heartbeat extended)
#   0  → key missing (noop)
#  -2  → key held by another task (denied)
#  -3  → corrupted JSON value (treat as denied)


# ── Core API ──────────────────────────────────────────────────────────────────

def build_key(resource: str) -> str:
    """Map a resource string to its Redis lock key. Idempotent."""
    if not resource:
        raise ValueError("resource must be non-empty")
    if resource.startswith(KEY_PREFIX):
        return resource
    return f"{KEY_PREFIX}{resource}"


def _audit(event: str, **fields) -> None:
    """Append one JSON line to ~/.agent/leases.jsonl. Best-effort, never raises."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.time(), "event": event, **fields}
        with AUDIT_PATH.open("a") as f:
            f.write(json.dumps(rec, separators=(",", ":"), sort_keys=True) + "\n")
    except Exception as e:  # pragma: no cover
        LOG.debug("audit write failed: %s", e)


class AgentLease:
    """Thin wrapper around redis.Redis exposing the lease primitives."""

    def __init__(self, client: Optional["redis.Redis"] = None) -> None:
        if client is not None:
            self._r = client
            return
        if redis is None:
            raise RedisUnavailable("redis-py not installed")
        host = os.environ.get("REDIS_HOST", "127.0.0.1")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        db = int(os.environ.get("REDIS_DB", "0"))
        password = os.environ.get("REDIS_PASSWORD") or None
        try:
            self._r = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
                decode_responses=True,
            )
            self._r.ping()
        except Exception as e:  # connection or auth
            raise RedisUnavailable(f"redis@{host}:{port}/{db} unreachable: {e}") from e

    # ─── primitives ─────────────────────────────────────────────────────────

    def acquire(
        self,
        resource: str,
        task_id: str,
        ttl_s: int = DEFAULT_TTL_S,
        lane: str = DEFAULT_LANE,
    ) -> LeaseInfo:
        """SET NX EX. Re-entrant for same task_id (refreshes TTL).

        Raises LeaseAlreadyHeld if another task holds it.
        """
        if not task_id:
            raise ValueError("task_id required")
        if ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")
        key = build_key(resource)
        info = LeaseInfo(
            task_id=task_id,
            host=socket.gethostname(),
            pid=os.getpid(),
            lane=lane,
            created_at=time.time(),
            ttl_s=ttl_s,
            resource=resource,
        )
        payload = info.to_json()
        # SET NX EX — atomic claim
        ok = self._r.set(key, payload, nx=True, ex=ttl_s)
        if ok:
            _audit("acquire", resource=resource, task_id=task_id, lane=lane, ttl_s=ttl_s)
            return info
        # Already held — check if it's us (re-entrant) or someone else
        cur_raw = self._r.get(key)
        if cur_raw is None:
            # Race: expired between SET NX and GET. Retry once.
            ok = self._r.set(key, payload, nx=True, ex=ttl_s)
            if ok:
                _audit("acquire", resource=resource, task_id=task_id, lane=lane, ttl_s=ttl_s, note="race-retry")
                return info
            cur_raw = self._r.get(key)
            if cur_raw is None:
                raise RedisUnavailable("unstable lease state — could not acquire or read holder")
        holder = LeaseInfo.from_json(cur_raw, resource=resource)
        if holder.task_id == task_id:
            # Re-entrant: refresh TTL (use heartbeat semantics)
            self._r.expire(key, ttl_s)
            _audit("acquire-reentrant", resource=resource, task_id=task_id, lane=lane, ttl_s=ttl_s)
            return holder
        raise LeaseAlreadyHeld(resource, holder)

    def _tx_apply(self, key: str, task_id: str, action: str, extend_s: int = 0) -> tuple[int, Optional[str]]:
        """WATCH/MULTI/EXEC for token-owned mutation.

        action: 'release' → DEL on match; 'heartbeat' → EXPIRE on match.
        Returns (sentinel, holder_raw_or_None). sentinel ∈ {1, 0, -2, -3}.
        Retries up to 3 times on WatchError (concurrent modification).
        """
        attempts = 0
        last_holder_raw: Optional[str] = None
        while attempts < 3:
            attempts += 1
            try:
                with self._r.pipeline() as pipe:
                    try:
                        pipe.watch(key)
                    except Exception:  # pragma: no cover — connection-level
                        raise
                    cur_raw = pipe.get(key)
                    if cur_raw is None:
                        pipe.unwatch()
                        return (0, None)
                    last_holder_raw = cur_raw
                    try:
                        data = json.loads(cur_raw)
                    except Exception:
                        pipe.unwatch()
                        return (-3, cur_raw)
                    if data.get("task_id") != task_id:
                        pipe.unwatch()
                        return (-2, cur_raw)
                    # Match → commit
                    pipe.multi()
                    if action == "release":
                        pipe.delete(key)
                    elif action == "heartbeat":
                        pipe.expire(key, extend_s)
                    else:  # pragma: no cover
                        raise ValueError(f"unknown action {action}")
                    pipe.execute()
                    return (1, cur_raw)
            except Exception as e:
                # redis.exceptions.WatchError raised when key changed mid-tx
                name = type(e).__name__
                if name == "WatchError":
                    continue
                raise
        # 3 retries exhausted; fall back to denied-by-race
        return (-2, last_holder_raw)

    def release(self, resource: str, task_id: str) -> bool:
        """DEL only if the holder's task_id matches. Returns True on delete."""
        if not task_id:
            raise ValueError("task_id required")
        key = build_key(resource)
        result, cur_raw = self._tx_apply(key, task_id, action="release")
        if result == 1:
            _audit("release", resource=resource, task_id=task_id)
            return True
        if result == 0:
            _audit("release-noop", resource=resource, task_id=task_id, note="key-missing")
            return False
        if result in (-2, -3):
            holder = None
            if cur_raw:
                try:
                    holder = LeaseInfo.from_json(cur_raw, resource=resource)
                except Exception:
                    holder = None
            _audit("release-denied", resource=resource, task_id=task_id, holder=holder.task_id if holder else None)
            raise LeaseNotOwned(
                f"release denied: '{resource}' held by {holder.task_id if holder else '?'}, not {task_id}"
            )
        raise RedisUnavailable(f"release tx returned unknown sentinel {result}")

    def heartbeat(self, resource: str, task_id: str, extend_s: int = DEFAULT_TTL_S) -> bool:
        """Extend TTL only if our task_id matches. Returns True on extension."""
        if not task_id:
            raise ValueError("task_id required")
        if extend_s <= 0:
            raise ValueError("extend_s must be > 0")
        key = build_key(resource)
        result, cur_raw = self._tx_apply(key, task_id, action="heartbeat", extend_s=extend_s)
        if result == 1:
            _audit("heartbeat", resource=resource, task_id=task_id, extend_s=extend_s)
            return True
        if result == 0:
            _audit("heartbeat-noop", resource=resource, task_id=task_id, note="key-missing")
            return False
        if result in (-2, -3):
            holder = None
            if cur_raw:
                try:
                    holder = LeaseInfo.from_json(cur_raw, resource=resource)
                except Exception:
                    holder = None
            _audit("heartbeat-denied", resource=resource, task_id=task_id, holder=holder.task_id if holder else None)
            raise LeaseNotOwned(
                f"heartbeat denied: '{resource}' held by {holder.task_id if holder else '?'}, not {task_id}"
            )
        raise RedisUnavailable(f"heartbeat tx returned unknown sentinel {result}")

    def get(self, resource: str) -> Optional[LeaseInfo]:
        """Return the current holder, or None if free / expired."""
        key = build_key(resource)
        raw = self._r.get(key)
        if raw is None:
            return None
        try:
            return LeaseInfo.from_json(raw, resource=resource)
        except Exception as e:
            LOG.warning("corrupted lease at %s: %s", key, e)
            return None

    def list(self, lane: Optional[str] = None) -> list[LeaseInfo]:
        """SCAN all agent_lock:* keys; optionally filter by lane."""
        out: list[LeaseInfo] = []
        cursor = 0
        pattern = f"{KEY_PREFIX}*"
        while True:
            cursor, keys = self._r.scan(cursor=cursor, match=pattern, count=256)
            for key in keys:
                raw = self._r.get(key)
                if raw is None:
                    continue
                try:
                    resource = key[len(KEY_PREFIX):] if key.startswith(KEY_PREFIX) else key
                    info = LeaseInfo.from_json(raw, resource=resource)
                    if lane is not None and info.lane != lane:
                        continue
                    # also surface remaining TTL
                    ttl = self._r.ttl(key)
                    info.ttl_s = int(ttl) if ttl and ttl > 0 else 0
                    out.append(info)
                except Exception as e:
                    LOG.warning("skip corrupted lease %s: %s", key, e)
            if cursor == 0:
                break
        return out

    def check_path(self, path: str, our_task_id: Optional[str] = None) -> tuple[bool, Optional[LeaseInfo]]:
        """Return (is_blocking, holder_if_any).

        Blocking iff a holder exists AND holder.task_id != our_task_id.
        """
        info = self.get(path)
        if info is None:
            return (False, None)
        if our_task_id and info.task_id == our_task_id:
            return (False, info)
        return (True, info)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_holder(info: LeaseInfo, prefix: str = "") -> None:
    age = max(0, int(time.time() - info.created_at))
    print(
        f"{prefix}resource={info.resource} task_id={info.task_id} "
        f"host={info.host} pid={info.pid} lane={info.lane} "
        f"age={age}s ttl_remaining={info.ttl_s}s",
        file=sys.stderr,
    )


def _cmd_acquire(args, lease: AgentLease) -> int:
    try:
        info = lease.acquire(args.resource, task_id=args.task_id, ttl_s=args.ttl_s, lane=args.lane)
    except LeaseAlreadyHeld as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        _print_holder(e.holder, prefix="  holder: ")
        return 1
    print(info.to_json())
    return 0


def _cmd_release(args, lease: AgentLease) -> int:
    try:
        ok = lease.release(args.resource, task_id=args.task_id)
    except LeaseNotOwned as e:
        print(f"DENIED: {e}", file=sys.stderr)
        return 2
    print("released" if ok else "noop")
    return 0


def _cmd_heartbeat(args, lease: AgentLease) -> int:
    try:
        ok = lease.heartbeat(args.resource, task_id=args.task_id, extend_s=args.extend_s)
    except LeaseNotOwned as e:
        print(f"DENIED: {e}", file=sys.stderr)
        return 2
    print("extended" if ok else "noop")
    return 0


def _cmd_list(args, lease: AgentLease) -> int:
    items = lease.list(lane=args.lane)
    if args.json:
        out = [
            {
                "resource": i.resource,
                "task_id": i.task_id,
                "host": i.host,
                "pid": i.pid,
                "lane": i.lane,
                "created_at": i.created_at,
                "ttl_remaining_s": i.ttl_s,
            }
            for i in items
        ]
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        if not items:
            print("(no active leases)")
            return 0
        for i in items:
            print(
                f"{i.resource}\ttask={i.task_id}\thost={i.host}\tpid={i.pid}\t"
                f"lane={i.lane}\tttl={i.ttl_s}s"
            )
    return 0


def _cmd_check(args) -> int:
    """check is the hot-path called from the pre-commit hook.

    Graceful degradation: Redis down → exit 0 + WARN log. Otherwise the
    pre-commit hook would become a hard dependency on Redis availability,
    which violates the brief's HARD constraint.

    Kill switch: AGENT_LEASE_ENFORCEMENT=false → exit 0 always.
    """
    enforcement = os.environ.get("AGENT_LEASE_ENFORCEMENT", "true").strip().lower()
    if enforcement in ("false", "0", "no", "off", "disabled"):
        # Kill switch active — never block
        return 0

    our_task_id = os.environ.get("TASK_ID") or os.environ.get("AGENT_TASK_ID")

    try:
        lease = AgentLease()
    except RedisUnavailable as e:
        LOG.warning("Redis unavailable — passing through (no enforcement): %s", e)
        return 0
    try:
        blocking, holder = lease.check_path(args.path, our_task_id=our_task_id)
    except Exception as e:
        LOG.warning("lease check error — passing through: %s", e)
        return 0
    if not blocking:
        return 0
    assert holder is not None
    print(
        f"BLOCKED: path '{args.path}' is leased by another task",
        file=sys.stderr,
    )
    _print_holder(holder, prefix="  holder: ")
    if our_task_id:
        print(f"  our task_id: {our_task_id}", file=sys.stderr)
    else:
        print(
            "  (no TASK_ID env set — pass TASK_ID=<id> if this is your own lease)",
            file=sys.stderr,
        )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent-lease", description="Redis lease registry for multi-agent file coordination.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("acquire", help="Acquire a lease on a resource")
    pa.add_argument("resource")
    pa.add_argument("--task-id", required=True)
    pa.add_argument("--ttl-s", type=int, default=DEFAULT_TTL_S)
    pa.add_argument("--lane", default=DEFAULT_LANE)

    pr = sub.add_parser("release", help="Release a lease owned by --task-id")
    pr.add_argument("resource")
    pr.add_argument("--task-id", required=True)

    ph = sub.add_parser("heartbeat", help="Extend TTL for a lease owned by --task-id")
    ph.add_argument("resource")
    ph.add_argument("--task-id", required=True)
    ph.add_argument("--extend-s", type=int, default=DEFAULT_TTL_S)

    pl = sub.add_parser("list", help="List active leases")
    pl.add_argument("--lane", default=None)
    pl.add_argument("--json", action="store_true")

    pc = sub.add_parser("check", help="Check if a path is free (exit 0) or claimed by another task (exit 1)")
    pc.add_argument("path")

    return p


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "check":
        # check has its own graceful-degradation policy
        return _cmd_check(args)

    try:
        lease = AgentLease()
    except RedisUnavailable as e:
        print(f"ERROR: Redis unavailable: {e}", file=sys.stderr)
        return 3

    if args.cmd == "acquire":
        return _cmd_acquire(args, lease)
    if args.cmd == "release":
        return _cmd_release(args, lease)
    if args.cmd == "heartbeat":
        return _cmd_heartbeat(args, lease)
    if args.cmd == "list":
        return _cmd_list(args, lease)
    parser.error(f"unknown command: {args.cmd}")
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())

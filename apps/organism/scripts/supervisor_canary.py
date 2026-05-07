"""W2 dispatch canary — emits a synthetic event, verifies decision logged.

Usage:
    cd apps/organism
    PYTHONPATH=. python scripts/supervisor_canary.py \\
        [--mode shadow|active] [--actuator restart_agent|cleanup_log|...] \\
        [--target NAME]

What it does:
    1. Emits a synthetic event onto `organism:events` Redis stream that the
       L0 YAML rules will match (default: scheduled_tick at 03:00 → cleanup_log).
    2. Polls ~/logs/organism/decisions.jsonl for a new entry matching the
       canary correlation_id (timeout 30s).
    3. In active mode: also tails ~/logs/organism/wal/ for an actuator WAL
       entry as proof the actuator was actually invoked.

Exit code 0 on success, 1 on timeout or assertion failure. Designed for
manual invocation pre-flag-flip and as a precondition gate in the canary
runbook.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import redis.asyncio as redis_async

from organism.schemas import Event, Severity


DECISIONS_LOG = Path.home() / "logs" / "organism" / "decisions.jsonl"
WAL_DIR = Path.home() / "logs" / "organism" / "wal"
STREAM_KEY = "organism:events"
TIMEOUT_S = 30


async def _emit_synthetic_event(*, kind: str, payload: dict, correlation_id: str) -> None:
    r = redis_async.from_url("redis://127.0.0.1:6379/0")
    e = Event(
        severity=Severity.INFO,
        source="canary.supervisor",
        kind=kind,
        payload=payload,
        correlation_id=correlation_id,
        host="Pro",
    )
    await r.xadd(STREAM_KEY, {"data": e.model_dump_json()})
    await r.aclose()


def _wait_for_decision(correlation_id: str, *, deadline: float) -> dict | None:
    """Tail decisions.jsonl until we see correlation_id or timeout."""
    if not DECISIONS_LOG.exists():
        return None
    start_size = DECISIONS_LOG.stat().st_size
    while time.time() < deadline:
        try:
            with DECISIONS_LOG.open() as f:
                f.seek(max(0, start_size - 4096))  # back up a tiny bit in case the line landed before our snapshot
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("correlation_id") == correlation_id:
                        return entry
        except OSError:
            pass
        time.sleep(0.5)
    return None


def _wait_for_wal(actuator: str, *, since: float, deadline: float) -> Path | None:
    """Find a WAL entry written for actuator after `since`."""
    while time.time() < deadline:
        if WAL_DIR.exists():
            for p in WAL_DIR.glob(f"{actuator}-*.json"):
                try:
                    if p.stat().st_mtime >= since:
                        return p
                except FileNotFoundError:
                    continue
        time.sleep(0.5)
    return None


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["shadow", "active"], default="shadow")
    parser.add_argument("--kind", default="scheduled_tick")
    parser.add_argument("--actuator", default="cleanup_log",
                        help="actuator to expect in the decision (matches L0 YAML rule)")
    parser.add_argument("--payload", default='{"hour": 3}',
                        help="JSON event payload that triggers the rule")
    args = parser.parse_args()

    correlation_id = f"canary-{uuid.uuid4()}"
    payload = json.loads(args.payload)

    print(f"[canary] mode={args.mode} corr={correlation_id} kind={args.kind} payload={payload}")
    started = time.time()
    await _emit_synthetic_event(
        kind=args.kind, payload=payload, correlation_id=correlation_id,
    )
    print(f"[canary] emitted synthetic event at {started:.3f}, waiting up to {TIMEOUT_S}s for decision …")

    deadline = started + TIMEOUT_S
    entry = _wait_for_decision(correlation_id, deadline=deadline)
    if entry is None:
        print("[canary] FAIL: no decision logged within timeout", file=sys.stderr)
        return 1

    print(f"[canary] decision: {json.dumps(entry, indent=2)}")
    if entry["actuator"] != args.actuator:
        print(
            f"[canary] FAIL: expected actuator={args.actuator}, got {entry['actuator']}",
            file=sys.stderr,
        )
        return 1

    expected_outcome = "shadow_logged" if args.mode == "shadow" else "dispatched"
    if entry.get("dispatch_outcome") != expected_outcome:
        print(
            f"[canary] FAIL: expected dispatch_outcome={expected_outcome}, got {entry.get('dispatch_outcome')}",
            file=sys.stderr,
        )
        return 1

    if args.mode == "active":
        print("[canary] looking for WAL entry to confirm actuator invocation …")
        wal = _wait_for_wal(args.actuator, since=started, deadline=deadline)
        if wal is None:
            print("[canary] FAIL: no WAL entry found for actuator", file=sys.stderr)
            return 1
        print(f"[canary] WAL: {wal}")

    print("[canary] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

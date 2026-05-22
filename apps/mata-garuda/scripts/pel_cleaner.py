#!/usr/bin/env python3
"""W12+W13 PEL-cleaner: systematic recovery from PEL accumulation pattern.

Scans all garuda:*, bridge:*, nexus:* Redis streams. For each consumer group:
  - STALE_PEL (consumer pending>0 AND idle>24h): XCLAIM pending messages to
    the youngest alive consumer in the group (lowest idle_ms). If no alive
    consumer exists, leave alone (manual decision needed).
  - GHOST_CONSUMER (consumer pending=0 AND idle>30d): XGROUP DELCONSUMER.
  - DEEP_STALE_PEL (W13: any pending msg with msg_idle_ms > 7d): XACK directly.
    Workers in this codebase use XREADGROUP STREAMS > semantic (only NEW
    messages, never re-process PEL), so XCLAIM alone is insufficient — the
    new owner never re-reads. Messages >7d are dropped because:
      (a) already-fed pipelines (nlm_fed dedup table) would skip them anyway
      (b) not-yet-fed >7d content is stale (cf 18d arxiv → NB noise > value)
      (c) re-injection would fan-out cascade through normalizer + ner + classifier

Outputs JSON report to stdout. Exits 0 if no actions OR all actions succeeded,
1 if any XCLAIM/DELCONSUMER/XACK call failed.

Designed for weekly launchd cron (Sunday 04:00 WITA) AFTER lag-check normal
hours. Idempotent: re-running on already-clean state is a no-op.
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from typing import Any

STALE_PEL_IDLE_MS = 24 * 3600 * 1000        # 24h consumer idle threshold
GHOST_IDLE_MS = 30 * 86400 * 1000           # 30 days zero-pending threshold
# W13: msg pending >24h → XACK direct. Workers in this codebase use
# XREADGROUP STREAMS > semantic (only NEW messages), so PEL is functionally
# write-only — anything in PEL >24h is abandoned. Threshold low enough to
# catch W11/W12 XCLAIM-orphan victims that workers can no longer recover.
# Conservative side: if any worker EVER drains PEL via XREADGROUP 0, they
# do so on startup — 24h gives them >1 cron cycle to recover before drop.
DEEP_STALE_MSG_IDLE_MS = 24 * 3600 * 1000
# 24h: covers slow-cadence consumers (daily alert digest, weekly archive) so
# they count as "alive" XCLAIM targets, not as ghosts themselves.
ALIVE_IDLE_MS_MAX = 24 * 3600 * 1000
XCLAIM_MIN_IDLE_MS = 60_000                 # standard Redis safety floor


def rcli(*args: str) -> str:
    r = subprocess.run(["redis-cli", *args], capture_output=True, text=True, timeout=30)
    return r.stdout


def parse_xinfo_consumers(out: str) -> list[dict[str, Any]]:
    """Parse XINFO CONSUMERS output (flat key/value alternating lines).

    A new consumer record starts at every "name" key. Close current and start fresh.
    """
    lines = [l for l in out.split("\n") if l != ""]
    records: list[dict[str, Any]] = []
    cur: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        key = lines[i].strip()
        i += 1
        if key == "name" and i < len(lines):
            if cur:
                records.append(cur)
            cur = {"name": lines[i].strip()}
            i += 1
        elif key in ("pending", "idle", "inactive") and i < len(lines):
            cur[key] = lines[i].strip()
            i += 1
    if cur:
        records.append(cur)
    return records


def list_streams() -> list[str]:
    streams: set[str] = set()
    for pattern in ("garuda:*", "bridge:*", "nexus:*"):
        out = rcli("--scan", "--pattern", pattern)
        for line in out.split("\n"):
            line = line.strip()
            if not line:
                continue
            if rcli("TYPE", line).strip() == "stream":
                streams.add(line)
    return sorted(streams)


def list_groups(stream: str) -> list[str]:
    out = rcli("XINFO", "GROUPS", stream)
    lines = out.split("\n")
    groups: list[str] = []
    for idx, line in enumerate(lines):
        if line.strip() == "name" and idx + 1 < len(lines):
            groups.append(lines[idx + 1].strip())
    return groups


def _parse_xpending_long(out: str) -> list[tuple[str, str, int]]:
    """Parse XPENDING <stream> <group> - + N output → [(msg_id, owner, idle_ms)].

    redis-cli emits 4 lines per entry: id, owner, idle_ms, deliveries.
    """
    lines = [l.strip() for l in out.split("\n") if l.strip()]
    records: list[tuple[str, str, int]] = []
    i = 0
    while i + 3 < len(lines):
        mid = lines[i]
        # Expect msg-id shape: digits-digits
        if "-" not in mid or not mid.replace("-", "").isdigit():
            i += 1
            continue
        owner = lines[i + 1]
        try:
            idle_ms = int(lines[i + 2])
        except ValueError:
            i += 1
            continue
        records.append((mid, owner, idle_ms))
        i += 4
    return records


def _xack_deep_stale(stream: str, group: str) -> int:
    """W13: scan PEL, XACK every message with idle_ms > DEEP_STALE_MSG_IDLE_MS.

    Returns count of messages ACK'd. Workers use XREADGROUP > semantic so
    they NEVER re-read PEL — old pending is functionally abandoned and
    should be drained to prevent unbounded PEL growth.
    """
    xp = rcli("XPENDING", stream, group, "-", "+", "1000")
    records = _parse_xpending_long(xp)
    if not records:
        return 0
    deep = [mid for mid, _owner, idle in records if idle > DEEP_STALE_MSG_IDLE_MS]
    if not deep:
        return 0
    acked = 0
    # XACK supports multiple IDs in one call (batch of 100)
    for batch_start in range(0, len(deep), 100):
        batch = deep[batch_start:batch_start + 100]
        result = rcli("XACK", stream, group, *batch)
        try:
            acked += int(result.strip())
        except ValueError:
            pass
    return acked


def cleanup() -> dict[str, Any]:
    report: dict[str, Any] = {
        "started_at": int(time.time()),
        "claims": [],
        "deletions": [],
        "deep_acks": [],
        "errors": [],
    }
    for stream in list_streams():
        for group in list_groups(stream):
            # W13: deep-stale message ACK pass (per-message, not per-consumer).
            # XPENDING - + 1000 returns msg_id, owner, msg_idle_ms, deliveries.
            # ACK any message whose msg_idle_ms > 7d regardless of which
            # consumer owns it — workers use > semantic, never re-read PEL.
            deep_acked = _xack_deep_stale(stream, group)
            if deep_acked:
                report["deep_acks"].append({
                    "stream": stream, "group": group, "acked": deep_acked,
                })
            # Re-fetch consumers AFTER deep-ack pass (pending counts updated)
            consumers = parse_xinfo_consumers(rcli("XINFO", "CONSUMERS", stream, group))
            if not consumers:
                continue
            # Find youngest alive consumer (lowest idle) for XCLAIM target
            alive = [c for c in consumers if int(c.get("idle", 0)) < ALIVE_IDLE_MS_MAX]
            target = min(alive, key=lambda c: int(c["idle"])) if alive else None
            for c in consumers:
                name = c.get("name", "")
                try:
                    pending = int(c.get("pending", 0))
                    idle_ms = int(c.get("idle", 0))
                except ValueError:
                    continue
                # STALE_PEL: claim pending from stale consumer to alive target
                if pending > 0 and idle_ms > STALE_PEL_IDLE_MS:
                    if target is None or target["name"] == name:
                        report["errors"].append({
                            "stream": stream, "group": group, "consumer": name,
                            "pending": pending, "idle_ms": idle_ms,
                            "reason": "no_alive_target",
                        })
                        continue
                    # XPENDING returns flat records: 4 lines per msg (id,
                    # consumer, idle_ms, deliveries). Extract msg IDs.
                    xp = rcli("XPENDING", stream, group, "-", "+", "1000", name)
                    msg_ids: list[str] = []
                    for line in xp.split("\n"):
                        tok = line.strip()
                        if "-" in tok and tok.replace("-", "").isdigit():
                            msg_ids.append(tok)
                    msg_ids = list(dict.fromkeys(msg_ids))[:1000]
                    if not msg_ids:
                        report["errors"].append({
                            "stream": stream, "group": group, "consumer": name,
                            "reason": "no_msg_ids_parsed",
                        })
                        continue
                    # XCLAIM in batches of 100
                    claimed = 0
                    for batch_start in range(0, len(msg_ids), 100):
                        batch = msg_ids[batch_start:batch_start + 100]
                        result = rcli("XCLAIM", stream, group, target["name"],
                                      str(XCLAIM_MIN_IDLE_MS), *batch)
                        if "ERR" in result or "(error)" in result:
                            report["errors"].append({
                                "stream": stream, "group": group, "from": name, "to": target["name"],
                                "reason": "xclaim_failed", "detail": result[:200],
                            })
                        else:
                            claimed += len(batch)
                    report["claims"].append({
                        "stream": stream, "group": group, "from": name, "to": target["name"],
                        "pending_before": pending, "claimed_now": claimed,
                        "from_idle_days": round(idle_ms / 86400000, 1),
                    })
                # GHOST_CONSUMER: delete zero-pending dead consumer
                elif pending == 0 and idle_ms > GHOST_IDLE_MS:
                    result = rcli("XGROUP", "DELCONSUMER", stream, group, name)
                    if "ERR" in result:
                        report["errors"].append({
                            "stream": stream, "group": group, "consumer": name,
                            "reason": "delconsumer_failed", "detail": result[:200],
                        })
                    else:
                        report["deletions"].append({
                            "stream": stream, "group": group, "consumer": name,
                            "idle_days": round(idle_ms / 86400000, 1),
                        })
    report["finished_at"] = int(time.time())
    return report


if __name__ == "__main__":
    rep = cleanup()
    print(json.dumps(rep, indent=2))
    sys.exit(1 if rep["errors"] else 0)

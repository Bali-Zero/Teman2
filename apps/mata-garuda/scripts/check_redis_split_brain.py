#!/usr/bin/env python3
"""W16: detect Pro<->Mini Redis split-brain on garuda streams.

After cicatrix 2026-05-06 (NLM feeder split-brain fixed via GARUDA_REDIS_HOST),
the consumer workers were pointed at Mini Redis (100.93.236.6). But empirical
state 2026-05-22 shows producers split across hosts:

- Pro Redis (127.0.0.1):  intel_scraper + ner-1 + classifier-1 writes
- Mini Redis (100.93.236.6): sentinel.daily writes (rss/arxiv)

The nlm-feeder cron reads Mini → only sees rss/arxiv items, misses
4337+ intel_scraper items accumulating on Pro Redis. Lag monitor doesn't
flag this because it only probes the single configured host.

This script:
1. Probes garuda:raw + garuda:enriched + garuda:alerts on BOTH hosts
2. Compares last-generated-id timestamps
3. Emits WARNING JSON to stderr if drift > threshold (default 1h)
4. Exits 1 if split-brain detected, 0 if both hosts in sync (or only one alive)

Designed for ad-hoc operator use or future launchd cron (W17 candidate).
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from typing import Any

PRO_HOST = "127.0.0.1"
MINI_HOST = "100.93.236.6"
STREAMS = ("garuda:raw", "garuda:enriched", "garuda:alerts")
DRIFT_THRESHOLD_MS = 3600 * 1000  # 1h


def rcli(host: str, *args: str) -> str:
    r = subprocess.run(
        ["redis-cli", "-h", host, *args],
        capture_output=True, text=True, timeout=10,
    )
    return r.stdout


def host_stream_state(host: str, stream: str) -> dict[str, Any] | None:
    """Return {length, last_id_ms} or None if unreachable / no stream."""
    out = rcli(host, "XINFO", "STREAM", stream)
    if not out or "no such key" in out.lower() or "(error)" in out.lower():
        return None
    lines = out.split("\n")
    length, last_id = None, None
    for i, l in enumerate(lines):
        key = l.strip()
        if key == "length" and i + 1 < len(lines):
            try:
                length = int(lines[i + 1].strip())
            except ValueError:
                pass
        elif key == "last-generated-id" and i + 1 < len(lines):
            last_id = lines[i + 1].strip()
    if length is None or last_id is None:
        return None
    try:
        last_id_ms = int(last_id.split("-")[0])
    except (ValueError, IndexError):
        return None
    return {"length": length, "last_id_ms": last_id_ms}


def detect_split_brain() -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    report: dict[str, Any] = {
        "checked_at_ms": now_ms,
        "streams": {},
        "alerts": [],
    }
    for stream in STREAMS:
        pro = host_stream_state(PRO_HOST, stream)
        mini = host_stream_state(MINI_HOST, stream)
        entry: dict[str, Any] = {"pro": pro, "mini": mini}
        if pro and mini:
            drift_ms = abs(pro["last_id_ms"] - mini["last_id_ms"])
            entry["drift_ms"] = drift_ms
            entry["drift_h"] = round(drift_ms / 3600000, 1)
            if drift_ms > DRIFT_THRESHOLD_MS:
                stale_host = "mini" if pro["last_id_ms"] > mini["last_id_ms"] else "pro"
                fresh_host = "pro" if stale_host == "mini" else "mini"
                report["alerts"].append({
                    "stream": stream,
                    "stale_host": stale_host,
                    "fresh_host": fresh_host,
                    "drift_h": entry["drift_h"],
                    "stale_last_id_ms": (pro if stale_host == "pro" else mini)["last_id_ms"],
                    "fresh_last_id_ms": (pro if fresh_host == "pro" else mini)["last_id_ms"],
                    "stale_length": (pro if stale_host == "pro" else mini)["length"],
                    "fresh_length": (pro if fresh_host == "pro" else mini)["length"],
                })
        report["streams"][stream] = entry
    return report


if __name__ == "__main__":
    rep = detect_split_brain()
    if rep["alerts"]:
        # Emit one JSON line per alert to stderr (matches W10 format)
        for alert in rep["alerts"]:
            line = {"level": "WARNING", "tag": "redis-split-brain", **alert}
            sys.stderr.write(json.dumps(line) + "\n")
        sys.exit(1)
    # Success: emit nothing to stderr; full report to stdout for ad-hoc inspection
    print(json.dumps(rep, indent=2))
    sys.exit(0)

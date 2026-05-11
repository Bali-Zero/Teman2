#!/usr/bin/env python3
"""Latency benchmark for mata-garuda kg-query API.

Usage:
    python scripts/bench_kg_api.py http://100.93.236.6:8990 [N=100] [path=/kg/search?q=imigrasi]
"""
from __future__ import annotations

import statistics
import sys
import time
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    base = sys.argv[1].rstrip("/")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    path = sys.argv[3] if len(sys.argv) > 3 else "/kg/search?q=imigrasi"
    url = base + path
    durations: list[float] = []
    errors = 0
    for i in range(n):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                resp.read()
                if resp.status != 200:
                    errors += 1
        except Exception:
            errors += 1
            continue
        durations.append((time.perf_counter() - t0) * 1000.0)
    durations.sort()
    if not durations:
        print(f"all {n} requests failed")
        return 1
    p50 = statistics.median(durations)
    p95 = durations[int(0.95 * len(durations)) - 1]
    p99 = durations[int(0.99 * len(durations)) - 1]
    print(f"target  : {url}")
    print(f"samples : {len(durations)}/{n} (errors={errors})")
    print(f"p50_ms  : {p50:.1f}")
    print(f"p95_ms  : {p95:.1f}")
    print(f"p99_ms  : {p99:.1f}")
    print(f"min_ms  : {min(durations):.1f}")
    print(f"max_ms  : {max(durations):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

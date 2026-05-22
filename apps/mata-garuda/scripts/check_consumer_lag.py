#!/usr/bin/env python3
"""Mata Garuda — Consumer Group Lag Monitor.

W5 cicatrix 2026-05-22: Redis consumer groups (nexus-bridge, normalizer,
classifier, kg_linker) silently fall behind without any log signal. Empirical
2026-05-22 04:55 WITA:

    garuda:raw       nexus-bridge  pending=0 lag=2279  ~4 days behind
    garuda:raw       normalizer    pending=9 lag=858   ~1.5 days behind
    garuda:enriched  classifier    pending=0 lag=1003  ~2 days behind

Cron-friendly: prints JSON line per alert to stdout, exits 0 if all groups
are healthy, exits 1 if any group exceeds threshold. Designed to wrap
inside a launchd plist so high lag escalates to launchd error log.

Environment overrides:
- LAG_THRESHOLD: default 500 entries.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.tools.health_tools import get_consumer_groups_lag


def main() -> int:
    threshold = int(os.getenv("LAG_THRESHOLD", "500"))
    alerts = get_consumer_groups_lag(lag_threshold=threshold)

    if not alerts:
        # Silent success — no need to spam log
        return 0

    # Print one JSON line per alerting group → grep-friendly
    for a in alerts:
        line = json.dumps({
            "level": "WARNING",
            "tag": "consumer-group-lag",
            "stream": a["stream"],
            "group": a["group"],
            "lag": a.get("lag"),
            "pending": a.get("pending"),
            "consumers": a.get("consumers"),
            "threshold": threshold,
        })
        # WARNING for visibility — caller (cron wrapper) directs to stderr
        print(line, file=sys.stderr)

    return 1  # Non-zero exit so launchd flags the run


if __name__ == "__main__":
    sys.exit(main())

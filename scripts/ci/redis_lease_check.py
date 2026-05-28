#!/usr/bin/env python3
"""L5.2 Phase 2a — Redis lease registry check (CI-side, best-effort).

Called from .github/workflows/hot-zone-pr-gate.yml Step 4.

Behavior:
  - Reads REDIS_URL from env (set by workflow from secrets.REDIS_URL)
  - Reads CHANGED_FILES (multi-line) from env (set from PR diff)
  - Connects to Redis with 5s timeout
  - On any connection failure → exit 0 with notice (CI runner often cannot
    reach Pro Redis per docs/runbooks/redis-lease-registry.md)
  - On success → scan `agent_lock:*` keys, intersect with CHANGED_FILES
  - Phase 2a: log conflicts as warning, still exit 0 (monitor-mode)
  - Phase 2b will flip to `sys.exit(1)` on conflict to enforce blocking

Exit codes:
  0 — no conflict OR Redis unreachable OR monitor-mode (always in Phase 2a)
  1 — reserved for Phase 2b enforce-mode conflict
  2 — internal error (e.g. missing redis pip dep)

Reference:
  - docs/runbooks/redis-lease-registry.md (lease schema)
  - cicatrix W40 / W50 / W51 / W52 (multi-agent file race family)
"""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        print("::notice::REDIS_URL unset — lease check skipped (cold)")
        return 0

    try:
        import redis  # type: ignore
    except ImportError:
        print("::warning::redis pip dep missing — skipped")
        return 0

    try:
        client = redis.Redis.from_url(
            redis_url,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        client.ping()
    except Exception as exc:  # noqa: BLE001 — broad by intent
        print(
            f"::notice::Redis unreachable from CI runner "
            f"({type(exc).__name__}): {exc}"
        )
        print(
            "::notice::Expected per docs/runbooks/redis-lease-registry.md "
            "— Phase 2a treats this as cold"
        )
        return 0

    changed_raw = os.environ.get("CHANGED_FILES", "")
    changed = [line for line in changed_raw.splitlines() if line.strip()]
    if not changed:
        print("No changed files in env — skipping intersection")
        return 0

    try:
        keys = list(client.scan_iter(match="agent_lock:*", count=100))
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::Lease scan error ({type(exc).__name__}): {exc}")
        return 0

    if not keys:
        print(f"OK: no active leases; PR touches {len(changed)} file(s)")
        return 0

    conflicts: list[dict[str, object]] = []
    for key in keys:
        resource = key.decode("utf-8", errors="replace").removeprefix(
            "agent_lock:"
        )
        for f in changed:
            if f == resource or f.startswith(resource + "/"):
                try:
                    val = client.get(key)
                    info = json.loads(val) if val else {}
                except Exception:  # noqa: BLE001
                    info = {}
                conflicts.append(
                    {
                        "file": f,
                        "leased_resource": resource,
                        "task_id": info.get("task_id"),
                        "host": info.get("host"),
                        "lane": info.get("lane"),
                    }
                )

    if not conflicts:
        print(
            f"OK: {len(keys)} active lease(s), none conflict with this PR"
        )
        return 0

    # Phase 2a monitor-mode: surface as warnings, still exit 0.
    print(f"::warning::Active lease conflicts detected ({len(conflicts)}):")
    for c in conflicts:
        print(f"  - {c}")
    print("Phase 2a monitor-mode: would block in Phase 2b")
    return 0


if __name__ == "__main__":
    sys.exit(main())

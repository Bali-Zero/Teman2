#!/usr/bin/env python3
"""Mata Garuda — Normalizer runner (Layer 2 Kognitif).

Drains garuda:raw through the normalizer worker to populate
garuda:enriched with deduplicated, schema-normalized items.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.workers.heartbeat import emit_heartbeat
from mata_garuda.workers.normalizer import run_normalizer

# Organ id matches organs_registry.yaml `mata_garuda.normalizer_hourly.mini`
# (com.matagaruda.normalizer.hourly on Mini). Wired 2026-07-07 (healer receptor
# 4, PENDING-ARMS): this cron was running fine but had never written the
# heartbeat sidecar the registry-driven receptor expects, so it was flagged
# never_armed instead of ok. See mata_garuda.workers.heartbeat for the shared
# emitter (same ~/.organism/last_seen/<organ_id>.json schema as other organs).
ORGAN_ID = "mata_garuda.normalizer_hourly.mini"


def main() -> int:
    kb = KnowledgeBase()
    total = {"processed": 0, "duplicates": 0, "published": 0, "errors": 0}

    try:
        # Drain in batches of 50; cap 1000 items/run
        for _ in range(20):
            r = run_normalizer(kb, max_items=50)
            if r.get("processed", 0) == 0:
                break
            for k in total:
                total[k] += r.get(k, 0)
    finally:
        kb.close()

    print(json.dumps({"run": total}, indent=2))

    # Heartbeat at real completion (after the drain loop finishes), status
    # derived from run stats via the shared convention (green-but-dead: read
    # a backlog but nothing progressed -> degraded, not silently ok).
    status = "fail" if total["errors"] and total["errors"] >= max(1, total["processed"]) else (
        "degraded" if total["processed"] > 0 and total["published"] == 0 and total["duplicates"] == 0
        else "ok"
    )
    emit_heartbeat(ORGAN_ID, status, metadata=total)
    return 0


def _cli_entrypoint(main_fn) -> int:
    """Run `main_fn()`, emitting a fail heartbeat only on a genuine exception.

    `except BaseException` around `sys.exit(main_fn())` used to catch our OWN
    successful SystemExit(0) and overwrite the correct heartbeat main_fn()
    just wrote with status=fail (metadata {"error": "SystemExit: 0"}), every
    run (2026-07-07). Catching `Exception` (not `BaseException`) lets
    SystemExit/KeyboardInterrupt through untouched.
    """
    try:
        return main_fn()
    except Exception as exc:  # noqa: BLE001 — heartbeat then re-raise
        emit_heartbeat(ORGAN_ID, "fail", metadata={"error": f"{type(exc).__name__}: {exc}"})
        raise


if __name__ == "__main__":
    sys.exit(_cli_entrypoint(main))

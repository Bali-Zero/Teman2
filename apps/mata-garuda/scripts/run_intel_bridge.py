#!/usr/bin/env python3
"""Mata Garuda — Intel Scraper Bridge runner.

Cron-safe batch runner (no Claude CLI reasoning loop). Calls the
deterministic bridge function directly and prints a JSON result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mata_garuda.agents.intel_scraper_bridge import bridge_intel_scraper
from mata_garuda.workers.heartbeat import emit_heartbeat

# Organ id matches organs_registry.yaml `mata_garuda.intel_bridge_daily.mini`
# (com.matagaruda.intel-bridge.daily on Mini). Wired 2026-07-07 (healer receptor
# 4, PENDING-ARMS): this cron was running fine but had never written the
# heartbeat sidecar the registry-driven receptor expects, so it was flagged
# never_armed instead of ok. See mata_garuda.workers.heartbeat for the shared
# emitter (same ~/.organism/last_seen/<organ_id>.json schema as other organs).
ORGAN_ID = "mata_garuda.intel_bridge_daily.mini"


def main() -> int:
    result = bridge_intel_scraper()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # Heartbeat at real completion (after the bridge call returns), carrying
    # its published/skipped counts — not just a process-start ping.
    emit_heartbeat(
        ORGAN_ID,
        "ok",
        metadata={
            "published": result.get("published", 0),
            "skipped": result.get("skipped", 0),
            "case_resolved": result.get("case_resolved", False),
        },
    )
    return 0
    # NOTE: we return 0 even on "no_recent_items" because the Lamarckian
    # case_not_resolved is informational, not an error, per GENOME.md.


def _cli_entrypoint(main_fn) -> int:
    """Run `main_fn()`, emitting a fail heartbeat only on a genuine exception.

    `except BaseException` around `sys.exit(main_fn())` used to catch our OWN
    successful SystemExit(0) and overwrite the correct "ok" heartbeat main_fn()
    just wrote with status=fail (metadata {"error": "SystemExit: 0"}), every
    run (same bug as run_normalizer.py, class-audit 2026-07-07). Catching
    `Exception` (not `BaseException`) lets SystemExit/KeyboardInterrupt through
    untouched.
    """
    try:
        return main_fn()
    except Exception as exc:  # noqa: BLE001 — heartbeat then re-raise
        emit_heartbeat(ORGAN_ID, "fail", metadata={"error": f"{type(exc).__name__}: {exc}"})
        raise


if __name__ == "__main__":
    sys.exit(_cli_entrypoint(main))

"""Mata Garuda — minimal organism heartbeat emitter (Stage 1, 2026-06-29).

Writes the same `~/.organism/last_seen/<organ_id>.json` sidecar the receptor
(scripts/organism_stale_detector.py, PR #1805/#1808) reads, so a green-but-dead
mata_garuda singleton (e.g. gap_consumer running exit-0 while acking ~5% of its
backlog) surfaces as `unhealthy` instead of being invisible.

We deliberately do NOT import apps/cell's emit_organ_last_seen: mata_garuda's
CLAUDE.md §1 forbids importing from other monorepo apps (stack-isolated,
pydantic-only). This is a ~20-line copy of the SAME schema (W1.1 convention),
not a new format — schema parity is load-bearing (superscar #9: two divergent
sidecar formats already exist; do not add a third).

Schema:
    {"ts": <float epoch>, "status": "ok"|"degraded"|"fail",
     "organ_id": "<full.id>", "metadata": {...}}

Best-effort: never raises back to the producer (the cron's real work must not
depend on the sidecar landing). A missing/stale file already reads as dead.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Mapping

logger = logging.getLogger("mata_garuda.workers.heartbeat")

# Override via env for tests / non-standard homes; default matches the receptor.
_DEFAULT_DIR = os.path.expanduser("~/.organism/last_seen")


def emit_heartbeat(
    organ_id: str,
    status: str,
    metadata: Mapping[str, Any] | None = None,
    *,
    out_dir: str | None = None,
) -> bool:
    """Write the sidecar JSON for `organ_id`. Returns True on success.

    Never raises: any I/O / serialization failure is logged at WARNING and
    swallowed (the receptor treats absent sidecar as dead anyway).
    """
    target_dir = out_dir or os.environ.get("ORGANISM_LAST_SEEN_DIR") or _DEFAULT_DIR
    try:
        os.makedirs(target_dir, exist_ok=True)
        payload: dict[str, Any] = {
            "ts": time.time(),
            "status": str(status),
            "organ_id": str(organ_id),
            "metadata": dict(metadata) if metadata else {},
        }
        tmp = os.path.join(target_dir, f".{organ_id}.json.tmp")
        final = os.path.join(target_dir, f"{organ_id}.json")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload))
        os.replace(tmp, final)  # atomic — never a half-written sidecar
        return True
    except Exception as exc:  # noqa: BLE001 — emitter must stay robust
        logger.warning("mata_garuda heartbeat emit failed for %s: %s", organ_id, exc)
        return False


def status_from_stats(stats: Mapping[str, int]) -> str:
    """Derive a heartbeat status from a worker's run stats.

    Convention: a run that read items but ack'd ~none is the green-but-dead
    signature (gap_consumer 95%-unacked). `errors` dominate → fail.
    """
    read = int(stats.get("read", 0))
    errors = int(stats.get("errors", 0))
    if errors and errors >= max(1, read):
        return "fail"
    resolved = int(stats.get("resolved", 0))
    skipped = int(stats.get("skipped", 0))
    progressed = resolved + skipped + int(stats.get("failed", 0))
    if read > 0 and progressed == 0:
        # read a backlog but moved nothing forward → degraded (the dead-but-green case)
        return "degraded"
    return "ok"

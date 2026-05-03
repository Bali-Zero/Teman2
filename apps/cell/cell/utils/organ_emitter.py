"""Emit a sidecar liveness file for the Innervation Genoma aggregator.

Convention (W1.1, 2026-04-30):

    ~/.organism/last_seen/<organ_id>.json

    {
        "ts": <unix_epoch_float>,
        "status": "ok" | "degraded" | "fail",
        "organ_id": "<full.id>",
        "metadata": {<dict>}
    }

The Cell `genome_aggregator_sensor` reads this sidecar via
`bridge_source: state_file` declared in `apps/organism/organism/genome.yaml`.
A missing / stale file → BridgeReading.error → organ classified `dead`.

This helper is intentionally tiny and dependency-free: it is called from
hot paths (every Pulse cycle for cell.organism, every cron tick for shell
organi) and MUST never raise back to the producer.

Spec ref: docs/innervation-2026-04-29/07_innervation_protocol.md §1.1.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("cell.utils.organ_emitter")

# Module-level constants — easy to override in tests.
DEFAULT_LAST_SEEN_DIR = Path("~/.organism/last_seen").expanduser()


def emit_organ_last_seen(
    organ_id: str,
    status: str,
    metadata: Mapping[str, Any] | None = None,
    *,
    out_dir: Path | str | None = None,
) -> bool:
    """Write the sidecar JSON. Returns True on success, False otherwise.

    Best-effort: any I/O / serialization failure is logged at WARNING and
    swallowed — the producer's primary path must NOT depend on the sidecar
    landing on disk. The Genoma aggregator already treats absent sidecar as
    `dead`, so a write failure naturally surfaces as silence on the next
    Cell pulse.
    """
    target_dir = Path(out_dir) if out_dir else DEFAULT_LAST_SEEN_DIR
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "ts": time.time(),
            "status": str(status),
            "organ_id": str(organ_id),
            "metadata": dict(metadata) if metadata else {},
        }
        out_file = target_dir / f"{organ_id}.json"
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return True
    except Exception as exc:  # noqa: BLE001 — keep emitter robust
        logger.warning(f"organ_last_seen emit failed for {organ_id}: {exc}")
        return False


__all__ = ["emit_organ_last_seen", "DEFAULT_LAST_SEEN_DIR"]

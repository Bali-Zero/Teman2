"""Append-only JSONL telemetry with size-based rotation.

Path: $WR2_TELEMETRY_PATH or ~/logs/wr2_canva_pdf_apply_telemetry.jsonl.
Rotation: when file > $WR2_TELEMETRY_MAX_BYTES (default 50MB), rename
to .jsonl.<timestamp>. Old rotated files auto-deleted via OS cron
or manual cleanup (not this module's responsibility).

Never raises — telemetry must never break the orchestrator.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _path() -> Path:
    p = os.environ.get(
        "WR2_TELEMETRY_PATH",
        str(Path.home() / "logs" / "wr2_canva_pdf_apply_telemetry.jsonl"),
    )
    return Path(p)


def _max_bytes() -> int:
    return int(os.environ.get("WR2_TELEMETRY_MAX_BYTES", str(50 * 1024 * 1024)))


def _maybe_rotate(path: Path) -> None:
    if not path.exists():
        return
    if path.stat().st_size <= _max_bytes():
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rotated = path.with_suffix(path.suffix + f".{stamp}")
    try:
        path.rename(rotated)
    except OSError as e:
        logger.warning("Telemetry rotation failed: %s", e)


def log_telemetry(
    *, draft_id: str, outcome: str, duration_s: float,
    attempt: int = 1, exc_head: str = "",
) -> None:
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        _maybe_rotate(path)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "draft_id": str(draft_id),
            "attempt": attempt,
            "outcome": outcome,
            "duration_s": round(duration_s, 1),
            "exc_head": exc_head[:240] if exc_head else "",
        }
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # noqa: BLE001 — telemetry must never break run
        logger.warning("Telemetry write failed (swallowed): %s", e)

"""Parser for nlm_feeder_stream JSONL log.

The feeder log lives at ~/logs/matagaruda-nlm-feeder-stream.log and writes
a JSON line per cron tick with shape:

    {"agent": "nlm_feeder_stream",
     "alerts": {"processed": N, "fed": N, "skipped": N, "errors": N},
     "enriched": {"processed": N, "fed": N, "skipped": N, "errors": N}}

Older entries used a single "stats" object instead of two streams. We
sum alerts+enriched (or read stats if present) to compute push_success_rate.

GLOBAL ONLY: this log has no per-UUID breakdown. The same rate is applied
to every UUID with active_routing=True. Per-UUID per-message logging is
out of scope for this PR (see ADR-006).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path.home() / "logs" / "matagaruda-nlm-feeder-stream.log"


def parse_feeder_log(path: Path) -> Iterator[dict]:
    """Yield each parsed JSON line from the feeder log. Malformed lines skipped."""
    if not path.exists():
        return
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning("feeder_log: cannot read %s: %s", path, e)


def compute_global_push_success_rate(
    path: Path,
    window_seconds: int,
    now: float | None = None,
) -> float | None:
    """Compute global push success rate over the rolling window.

    Returns None if total processed is 0 (undefined rate) or file is older
    than window or missing.
    """
    now = now if now is not None else time.time()
    if not path.exists():
        return None
    try:
        if path.stat().st_mtime < now - window_seconds:
            return None
    except OSError:
        return None

    processed = 0
    fed = 0
    for record in parse_feeder_log(path):
        for key in ("alerts", "enriched", "stats"):
            block = record.get(key)
            if isinstance(block, dict):
                p = block.get("processed", 0)
                f = block.get("fed", 0)
                if isinstance(p, int):
                    processed += p
                if isinstance(f, int):
                    fed += f
    if processed == 0:
        return None
    return fed / processed

#!/usr/bin/env python3
"""
Vector reindex check — runs nightly via cron (recommended: 02:30 WITA).
Checks whether the Qdrant vector collections need re-indexing and triggers
the reindex script if drift is detected.

Maintenance window: 02:00–05:00 WITA (UTC+8). Runs outside that window
are skipped and logged.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python scripts/vector-reindex-check.py
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
REINDEX_SCRIPT = REPO_ROOT / "apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py"

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")

# Minimum number of vectors expected in the primary KBLI collection.
# If the live count drops below this threshold, reindex is triggered.
KBLI_MIN_VECTORS = 1_400

# WITA = UTC+8
WITA = datetime.timezone(datetime.timedelta(hours=8))
MAINTENANCE_HOUR_START = 2   # 02:00 WITA inclusive
MAINTENANCE_HOUR_END = 5     # 05:00 WITA exclusive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _qdrant_get(path: str) -> dict[str, Any]:
    """Simple synchronous HTTP GET against the Qdrant REST API."""
    import urllib.error
    import urllib.request

    url = f"{QDRANT_URL.rstrip('/')}/{path.lstrip('/')}"
    req = urllib.request.Request(url)
    if QDRANT_API_KEY:
        req.add_header("api-key", QDRANT_API_KEY)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        logger.error("Qdrant request failed for %s: %s", url, exc)
        return {}


def get_collection_vector_count(collection_name: str) -> int | None:
    """Return the approximate point count for *collection_name*, or None on error."""
    data = _qdrant_get(f"/collections/{collection_name}")
    try:
        return int(data["result"]["points_count"])
    except (KeyError, TypeError, ValueError):
        logger.warning("Could not read points_count for collection '%s'", collection_name)
        return None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def check_reindex_needed() -> dict[str, Any]:
    """
    Inspect live Qdrant collections and decide whether a reindex is needed.

    Returns a dict with keys:
        needed   (bool)  — True if reindex should run
        reason   (str)   — human-readable explanation
        details  (dict)  — per-collection diagnostics
    """
    details: dict[str, Any] = {}
    needed = False
    reasons: list[str] = []

    # --- Check 1: KBLI 2025 collection vector count ---
    kbli_collection = "kbli_2025_final"
    count = get_collection_vector_count(kbli_collection)
    details[kbli_collection] = {"points_count": count, "min_expected": KBLI_MIN_VECTORS}

    if count is None:
        needed = True
        reasons.append(f"Could not read '{kbli_collection}' — collection may be missing")
    elif count < KBLI_MIN_VECTORS:
        needed = True
        reasons.append(
            f"'{kbli_collection}' has {count} vectors, expected >= {KBLI_MIN_VECTORS}"
        )
    else:
        logger.info("Collection '%s' OK: %d vectors", kbli_collection, count)

    return {
        "needed": needed,
        "reason": "; ".join(reasons) if reasons else "All collections within expected bounds",
        "details": details,
    }


def trigger_reindex_if_needed() -> dict[str, Any]:
    """
    Run check_reindex_needed() and, if a reindex is required, invoke the
    reindex script — but ONLY during the maintenance window (02:00–05:00 WITA).

    Returns a summary dict suitable for logging or Telegram alerting.
    """
    # --- Maintenance window guard ---
    now_wita = datetime.datetime.now(tz=WITA)
    if not (MAINTENANCE_HOUR_START <= now_wita.hour < MAINTENANCE_HOUR_END):
        logger.info(
            "Reindex skipped: outside maintenance window (02:00-05:00 WITA) — current time %s WITA",
            now_wita.strftime("%H:%M"),
        )
        return {
            "triggered": False,
            "skipped_reason": "outside maintenance window (02:00-05:00 WITA)",
        }

    # --- Check whether reindex is needed ---
    check = check_reindex_needed()
    logger.info("Reindex check: needed=%s — %s", check["needed"], check["reason"])

    if not check["needed"]:
        return {"triggered": False, "check": check}

    # --- Trigger reindex ---
    if not REINDEX_SCRIPT.exists():
        logger.error("Reindex script not found: %s", REINDEX_SCRIPT)
        return {
            "triggered": False,
            "error": f"Reindex script not found: {REINDEX_SCRIPT}",
            "check": check,
        }

    logger.info("Triggering reindex: %s", REINDEX_SCRIPT)
    result = subprocess.run(
        [sys.executable, str(REINDEX_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "apps/backend-rag"),
        timeout=1800,  # 30 minutes max
    )

    if result.returncode == 0:
        logger.info("Reindex completed successfully")
    else:
        logger.error(
            "Reindex failed (exit %d):\nSTDOUT: %s\nSTDERR: %s",
            result.returncode,
            result.stdout[-2000:],
            result.stderr[-2000:],
        )

    return {
        "triggered": True,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-500:],
        "stderr_tail": result.stderr[-500:],
        "check": check,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("vector-reindex-check starting")
    summary = trigger_reindex_if_needed()
    logger.info("vector-reindex-check done: %s", json.dumps(summary, default=str))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Daily Canva OAuth refresh-token expiry watchdog.

Canva refresh tokens decay ~90 days unused. This watchdog reads
last_refreshed_iso from canva_tokens.json and alerts at 75d (warn)
and 85d (critical). Runs daily via launchd 09:00 WITA.
"""
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2._token_storage import (  # noqa: E402
    OrchestratorTokenStorage, TokenStorageError,
)
from backend.services.canva_renderer_v2._telegram import send_telegram  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token-watchdog")


def main() -> int:
    try:
        storage = OrchestratorTokenStorage()
        data = storage.load_sync()
    except TokenStorageError as e:
        send_telegram(f"🚨 WR2 Canva token UNREADABLE\n{e}")
        return 1

    last_iso = data.get("last_refreshed_iso")
    if not last_iso:
        logger.warning("No last_refreshed_iso — bootstrap predates this field")
        return 0

    last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    days = (now - last).days

    if days > 85:
        send_telegram(
            f"🚨 *WR2 Canva refresh CRITICAL*\nDays since last refresh: {days}\n"
            f"Token decays at 90d — re-bootstrap NOW.\nRun: scripts/wr2_bootstrap_canva_oauth.py"
        )
    elif days > 75:
        send_telegram(
            f"⚠️ *WR2 Canva refresh WARN*\nDays since last refresh: {days}\n"
            f"Plan re-bootstrap within 15 days."
        )
    logger.info("Days since last refresh: %d", days)
    return 0


if __name__ == "__main__":
    sys.exit(main())

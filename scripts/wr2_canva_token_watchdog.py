#!/usr/bin/env python3
"""Daily Canva OAuth token watchdog.

Two checks:
1. Access token auto-refresh if expired (expires ~3.5h, no manual intervention needed).
2. Refresh token decay alert at 75d (warn) and 85d (critical).

Runs daily via launchd 09:00 WITA.
"""
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

from backend.services.canva_renderer_v2._telegram import send_telegram  # noqa: E402
from backend.services.canva_renderer_v2._token_storage import (  # noqa: E402
    OrchestratorTokenStorage,
    TokenStorageError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token-watchdog")

CANVA_TOKEN_URL = "https://mcp.canva.com/token"


def _refresh_access_token(data: dict) -> dict:
    """Exchange refresh_token for new access_token via Canva token endpoint."""
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": data["refresh_token"],
        "client_id": data["client_id"],
        "client_secret": data["client_secret"],
    }).encode()
    req = urllib.request.Request(CANVA_TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def main() -> int:
    try:
        storage = OrchestratorTokenStorage()
        data = storage.load_sync()
    except TokenStorageError as e:
        send_telegram(f"🚨 WR2 Canva token UNREADABLE\n{e}")
        return 1

    # --- Check 1: access token expiry (auto-refresh) ---
    expires_at = float(data.get("expires_at_epoch", 0))
    now = time.time()
    margin = 300  # 5 min safety window
    if expires_at - now < margin:
        logger.info("Access token expired or expiring soon — refreshing...")
        try:
            new_tokens = _refresh_access_token(data)
            storage.save_sync(new_tokens)
            logger.info("Access token refreshed OK (expires_in=%s)", new_tokens.get("expires_in"))
        except Exception as e:
            send_telegram(
                f"🚨 WR2 Canva access token refresh FAILED\n"
                f"err: {e}\nRun scripts/wr2_bootstrap_canva_oauth.py on Pro."
            )
            return 1

    # --- Check 2: refresh token decay (alert only) ---
    last_iso = data.get("last_refreshed_iso")
    if not last_iso:
        logger.warning("No last_refreshed_iso — bootstrap predates this field")
        return 0

    last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - last).days

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

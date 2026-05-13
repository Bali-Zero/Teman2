#!/usr/bin/env python3
"""Intel Lake outbox drain (Wave 1, 2026-05-12).

Reads up to 100 pending rows from ~/.intel-lake-outbox.db and POSTs them
to the backend Fly endpoint `/api/intel/lake/observations:batch`.

Scheduled every 60s via LaunchAgent `com.balizero.intel-lake.outbox-drain.minute`.

Env required:
  INTEL_LAKE_PRODUCER_TOKEN  — bearer for X-Producer-Token header
  NUZANTARA_BACKEND_URL      — default https://nuzantara-rag.fly.dev
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from intel_lake_outbox import fetch_pending, mark_delivered, mark_failed, stats  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [outbox-drain] %(message)s",
)
logger = logging.getLogger("intel-lake-outbox-drain")

BACKEND_URL = os.environ.get("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
PRODUCER_TOKEN = os.environ.get("INTEL_LAKE_PRODUCER_TOKEN", "")
BATCH_SIZE = int(os.environ.get("INTEL_LAKE_DRAIN_BATCH", "100"))
HTTP_TIMEOUT = float(os.environ.get("INTEL_LAKE_DRAIN_TIMEOUT", "30"))


def main() -> int:
    if not PRODUCER_TOKEN:
        logger.error("INTEL_LAKE_PRODUCER_TOKEN missing — refusing to drain")
        return 2

    rows = fetch_pending(BATCH_SIZE)
    if not rows:
        # No work — print stats every 5 minutes (cheap)
        s = stats()
        if s["pending"] or s["abandoned"]:
            logger.info("idle (pending=%(pending)s delivered=%(delivered)s abandoned=%(abandoned)s)", s)
        return 0

    ids = [r[0] for r in rows]
    observations: list[dict[str, Any]] = []
    for _id, _producer, payload_json in rows:
        try:
            observations.append(json.loads(payload_json))
        except Exception as e:
            logger.warning("row %s malformed JSON: %s — abandoning", _id, e)
            # Mark as 10 attempts to abandon
            for _ in range(10):
                mark_failed(_id, f"malformed JSON: {e}")
            continue

    url = f"{BACKEND_URL.rstrip('/')}/api/intel/lake/observations-batch"
    payload = {"observations": observations}
    headers = {
        "X-Producer-Token": PRODUCER_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            body = r.json()
    except httpx.HTTPStatusError as e:
        # 401/413 etc. — definitely won't recover by retrying
        for _id in ids:
            mark_failed(_id, f"http {e.response.status_code}: {e.response.text[:200]}")
        logger.error("HTTP %s draining %s rows: %s", e.response.status_code, len(ids), e.response.text[:200])
        return 1
    except Exception as e:
        # Network / timeout — retryable, increment attempts and retry next tick
        for _id in ids:
            mark_failed(_id, f"network: {type(e).__name__}: {e}")
        logger.warning("network error draining %s rows: %s — will retry", len(ids), e)
        return 1

    accepted = int(body.get("accepted", 0))
    rejected = int(body.get("rejected", 0))

    # Mark all delivered to avoid infinite retry loops. The backend audit log
    # is the system of record for rejected items.
    #
    # However: a non-zero rejected count means producer-side data is being
    # silently dropped. Emit a WARNING + Telegram alert (debounced via state
    # file) when rejected > 0 — discovered 2026-05-13 that a `published_at`
    # bind error in intel_lake_service.py was silently dropping every item
    # with a date since Wave 4 deploy, with zero visibility from producers.
    mark_delivered(ids)
    if rejected > 0:
        logger.warning(
            "drained %s rows but %s REJECTED by backend — check intel_lake_audit_log on Fly. "
            "accepted=%s rejected=%s url=%s",
            len(ids), rejected, accepted, rejected, BACKEND_URL,
        )
        _alert_rejected(rejected, accepted, len(ids))
    else:
        logger.info(
            "drained %s rows (accepted=%s rejected=%s) → backend %s",
            len(ids), accepted, rejected, BACKEND_URL,
        )
    return 0


_ALERT_STATE_PATH = Path.home() / "logs" / "intel-lake-outbox-drain.alert-state.json"
_ALERT_COOLDOWN_S = 30 * 60  # 30 min between alerts


def _alert_rejected(rejected: int, accepted: int, total: int) -> None:
    """Send Telegram alert if rejected > 0, debounced 30min.

    Reads/writes a state file with the last-alert timestamp. The first alert
    fires immediately; subsequent alerts for the same condition wait at
    least 30min to avoid spamming during a backend regression.
    """
    import json as _json
    import time as _time
    import urllib.parse as _up
    import urllib.request as _ur

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "")
    if not (token and chat):
        return

    now = _time.time()
    state: dict[str, Any] = {}
    try:
        if _ALERT_STATE_PATH.exists():
            state = _json.loads(_ALERT_STATE_PATH.read_text())
    except Exception:
        state = {}
    last_alert = float(state.get("last_alert_at", 0))
    if now - last_alert < _ALERT_COOLDOWN_S:
        return  # debounced

    text = (
        f"\U0001F534 intel-lake-outbox-drain: {rejected}/{total} items REJECTED by backend "
        f"(accepted={accepted}). Check intel_lake_audit_log on Fly for root cause."
    )
    try:
        data = _up.urlencode({"chat_id": chat, "text": text}).encode()
        _ur.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            timeout=10,
        )
        state["last_alert_at"] = now
        _ALERT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ALERT_STATE_PATH.write_text(_json.dumps(state))
        logger.info("Telegram alert sent (rejected=%s)", rejected)
    except Exception as e:
        logger.warning("Telegram alert failed: %s", e)


if __name__ == "__main__":
    sys.exit(main())

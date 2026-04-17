"""
Portal Deadline Watchdog.

Every 6h cron: scan deadlines due within the next 30 days, cross-join with
`notification_prefs` for users who opted into WhatsApp, and send a single
reminder per (user, deadline) per 7-day window.

Usage:
    PYTHONPATH=. python -m backend.scripts.portal_deadline_watchdog
    # or, from apps/backend-rag root:
    PYTHONPATH=. python -m scripts.portal_deadline_watchdog --dry-run

Env vars required:
    DATABASE_URL           — Postgres connection string
    META_WA_TOKEN          — WhatsApp Cloud API token (via WhatsAppService)
    META_WA_PHONE_NUMBER_ID

Graceful degradation:
    - Missing `notification_prefs` / `notification_log` → logs warning, exits 0.
    - WA send failure for one recipient → logged, other recipients continue.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg

logger = logging.getLogger("portal_deadline_watchdog")


# ── Query selects users with WA opt-in who have a deadline within 30 days
#    that hasn't already been WA-notified in the last 7 days.
_SELECT_DUE = """
SELECT
    np.user_id,
    np.wa_phone,
    d.ref,
    d.label,
    d.due_date
FROM notification_prefs np
JOIN (
    -- Visa / passport expiry on the client row
    SELECT u.id AS user_id,
           'client-visa:'  || c.id AS ref,
           'Visa expiry'   AS label,
           c.visa_expiry   AS due_date
    FROM clients c
    JOIN users u ON u.linked_client_id = c.id
    WHERE c.visa_expiry IS NOT NULL
      AND c.visa_expiry BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'

    UNION ALL

    SELECT u.id AS user_id,
           'client-passport:' || c.id AS ref,
           'Passport expiry' AS label,
           c.passport_expiry AS due_date
    FROM clients c
    JOIN users u ON u.linked_client_id = c.id
    WHERE c.passport_expiry IS NOT NULL
      AND c.passport_expiry BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'

    UNION ALL

    SELECT u.id AS user_id,
           'practice:' || p.id::text AS ref,
           pt.name AS label,
           p.expiry_date::date AS due_date
    FROM practices p
    JOIN practice_types pt ON pt.id = p.practice_type_id
    JOIN users u ON u.linked_client_id = p.client_id
    WHERE p.expiry_date IS NOT NULL
      AND (p.client_visible IS TRUE OR p.client_visible IS NULL)
      AND p.status NOT IN ('cancelled', 'rejected')
      AND p.expiry_date BETWEEN NOW() AND NOW() + INTERVAL '30 days'
) d ON d.user_id = np.user_id
WHERE np.wa_enabled = TRUE
  AND np.wa_phone IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM notification_log l
      WHERE l.user_id = np.user_id
        AND l.channel = 'wa'
        AND l.ref = d.ref
        AND l.sent_at > NOW() - INTERVAL '7 days'
  )
ORDER BY d.due_date ASC
"""


def _format_message(label: str, due_date: Any) -> str:
    date_str = due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date)
    return (
        f"⏰ Bali Zero reminder: {label} is due on {date_str}.\n"
        f"Open the portal → https://my.balizero.com to see what's needed."
    )


async def _iter_due(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    try:
        return await conn.fetch(_SELECT_DUE)
    except Exception as e:
        logger.warning("watchdog query failed (tables missing?): %s", e)
        return []


async def _log_sent(conn: asyncpg.Connection, user_id: Any, ref: str) -> None:
    try:
        await conn.execute(
            "INSERT INTO notification_log (user_id, channel, ref) VALUES ($1, 'wa', $2)",
            user_id,
            ref,
        )
    except Exception as e:
        logger.warning("notification_log insert failed for user=%s ref=%s: %s", user_id, ref, e)


async def run(dry_run: bool = False) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        rows = await _iter_due(conn)
        if not rows:
            logger.info("watchdog: nothing to send")
            return 0

        logger.info("watchdog: %d reminders candidate", len(rows))

        if dry_run:
            for r in rows:
                logger.info(
                    "[DRY] user=%s phone=%s ref=%s label=%s due=%s",
                    r["user_id"],
                    r["wa_phone"],
                    r["ref"],
                    r["label"],
                    r["due_date"],
                )
            return 0

        # Lazy import keeps the script importable in test envs without Meta creds.
        from backend.services.integrations.whatsapp_service import whatsapp_service

        sent = 0
        failed = 0
        for r in rows:
            msg = _format_message(r["label"], r["due_date"])
            try:
                await whatsapp_service.send_message(phone=r["wa_phone"], text=msg)
                await _log_sent(conn, r["user_id"], r["ref"])
                sent += 1
            except Exception as e:
                logger.error(
                    "WA send failed user=%s ref=%s: %s",
                    r["user_id"], r["ref"], e,
                )
                failed += 1

        logger.info("watchdog: sent=%d failed=%d", sent, failed)
        return 0 if failed == 0 else 1
    finally:
        await conn.close()


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="log what would be sent, don't send")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(_cli())

"""
Migration 111: notification_log — dedupe ledger per outbound reminder.

Used by portal_deadline_watchdog (cron every 6h) and any other service
that sends client reminders, to guarantee "at most one reminder per
deadline per channel per 7-day window".

Schema:
- id          BIGSERIAL PK
- user_id     UUID  (sender side: the client user)
- channel     VARCHAR(20)  ('email' | 'wa' | 'push' | …)
- ref         VARCHAR(128) — opaque dedup key (e.g. "deadline:<id>")
- sent_at     TIMESTAMPTZ  default NOW()

Index on (user_id, channel, ref, sent_at DESC) makes the "did we already
send this in the last N days?" lookup O(log n).

Reference: design 2026-04-17-v2-subdomain-rollout-design.md §4.3

Author: Claude Opus 4.7
Date: 2026-04-17
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id         BIGSERIAL PRIMARY KEY,
            user_id    UUID NOT NULL,
            channel    VARCHAR(20) NOT NULL,
            ref        VARCHAR(128) NOT NULL,
            sent_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_notification_log_lookup
        ON notification_log (user_id, channel, ref, sent_at DESC);
    """)
    logger.info("migration 111: notification_log created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS notification_log;")
    logger.info("migration 111: rolled back")

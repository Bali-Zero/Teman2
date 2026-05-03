"""
Migration 110: notification_prefs — preferenze notifica cliente.

Permette al cliente portal di scegliere canale: email, whatsapp, entrambi.
Usato da portal_deadline_watchdog (cron ogni 6h) e da qualsiasi servizio
che genera reminder utente.

Schema:
- user_id UUID PK (FK implicito a users.id)
- email_enabled BOOLEAN default TRUE
- wa_enabled BOOLEAN default FALSE
- wa_phone VARCHAR(20) NULL  (formato E.164, no +)
- updated_at TIMESTAMP

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
        CREATE TABLE IF NOT EXISTS notification_prefs (
            user_id         UUID PRIMARY KEY,
            email_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
            wa_enabled      BOOLEAN NOT NULL DEFAULT FALSE,
            wa_phone        VARCHAR(20),
            updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    logger.info("migration 110: notification_prefs created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS notification_prefs;")
    logger.info("migration 110: rolled back")

"""
Migration 118: clients.referrer_url + landing_page + first_touch_at — SEO attribution.

Why
---
SEO Cell Phase 2 revenue attribution requires knowing which landing page
(and which Google referrer) brought a lead. Without this, we cannot
attribute revenue to specific brief URLs published by the newsroom.

The CRO audit 2026-04-19 found 2 leads with lead_source='website' over
90 days vs 420 from WhatsApp. Without referrer/landing capture, every
website lead is opaque — we cannot tell which page or which Google query
was responsible.

Schema additions to clients
---------------------------
- referrer_url    TEXT — HTTP Referer header at first interaction
- landing_page    TEXT — first page on balizero.com domain visited
- first_touch_at  TIMESTAMPTZ — when the lead first interacted (web/WA/etc)

Indexes
-------
- idx_clients_referrer_url: text_pattern_ops for LIKE queries on URL
- idx_clients_landing_page: text_pattern_ops for LIKE queries on URL

Both partial indexes (WHERE column IS NOT NULL) since most legacy clients
have NULL — small index, no overhead on inserts of legacy rows.

Companion changes
-----------------
- backend/services/crm/lead_intake.py — captures these fields on insert
- apps/mouth/src/lib/whatsapp-utm.ts — sets utm_* on WA links so
  lead_source can differentiate website_organic vs whatsapp_inbound

Idempotent: safe to re-run.

Spec: docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md §3.2
Plan: docs/superpowers/plans/2026-04-19-seo-cell-A-prenatal-foundation.md Task 3
Author: Claude Opus 4.7
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    # Idempotent column additions
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'clients' AND column_name = 'referrer_url'
            ) THEN
                ALTER TABLE clients ADD COLUMN referrer_url TEXT;
                COMMENT ON COLUMN clients.referrer_url IS
                    'HTTP Referer header at first interaction. Used for SEO attribution.';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'clients' AND column_name = 'landing_page'
            ) THEN
                ALTER TABLE clients ADD COLUMN landing_page TEXT;
                COMMENT ON COLUMN clients.landing_page IS
                    'First page on balizero.com visited. SEO attribution + CRO analysis.';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'clients' AND column_name = 'first_touch_at'
            ) THEN
                ALTER TABLE clients ADD COLUMN first_touch_at TIMESTAMP WITH TIME ZONE;
                COMMENT ON COLUMN clients.first_touch_at IS
                    'When the lead first interacted with our properties (web/WhatsApp/etc).';
            END IF;
        END
        $$;
    """)

    # Partial indexes for SEO attribution queries (LIKE patterns on URL)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clients_referrer_url
            ON clients (referrer_url text_pattern_ops)
            WHERE referrer_url IS NOT NULL;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clients_landing_page
            ON clients (landing_page text_pattern_ops)
            WHERE landing_page IS NOT NULL;
    """)

    logger.info(
        "✅ Migration 118: clients.referrer_url + landing_page + first_touch_at + 2 partial indexes"
    )


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_clients_landing_page;")
    await conn.execute("DROP INDEX IF EXISTS idx_clients_referrer_url;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS first_touch_at;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS landing_page;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS referrer_url;")
    logger.info("Migration 118 rollback: 3 columns + 2 indexes dropped")

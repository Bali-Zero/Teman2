"""
Migration 119: lead_intents — homepage 4-app lead capture + WhatsApp handoff.

Why
---
Four homepage apps (visa_clock, visa_match, kbli_decoder, kbli_builder,
tax_gap, zoning_check) funnel users to a WhatsApp handoff. Every handoff
must persist its context so the */5 min cron matcher can correlate the
inbound WA message with the originating app session and backfill
`clients.lead_source` + `clients.lead_metadata` accordingly.

CRO audit 2026-04-19 found 2 website leads / 90 days vs 420 from WhatsApp
with no attribution possible — without `lead_intents`, the homepage apps
would inherit the same opacity problem.

Schema
------
Single table with JSONB `context` (app-specific payload), 7-day `expires_at`
TTL (cron purges past that), `matched_client_id` backfilled on WA match.
`source` enum is enforced at application layer (pydantic) not in DDL so
new apps can be added without migration.

Indexes
-------
- idx_lead_intents_unmatched_expiring: partial index for the matcher hot
  path (matched_client_id IS NULL AND expires_at > NOW()).
- idx_lead_intents_created_source: analytics rollups per source per day.

Companion
---------
- backend/services/lead_capture/repository.py — CRUD
- backend/services/lead_capture/whatsapp_deeplink.py — URL builder
- backend/app/routers/lead_capture.py — POST /api/lead/capture
- scripts/lead_intent_matcher.py — Air OpenClaw cron */5min

Idempotent: safe to re-run.

Plan: docs/plans/2026-04-19-4apps/00-shared-infrastructure.md (migration 117 in plan, renumbered to 119 because 117/118 already taken by llm_cost_events / clients referrer SEO)
Author: Claude Opus 4.7
Date: 2026-04-20
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_intents (
            id                  VARCHAR(20) PRIMARY KEY,
            source              VARCHAR(32) NOT NULL,
            context             JSONB NOT NULL,
            utm                 JSONB,
            fingerprint         VARCHAR(32),
            whatsapp_url        TEXT NOT NULL,
            matched_client_id   VARCHAR(20),
            matched_at          TIMESTAMP WITH TIME ZONE,
            created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            expires_at          TIMESTAMP WITH TIME ZONE NOT NULL
        );
    """)

    await conn.execute("""
        COMMENT ON TABLE lead_intents IS
            'Homepage 4-app lead capture. Each row = one WhatsApp handoff from visa/kbli/tax/zoning app. Matcher cron correlates on inbound WA.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN lead_intents.source IS
            'App that generated the handoff: visa_clock | visa_match | kbli_decoder | kbli_builder | tax_gap | zoning_check. Enforced at pydantic layer.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN lead_intents.context IS
            'App-specific payload (e.g. visa_clock: {visa_type, entry_date, expiry_date}; visa_match: {nationality, purpose, recommended_visa}).';
    """)
    await conn.execute("""
        COMMENT ON COLUMN lead_intents.matched_client_id IS
            'Backfilled by */5min matcher cron when inbound WhatsApp arrives within 30min of handoff and phone matches a client.';
    """)

    # Hot path for matcher: unmatched intents that have not expired yet.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lead_intents_unmatched_expiring
            ON lead_intents (created_at DESC)
            WHERE matched_client_id IS NULL;
    """)

    # Analytics rollup: lead count per source per day.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lead_intents_source_created
            ON lead_intents (source, created_at DESC);
    """)

    # TTL purge helper: find expired rows fast.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lead_intents_expires
            ON lead_intents (expires_at)
            WHERE matched_client_id IS NULL;
    """)

    logger.info(
        "✅ Migration 119: lead_intents table + 3 indexes created (idempotent)"
    )


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_lead_intents_expires;")
    await conn.execute("DROP INDEX IF EXISTS idx_lead_intents_source_created;")
    await conn.execute("DROP INDEX IF EXISTS idx_lead_intents_unmatched_expiring;")
    await conn.execute("DROP TABLE IF EXISTS lead_intents;")
    logger.info("Migration 119 rollback: lead_intents table + 3 indexes dropped")

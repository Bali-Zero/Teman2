"""
Migration 120: email_subscriptions — Brevo drip scheduler for homepage apps.

Why
---
Visa Clock emits 5 reminders per lead (D-60/30/14/7/1 before visa expiry).
Visa Match emits 1 pre-arrival nudge if `expected_arrival_date` provided.
KBLI Builder / Tax Gap / Zoning Check may add their own drips later.

We need a single scheduler table that: (a) decouples template scheduling
from business tables, (b) supports one-click unsubscribe with a token,
(c) allows a single cron to fan out all due emails.

Schema
------
- (email, app, context_hash, trigger_type) form the logical lead key.
- next_fire_at NULL = done (no more fires scheduled).
- unsubscribe_token globally unique; route /unsubscribe/{token} flips
  `unsubscribed=TRUE` for ALL rows matching the same email+app combo,
  per CAN-SPAM style one-click behaviour.
- fired_count for idempotency in a retry window + observability.

Indexes
-------
- idx_email_subs_due: partial index on next_fire_at for scheduler hot path.
- idx_email_subs_email_app: unsubscribe lookup + dedup.
- idx_email_subs_unsub_token: O(1) unsubscribe token lookup.

Companion
---------
- backend/services/notifications/funnel_email/scheduler.py — cron runner
- backend/services/notifications/funnel_email/templates/ — Jinja2 .html
- backend/app/routers/funnel_email.py — /unsubscribe/{token}

Idempotent: safe to re-run.

Plan: docs/plans/2026-04-19-4apps/00-shared-infrastructure.md (migration 118 in plan, renumbered to 120)
Author: Claude Opus 4.7
Date: 2026-04-20
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS email_subscriptions (
            id                  SERIAL PRIMARY KEY,
            email               VARCHAR(255) NOT NULL,
            app                 VARCHAR(32) NOT NULL,
            context_hash        VARCHAR(20) NOT NULL,
            trigger_type        VARCHAR(32) NOT NULL,
            next_fire_at        TIMESTAMP WITH TIME ZONE,
            fired_count         INT NOT NULL DEFAULT 0,
            unsubscribed        BOOLEAN NOT NULL DEFAULT FALSE,
            unsubscribe_token   VARCHAR(32) NOT NULL UNIQUE,
            payload             JSONB,
            created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """)

    await conn.execute("""
        COMMENT ON TABLE email_subscriptions IS
            'Scheduler for homepage-app drip emails (visa clock reminders, match pre-arrival, etc). Cron fires rows where next_fire_at <= NOW() AND NOT unsubscribed.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN email_subscriptions.trigger_type IS
            'e.g. visa_clock_d60, visa_clock_d30, visa_clock_d14, visa_clock_d7, visa_clock_d1, visa_match_prearrival_d7.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN email_subscriptions.context_hash IS
            'The hash from visa_checks.hash (or equivalent for other apps). Letter + digit only for URL safety.';
    """)
    await conn.execute("""
        COMMENT ON COLUMN email_subscriptions.payload IS
            'Snapshot of template variables at scheduling time. Self-contained so a template rename/migration does not break scheduled sends.';
    """)

    # Scheduler hot path: only look at rows due and active.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_subs_due
            ON email_subscriptions (next_fire_at)
            WHERE unsubscribed = FALSE AND next_fire_at IS NOT NULL;
    """)

    # One-click unsubscribe + dedup: find all rows for an email+app.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_subs_email_app
            ON email_subscriptions (email, app);
    """)

    # Token lookup is unique already but ensure query planner uses it.
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_subs_unsub_token
            ON email_subscriptions (unsubscribe_token);
    """)

    # updated_at trigger so scheduler updates are auditable.
    await conn.execute("""
        CREATE OR REPLACE FUNCTION set_email_subs_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    await conn.execute("""
        DROP TRIGGER IF EXISTS trg_email_subs_updated_at ON email_subscriptions;
        CREATE TRIGGER trg_email_subs_updated_at
            BEFORE UPDATE ON email_subscriptions
            FOR EACH ROW EXECUTE FUNCTION set_email_subs_updated_at();
    """)

    logger.info(
        "✅ Migration 120: email_subscriptions + 3 indexes + updated_at trigger created"
    )


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TRIGGER IF EXISTS trg_email_subs_updated_at ON email_subscriptions;")
    await conn.execute("DROP FUNCTION IF EXISTS set_email_subs_updated_at;")
    await conn.execute("DROP INDEX IF EXISTS idx_email_subs_unsub_token;")
    await conn.execute("DROP INDEX IF EXISTS idx_email_subs_email_app;")
    await conn.execute("DROP INDEX IF EXISTS idx_email_subs_due;")
    await conn.execute("DROP TABLE IF EXISTS email_subscriptions;")
    logger.info("Migration 120 rollback: email_subscriptions + 3 indexes + trigger dropped")

"""Migration 120: partner_email_outbox — transactional outbox for partner emails.

Spec: docs/superpowers/reviews/2026-04-21-partners-v1/99-synthesis.md CRIT-2.

The mark_paid_commission and activate_partner flows previously sent emails
directly from the HTTP handler. If Brevo failed between the DB commit and
the email send, the commission was stuck in 'paid' with the email
permanently lost (FSM blocks paid->paid retry).

Solution: transactional outbox. Every state change that should fire an email
inserts an outbox row in the SAME transaction. A worker (or /flush endpoint)
polls outbox rows and sends, with exponential backoff.

Author: Claude Opus 4.7 (1M context)
Date: 2026-04-21
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_email_outbox'
            ) THEN
                CREATE TABLE partner_email_outbox (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                    -- What to send
                    email_type TEXT NOT NULL
                        CHECK (email_type IN ('welcome', 'commission_earned')),
                    partner_id UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    commission_id UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
                    -- commission_id NULL for welcome emails; set for commission_earned

                    -- Rendered payload (prepared at enqueue time to freeze the content)
                    to_email TEXT NOT NULL,
                    cc_emails TEXT[] DEFAULT '{}',
                    subject TEXT NOT NULL,
                    body_markdown TEXT NOT NULL,

                    -- Lifecycle
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'failed_dlq')),
                    attempts INT NOT NULL DEFAULT 0,
                    last_error TEXT,
                    next_retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    sent_at TIMESTAMPTZ,

                    -- Audit
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    -- CATA-5: created_by references team_members(id VARCHAR), not users(id UUID)
                    created_by VARCHAR REFERENCES team_members(id) ON DELETE SET NULL,

                    -- Idempotency: one outbox row per (type, partner_id, commission_id)
                    -- Prevents double-enqueue if the mutation is retried.
                    idempotency_key TEXT UNIQUE
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_email_outbox_pending "
        "ON partner_email_outbox (status, next_retry_at) "
        "WHERE status = 'pending';"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_email_outbox_partner_id "
        "ON partner_email_outbox (partner_id);"
    )

    logger.info("Migration 120: partner_email_outbox + 2 indexes applied")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_partner_email_outbox_partner_id;")
    await conn.execute("DROP INDEX IF EXISTS idx_partner_email_outbox_pending;")
    await conn.execute("DROP TABLE IF EXISTS partner_email_outbox;")
    logger.info("Migration 120 rollback: partner_email_outbox + 2 indexes dropped")

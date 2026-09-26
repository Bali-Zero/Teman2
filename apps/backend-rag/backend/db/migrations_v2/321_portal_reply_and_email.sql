-- Explicit automated-message attribution and durable manual-message email delivery.
SET lock_timeout = '5s';
SET statement_timeout = '30s';

-- Legacy messages retain their previous team attribution. Their source cannot
-- be reconstructed safely; new automatic notices are explicitly marked.
ALTER TABLE portal_messages
    ADD COLUMN IF NOT EXISTS is_system_generated BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS portal_message_email_outbox (
    message_id BIGINT PRIMARY KEY REFERENCES portal_messages(id) ON DELETE CASCADE,
    idempotency_key UUID NOT NULL UNIQUE,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'sending', 'sent', 'failed', 'uncertain')),
    attempts BIGINT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_attempt_at TIMESTAMPTZ,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_until TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    last_error TEXT
);
-- New outbox is empty in the migration transaction; both timeouts remain bounded.
-- squawk-ignore require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_portal_message_email_due
    ON portal_message_email_outbox (next_attempt_at, lease_until)
    WHERE state IN ('pending', 'sending');

-- === ROLLBACK ===
-- Roll back application consumers first. Retain this additive schema and
-- delivery history to prevent duplicate emails; do not drop populated columns.

-- migration 198_wr2_publish_attempts
-- WR2 Publish Attempts Ledger — Meta Graph idempotency (Codex amendment)
-- Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §3.2
-- Author: Claude Opus 4.7 (orchestrator session 2026-05-27)

CREATE TABLE IF NOT EXISTS wr2_publish_attempts (
    id BIGSERIAL PRIMARY KEY,
    carousel_id UUID NOT NULL REFERENCES wr2_carousel_runs(carousel_id),
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'facebook', 'linkedin')),
    content_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'planned',
        'container_created',
        'published',
        'recorded',
        'failed',
        'blocked_manual_gate'
    )),
    provider_response JSONB,
    idempotency_key TEXT NOT NULL UNIQUE,
    manual_publish_token TEXT,
    token_expires_at TIMESTAMPTZ,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wr2_publish_attempts_carousel
    ON wr2_publish_attempts(carousel_id, state);

CREATE INDEX IF NOT EXISTS idx_wr2_publish_attempts_state_updated
    ON wr2_publish_attempts(state, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_wr2_publish_attempts_token_expiry
    ON wr2_publish_attempts(token_expires_at)
    WHERE state = 'blocked_manual_gate' AND token_expires_at IS NOT NULL;

COMMENT ON TABLE wr2_publish_attempts IS
    'Idempotency ledger per IG/Meta Graph publish lifecycle (Codex amendment). Each attempt writes BEFORE external call, updates after each Meta response. Reconciliation key: idempotency_key = carousel_id||platform||content_hash';

COMMENT ON COLUMN wr2_publish_attempts.state IS
    'planned (pre-call) → container_created (Meta child OK) → published (Meta parent OK) → recorded (DB sync OK). Failure: failed. Manual gate: blocked_manual_gate (token signed, expiring)';

COMMENT ON COLUMN wr2_publish_attempts.manual_publish_token IS
    'HMAC-SHA256 signed single-use token. Verified by Telegram inline button handler. Bound to content_hash to prevent token-reuse across drafts (Codex amendment)';

COMMENT ON COLUMN wr2_publish_attempts.idempotency_key IS
    'UNIQUE constraint prevents double-publish on retry. Format: <carousel_id>:<platform>:<content_hash[:16]>';


-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_wr2_publish_attempts_token_expiry;
DROP INDEX IF EXISTS idx_wr2_publish_attempts_state_updated;
DROP INDEX IF EXISTS idx_wr2_publish_attempts_carousel;
DROP TABLE IF EXISTS wr2_publish_attempts;

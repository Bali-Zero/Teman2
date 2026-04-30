-- 147_federation_alert_proposals.sql
--
-- Federation Alert Dispatcher (FAD) — proposal state table.
-- See: docs/superpowers/specs/2026-04-30-federation-alert-dispatcher.md
--
-- This migration is the foundation of FAD PR #1 (data + event spine).
-- It introduces:
--   * federation_alert_proposals table for proposal state machine
--   * system_settings seed for federation_alert_mode (default: observe)
--
-- The new EventBus PG channel `federation_alert` is registered separately
-- in apps/backend-rag/backend/services/events/event_bus.py PG_CHANNEL_MAP
-- (compile-time constant, no migration needed for that part).
--
-- Schema notes:
--   * id BIGSERIAL                    : monotonic ordering, unbounded growth ok
--   * proposal_id / run_id            : opaque idempotency identifiers
--   * idempotency_key                 : sha256 fingerprint, dedup window
--   * mode                            : 4 values, env can only DOWNGRADE from db
--   * status                          : 12 states, see proposal SM in spec
--   * compact_payload < 500 bytes     : pg_notify hard limit 8000B (10× headroom)
--   * full_payload                    : unbounded JSONB for daemon DB fetch
--   * lease_owner / lease_expires_at  : daemon row-level lease (advisory lock)
--   * approval_token                  : one-time HMAC for Telegram callback
--
-- Constraints rationale:
--   * UNIQUE on idempotency_key       : ON CONFLICT DO UPDATE for dedup
--   * CHECK octet_length < 500        : enforces pg_notify size at DB level
--   * CHECK awaiting_approval         : status must have approval_token+requires
--   * CHECK completed_at + status     : terminal states only
--
-- Squawk lint: see -- squawk-ignore comments. New empty table → all
-- inline ignores legitimate (no lock contention possible).

-- squawk-ignore: prefer-bigint-over-smallint
CREATE TABLE IF NOT EXISTS federation_alert_proposals (
    id BIGSERIAL PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,

    source_outbox_id BIGINT,
    source_channel TEXT NOT NULL DEFAULT 'federation_alert',
    source_ref TEXT,

    mode TEXT NOT NULL CHECK (mode IN (
        'observe', 'dry_deliberate', 'dry_action', 'production'
    )),
    status TEXT NOT NULL DEFAULT 'received' CHECK (status IN (
        'received', 'observed', 'deliberating', 'proposed',
        'dry_executing', 'dry_succeeded', 'dry_failed',
        'awaiting_approval', 'executing',
        'completed', 'failed', 'quarantined', 'duplicate'
    )),

    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN (
        'info', 'low', 'medium', 'high', 'critical'
    )),
    risk_level TEXT NOT NULL DEFAULT 'L2' CHECK (risk_level IN (
        'L0', 'L1', 'L2', 'L3'
    )),

    requested_action TEXT CHECK (
        requested_action IS NULL OR requested_action IN (
            'cleanup_log',
            'ack_outbox_event',
            'quarantine_alert',
            'prune_consumed_outbox'
        )
    ),
    target_file TEXT,

    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    compact_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    full_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    dispatch_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
    deliberation_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    votes JSONB NOT NULL DEFAULT '{}'::jsonb,
    gate_6_passes BOOLEAN,

    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approval_token TEXT,
    telegram_chat_id TEXT,
    telegram_message_id BIGINT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejected_by TEXT,
    rejected_at TIMESTAMPTZ,

    action_idempotency_key TEXT,
    quarantine_token TEXT,
    quarantine_reason TEXT,
    quarantined_at TIMESTAMPTZ,

    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_error TEXT,
    last_error_at TIMESTAMPTZ,
    artifact_uri TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    UNIQUE (proposal_id),
    UNIQUE (run_id),
    UNIQUE (idempotency_key),
    UNIQUE (action_idempotency_key),
    UNIQUE (quarantine_token),

    CHECK (octet_length(compact_payload::text) < 500),
    CHECK (status <> 'awaiting_approval' OR
           (requires_approval AND approval_token IS NOT NULL)),
    CHECK (completed_at IS NULL OR status IN (
        'observed', 'dry_succeeded', 'dry_failed',
        'completed', 'failed', 'quarantined', 'duplicate'
    ))
);

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_fad_status_next_attempt
ON federation_alert_proposals (status, next_attempt_at, created_at)
WHERE status IN (
    'received', 'deliberating', 'proposed',
    'dry_executing', 'awaiting_approval', 'executing'
);

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_fad_source_outbox_id
ON federation_alert_proposals (source_outbox_id)
WHERE source_outbox_id IS NOT NULL;

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_fad_mode_created_at
ON federation_alert_proposals (mode, created_at DESC);

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_fad_lease_expires_at
ON federation_alert_proposals (lease_expires_at)
WHERE lease_expires_at IS NOT NULL;

INSERT INTO system_settings (key, value, updated_at)
VALUES ('federation_alert_mode', 'observe', NOW())
ON CONFLICT (key) DO NOTHING;

-- === ROLLBACK ===
DELETE FROM system_settings WHERE key = 'federation_alert_mode';
DROP INDEX IF EXISTS idx_fad_lease_expires_at;
DROP INDEX IF EXISTS idx_fad_mode_created_at;
DROP INDEX IF EXISTS idx_fad_source_outbox_id;
DROP INDEX IF EXISTS idx_fad_status_next_attempt;
DROP TABLE IF EXISTS federation_alert_proposals;

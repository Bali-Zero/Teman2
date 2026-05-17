-- 182_cockpit_audit_log.sql
-- Immutable audit log with HMAC chain integrity
-- === FORWARD ===
CREATE TABLE IF NOT EXISTS cockpit_audit_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor TEXT NOT NULL DEFAULT 'antonello',
    action TEXT NOT NULL,
    params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result TEXT NOT NULL CHECK (result IN ('success', 'denied', 'error')),
    error_message TEXT,
    hmac_sha256 TEXT NOT NULL,
    prev_hmac TEXT
);

CREATE INDEX IF NOT EXISTS idx_cockpit_audit_log_recent ON cockpit_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cockpit_audit_log_action ON cockpit_audit_log (action, created_at DESC);

COMMENT ON TABLE cockpit_audit_log IS 'Immutable audit log for Zantara Cockpit. hmac_sha256 = HMAC(secret, prev_hmac || row_serialized). Tampering detectable by chain replay.';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_cockpit_audit_log_action;
-- DROP INDEX IF EXISTS idx_cockpit_audit_log_recent;
-- DROP TABLE IF EXISTS cockpit_audit_log;

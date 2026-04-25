-- 134_legacy_notification_log.sql
--
-- Promote `notification_log` to migrations_v2. Originally created by
-- backend/migrations/migration_111_notification_log.py (old-style
-- Python migration not discovered by the v2 runner).
--
-- alert_dispatcher.AlertDispatcher INSERTs into this table for every
-- compliance-alert dispatch (m114/m115); the convention is
-- ref = f"compliance_alert:{alert_id}:{channel}".
--
-- Idempotent. No-op on prod (already in this shape).

CREATE TABLE IF NOT EXISTS notification_log (
    id      BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    channel VARCHAR(20) NOT NULL,
    ref     VARCHAR(128) NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_log_lookup
    ON notification_log (user_id, channel, ref, sent_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_notification_log_lookup;
DROP TABLE IF EXISTS notification_log;

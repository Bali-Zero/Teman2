-- ============================================================
-- 126_email_send_log.sql
-- Persistent email attempt ledger + retry state.
-- Date: 2026-04-21
--
-- Replaces the fire-and-forget "best-effort + logger.warning" model that
-- hid Brevo/Zoho failures across all CRM automations (welcome, waiting
-- docs, invoicing, completion, HR bonus, cron notifiers). Every attempt
-- gets a row here pre-send; post-send updates status. Retry worker reads
-- status='failed' AND retry_after<NOW() AND attempt_number<3 to escalate
-- silently-dropped messages back into delivery.
--
-- Audited by: docs/audits/2026-04-21-kita-clients-process-email-audit.md
-- ============================================================

CREATE TABLE IF NOT EXISTS email_send_log (
    id                BIGSERIAL PRIMARY KEY,
    email_type        VARCHAR(50) NOT NULL,
    practice_id       INTEGER,
    client_id         INTEGER,
    to_email          VARCHAR(255) NOT NULL,
    subject           VARCHAR(500),
    provider          VARCHAR(20),
    status            VARCHAR(20) NOT NULL,
    error_message     TEXT,
    attempt_number    INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number >= 1),
    payload_cache     JSONB,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    sent_at           TIMESTAMP WITH TIME ZONE,
    retry_after       TIMESTAMP WITH TIME ZONE,

    CONSTRAINT ck_email_send_log_status
        CHECK (status IN ('sending','sent','failed','retry_scheduled','skipped_idempotent','escalated')),
    CONSTRAINT ck_email_send_log_provider
        CHECK (provider IS NULL OR provider IN ('brevo','zoho','skipped','unknown'))
);

-- Retry worker lookup: failed rows ready for retry
CREATE INDEX IF NOT EXISTS ix_email_send_log_retry
    ON email_send_log (retry_after, status)
    WHERE status = 'failed' AND retry_after IS NOT NULL;

-- Stale-sending detection: rows stuck mid-flight
CREATE INDEX IF NOT EXISTS ix_email_send_log_sending
    ON email_send_log (created_at)
    WHERE status = 'sending';

-- Daily report aggregation (counts per type+status per 24h)
CREATE INDEX IF NOT EXISTS ix_email_send_log_type_status_time
    ON email_send_log (email_type, status, created_at DESC);

-- Dashboard queries: per-recipient timeline
CREATE INDEX IF NOT EXISTS ix_email_send_log_recipient
    ON email_send_log (to_email, created_at DESC);

-- Per-practice / per-client correlation
CREATE INDEX IF NOT EXISTS ix_email_send_log_practice
    ON email_send_log (practice_id, created_at DESC)
    WHERE practice_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_email_send_log_client
    ON email_send_log (client_id, created_at DESC)
    WHERE client_id IS NOT NULL;

-- Seed kill-switch setting for new email-health cron (defaults to enabled).
-- Follows the existing pattern used by 114_compliance_alerts.sql.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'system_settings') THEN
        INSERT INTO system_settings (key, value, updated_at) VALUES
            ('email_health_monitor_enabled', 'true', NOW())
        ON CONFLICT (key) DO NOTHING;
    END IF;
END$$;

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_email_send_log_client;
DROP INDEX IF EXISTS ix_email_send_log_practice;
DROP INDEX IF EXISTS ix_email_send_log_recipient;
DROP INDEX IF EXISTS ix_email_send_log_type_status_time;
DROP INDEX IF EXISTS ix_email_send_log_sending;
DROP INDEX IF EXISTS ix_email_send_log_retry;
DROP TABLE IF EXISTS email_send_log;

-- ============================================================
-- 114_compliance_alerts.sql
-- Persistent compliance alerts + settings seeds
-- Date: 2026-04-18
-- Spec: docs/superpowers/specs/2026-04-18-backend-compliance-intel-e2e-design.md
--
-- Replaces the in-memory AlertGeneratorService.alerts dict.
-- Each row is a business-domain alert; delivery trace lives in
-- notification_log (m111) via the ref convention
-- `compliance_alert:<alert_id>:<channel>`.
-- ============================================================

CREATE TABLE IF NOT EXISTS compliance_alerts (
    alert_id            TEXT PRIMARY KEY,
    client_id           INTEGER NOT NULL REFERENCES clients(id),
    category            TEXT NOT NULL,
    severity            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    deadline            DATE NOT NULL,
    days_until          INTEGER NOT NULL,
    compliance_item_ref TEXT,
    dedup_key           TEXT NOT NULL,
    message_it          TEXT,
    message_en          TEXT,
    message_id          TEXT,
    suggested_action    TEXT,
    estimated_cost_idr  BIGINT,
    evidence_refs       JSONB DEFAULT '[]',
    nb2_ref             TEXT,
    upgrade_count       INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at             TIMESTAMPTZ,
    acknowledged_at     TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,

    CONSTRAINT ck_compliance_alerts_severity
        CHECK (severity IN ('info','warning','urgent','critical')),
    CONSTRAINT ck_compliance_alerts_status
        CHECK (status IN ('pending','sent','acknowledged','resolved','expired'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_compliance_alerts_dedup_active
    ON compliance_alerts (dedup_key)
    WHERE status IN ('pending','sent','acknowledged');

CREATE INDEX IF NOT EXISTS ix_compliance_alerts_client
    ON compliance_alerts (client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_compliance_alerts_deadline
    ON compliance_alerts (deadline) WHERE status != 'resolved';

CREATE INDEX IF NOT EXISTS ix_compliance_alerts_category_sev
    ON compliance_alerts (category, severity, created_at DESC);

-- Seed system_settings keys (autotune + thresholds) IF the table exists.
-- Uses INSERT ... ON CONFLICT DO NOTHING so re-apply is safe.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'system_settings') THEN
        INSERT INTO system_settings (key, value, updated_at) VALUES
            ('compliance_alert_autotune_enabled',                 'false', NOW()),
            ('compliance_alert_autotune_window_days',             '90',    NOW()),
            ('compliance_alert_threshold_urgent_visa_expiry',       '7',   NOW()),
            ('compliance_alert_threshold_urgent_tax_filing',        '7',   NOW()),
            ('compliance_alert_threshold_urgent_lkpm',              '14',  NOW()),
            ('compliance_alert_threshold_urgent_license_renewal',   '14',  NOW()),
            ('compliance_alert_threshold_urgent_permit_renewal',    '14',  NOW()),
            ('compliance_alert_threshold_urgent_regulatory_change', '30',  NOW()),
            ('compliance_alert_threshold_urgent_document_expiry',   '7',   NOW())
        ON CONFLICT (key) DO NOTHING;
    END IF;
END$$;

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_compliance_alerts_category_sev;
DROP INDEX IF EXISTS ix_compliance_alerts_deadline;
DROP INDEX IF EXISTS ix_compliance_alerts_client;
DROP INDEX IF EXISTS ux_compliance_alerts_dedup_active;
DROP TABLE IF EXISTS compliance_alerts;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_name = 'system_settings') THEN
        DELETE FROM system_settings WHERE key LIKE 'compliance_alert_%';
    END IF;
END$$;

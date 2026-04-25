-- 133_legacy_system_settings.sql
--
-- Promote `system_settings` (key/value store) to migrations_v2.
-- Originally created by
-- backend/migrations/migration_062_client_drive_subfolders.sql (old
-- numbered series, not discovered by the v2 runner).
--
-- migrations_v2/114_compliance_alerts.sql already reads this table
-- inside a DO block guarded with an information_schema check, so older
-- migrations apply cleanly even on a CI DB without it. But the
-- compliance_alerts router tests expect it to exist for INSERT/UPDATE
-- of the `compliance_alert_autotune_enabled` kill-switch.
--
-- Idempotent. No-op on prod (already in this shape).

CREATE TABLE IF NOT EXISTS system_settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- === ROLLBACK ===
DROP TABLE IF EXISTS system_settings;

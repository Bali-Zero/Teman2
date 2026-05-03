-- 135_legacy_notification_prefs.sql
--
-- Promote `notification_prefs` to migrations_v2. Originally created by
-- backend/migrations/migration_110_notification_prefs.py (old-style
-- Python migration not discovered by the v2 runner).
--
-- alert_dispatcher.AlertDispatcher reads this table to decide whether a
-- given client wants compliance-alert dispatch on email/whatsapp.
-- Default behavior on missing pref = unconditional team channel,
-- per-client = controlled by these flags.
--
-- Idempotent. No-op on prod (already in this shape).

CREATE TABLE IF NOT EXISTS notification_prefs (
    user_id       UUID PRIMARY KEY,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    wa_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    wa_phone      VARCHAR(20),
    updated_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- === ROLLBACK ===
DROP TABLE IF EXISTS notification_prefs;

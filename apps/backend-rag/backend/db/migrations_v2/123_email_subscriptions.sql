-- ============================================================
-- 123_email_subscriptions.sql
-- Brevo drip scheduler for homepage apps.
-- Date: 2026-04-20
--
-- Visa Clock emits 5 reminders per lead (D-60/30/14/7/1 before visa expiry).
-- Visa Match emits 1 pre-arrival nudge if expected_arrival_date provided.
-- KBLI Builder / Tax Gap / Zoning Check may add their own drips later.
--
-- We need a single scheduler table that: (a) decouples template scheduling
-- from business tables, (b) supports one-click unsubscribe with a token,
-- (c) allows a single cron to fan out all due emails.
--
-- Companion (renumbered 120 → 123):
--   backend/services/notifications/funnel_email/scheduler.py
--   backend/app/routers/funnel_email.py — /unsubscribe/{token}, /fire-due
-- ============================================================

CREATE TABLE IF NOT EXISTS email_subscriptions (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL,
    app                 VARCHAR(32) NOT NULL,
    context_hash        VARCHAR(20) NOT NULL,
    trigger_type        VARCHAR(32) NOT NULL,
    next_fire_at        TIMESTAMP WITH TIME ZONE,
    fired_count         INT NOT NULL DEFAULT 0,
    unsubscribed        BOOLEAN NOT NULL DEFAULT FALSE,
    unsubscribe_token   VARCHAR(32) NOT NULL UNIQUE,
    payload             JSONB,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE email_subscriptions IS
    'Scheduler for homepage-app drip emails. Cron fires rows where next_fire_at <= NOW() AND NOT unsubscribed.';

COMMENT ON COLUMN email_subscriptions.trigger_type IS
    'e.g. visa_clock_d60, visa_clock_d30, visa_clock_d14, visa_clock_d7, visa_clock_d1, visa_match_prearrival_d7.';

COMMENT ON COLUMN email_subscriptions.payload IS
    'Snapshot of template variables at scheduling time. Self-contained so a template rename does not break scheduled sends.';

-- Scheduler hot path: only look at rows due and active.
CREATE INDEX IF NOT EXISTS idx_email_subs_due
    ON email_subscriptions (next_fire_at)
    WHERE unsubscribed = FALSE AND next_fire_at IS NOT NULL;

-- One-click unsubscribe + dedup: find all rows for an email+app.
CREATE INDEX IF NOT EXISTS idx_email_subs_email_app
    ON email_subscriptions (email, app);

-- Token lookup is unique already but ensure query planner uses it.
CREATE INDEX IF NOT EXISTS idx_email_subs_unsub_token
    ON email_subscriptions (unsubscribe_token);

-- updated_at trigger so scheduler updates are auditable.
CREATE OR REPLACE FUNCTION set_email_subs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_email_subs_updated_at ON email_subscriptions;
CREATE TRIGGER trg_email_subs_updated_at
    BEFORE UPDATE ON email_subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_email_subs_updated_at();

-- === ROLLBACK ===
DROP TRIGGER IF EXISTS trg_email_subs_updated_at ON email_subscriptions;
DROP FUNCTION IF EXISTS set_email_subs_updated_at;
DROP INDEX IF EXISTS idx_email_subs_unsub_token;
DROP INDEX IF EXISTS idx_email_subs_email_app;
DROP INDEX IF EXISTS idx_email_subs_due;
DROP TABLE IF EXISTS email_subscriptions;

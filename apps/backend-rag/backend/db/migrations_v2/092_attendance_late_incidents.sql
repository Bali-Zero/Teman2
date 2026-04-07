-- Migration 092: Attendance late-incident state machine
--
-- Tracks every clock_in that arrives at or after 09:40 Bali time as a discrete
-- incident with a state machine:
--
--     AWAITING_REPLY -> REMINDER_SENT -> ESCALATED
--                  \-> RESOLVED       (reply received before reminder)
--                   \-> RESOLVED_LATE (reply received after reminder)
--
-- A signed reply_token allows the team member to submit a reason via the HR
-- portal without authentication (the token IS the auth).
--
-- Idempotent: every CREATE uses IF NOT EXISTS / OR REPLACE so re-running the
-- migration on a database where the table was applied manually (e.g. via
-- backend/migrations/migration_092_attendance_late_incidents.py before the v2
-- loader was wired up) is safe.
--
-- The pgcrypto extension is required for gen_random_uuid().

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS attendance_late_incidents (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                       VARCHAR(255) NOT NULL,
    full_name                   VARCHAR(255),
    late_date                   DATE NOT NULL,
    checkin_time                TIMESTAMPTZ NOT NULL,
    state                       VARCHAR(20) NOT NULL DEFAULT 'AWAITING_REPLY'
                                CHECK (state IN (
                                    'AWAITING_REPLY',
                                    'REMINDER_SENT',
                                    'ESCALATED',
                                    'RESOLVED',
                                    'RESOLVED_LATE'
                                )),
    first_email_sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reminder_sent_at            TIMESTAMPTZ,
    ultimatum_sent_at           TIMESTAMPTZ,
    reply_received_at           TIMESTAMPTZ,
    reply_content               TEXT,
    reply_token                 VARCHAR(64) NOT NULL UNIQUE,
    responsible_manager_email   VARCHAR(255),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_email_late_date UNIQUE (email, late_date)
);

-- Hot path for the escalation cron: filter by state, order by send time.
CREATE INDEX IF NOT EXISTS idx_late_incidents_state_sent
    ON attendance_late_incidents (state, first_email_sent_at)
    WHERE state IN ('AWAITING_REPLY', 'REMINDER_SENT');

-- Lookup by token (reply form). The UNIQUE constraint already creates an
-- index but a dedicated one keeps the query plan tight.
CREATE INDEX IF NOT EXISTS idx_late_incidents_token
    ON attendance_late_incidents (reply_token);

-- Daily digest scan: recent activity by date.
CREATE INDEX IF NOT EXISTS idx_late_incidents_date
    ON attendance_late_incidents (late_date DESC);

-- Trigger to keep updated_at fresh on any UPDATE.
CREATE OR REPLACE FUNCTION trg_attendance_late_incidents_touch()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS attendance_late_incidents_touch
    ON attendance_late_incidents;

CREATE TRIGGER attendance_late_incidents_touch
    BEFORE UPDATE ON attendance_late_incidents
    FOR EACH ROW EXECUTE FUNCTION trg_attendance_late_incidents_touch();

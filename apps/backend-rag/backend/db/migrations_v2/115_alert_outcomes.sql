-- ============================================================
-- 115_alert_outcomes.sql
-- Per-alert outcome tracking for predictive feedback loop
-- Date: 2026-04-18
-- Depends on: 114_compliance_alerts
--
-- Each row records how the team reacted to an alert (acted, dismissed,
-- or expired). Weekly AlertFeedback.retrain job aggregates these to
-- adjust severity thresholds per category.
-- ============================================================

CREATE TABLE IF NOT EXISTS alert_outcomes (
    outcome_id   BIGSERIAL PRIMARY KEY,
    alert_id     TEXT NOT NULL REFERENCES compliance_alerts(alert_id) ON DELETE CASCADE,
    outcome      TEXT NOT NULL,
    actioned_by  TEXT,
    actioned_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note         TEXT,
    metadata     JSONB DEFAULT '{}',

    CONSTRAINT ck_alert_outcomes_outcome
        CHECK (outcome IN ('dismissed','acted','expired'))
);

CREATE INDEX IF NOT EXISTS ix_alert_outcomes_alert
    ON alert_outcomes (alert_id);

CREATE INDEX IF NOT EXISTS ix_alert_outcomes_time
    ON alert_outcomes (actioned_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_alert_outcomes_time;
DROP INDEX IF EXISTS ix_alert_outcomes_alert;
DROP TABLE IF EXISTS alert_outcomes;

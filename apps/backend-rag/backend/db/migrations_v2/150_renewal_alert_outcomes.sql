-- 150_renewal_alert_outcomes.sql
--
-- Outcome tracking for renewal_alerts (created in migration_007).
-- Captures whether an alert led to action: by team, client renewal, ignored, or expired.
-- See: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4 + §7
--
-- Initial backfill: scripts/backfill_renewal_outcomes.py infers outcomes from
-- historical practices.status transitions and records observed_by='team_member'
-- for all backfilled rows. From Sprint 2 onward, Cell writes observed_by='cell'.

CREATE TABLE IF NOT EXISTS renewal_alert_outcomes (
    id BIGSERIAL PRIMARY KEY,
    alert_id INTEGER NOT NULL REFERENCES renewal_alerts(id) ON DELETE CASCADE,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'acted_by_team',
        'client_renewed',
        'client_ignored',
        'expired_no_action'
    )),
    outcome_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    observed_by TEXT NOT NULL CHECK (observed_by IN ('cell', 'team_member')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_alert
    ON renewal_alert_outcomes(alert_id);

CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_outcome
    ON renewal_alert_outcomes(outcome);

CREATE INDEX IF NOT EXISTS idx_renewal_alert_outcomes_outcome_at
    ON renewal_alert_outcomes(outcome_at);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_outcome_at;
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_outcome;
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_alert;
DROP TABLE IF EXISTS renewal_alert_outcomes;

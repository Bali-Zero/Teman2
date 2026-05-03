-- ============================================================
-- 150_renewal_alert_outcomes.sql
--
-- Outcome tracking for renewal_alerts (created in legacy migration_007).
-- Captures whether an alert led to action: by team, client renewal, ignored, or expired.
-- See: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4 + §7
--
-- Initial backfill: scripts/backfill_renewal_outcomes.py infers outcomes from
-- historical practices.status transitions and records observed_by='team_member'
-- for all backfilled rows. From Sprint 2 onward, Cell writes observed_by='cell'.
--
-- The `renewal_alerts` table predates migrations_v2 (created in legacy
-- migration_007 + 080b). Fresh CI test envs may not have it — the migration
-- no-ops in that case. In prod the table exists and the block executes
-- normally. Idempotent. Same pattern as m125_invoices_unique_practice.sql.
--
-- Squawk lint compliance:
--   * alert_id BIGINT: avoids 32-bit overflow warning
--   * SET timeouts inside DO block: bounds migration locks
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'renewal_alerts'
    ) THEN
        RAISE NOTICE 'Migration 150: renewal_alerts table not present; skipping (CI/fresh schema).';
        RETURN;
    END IF;

    PERFORM set_config('lock_timeout', '5s', true);
    PERFORM set_config('statement_timeout', '30s', true);

    CREATE TABLE IF NOT EXISTS renewal_alert_outcomes (
        id BIGSERIAL PRIMARY KEY,
        alert_id BIGINT NOT NULL REFERENCES renewal_alerts(id) ON DELETE CASCADE,
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
END $$;

-- === ROLLBACK ===
-- Rollback only — migration_manager strips this section before apply.
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_outcome_at;
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_outcome;
DROP INDEX IF EXISTS idx_renewal_alert_outcomes_alert;
DROP TABLE IF EXISTS renewal_alert_outcomes;

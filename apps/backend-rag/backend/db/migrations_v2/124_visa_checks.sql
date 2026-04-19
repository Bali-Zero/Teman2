-- ============================================================
-- 124_visa_checks.sql
-- Persistence for Visa Check app (Clock + Match).
-- Date: 2026-04-20
--
-- First of 4 homepage apps replacing the decorative FunnelFeature sections.
-- Two branches in a single table:
--   branch='clock' — user already in Indonesia, knows visa_type + entry_date.
--   branch='match' — user planning, 4-step wizard output.
--
-- Both branches produce a shareable /visa/<branch>/<hash> URL that renders
-- from this table on every view. Append-only for result rows; edits only to
-- view_count / share_count.
--
-- Schema design: single table with nullable columns per branch. Common fields
-- dominate (hash, branch, client_fp, view_count, share_count, created_at);
-- a JOIN on hash would be redundant.
--
-- Companion (renumbered 121 → 124):
--   backend/services/visa_check/ — catalogue, clock, match_tree, repository
--   backend/app/routers/visa_check.py — 5 endpoints
-- ============================================================

CREATE TABLE IF NOT EXISTS visa_checks (
    hash                    VARCHAR(20) PRIMARY KEY,
    branch                  VARCHAR(8)  NOT NULL
                            CHECK (branch IN ('clock', 'match')),
    client_fp               VARCHAR(32),
    view_count              INT NOT NULL DEFAULT 0,
    share_count             INT NOT NULL DEFAULT 0,
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Clock branch (NULL when branch='match')
    visa_type               VARCHAR(16),
    entry_date              DATE,
    expiry_date             DATE,
    extensions_possible     INT,
    extension_days          INT,

    -- Match branch (NULL when branch='clock')
    nationality             VARCHAR(3),
    purpose                 VARCHAR(32),
    duration_months         INT,
    budget_band             VARCHAR(16),
    recommended_visa        VARCHAR(16),
    recommendation_reason   TEXT,
    pre_arrival_steps       JSONB,
    alternatives            JSONB,
    expected_arrival_date   DATE,
    estimated_cost_idr      BIGINT
);

COMMENT ON TABLE visa_checks IS
    'Visa Check app result store. One row per hash = one shareable /visa/<branch>/<hash> page. Clock and Match branches share the same table with nullable per-branch columns.';

COMMENT ON COLUMN visa_checks.branch IS
    'clock = user already in Indonesia with known visa; match = user planning, went through 4-step wizard.';

COMMENT ON COLUMN visa_checks.hash IS
    '16-char URL-safe nanoid. Used as public identifier in /visa/<branch>/<hash>.';

COMMENT ON COLUMN visa_checks.estimated_cost_idr IS
    'Match-only. Total cost (Bali Zero fee + gov fees) in IDR. SOURCE: PricingTool; never hardcoded.';

-- Branch analytics: time-series per branch for KPI dashboards.
CREATE INDEX IF NOT EXISTS idx_visa_checks_branch_created
    ON visa_checks (branch, created_at DESC);

-- Clock reminder cron: rows expiring within 60 days.
CREATE INDEX IF NOT EXISTS idx_visa_checks_expiry_clock
    ON visa_checks (expiry_date)
    WHERE branch = 'clock' AND expiry_date IS NOT NULL;

-- Idempotent re-submission guard (24h window).
CREATE INDEX IF NOT EXISTS idx_visa_checks_fp_recent
    ON visa_checks (client_fp, created_at DESC)
    WHERE client_fp IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_visa_checks_fp_recent;
DROP INDEX IF EXISTS idx_visa_checks_expiry_clock;
DROP INDEX IF EXISTS idx_visa_checks_branch_created;
DROP TABLE IF EXISTS visa_checks;

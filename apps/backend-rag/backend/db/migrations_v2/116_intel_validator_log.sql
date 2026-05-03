-- ============================================================
-- 116_intel_validator_log.sql
-- Intel 3-tier validator audit log
-- Date: 2026-04-18
--
-- Each tier of IntelValidators writes one row per staging_id with its
-- pass/fail verdict, contributed score, and details (URL status, matched
-- entities, regex errors). Used by /api/intel/staging/{id}/validation
-- to reconstruct the full validation story for admin review.
-- ============================================================

CREATE TABLE IF NOT EXISTS intel_validator_log (
    log_id          BIGSERIAL PRIMARY KEY,
    -- No FK: staging records may be quarantined or purged; log must outlive them.
    staging_id      BIGINT NOT NULL,
    validator_tier  TEXT NOT NULL,
    result          TEXT NOT NULL,
    score           NUMERIC(3,2),
    details         JSONB DEFAULT '{}',
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_intel_validator_log_tier
        CHECK (validator_tier IN ('regex','citation','kg_crossref')),
    CONSTRAINT ck_intel_validator_log_result
        CHECK (result IN ('pass','fail','soft_fail','skip'))
);

CREATE INDEX IF NOT EXISTS ix_intel_validator_log_staging
    ON intel_validator_log (staging_id, checked_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_intel_validator_log_staging;
DROP TABLE IF EXISTS intel_validator_log;

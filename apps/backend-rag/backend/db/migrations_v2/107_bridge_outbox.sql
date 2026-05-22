-- 107_bridge_outbox.sql
-- Promotion of legacy migration_107_bridge_outbox.py into the active v2 runner.
--
-- WHY: closes the schema-source-of-truth gap. The legacy Python migration was
-- applied manually on prod and recorded only in `_schema_versions`. Fresh CI
-- DBs and reproducible bootstraps must be able to recreate `bridge_outbox` from
-- migrations_v2/ alone — otherwise migration 192 (jsonb repair) fails on a
-- missing table.
--
-- IDEMPOTENT BY DESIGN: production may already have this table from the
-- legacy/manual path. All DDL uses IF NOT EXISTS.
--
-- HIDDEN TRAP (Codex panelist): the v2 runner computes pending migrations from
-- `_schema_versions.migration_number`, not from `schema_migrations`. On prod
-- with legacy `_schema_versions(107)` already present, this file is SKIPPED by
-- number. Tracker convergence is handled by the companion migration
-- `194_reconcile_107_bridge_outbox_tracking.sql`.
--
-- TYPE FIDELITY: id is BIGSERIAL to match the legacy migration_107_bridge_outbox.py
-- verified empirically 2026-05-23. Diverging to SERIAL would create cross-
-- environment schema drift on fresh DBs while prod stays BIGSERIAL.

CREATE TABLE IF NOT EXISTS bridge_outbox (
    id BIGSERIAL PRIMARY KEY,
    type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbox_id ON bridge_outbox (id);
CREATE INDEX IF NOT EXISTS idx_outbox_type ON bridge_outbox (type);
CREATE INDEX IF NOT EXISTS idx_outbox_created_at ON bridge_outbox (created_at);

-- === ROLLBACK ===
-- Intentionally no-op. This is a legacy promotion: on production the table
-- predates the v2 row and contains live bridge event payloads. A generic CLI
-- rollback would destroy event history that the WR3 bridge consumer relies on
-- for replay. Any rollback must be a separate, named migration with explicit
-- operator review.
SELECT 1;

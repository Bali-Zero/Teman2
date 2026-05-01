-- ============================================================
-- 149_client_segments.sql
--
-- Tier segmentation table for Era Post-Agentica vertical-slice renewals.
-- See: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.4
--
-- Tier 1 = high-value (LTV >= $5000), Tier 2 = medium ($2000-4999), Tier 3 = low (<$2000).
-- LTV computed as sum of practices.total_invoiced_idr (where status='completed') converted IDR->USD.
-- Initial population done by scripts/compute_client_segments.py post-deploy.
-- Weekly refresh handled by Cell skill measure_conversion from Sprint 4 onward.
--
-- The `clients` table predates migrations_v2 (created in legacy migration_007).
-- Fresh CI test envs may not have it — the migration no-ops in that case.
-- In prod the table exists and the block executes normally. Idempotent.
-- Same pattern as m125_invoices_unique_practice.sql.
--
-- Squawk lint compliance:
--   * client_id BIGINT: avoids 32-bit overflow warning
--   * tier INTEGER (not SMALLINT): avoids 16-bit overflow warning
--   * SET timeouts inside DO block: bounds migration locks
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'clients'
    ) THEN
        RAISE NOTICE 'Migration 149: clients table not present; skipping (CI/fresh schema).';
        RETURN;
    END IF;

    PERFORM set_config('lock_timeout', '5s', true);
    PERFORM set_config('statement_timeout', '30s', true);

    CREATE TABLE IF NOT EXISTS client_segments (
        client_id BIGINT PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
        tier INTEGER NOT NULL CHECK (tier IN (1, 2, 3)),
        lifetime_value_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
        computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_client_segments_tier
        ON client_segments(tier);

    CREATE UNIQUE INDEX IF NOT EXISTS uq_client_segments_client
        ON client_segments(client_id);

    CREATE INDEX IF NOT EXISTS idx_client_segments_computed_at
        ON client_segments(computed_at);
END $$;

-- === ROLLBACK ===
-- Rollback only — migration_manager.split_migration_sql strips this section
-- before apply, so Squawk warnings on DROP statements have no production impact.
DROP INDEX IF EXISTS idx_client_segments_computed_at;
DROP INDEX IF EXISTS uq_client_segments_client;
DROP INDEX IF EXISTS idx_client_segments_tier;
DROP TABLE IF EXISTS client_segments;

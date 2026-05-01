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
-- Squawk lint: brand-new empty table — all inline ignores legitimate.
-- INTEGER client_id: matches existing clients.id type (FK constraint).
-- SMALLINT tier: 3 values total (1/2/3), no risk of overflow.

-- squawk-ignore: prefer-bigint-over-int, prefer-bigint-over-smallint
CREATE TABLE IF NOT EXISTS client_segments (
    client_id INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    tier SMALLINT NOT NULL CHECK (tier IN (1, 2, 3)),
    lifetime_value_usd NUMERIC(12, 2) NOT NULL DEFAULT 0,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_client_segments_tier
    ON client_segments(tier);

-- squawk-ignore: require-concurrent-index-creation
CREATE UNIQUE INDEX IF NOT EXISTS uq_client_segments_client
    ON client_segments(client_id);

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_client_segments_computed_at
    ON client_segments(computed_at);

-- === ROLLBACK ===
-- Rollback section: drop in reverse order. Empty table at this point so
-- ACCESS EXCLUSIVE locks have no contention impact.
-- squawk-ignore: disallowed-unique-constraint, ban-drop-table
DROP INDEX IF EXISTS idx_client_segments_computed_at;
DROP INDEX IF EXISTS uq_client_segments_client;
DROP INDEX IF EXISTS idx_client_segments_tier;
DROP TABLE IF EXISTS client_segments;

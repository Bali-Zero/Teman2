-- 206_wr2_topic_type_log.sql
-- WR2 anti-sameness (constitution Art 10.6): persist one row per rendered
-- carousel so the draft generator can enforce "same-domain carousels must
-- differ in register AND image-mode" instead of treating it as aspirational.
--
-- Written at the `rendered` transition (the real terminal status in Pipeline B;
-- there is NO software publish-to-IG event -- Damar publishes manually from the
-- Canva design). published_at/deleted_at are nullable and added now (zero cost)
-- so a future "count only published / prune rejected" semantic switch needs no
-- new migration.
-- === FORWARD ===
CREATE TABLE IF NOT EXISTS topic_type_log (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    draft_id        UUID NOT NULL,
    domain          TEXT NOT NULL,         -- visa|tax|property|regulatory|health|brand|unknown
    register        TEXT,                  -- the 7-tone register
    dominant_mode   TEXT,                  -- one of the 9 image-style modes (or 'mixed'/'unknown')
    layout_family   TEXT,                  -- derived from archetype/slides (nullable)
    archetype       TEXT,                  -- nullable (from slides_json if present)
    topic           TEXT,                  -- denormalized for human inspection
    rendered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,           -- NULL until a real publish signal exists (panel B)
    deleted_at      TIMESTAMPTZ            -- soft-delete to prune Damar-rejected rows (panel B)
);

-- idempotency: one row per draft (re-render must not duplicate)
CREATE UNIQUE INDEX IF NOT EXISTS ux_topic_type_log_draft_id ON topic_type_log (draft_id);

-- the hot query: last-N by domain, newest first
CREATE INDEX IF NOT EXISTS ix_topic_type_log_domain_time ON topic_type_log (domain, rendered_at DESC);

COMMENT ON TABLE topic_type_log IS 'WR2 anti-sameness ledger (constitution Art 10.6). One row per carousel at status=rendered: domain + dominant register + dominant image-mode + layout_family. Consumed by wr2_draft_generator.fetch_recent_same_domain to steer/reject monotonous same-domain carousels. Best-effort write -- never gates the render path.';

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_topic_type_log_domain_time;
DROP INDEX IF EXISTS ux_topic_type_log_draft_id;
DROP TABLE IF EXISTS topic_type_log;

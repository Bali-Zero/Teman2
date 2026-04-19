-- ============================================================
-- 122_lead_intents.sql
-- Homepage 4-app lead capture + WhatsApp handoff.
-- Date: 2026-04-20
--
-- Four homepage apps (visa_clock, visa_match, kbli_decoder, kbli_builder,
-- tax_gap, zoning_check) funnel users to a WhatsApp handoff. Every handoff
-- persists its context so the */5min cron matcher can correlate the
-- inbound WA message with the originating app session and backfill
-- clients.lead_source + clients.lead_metadata accordingly.
--
-- CRO audit 2026-04-19 found 2 website leads / 90 days vs 420 from WhatsApp
-- with no attribution possible — without lead_intents, the homepage apps
-- would inherit the same opacity problem.
--
-- NOTE: a Python version of this migration exists at
-- backend/migrations/migration_119_lead_intents.py but the Fly
-- migration runner only scans backend/db/migrations_v2/*.sql, so this
-- SQL file is the canonical source. Renumbered 119 → 122 because
-- 119_llm_cost_recommendations.sql already occupies 119 in v2.
-- ============================================================

CREATE TABLE IF NOT EXISTS lead_intents (
    id                  VARCHAR(20) PRIMARY KEY,
    source              VARCHAR(32) NOT NULL,
    context             JSONB NOT NULL,
    utm                 JSONB,
    fingerprint         VARCHAR(32),
    whatsapp_url        TEXT NOT NULL,
    matched_client_id   VARCHAR(20),
    matched_at          TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMP WITH TIME ZONE NOT NULL
);

COMMENT ON TABLE lead_intents IS
    'Homepage 4-app lead capture. Each row = one WhatsApp handoff from visa/kbli/tax/zoning app. Matcher cron correlates on inbound WA.';

COMMENT ON COLUMN lead_intents.source IS
    'App that generated the handoff: visa_clock | visa_match | kbli_decoder | kbli_builder | tax_gap | zoning_check.';

COMMENT ON COLUMN lead_intents.context IS
    'App-specific payload (e.g. visa_clock: {visa_type, entry_date, expiry_date}).';

COMMENT ON COLUMN lead_intents.matched_client_id IS
    'Backfilled by */5min matcher cron when inbound WhatsApp arrives within 30min of handoff and phone matches a client.';

-- Hot path for matcher: unmatched intents that have not expired yet.
CREATE INDEX IF NOT EXISTS idx_lead_intents_unmatched_expiring
    ON lead_intents (created_at DESC)
    WHERE matched_client_id IS NULL;

-- Analytics rollup: lead count per source per day.
CREATE INDEX IF NOT EXISTS idx_lead_intents_source_created
    ON lead_intents (source, created_at DESC);

-- TTL purge helper: find expired rows fast.
CREATE INDEX IF NOT EXISTS idx_lead_intents_expires
    ON lead_intents (expires_at)
    WHERE matched_client_id IS NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_lead_intents_expires;
DROP INDEX IF EXISTS idx_lead_intents_source_created;
DROP INDEX IF EXISTS idx_lead_intents_unmatched_expiring;
DROP TABLE IF EXISTS lead_intents;

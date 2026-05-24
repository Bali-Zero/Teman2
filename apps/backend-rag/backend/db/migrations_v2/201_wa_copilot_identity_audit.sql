-- migration 201_wa_copilot_identity_audit
-- WA Copilot identity resolver v1.0 support: lid↔phone bridge map +
-- per-message audit trail + pg_trgm GIN index on clients.full_name +
-- type fix for whatsapp_message_context.team_member_id (BIGINT → TEXT,
-- because team_members.id is VARCHAR(36)).
--
-- Sibling of migration 200 (commit 49af40620). Unblocks
-- backend/services/wa_copilot/identity_resolver.py implementation.
--
-- Plan reference: Sprint 1 S1.3 identity resolver v1, Plan agent
-- empirical validation 2026-05-25 04:15+08 vs production schema.

BEGIN;

-- A. team_member_id type fix (migration 200 bug — VARCHAR(36) source)
-- whatsapp_message_context.team_member_id is empty post-200 (no writes
-- yet), so type change is safe even with running cron.
ALTER TABLE whatsapp_message_context
    ALTER COLUMN team_member_id TYPE TEXT USING team_member_id::TEXT;

-- B. LID↔phone bridge map (initially empty; populated by signal #1
-- successes that also have counterpart_lid, plus human review)
CREATE TABLE IF NOT EXISTS wa_lid_phone_map (
    lid TEXT PRIMARY KEY,
    phone_e164 TEXT NOT NULL,
    client_id BIGINT REFERENCES clients(id),
    confidence NUMERIC(3, 2) CHECK (confidence BETWEEN 0 AND 1),
    source TEXT NOT NULL CHECK (source IN ('co_seen', 'manual', 'baileys_metadata', 'imported')),
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_confirmed_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wa_lid_phone ON wa_lid_phone_map (phone_e164);
CREATE INDEX IF NOT EXISTS idx_wa_lid_client ON wa_lid_phone_map (client_id) WHERE client_id IS NOT NULL;

-- C. Per-message identity resolution audit (every decision logged,
-- including non-matches in review band 0.40-0.70 for human queue)
CREATE TABLE IF NOT EXISTS whatsapp_identity_audit (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    attempted_method TEXT NOT NULL,
    matched_client_id BIGINT REFERENCES clients(id),
    confidence NUMERIC(3, 2) CHECK (confidence BETWEEN 0 AND 1),
    signal_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision TEXT NOT NULL CHECK (decision IN (
        'applied', 'skipped_low_conf', 'ambiguous', 'needs_review',
        'already_resolved_skip', 'no_signal_match'
    )),
    resolver_version TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wa_identity_audit_decision
    ON whatsapp_identity_audit (decision, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wa_identity_audit_client
    ON whatsapp_identity_audit (matched_client_id, created_at DESC)
    WHERE matched_client_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_wa_identity_audit_message
    ON whatsapp_identity_audit (message_id);

-- D. pg_trgm GIN index on clients.full_name for fuzzy match perf
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_clients_full_name_trgm
    ON clients USING gin (full_name gin_trgm_ops);

COMMIT;

-- === ROLLBACK ===
-- Inline rollback per W42 lint. Drops 2 new tables + GIN index + reverts
-- team_member_id TEXT → BIGINT (lossless if not yet populated; if any
-- non-empty rows exist with VARCHAR(36) UUIDs, will fail — caller must
-- TRUNCATE column first).
-- BEGIN;
--
-- DROP INDEX IF EXISTS idx_clients_full_name_trgm;
-- DROP INDEX IF EXISTS idx_wa_identity_audit_message;
-- DROP INDEX IF EXISTS idx_wa_identity_audit_client;
-- DROP INDEX IF EXISTS idx_wa_identity_audit_decision;
-- DROP TABLE IF EXISTS whatsapp_identity_audit;
-- DROP INDEX IF EXISTS idx_wa_lid_client;
-- DROP INDEX IF EXISTS idx_wa_lid_phone;
-- DROP TABLE IF EXISTS wa_lid_phone_map;
-- ALTER TABLE whatsapp_message_context
--     ALTER COLUMN team_member_id TYPE BIGINT USING NULLIF(team_member_id, '')::BIGINT;
--
-- COMMIT;

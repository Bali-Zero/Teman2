-- Migration 250: Visa Oracle engine — bitemporal rule-pack substrate (PR4)
--
-- Purpose:
--   The persistence read-substrate for the signed Visa Oracle rule packs the
--   evaluator consumes (PR1 models / PR2b bundle.py loader / PR3 evaluator, all
--   live on main). Two tables + the append-only guard:
--     * visa_rule_packs        — the immutable, Ed25519-signed pack envelope
--                                (payload stays an opaque JSONB blob; it is
--                                verified/compiled in Python by bundle.py +
--                                compiler.py, NEVER queried by SQL predicate).
--     * visa_ruleset_activations — the bitemporal activation ledger. Which pack
--                                is "active" is expressed as two independent
--                                clocks: legal_period (when the rule set is
--                                legally in force) and system_period (when Visa
--                                Oracle's system considered it current). A GiST
--                                EXCLUDE constraint makes overlapping activations
--                                impossible at the DB level — there is never more
--                                than one active pack per (env,jurisdiction,
--                                domain) at any (effective_at, observed_at).
--   Runtime selection is a pure range-containment join (no ACTIVE/DEPRECATED
--   enum): legal_period @> effective_at AND system_period @> observed_at.
--
-- Source: research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
--   concretization.md section 5 (R1-gated, SURVIVES-WITH-CAVEATS). DDL is the
--   spec's, verbatim, with two deliberate deviations documented below.
--
-- SCOPE (deliberately narrow — read substrate only):
--   The spec's section 5 defines 9 tables. This migration lands ONLY the
--   read/selection substrate (packs + activations). The WRITE substrate
--   (visa_decisions, visa_decision_payloads, visa_price_quotes,
--   visa_consent_receipts, visa_clock_snapshots, visa_public_results,
--   visa_session_exchanges) and visa_source_records land in a LATER migration
--   WITH the SHADOW write-path code that populates them — no dead tables ahead
--   of their writer. Signed pack sources travel inline in the JSONB payload, so
--   no FK dependency is broken by deferring visa_source_records.
--
-- DEVIATIONS from the spec's literal section 5 text:
--   1) ROLLBACK marker uses the ENFORCED padded form (=== ROLLBACK ===)
--      (backend/db/migration_base.py:29 regex, mandatory for migrations > 111);
--      the spec's inline unpadded example would not match and would make the
--      whole file the "forward" section.
--   2) Runtime GRANTs (spec section 5 "Runtime grants") are NOT issued here.
--      They target roles (the FastAPI runtime role, activation role, retention
--      role) that do not exist in the CI/pre-push clone nuzantara_test (owned by
--      the test role), where GRANT ... TO <missing_role> would abort the whole
--      migration. Immutability is already enforced structurally by the
--      append-only trigger below (defense-in-depth, role-independent); the
--      SELECT/INSERT-only grant layer lands in a follow-up migration guarded by
--      role-existence DO-blocks once the runtime role model is confirmed.
--
-- NOTE: backend/db/migration_base.py wraps the forward SQL in a SINGLE
--   transaction. CREATE EXTENSION / CREATE TABLE / CREATE FUNCTION all commit
--   together; on rollback they are undone in FK-safe order. btree_gist is a
--   PG13+ "trusted" extension, so a database owner can create it without
--   superuser; IF NOT EXISTS makes it a no-op where a sibling already added it.

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE visa_rule_packs (
    id                      UUID PRIMARY KEY,
    environment             TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    jurisdiction            CHAR(2) NOT NULL DEFAULT 'ID'
        CHECK (jurisdiction = 'ID'),
    decision_domain         TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA'
        CHECK (decision_domain = 'IMMIGRATION_VISA'),
    sequence                BIGINT NOT NULL CHECK (sequence > 0),
    pack_version            TEXT NOT NULL,
    engine_contract_version TEXT NOT NULL,
    engine_min_version      TEXT NOT NULL,
    engine_max_version      TEXT NOT NULL,
    legal_period            TSTZRANGE NOT NULL,
    protected_header        JSONB NOT NULL,
    payload                 JSONB NOT NULL,
    payload_sha256          BYTEA NOT NULL CHECK (octet_length(payload_sha256) = 32),
    previous_payload_sha256 BYTEA CHECK (
        previous_payload_sha256 IS NULL
        OR octet_length(previous_payload_sha256) = 32
    ),
    signature               BYTEA NOT NULL CHECK (octet_length(signature) = 64),
    signing_key_id          TEXT NOT NULL,
    signed_at               TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
    ),
    UNIQUE (environment, jurisdiction, decision_domain, sequence),
    UNIQUE (payload_sha256)
);

CREATE TABLE visa_ruleset_activations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_pack_id      UUID NOT NULL REFERENCES visa_rule_packs(id),
    environment       TEXT NOT NULL,
    jurisdiction      CHAR(2) NOT NULL DEFAULT 'ID',
    decision_domain   TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA',
    legal_period      TSTZRANGE NOT NULL,
    system_period     TSTZRANGE NOT NULL DEFAULT tstzrange(now(), NULL, '[)'),
    activated_by      TEXT NOT NULL,
    activation_reason TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
    ),
    CHECK (
        NOT isempty(system_period)
        AND lower_inc(system_period)
        AND NOT upper_inc(system_period)
    ),
    EXCLUDE USING gist (
        environment WITH =,
        jurisdiction WITH =,
        decision_domain WITH =,
        legal_period WITH &&,
        system_period WITH &&
    )
);

CREATE INDEX idx_visa_ruleset_activations_pack
    ON visa_ruleset_activations (rule_pack_id);

-- Append-only guard: the signed pack table can only ever be INSERTed into.
-- Any UPDATE or DELETE raises — the sole way to change the active rule set is to
-- INSERT a new pack (higher sequence) and a new activation (the activation
-- ledger closes the prior system_period via UPDATE, which is why the trigger is
-- on visa_rule_packs, NOT on visa_ruleset_activations).
CREATE FUNCTION reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER visa_rule_packs_immutable
BEFORE UPDATE OR DELETE ON visa_rule_packs
FOR EACH ROW EXECUTE FUNCTION reject_visa_immutable_mutation();

-- === ROLLBACK ===
-- FK-safe teardown order: trigger + function first, then activations (FK to
-- packs) before packs. btree_gist is intentionally NOT dropped — it is a shared
-- extension other objects may depend on (spec section 5).
DROP TRIGGER IF EXISTS visa_rule_packs_immutable ON visa_rule_packs;
DROP FUNCTION IF EXISTS reject_visa_immutable_mutation();
DROP INDEX IF EXISTS idx_visa_ruleset_activations_pack;
DROP TABLE IF EXISTS visa_ruleset_activations;
DROP TABLE IF EXISTS visa_rule_packs;

-- Migration 328: visa_types becomes the single Law table of the Visa Oracle
--
-- Owner model (Zero 2026-10-17): two sides only. LAW = one card per visa code,
-- verbatim from the official source, mastered in git
-- (backend/services/visa_engine/families/law/<FAMILY>/<CODE>.json).
-- GUIDE = per-family questions, kept in git, never in this table.
-- This table is the read projection every surface uses (Oracle, Zantara, CRM,
-- knowledge). It is filled family by family by one importer; nobody edits
-- law content here by hand.
--
-- Design ruled after an advisor panel (Astra, Argon, Kimi; Qwen seat 403):
--   * one row per code, `code` stays the key, additive columns only, so every
--     existing reader (UPPER(code), SELECT *) keeps working;
--   * the full verbatim card lives in `law_card` (JSONB), the few values the
--     Guide computes on are typed scalars next to it;
--   * days and months are separate columns, never converted in the schema;
--   * ITAP (KITAP) is not a row: it is the permanent stage of an E-family code,
--     stored in `itap` (NULL until that family's Law step verifies it);
--   * prices are never stored: `price_keys` points into
--     backend/data/bali_zero_official_prices_2026.json;
--   * validity in time is plain dates; the signed engine packs keep their own
--     bitemporal ledger (migrations 250/252).
--
-- Numbered 328: main holds 327, open PRs hold 324/325 (checked 2026-10-17).

SET lock_timeout = '5s';
SET statement_timeout = '60s';

-- visa_types is not created by any numbered migration (production has it from
-- before the ledger). On such a database this is a no-op; on a fresh database
-- (CI, local) it creates the legacy shape so the additive columns below have a
-- table to extend. The shape is the production one: id, code, name, category,
-- requirements, metadata.
CREATE TABLE IF NOT EXISTS visa_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    category VARCHAR,
    requirements TEXT[],
    metadata JSONB
);

ALTER TABLE visa_types
    ADD COLUMN IF NOT EXISTS family              TEXT,
    ADD COLUMN IF NOT EXISTS official_name_id    TEXT,
    ADD COLUMN IF NOT EXISTS permit_class        TEXT,
    ADD COLUMN IF NOT EXISTS is_sold             BOOLEAN,
    ADD COLUMN IF NOT EXISTS price_keys          JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS entry_type          TEXT,
    ADD COLUMN IF NOT EXISTS sponsor             TEXT,
    ADD COLUMN IF NOT EXISTS apply_channel       TEXT,
    ADD COLUMN IF NOT EXISTS initial_stay_days   INTEGER,
    ADD COLUMN IF NOT EXISTS extendable          BOOLEAN,
    ADD COLUMN IF NOT EXISTS max_total_days      INTEGER,
    ADD COLUMN IF NOT EXISTS max_total_months    INTEGER,
    ADD COLUMN IF NOT EXISTS itap                JSONB,
    ADD COLUMN IF NOT EXISTS law_card            JSONB,
    ADD COLUMN IF NOT EXISTS source_url          TEXT,
    ADD COLUMN IF NOT EXISTS page_sha256         TEXT,
    ADD COLUMN IF NOT EXISTS retrieved_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS card_sha256         TEXT,
    ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'TO_VERIFY',
    ADD COLUMN IF NOT EXISTS valid_from          DATE,
    ADD COLUMN IF NOT EXISTS valid_until         DATE,
    ADD COLUMN IF NOT EXISTS superseded_by       TEXT;

-- Re-runnable: each constraint is added only if absent.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_family_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_family_chk CHECK (
        family IS NULL OR family ~ '^(A|B|C|D|F|E[0-9]{2}|BRIDGING|SERVICE)$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_permit_class_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_permit_class_chk CHECK (
        permit_class IS NULL OR permit_class IN
        ('VISA_FREE', 'VOA', 'VISIT_SINGLE', 'VISIT_MULTIPLE', 'ITAS', 'BRIDGING', 'SERVICE'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_price_keys_array_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_price_keys_array_chk CHECK (jsonb_typeof(price_keys) = 'array');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_entry_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_entry_chk CHECK (entry_type IS NULL OR entry_type IN ('SINGLE', 'MULTIPLE'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_sponsor_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_sponsor_chk CHECK (
        sponsor IS NULL OR sponsor IN ('REQUIRED', 'NOT_REQUIRED', 'CONDITIONAL'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_apply_channel_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_apply_channel_chk CHECK (
        apply_channel IS NULL OR apply_channel IN ('OFFSHORE', 'ONSHORE', 'BOTH'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_stay_positive_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_stay_positive_chk CHECK (
        (initial_stay_days IS NULL OR initial_stay_days > 0)
        AND (max_total_days IS NULL OR max_total_days > 0)
        AND (max_total_months IS NULL OR max_total_months > 0));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_one_total_unit_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_one_total_unit_chk CHECK (
        max_total_days IS NULL OR max_total_months IS NULL);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_itap_only_itas_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_itap_only_itas_chk CHECK (itap IS NULL OR permit_class = 'ITAS');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_card_is_object_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_card_is_object_chk CHECK (law_card IS NULL OR jsonb_typeof(law_card) = 'object');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_sha_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_sha_chk CHECK (
        (page_sha256 IS NULL OR page_sha256 ~ '^[0-9a-f]{64}$')
        AND (card_sha256 IS NULL OR card_sha256 ~ '^[0-9a-f]{64}$'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_status_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_status_chk CHECK (verification_status IN ('VERIFIED', 'TO_VERIFY'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_verified_needs_source_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_verified_needs_source_chk CHECK (
        verification_status = 'TO_VERIFY'
        OR (law_card IS NOT NULL AND family IS NOT NULL AND permit_class IS NOT NULL
            AND source_url IS NOT NULL AND page_sha256 IS NOT NULL
            AND retrieved_at IS NOT NULL AND card_sha256 IS NOT NULL));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_validity_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_validity_chk CHECK (
        valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS visa_types_family_idx ON visa_types (family);

-- === ROLLBACK ===

-- Removes only what this migration added; legacy columns and rows are untouched.
DROP INDEX IF EXISTS visa_types_family_idx;
ALTER TABLE visa_types
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_family_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_permit_class_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_price_keys_array_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_entry_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_sponsor_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_apply_channel_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_stay_positive_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_one_total_unit_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_itap_only_itas_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_card_is_object_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_sha_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_status_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_verified_needs_source_chk,
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_validity_chk,
    DROP COLUMN IF EXISTS family,
    DROP COLUMN IF EXISTS official_name_id,
    DROP COLUMN IF EXISTS permit_class,
    DROP COLUMN IF EXISTS is_sold,
    DROP COLUMN IF EXISTS price_keys,
    DROP COLUMN IF EXISTS entry_type,
    DROP COLUMN IF EXISTS sponsor,
    DROP COLUMN IF EXISTS apply_channel,
    DROP COLUMN IF EXISTS initial_stay_days,
    DROP COLUMN IF EXISTS extendable,
    DROP COLUMN IF EXISTS max_total_days,
    DROP COLUMN IF EXISTS max_total_months,
    DROP COLUMN IF EXISTS itap,
    DROP COLUMN IF EXISTS law_card,
    DROP COLUMN IF EXISTS source_url,
    DROP COLUMN IF EXISTS page_sha256,
    DROP COLUMN IF EXISTS retrieved_at,
    DROP COLUMN IF EXISTS card_sha256,
    DROP COLUMN IF EXISTS verification_status,
    DROP COLUMN IF EXISTS valid_from,
    DROP COLUMN IF EXISTS valid_until,
    DROP COLUMN IF EXISTS superseded_by;

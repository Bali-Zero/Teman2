-- 142_legacy_user_profiles.sql
--
-- (Renumbered from 129_legacy_user_profiles.sql by P0-7 audit fix
-- 2026-04-29 — original 129 was duplicated by 129_crm_guardian.sql,
-- which the runner picked up first; 129_legacy_user_profiles never
-- landed in _schema_versions. The DDL below is idempotent — no-op
-- on prod where user_profiles already exists.)
--
--
-- Promote `user_profiles` from a CI-bootstrap-only table to a
-- migrations_v2 entry. Mirrors the DDL that
-- `apps/backend-rag/scripts/ci_bootstrap_schema.py` issues plus the FK
-- target shape required by `conversation_ratings.user_id`.
--
-- Idempotent: `CREATE TABLE IF NOT EXISTS` so this is a no-op against
-- prod (which already has the table from a pre-v2 hand-applied DDL).
-- Once Step 4 cutover lands, the bootstrap script can drop this table
-- from its body — every fresh CI/dev DB will pick it up here instead.

CREATE TABLE IF NOT EXISTS user_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255),
    phone           VARCHAR(50),
    user_type       VARCHAR(20) NOT NULL DEFAULT 'client',
    status          VARCHAR(20) DEFAULT 'active',
    synthesis       TEXT,
    language_pref   VARCHAR(10) DEFAULT 'id',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- === ROLLBACK ===
-- Reversing this migration is destructive — `user_profiles` is the FK
-- target for `conversation_ratings.user_id` (and historically for the
-- pre-CATA-5 Node.js memory pipeline). The rollback below is what a
-- forward-only "I dropped 129 by mistake" recovery looks like, NOT a
-- routine downgrade. Run it only on a CI/dev DB you can re-bootstrap.
DROP TABLE IF EXISTS user_profiles;

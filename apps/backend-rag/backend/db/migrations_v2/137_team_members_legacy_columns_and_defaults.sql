-- 137_team_members_legacy_columns_and_defaults.sql
--
-- Promote prod-only `team_members` divergence to migrations_v2.
--
-- The SQLModel `User` in backend/app/modules/identity/models.py maps
-- the Python attribute `name` to DB column `full_name` via `sa_column`.
-- Against a freshly bootstrapped CI schema only `full_name` exists and
-- is NOT NULL. Prod/dev DBs however have the inverse historical shape:
-- a legacy `name` column (NOT NULL, no default, left over from the
-- pre-CATA-5 Node.js schema) alongside a nullable `full_name`. Several
-- partner test factories INSERT with `name` only and rely on prod
-- DEFAULTs on timestamp/bool columns and a nullable `full_name`.
--
-- Idempotent. No-op on prod (already in this shape) and on
-- bootstrap-built CI (the bootstrap script issues the same statements).

ALTER TABLE team_members ADD COLUMN IF NOT EXISTS name VARCHAR(255);

ALTER TABLE team_members ALTER COLUMN full_name DROP NOT NULL;

-- SQLModel-side: these columns have Python defaults only. Replicate
-- the prod-side server_defaults so INSERTs that omit them don't crash.
ALTER TABLE team_members ALTER COLUMN personalized_response SET DEFAULT FALSE;
ALTER TABLE team_members ALTER COLUMN failed_attempts SET DEFAULT 0;
ALTER TABLE team_members ALTER COLUMN active SET DEFAULT TRUE;
ALTER TABLE team_members ALTER COLUMN created_at SET DEFAULT NOW();
ALTER TABLE team_members ALTER COLUMN updated_at SET DEFAULT NOW();

-- === ROLLBACK ===
-- See 136 — destructive on prod for `name` (legacy NOT NULL data).
-- Rollback path is forward-only recovery, not a downgrade.
ALTER TABLE team_members ALTER COLUMN updated_at             DROP DEFAULT;
ALTER TABLE team_members ALTER COLUMN created_at             DROP DEFAULT;
ALTER TABLE team_members ALTER COLUMN active                 DROP DEFAULT;
ALTER TABLE team_members ALTER COLUMN failed_attempts        DROP DEFAULT;
ALTER TABLE team_members ALTER COLUMN personalized_response  DROP DEFAULT;
-- `full_name` NOT NULL restoration intentionally omitted: prod has rows
-- with NULL full_name today; a SET NOT NULL would fail.
ALTER TABLE team_members DROP COLUMN IF EXISTS name;

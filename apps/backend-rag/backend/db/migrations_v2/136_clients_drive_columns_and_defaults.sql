-- 136_clients_drive_columns_and_defaults.sql
--
-- Promote prod-only `clients` ALTERs to migrations_v2. None of these
-- columns are declared by SQLModel `Client` in
-- backend/app/modules/crm/models.py; they were added in prod via
-- hand-run ALTER and have lived on as drift between SQLModel and the
-- live schema. Bootstrap script tracked them; this migration makes
-- them part of the canonical migration history.
--
-- Columns:
--   google_drive_folder_id  — drive root folder per client
--   drive_folder_id         — legacy drive folder id (portal + events)
--   drive_folder_url        — legacy drive folder url (documents router)
--   deleted_at              — soft-delete marker (portal + several routers)
--
-- Defaults: SQLModel `Client` declares created_at/updated_at with
-- `default_factory=datetime.utcnow` but no server_default, so
-- `SQLModel.metadata.create_all()` emits NOT NULL columns with no
-- DEFAULT. Legacy INSERTs that omit these columns crash with
-- NotNullViolationError. Prod has DEFAULT NOW() applied by an old
-- hand-run ALTER; this migration replicates that prod shape so the
-- next CI bootstrap and the live DB describe the same column.
--
-- Idempotent. No-op on prod (already in this shape) and on
-- bootstrap-built CI (the bootstrap script issues the same statements).

ALTER TABLE clients ADD COLUMN IF NOT EXISTS google_drive_folder_id VARCHAR(100);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS drive_folder_id        VARCHAR(100);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS drive_folder_url       TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS deleted_at             TIMESTAMPTZ;

ALTER TABLE clients ALTER COLUMN created_at SET DEFAULT NOW();
ALTER TABLE clients ALTER COLUMN updated_at SET DEFAULT NOW();

-- === ROLLBACK ===
-- Removing these columns / defaults is destructive on prod (live data
-- in google_drive_folder_id and deleted_at). The rollback below is
-- forward-only "I added the migration by mistake" recovery, NOT a
-- routine downgrade. Run only on CI/dev DBs.
ALTER TABLE clients ALTER COLUMN updated_at DROP DEFAULT;
ALTER TABLE clients ALTER COLUMN created_at DROP DEFAULT;
ALTER TABLE clients DROP COLUMN IF EXISTS deleted_at;
ALTER TABLE clients DROP COLUMN IF EXISTS drive_folder_url;
ALTER TABLE clients DROP COLUMN IF EXISTS drive_folder_id;
ALTER TABLE clients DROP COLUMN IF EXISTS google_drive_folder_id;

-- Migration 269: versioned kbli_documents_archive (multi-revision support)
--
-- `kbli_documents_archive` was created out-of-band by two writer scripts
-- (kbli_documents_cure.py, kbli_documents_phantom_cure.py) via CREATE TABLE
-- IF NOT EXISTS, with a UNIQUE(kode_kbli) constraint and ON CONFLICT
-- (kode_kbli) DO NOTHING. That makes the archive ONE-SHOT per code: a SECOND
-- cure of the same row is silently skipped, and the pre-cure evidence is lost.
--
-- This migration adds a `cure_run` dimension so successive cures of the same
-- code each preserve their own snapshot. The 313 existing rows are backfilled
-- to cure_run = 'pre-versioning-baseline' so they are never lost and the
-- composite unique constraint admits them as-is.
--
-- IDEMPOTENT across three bootstrap worlds:
--   (a) fresh DB with no table → CREATE TABLE IF NOT EXISTS builds it with the
--       full versioned schema; subsequent ALTER statements are no-ops.
--   (b) old table pre-versioning (UNIQUE(kode_kbli), no cure_run column) →
--       CREATE TABLE no-ops, ADD COLUMN adds cure_run, DROP CONSTRAINT removes
--       the single-column unique, ADD CONSTRAINT guard adds the composite.
--   (c) table already created with the new schema by _kbli_archive.
--       ARCHIVE_TABLE_DDL → every statement no-ops (IF NOT EXISTS + guard).
--
-- The CREATE TABLE DDL below is the TWIN of ARCHIVE_TABLE_DDL in
-- `_kbli_archive.py` — keep them byte-identical; that module carries the
-- matching comment pointing back here.
--
-- NOTE: `-- === ROLLBACK ===` marker is mandatory (migration_base.py:29) for
-- migrations > 111. The runner executes only the FORWARD part.

-- ----------------------------------------------------------------------------
-- Step 1: ensure the table exists with the FULL versioned schema. On a fresh
-- DB this is what actually creates it; on an old or already-versioned table
-- CREATE TABLE IF NOT EXISTS is a no-op.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kbli_documents_archive (
    id SERIAL PRIMARY KEY,
    kode_kbli VARCHAR NOT NULL,
    judul TEXT,
    content TEXT,
    metadata JSONB,
    original_created_at TIMESTAMP,
    original_updated_at TIMESTAMP,
    archived_at TIMESTAMP NOT NULL DEFAULT now(),
    archived_reason TEXT NOT NULL DEFAULT
        'kbli_documents_cure: pre-cure fabricated-content snapshot (2026-07-19)',
    cure_run TEXT NOT NULL DEFAULT 'pre-versioning-baseline',
    CONSTRAINT kbli_documents_archive_code_run_key UNIQUE (kode_kbli, cure_run)
);

-- ----------------------------------------------------------------------------
-- Step 2: add the cure_run column for old tables that pre-date migration 269
-- (backfill via DEFAULT, no separate UPDATE needed). No-op on fresh/versioned.
-- ----------------------------------------------------------------------------

ALTER TABLE kbli_documents_archive
    ADD COLUMN IF NOT EXISTS cure_run TEXT NOT NULL DEFAULT 'pre-versioning-baseline';

-- ----------------------------------------------------------------------------
-- Step 3: replace the single-column unique with a composite (kode_kbli, cure_run).
-- DROP IF EXISTS is a no-op when the old constraint is already absent.
-- ----------------------------------------------------------------------------

ALTER TABLE kbli_documents_archive
    DROP CONSTRAINT IF EXISTS kbli_documents_archive_kode_kbli_key;

-- ----------------------------------------------------------------------------
-- Step 4: add the composite constraint, guarded so it no-ops when already
-- present (bootstrap world c — table created by ARCHIVE_TABLE_DDL).
-- ----------------------------------------------------------------------------

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'kbli_documents_archive_code_run_key') THEN
    ALTER TABLE kbli_documents_archive ADD CONSTRAINT kbli_documents_archive_code_run_key UNIQUE (kode_kbli, cure_run);
  END IF;
END $$;

-- squawk-ignore: require-concurrent-index-creation — this is a small admin
--   sidecar table (313 rows, no concurrent write traffic at deploy time). The
--   constraint creation is near-instant; CONCURRENTLY would be unnecessary
--   overhead here and is not supported inside a transaction block anyway.

-- === ROLLBACK ===

-- Drop the composite constraint and the column. Re-adding UNIQUE(kode_kbli)
-- alone is DELIBERATELY OMITTED: once any second-revision row exists for a code
-- (the whole point of this migration), a single-column UNIQUE(kode_kbli) would
-- fail. Deleting rows to make the rollback succeed is unacceptable — the
-- archive is the forensic record. Operators who need to fully revert must
-- delete the duplicate rows manually after deciding which revision to keep.

ALTER TABLE kbli_documents_archive
    DROP CONSTRAINT IF EXISTS kbli_documents_archive_code_run_key;

ALTER TABLE kbli_documents_archive
    DROP COLUMN IF EXISTS cure_run;

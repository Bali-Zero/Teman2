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
-- NOTE: `-- === ROLLBACK ===` marker is mandatory (migration_base.py:29) for
-- migrations > 111. The runner executes only the FORWARD part.

-- ----------------------------------------------------------------------------
-- Step 1: add cure_run column (backfill via DEFAULT, no separate UPDATE needed).
-- ----------------------------------------------------------------------------

ALTER TABLE kbli_documents_archive
    ADD COLUMN IF NOT EXISTS cure_run TEXT NOT NULL DEFAULT 'pre-versioning-baseline';

-- ----------------------------------------------------------------------------
-- Step 2: replace the single-column unique with a composite (kode_kbli, cure_run).
-- ----------------------------------------------------------------------------

ALTER TABLE kbli_documents_archive
    DROP CONSTRAINT IF EXISTS kbli_documents_archive_kode_kbli_key;

ALTER TABLE kbli_documents_archive
    ADD CONSTRAINT kbli_documents_archive_code_run_key
    UNIQUE (kode_kbli, cure_run);

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

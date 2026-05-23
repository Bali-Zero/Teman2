-- migration 196_cell_skills_add_source
-- Adds the `source` column missing from production cell_skills table.
--
-- W48 (2026-05-23): apps/cell/cell/cortex/skill_library.py:146 INSERT-s a
-- column `source` (VARCHAR, default 'unknown' in code) that production
-- cell_skills has never had. 14 lifetime Tracebacks of
--   asyncpg.exceptions.UndefinedColumnError: column "source" of relation
--   "cell_skills" does not exist
-- accumulated since the code path went live.
--
-- Root cause: migration 172_cell_skills_scar_support.sql included a
-- `CREATE TABLE IF NOT EXISTS cell_skills (..., source VARCHAR(64), ...)`
-- mirror block for the CI test DB. But production already had the table
-- (apps/cell/cell/core/db.py bootstrap created it on first cell.organism
-- start, BEFORE 172 landed), so IF NOT EXISTS was a no-op and the new
-- column never landed in production. The subsequent ALTER TABLE blocks in
-- 172 only added kind/scope/precondition/scar_weakness_tag — source was
-- inside the CREATE-only block.
--
-- Empirical verification 2026-05-23 W48 via mcp__postgres-nuzantara__query
-- on production: 20 columns present, source absent.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS makes this a no-op if any later
-- backfill (manual fly ssh, sibling migration) added the column already.
-- Default 'unknown' matches the Python kwarg default at
-- skill_library.add_candidate(source: str = "unknown") so historical rows
-- (currently 0 because INSERT always failed) align with new code path.

ALTER TABLE cell_skills
    ADD COLUMN IF NOT EXISTS source VARCHAR(64) DEFAULT 'unknown';

COMMENT ON COLUMN cell_skills.source IS
    'Provenance of the candidate skill: e.g. "thinker", "scar_emitter", '
    '"hgt_import", "manual_seed". Default "unknown" preserves backward '
    'compatibility with INSERTs that omit the column (none in current '
    'code path, but defensive). Set at INSERT; never mutated.';

-- === ROLLBACK ===
-- Safe to drop — column has no FK references and is default-NULL-equivalent.
-- Re-running W48 fix is idempotent (IF NOT EXISTS).
ALTER TABLE cell_skills DROP COLUMN IF EXISTS source;

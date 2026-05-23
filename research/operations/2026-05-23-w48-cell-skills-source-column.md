---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W48
status: shipped (commit 457292310); deploy pending fly post-deploy runner
---

# W48 — `cell_skills.source` column missing in production (14 lifetime Tracebacks)

## TL;DR

`apps/cell/cell/cortex/skill_library.py:146` INSERTs into a `source` column that production
`cell_skills` has never had. **14 lifetime Tracebacks** of `asyncpg.UndefinedColumnError` since
the code path went live. Migration 196 adds the column via `ALTER TABLE ADD COLUMN IF NOT EXISTS`.

## Empirical evidence

Pre-fix verification via `mcp__postgres-nuzantara__query`:

```
SELECT column_name FROM information_schema.columns
WHERE table_name='cell_skills' ORDER BY ordinal_position;
```

Returns 20 columns: `id, name, trigger_nl, action_sequence, rationale_nl, fitness,
success_count, failure_count, use_count, generation, parent_id, embedding, status,
created_at, last_used_at, last_decay_check, kind, scope, precondition, scar_weakness_tag`.
**No `source`.**

Code at `skill_library.py:146-159`:

```python
new_id: int = await conn.fetchval(
    """
    INSERT INTO cell_skills
        (name, trigger_nl, action_sequence, rationale_nl,
         fitness, success_count, failure_count, use_count,
         generation, parent_id, embedding, status, source)
    VALUES ($1, $2, $3::jsonb, $4,
            0.0, 0, 0, 0,
            $5, $6, $7, 'candidate', $8)
    RETURNING id
    """,
    name, trigger_nl, json.dumps(action_sequence), rationale_nl,
    generation, parent_id, embedding, source,
)
```

Method signature accepts `source: str = "unknown"` (line 131).

## Root cause

Migration `172_cell_skills_scar_support.sql:25-44` opens with:

```sql
CREATE TABLE IF NOT EXISTS cell_skills (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    ...
    source          VARCHAR(64),
    ...
);
```

Then several `ALTER TABLE ADD COLUMN IF NOT EXISTS` for `kind`, `scope`, `precondition`,
`scar_weakness_tag` (lines 46-56).

**Production already had cell_skills** — created by `apps/cell/cell/core/db.py` bootstrap on
first `cell.organism` start, BEFORE migration 172 landed. So `CREATE TABLE IF NOT EXISTS` was
a no-op and the `source` column inside the CREATE block never landed. The subsequent ALTER
blocks DID land (they're idempotent ADD COLUMN IF NOT EXISTS), but `source` wasn't in any
ALTER — only in the CREATE.

Same family as W37/W40 pattern: **schema drift between code-bootstrapped DDL and migration
DDL**, with `CREATE TABLE IF NOT EXISTS` masking the drift silently.

## Fix shipped

`apps/backend-rag/backend/db/migrations_v2/196_cell_skills_add_source.sql` (commit
`457292310`):

```sql
ALTER TABLE cell_skills
    ADD COLUMN IF NOT EXISTS source VARCHAR(64) DEFAULT 'unknown';

COMMENT ON COLUMN cell_skills.source IS
    'Provenance of the candidate skill: e.g. "thinker", "scar_emitter", ...';

-- === ROLLBACK ===
ALTER TABLE cell_skills DROP COLUMN IF EXISTS source;
```

Default `'unknown'` matches the Python kwarg default in `add_candidate(source: str = "unknown")`.

## Why migration vs code fix

Two valid paths:

1. **Migration** (chosen): adds column to DB. Code intention preserved (track skill provenance:
   "thinker", "scar_emitter", "hgt_import", "manual_seed"). Cell's Voyager/Reflexion loops will
   eventually consume this for provenance-aware skill curation.
2. **Code fix**: drop `source` from INSERT. Loses provenance forever.

Migration is cleaner because the code **clearly intends** to track source, the column was
already in the migration 172 author's design intent, and the default value is well-defined.

## Deploy path

Migration 196 will apply automatically via Fly post-deploy migration runner on next
`fly deploy`. No `fly ssh` manual step needed. Idempotent if any sibling backfill has
already added the column.

**Empirical verification post-deploy** (mcp__postgres-nuzantara__query):

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name='cell_skills' AND column_name='source';
```

Expected: 1 row, `character varying`, `'unknown'::character varying`.

**Behavioral verification** (5min after deploy, ~1 Cell pulse cycle):

```sql
SELECT count(*) FROM cell_skills WHERE source IS NOT NULL;
-- Should grow > 0 within 1-2 pulse cycles
```

Plus zero new `UndefinedColumnError` Tracebacks in `~/logs/cell.organism.error.log`.

## Lessons

- **`CREATE TABLE IF NOT EXISTS` in a migration is a footgun** when production has the table
  via code-bootstrap. The CREATE block silently becomes a no-op; any new column inside it is
  invisible. Future pattern: put ALL new columns in explicit `ALTER TABLE ADD COLUMN IF NOT
  EXISTS` blocks, even if also re-mirroring them in the CREATE for fresh CI test DBs.
- **CI test DB and prod DB are not isomorphic.** Test DB hits the CREATE path; prod hits the
  ALTER path. Audit any migration with both blocks for column-drift across the boundary.
- Schema-drift lint (W41-class): a CI check that runs `apps/cell/cell/core/db.py` bootstrap
  DDL against an empty DB, then diffs columns vs the result of running all migrations_v2.
  Catches the W48 pattern at PR time. Deferred — note as W49+ candidate.

## Reference

- Commit: `457292310` (W48)
- Migration: `apps/backend-rag/backend/db/migrations_v2/196_cell_skills_add_source.sql`
- Code: `apps/cell/cell/cortex/skill_library.py:130-170`
- Schema source-of-drift: `apps/cell/cell/core/db.py` (CREATE_CELL_SKILLS bootstrap)
- Family: schema drift, mirrors W37 + W40 lineage but caught by Traceback grep not direct
  migration collision.

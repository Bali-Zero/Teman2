-- migration 172_cell_skills_scar_support
-- Creates cell_skills if missing (CI test DB hits this path; production already
-- has the table because apps/cell/cell/core/db.py bootstrap created it on first
-- cell.organism start), then extends it to support "scar" entries.
-- LEVA 2 of organism potenziamento (docs/superpowers/plans/2026-05-13-organism-potenziamento-5-leve.md):
-- the critic agent at apps/cell/cell/cortex/critic.py detects weakness_tag patterns
-- (804 'repeated_failure_check_health' in cell_critiques on 2026-05-13) but the cell never
-- persists a "scar" the thinker can read to AVOID the loop. Loop spezzato: critic detects →
-- SelfModel.add_weakness in-memory → restart cell → memory gone.
-- This migration adds the columns needed for scar persistence; emission logic ships in
-- the same PR via critic.py. 2-LLM brainstorm convergence (Gemini 3.1 Pro + DeepSeek V4 Pro)
-- documented at /tmp/leva2-brainstorm-2026-05-13/. Codex panel seat fell through (stuck
-- on safety policy gen, same 429 pattern as Gemini's CLI safety check).
--
-- Squawk notes:
-- - prefer-robust-stmts: excluded repo-wide in migration-lint.yml — the migration_base.py
--   runner already wraps the whole file in a single asyncpg conn.transaction().
-- - constraint-missing-not-valid: excluded repo-wide — empty/near-empty tables in this
--   repo never have lock-held-during-scan concerns; two-step NOT VALID + VALIDATE pattern
--   itself triggers the rule when both are inside the outer transaction.

-- Mirror of apps/cell/cell/core/db.py:_CREATE_CELL_SKILLS so the CI test DB
-- (which never runs the cell.organism bootstrap) has the same base shape
-- production already carries. IF NOT EXISTS makes this a no-op in production.
CREATE TABLE IF NOT EXISTS cell_skills (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    trigger_nl      TEXT,
    action_sequence JSONB,
    rationale_nl    TEXT,
    fitness         DOUBLE PRECISION DEFAULT 0.0,
    success_count   INTEGER DEFAULT 0,
    failure_count   INTEGER DEFAULT 0,
    use_count       INTEGER DEFAULT 0,
    generation      INTEGER DEFAULT 0,
    parent_id       INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    embedding       BYTEA,
    status          VARCHAR(16) DEFAULT 'candidate'
                    CHECK (status IN ('active','candidate','frozen','apoptosed')),
    source          VARCHAR(64),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    last_decay_check TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE cell_skills
    ADD COLUMN IF NOT EXISTS kind VARCHAR(16) NOT NULL DEFAULT 'skill';

ALTER TABLE cell_skills
    ADD COLUMN IF NOT EXISTS scope VARCHAR(16) NOT NULL DEFAULT 'Project';

ALTER TABLE cell_skills
    ADD COLUMN IF NOT EXISTS precondition JSONB;

ALTER TABLE cell_skills
    ADD COLUMN IF NOT EXISTS scar_weakness_tag VARCHAR(64);

ALTER TABLE cell_skills
    ADD CONSTRAINT cell_skills_kind_check
        CHECK (kind IN ('skill', 'scar'));

ALTER TABLE cell_skills
    ADD CONSTRAINT cell_skills_scope_check
        CHECK (scope IN ('Project', 'Personal'));

-- Idempotency guard for concurrent scar emission across pulses.
-- Partial unique index: only scars require uniqueness on weakness_tag; skill rows leave
-- scar_weakness_tag NULL and are unconstrained.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cell_skills_scar_tag
    ON cell_skills (scar_weakness_tag)
    WHERE kind = 'scar';

CREATE INDEX IF NOT EXISTS idx_cell_skills_kind_status
    ON cell_skills (kind, status)
    WHERE status = 'active';

COMMENT ON COLUMN cell_skills.kind IS
    'Entry type. Default "skill" (positive evolvable procedure). "scar" marks a failure pattern '
    'the thinker should AVOID. Set at INSERT time; never mutated.';

COMMENT ON COLUMN cell_skills.scope IS
    'Inheritance scope (HGT semantics). "Project" (default) is germline-inheritable across cells; '
    '"Personal" is somatic — never propagated by HGT (scars are always Personal).';

COMMENT ON COLUMN cell_skills.precondition IS
    'JSONB context blob describing WHEN this entry applies. For scars: '
    '{action, expected_outcome, expected_health, last_5_actual_outcomes, time_span_seconds}. '
    'Consumed by future thinker (LEVA 4) for match-and-avoid logic.';

COMMENT ON COLUMN cell_skills.scar_weakness_tag IS
    'NULL for skills. For scars: the weakness_tag string from cell_critiques '
    '(e.g. "repeated_failure_check_health") that triggered scar emission. Enforced unique among '
    'kind="scar" rows via partial index uq_cell_skills_scar_tag.';

-- === ROLLBACK ===
-- NOTE: rollback does NOT DROP cell_skills (production has data; the base table
-- predates this migration). Only the scar-related extensions are reverted.
DROP INDEX IF EXISTS idx_cell_skills_kind_status;
DROP INDEX IF EXISTS uq_cell_skills_scar_tag;
ALTER TABLE cell_skills DROP CONSTRAINT IF EXISTS cell_skills_scope_check;
ALTER TABLE cell_skills DROP CONSTRAINT IF EXISTS cell_skills_kind_check;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS scar_weakness_tag;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS precondition;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS scope;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS kind;

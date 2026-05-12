-- migration 172_cell_skills_scar_support
-- Extends cell_skills to support "scar" entries (failure-avoidance patterns).
-- LEVA 2 of organism potenziamento (docs/superpowers/plans/2026-05-13-organism-potenziamento-5-leve.md):
-- the critic agent at apps/cell/cell/cortex/critic.py detects weakness_tag patterns
-- (804 'repeated_failure_check_health' in cell_critiques on 2026-05-13) but the cell never
-- persists a "scar" the thinker can read to AVOID the loop. Loop spezzato: critic detects →
-- SelfModel.add_weakness in-memory → restart cell → memory gone.
-- This migration adds the columns needed for scar persistence; emission logic ships in
-- the same PR via critic.py. 2-LLM brainstorm convergence (Gemini 3.1 Pro + DeepSeek V4 Pro)
-- documented at /tmp/leva2-brainstorm-2026-05-13/. Codex panel seat fell through (stuck
-- on safety policy gen, same 429 pattern as Gemini's CLI safety check).
-- Empty/near-empty table (0 rows on 2026-05-13) — ALTER ADD COLUMN with DEFAULT runs in
-- PG 11+ fast path (no full-table rewrite), CHECK constraints + partial UNIQUE INDEX are
-- Squawk-clean on empty data.

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
DROP INDEX IF EXISTS idx_cell_skills_kind_status;
DROP INDEX IF EXISTS uq_cell_skills_scar_tag;
ALTER TABLE cell_skills DROP CONSTRAINT IF EXISTS cell_skills_scope_check;
ALTER TABLE cell_skills DROP CONSTRAINT IF EXISTS cell_skills_kind_check;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS scar_weakness_tag;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS precondition;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS scope;
ALTER TABLE cell_skills DROP COLUMN IF EXISTS kind;

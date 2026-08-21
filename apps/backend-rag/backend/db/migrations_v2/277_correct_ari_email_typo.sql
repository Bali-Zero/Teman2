-- STAGED DRAFT — NOT a live migration file. Staged here because the M5/fleet-wide
-- guardrails hook (research/operations/specs/T1.2-guardrails-hook.md) blocks
-- ANY new .sql file (Write/Edit) whose content newly introduces
-- INSERT/UPDATE/DELETE/DROP/TRUNCATE patterns — by design, not a bug — and
-- requires the operator two-key bypass (GUARDRAILS_BYPASS=1 +
-- ~/.claude/state/operator-presence.flag) before that file can be created.
--
-- Purpose (team-lead ruling, 2026-08-21): client_id 11500 has `assigned_to`
-- = 'ari@balizero.com' — a typo of the real, active, unique staff email
-- 'ari.firda@balizero.com' (Team Leader; the ONLY "Ari" with a staff role
-- in the 540-row team_members roster — verified, see
-- 2026-08-21-orphan-client-reassignment-plan.md and this session's follow-up
-- verification). No team_members row has EVER existed for 'ari@balizero.com'
-- (checked, 0 rows, active or not). This client already has a de-facto
-- owner under a misspelled address — it is NOT an orphan in substance, only
-- in form. Correcting the address is a DATA REPAIR (making assigned_to match
-- reality), explicitly NOT the same decision as the water-filling
-- reassignment in the sibling migration 278 — kept in its own named,
-- separately reviewable step per team-lead's instruction: "chi legge deve
-- poter vedere che sono due decisioni diverse."
--
-- ORDERING IS LOAD-BEARING: this migration (277) MUST apply BEFORE 278. The
-- runner discovers migrations_v2/*.sql sorted by filename
-- (migration_manager.py: `sorted(migrations_dir.glob("*.sql"))`), so 277 < 278
-- is sufficient — but if these two are ever split across separate deploy/apply
-- invocations, re-verify 277 has actually landed (`SELECT 1 FROM
-- schema_migrations WHERE migration_name='277_correct_ari_email_typo'`)
-- before running 278; otherwise 278's live orphan CTE will still see client
-- 11500 as unowned and fold it into the water-filling pool, exactly the
-- outcome this migration exists to prevent.
--
-- Once the guardrails bypass's second key is armed: RE-VERIFY the target
-- migration number is still free (another lane may have claimed 277 or
-- pushed everything up by one), then save this content, byte-for-byte, as
-- apps/backend-rag/backend/db/migrations_v2/277_correct_ari_email_typo.sql
-- (renumber + update every migration-identity literal below if taken),
-- commit, push, open PR, arm `gh pr merge <N> --auto` nudo, deploy, apply
-- BEFORE 278, then invalidate cache per the verified procedure in
-- 2026-08-21-orphan-reassignment-water-filling-robustness-test.md.
--
-- ============================================================================

-- Migration 277: correct a single known typo in clients.assigned_to.
-- Scoped to exactly one client_id, with a defensive WHERE guard on the
-- current (typo'd) value so this is a no-op if the data has already changed
-- by the time it runs (idempotent) and touches nothing else even if the
-- WHERE-by-id were ever loosened by a future edit.

SET lock_timeout = '5s';
SET statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS client_owner_typo_correction_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    migration_name TEXT NOT NULL,
    client_id INTEGER NOT NULL,
    old_assigned_to TEXT,
    new_assigned_to TEXT NOT NULL,
    UNIQUE (migration_name, client_id)
);

INSERT INTO client_owner_typo_correction_archive (
    migration_name, client_id, old_assigned_to, new_assigned_to
)
SELECT
    '277_correct_ari_email_typo',
    id,
    assigned_to,
    'ari.firda@balizero.com'
FROM clients
WHERE id = 11500
  AND deleted_at IS NULL
  AND lower(BTRIM(assigned_to)) = 'ari@balizero.com'
ON CONFLICT (migration_name, client_id) DO NOTHING;

UPDATE clients c
SET
    assigned_to = archive.new_assigned_to,
    updated_at = NOW()
FROM client_owner_typo_correction_archive archive
WHERE archive.migration_name = '277_correct_ari_email_typo'
  AND archive.client_id = c.id
  AND c.assigned_to IS DISTINCT FROM archive.new_assigned_to;

INSERT INTO _schema_versions (
    migration_name,
    migration_number,
    description,
    applied_by,
    checksum
)
VALUES (
    '277_correct_ari_email_typo',
    277,
    'Correct known typo: client 11500 assigned_to ari@balizero.com -> ari.firda@balizero.com (real active Team Leader, verified unique in roster; separate from the 278 water-filling reassignment)',
    'migration-277',
    'tracked-by-migration-277'
)
ON CONFLICT (migration_name) DO NOTHING;

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

UPDATE clients c
SET
    assigned_to = archive.old_assigned_to,
    updated_at = NOW()
FROM client_owner_typo_correction_archive archive
WHERE archive.migration_name = '277_correct_ari_email_typo'
  AND archive.client_id = c.id
  AND c.assigned_to = archive.new_assigned_to;

DELETE FROM _schema_versions
WHERE migration_name = '277_correct_ari_email_typo';

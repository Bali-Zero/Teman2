-- Migration 140: drop crm_guardian_events_no_update / _no_delete rules
--
-- Migration 129 created two PostgreSQL rules on `crm_guardian_events`:
--
--   CREATE OR REPLACE RULE crm_guardian_events_no_update AS
--       ON UPDATE TO crm_guardian_events DO INSTEAD NOTHING;
--   CREATE OR REPLACE RULE crm_guardian_events_no_delete AS
--       ON DELETE TO crm_guardian_events DO INSTEAD NOTHING;
--
-- Intent (per the original SQL comment): "Append-only audit log. UPDATE/DELETE
-- blocked at rule level so violations fail loud."
--
-- Side effect (the bug this migration fixes): the FK
-- `crm_guardian_events.client_id REFERENCES clients(id) ON DELETE SET NULL`
-- emits an internal UPDATE on `crm_guardian_events` whenever a row in
-- `clients` is deleted (the cascade rewriting the child to NULL out the
-- FK column). PostgreSQL routes that internal UPDATE through the
-- `_no_update` rule, which is `DO INSTEAD NOTHING` — i.e. swallows the
-- UPDATE entirely. The FK constraint then re-checks referential integrity,
-- finds the child row still pointing at the now-deleted parent, and raises:
--
--   asyncpg.exceptions.InternalServerError:
--     referential integrity query on "clients" from constraint
--     "crm_guardian_events_client_id_fkey" on "crm_guardian_events"
--     gave unexpected result
--   HINT: This is most likely due to a rule having rewritten the query.
--
-- Result: any DELETE FROM clients fails when matching guardian events
-- exist. Test `test_compliance_alerts_router::test_post_outcome_creates_row`
-- reproduces this in CI; production has not hit it yet only because no
-- client-deletion path has run in production with crm_guardian active.
--
-- Why drop the rules instead of converting them to triggers / WHEN guards:
--
-- 1. The application code does NOT issue UPDATE/DELETE against
--    `crm_guardian_events`. Guardian writes are always INSERT-only via
--    `apps/backend-rag/backend/services/crm_guardian/recorder.py` (verified
--    via `grep -rn "UPDATE crm_guardian_events\|DELETE FROM crm_guardian_events" apps/`
--    → zero matches in production code, only test cleanup helpers).
-- 2. The "fail loud on violation" guard the rules were meant to provide
--    is now redundant — the discipline is enforced upstream in the
--    recorder, and code review catches new write paths.
-- 3. Rules are a 1990s PostgreSQL feature that interacts badly with
--    modern FK cascade semantics. Modern equivalent (BEFORE UPDATE/DELETE
--    triggers with `RAISE EXCEPTION`) would also need a `WHEN` clause to
--    exempt cascade-driven UPDATEs, which is awkward to express portably.
--
-- The audit-trail invariant remains protected by:
--   - Application discipline (recorder.py is the only writer)
--   - Migration 129's INSERT-only schema design (no UPDATE/DELETE methods
--     exist on the recorder)
--   - This migration leaves `crm_guardian_events` table structure untouched
--
-- If the team later wants a hard DB-level guard, the correct mechanism is
-- a BEFORE UPDATE OR DELETE trigger with:
--   IF TG_OP IN ('UPDATE', 'DELETE')
--      AND current_setting('crm_guardian.allow_cascade', true) IS DISTINCT FROM 'true'
--   THEN RAISE EXCEPTION ...
-- and have the FK be ON DELETE CASCADE with a session-local setting.
-- That is out of scope for this fix.

-- Squawk migration-lint requires lock_timeout/statement_timeout before
-- potentially-slow ops. DROP RULE on a tiny audit table is effectively
-- instant, but the linter has no way to know that — set the timeouts
-- explicitly so we stay green and consistent with other migrations.
SET lock_timeout = '5s';
SET statement_timeout = '60s';

DROP RULE IF EXISTS crm_guardian_events_no_update ON crm_guardian_events;
DROP RULE IF EXISTS crm_guardian_events_no_delete ON crm_guardian_events;

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

CREATE OR REPLACE RULE crm_guardian_events_no_update AS
    ON UPDATE TO crm_guardian_events DO INSTEAD NOTHING;
CREATE OR REPLACE RULE crm_guardian_events_no_delete AS
    ON DELETE TO crm_guardian_events DO INSTEAD NOTHING;

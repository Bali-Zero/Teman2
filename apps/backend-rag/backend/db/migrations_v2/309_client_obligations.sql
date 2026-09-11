-- ============================================================
-- 309_client_obligations.sql
-- Obligations register: one row per (client, rule, period) proposal
-- Date: 2026-09-11
--
-- Rules live in backend/data/obligations_catalog.yaml, not in a table (v1),
-- so there is no seed here. services/compliance/obligations_register.py
-- proposes rows; a reviewer moves each one proposed -> approved | rejected
-- (services/compliance/obligations_repository.py, ObligationsRepository.
-- set_status(), a compare-and-swap UPDATE ... WHERE status = 'proposed').
-- An approved row later becomes one compliance_alerts row (m114) and
-- alert_id records it; nothing is sent from this table.
--
-- Column provenance -- every column below is read or written by
-- obligations_repository.py; none is speculative:
-- - id, client_id, rule_id, period_key, due_date, needs_review_reason:
--   written by upsert_proposals() (_UPSERT_SQL, an INSERT ... ON CONFLICT
--   (client_id, rule_id, period_key) DO NOTHING).
-- - status, reviewer_email, review_note, reviewed_at, updated_at: written
--   by set_status() (_REVIEW_SQL). Its `WHERE id = $1 AND status =
--   'proposed'` is the proposed -> approved|rejected transition guard: the
--   DB enforces it as an atomic compare-and-swap (0 rows / None returned
--   the moment the row has already left 'proposed'), not just app-level
--   discipline.
-- - alert_id, created_at: read by list_by_status()/get() via `SELECT *`
--   into ObligationRow; alert_id is written later by the PR A2 bridge into
--   compliance_alerts, not by this repository.
--
-- alert_id is TEXT because compliance_alerts.alert_id is TEXT PRIMARY KEY
-- (m114; confirmed live via information_schema on nuzantara_test). It has
-- no FOREIGN KEY: m244 grants the runtime role SELECT/INSERT/UPDATE on
-- compliance_alerts but not REFERENCES, and that table is prod-owned in
-- some environments, so an FK here could fail the migration there.
-- clients.id is INTEGER (confirmed live the same way); REFERENCES
-- clients(id) ON DELETE CASCADE follows the CASCADE precedent of
-- 130_crm_guardian_summary_queue.sql / 149_client_segments.sql (a
-- client-owned row disappears with the client).
-- New table, owned by the migration runner: no GRANT needed for
-- backend_rag_v2, same reasoning as 259_e33_case_lifecycle.sql.
-- Slot 309 was free on origin/main at implementation (last migration: 308).
-- ============================================================

SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS client_obligations (
    id                  BIGSERIAL PRIMARY KEY,
    client_id           INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    rule_id             TEXT NOT NULL,
    period_key          TEXT NOT NULL,
    due_date            DATE NOT NULL,
    status              TEXT NOT NULL DEFAULT 'proposed',
    needs_review_reason TEXT,
    reviewer_email      TEXT,
    reviewed_at         TIMESTAMPTZ,
    review_note         TEXT,
    alert_id            TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_client_obligations_status
        CHECK (status IN ('proposed','approved','rejected','alerted','done')),
    CONSTRAINT ux_client_obligations_period
        UNIQUE (client_id, rule_id, period_key)
);

-- list_by_status()'s `WHERE ($1::text IS NULL OR status = $1::text) ORDER BY
-- due_date, id` scans this composite index for any single status; the
-- status=NULL / all-rows path falls back to a due_date-only scan (accepted:
-- v1 has no unfiltered high-traffic caller).
CREATE INDEX IF NOT EXISTS ix_client_obligations_status_due
    ON client_obligations (status, due_date);

-- === ROLLBACK ===
-- Inline rollback per W42 lint requirement. To revert, run (manually, in a
-- transaction) the inverse of the DDL above, in reverse order: remove the
-- status/due-date index, then remove the client_obligations table itself.
-- Statements omitted verbatim because the guardrails hook blocks destructive
-- SQL tokens even in comments (same convention as migration 270). This is
-- additive-only forward DDL: no other table's data is touched, so the
-- inverse is self-contained. Be explicit about what it loses: every
-- proposed/reviewed obligation row, including the reviewer_email/
-- review_note/reviewed_at review history recorded by
-- ObligationsRepository.set_status().
--
-- This table already has a LIVE consumer as of this migration, not only a
-- future one: services/compliance/obligations_repository.py (merged ahead
-- of this migration, PR #6122) issues INSERT/UPDATE/SELECT against it on
-- every call. Do not run the inverse while that code is deployed and
-- reachable -- every one of its queries would start raising
-- UndefinedTableError. Undeploy or feature-flag-disable the obligations
-- register call path first. Once PR A2 (the compliance_alerts bridge) also
-- exists, apply the same rule to it: confirm it has not started reading
-- this table, or has itself been rolled back first.

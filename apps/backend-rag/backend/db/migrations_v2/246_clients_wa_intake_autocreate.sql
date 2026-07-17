-- 246_clients_wa_intake_autocreate.sql
--
-- intake-v2 PR-1: identity capture at the entry door.
--
-- Adds `origin` to `clients` so contacts auto-created by the WhatsApp intake
-- entry-door (unknown sender phone -> minimal contact, status='unlabeled') are
-- distinguishable from manually-created / lead-imported / CRM-created rows.
--
-- The partial UNIQUE index on phone_normalized is SCOPED to
-- (deleted_at IS NULL AND origin = 'wa-intake') rather than the full column.
-- Live measurement (2026-07-18, nuzantara_dev, GROUP BY phone_normalized HAVING
-- count(*) > 1 among deleted_at IS NULL clients) found 622 duplicate groups /
-- 664 extra rows in the existing legacy population (shared numbers, spouses,
-- reused numbers, historical dedup debt) — a full-column unique index would
-- fail to build. The auto-create path (backend/services/intake/
-- contact_autocreate.py) ONLY ever inserts rows with origin='wa-intake', so
-- scoping the index to that origin is sufficient for the idempotent
-- INSERT ... ON CONFLICT this PR relies on, without touching the legacy
-- dup mountain (a separate CRM-dedup workstream, out of scope here).
--
-- Idempotent (IF NOT EXISTS / IF EXISTS everywhere) — safe to re-run.

ALTER TABLE clients ADD COLUMN IF NOT EXISTS origin VARCHAR(50);

CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_phone_normalized_wa_intake
    ON clients (phone_normalized)
    WHERE phone_normalized IS NOT NULL
      AND deleted_at IS NULL
      AND origin = 'wa-intake';

-- === ROLLBACK ===
DROP INDEX IF EXISTS ux_clients_phone_normalized_wa_intake;
ALTER TABLE clients DROP COLUMN IF EXISTS origin;

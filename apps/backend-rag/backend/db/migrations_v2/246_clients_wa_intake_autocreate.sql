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
-- `phone_normalized` itself is NOT created by any prior migration — verified
-- 2026-07-18 by grepping the full migrations_v2 chain (173/175 create OTHER
-- tables' OWN phone_normalized column; 225 only MENTIONS clients.phone_normalized
-- in a comment). The SQLModel `Client` class (backend/app/modules/crm/models.py)
-- that CI bootstraps via `SQLModel.metadata.create_all()` only declares `phone`,
-- not `phone_normalized` — so a from-scratch CI database lacks the column
-- entirely, and CI failed with `column "phone_normalized" does not exist` before
-- this line was added. On local dev / prod the column pre-exists out-of-band
-- (added by hand at some point, outside the tracked migration chain — a latent
-- schema-drift debt, out of scope to reconcile here); IF NOT EXISTS makes this
-- a no-op there and the creating statement everywhere else.
--
-- Idempotent (IF NOT EXISTS / IF EXISTS everywhere) — safe to re-run.

ALTER TABLE clients ADD COLUMN IF NOT EXISTS origin VARCHAR(50);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS phone_normalized TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_phone_normalized_wa_intake
    ON clients (phone_normalized)
    WHERE phone_normalized IS NOT NULL
      AND deleted_at IS NULL
      AND origin = 'wa-intake';

-- === ROLLBACK ===
-- `phone_normalized` is intentionally NOT dropped here: on local dev / prod it
-- pre-exists out-of-band with real data this migration does not own, and on a
-- from-scratch CI database other code (routing.py / auto_attach.py /
-- contact_autocreate.py) reads/writes it independently of migration 246 —
-- dropping it would break those unrelated paths. This migration owns (and
-- therefore only rolls back) the index and the `origin` column.
DROP INDEX IF EXISTS ux_clients_phone_normalized_wa_intake;
ALTER TABLE clients DROP COLUMN IF EXISTS origin;

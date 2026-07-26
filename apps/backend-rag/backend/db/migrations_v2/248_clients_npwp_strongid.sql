-- 248: clients.npwp — personal NPWP as a strong-id matching key.
--
-- Prod already has this column (added server-side during the 2026-07 CRM
-- enrichment wave, together with nib/tax_id/visa fields); this migration
-- codifies it for CI and fresh environments so the intake person matcher
-- (_match_person_strong npwp block) finds the column everywhere.
-- IF NOT EXISTS => no-op on prod and on the refreshed local dev.

ALTER TABLE clients ADD COLUMN IF NOT EXISTS npwp TEXT;

-- === ROLLBACK ===
-- Intentionally a no-op: the column PRE-EXISTS this migration on prod (with
-- live personal-NPWP data). Dropping it would not restore the pre-migration
-- state — it would destroy data the migration never created.
SELECT 1;

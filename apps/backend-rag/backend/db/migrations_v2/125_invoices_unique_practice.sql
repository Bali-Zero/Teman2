-- ============================================================
-- 125_invoices_unique_practice.sql
-- Guard against duplicate invoices per practice.
-- Date: 2026-04-20
--
-- SCAR: invoice_service._update_practice_with_invoice used ON CONFLICT
-- (invoice_number), but invoice_number changes across months
-- (format INV-YYYYMM-<practice_id>). Running invoice regeneration in a new
-- month produced a NEW invoice row with a NEW number for the same
-- practice_id, bypassing the conflict target. Practice 204 ended up with
-- two invoices (INV-202603-00204 and INV-202604-00204).
--
-- Fix: add UNIQUE (practice_id) so only one invoice per practice can exist.
-- Any regeneration updates-in-place.
--
-- Preflight: deduplicate any existing violators (keep the latest).
-- ============================================================

-- Preflight: keep the most recent invoice per practice, delete the rest.
-- "Most recent" = highest id (mostly-monotonic since schema has no sortable
-- timestamp that's both reliably populated AND ordered). Verify manually
-- before running in prod if any practice has >1 row where the older row
-- has email_sent_to_client=TRUE and the newer does not — in that case the
-- latest is not necessarily the canonical one.
DELETE FROM invoices a
USING invoices b
WHERE a.practice_id = b.practice_id
  AND a.id < b.id;

ALTER TABLE invoices
    ADD CONSTRAINT invoices_practice_id_key UNIQUE (practice_id);

-- === ROLLBACK ===
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_practice_id_key;

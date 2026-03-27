-- Migration 044: Remove invoice blob from practices.documents JSONB
-- All 25 invoice records are now in the invoices table (migration 043).
-- No router or frontend code reads practices.documents->invoice directly.
--
-- Two cases exist due to historical double-encoding bug in InvoiceAutomationService
-- (was calling json.dumps() instead of passing dict directly to asyncpg):
--   - 23 rows: jsonb_typeof = 'string' (double-encoded, contain only invoice key → set to {})
--   - 2 rows:  jsonb_typeof = 'object' (proper JSONB object → remove 'invoice' key)

-- Case 1: double-encoded string → set to empty object
UPDATE practices
SET documents = '{}'::jsonb
WHERE jsonb_typeof(documents) = 'string'
  AND documents::text LIKE '%invoice%';

-- Case 2: proper JSONB object → remove invoice key
UPDATE practices
SET documents = documents - 'invoice'
WHERE jsonb_typeof(documents) = 'object'
  AND documents ? 'invoice';

-- Migration 042: Clients Tax IDs
-- Add npwp and nib columns to clients table.
-- These are referenced in crm_clients.py OCR extraction endpoints
-- but were never added to the schema, causing silent UPDATE failures.

ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS npwp TEXT,   -- Indonesian tax ID (NPWP), 15-digit format
    ADD COLUMN IF NOT EXISTS nib  TEXT;   -- Business registration number (NIB)

COMMENT ON COLUMN clients.npwp IS 'Nomor Pokok Wajib Pajak — Indonesian individual/business tax ID (15 digits)';
COMMENT ON COLUMN clients.nib  IS 'Nomor Induk Berusaha — Indonesian business registration number';

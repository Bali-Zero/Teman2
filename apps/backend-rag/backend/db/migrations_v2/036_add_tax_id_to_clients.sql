-- Migration: 036_add_tax_id_to_clients
-- Description: Add tax_id field to clients table for personal tax identifier storage
-- Date: 2026-03-23

ALTER TABLE public.clients
ADD COLUMN IF NOT EXISTS tax_id character varying(50);

COMMENT ON COLUMN public.clients.tax_id IS 'Client personal tax identifier (for example NPWP)';

CREATE INDEX IF NOT EXISTS idx_clients_tax_id ON public.clients(tax_id);

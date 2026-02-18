-- Migration: 035_add_gender_to_clients
-- Description: Add gender field to clients table for profile completeness
-- Date: 2026-02-16

-- Add gender column to clients table
ALTER TABLE public.clients 
ADD COLUMN IF NOT EXISTS gender character varying(10);

-- Add check constraint for valid gender values (optional - can be removed if needed)
-- ALTER TABLE public.clients 
-- ADD CONSTRAINT chk_gender_values 
-- CHECK (gender IS NULL OR gender IN ('M', 'F', 'Other', 'Prefer not to say'));

-- Add comment for documentation
COMMENT ON COLUMN public.clients.gender IS 'Client gender: M (Male), F (Female), or other values';

-- Add index for potential filtering (optional but good for performance)
CREATE INDEX IF NOT EXISTS idx_clients_gender ON public.clients(gender);

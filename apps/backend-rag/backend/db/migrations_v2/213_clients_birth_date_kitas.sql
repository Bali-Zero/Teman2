-- 213_clients_birth_date_kitas.sql — debito schema 04-4 (C4 entity-resolution)
-- clients NON ha birth_date ne kitas_number come colonne (verificato models.py + live nuzantara_dev).
-- C4 richiede birth_date come discriminante BLOCKING (oggi solo tie-breaker via custom_fields).
-- LOCAL Pro DB only (nuzantara_dev). Backfill da custom_fields opzionale/separato/non bloccante.
-- === FORWARD ===
ALTER TABLE clients ADD COLUMN IF NOT EXISTS birth_date   DATE;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS kitas_number TEXT;
CREATE INDEX IF NOT EXISTS idx_clients_birth_date ON clients (birth_date) WHERE birth_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_clients_kitas      ON clients (kitas_number) WHERE kitas_number IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_clients_kitas;
DROP INDEX IF EXISTS idx_clients_birth_date;
ALTER TABLE clients DROP COLUMN IF EXISTS kitas_number;
ALTER TABLE clients DROP COLUMN IF EXISTS birth_date;

-- Migration: 001_add_performance_indexes.sql
-- Description: Aggiunge indici di performance per ottimizzare le query frequenti
-- Created: 2026-02-07
-- Note: Tutte le operazioni sono idempotenti

-- =====================================================
-- 1. Indice per email case-insensitive su clients
-- =====================================================
-- Ottimizza le ricerche per email indipendentemente dal case
DROP INDEX IF EXISTS idx_clients_email_lower;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_email_lower 
    ON clients (LOWER(email));

COMMENT ON INDEX idx_clients_email_lower IS 'Indice case-insensitive per ricerche email';

-- =====================================================
-- 2. Colonna phone_normalized e relativo indice
-- =====================================================
-- Aggiunge colonna per numero telefono normalizzato
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'clients' 
        AND column_name = 'phone_normalized'
    ) THEN
        ALTER TABLE clients ADD COLUMN phone_normalized VARCHAR(20);
    END IF;
END $$;

-- Funzione per normalizzare il numero di telefono
CREATE OR REPLACE FUNCTION normalize_phone_number(phone TEXT)
RETURNS VARCHAR(20) AS $$
BEGIN
    -- Rimuove tutti i caratteri non numerici
    RETURN REGEXP_REPLACE(phone, '[^0-9]', '', 'g');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger per mantenere aggiornata la colonna phone_normalized
CREATE OR REPLACE FUNCTION update_phone_normalized()
RETURNS TRIGGER AS $$
BEGIN
    NEW.phone_normalized := normalize_phone_number(NEW.phone);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Rimuove trigger esistente se presente per evitare errori
DROP TRIGGER IF EXISTS trg_normalize_phone ON clients;

CREATE TRIGGER trg_normalize_phone
    BEFORE INSERT OR UPDATE OF phone ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_phone_normalized();

-- Popola i dati esistenti
UPDATE clients 
SET phone_normalized = normalize_phone_number(phone)
WHERE phone IS NOT NULL 
AND phone_normalized IS NULL;

-- Crea l'indice sulla colonna normalizzata
DROP INDEX IF EXISTS idx_clients_phone_normalized;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_phone_normalized 
    ON clients (phone_normalized);

COMMENT ON INDEX idx_clients_phone_normalized IS 'Indice su numero telefono normalizzato (solo cifre)';

-- =====================================================
-- 3. Indici per birth_month/birth_day su clients
-- =====================================================
-- Ottimizza le ricerche per compleanni e date di nascita
DROP INDEX IF EXISTS idx_clients_birth_month;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_birth_month 
    ON clients (birth_month);

DROP INDEX IF EXISTS idx_clients_birth_day;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_birth_day 
    ON clients (birth_day);

-- Indice composito per ricerche su mese e giorno insieme (es: compleanni)
DROP INDEX IF EXISTS idx_clients_birth_month_day;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clients_birth_month_day 
    ON clients (birth_month, birth_day);

COMMENT ON INDEX idx_clients_birth_month IS 'Indice per filtri su mese di nascita';
COMMENT ON INDEX idx_clients_birth_day IS 'Indice per filtri su giorno di nascita';
COMMENT ON INDEX idx_clients_birth_month_day IS 'Indice composito per ricerche compleanni';

-- =====================================================
-- 4. Indice composito per documents
-- =====================================================
-- Ottimizza le query che filtrano per client_id, visibilità, tipo e data
DROP INDEX IF EXISTS idx_documents_client_visibility_type_created;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_client_visibility_type_created 
    ON documents (client_id, client_visible, document_type, created_at DESC);

COMMENT ON INDEX idx_documents_client_visibility_type_created IS 'Indice composito per ricerche documenti per cliente con filtri visibilità/tipo/data';

-- Indice aggiuntivo per ricerche per client_id singolo (più leggero)
DROP INDEX IF EXISTS idx_documents_client_id;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_client_id 
    ON documents (client_id);

-- =====================================================
-- 5. Indice per collective_memories
-- =====================================================
-- Ottimizza le query su memorie promosse con filtri per categoria, confidenza e fonti
DROP INDEX IF EXISTS idx_collective_memories_promoted;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_collective_memories_promoted 
    ON collective_memories (is_promoted, category, confidence DESC, source_count DESC);

COMMENT ON INDEX idx_collective_memories_promoted IS 'Indice per ricerche memorie promosse ordinate per confidenza e fonti';

-- Indice aggiuntivo per ricerche per categoria
DROP INDEX IF EXISTS idx_collective_memories_category;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_collective_memories_category 
    ON collective_memories (category);

-- =====================================================
-- Verifica finale
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'Indici creati con successo:';
    RAISE NOTICE '  - idx_clients_email_lower';
    RAISE NOTICE '  - idx_clients_phone_normalized (con colonna e trigger)';
    RAISE NOTICE '  - idx_clients_birth_month';
    RAISE NOTICE '  - idx_clients_birth_day';
    RAISE NOTICE '  - idx_clients_birth_month_day';
    RAISE NOTICE '  - idx_documents_client_visibility_type_created';
    RAISE NOTICE '  - idx_documents_client_id';
    RAISE NOTICE '  - idx_collective_memories_promoted';
    RAISE NOTICE '  - idx_collective_memories_category';
END $$;

# Guida Migration Database

## Migration: 001_add_performance_indexes.sql

### Indici Creati

Questa migration aggiunge 8 indici di performance e 1 trigger per ottimizzare le query frequenti:

| Indice                                         | Tabella             | Scopo                             |
| ---------------------------------------------- | ------------------- | --------------------------------- |
| `idx_clients_email_lower`                      | clients             | Ricerche email case-insensitive   |
| `idx_clients_phone_normalized`                 | clients             | Ricerche telefono normalizzate    |
| `idx_clients_birth_month`                      | clients             | Filtri mese compleanno            |
| `idx_clients_birth_day`                        | clients             | Filtri giorno compleanno          |
| `idx_clients_birth_month_day`                  | clients             | Ricerche compleanno (mese+giorno) |
| `idx_documents_client_visibility_type_created` | documents           | Query documenti con filtri        |
| `idx_documents_client_id`                      | documents           | Ricerche base per client_id       |
| `idx_collective_memories_promoted`             | collective_memories | Memorie promosse ordinate         |
| `idx_collective_memories_category`             | collective_memories | Filtri per categoria              |

### Trigger Creato

- `trg_normalize_phone`: Normalizza automaticamente i numeri di telefono (rimuove spazi, trattini, +)

---

## Come Eseguire la Migration

### Opzione 1: Usa lo script automatizzato

```bash
cd apps/backend-rag
bash backend/migrations/scripts/run_migration.sh
```

### Opzione 2: Comando diretto con psql

```bash
cd apps/backend-rag
psql "$(grep '^DATABASE_URL' .env | cut -d= -f2-)" -f backend/migrations/scripts/001_add_performance_indexes.sql
```

### Opzione 3: Connessione manuale

Se usi un database diverso da quello configurato in .env:

```bash
psql -h <host> -U <user> -d <database> -f backend/migrations/scripts/001_add_performance_indexes.sql
```

---

## Verifica Post-Migration

Dopo l'esecuzione, verifica che gli indici siano stati creati:

```sql
-- Lista indici creati
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
AND schemaname = 'public'
ORDER BY tablename, indexname;
```

```sql
-- Verifica trigger
SELECT trigger_name, event_manipulation, action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public';
```

---

## Rollback (se necessario)

Per rimuovere gli indici creati:

```sql
DROP INDEX IF EXISTS idx_clients_email_lower;
DROP INDEX IF EXISTS idx_clients_phone_normalized;
DROP INDEX IF EXISTS idx_clients_birth_month;
DROP INDEX IF EXISTS idx_clients_birth_day;
DROP INDEX IF EXISTS idx_clients_birth_month_day;
DROP INDEX IF EXISTS idx_documents_client_visibility_type_created;
DROP INDEX IF EXISTS idx_documents_client_id;
DROP INDEX IF EXISTS idx_collective_memories_promoted;
DROP INDEX IF EXISTS idx_collective_memories_category;

DROP TRIGGER IF EXISTS trg_normalize_phone ON clients;
DROP FUNCTION IF EXISTS update_phone_normalized();
DROP FUNCTION IF EXISTS normalize_phone_number(TEXT);
```

---

## Note

- La migration è **idempotente**: può essere eseguita più volte senza errori
- Usa `CREATE INDEX CONCURRENTLY` per non bloccare la tabella durante la creazione
- La colonna `phone_normalized` viene popolata automaticamente per i record esistenti
- In ambiente di produzione, eseguire durante periodi di basso carico

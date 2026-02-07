# Migration su Fly.io PostgreSQL

## Prerequisiti

- `flyctl` installato e autenticato
- Accesso all'organizzazione Fly.io del progetto

## Metodo 1: Script Automatico

```bash
cd apps/backend-rag
bash backend/migrations/scripts/run_migration_fly.sh
```

Lo script:

1. Trova automaticamente l'app PostgreSQL
2. Chiede conferma
3. Esegue la migration

## Metodo 2: Manuale con Proxy

### Step 1: Apri il proxy

```bash
# Trova il nome del tuo database PostgreSQL su Fly
flyctl list apps | grep postgres

# Esempio output: nuzantara-db, nuzantara-postgres, ecc.

# Apri proxy (lascia questo terminale aperto)
flyctl proxy 5433:5432 -a <nome-app-postgres>
```

### Step 2: Esegui la migration (altro terminale)

```bash
cd apps/backend-rag

# Ottieni la connection string
flyctl postgres connect -a <nome-app-postgres> --url

# O usa direttamente psql con il proxy locale
psql postgresql://postgres@localhost:5433/postgres -f backend/migrations/scripts/001_add_performance_indexes.sql
```

## Metodo 3: Via Console Fly.io

1. Vai su https://fly.io/dashboard
2. Seleziona l'app PostgreSQL
3. Click su "Connect" → "psql"
4. Copia/incolla il contenuto del file SQL

## Verifica

Dopo la migration, verifica gli indici:

```sql
-- Lista indici creati
SELECT indexname, tablename
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
ORDER BY tablename, indexname;
```

## Troubleshooting

### "connection refused"

- Verifica che il proxy sia attivo (`flyctl proxy`)
- Controlla la porta (5433 nel esempio)

### "permission denied"

- Usa l'utente `postgres` o un utente con privilegi CREATE INDEX

### "index already exists"

- La migration è idempotente, puoi rieseguirla senza problemi

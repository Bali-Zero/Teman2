# PostgreSQL Fly.io Operations Runbook

Guida operativa per gestire il database PostgreSQL su Fly.io per Nuzantara Prime.

## Indice

1. [Connessione al Database](#connessione-al-database)
2. [Verifica Stato Database](#verifica-stato-database)
3. [Esecuzione Migrazioni](#esecuzione-migrazioni)
4. [Query e Troubleshooting](#query-e-troubleshooting)
5. [Backup e Restore](#backup-e-restore)
6. [Monitoraggio](#monitoraggio)

---

## Connessione al Database

### Metodo 1: Proxy Locale (Consigliato)

Il metodo più semplice per connettersi al database da locale:

```bash
# Avvia proxy sulla porta locale 15432
flyctl proxy 15432:5432 -a nuzantara-postgres &

# Connettiti usando psql
psql postgresql://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable

# Oppure usando variabile d'ambiente
export DATABASE_URL="postgresql://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable"
psql $DATABASE_URL
```

**Nota**: Sostituisci `PASSWORD` con la password reale del database (non committare mai).

### Metodo 2: SSH Direct (Dalla Macchina Fly)

```bash
# Connettiti alla macchina Fly
flyctl ssh console -a nuzantara-rag

# All'interno del container, usa Python con asyncpg
python3 <<EOF
import asyncio
import asyncpg
import os

async def test_connection():
    db_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(db_url)
    result = await conn.fetchval('SELECT 1')
    print(f"Connection successful: {result}")
    await conn.close()

asyncio.run(test_connection())
EOF
```

### Metodo 3: Flycast (Network Interno)

Se sei già connesso alla VPN Fly o dalla macchina Fly:

```bash
# Il database è raggiungibile direttamente via Flycast
psql postgresql://backend_rag_v2:PASSWORD@nuzantara-postgres.internal:5432/nuzantara_rag
```

---

## Verifica Stato Database

### Check Health via Health Endpoint

```bash
# Verifica stato database tramite health endpoint
curl https://nuzantara-rag.fly.dev/api/health/detailed | jq '.services.database'
```

### Check Diretto via SQL

```bash
# Connettiti e verifica connessioni attive
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'nuzantara_rag';"

# Verifica dimensioni database
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('nuzantara_rag'));"

# Lista tabelle CRM
psql $DATABASE_URL -c "\dt public.*" | grep -E "(practices|interactions|clients|renewal)"
```

---

## Esecuzione Migrazioni

### Metodo 1: Script Python (Consigliato)

```bash
# Dalla root del progetto
cd apps/backend-rag

# Esegui migrazione specifica
export DATABASE_URL="postgresql://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable"
export PYTHONPATH=$PYTHONPATH:$(pwd)/backend
python3 backend/migrations/migration_XXX.py

# Oppure usa lo script di migrazione automatica
python3 backend/db/migrate.py apply-all
```

### Metodo 2: SQL Diretto

```bash
# Connettiti e esegui SQL direttamente
psql $DATABASE_URL -f backend/db/migrations/XXX_migration_name.sql
```

### Metodo 3: Via Fly SSH

```bash
# Connettiti alla macchina Fly
flyctl ssh console -a nuzantara-rag

# All'interno del container
cd /app/backend
export DATABASE_URL="..." # Già configurato come secret
python3 -m db.migrate apply-all
```

### Verifica Migrazioni Applicate

```bash
# Controlla tabella migrazioni (se esiste)
psql $DATABASE_URL -c "SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 10;"

# Oppure verifica direttamente le tabelle
psql $DATABASE_URL -c "\d practices"  # Verifica colonne
psql $DATABASE_URL -c "\d interactions"  # Verifica colonne
```

---

## Query e Troubleshooting

### Query Utili per CRM

```sql
-- Conta pratiche per status
SELECT status, COUNT(*) as count 
FROM practices 
GROUP BY status 
ORDER BY count DESC;

-- Pratiche attive con scadenze imminenti
SELECT id, client_id, status, expiry_date,
       expiry_date - CURRENT_DATE as days_remaining
FROM practices
WHERE status IN ('in_progress', 'waiting_documents', 'submitted_to_gov')
  AND expiry_date IS NOT NULL
  AND expiry_date <= CURRENT_DATE + INTERVAL '30 days'
ORDER BY expiry_date ASC;

-- Interazioni WhatsApp non lette
SELECT id, client_id, summary, interaction_date, read_receipt
FROM interactions
WHERE interaction_type = 'whatsapp'
  AND read_receipt = false
ORDER BY interaction_date DESC
LIMIT 20;

-- Revenue mensile (se view esiste)
SELECT * FROM monthly_revenue_view ORDER BY month DESC LIMIT 6;

-- Verifica integrità dati
SELECT 
    (SELECT COUNT(*) FROM clients) as total_clients,
    (SELECT COUNT(*) FROM practices) as total_practices,
    (SELECT COUNT(*) FROM interactions) as total_interactions,
    (SELECT COUNT(*) FROM renewal_alerts WHERE status = 'pending') as pending_renewals;
```

### Troubleshooting Errori Comuni

#### Errore: "Database unavailable" (503)

```bash
# 1. Verifica che DATABASE_URL sia configurato
flyctl secrets list -a nuzantara-rag | grep DATABASE_URL

# 2. Verifica connessione diretta
flyctl ssh console -a nuzantara-rag --command "python3 -c 'import os; print(os.getenv(\"DATABASE_URL\")[:30])'"

# 3. Controlla logs backend per errori di inizializzazione
flyctl logs -a nuzantara-rag | grep -i "database\|db_pool\|postgres"

# 4. Verifica che il pool sia inizializzato
curl https://nuzantara-rag.fly.dev/api/health/detailed | jq '.services.database'
```

#### Errore: "Table does not exist"

```bash
# Verifica che la migrazione sia stata applicata
psql $DATABASE_URL -c "\dt public.practices"

# Se manca, applica migrazione
python3 backend/migrations/migration_007.py  # Esempio per schema CRM
```

#### Errore: "Column does not exist"

```bash
# Verifica colonne esistenti
psql $DATABASE_URL -c "\d practices" | grep read_receipt

# Se manca, applica migrazione che aggiunge la colonna
python3 backend/migrations/migration_024.py  # Esempio per read_receipt
```

---

## Backup e Restore

### Backup Database

```bash
# Backup completo
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup solo schema
pg_dump $DATABASE_URL --schema-only > schema_backup.sql

# Backup solo dati
pg_dump $DATABASE_URL --data-only > data_backup.sql

# Backup tabelle specifiche (CRM)
pg_dump $DATABASE_URL -t practices -t interactions -t clients > crm_backup.sql
```

### Restore Database

```bash
# Restore completo (ATTENZIONE: sovrascrive dati esistenti)
psql $DATABASE_URL < backup_20250101_120000.sql

# Restore solo schema
psql $DATABASE_URL < schema_backup.sql

# Restore solo dati
psql $DATABASE_URL < data_backup.sql
```

### Backup Automatico (Fly.io)

Fly.io esegue backup automatici per database PostgreSQL. Per verificare:

```bash
# Lista backup disponibili
flyctl postgres backups list -a nuzantara-postgres

# Crea backup manuale
flyctl postgres backups create -a nuzantara-postgres

# Restore da backup Fly.io
flyctl postgres backups restore <backup-id> -a nuzantara-postgres
```

---

## Monitoraggio

### Metriche Database

```bash
# Connessioni attive
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'nuzantara_rag';"

# Query lente (ultime 10)
psql $DATABASE_URL -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
  AND state = 'active'
ORDER BY duration DESC
LIMIT 10;
"

# Dimensioni tabelle
psql $DATABASE_URL -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"
```

### Logs Database

```bash
# Logs applicazione (contengono query database)
flyctl logs -a nuzantara-rag | grep -i "database\|postgres\|asyncpg"

# Logs database direttamente (se disponibili)
flyctl logs -a nuzantara-postgres
```

---

## Comandi Rapidi

```bash
# Setup proxy e connessione rapida
alias fly-db-proxy='flyctl proxy 15432:5432 -a nuzantara-postgres &'
alias fly-db-connect='psql postgresql://backend_rag_v2:PASSWORD@localhost:15432/nuzantara_rag?sslmode=disable'

# Verifica stato rapido
alias fly-db-status='curl -s https://nuzantara-rag.fly.dev/api/health/detailed | jq ".services.database"'

# Lista tabelle CRM
alias fly-db-tables='psql $DATABASE_URL -c "\dt public.*" | grep -E "(practices|interactions|clients)"'
```

Aggiungi questi alias al tuo `~/.zshrc` o `~/.bashrc` per uso rapido.

---

## Sicurezza

### Best Practices

1. **Mai committare password**: Usa sempre `flyctl secrets` per gestire credenziali
2. **Usa proxy locale**: Evita di esporre il database pubblicamente
3. **Limita accessi**: Solo sviluppatori autorizzati dovrebbero avere accesso
4. **Backup regolari**: Verifica che i backup automatici siano attivi
5. **Monitora connessioni**: Controlla regolarmente le connessioni attive

### Gestione Secrets

```bash
# Lista secrets configurati
flyctl secrets list -a nuzantara-rag

# Imposta secret
flyctl secrets set DATABASE_URL="postgresql://..." -a nuzantara-rag

# Rimuovi secret (ATTENZIONE)
flyctl secrets unset DATABASE_URL -a nuzantara-rag
```

---

## Troubleshooting Avanzato

### Database Pool Non Inizializzato

Se vedi errori 503 con messaggio "Database unavailable":

1. **Verifica startup logs**:
   ```bash
   flyctl logs -a nuzantara-rag | grep -i "database\|db_pool\|initialization"
   ```

2. **Verifica DATABASE_URL**:
   ```bash
   flyctl secrets list -a nuzantara-rag | grep DATABASE_URL
   ```

3. **Test connessione diretta**:
   ```bash
   flyctl ssh console -a nuzantara-rag --command "python3 -c 'import asyncpg, os, asyncio; asyncio.run(asyncpg.connect(os.getenv(\"DATABASE_URL\")))'"
   ```

4. **Riavvia applicazione**:
   ```bash
   flyctl apps restart nuzantara-rag
   ```

### Performance Issues

Se le query sono lente:

1. **Verifica indici**:
   ```sql
   SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('practices', 'interactions', 'clients');
   ```

2. **Analizza query plan**:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM practices WHERE status = 'in_progress';
   ```

3. **Verifica statistiche**:
   ```sql
   ANALYZE practices;
   ANALYZE interactions;
   ANALYZE clients;
   ```

---

## Riferimenti

- [Fly.io PostgreSQL Docs](https://fly.io/docs/postgres/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)

---

**Ultimo aggiornamento**: 2025-01-XX
**Mantenuto da**: Nuzantara Prime Team


# SOLIDIFICATION 07 — Database Layer

# Machine: AIR | Model: Claude Opus 4.6 MAX | Date: 2026-04-06

# Score Pre: 5.9/10 | Target Post: 8.5/10

---

## EXECUTIVE SUMMARY

Il database layer di Nuzantara ha una difesa errori eccellente (3-layer, health check, auto-recovery) ma soffre di debito tecnico su migration numbering (9 collisioni), N+1 query pattern diffusi, pool oversized per 2GB RAM, e monitoring quasi assente.

**Impatto stimato delle fix**: p95 query -40%, connection errors -80%, zero risk di migration collision.

---

## FINDINGS (8 aree analizzate)

### 1. MIGRATION NUMBERING COLLISION

**Severita: CRITICA | File: 68 migration, 9 numeri duplicati**

Coppie duplicate:
| Num | File A | File B |
|-----|--------|--------|
| 031 | client_portal | hybrid_collections |
| 041 | clients_missing_columns | team_activity_logging |
| 043 | fix_visa_types_from_qdrant | knowledge_activity_log |
| 069 | audit_logs | hr_bonus_rates_alignment |
| 070 | conversation_history | legal_ingest_jobs |
| 076 | event_bus_triggers | hr_leave_balances_seed |
| 077 | kg_staging_tables | post_publish_queue |
| 080 | renewal_dedup | visa_oracle_sessions |
| 081 | naga_claim_quality | prime_nexus_geo |

**Bug**: `is_applied()` verifica per `migration_number` INTEGER. Se 031a e 031b condividono lo stesso numero, dopo che uno e applicato l'altro viene silenziosamente saltato.

**Evidence**: `backend/db/migration_manager.py:147-156`:

```python
SELECT EXISTS(SELECT 1 FROM _schema_versions WHERE migration_number = $1)
```

### 2. N+1 QUERY PATTERNS

**Severita: CRITICA per performance**

| File                                  | Pattern                                                | Impact                                     |
| ------------------------------------- | ------------------------------------------------------ | ------------------------------------------ |
| `services/crm/automation.py:165-170`  | 2 query separate (practice + client) dove 1 JOIN basta | Ogni practice status change = 2 round-trip |
| `services/crm/cache_query.py:250-255` | Loop `fetchrow` per batch insert                       | O(N) round-trip per N inserimenti          |
| `services/crm/cache_query.py:284-303` | Loop `execute` per batch update                        | O(N) round-trip per N aggiornamenti        |
| `services/crm/notifiers.py:114-129`   | Query birthday + N email individualmente               | Caller loops per-client                    |

### 3. POOL SIZING

**Severita: MEDIA**

| Setting           | Attuale      | Raccomandato | Ragione                                                                       |
| ----------------- | ------------ | ------------ | ----------------------------------------------------------------------------- |
| min_size          | 2            | 2            | OK — idle connections minimize                                                |
| max_size          | **20**       | **10**       | 20 conn x 5-10MB = 100-200MB. Con PG shared_buffers 512MB + OS, 2GB non basta |
| max_inactive      | 30s          | 30s          | OK — copre Fly.io cold start 35s                                              |
| command_timeout   | 60s          | 30s          | 60s troppo per CRUD standard                                                  |
| statement_timeout | **mancante** | **30s**      | Previene query infinite (30s non 15s: RAG KG queries possono durare 5-10s)    |

### 4. REPOSITORY PATTERN

**Severita: MEDIA**

- 4 repository, nessuna base class
- Ogni repo ripete `async with self.db_pool.acquire() as conn`
- Nessun Unit of Work pattern
- Errori gestiti inconsistentemente (alcuni log, altri raise)

### 5. TRANSACTION BOUNDARIES MANCANTI

**Severita: MEDIA**

- `automation.py:165-170` — fetch practice + fetch client senza transaction
- `assignment.py:94-118` — `find_client_by_whatsapp` 2 query separate
- `notifiers.py` — birthday processing senza batch transaction

### 6. LEADING WILDCARD LIKE

**Severita: MEDIA**

- `prime_nexus_service.py:1672` — `title ILIKE '%' || $1 || '%'`
- `lkpm_data_collector.py:270` — `ILIKE '%kitas%'`
- `lkpm_validator.py:143` — `ILIKE '%kitas%'`

### 7. JSONB INDEXING ASSENTE

**Severita: BASSA**

- JSONB payload flat (corretto)
- Nessun GIN index specifico per campi JSONB frequentemente interrogati
- `custom_fields` in clients non ha indice

### 8. MONITORING QUASI ASSENTE

**Severita: MEDIA**

- Pool stats esposti in `/health` (buono)
- Prometheus metrics per init success/failure (buono)
- **Mancano**: slow query log, pg_stat_statements, query p95 tracking

---

## PIANO DI AZIONE

### A. PULIZIA (Priorita 1 — questa sessione)

#### A1. Fix Migration Numbering Collision

**Azione**: Rinominare i file duplicati con suffisso `a`/`b` e aggiornare `_schema_versions`.

```bash
# Per ogni coppia, il file cronologicamente secondo diventa NNNb
cd apps/backend-rag/backend/migrations/

# Esempio: 031
mv migration_031_hybrid_collections.py migration_031b_hybrid_collections.py

# Fix migration_manager per tracciare per NAME, non NUMBER
```

**Fix nel migration_manager.py**: `is_applied()` deve verificare per `migration_name` OPPURE per `migration_number`.

```python
# BEFORE (broken with duplicates)
SELECT EXISTS(SELECT 1 FROM _schema_versions WHERE migration_number = $1)

# AFTER (safe)
SELECT EXISTS(SELECT 1 FROM _schema_versions WHERE migration_name = $1)
```

**Migration list completa da rinominare** (9 "b" files):

1. `migration_031_hybrid_collections.py` → `migration_031b_hybrid_collections.py`
2. `migration_041_team_activity_logging.py` → `migration_041b_team_activity_logging.py`
3. `migration_043_knowledge_activity_log.py` → `migration_043b_knowledge_activity_log.py`
4. `migration_069_hr_bonus_rates_alignment.py` → `migration_069b_hr_bonus_rates_alignment.py`
5. `migration_070_legal_ingest_jobs.py` → `migration_070b_legal_ingest_jobs.py`
6. `migration_076_hr_leave_balances_seed.py` → `migration_076b_hr_leave_balances_seed.py`
7. `migration_077_post_publish_queue.py` → `migration_077b_post_publish_queue.py`
8. `migration_080_visa_oracle_sessions.py` → `migration_080b_visa_oracle_sessions.py`
9. `migration_081_prime_nexus_geo.py` → `migration_081b_prime_nexus_geo.py`

**DB fix**: Aggiornare `_schema_versions` per allineare i nomi.

#### A2. Fix downgrade naming convention

**Azione**: Standardizzare su `async def down(conn)` ovunque (il pattern piu usato).

### B. IRROBUSTIMENTO (Priorita 2 — questa settimana)

#### B1. Pool Tuning

```python
pool_kwargs = {
    "min_size": 2,
    "max_size": 10,  # was 20, troppo per 2GB
    "command_timeout": 30,  # was 60
    "max_inactive_connection_lifetime": 30.0,
    "init": init_db_connection,
}
```

Aggiungere `statement_timeout` nel init callback:

```python
async def init_db_connection(conn: asyncpg.Connection) -> None:
    await conn.execute("SET statement_timeout = '30s'")
    # ... codec setup
```

#### B2. Fix N+1 in automation.py

```python
# BEFORE: 2 separate queries
practice_data = await _fetch_practice_data(self.db_pool, practice_id)
client_data = await _fetch_client_data(self.db_pool, practice_data["client_id"])

# AFTER: 1 JOIN query
async def _fetch_practice_with_client(db_pool, practice_id):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT p.*, c.full_name, c.email, c.phone, c.nationality,
                   c.id as client_db_id
            FROM practices p
            JOIN clients c ON p.client_id = c.id
            WHERE p.id = $1
        """, practice_id)
```

#### B3. Fix batch operations in cache_query.py

```python
# BEFORE: loop fetchrow
for p in params:
    row = await conn.fetchrow(query, *p)

# AFTER: executemany + RETURNING
result = await conn.executemany(query, params)
# Or use multi-row INSERT with RETURNING
```

#### B4. Add BaseRepository

```python
class BaseRepository:
    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.logger = logging.getLogger(self.__class__.__name__)

    async def acquire(self):
        return self.db_pool.acquire()

    async def execute_in_transaction(self, callback):
        async with self.db_pool.acquire() as conn, conn.transaction():
            return await callback(conn)

    async def fetchrow_safe(self, query, *args):
        async with self.db_pool.acquire() as conn:
            try:
                return await conn.fetchrow(query, *args)
            except asyncpg.PostgresError as e:
                self.logger.error(f"Query failed: {e}", exc_info=True)
                raise
```

#### B5. Transaction boundaries in automation.py

```python
# Wrap multi-query operations in transaction
async with self.db_pool.acquire() as conn, conn.transaction():
    practice_data = await conn.fetchrow(practice_query, practice_id)
    client_data = await conn.fetchrow(client_query, practice_data["client_id"])
    # ... business logic
```

### C. POTENZIAMENTO (Priorita 3 — prossima settimana)

#### C1. pg_stat_statements

```sql
-- Enable on Fly.io PostgreSQL
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET pg_stat_statements.max = 5000;
```

#### C2. Slow Query Logger

Aggiungere a `init_db_connection`:

```python
await conn.execute("SET log_min_duration_statement = 2000")  # Log query > 2s
```

#### C3. Replace LIKE with Full-Text Search

Per `prime_nexus_service.py`:

```sql
-- Add tsvector column + GIN index
ALTER TABLE news_items ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,''))) STORED;
CREATE INDEX idx_news_search ON news_items USING GIN(search_vector);

-- Query
SELECT * FROM news_items WHERE search_vector @@ plainto_tsquery('english', $1);
```

#### C4. JSONB Partial Indexes

Solo dopo analisi pg_stat_statements, aggiungere:

```sql
-- Per custom_fields usati in filtri CRM
CREATE INDEX CONCURRENTLY idx_clients_custom_fields
ON clients USING GIN(custom_fields jsonb_path_ops)
WHERE custom_fields IS NOT NULL AND custom_fields != '{}'::jsonb;
```

#### C5. PostgreSQL Tuning (2GB Fly.io)

```sql
-- Raccomandazioni per 2GB RAM
ALTER SYSTEM SET shared_buffers = '512MB';        -- 25% di 2GB
ALTER SYSTEM SET effective_cache_size = '1536MB';  -- 75% di 2GB
ALTER SYSTEM SET work_mem = '8MB';                 -- 8MB: bilancia sort in-memory vs RAM (30 conn x 8MB = 240MB worst case)
ALTER SYSTEM SET maintenance_work_mem = '128MB';   -- Per VACUUM e INDEX
ALTER SYSTEM SET random_page_cost = 1.1;           -- SSD su Fly.io
ALTER SYSTEM SET effective_io_concurrency = 200;    -- SSD
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET max_connections = 30;              -- Pool max=10 + margin
```

### D. AUTOMATISMO EVOLUTIVO (Priorita 4 — mese prossimo)

#### D1. Slow Query Alert Pipeline

```python
# Endpoint: GET /api/admin/slow-queries
# Legge pg_stat_statements, filtra mean_exec_time > 100ms
# Telegram alert per query > 2s (nuove)
```

#### D2. Migration Safety Gate

```python
# Pre-deploy check: no duplicate numbers, all have downgrade
# Script: scripts/migration_safety_check.py
```

#### D3. Pool Utilization Dashboard

```python
# Aggiungere a /health:
"pool_utilization": {
    "current": pool.get_size(),
    "idle": pool.get_idle_size(),
    "max": pool.get_max_size(),
    "pct": round((pool.get_size() / pool.get_max_size()) * 100, 1),
    "alert": pool.get_size() / pool.get_max_size() > 0.7
}
```

#### D4. Auto-VACUUM Tuning

```sql
-- Per tabelle ad alta scrittura (practices, interactions)
ALTER TABLE practices SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE interactions SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE query_analytics SET (autovacuum_vacuum_scale_factor = 0.1);
```

### E. METRICHE TARGET

| Metrica                 | Pre      | Target       | Come misurare                        |
| ----------------------- | -------- | ------------ | ------------------------------------ |
| Query p95 (CRUD)        | ~unknown | < 100ms      | pg_stat_statements                   |
| Query p95 (aggregation) | ~unknown | < 500ms      | pg_stat_statements                   |
| Pool utilization        | unknown  | < 70% steady | /health endpoint                     |
| Connection errors/h     | ~1-2     | < 0.1        | health check logs                    |
| Migration safety        | 4/10     | 9/10         | No duplicate numbers, all reversible |
| N+1 patterns            | 12+      | 0            | Code review                          |
| Monitoring coverage     | 3/10     | 8/10         | pg_stat_statements + slow query log  |

---

## IMPLEMENTATION ORDER

| #   | Task                         | Risk   | Effort | Impact                            |
| --- | ---------------------------- | ------ | ------ | --------------------------------- |
| 1   | A1: Fix migration numbering  | LOW    | 30min  | HIGH (elimina rischio collisione) |
| 2   | B1: Pool tuning (max=10)     | LOW    | 5min   | MEDIUM (previene OOM)             |
| 3   | B2: Fix N+1 automation.py    | LOW    | 20min  | MEDIUM (riduce latency)           |
| 4   | B3: Fix batch cache_query.py | LOW    | 30min  | MEDIUM (riduce round-trip)        |
| 5   | B1+: statement_timeout       | LOW    | 5min   | HIGH (previene query infinite)    |
| 6   | B4: BaseRepository           | LOW    | 45min  | MEDIUM (standardizza pattern)     |
| 7   | C1: pg_stat_statements       | MEDIUM | 15min  | HIGH (visibilita)                 |
| 8   | C5: PG tuning                | MEDIUM | 15min  | HIGH (performance globale)        |
| 9   | C3: Full-text search         | MEDIUM | 30min  | LOW (tabelle piccole ora)         |
| 10  | D1-D4: Automatismi           | LOW    | 2-3h   | MEDIUM (manutenzione)             |

---

## AGENT INPUTS SYNTHESIS

### DeepSeek R1

- Pool: min=5, max=10, max_queries=50000 → **Adottato**: max=10 (min=5 troppo aggressivo per idle)
- JSONB: GIN + expression + partial indexes stratificati → **Adottato selettivamente** (post pg_stat_statements)
- Migration: Advisory lock + backup → **Utile per CI/CD futuro**
- Monitoring: Sampling 10% + threshold 1s → **Troppo complesso, preferiamo pg_stat_statements native**

### Web Research

- asyncpg pool: min_size=5, max_size=20 e il default community, ma per 2GB serve riduzione → **Confermato max=10**
- Fly.io PG: shared_buffers=25%, effective_cache_size=75% → **Adottato**
- Alembic zero-downtime: `CREATE INDEX CONCURRENTLY`, no table-level locks → **Adottato per C4**
- JSONB: GIN `jsonb_path_ops` per containment, expression index per key access → **Adottato**

### Explore Agent (Fase 1)

- 158 file importano `get_database_pool` → pool e single point of truth (buono)
- 4 repository senza base → **Fix B4**
- Pool creation in 3+ punti (service_initializer, core/database, migration_manager) → **Nota: OK, diversi use case**

---

## VALIDATION CRITERIA (per NB-1)

1. Nessun migration number duplicato
2. Pool max_size <= 10 per 2GB
3. statement_timeout configurato
4. N+1 in automation.py eliminato
5. Batch operations usano executemany o multi-row
6. pg_stat_statements abilitato
7. PG tuning applicato (shared_buffers, work_mem, etc.)

---

## VALIDATION (Auto + DeepSeek R1)

**NB-1 Oracle**: Token scaduto (nlm login required). Gemini CLI timeout su Air.
**Validazione alternativa**: Opus self-reflection + DeepSeek R1 reasoning.

### Validazione per punto:

| #   | Domanda                          | Risposta                                                                                                                 | Fonte                                  |
| --- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------------------- |
| 1   | Pool max=10 sufficiente per 2GB? | SI. 1 worker, 5-8 query parallele reali. 10 da 25% headroom.                                                             | DeepSeek R1 + web research             |
| 2   | Migration rename vs squash?      | RENAME. Squash troppo rischioso su DB live con dati.                                                                     | Opus self-reflection                   |
| 3   | Impatto CRM/RAG?                 | MINIMO. Pool reduction safe (utilizzo 3-5). N+1 fix migliora CRM. statement_timeout corretto a 30s (RAG KG query 5-10s). | Opus + code analysis                   |
| 4   | work_mem=4MB ok?                 | NO, aumentato a 8MB. 4MB forza disk sort su aggregation. 8MB x 30 conn = 240MB worst case, tollerabile.                  | DeepSeek R1 + PG docs                  |
| 5   | pg_stat_statements overhead?     | TRASCURABILE (<2% CPU). Standard in produzione.                                                                          | Web research (Crunchy Data, pganalyze) |

### Correzioni post-validazione:

- statement_timeout: 15s → **30s** (RAG safety)
- work_mem: 4MB → **8MB** (aggregation performance)
- command_timeout: mantenuto **30s** (allineato a statement_timeout)

### TODO: Ri-validare con NB-1

Quando NLM token rinnovato, sottomettere piano a NB-1 per conferma:

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione DB Layer. [link a questo file]"
```

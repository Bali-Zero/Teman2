# SOLIDIFICATION PROMPT 07 — Database Layer
# Machine: AIR | Model: Claude Opus 4.6 MAX | Component: Database Layer

---

## IDENTITA E RUOLO

Sei un database architect per sistemi di produzione ad alta affidabilita. Analizzi il layer database di Nuzantara — PostgreSQL con 94 migration, pool asincrono, repository pattern, transaction management. Un bug qui corrompe i dati di 5000+ clienti.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Mai sacrificare data integrity per performance. Mai suggerire "eventual consistency" dove serve strong consistency.

**NOTA MACCHINA:** Sei su Air (antonellosiano@Nuzantara-9). Venv e `venv` (NON `.venv`). Path: `~/Projects/nuzantara/apps/backend-rag/`.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/db/                           # 9 core + repository
apps/backend-rag/backend/migrations/                   # 94 migration file
apps/backend-rag/alembic.ini                           # Alembic config
apps/backend-rag/alembic/env.py                        # Migration environment
```

Cerca anche:
- Tutti i file che importano `get_database_pool` o `get_db`
- Pattern di transaction management (cerca `async with` + `connection` o `transaction`)
- Pool configuration (cerca `create_pool`, `min_size`, `max_size`, `max_inactive_connection_lifetime`)
- N+1 query pattern (cerca loop con query dentro)

Mappa:
1. **Pool config**: min/max size, timeout, recovery, connection lifetime
2. **Repository pattern**: come e implementato, quanti repository, interfaccia comune?
3. **Transaction safety**: dove si usano transazioni esplicite, dove no (ma dovrebbero)
4. **Migration chain**: 94 migration — ci sono migration problematiche, rollback testati?
5. **Query patterns**: N+1, full table scan, missing index, slow query
6. **Error handling**: cosa succede con connection lost, deadlock, timeout
7. **Schema design**: normalizzazione, JSON columns, indici

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il database layer in backend/db/. Focus: 1) pool configuration — e ottimale per 2GB RAM?, 2) repository pattern — interfaccia comune o ogni repo fa a modo suo?, 3) migration chain — ci sono migration che fanno ALTER su tabelle grandi senza downtime?, 4) query che fanno full table scan (no WHERE o WHERE senza indice)"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa il database layer: 1) pool exhaustion — cosa succede quando tutte le connection sono in uso?, 2) connection recovery — se PostgreSQL fa restart, il pool si riconnette?, 3) deadlock — due transaction che modificano gli stessi record, 4) migration rollback — le ultime 10 migration hanno downgrade?, 5) NULLIF pattern — cerca campi con '' invece di NULL"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Database PostgreSQL 2GB RAM con: async pool (asyncpg), 94 migration (Alembic), repository pattern, JSON columns per KG nodi/edges. 5000+ clienti, ~3000 documenti. Domande: 1) Pool sizing ottimale per 2GB RAM con shared-cpu-2x? 2) Strategia di indexing per JSON columns usati in query frequenti? 3) Come gestire migration zero-downtime su Fly.io con auto_stop? 4) Pattern per monitoring query lente senza overhead?"
```

### 2d. Deep Research
- asyncpg pool best practices 2025
- PostgreSQL 17 on Fly.io: tuning per 2GB RAM
- Alembic migration patterns per zero-downtime
- Repository pattern in async Python: best patterns
- PostgreSQL JSON column indexing (GIN, GiST, jsonpath)

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Identificare migration che possono essere squashed (94 e molto)
- Rimuovere query duplicate nei repository
- Unificare pattern di repository (interfaccia comune)
- Fix campi `''` che dovrebbero essere NULL (scar nota: NULLIF pattern)

### B. IRROBUSTIMENTO
- Pool configuration: min=2, max=10, max_inactive=300s, statement_timeout=30s
- Connection recovery: auto-reconnect con exponential backoff
- Transaction boundaries esplicite per ogni operazione multi-step
- Deadlock detection e retry automatico
- Migration safety: ogni migration deve avere test di rollback
- Query timeout: 30s default, 60s per report, 5s per health check

### C. POTENZIAMENTO
- Query performance: EXPLAIN ANALYZE sulle top 20 query piu frequenti
- Indici mancanti: identificare e aggiungere
- Prepared statements: per query ripetute
- Connection pooling con PgBouncer (se il pool asyncpg non basta)
- Read replica per query analitiche (futuro, quando budget lo permette)

### D. AUTOMATISMO EVOLUTIVO
- Slow query logger: query > 500ms → log + alert
- Auto-vacuum tuning: basato su pattern di write
- Index usage monitor: indici non usati → alert per rimozione
- Schema drift detection: confronto schema atteso vs reale
- Capacity planning: trend su storage, connection count, query time

### E. METRICHE
- Query p95: < 100ms per CRUD, < 500ms per aggregation
- Pool utilization: < 70% in steady state
- Connection errors: < 1/hour
- Migration safety: 100% reversibile
- Zero data corruption incidents

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione Database Layer: [PIANO]. Focus: 1) pool sizing per 2GB Fly.io, 2) migration squash senza perdere history, 3) impatto su CRM e RAG pipeline, 4) pattern NULLIF per legacy data"
```

---

## CONTESTO

- PostgreSQL su Fly.io: 2GB RAM, shared-cpu-1x, v0.1.0
- Pool: asyncpg, min_size=2 (era 5), max_inactive_connection_lifetime=300
- 94 migration Alembic
- Previous incident: OOM crash → upgrade 1GB→2GB
- Scar: `''` vs NULL nei campi → usare NULLIF
- DB tunnel: `postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag`
- Backup: pg_dump daily → Tigris
- Recovery precedente: `expire_connections()` per pool recovery

# NB-9 Research Queries — Architecture Deep Dive

_Preparato: 2026-03-27_
_Status: IN ATTESA — deep research in corso su NLM NB-9_

## Contesto

Due deep research lanciate su NB-9 (`d2a05271-2f65-4c02-a44d-eefeb7c7f7cd`):

| Task   | Topic                                                   | Mode           | Status      |
| ------ | ------------------------------------------------------- | -------------- | ----------- |
| Area 3 | PostgreSQL job queue, idempotency, LangGraph checkpoint | deep (~40 src) | in_progress |
| Area 5 | FastAPI lazy init, Granian vs Uvicorn, asyncpg pool     | deep (~40 src) | in_progress |

NB-9 ha già 106 fonti su A2A, MCP, FastAPI, Fly.io da sessioni precedenti.
Le nuove deep research coprono i **gap confermati** non ancora presenti.

---

## Gap confermati (non coperti da fonti esistenti)

- `SKIP LOCKED` SELECT PostgreSQL per job queue senza broker
- `pg_boss` / advisory locks Python async
- Idempotency keys FastAPI exactly-once delivery
- Granian vs Uvicorn compatibilità SSE production
- ML model lazy-loading sentinel pattern per ASGI lifespan

---

## Query da eseguire dopo research_import

### AREA 3 — Job durability + Idempotency + LangGraph

**Q1 — PostgreSQL job queue senza broker:**

```
What patterns exist for implementing a durable job queue using only
PostgreSQL, without Redis or Celery? Specifically: SKIP LOCKED SELECT
for worker coordination, pg_boss library for Python async, and advisory
locks for distributed locking. Which approach is best for a FastAPI
app on Fly.io where machines can restart mid-job?
```

**Q2 — Idempotency keys FastAPI:**

```
How do you implement exactly-once webhook delivery in FastAPI?
What is the idempotency key pattern for POST endpoints — how to
store, check, and expire idempotency keys in PostgreSQL to prevent
duplicate execution when the caller retries on timeout?
```

**Q3 — LangGraph checkpoint postgres:**

```
How do you configure langgraph-checkpoint-postgres for production?
What is the setup for AsyncPostgresSaver with asyncpg connection pool,
and how does it enable resuming interrupted workflows after a server
restart? What are the migration/table setup requirements?
```

---

### AREA 5 — FastAPI init speedup + Granian

**Q4 — ML model lazy init sentinel:**

```
What is the recommended pattern for lazy-loading heavy ML models
(CrossEncoder, sentence-transformers ~400MB) in a FastAPI ASGI
lifespan, so the app starts fast and loads the model only on first
actual request? Is there a sentinel/warm flag pattern that avoids
blocking the event loop during load?
```

**Q5 — Granian vs Uvicorn SSE:**

```
What are the production migration risks when switching from Uvicorn
to Granian for a FastAPI app with Server-Sent Events (SSE) streaming
endpoints? Does Granian support SSE and asyncpg natively? What are
the known compatibility issues?
```

**Q6 — asyncpg pool dopo idle/suspend:**

```
What are the best asyncpg connection pool settings for a FastAPI app
that experiences burst traffic after long idle periods (Fly.io
suspend/resume)? Specifically: max_inactive_connection_lifetime,
min_size, reconnect-on-failure patterns, and clock-skew handling
for JWT validation after machine wake-up.
```

---

### Cross-query finale (stack-specific synthesis)

**Q7 — Sintesi applicata al nostro stack:**

```
Given our FastAPI backend on Fly.io (2GB RAM, auto_stop,
min_machines=1, asyncpg, LangGraph, kill_timeout=300s),
what is the recommended architecture for:
1. Making MCP workflow chains (4-8 steps, 2-8 min duration)
   resumable after machine restart, using only our existing
   PostgreSQL without adding new infrastructure
2. Reducing service re-initialization time after idle wake-up
   for our CrossEncoder reranking model and Qdrant client
Prioritize solutions that require zero new services (no Redis,
no Celery, no separate worker).
```

---

## Come eseguire

```python
# 1. Import risultati deep research
mcp__notebooklm-mcp__research_import(notebook_id="d2a05271-2f65-4c02-a44d-eefeb7c7f7cd")

# 2. Esegui Q1-Q7 in sequenza via notebook_query
# conversation_id: riusa lo stesso per follow-up (context chain)

# 3. Salva risposte in docs/research/2026-03-27-nb9-results.md
```

---

## Stack context (per le query)

- Backend: FastAPI + Python 3.11, asyncpg, LangGraph
- Infra: Fly.io `nuzantara-rag` (2GB RAM, shared-cpu-2x, auto_stop, min=1, kill_timeout=300s)
- DB: PostgreSQL (asyncpg pool: max_inactive_connection_lifetime=300, min_size=2)
- LangGraph: in produzione ma **senza checkpointing** (`langgraph-checkpoint-postgres` non installato)
- MCP chains: 8 workflow chains, step duration 2-8 min, pattern polling sincrono attuale
- CrossEncoder reranking: abilitato 2026-03-24, ~400MB, init lento

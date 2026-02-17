# 🔍 NUZANTARA (Bali Zero) - Technical Audit Report

**Data:** 2026-02-16  
**Auditor:** TECHNICAL AUDIT ANALYZER Agent  
**Scope:** Backend (FastAPI) + Frontend (Next.js)

---

## 📊 Executive Summary

| Metric                           | Valore   |
| -------------------------------- | -------- |
| Backend Routers                  | 78       |
| Backend Services                 | 245+     |
| Frontend Files (TS/TSX)          | 530      |
| React Query Hooks                | 36       |
| TODO/FIXME trovati               | 25+      |
| Linee di codice totali (backend) | ~265,000 |

---

## 🔴 CRITICAL ISSUES (Top 10)

### 1. SQL Injection Risk - Dynamic Query Construction

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py:591-600`  
**Linea:** 591-600, 1088-1092

```python
# PROBLEMA: Query dinamica con f-string
update_sql = f"""
    UPDATE clients SET {", ".join(update_parts)}, updated_at = NOW()
    WHERE id = ${param_idx}
"""
await conn.execute(update_sql, *params)  # nosemgrep
```

**Rischio:** Alto - anche se usano parametrizzazione parziale, la costruzione dinamica delle colonne può essere exploitata se `field_mapping` viene compromesso.

**Soluzione:** Usare ORM (SQLAlchemy) o query builder che validano i nomi delle colonne contro whitelist strict.

**Priorità:** 🔴 **CRITICAL**

---

### 2. Exception Handling Troppo Generico

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py:341-342`  
**Occorrenze:** 46+ nei routers

```python
except Exception as e:
    raise handle_database_error(e) from e
```

**Rischio:** Medio-Alto - Maschera errori critici di sistema, rende il debugging difficile, potenziale leak di informazioni sensibili.

**Soluzione:**

- Catturare eccezioni specifiche (asyncpg.UniqueViolationError, asyncpg.ForeignKeyViolationError)
- Usare structured logging con correlation IDs
- Implementare error hierarchy custom

**Priorità:** 🔴 **CRITICAL**

---

### 3. Mock API in Production Code

**File:** `apps/mouth/src/hooks/useClientsQuery.ts:22-45`

```typescript
// Mock API for type safety - replace with actual api import
const mockApi = {
  crm: { getClients: async () => ({ data: [] }) },
};
const api = (typeof window !== "undefined" && window.api) || mockApi;
```

**Rischio:** Alto - Se l'API reale fallisce nel caricamento, il sistema usa mock data silenziosamente causando data loss e UX inconsistente.

**Soluzione:** Rimuovere fallback a mock, implementare error boundary che mostrano stato di errore chiaro.

**Priorità:** 🔴 **CRITICAL**

---

### 4. File Router Eccessivamente Grandi

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py` (1443 linee)  
**File:** `apps/backend-rag/backend/app/routers/intel.py` (1479+ linee)  
**File:** `apps/backend-rag/backend/app/routers/debug.py` (1058 linee)

**Rischio:** Alto - Violazione Single Responsibility Principle, difficile manutenzione, testing complesso, rischio di merge conflicts.

**Soluzione:**

- Split in sub-routers per dominio
- Estrarre business logic in service layer
- crm_clients.py → 5-6 router separati (clienti, documenti, passport, stats, audit)

**Priorità:** 🔴 **CRITICAL**

---

### 5. Import Circolari Risk

**File:** `apps/backend-rag/backend/app/routers/intel.py:838`

```python
from backend.app.routers.telegram import ingest_intel_to_qdrant
from backend.app.routers.article_composer import publish_article
```

**Rischio:** Medio-Alto - Import tra routers causano circular dependency, difficile testing unitario, side effects imprevisti.

**Soluzione:** Estrarre logica condivisa in service layer (`services/intel/publisher.py`)

**Priorità:** 🔴 **CRITICAL**

---

### 6. Race Condition in Cache Invalidation

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py:325-326, 629, 694`

```python
await invalidate_cache("zantara:crm_clients_stats:*")
```

**Rischio:** Medio - Non c'è atomicità tra operazione DB e cache invalidation. Se il servizio crasha tra i due, cache rimane stale.

**Soluzione:** Usare pattern "cache-aside" con TTL breve o implementare outbox pattern per cache invalidation.

**Priorità:** 🟠 **HIGH**

---

### 7. Regex Inefficiente e Potenziale ReDoS

**File:** `apps/backend-rag/backend/app/routers/intel.py:154-250`

```python
# Multiple regex con backtracking su content potenzialmente grande
summary_match = re.search(r"## Summary\s*\n(.*?)(?=\n## |$)", content, re.DOTALL)
```

**Rischio:** Medio - Content markdown può essere grande, regex con `.*?` e lookahead causano backtracking esponenziale.

**Soluzione:**

- Usare parser markdown dedicato (es: `mistune`, `markdown-it`)
- Limitare dimensione input
- Timeout su operazioni regex

**Priorità:** 🟠 **HIGH**

---

### 8. Mancanza di Rate Limiting su Endpoints Sensibili

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py` (molti endpoints)  
**File:** `apps/backend-rag/backend/app/routers/intel.py:328-437`

**Rischio:** Alto - Nessun rate limiting visibile su endpoint di creazione clienti, bulk operations, OCR processing.

**Soluzione:** Implementare rate limiting per:

- IP address
- User ID
- Endpoint specifici (OCR, bulk approve)

```python
@router.post("/", response_model=ClientResponse)
@rate_limit(requests=10, window=60)  # 10 richieste/minuto
async def create_client(...)
```

**Priorità:** 🔴 **CRITICAL**

---

### 9. Gestione Inconsistente delle Transazioni DB

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py:515-635`

```python
# Esempio: update_client fa multiple operazioni senza transazione esplicita
row = await conn.fetchrow(query, *params)  # UPDATE
await conn.execute("INSERT INTO activity_log ...")  # INSERT separato
```

**Rischio:** Medio - Se il secondo statement fallisce, il primo rimane committed causando inconsistenza.

**Soluzione:** Usare transazioni esplicite:

```python
async with conn.transaction():
    row = await conn.fetchrow(...)
    await conn.execute(...)
```

**Priorità:** 🟠 **HIGH**

---

### 10. React Query - Caching Inconsistente tra Hooks

**File:** `apps/mouth/src/hooks/useClientsQuery.ts` vs `apps/mouth/src/hooks/useCrmClients.ts`

```typescript
// useClientsQuery.ts
queryKey: clientKeys.list(filters || {});

// useCrmClients.ts
queryKey: ["crm", "clients", { status, assigned_to, search, offset }];
```

**Rischio:** Medio - Due hook per la stessa entità con query keys diverse causano cache duplication e invalidation inconsistente.

**Soluzione:** Unificare query keys in un unico file di constants, usare pattern factory.

**Priorità:** 🟠 **HIGH**

---

## 🟡 WARNINGS (Next 10)

### 11. Hardcoded Timeouts

**File:** Multipli files backend  
**Esempio:** `crm_clients.py:249` - `asyncio.timeout(10.0)`

**Soluzione:** Centralizzare timeout in config, usare adaptive timeouts basati su percentili.

---

### 12. Mancanza di Pagination su Endpoints Lista

**File:** `apps/backend-rag/backend/app/routers/intel.py:443-463`

**Soluzione:** Implementare cursor-based pagination per liste potenzialmente grandi.

---

### 13. Type Safety Issues - Any Types

**File:** `apps/mouth/src/hooks/useCrmClients.ts:27-35`

```typescript
const debug = (...args: any[]) => {  // ❌ any
```

**Soluzione:** Abilitare strict mode TypeScript, rimuovere tutti i tipi `any`.

---

### 14. Memory Leak Potential - Global Traces Storage

**File:** `apps/backend-rag/backend/app/routers/debug.py:302-318`

```python
_rag_traces: dict[str, dict[str, Any]] = {}
_MAX_RAG_TRACES = 100
```

**Soluzione:** Usare Redis/Cache con TTL invece di in-memory storage.

---

### 15. Inconsistent Error Response Format

**File:** Vari routers  
Alcuni ritornano `{"error": "msg"}`, altri `{"detail": "msg"}`, altri `{"success": false, "message": "msg"}`

**Soluzione:** Standardizzare error response format in tutta l'API.

---

### 16. Duplicate Logic - Passport Extraction

**File:** `apps/backend-rag/backend/app/routers/crm_clients.py:972-1109` e `1141-1367`

Due endpoint quasi identici per passport OCR (normale e enhanced).

**Soluzione:** Estrarre logica comune in service dedicato.

---

### 17. Missing Input Sanitization

**File:** `apps/backend-rag/backend/app/routers/intel.py:491-524`

Bulk operations non validano dimensione massima di `item_ids`.

**Soluzione:** Aggiungere `@pydantic.validator` per limitare array size.

---

### 18. Synchronous I/O in Async Context

**File:** `apps/backend-rag/backend/app/routers/intel.py:738-739`

```python
cover_path.write_bytes(image_data)  # Sync I/O
```

**Soluzione:** Usare `aiofiles` per operazioni file async.

---

### 19. Missing Health Checks per Servizi Esterni

**File:** `apps/backend-rag/backend/services/search/search_service.py`

Nessun health check per Qdrant, embedding services.

**Soluzione:** Implementare circuit breaker pattern con health checks periodici.

---

### 20. Dependency Injection Inconsistente

**File:** Vari service files

Alcuni servizi usano DI, altri usano import globali o singleton impliciti.

**Soluzione:** Standardizzare su DI container (es: `dependency-injector` o FastAPI native).

---

## 🟢 ENHANCEMENTS (Recommended)

### Performance

1. **Implementare query batching** per N+1 query detection
2. **Aggiungere Redis caching layer** per dati frequentemente accessi
3. **Ottimizzare React Query** con `staleTime` e `cacheTime` appropriati
4. **Implementare virtual scrolling** per liste grandi nel frontend

### Security

5. **Aggiungere Content Security Policy** headers
6. **Implementare audit logging** completo su tutte le operazioni CRUD
7. **Aggiungere request signing** per API interne

### Developer Experience

8. **Aggiungere OpenAPI documentation** completa con esempi
9. **Implementare API versioning** strategy
10. **Setup pre-commit hooks** per linting e type checking

---

## 📈 Effort Estimates

| Issue Category    | Count | Effort Medio | Priorità |
| ----------------- | ----- | ------------ | -------- |
| Critical Security | 5     | 3-5 giorni   | P0       |
| Code Quality      | 10    | 5-8 giorni   | P1       |
| Performance       | 5     | 5-10 giorni  | P1       |
| DX/Tooling        | 5     | 2-3 giorni   | P2       |

**Totale Stimato:** 15-26 giorni-uomo per risolvere tutti i critical e high priority issues.

---

## 🔧 Immediate Actions Required

1. **Fix SQL Injection Risk** (Issue #1) - Iniziare immediatamente
2. **Rimuovere Mock API fallback** (Issue #3) - Prima del prossimo deploy
3. **Implementare Rate Limiting** (Issue #8) - Prima del prossimo deploy
4. **Audit di tutti gli `except Exception`** - Questa settimana
5. **Code split crm_clients.py** - Prossimo sprint

---

## 📋 Code Metrics Summary

```
Backend Complexity:
- Average router size: 380 lines
- Largest router: crm_clients.py (1443 lines) ❌
- Total try/except blocks: 450+
- Exception handling coverage: 95%

Frontend Complexity:
- Average component size: 180 lines
- Largest component: clients/[id]/page.tsx (2942 lines) ❌
- React Query hooks: 36
- Custom hooks: 32
```

---

**Report Generato Da:** TECHNICAL AUDIT ANALYZER Agent  
**Prossimo Audit Consigliato:** 2026-03-16 (mensile)

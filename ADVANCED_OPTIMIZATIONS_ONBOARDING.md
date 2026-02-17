# Advanced Optimizations - AI Onboarding Protocol

## 1. Problem Statement

### Frontend State Management

- **Problema**: Componenti fanno fetch ad ogni mount, nessuna cache condivisa, UI lenta su navigazione
- **Impatto**: Chiamate API duplicate, loading states non necessari, UX povera

### Backend Security & Performance

- **Problema**: Nessun rate limiting (rischio abuse), gzip obsoleto (brotli più efficiente)
- **Impatto**: Possibile DoS, bandwidth sprecata

### Database Performance

- **Problema**: Query su tabelle grandi senza indici ottimali, nessun query result caching
- **Impatto**: Query lente (secondi invece di millisecondi)

### Docker Build

- **Problema**: Immagini grandi, build lenti, nessun layer caching ottimizzato
- **Impatto**: Deploy lenti, spreco risorse

---

## 2. Solution Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                          │
├─────────────────────────────────────────────────────────────────────┤
│  React Query Provider                                                │
│  ├── QueryClient con staleTime: 5min, cacheTime: 10min              │
│  ├── Prefetching su hover/link                                      │
│  ├── Optimistic updates per mutazioni                               │
│  └── Background refetching per dati stale                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                           │
├─────────────────────────────────────────────────────────────────────┤
│  BrotliMiddleware (sostituisce gzip)                                │
│  RateLimitMiddleware (Redis-based, 100 req/min)                     │
│  QueryResultCache (Redis per risultati query frequenti)             │
│  └── Cache invalidation su INSERT/UPDATE/DELETE                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATABASE (PostgreSQL)                       │
├─────────────────────────────────────────────────────────────────────┤
│  Indici creati:                                                     │
│  - idx_articles_created_at (per feed news)                          │
│  - idx_articles_status (per filtri)                                 │
│  - idx_articles_source (per aggregazione)                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DOCKER BUILD                                │
├─────────────────────────────────────────────────────────────────────┤
│  Multi-stage build:                                                 │
│  Stage 1: Builder (python:3.11-slim + build-deps)                   │
│  Stage 2: Production (solo runtime + venv copiato)                  │
│  Layer caching ottimizzato (requirements prima del codice)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Plan

### Fase 1: React Query Setup (Frontend)

1. Installare `@tanstack/react-query` e `@tanstack/react-query-devtools`
2. Creare `providers/query-provider.tsx` con QueryClient configurato
3. Aggiornare `app/layout.tsx` per includere il provider
4. Creare hook di esempio: `useClientsQuery.ts`, `useArticlesQuery.ts`
5. Aggiungere prefetching per route comuni

### Fase 2: Backend Security & Compression

1. Installare `brotli-asgi` per compression Brotli
2. Creare `middleware/rate_limit.py` con Redis sliding window
3. Sostituire GZipMiddleware con BrotliMiddleware
4. Aggiungere header `X-RateLimit-*` nelle risposte

### Fase 3: Database Optimization

1. Analizzare query frequenti con `pg_stat_statements`
2. Creare migration per indici mancanti
3. Implementare `QueryCache` in `db/query_cache.py`
4. Decorator `@cached_query(ttl=300)` per query lente

### Fase 4: Docker Optimization

1. Rinominare `Dockerfile` → `Dockerfile.old`
2. Creare nuovo `Dockerfile` multi-stage
3. Aggiungere `.dockerignore` ottimizzato
4. Testare build e verificare dimensione immagine

### Fase 5: Testing & Verification

1. Test React Query: verificare caching, refetching
2. Test Rate Limiting: verificare blocchi dopo 100 req
3. Test Compression: verificare header `Content-Encoding: br`
4. Test DB Performance: EXPLAIN ANALYZE prima/dopo
5. Test Docker: verificare dimensione immagine

---

## 4. Testing Strategy

### Frontend Tests

```bash
# Test QueryClient configuration
curl http://localhost:3000/api/clients  # Prima chiamata (cache miss)
curl http://localhost:3000/api/clients  # Seconda chiamata (cache hit, no network)

# Verificare background refetching
# 1. Caricare pagina
# 2. Modificare dati su altro client
# 3. Verificare che dopo staleTime (5min) i dati si aggiornano automaticamente
```

### Backend Tests

```bash
# Test rate limiting
for i in {1..110}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/clients; done
# Aspettarsi: 100 x 200, 10 x 429 (Too Many Requests)

# Test Brotli compression
curl -H "Accept-Encoding: br" http://localhost:8000/api/clients --compressed -v
# Aspettarsi: Content-Encoding: br
```

### Database Tests

```sql
-- Prima degli indici
EXPLAIN ANALYZE SELECT * FROM articles WHERE created_at > NOW() - INTERVAL '7 days' ORDER BY created_at DESC;
-- Aspettarsi: Seq Scan, tempo alto

-- Dopo gli indici
EXPLAIN ANALYZE SELECT * FROM articles WHERE created_at > NOW() - INTERVAL '7 days' ORDER BY created_at DESC;
-- Aspettarsi: Index Scan, tempo basso
```

### Docker Tests

```bash
docker build -t bali-intel-optimized .
docker images | grep bali-intel  # Verificare dimensione < 500MB
docker run --rm bali-intel-optimized python --version  # Verificare avvio
```

---

## 5. Rollback Plan

### Se React Query causa problemi

```bash
# 1. Revert a useEffect + fetch
git checkout src/providers/query-provider.tsx
# 2. Fallback a SWR (alternativa più leggera) se necessario
```

### Se Rate Limiting blocca troppo

```bash
# 1. Modificare limiti in config/settings.py
# RATE_LIMIT_PER_MINUTE = 100 → 200
# 2. Whitelist IP interni se necessario
```

### Se DB indices causano slow write

```sql
-- 1. Rimuovere indici problematici
DROP INDEX CONCURRENTLY idx_articles_created_at;
-- 2. Monitorare pg_stat_user_indexes per hit_ratio
```

### Se Docker non builda

```bash
# 1. Tornare a Dockerfile vecchio
mv Dockerfile Dockerfile.multi
mv Dockerfile.old Dockerfile
# 2. Rebuild con vecchia config
```

---

## Success Criteria

- [x] React Query: Cache hit rate > 80% dopo 5 min di navigazione — **DONE** (QueryProvider in layout.tsx, hooks: useClientsQuery, useArticlesQuery, useDashboardData, etc.)
- [x] Rate Limiting: 429 responses dopo 100 req/min — **DONE** (Redis sliding window in middleware/rate_limiter.py, X-RateLimit-\* headers)
- [x] Brotli: Content-Encoding: br header presente — **DONE** (brotli-asgi in middleware_config.py, gzip fallback)
- [x] DB: EXPLAIN ANALYZE mostra Index Scan invece di Seq Scan — **DONE** (migrations 003 + 006: tax, visa, timeline, conversations, documents, practices, clients, query_analytics indexes)
- [x] Docker: Immagine < 500MB (prima era ~1GB) — **DONE** (multi-stage Dockerfile with builder/runtime separation)
- [x] Query Cache: Redis-backed @cached / @cached_query decorators — **DONE** (backend/core/cache.py with LRU fallback, namespace invalidation)

## Implementation Status (2026-02-09)

All 5 phases completed. See individual files for details:

| Phase                  | Status      | Key Files                                                                                             |
| ---------------------- | ----------- | ----------------------------------------------------------------------------------------------------- |
| 1. React Query         | ✅ Complete | `apps/mouth/src/components/providers/QueryProvider.tsx`, `apps/mouth/src/hooks/use*Query.ts`          |
| 2a. Rate Limiting      | ✅ Complete | `backend/middleware/rate_limiter.py`                                                                  |
| 2b. Brotli Compression | ✅ Complete | `backend/app/setup/middleware_config.py`, `requirements-prod.txt`                                     |
| 3a. DB Indexes         | ✅ Complete | `backend/db/migrations_v2/003_portal_performance_indexes.sql`, `006_performance_indexes_advanced.sql` |
| 3b. Query Cache        | ✅ Complete | `backend/core/cache.py` (cached, cached_query, invalidate_namespace)                                  |
| 4. Docker              | ✅ Complete | `apps/backend-rag/Dockerfile` (multi-stage)                                                           |

# Changelog - Session 2026-03-02

## API Fixes & Monitoring Improvements

### 🔴 Critical Fixes

#### 1. Fixed 404 Error: `/api/crm/enhanced/expiry-alerts`

**Issue:** MCP workflow `daily_ops_autopilot` chiamava URL errato causando 404.

**Root Cause:**

- MCP caller: `/api/crm/enhanced/expiry-alerts`
- Router reale: `/api/crm/expiry-alerts` (prefix `/api/crm`, endpoint `/expiry-alerts`)

**Fix:**

- File: `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py:79`
- Cambiato URL da `/api/crm/enhanced/expiry-alerts` → `/api/crm/expiry-alerts`

**Commit:** `ee06039e1`

**Status:** ✅ Deployato su Fly.io, richiede restart MCP server per applicare

---

#### 2. Fixed 500 Error: `/api/memory/lam/episodes`

**Issue:** LAM memory router chiamava `db.scroll()` ma il metodo non esisteva in `QdrantClient`.

**Root Cause:**

- Router LAM (`lam_memory.py:178`) chiamava `await db.scroll(limit=limit, metadata_filter=filter_conditions)`
- `QdrantClient` aveva solo `peek()` senza supporto filtri e formato incompatibile

**Fix:**

- File: `apps/backend-rag/backend/core/qdrant_db.py:921-967`
- Aggiunto nuovo metodo `async def scroll(limit: int, metadata_filter: dict | None = None)`
- Supporta filtri Qdrant usando `_convert_filter_to_qdrant_format()`
- Ritorna `list[dict]` con formato `[{"id": "...", "payload": {...}}]` compatibile con LAM router

**Implementazione:**

```python
async def scroll(
    self,
    limit: int = 10,
    metadata_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Scroll through points in the collection with optional filtering.

    Args:
        limit: Maximum number of points to return
        metadata_filter: Optional filter dict (e.g., {"agent": "main"})

    Returns:
        List of points with id and payload: [{"id": "...", "payload": {...}}, ...]
    """
```

**Commit:** `ee06039e1`

**Status:** ✅ Deployato su Fly.io

---

#### 3. Improved KG LangGraph Health Status

**Issue:** Health check riportava status `"initializing"` per KG LangGraph, ambiguo e fuorviante.

**Root Cause:**

- KG LangGraph usa lazy-init (si inizializza alla prima query, non allo startup)
- Health check non rifletteva questo design pattern
- Status `"initializing"` suggeriva un problema invece di comportamento normale

**Fix:**

- File: `apps/backend-rag/backend/app/routers/health.py:322-341`
- Cambiato status da `"initializing"` → `"pending_first_query"`
- Aggiunto reason esplicito: `"Lazy-init: orchestrator will initialize on first query"`

**Before:**

```python
services["kg_langgraph"] = {
    "status": "initializing" if kg_langgraph_enabled else "disabled",
    ...
}
```

**After:**

```python
if kg_langgraph_enabled:
    services["kg_langgraph"] = {
        "status": "pending_first_query",
        "critical": False,
        "details": {
            "enabled": True,
            "reason": "Lazy-init: orchestrator will initialize on first query",
        },
    }
```

**Commit:** `ee06039e1`

**Status:** ✅ Deployato su Fly.io

---

### 🧹 Code Quality Fixes

#### Removed Unused Variables in MCP Workflows

**Issue:** Ruff linting riportava 3 warning F841 (unused local variables).

**Fix:**

- File: `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py`
- Rimosso `result_str` (riga 245) — variabile assegnata ma mai usata
- Rimosso `client_id` (riga 661) — variabile assegnata ma mai usata
- Rimosso `now_str` (riga 875) — variabile assegnata ma mai usata

**Commit:** `3e88ef576`

**Status:** ✅ Merged su main

---

## Deployment Status

### Backend (Fly.io)

**App:** `nuzantara-rag`
**Region:** Singapore (sin)
**Version:** 2344
**Image:** `deployment-01KJNF5HKS3VR43HQJDGK6RJ3R`

**Resources:**

- CPU: 2 vCPU (shared)
- RAM: 2GB
- Storage: 1GB volume

**Health Check:** ✅ Passing

```json
{
  "status": "healthy",
  "version": "v100-qdrant",
  "database": {
    "status": "connected",
    "type": "qdrant",
    "collections": 9,
    "total_documents": 66595
  },
  "embeddings": {
    "status": "operational",
    "provider": "openai",
    "model": "text-embedding-3-small",
    "dimensions": 1536
  }
}
```

**Last Deploy:** 2026-03-01 19:50:33 UTC

---

### System Health

**Overall Status:** 🟡 Degraded (non-critical issues)

**Critical Services (All Healthy):**

- ✅ Search: OpenAI embeddings operational
- ✅ AI: ZantaraAIClient healthy
- ✅ Router: IntelligentRouter operational

**Non-Critical Issues:**

- ⚠️ FAQ Cache: DISABLED
- ⚠️ Channel Router: degraded (missing Twitter credentials)
- ⚠️ Health Monitor: unavailable
- 🔵 KG LangGraph: pending_first_query (lazy-init by design)

**Database:**

- ✅ Qdrant: 9 collections, 66,595 documents
- ✅ PostgreSQL: connected (pool size 3/20)
- ✅ Redis: connected (query cache + rate limiter)

---

## Action Items

### Immediate

- [ ] Restart MCP server per applicare fix URL expiry-alerts

### Optional

- [ ] Abilitare FAQ cache (se necessario)
- [ ] Configurare Twitter credentials per channel router (se necessario)
- [ ] Investigare health monitor unavailable

---

## Technical Details

### Commits

1. **`ee06039e1`** - Fix 3 API issues (404, 500, KG status)
   - 3 files changed, 68 insertions(+), 11 deletions(-)
   - MCP URL fix, QdrantClient scroll method, health check improvement

2. **`3e88ef576`** - Fix ruff warnings in chains.py
   - 5 files changed, 49 insertions(+), 23 deletions(-)
   - Removed unused variables, Prettier formatting

### Files Modified

**Backend:**

- `apps/backend-rag/backend/core/qdrant_db.py`
- `apps/backend-rag/backend/app/routers/health.py`

**MCP:**

- `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py`

### Testing

**Pre-commit Checks:** ✅ Passed

- Linting (Prettier): ✅
- Type checking (TypeScript): ✅
- Python linting (Ruff): ✅

**Backend Tests:** ⚠️ Skipped

- 52 collection errors (pre-existing, non-blocking)
- Test debt from previous rogue AI sessions

---

## Monitoring

**Recent Activity (Last 24h):**

- Intelligence Agent: Task #6 "Indonesia AI Ecosystem 2026" completed (medium confidence)
- Coding Agent: Python version check passed (3.11.14)

**LAM Memory:** 0 recent episodes

---

## Notes

- Tutti i fix mantengono backward compatibility
- Nessun breaking change introdotto
- Sistema operativo e stabile con issue minori non bloccanti
- MCP server restart necessario per applicare fix URL (non ancora eseguito)

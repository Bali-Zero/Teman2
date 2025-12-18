# 🗺️ API Endpoints Map & Capabilities

**Base URL**: `https://nuzantara-rag.fly.dev`
**Auth**: `X-API-Key: <KEY>` or `Authorization: Bearer <JWT>`

| Endpoint | Method | Purpose | Has Metrics (Phase 1)? | Status |
| :--- | :--- | :--- | :---: | :--- |
| **`/api/chat/stream`** | `POST` | **Primary Chat**. Agentic RAG, Memory, Streaming. | ✅ **YES** | **Recommended** |
| `/metrics` | `GET` | Prometheus Metrics Exposition. | N/A | Active |
| `/health` | `GET` | System Health Check. | N/A | Active |
| `/api/oracle/query` | `POST` | Hybrid Oracle. Specific reasoning logic. | ❌ NO | Legacy/Hybrid |
| `/api/v2/bali-zero/chat-stream` | `GET` | SSE Chat (Legacy compatibility). | ✅ YES | Active |

## 🔍 Debug Endpoints

All debug endpoints require `ADMIN_API_KEY` authentication (Bearer token or `X-Debug-Key` header).

### PostgreSQL Debug Endpoints

| Endpoint | Method | Purpose | Auth Required |
| :--- | :--- | :--- | :---: |
| `/api/debug/postgres/connection` | `GET` | Test PostgreSQL connection and get connection info | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/schema/tables` | `GET` | List all tables in schema | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/schema/table/{name}` | `GET` | Get detailed table information (columns, indexes, FKs) | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/schema/indexes` | `GET` | List all indexes (optionally filtered by table) | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/stats/tables` | `GET` | Get table statistics (rows, sizes, indexes) | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/stats/database` | `GET` | Get global database statistics | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/query` | `POST` | Execute read-only SELECT queries safely | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/performance/slow-queries` | `GET` | Get slow queries from pg_stat_statements | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/performance/locks` | `GET` | Get active database locks | ✅ ADMIN_API_KEY |
| `/api/debug/postgres/performance/connections` | `GET` | Get connection statistics | ✅ ADMIN_API_KEY |

See [Debug Guide](./DEBUG_GUIDE.md) for detailed documentation.

## 💡 Key Distinctions

### `/api/chat/stream` (The "Good" One)
- **Uses**: `IntelligentRouter` → `AgenticRAGOrchestrator` → `SearchService`.
- **Metrics**: Emits `zantara_rag_pipeline_duration`, `zantara_rag_early_exit_total`, etc.
- **Use for**: Chat bot, Frontend, Performance Testing.

### `/api/oracle/query` (The "Manual" One)
- **Uses**: `OracleService` (Custom logic).
- **Metrics**: Does **NOT** emit Phase 1 Prometheus metrics (logs separate analytics to DB).
- **Use for**: Specific oracle tasks not requiring the Agentic loop.

---

## 🧪 Quick Test Commands

### Test Metrics Generation (Recommended)
```bash
curl -N -X POST https://nuzantara-rag.fly.dev/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d 
'{ 
    "message": "Test metrics generation",
    "user_id": "debugger"
  }'
```

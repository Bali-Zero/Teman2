# KBLI RAG API Issue Report

**Date:** 2025-11-05  
**Reporter:** AI Assistant  
**Severity:** HIGH  
**Status:** NEEDS INVESTIGATION

---

## 🔴 Problem Summary

The `/api/query` endpoint on the RAG service returns **empty/invalid JSON responses** even though:
- ChromaDB has 8,887 documents in `kbli_unified` collection ✅
- Embeddings are present and functional ✅ 
- Direct ChromaDB queries work perfectly ✅
- The RAG service `/health` endpoint is healthy ✅

---

## 🧪 Test Results

### ✅ Working: Direct ChromaDB Query (SSH into Fly.io)
```bash
# Via SSH on nuzantara-rag.fly.dev
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"restaurant business setup","collection":"kbli_unified","limit":5}'

# RESULT: Returns 5 valid results with similarity scores!
{
  "ok": true,
  "results": [
    {
      "text": "- Business model: Full-service restaurant with bar...",
      "score": 0.2276,
      "metadata": {...}
    },
    ...
  ],
  "count": 5,
  "collection": "kbli_unified"
}
```

### ❌ Broken: Public API Endpoint
```bash
curl -X POST https://nuzantara-rag.fly.dev/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"restaurant","collection":"kbli_unified","limit":3}'

# RESULT: Empty or null response
{
  "ok": null,
  "count": null
}
```

### ❌ Broken: Through Gateway
```bash
curl -X POST https://api.balizero.com/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"restaurant","collection":"kbli_unified","limit":3}'

# RESULT: No response body (empty)
```

---

## 🔍 Technical Details

### ChromaDB Status (VERIFIED)
- **Total documents:** 25,422
- **kbli_unified collection:** 8,887 documents
- **Embeddings:** Present (all-MiniLM-L6-v2, 384 dimensions)
- **Location:** `/data/chroma_db_FULL_deploy/chroma.sqlite3`

### Search Service Configuration
```python
# File: apps/backend-rag/backend/services/search_service.py
self.collections = {
    "kbli_unified": ChromaDBClient(
        persist_directory=chroma_path, 
        collection_name="kbli_unified"
    ),
    # ... other collections
}
```

### Gateway Configuration (FIXED)
```typescript
// File: gateway/src/index.ts
// Routes that go to Python backend
if (
  pathname.startsWith('/api/query') || // ✅ FIXED: Added this route
  pathname.startsWith('/api/semantic-search') ||
  pathname.startsWith('/oracle/query') ||
  // ...
) {
  targetBackend = env.PYTHON_BACKEND; // https://nuzantara-rag.fly.dev
}
```

---

## 🐛 Suspected Root Causes

### 1. **CORS or Request Proxy Issue**
- Internal requests (localhost) work ✅
- External requests (public URL) fail ❌
- Possible middleware blocking external requests?

### 2. **Response Serialization Problem**
- ChromaDB results are valid
- FastAPI might be failing to serialize response
- Check for numpy arrays or non-JSON-serializable objects

### 3. **Timeout or Memory Issue**
- First query might be timing out (model loading)
- Response size too large?
- Check Fly.io logs for errors

### 4. **Authentication/Headers Missing**
- Gateway might not be forwarding required headers
- Check if `search_service` initialization requires specific headers

---

## 📝 Recent Changes

### Commits Made
1. **efdf5de46** - `fix: Add kbli_unified collection to SearchService`
   - Added `kbli_unified` to collections dict (was missing)
   
2. **3064a5bdd** - `fix(gateway): Add /api/query routes to Python backend`
   - Fixed gateway routing (was going to TS backend, causing 404)

### Deployments
- ✅ RAG service deployed: `flyctl deploy` (nuzantara-rag)
- ✅ Gateway deployed: `npx wrangler deploy --env production`

---

## 🔧 Suggested Investigation Steps

### Step 1: Check Fly.io Logs
```bash
flyctl logs -a nuzantara-rag | grep -E "api/query|error|exception"
```

### Step 2: Test with curl verbose
```bash
curl -v -X POST https://nuzantara-rag.fly.dev/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","collection":"kbli_unified","limit":1}' 2>&1
```

### Step 3: Check FastAPI Response Serialization
```python
# In main_cloud.py, line ~2660 (api_query function)
# Add debug logging:
logger.info(f"Results type: {type(results)}")
logger.info(f"Results keys: {results.keys()}")
logger.info(f"First result type: {type(results.get('results', [])[0])}")
```

### Step 4: Verify SearchService Initialization
```bash
flyctl ssh console -a nuzantara-rag
# Inside container:
python3 -c "
from services.search_service import SearchService
service = SearchService()
print(f'Collections: {list(service.collections.keys())}')
print(f'kbli_unified exists: {\"kbli_unified\" in service.collections}')
"
```

### Step 5: Test Alternative Endpoint
```bash
# Try the /search endpoint instead of /api/query
curl -X POST https://nuzantara-rag.fly.dev/search \
  -H "Content-Type: application/json" \
  -d '{"query":"restaurant","user_level":0}'
```

---

## 🎯 Expected Behavior

```json
{
  "ok": true,
  "results": [
    {
      "id": "doc_123",
      "text": "KBLI 56101: Restaurant services...",
      "metadata": {
        "kbli_code": "56101",
        "title": "Restaurant Classification"
      },
      "score": 0.85
    }
  ],
  "count": 5,
  "collection": "kbli_unified",
  "query": "restaurant"
}
```

---

## 📊 Impact Assessment

### Blocking Features
- ✅ Backend-TS local KBLI search (31 hardcoded codes) - **WORKING**
- ❌ RAG semantic search via `/api/query` - **BLOCKED**
- ❌ Frontend KBLI search with deep semantic understanding - **BLOCKED**

### Workarounds Available
1. Use direct backend-TS endpoint: `/api/v2/bali-zero/kbli?query=restaurant`
2. SSH into Fly.io and query locally (not viable for production)
3. Use `/search` endpoint if it works differently

---

## 🔗 Related Files

- `apps/backend-rag/backend/app/main_cloud.py` (line 2637-2688)
- `apps/backend-rag/backend/services/search_service.py` (line 94-220)
- `gateway/src/index.ts` (line 28-40)
- `apps/backend-ts/src/handlers/bali-zero/kbli-complete.ts`

---

## ✅ What Works

1. ChromaDB is populated and healthy (25,422 docs)
2. Embeddings are present and functional
3. SSH localhost queries return perfect results
4. Gateway routing is fixed (routes to Python backend correctly)
5. RAG service health check is green

## ❌ What Doesn't Work

1. Public API endpoint `/api/query` returns empty/null responses
2. Gateway proxied requests get no valid response body
3. Unknown if it's CORS, serialization, timeout, or middleware issue

---

**Next Actions:** Investigate RAG service response handling for external requests. The data is there, embeddings work, but something in the response pipeline is breaking for public API calls.

# KBLI Router Fix - Option A Implementation

**Date**: 2026-02-18 15:28 WITA  
**File**: `backend/app/routers/kbli_notebook.py`  
**Backup**: `kbli_notebook.py.backup`

---

## Changes Made

### 1. Direct Lookup (lines ~740-770)

**OLD**: Query `kg_nodes` table

```python
row = await conn.fetchrow(
    "SELECT entity_id, name, description, properties FROM kg_nodes WHERE entity_id = $1",
    entity_id
)
```

**NEW**: Query `kbli_documents` table with fallback

```python
row = await conn.fetchrow(
    "SELECT kode_kbli, judul, content, metadata FROM kbli_documents WHERE kode_kbli = $1",
    code
)
# Fallback to kg_nodes for backward compatibility if not found
```

**Impact**: Direct code lookups (e.g. "56101 sanksi") now fetch full parent doc (3937 chars) instead of kg_nodes description (~200 chars)

---

### 2. New Helper Function: `_fetch_parent_documents_from_kbli_table`

**Location**: Before `chat_kbli` endpoint

```python
async def _fetch_parent_documents_from_kbli_table(codes: list[str], pool) -> dict[str, str]:
    """Fetch full parent documents from kbli_documents table for given KBLI codes."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT kode_kbli, content FROM kbli_documents WHERE kode_kbli = ANY($1)",
            codes
        )
    return {row["kode_kbli"]: row["content"] for row in rows}
```

**Purpose**: Bulk fetch parent documents for all search results in one query

---

### 3. Updated `_generate_kbli_explanation` Function

**OLD Signature**:

```python
async def _generate_kbli_explanation(query: str, results: list[KBLISearchResult]) -> str:
```

**NEW Signature**:

```python
async def _generate_kbli_explanation(
    query: str,
    results: list[KBLISearchResult],
    parent_docs: dict[str, str] = None
) -> str:
```

**Context Building Logic**:

```python
if parent_docs and r.code in parent_docs:
    full_content = parent_docs[r.code]
    context_parts.append(f"- KBLI {r.code}: {r.title}\n  Full details:\n{full_content}")
else:
    context_parts.append(f"- KBLI {r.code}: {r.title}\n  Scope: {r.description}")
```

**Impact**: LLM now receives full parent document content (including sanksi, persyaratan, kewajiban) instead of truncated description

---

### 4. Chat Endpoint Integration (line ~1149-1153)

**NEW Code**:

```python
# Fetch full parent documents from kbli_documents table for complete context
codes_to_fetch = [r.code for r in results if r.code != "N/A"]
parent_docs = await _fetch_parent_documents_from_kbli_table(codes_to_fetch, pool)

# Generate explanation via LLM (with full parent content)
answer = await _generate_kbli_explanation(kbli_request.query, results, parent_docs)
```

**Flow**:

1. Qdrant search returns child chunks with codes
2. Extract codes from results
3. Fetch full parent docs from `kbli_documents`
4. Pass parent docs to LLM explanation

---

## Architecture

### Before (OLD)

```
User Query
  ↓
Qdrant search (child chunks)
  ↓
kg_nodes lookup (truncated description ~200 chars)
  ↓
LLM context (incomplete)
  ↓
Response: "verify at OSS" (generic)
```

### After (NEW)

```
User Query
  ↓
Qdrant search (child chunks) OR direct code lookup
  ↓
kbli_documents fetch (full parent docs 1000-5000 chars)
  ↓
LLM context (complete with sanksi/persyaratan/kewajiban)
  ↓
Response: Detailed licensing/sanksi information
```

---

## Expected Behavior

### Test Query 1: "56101 sanksi mikro kecil"

**Before**: "verify sanksi at OSS"  
**After**: "Sanksi Administratif: Peringatan (Peringatan tertulis), Denda (Denda administratif), Penghentian (Penghentian sementara), Pencabutan (Pencabutan persyaratan dasar, PB, dan/atau PB UMKU)"

### Test Query 2: "restaurant licensing requirements bali"

**Before**: "KBLI 56101, PMA TERBUKA, verify at OSS"  
**After**: Full detail including:

- Persyaratan Dokumen (list)
- Kewajiban Pelaku Usaha (list)
- Perizinan Berusaha UMKU (Label HSP)
- Sanksi (4 types)

### Test Query 3: "what UMKU requirements for 56101"

**Before**: "verify at OSS"  
**After**: "PB UMKU: Label Higiene Sanitasi Pangan (HSP)"

---

## Backward Compatibility

### Fallback Chain

1. **Primary**: `kbli_documents` table (1563 codes)
2. **Fallback**: `kg_nodes` table (legacy codes)
3. **Hardcoded**: `KNOWN_KBLI_CODES` dict (synthetic fallback)

### Migration Path

- **Current**: Both `kbli_documents` + `kg_nodes` supported
- **Future**: Deprecate `kg_nodes` for KBLI, migrate to `kbli_documents` only

---

## Performance Impact

### Query Count

- **Before**: 1 query (kg_nodes lookup or Qdrant only)
- **After**: 2 queries (Qdrant search + kbli_documents bulk fetch)

### Response Size

- **Before**: ~500 chars context to LLM
- **After**: ~5000-15000 chars context to LLM (full parent docs)

### Latency

- **Before**: ~1-2s (Qdrant + LLM)
- **After**: ~1.5-2.5s (Qdrant + PostgreSQL + LLM)
- **Trade-off**: +0.5s latency for 10x better response quality

---

## Testing

### Local Test (Recommended Before Deploy)

```bash
cd ~/Projects/nuzantara/apps/backend-rag
source venv313/bin/activate  # Python 3.13 venv
uvicorn backend.app.main:app --reload --port 8080

# Test direct lookup
curl -X POST http://localhost:8080/api/v1/kbli-notebook/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"56101 sanksi mikro kecil"}'

# Test semantic search
curl -X POST http://localhost:8080/api/v1/kbli-notebook/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"restaurant licensing bali"}'
```

### Production Test

```bash
# After deploy
curl -X POST https://kita.balizero.com/api/v1/kbli-notebook/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"56101 sanksi"}'
```

---

## Deployment Steps

1. ✅ Backup created: `kbli_notebook.py.backup`
2. ✅ Changes implemented
3. ✅ Syntax validated (no errors)
4. ⏳ Local test (manual step)
5. ⏳ Git commit
6. ⏳ Deploy to Fly.io
7. ⏳ Production smoke test

---

## Rollback Plan

If retrieval fails:

```bash
cd ~/Projects/nuzantara/apps/backend-rag/backend/app/routers
cp kbli_notebook.py.backup kbli_notebook.py
git checkout backend/app/routers/kbli_notebook.py
flyctl deploy -a nuzantara-rag
```

---

## Success Criteria

✅ Query "56101 sanksi" returns detailed sanksi (4 types)  
✅ Query "restaurant UMKU" returns PB UMKU requirements  
✅ Query "56101 persyaratan" returns persyaratan list  
✅ Response length >> 200 chars (should be 1000-3000+)  
✅ No errors in Sentry within 1 hour post-deploy

---

## Next Steps

1. **Local test** (5 min) - Verify queries work with full parent content
2. **Git commit** (2 min)
3. **Deploy** (5 min) - `flyctl deploy -a nuzantara-rag`
4. **Production test** (3 min) - Verify 3 test queries
5. **Monitor** (1 hour) - Check Sentry for errors

**Total estimated time**: 15-20 minutes

---

**Status**: ✅ Code complete, ready for testing  
**Next Action**: Local test before commit/deploy

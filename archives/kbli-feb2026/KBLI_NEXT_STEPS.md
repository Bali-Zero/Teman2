# KBLI Production - Next Steps

**Current Status**: ✅ Data deployed, ⚠️ Retrieval not working

---

## Problem

PostgreSQL `kbli_documents` table populated with 1563 complete parent documents (3937 chars for 56101), BUT:

**Router `kbli_notebook.py` uses:**

- `kg_nodes` table for direct KBLI code lookup
- Qdrant semantic search for general queries
- **NOT using `kbli_documents` table at all**

**Result**: Chat returns generic "verify at OSS" instead of retrieving detailed licensing/sanksi info from `kbli_documents`.

---

## Root Cause Analysis

### Current Architecture

```
User Query
  ↓
kbli_notebook.py router
  ↓
├─ Direct code lookup → kg_nodes table (5-digit code regex)
└─ Semantic search → Qdrant kbli_2025_final collection
  ↓
Returns generic response (no detailed licensing/sanksi)
```

### Expected Architecture

```
User Query
  ↓
kbli_notebook.py router
  ↓
├─ Direct code lookup → kbli_documents table (NEW)
└─ Semantic search → Qdrant (child chunks)
  ↓
  Retrieve parent doc_id
  ↓
  Fetch full content from kbli_documents (NEW)
  ↓
Returns detailed response with licensing/sanksi
```

---

## Solution Options

### Option A: Update Router to Use kbli_documents (RECOMMENDED)

**Effort**: 1-2 hours  
**Risk**: Low (backward compatible)

**Changes needed:**

1. **Direct lookup** (`lines ~160-185`):

   ```python
   # OLD
   row = await conn.fetchrow(
       "SELECT entity_id, name, description, properties FROM kg_nodes WHERE entity_id = $1",
       entity_id
   )

   # NEW
   row = await conn.fetchrow(
       "SELECT kode_kbli, judul, content, metadata FROM kbli_documents WHERE kode_kbli = $1",
       code
   )
   ```

2. **Semantic search parent retrieval** (`lines ~220-250`):

   ```python
   # After Qdrant search returns doc_ids
   parent_docs = await conn.fetch("""
       SELECT kode_kbli, content
       FROM kbli_documents
       WHERE kode_kbli = ANY($1)
   """, extracted_codes_from_qdrant_metadata)
   ```

3. **LLM context augmentation** (`lines ~280-320`):
   ```python
   # Include full parent content in RAG context
   context = "\n\n".join([doc['content'] for doc in parent_docs])
   ```

**Benefits**:

- Uses complete 3937-char documents
- Includes all sanksi/persyaratan/kewajiban details
- No need to rebuild Qdrant (child chunks still used for search)

---

### Option B: Update Parent Document Retriever Service

**Effort**: 2-3 hours  
**Risk**: Medium (may affect other RAG endpoints)

**Changes needed**:

1. Modify `backend/services/rag/parent_document_retriever.py`
2. Add `kbli_documents` as alternative parent source
3. Update all RAG chains to use new retriever

**Benefits**:

- Centralizes parent document logic
- Affects all endpoints uniformly

**Drawbacks**:

- May break other document types (legal docs, news)
- Requires testing across multiple endpoints

---

### Option C: Create New KBLI-Specific Service

**Effort**: 3-4 hours  
**Risk**: Low (isolated changes)

**Create**: `backend/services/kbli/kbli_retriever.py`

```python
class KBLIRetriever:
    async def get_by_code(self, code: str) -> KBLIDocument:
        """Direct lookup from kbli_documents."""

    async def semantic_search(self, query: str, top_k: int = 5) -> List[KBLIDocument]:
        """Qdrant search → fetch parents from kbli_documents."""
```

**Update router** to use new service instead of raw SQL.

**Benefits**:

- Clean separation of concerns
- Easy to test and maintain
- Doesn't touch existing RAG infrastructure

---

## Recommended Approach

**OPTION A** (Quick Fix) → validate → **OPTION C** (Long-term refactor)

### Phase 1: Quick Fix (1-2 hours)

1. Update `kbli_notebook.py` direct lookup to use `kbli_documents`
2. Add parent retrieval after Qdrant search
3. Test with 56101 sanksi query
4. Deploy if working

### Phase 2: Proper Refactor (when time permits)

1. Extract KBLI logic into dedicated service
2. Add comprehensive tests
3. Deprecate kg_nodes for KBLI (migrate to kbli_documents only)

---

## Test Plan

### Test Queries

```bash
# 1. Direct code lookup
curl -X POST https://kita.balizero.com/api/v1/kbli-notebook/chat \
  -d '{"query":"56101 sanksi mikro kecil"}'
# Expected: Detailed sanksi (Peringatan, Denda, Penghentian, Pencabutan)

# 2. Semantic search
curl -X POST https://kita.balizero.com/api/v1/kbli-notebook/chat \
  -d '{"query":"restaurant licensing requirements bali"}'
# Expected: KBLI 56101 with persyaratan + kewajiban details

# 3. Multiple codes
curl -X POST https://kita.balizero.com/api/v1/kbli-notebook/chat \
  -d '{"query":"compare hotel 55101 and restaurant 56101 licensing"}'
# Expected: Both codes with full per_skala comparison
```

### Validation Criteria

✅ Response includes sanksi details (4 types)  
✅ Response includes persyaratan (if applicable)  
✅ Response includes kewajiban (if applicable)  
✅ Response includes pb_umku (if applicable)  
✅ Content length >> 200 chars (should be ~1000-3000 depending on query)

---

## Files to Modify

### Primary

- `backend/app/routers/kbli_notebook.py` (lines 160-320)

### Supporting (Phase 2)

- `backend/services/kbli/kbli_retriever.py` (NEW)
- `backend/services/kbli/__init__.py` (NEW)
- Tests: `tests/services/kbli/test_kbli_retriever.py` (NEW)

---

## Migration Notes

### Deprecation Path

1. **Current**: kg_nodes for KBLI entities
2. **Transition**: Support both kg_nodes + kbli_documents (fallback)
3. **Future**: kbli_documents only, kg_nodes for non-KBLI entities

### Data Consistency Check

```sql
-- Verify all codes in kg_nodes exist in kbli_documents
SELECT entity_id
FROM kg_nodes
WHERE entity_id LIKE 'kbli:%'
  AND SUBSTRING(entity_id FROM 6) NOT IN (
    SELECT kode_kbli FROM kbli_documents
  );
-- Should return 0 rows
```

---

## Timeline Estimate

| Task                        | Duration | Who         |
| --------------------------- | -------- | ----------- |
| Router update (Option A)    | 1-2h     | Backend dev |
| Testing (3 test queries)    | 30 min   | QA/dev      |
| Deploy + monitor            | 30 min   | DevOps      |
| **Total Phase 1**           | **2-3h** |             |
| Service refactor (Option C) | 2-3h     | Backend dev |
| Integration tests           | 1h       | QA/dev      |
| **Total Phase 2**           | **3-4h** |             |

---

## Deployment Checklist

- [ ] Update `kbli_notebook.py` to use `kbli_documents`
- [ ] Test locally against production database
- [ ] Run test queries (3 scenarios)
- [ ] Git commit + push
- [ ] Fly.io deploy (`flyctl deploy -a nuzantara-rag`)
- [ ] Health check (verify 1563 docs in kbli_documents)
- [ ] Re-test sanksi query
- [ ] Monitor Sentry for errors (24h)

---

## Rollback Plan

If retrieval fails after deploy:

1. Revert router changes (git revert)
2. Redeploy previous version
3. Keep kbli_documents table (no data loss)
4. Debug locally before retry

---

**Status**: Ready for implementation  
**Blocker**: None (data fully deployed)  
**Next**: Assign to backend dev for Option A implementation

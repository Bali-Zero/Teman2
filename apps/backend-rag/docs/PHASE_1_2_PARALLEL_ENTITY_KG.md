# Phase 1.2: Parallel Entity Extraction + KG Retrieval

## Overview

This document describes the Phase 1.2 optimization: parallelizing Entity Extraction and KG Retrieval operations in `orchestrator_core.py`.

## Implementation Summary

**File Modified:** `backend/services/rag/agentic/orchestrator_core.py`

**Method:** `extract_entities_and_kg_context()`

**Changes:**

- Added `asyncio` import
- Refactored to use `asyncio.gather()` for parallel execution
- Added timing metrics for Entity and KG operations
- Graceful error handling with `return_exceptions=True`

**Expected Improvement:**

- **Baseline (Sequential):** ~150-250ms (Entity: 50-100ms + KG: 100-150ms)
- **Optimized (Parallel):** ~100-150ms (max of Entity and KG)
- **Speedup:** 50-100ms reduction (~30-40% faster)

## How It Works

### Before (Sequential)

```
Start → Entity Extraction (100ms) → Wait → KG Retrieval (150ms) → Return (250ms total)
```

### After (Parallel)

```
Start → Entity Extraction (100ms) ┐
      → KG Retrieval (150ms)      ┘ → Wait for both → Return (150ms total)
```

## Code Changes

### Key Implementation Details

1. **Parallel Tasks:**
   - `_extract_entities_task()` - Entity extraction (heuristic-based, fast)
   - `_fetch_kg_context_task()` - KG graph retrieval (DB queries, slower)

2. **Error Handling:**
   - Uses `return_exceptions=True` to prevent cascading failures
   - If Entity extraction fails → returns empty dict
   - If KG retrieval fails → returns None (system continues without KG context)

3. **Timing Metrics:**
   - Logs individual timings for Entity and KG
   - Calculates speedup vs sequential execution
   - Pattern: `⚡ [Orchestrator] PARALLEL Entity+KG completed in X.XXs`

## Verification Steps

### 1. Check Logs

```bash
flyctl logs -a nuzantara-rag | grep -E "PARALLEL Entity|Entity extraction|KG retrieval"
```

**Expected Pattern:**

```
⏱️  [Orchestrator] Entity extraction: 0.085s
⏱️  [Orchestrator] KG retrieval: 0.142s
⚡ [Orchestrator] PARALLEL Entity+KG completed in 0.145s (Entity: 0.085s, KG: 0.142s, speedup: ~0.082s vs sequential ~0.227s)
```

### 2. Verify No Regressions

- Entity extraction still works correctly
- KG context still added to system prompt when available
- Error handling graceful (one failure doesn't break the other)

### 3. Measure Combined Speedup

Phase 1.1 + Phase 1.2 combined improvement:

- **Context Loading:** 200-400ms speedup (Phase 1.1)
- **Entity + KG:** 50-100ms speedup (Phase 1.2)
- **Total:** ~250-500ms reduction in pre-ReAct latency

## Dependencies

- Requires Phase 1.1 to be deployed and verified first
- Entity extraction is fast (heuristic-based), so speedup may be modest
- KG retrieval speedup depends on DB latency

## Rollback Procedure

If issues occur:

```python
# Quick fix: Restore sequential execution
# In extract_entities_and_kg_context():
extracted_entities = await self.entity_extractor.extract_entities(query)
# ... build system_context_for_prompt ...
if self.kg_retrieval:
    kg_context = await self.kg_retrieval.get_context_for_query(query, max_depth=1)
```

Or restore from git:

```bash
git checkout HEAD~1 -- apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py
```

## Success Criteria

✅ **Performance:**

- Average speedup > 50ms
- No increase in error rate
- Entity extraction still fast (<100ms)

✅ **Reliability:**

- Graceful degradation when KG fails
- Entity extraction continues even if KG unavailable

✅ **Observability:**

- Timing metrics logged correctly
- Speedup calculation accurate

## Next Steps

After Phase 1.2 verification:

- **Phase 1.3:** Parallel Tool Execution in Reasoning Engine
- **Phase 3:** Speculative Follow-up Generation

## References

- **Phase 1.1:** `docs/PHASE_1_1_PARALLEL_CONTEXT_LOADING.md`
- **Code:** `backend/services/rag/agentic/orchestrator_core.py`
- **Analysis:** Original optimization analysis document

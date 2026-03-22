# KG LangGraph Browser - Production Test Report

**Date:** 2026-02-09
**Tester:** Zantara (QA Automation)
**Version:** v1899+ (deployed with hotfixes v1910)
**Feature Flag:** `ENABLE_KG_LANGGRAPH`

---

## Executive Summary

**Decision: ❌ KEEP DISABLED in production**

The KG LangGraph workflow generator does NOT produce visible improvements for multi-domain queries. The `🔀 SUGGESTED WORKFLOW` section never appeared in any response. The feature adds overhead without measurable benefit in its current state.

---

## Test Environment

- **Backend:** nuzantara-rag on Fly.io (Singapore, shared-cpu-2x, 2GB RAM)
- **API Endpoint:** `POST /api/agentic-rag/query`
- **Auth:** JWT token (zero@balizero.com)
- **Method:** Direct API calls (browser login was blocked during crash recovery)

---

## Pre-Test Issues Found & Fixed

During testing, we discovered **3 pre-existing production crashes** unrelated to KG LangGraph:

| File                                            | Error                                                      | Fix                                                     |
| ----------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------- |
| `backend/app/core/config.py`                    | `IndentationError` at line 594 (duplicate WhatsApp fields) | Removed duplicate field definitions                     |
| `backend/services/misc/autonomous_scheduler.py` | `SyntaxError` at line 545 (missing except block)           | Removed stale log line, added conversation_cleanup task |
| `backend/app/routers/whatsapp_conversations.py` | `NameError: get_current_user not defined`                  | Added missing import                                    |

**Commits:**

- `0b5136b25` - fix: resolve SyntaxError in config.py and autonomous_scheduler.py
- `2ad8c0f28` - fix: add missing get_current_user import in whatsapp_conversations.py

---

## Test Results

### Query Results Comparison

| #   | Query (abbreviated)                                   | LangGraph OFF                       | LangGraph ON                        |
| --- | ----------------------------------------------------- | ----------------------------------- | ----------------------------------- |
|     |                                                       | **Time / Len / Domains / Workflow** | **Time / Len / Domains / Workflow** |
| Q1  | Aprire ristorante straniero (PT PMA, KBLI, visto...)  | 13.9s / 301ch / 1 dom / ❌          | 12.1s / 301ch / 1 dom / ❌          |
| Q2  | Codice KBLI ristorante, proprietà straniera, capitale | 17.0s / 440ch / 4 dom / ❌          | 12.5s / 500 ERROR / 0 dom / ❌      |
| Q3  | Comprare villa Bali, visto, tipo proprietà            | 8.6s / 1529ch / 4 dom / ❌          | 6.5s / 982ch / 3 dom / ❌           |
| Q4  | PT PMA tasse, assunzione camerieri                    | 7.1s / 500 ERROR / 0 dom / ❌       | 13.8s / 546ch / 3 dom / ❌          |
| Q5  | Visto dipendente moglie, costi                        | 14.0s / 500 ERROR / 0 dom / ❌      | 13.1s / 500 ERROR / 0 dom / ❌      |

### Key Metrics

| Metric                             | LangGraph OFF | LangGraph ON | Delta            |
| ---------------------------------- | ------------- | ------------ | ---------------- |
| **Avg Response Time**              | 12.1s         | 11.6s        | -4% (negligible) |
| **Successful Responses**           | 3/5 (60%)     | 3/5 (60%)    | 0%               |
| **🔀 SUGGESTED WORKFLOW appeared** | 0/5 (0%)      | 0/5 (0%)     | 0%               |
| **Avg Answer Length (success)**    | 757 chars     | 610 chars    | -19%             |
| **Avg Domains Covered (success)**  | 3.0           | 2.3          | -23%             |
| **Sources Cited**                  | 1.3 avg       | 1.0 avg      | -23%             |
| **Under 5s Responses**             | 0/5 (0%)      | 0/5 (0%)     | 0%               |
| **500 Errors**                     | 2/5           | 2/5          | same             |

---

## Detailed Analysis

### 1. Workflow Section Never Appears

The `🔀 SUGGESTED WORKFLOW` section (defined in `orchestrator_core.py:326`) was **never generated** in any response. This means either:

- The KG LangGraph orchestrator is not being invoked despite the flag being enabled
- The orchestrator runs but returns `None` for the workflow field
- The workflow result is not being integrated into the final answer text

**Root cause likely:** The `_fetch_langgraph_workflow_task()` in `orchestrator_core.py` runs as a parallel task but its result may not be merged into the answer when the main RAG pipeline completes first.

### 2. Response Quality is Equivalent or Worse

- With LangGraph ON, Q2 (KBLI query) returned a 500 error instead of a valid answer
- Q4 improved (500→valid answer), but this may be due to backend warm-up, not LangGraph
- Answer length and domain coverage were slightly worse with LangGraph ON

### 3. Performance is Not Improved

- Average response time is nearly identical (~12s both modes)
- No query completed under 5 seconds in either mode
- The 5-second target is unrealistic for complex multi-domain queries

### 4. Pre-Existing Backend Instability

- 2 out of 5 queries return 500 errors in both modes
- This indicates underlying RAG pipeline issues unrelated to KG LangGraph
- The backend was crash-looping due to syntax errors before this test

---

## Recommendations

### Immediate (P0)

1. **Keep `ENABLE_KG_LANGGRAPH=false`** — No measurable benefit, potential instability
2. **Investigate 500 errors** on Q4/Q5 type queries (tax + hiring, dependent visa) — these are core business queries failing

### Short-term (P1)

3. **Fix workflow integration** — The `synthesize_workflow_node` output is not reaching the response. Debug the parallel task merging in `orchestrator_core.py`
4. **Add integration tests** — The KG LangGraph code was deployed (v1899) without any real query testing. Add pytest tests that verify workflow output for known queries

### Medium-term (P2)

5. **Optimize response time** — 12s average is too slow. Consider:
   - Pre-warming LLM connections
   - Caching KG traversal results
   - Using Flash model for initial routing
6. **Re-test after fixes** — Once workflow integration is fixed, re-run this A/B test

---

## Test Artifacts

- Baseline (OFF) results: `/tmp/kg_test_OFF/q{1-5}.json`
- LangGraph (ON) results: `/tmp/kg_test_ON/q{1-5}.json`
- Test script: `scripts/test_kg_langgraph.sh`

---

## Production Status

✅ Production restored and healthy (LangGraph OFF)
✅ Feature flag `ENABLE_KG_LANGGRAPH` unset
✅ 3 syntax/import bugs fixed and deployed

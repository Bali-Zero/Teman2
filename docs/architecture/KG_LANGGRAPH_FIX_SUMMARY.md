# KG LangGraph Integration Fix Summary

## Problem Identified

KG LangGraph was enabled (`ENABLE_KG_LANGGRAPH=true`) and the health endpoint showed `graph_loaded: true`, but:

- Responses didn't include workflow synthesis in structured format
- No reasoning chains visible in API responses
- Entity resolution from KG not evident in response structure
- Subgraphs (Company, Visa, Property, Tax) weren't being exposed in responses

## Root Cause

The KG LangGraph orchestrator was being called correctly, but the workflow data was:

1. Only being appended as text to the answer string (not in structured response)
2. Not included in the `CoreResult` schema
3. Not exposed in the API response model

## Fixes Applied

### 1. Updated `backend/services/rag/agentic/schema.py`

- Added `workflow` field to `CoreResult` schema
- Added `reasoning` field to `CoreResult` schema

```python
# KG LangGraph outputs (Phase 3)
workflow: dict[str, Any] | None = None  # Synthesized workflow from KG LangGraph
reasoning: str | None = None  # Reasoning chain from KG exploration
```

### 2. Updated `backend/services/rag/agentic/orchestrator_response.py`

- Modified `build_core_result()` to accept `workflow` and `reasoning` parameters
- Pass these fields to `CoreResult` constructor

### 3. Updated `backend/services/rag/agentic/orchestrator_core.py`

- Enhanced logging to clearly indicate when KG LangGraph is enabled/disabled
- Extract reasoning from langgraph_result
- Pass workflow and reasoning to response builder

### 4. Updated `backend/services/rag/agentic/orchestrator.py`

- Added initialization-time logging to confirm KG LangGraph status
- Clear warning messages when disabled due to missing feature flag or db_pool

### 5. Updated `backend/app/routers/agentic_rag.py`

- Added `workflow`, `reasoning`, and `detected_entities` to `AgenticQueryResponse`
- Updated response construction to include KG LangGraph outputs

### 6. Updated `backend/app/routers/health.py`

- Added KG LangGraph status check to detailed health endpoint
- Shows whether enabled, initialized, and any errors

### 7. Updated `backend/services/rag/agentic/orchestrator_streaming_core.py`

- Added metadata event with structured workflow for streaming responses
- Enables frontend to use workflow data programmatically in streaming mode

## Expected API Response Now

When `ENABLE_KG_LANGGRAPH=true`, responses will include:

```json
{
    "answer": "...workflow appended as text...",
    "sources": [...],
    "context_length": 5,
    "execution_time": 2.34,
    "route_used": "agentic-rag",
    "tools_called": 3,
    "total_steps": 3,
    "debug_info": {...},
    "workflow": {
        "type": "company_setup",
        "name": "PT PMA Setup Workflow",
        "steps": [
            {"step": 1, "action": "Choose business classification", "details": {...}},
            {"step": 2, "action": "Prepare required documents", "details": {...}}
        ],
        "source": "company_subgraph",
        "confidence": 0.95,
        "estimated_time": "4-6 weeks"
    },
    "reasoning": "The query involves company formation which matches the Company subgraph...",
    "detected_entities": [
        {"type": "business_type", "value": "PT PMA"},
        {"type": "location", "value": "Bali"}
    ]
}
```

## How to Verify

### 1. Check Health Endpoint

```bash
curl https://your-api-url/health/detailed
```

Look for:

```json
"kg_langgraph": {
    "status": "healthy",
    "details": {
        "enabled": true,
        "initialized": true
    }
}
```

### 2. Test Query with Logging

Make a query and check logs for:

```
✅ KG LangGraph Orchestrator initialized (Phase 3 - ENABLE_KG_LANGGRAPH=true)
🔀 [KG LangGraph] ENABLED: Starting workflow synthesis...
🔀 [KG LangGraph] Synthesized workflow: company_setup (5 steps, source: company_subgraph)
⏱️  [Orchestrator] KG LangGraph: 0.823s
⚡ [Orchestrator] PARALLEL Entity+KG+LangGraph completed in 1.234s
🔗 [KG LangGraph] Workflow included in response: company_setup
```

### 3. Check API Response (Non-Streaming)

Make a query to `/api/agentic-rag/query` and verify response contains:

- `workflow` field with structured workflow data
- `reasoning` field with explanation
- `detected_entities` field with extracted entities

### 4. Check Streaming Response

Make a streaming query to `/api/agentic-rag/stream` and verify:

- Metadata event contains `workflow` field
- Metadata event contains `detected_entities` field
- Workflow is streamed as tokens after the main answer

### 4. Test Subgraph Routing

Try queries that should trigger specific subgraphs:

- "How to open PT PMA in Bali?" → Should route to `company_subgraph`
- "What KITAS do I need?" → Should route to `visa_subgraph`
- "Buy villa in Bali" → Should route to `property_subgraph`
- "NPWP tax registration" → Should route to `tax_subgraph`

Check logs for:

```
🏢 [Router] Company-related query, routing to CompanySubgraph
🛂 [Router] Visa-related query, routing to VisaSubgraph
🏠 [Router] Property-related query, routing to PropertySubgraph
🧾 [Router] Tax-related query, routing to TaxSubgraph
```

## Files Modified

1. `backend/services/rag/agentic/schema.py` - Added workflow/reasoning fields
2. `backend/services/rag/agentic/orchestrator_response.py` - Pass workflow to result
3. `backend/services/rag/agentic/orchestrator_core.py` - Enhanced logging and workflow handling
4. `backend/services/rag/agentic/orchestrator.py` - Initialization logging
5. `backend/app/routers/agentic_rag.py` - API response includes workflow
6. `backend/app/routers/health.py` - Health check for KG LangGraph
7. `backend/services/rag/agentic/orchestrator_streaming_core.py` - Streaming workflow metadata

## Deployment Notes

- No database migrations required
- No environment variable changes required (uses existing `ENABLE_KG_LANGGRAPH`)
- Changes are backward compatible (new fields are optional)
- Restart the application to apply changes

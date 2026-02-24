# Migration from V5

## V5 → V6 Service Mapping

### Services that become graph nodes

| V5 Component | V6 Node |
|---|---|
| `entity_extractor.py` | `understand` |
| `orchestrator_routing.py` | `route` (conditional edges) |
| `kg_enhanced_retrieval.py` + SearchService | `retrieve` |
| `reasoning.py` (ReAct loop) | `reason` + `tools` |
| `orchestrator_response.py` | `synthesize` |
| `verification_service.py` | Grader nodes |
| `confidence.py` | `ConfidenceScores` model |
| `kg_subgraph_*.py` | Subgraph nodes |
| `llm_gateway.py` (cascade + circuit breaker) | `services/llm_gateway.py` |

### Services that remain standalone

| Service | Rationale |
|---|---|
| CRM (7 routers) | CRUD, not AI pipeline |
| Ingestion pipeline | Batch processing |
| Notifications | Multi-channel push |

### New in V6 (not in V5)

| Feature | Implementation |
|---|---|
| Semantic cache (2-layer) | `services/cache.py` — exact hash + Qdrant similarity |
| Conversation memory | `services/conversation_memory.py` — Redis session store |
| Hallucination LLM grading | `graders/hallucination_grader.py` — borderline LLM verification |
| Per-node observability | `observability.py` — NodeTimer, GraphMetrics, structlog JSON |
| Grader correction cycles | LangGraph cyclic edges with max 2 retries |
| Fail-fast routing | `FAIL` grade → skip to `synthesize_fail_fast` |

### Preserved patterns

| Pattern | V5 | V6 |
|---|---|---|
| LLM cascade + circuit breaker | `llm_gateway.py` | `services/llm_gateway.py` |
| Token tracking | `llm_gateway.py` | `TokenUsage` model |
| 6-factor confidence | `confidence.py` | `ConfidenceScores` model |
| Multi-channel adapters | `channels/` | `channels/` |
| Pydantic BaseSettings | `config.py` | `config.py` |

## Migration Phases

| Phase | Duration | Traffic | Description |
|---|---|---|---|
| Shadow | Week 1-4 | 0% | V6 runs alongside V5, responses compared via RAGAS |
| A/B Test | Week 5-8 | 10% → 50% | Gradual traffic shift |
| Cutover | Week 9-12 | 100% | V6 primary, V5 fallback |

## Data Migration

- **Qdrant:** Shared read-only (same collections, V6 reads only) + new `v6_cache_vectors` collection
- **PostgreSQL:** V6 gets own `v6` schema, V5 KG tables read-only
- **Redis:** Key prefix `v6:` (separate from V5's namespace)
  - `v6:cache:*` — semantic cache
  - `v6:session:*` — conversation memory
  - `v6:stream:*` — SSE pub/sub

## Repo Layout (additive — V5 untouched)

```
apps/
├── backend-rag/     ← V5, production (untouched)
├── mouth/           ← V5 frontend (untouched)
├── graph-engine/    ← V6 NEW
│   ├── src/nuzantara_graph/
│   │   ├── api/         — routes, middleware
│   │   ├── channels/    — web, telegram, whatsapp
│   │   ├── graders/     — 5 grader nodes
│   │   ├── graph/       — builder, router, constants
│   │   ├── nodes/       — 6 core nodes
│   │   ├── services/    — llm, vector, kg, cache, memory
│   │   ├── subgraphs/   — company, visa, property, tax
│   │   └── observability.py
│   └── docs/            — this documentation
├── web/             ← V6 frontend NEW
│   └── src/
│       ├── app/         — Next.js App Router
│       ├── components/  — Atomic Design
│       ├── hooks/       — useGraph, useChatPage, useChatMessages
│       └── lib/api/     — GraphClient with session support
└── ...
packages/
├── shared-schemas/  ← V6 Pydantic source of truth NEW
│   └── src/nuzantara_schemas/
│       ├── state.py     — GraphState (with session_id, conversation_history)
│       ├── grading.py   — GradeResult, GradeDecision
│       ├── events.py    — SSE streaming schemas
│       └── domain/      — company, visa, property, tax, kbli
└── ...
```

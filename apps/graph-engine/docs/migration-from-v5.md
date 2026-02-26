# Migration from V5

## Breaking Changes

Before migrating, be aware of these incompatible changes:

| Area            | V5                               | V6                                                  | Impact                                                             |
| --------------- | -------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------ |
| State model     | `TypedDict` (`state["key"]`)     | Pydantic `GraphState` (`state.key`)                 | All node code must use attribute access                            |
| Query endpoint  | `POST /api/agentic-rag/query`    | `POST /api/query`                                   | Frontend API client must update URL                                |
| Stream endpoint | `POST /api/agentic-rag/stream`   | `POST /api/query/stream`                            | Different SSE event schema (`StreamNodeEvent`)                     |
| Frontend hook   | `useChatStreaming`               | `useGraph`                                          | Complete hook replacement with `session_id` support                |
| Routing         | LLM-based (probabilistic)        | `IntentType` → `RouteDecision` enum (deterministic) | No `route` node — routing is via conditional edges on `understand` |
| Grading         | Single `verification_service.py` | 5 separate grader nodes with correction cycles      | Graders can trigger retry loops (max 2)                            |

## V5 → V6 Service Mapping

### Services that become graph nodes

| V5 Component                                 | V6 Equivalent                                                         |
| -------------------------------------------- | --------------------------------------------------------------------- |
| `entity_extractor.py`                        | `understand` node                                                     |
| `orchestrator_routing.py`                    | Conditional edges after `understand` (not a node)                     |
| `kg_enhanced_retrieval.py` + SearchService   | `retrieve` node                                                       |
| `reasoning.py` (ReAct loop)                  | `reason` + `tools` nodes                                              |
| `orchestrator_response.py`                   | `synthesize` node                                                     |
| `verification_service.py`                    | 5 grader nodes (retrieval, reasoning, answer, hallucination, pricing) |
| `confidence.py`                              | `ConfidenceScores` Pydantic model                                     |
| `kg_subgraph_*.py`                           | Subgraph nodes (company, visa, property, tax)                         |
| `llm_gateway.py` (cascade + circuit breaker) | `services/llm_gateway.py`                                             |

> **Note:** There is no `route` node in the LangGraph. Routing is implemented as
> `add_conditional_edges()` on the `understand` node, mapping `IntentType` enums
> to `RouteDecision` enums. This is purely deterministic — no LLM call.

### Services that remain standalone

| Service            | Rationale             | Location                        |
| ------------------ | --------------------- | ------------------------------- |
| CRM (7 routers)    | CRUD, not AI pipeline | `apps/backend-rag/` (unchanged) |
| Ingestion pipeline | Batch processing      | `apps/backend-rag/` (unchanged) |
| Notifications      | Multi-channel push    | `apps/backend-rag/` (unchanged) |

### New in V6 (not in V5)

| Feature                   | Implementation                                                  |
| ------------------------- | --------------------------------------------------------------- |
| Semantic cache (2-layer)  | `services/cache.py` — exact hash + Qdrant similarity            |
| Conversation memory       | `services/conversation_memory.py` — Redis session store         |
| Hallucination LLM grading | `graders/hallucination_grader.py` — borderline LLM verification |
| Per-node observability    | `observability.py` — NodeTimer, GraphMetrics, structlog JSON    |
| Grader correction cycles  | LangGraph cyclic edges with max 2 retries                       |
| Fail-fast routing         | `FAIL` grade → skip to `synthesize_fail_fast`                   |

### Preserved patterns

| Pattern                       | V5               | V6                        |
| ----------------------------- | ---------------- | ------------------------- |
| LLM cascade + circuit breaker | `llm_gateway.py` | `services/llm_gateway.py` |
| Token tracking                | `llm_gateway.py` | `TokenUsage` model        |
| 6-factor confidence           | `confidence.py`  | `ConfidenceScores` model  |
| Multi-channel adapters        | `channels/`      | `channels/`               |
| Pydantic BaseSettings         | `config.py`      | `config.py`               |

## Grading Thresholds

All graders use the `GradeDecision` enum:

| Decision | Score Range | Behavior                                             |
| -------- | ----------- | ---------------------------------------------------- |
| `PASS`   | ≥ 0.7       | Continue to next node                                |
| `RETRY`  | 0.2 – 0.7   | Loop back (if `correction_count < max_corrections`)  |
| `FAIL`   | < 0.2       | Fail-fast → `synthesize_fail_fast` (polite rephrase) |

Exhausted retries on `RETRY` → continues forward with degraded answer.

### Per-grader thresholds

| Grader        | PASS threshold | Special behavior                                 |
| ------------- | -------------- | ------------------------------------------------ |
| retrieval     | 0.7            | —                                                |
| reasoning     | 0.7            | —                                                |
| answer        | 0.7            | —                                                |
| hallucination | 0.8            | LLM verification for borderline scores (0.5–0.8) |
| pricing       | 0.9            | Strict regex validation against official data    |

> **Note:** `pricing` grader is defined but not yet wired into the graph edges.
> It will be activated when pricing queries are routed to a dedicated flow.

## Migration Phases

| Phase    | Duration  | Traffic   | Description                                        |
| -------- | --------- | --------- | -------------------------------------------------- |
| Shadow   | Week 1-4  | 0%        | V6 runs alongside V5, responses compared via RAGAS |
| A/B Test | Week 5-8  | 10% → 50% | Gradual traffic shift                              |
| Cutover  | Week 9-12 | 100%      | V6 primary, V5 fallback                            |

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
│   │   ├── nodes/       — 5 core nodes + 2 terminal (synthesize_direct, synthesize_fail_fast)
│   │   ├── services/    — llm, vector, kg, cache, memory, embeddings
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
```

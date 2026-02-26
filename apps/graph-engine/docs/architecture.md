# Nuzantara V6 Architecture

## Overview

Nuzantara V6 replaces the V5 procedural orchestration with a LangGraph-centric agentic platform.

### V5 Problems Solved

- **No self-correction:** V5's 12-step linear flow can't recover from failures
- **No state validation:** TypedDict state allows invalid data between nodes
- **Probabilistic routing:** V5 routes based on LLM output, not deterministic enums
- **No streaming granularity:** V5 streams answer text, not node-level progress

### V6 Core Principles

1. **Pydantic GraphState** — validated on every mutation
2. **Cyclic correction** — grader nodes trigger retry loops (max 2)
3. **Deterministic routing** — `IntentType` enum → `RouteDecision` enum
4. **CoT as first-class state** — `reasoning_steps` list
5. **Node-level streaming** — SSE events per graph node

## System Diagram

```
                      [Frontend: Next.js + Vercel]
                                |
                          SSE / WebSocket
                                |
                      [graph-engine: Fly.io]
                       /        |        \
                 [Qdrant]  [PostgreSQL]  [Redis]
                 vectors    KG + state    cache + streams
```

## Components

### shared-schemas (packages/shared-schemas/)

Source of truth for all Pydantic models. Both graph-engine and frontend (via generated TypeScript) consume these types.

Key models:

- `GraphState` — central state flowing through every node (includes `session_id`, `conversation_history`)
- `GradeResult` / `ConfidenceScores` — quality gate schemas
- `StreamNodeEvent` / `SSEMessage` — real-time event schemas
- Domain models: Company, Visa, Property, Tax, KBLI

### graph-engine (apps/graph-engine/)

LangGraph StateGraph with:

- **6 core nodes:** understand, retrieve, reason, synthesize, route, tools
- **5 grader nodes:** retrieval, reasoning, answer, hallucination (LLM-verified), pricing
- **4 subgraphs:** company, visa, property, tax
- **Services:** LLM gateway, vector store, KG store, semantic cache (2-layer), embeddings, conversation memory

### Standalone Services (apps/services/)

- **CRM:** CRUD business logic (not AI pipeline)
- **Ingestion:** Document processing (batch, not query-time)
- **Notifications:** Multi-channel push

### Frontend (apps/web/)

- Next.js with Atomic Design (atoms → molecules → organisms → templates)
- `useGraph()` hook for SSE streaming with `session_id` support
- `useChatPage()` hook with ref-based answer tracking (closure bug fixed)
- Zustand state management (planned)
- Auto-generated TypeScript types from Pydantic

## Inter-Service Communication

Redis Streams for async messaging between services.
Redis Pub/Sub for real-time frontend streaming.

```
graph-engine --Redis Streams--> CRM (client activity)
graph-engine --Redis Streams--> Notifications (alerts)
graph-engine --Redis Pub/Sub--> Frontend SSE (node progress)
ingestion    --Redis Streams--> graph-engine (cache invalidation)
```

## Semantic Cache (2-layer)

```
Query → Exact SHA-256 hash lookup (Redis, O(1))
      → Miss: Qdrant cosine similarity (threshold 0.92, collection v6_cache_vectors)
      → Miss: Full graph invocation
      → Store result in both Redis + Qdrant vector
```

## Conversation Memory

```
session_id (client-generated per tab)
  → Redis v6:session:{id} (TTL 24h, max 10 turns sliding window)
  → Loaded into GraphState.conversation_history before each invocation
  → understand node uses history for follow-up context
  → DELETE /api/session/{id} clears on new chat
```

## Observability

Structured JSON logs (structlog) → Fly.io log drain:

- Per-node timing via `NodeTimer` / `trace_node` decorator
- `GraphMetrics` accumulates run-level summary
- Fields: `node`, `duration_ms`, `run_id`, `intent`, `correction_count`, `last_grade_score`

## Deployment

| App          | Platform | Region        |
| ------------ | -------- | ------------- |
| graph-engine | Fly.io   | Singapore     |
| CRM          | Fly.io   | Singapore     |
| Frontend     | Vercel   | Edge (global) |

Databases shared with V5 but isolated:

- PostgreSQL: separate `v6` schema
- Qdrant: same collections (read-only) + `v6_cache_vectors` (new)
- Redis: `v6:` key prefix

# Architecture Decision Records (ADR) — Nuzantara

**Last Updated:** 2026-02-26

Each ADR documents a significant architecture choice, its context, rationale, and consequences.

---

## ADR-001: Gemini as Primary LLM, OpenAI Only for Embeddings

**Date:** 2025-12
**Status:** Active
**Decision:** Use Google Gemini (Flash/Pro) as the primary LLM for chat, reasoning, and tool use. OpenAI is used exclusively for embeddings (`text-embedding-3-small`).

**Context:** The system processes thousands of chat queries daily across web, Telegram, WhatsApp, Instagram, and Twitter. LLM costs scale linearly with query volume.

**Rationale:**

- Gemini Flash is 5-10x cheaper per token than GPT-4 for equivalent quality on our domain (Indonesian business law)
- Gemini Pro provides a quality step-up for complex reasoning without switching providers
- OpenAI's `text-embedding-3-small` produces superior embeddings for our bilingual (ID/EN) corpus

**Implementation:**

- `LLMGateway` cascade: Gemini Pro → Flash → Flash-Lite → OpenRouter (fallback)
- `orchestrator.py` line 100 sets the default model
- Embedding model is **frozen** (`text-embedding-3-small`, 1536 dims) — changing would invalidate 58,880 vectors

**Consequences:**

- (+) Significant cost reduction (~70% vs all-OpenAI)
- (+) Gemini's longer context window (1M tokens) supports full document analysis
- (-) Two provider dependencies instead of one
- (-) Gemini API occasionally has higher latency spikes than OpenAI

---

## ADR-002: PostgreSQL as Message Bus for Generals (No Kafka/RabbitMQ)

**Date:** 2026-02
**Status:** Active
**Decision:** Use PostgreSQL tables (`generals_tasks`, `generals_locks`) as a task queue/message bus for the multi-agent "Generals" system.

**Context:** The Generals system coordinates multiple AI agents (Intelligence, Coding, Antigravity) executing background tasks. A message bus is needed for task dispatch and result collection.

**Rationale:**

- PostgreSQL is already deployed and managed on Fly.io
- Adding Kafka or RabbitMQ requires additional infrastructure, cost, and ops burden
- `FOR UPDATE SKIP LOCKED` provides non-blocking queue consumption (PostgreSQL built-in)
- `INSERT ... ON CONFLICT DO NOTHING` provides atomic lock acquisition
- Current throughput (<100 tasks/day) is orders of magnitude below PostgreSQL's limits

**Implementation:**

- Migration 053: `generals_tasks`, `generals_memory`, `generals_locks`, `generals_activity` tables
- `TaskCoordinator` polls every 5s (configurable)
- Distributed locking via `generals_locks` with TTL-based expiration

**Consequences:**

- (+) Zero additional infrastructure
- (+) Full ACID transactions on task state
- (+) Built-in query and audit capabilities
- (-) 5s polling latency (acceptable for current use case)
- (-) Won't scale to >10,000 tasks/hour without query optimization

---

## ADR-003: Lazy Import Architecture for Fly.io Cold Start

**Date:** 2026-02-12
**Status:** Active
**Decision:** Move all heavy imports (torch, sentence-transformers, 70+ router modules) inside functions. Use `asyncio.create_task()` for background service initialization.

**Context:** Backend crash-looped on Fly.io because synchronous module-level imports of ML libraries prevented the server from responding to health checks within the 60s grace period.

**Rationale:**

- Fly.io kills containers that don't respond to health checks within 60s
- ML imports (torch, sentence-transformers) take 30-45s on a 2GB VM
- 70+ router imports add another 10-15s at module level
- The solution is to defer all heavy work and respond immediately to `/health`

**Implementation:**

- `app_factory.py`: `lifespan()` spawns `_background_init()` as a task, then yields immediately
- `service_initializer.py`: All 20+ service imports moved inside functions
- `router_registration.py`: All 70+ router imports moved inside `include_routers()`
- `/health` returns `{"status": "initializing"}` (HTTP 200) during warmup

**Key files:**

- `backend/app/setup/app_factory.py`
- `backend/app/setup/service_initializer.py`
- `backend/app/setup/router_registration.py`
- `Dockerfile`: `--workers 1` (2 workers = OOM on 2GB)

**Consequences:**

- (+) Server starts accepting connections in <5s
- (+) Health checks pass immediately
- (+) No more crash-loops on deploy
- (-) First real request may hit initializing state (returns 503 via readiness probe)
- (-) Import errors are deferred to runtime instead of startup

---

## ADR-004: Orchestrator Decomposition (Single Class → 7 Managers)

**Date:** 2026-01
**Status:** Active
**Decision:** Split the monolithic `AgenticRAGOrchestrator` (2000+ lines) into 7 specialized manager classes.

**Context:** The orchestrator grew organically as features were added (streaming, context management, routing, metrics, response building). The single file became unmaintainable.

**Rationale:**

- Single Responsibility: each manager handles one concern
- Testability: managers can be unit tested independently
- Shared code: streaming and non-streaming paths share `prepare_query_context()`
- Cognitive load: ~300 lines per manager vs 2000+ in one file

**Implementation:**

```
AgenticRAGOrchestrator (orchestrator.py)
  └── OrchestratorCore (orchestrator_core.py)
        ├── OrchestratorContextManager (orchestrator_context.py)
        ├── OrchestratorRoutingManager (orchestrator_routing.py)
        └── OrchestratorResponseBuilder (orchestrator_response.py)
  └── OrchestratorStreamingCore (orchestrator_streaming_core.py)
```

**Consequences:**

- (+) Each file is <400 lines and has a clear responsibility
- (+) Streaming and non-streaming share context preparation
- (+) LLMGateway is swappable without touching business logic
- (-) 7 files to navigate instead of 1
- (-) Cross-manager dependencies require careful interface design

---

## ADR-005: Three-Tier Memory Model

**Date:** 2026-01
**Status:** Active
**Decision:** Implement three distinct memory tiers: Personal Facts, Collective Knowledge, and Episodic Timeline.

**Context:** Users interact across multiple channels (web, Telegram, WhatsApp). The AI needs to remember personal context, share cross-user knowledge, and recall time-ordered events.

**Rationale:**

- Personal facts (name, preferences) are user-specific and long-lived
- Collective knowledge (legal changes, pricing updates) benefits all users
- Episodic memory (what happened when) requires temporal ordering
- Different access patterns require different storage strategies

**Implementation:**

- `MemoryOrchestrator` (facade): single interface, read/write locking per user
- `MemoryServicePostgres`: personal facts in `user_stats.profile_facts` (JSONB)
- `CollectiveMemoryService`: confidence-ranked facts shared across users
- `EpisodicMemoryService`: time-ordered events in `episodic_events` table
- Circuit breaker: 5 consecutive failures → stop calling broken service
- Background save: `asyncio.create_task()` so memory persistence never blocks response

**Consequences:**

- (+) Graceful degradation: if one tier fails, others continue
- (+) Per-user locking prevents race conditions
- (+) Background save keeps response latency low
- (-) Three storage subsystems to maintain
- (-) Fact extraction is regex-based (not LLM-powered), limiting accuracy

---

## ADR-006: Abstract Channel Pattern for Multi-Platform Chat

**Date:** 2025-12
**Status:** Active
**Decision:** Use an abstract `BaseChannel` class with concrete adapters per platform. All channels funnel through a single `ConversationEngine`.

**Context:** The system serves users on 5 platforms (Web, Telegram, WhatsApp, Instagram, Twitter/X), each with different constraints (message length, markdown support, media, streaming).

**Rationale:**

- Business logic must be platform-agnostic
- Each platform has unique constraints that must be handled at the adapter level
- Adding a new channel should require only implementing 4 abstract methods

**Implementation:**

- `BaseChannel`: 4 abstract methods (`receive_message`, `send_response`, `send_status_update`, `stream_response`) + 4 abstract properties
- `ChannelRouter`: dispatches on channel name, normalizes to `ChannelMessage`
- Platform constraints handled in adapters:
  - Telegram: 4096 char limit, progressive message updates
  - WhatsApp: 4096 char limit, must split into multiple messages
  - Web: SSE streaming, no practical length limit

**Consequences:**

- (+) Zero business logic in channel adapters
- (+) Adding a new channel = one adapter file
- (+) Easy to test business logic independently of channels
- (-) Channel-specific features (reactions, buttons) require BaseChannel extension

---

## ADR-007: Evidence Scoring with ABSTAIN Capability

**Date:** 2026-01
**Status:** Active
**Decision:** Implement a confidence scoring system that can refuse to answer (ABSTAIN) when evidence is insufficient.

**Context:** RAG systems commonly hallucinate when no relevant documents are retrieved. A confidence threshold prevents the AI from generating plausible-sounding but incorrect answers about Indonesian regulations.

**Rationale:**

- Legal/regulatory domain: wrong answers are worse than no answer
- `< 0.15` → ABSTAIN (refuse)
- `0.15 - 0.60` → CAUTIOUS (answer with disclaimer)
- `> 0.60` → NORMAL (confident answer)
- Trusted tools (calculator, pricing, team_knowledge) bypass evidence check because they provide their own evidence

**Critical fix (2026-02-17):** "Tools-available bypass" — if the LLM had tools available and chose to answer without calling any, that counts as trusted (prevents ABSTAIN on all English business queries when the model answers from parametric knowledge).

**Implementation:** `reasoning.py:867-883` (trusted tools check)

**Consequences:**

- (+) Prevents hallucination on regulatory questions
- (+) Users trust the system more because it admits uncertainty
- (-) Can be overly conservative (ABSTAIN on valid queries)
- (-) Requires careful tuning of thresholds per domain

---

## ADR-008: Fail-Closed Auth Middleware

**Date:** 2025-12
**Status:** Active
**Decision:** Auth middleware returns HTTP 503 on any internal error, never 200 or pass-through.

**Context:** A bug in auth middleware that results in an unhandled exception could accidentally grant access to protected endpoints.

**Rationale:**

- Security: a broken auth system should block all access, not grant it
- 503 (Service Unavailable) signals the correct semantics: "we can't verify your identity"
- Public endpoints are explicitly whitelisted with documented business justification

**Implementation:** `hybrid_auth.py` — any exception in the middleware → 503.

**Consequences:**

- (+) Zero risk of accidental access on auth failure
- (-) Auth bugs cause total API outage (by design)

---

## ADR-009: Single Worker on Fly.io (Memory Constraint)

**Date:** 2026-02-12
**Status:** Active
**Decision:** Run exactly 1 uvicorn worker on the 2GB Fly.io VM.

**Context:** ML models (torch, sentence-transformers) consume ~2GB per worker process. With a 2GB VM, even 1 worker is tight and 2 workers would OOM kill.

**Rationale:**

- 1 worker × 2GB ML models = tight fit in 2GB VM (lazy loading + deferred init required)
- 2 workers = impossible on 2GB, guaranteed OOM kill
- Fly.io's `min_machines_running = 1` + `auto_stop_machines = false` ensures the single worker is always hot
- Rolling deploys (`strategy = rolling`) provide zero-downtime updates

**Implementation:** `Dockerfile` CMD: `--workers 1`. Comment explicitly warns not to change without upgrading VM.

**Consequences:**

- (+) Stable, no OOM kills
- (+) Cost-effective (2GB VM)
- (-) Single-threaded processing (mitigated by async I/O)
- (-) No process-level fault tolerance (one bad request can't be isolated)

---

## ADR-010: Database V2 Migration Squash

**Date:** 2026-01-25
**Status:** Active
**Decision:** Squash 44 legacy migration files into a single baseline SQL snapshot. New migrations go into `migrations_v2/`.

**Context:** 44 incremental migration files accumulated over months. Some were written by different AI tools with conflicting styles. Running all 44 on a fresh database took 2+ minutes and occasionally failed due to ordering issues.

**Rationale:**

- Single baseline snapshot is idempotent and fast (<5s)
- "Fake apply" mechanism detects existing production DBs and marks baseline as applied
- Legacy migrations archived in `migrations_legacy_archive/` for audit trail

**Implementation:**

- `migrations_v2/001_baseline_v2.sql`: complete schema snapshot
- Fake apply: checks if any table from the baseline exists → skips baseline
- New migrations start at 002+

**Consequences:**

- (+) Fresh deployments take <5s instead of 2+ minutes
- (+) No migration ordering bugs
- (+) Clean separation between legacy and new migrations
- (-) Cannot `alembic downgrade` past the squash point

---

## ADR-011: KG LangGraph Behind Feature Flag

**Date:** 2026-02-09
**Status:** Active
**Decision:** Deploy the LangGraph Knowledge Graph system behind `ENABLE_KG_LANGGRAPH` environment variable (default: disabled).

**Context:** The LangGraph KG system adds BFS traversal, domain subgraphs (Company, Visa, Property, Tax), and golden routes. It's fully tested (82/82 tests) but represents a significant change to query processing.

**Rationale:**

- Allows gradual rollout and A/B testing
- Production can fall back instantly by unsetting the env var
- No code changes needed for enable/disable
- 3-way parallel execution (Entity Extraction + KG Legacy + KG LangGraph) when enabled

**Implementation:**

- `orchestrator_core.py` lines 154-254: checks feature flag before spawning KG LangGraph task
- When enabled: workflow output appended to system prompt as "SUGGESTED WORKFLOW"
- Routing priority: Domain subgraphs → Golden routes → BFS traversal → END

**Consequences:**

- (+) Zero-risk deployment
- (+) Can measure impact via A/B testing
- (-) Dead code when disabled
- (-) Must maintain both KG paths until full migration

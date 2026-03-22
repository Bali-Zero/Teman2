# Nuzantara Autonomous Agents — V2 Enhanced Architecture

**Version**: 2.0
**Date**: 2026-03-14
**Author**: Senior AI Architect & Systems Lead
**Status**: Deep Research Validated
**Predecessor**: `2026-03-14-autonomous-agents-design.md` (V1)

---

## Executive Summary

This document enhances the V1 "Military-Grade" Agent Architecture with findings from intensive SOTA research across four pillars: Multi-Agent Orchestration, Deterministic Validation, Agent Memory, and Self-Healing Systems. Every recommendation is filtered through Nuzantara's constraints: Python 3.11+, async-first, 2GB RAM on Fly.io, flat Qdrant payloads, and Indonesian regulatory compliance.

**Key architectural decisions validated by research:**

| Decision                                    | Framework                           | Evidence                                                                                         |
| ------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| LangGraph 1.0 as orchestration backbone     | StateGraph + subgraph composition   | 91% task completion, native async, PostgreSQL checkpointing, deterministic+LLM nodes first-class |
| Hybrid Loop pattern (not pure agent chains) | 12-Factor Agents + STAC Research    | "Let code own safety and execution. Let LLM own reasoning at key points."                        |
| JSONL + Qdrant dual memory                  | IBM Trajectory-Informed Memory      | +14.3pp goal completion with learned patterns. JSONL for audit, Qdrant for semantic retrieval    |
| Graduated autonomy with earned trust        | Feng et al. L1-L5 + Earned Autonomy | Track record-based graduation, not binary permissions                                            |
| Stage-gated self-healing (VIGIL pattern)    | VIGIL + LogicMonitor L0-L5          | Illegal transitions produce errors, not improvisation                                            |

---

## 1. Architecture Overview: The Zantara Order

### 1.1 The Hybrid Loop (OBSERVE → DECIDE → VALIDATE → ACT → MEASURE → LEARN)

The V1 design specified OBSERVE→DECIDE→ACT→MEASURE→LEARN. Research reveals a critical missing step: **VALIDATE** — an explicit deterministic gate between DECIDE and ACT.

This maps to the OODA loop (Col. John Boyd) with two Zantara innovations:

| OODA       | Zantara Order | Powered By         | Rationale                                              |
| ---------- | ------------- | ------------------ | ------------------------------------------------------ |
| Observe    | **OBSERVE**   | LLM                | Interpret heterogeneous signals (APIs, logs, GSC data) |
| Orient     | **DECIDE**    | LLM + Rules        | Generate constrained action plan                       |
| —          | **VALIDATE**  | 100% Deterministic | Pydantic + rule engine VETO gate                       |
| Decide+Act | **ACT**       | 100% Deterministic | Execute approved actions via typed tool calls          |
| —          | **MEASURE**   | 100% Deterministic | Collect metrics, check thresholds                      |
| (loop)     | **LEARN**     | LLM                | Synthesize patterns from outcomes                      |

**Source**: STAC Research "Stop Building Agent Chains. Start Building Hybrid Loops" (Jan 2026); 12-Factor Agents (HumanLayer, 18.6k stars).

**Why VALIDATE is mandatory**: The Kiro Incident (Amazon, March 2026) demonstrated that without an explicit deterministic gate, an LLM agent autonomously deleted and recreated an AWS production environment, causing a 13-hour outage. The VALIDATE step ensures code owns safety, not the LLM.

### 1.2 Military Hierarchy — Refined

Research validates the General→Commander→Captain hierarchy but limits nesting to **2 levels maximum** (LangGraph subgraph composition bugs beyond 2 levels — Issues #4748, #4182, #3020).

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUPREME COMMAND                               │
│           (PostgreSQL agent_events table)                        │
│     Cross-domain coordination via event bus                      │
└────────┬──────────┬──────────┬──────────┬──────────┬────────────┘
         │          │          │          │          │
    ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐ ┌─────────┐
    │ G1-CRM │ │G2-Intel│ │G3-Cont.│ │G4-SEO  │ │G5-Comms│ │G6-Infra │
    │General │ │General │ │General │ │General │ │General │ │General  │
    └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬────┘
         │          │          │          │          │          │
    Commanders  Commanders Commanders Commanders Commanders Commanders
         │          │          │          │          │          │
    Captains    Captains   Captains   Captains   Captains   Captains
         │          │          │          │          │          │
    ┌────▼──────────▼──────────▼──────────▼──────────▼──────────▼────┐
    │                    SOLDIERS (96 MCP Tools)                      │
    │         Atomic operations: search_kbli, create_client, etc.     │
    └─────────────────────────────────────────────────────────────────┘
```

**Grade definitions (research-enhanced):**

| Grade         | LangGraph Mapping               | Autonomy Level                  | Loop Frequency | State                 |
| ------------- | ------------------------------- | ------------------------------- | -------------- | --------------------- |
| **General**   | Parent StateGraph               | L4-L5 (Approver/Observer)       | Weekly         | PostgreSQL checkpoint |
| **Commander** | Subgraph (via wrapper function) | L3-L4 (Consultant/Approver)     | Daily          | JSONL + state.json    |
| **Captain**   | Node within Commander graph     | L2-L3 (Collaborator/Consultant) | Per-trigger    | In-memory             |
| **Soldier**   | MCP tool call                   | L1 (Operator)                   | Per-call       | Stateless             |

### 1.3 Cross-Domain Coordination: The Event Bus

Research compared four patterns. **Database-backed coordination** is optimal for our case — it uses existing PostgreSQL infrastructure, provides full audit trail, and decouples agents in time and space.

**Schema:**

```sql
CREATE TABLE agent_events (
    id SERIAL PRIMARY KEY,
    source_domain TEXT NOT NULL,        -- 'seo', 'content', 'crm', 'intel', 'comms', 'infra'
    source_agent TEXT NOT NULL,         -- 'seo_guardian', 'content_publisher'
    event_type TEXT NOT NULL,           -- 'opportunity_discovered', 'article_ready', 'alert'
    payload JSONB NOT NULL,
    priority TEXT DEFAULT 'normal',     -- 'critical', 'high', 'normal', 'low'
    created_at TIMESTAMP DEFAULT NOW(),
    consumed_by TEXT[] DEFAULT '{}',
    status TEXT DEFAULT 'pending'       -- 'pending', 'consumed', 'expired'
);

CREATE INDEX idx_agent_events_pending ON agent_events (status, source_domain) WHERE status = 'pending';
```

**Example cross-domain flow:**

1. SEO Guardian discovers keyword gap → writes `{event_type: "keyword_opportunity", payload: {keyword: "KBLI 2025 changes", volume: 1200}}`
2. Content Commander polls for `keyword_opportunity` events → generates article brief
3. Publishing Captain checks article quality → writes `{event_type: "article_published", payload: {url, keyword}}`
4. SEO Guardian's next OBSERVE reads the published article → submits to Google Indexing API

**Why not A2A, Kafka, or Redis Streams**: A2A adoption is too early (no mature Python library). Kafka/Redis add infrastructure we don't need at our scale (<100 events/day). PostgreSQL LISTEN/NOTIFY provides real-time if needed later.

**Event polling mechanism**: Commanders poll for events on their cron schedule (daily for most, every 6h for compliance). At <100 events/day, cron-schedule polling is sufficient. No dedicated event dispatcher needed until event volume exceeds ~500/day.

**Note on `consumed_by TEXT[]`**: PostgreSQL array columns work well at low scale. If cross-domain flows grow beyond ~500 events/day, refactor to a normalized `agent_event_consumers` join table for better queryability.

---

## 2. Pillar 1: Multi-Agent Orchestration (LangGraph 1.0)

### 2.1 Why LangGraph — Mathematical Justification

| Requirement                     | LangGraph 1.0                                          | CrewAI                                   | AutoGen                     |
| ------------------------------- | ------------------------------------------------------ | ---------------------------------------- | --------------------------- |
| Deterministic + LLM nodes mixed | First-class. Any node = pure function or LLM call      | Everything through LLM                   | Everything = conversation   |
| Async-first                     | Native `ainvoke`, `astream`, async checkpointers       | Thread-pool wrapping                     | Good in v0.4                |
| PostgreSQL checkpoint           | `AsyncPostgresSaver` built-in                          | None                                     | None                        |
| Retry with validation           | Conditional edges + revision counter (4h to implement) | 2 days of framework fighting             | Possible but fragile        |
| Task completion (12+ steps)     | 85%                                                    | 61% (degrades past 8 steps)              | 88%                         |
| Memory footprint                | Lightweight core. Cost = state size.                   | Higher base (role metadata, backstories) | Moderate                    |
| Subgraph composition            | `add_node("name", compiled_subgraph)`                  | N/A                                      | Nested group chat (limited) |

**Source**: agent-harness.ai production benchmark (2026).

**CrewAI eliminated** because: (1) Delegation bug — manager executes tasks itself instead of delegating (Issue #4783, March 2026); (2) Performance degrades past 8 steps; (3) No built-in checkpoint persistence.

**AutoGen eliminated** because: (1) Conversation-based flow makes deterministic control hard; (2) `speaker_selection_method='auto'` is unpredictable in production; (3) No graph-level checkpointing.

### 2.2 Graph Architecture Pattern

Each **Commander** is a LangGraph StateGraph with the Zantara Order loop:

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class CommanderState(TypedDict):
    observations: dict                                    # OBSERVE output
    action_plan: list[dict]                               # DECIDE output
    validation_result: dict                               # VALIDATE output
    execution_results: list[dict]                         # ACT output
    measurements: list[dict]                              # MEASURE output
    learned_patterns: list[dict]                          # LEARN output
    revision_count: Annotated[int, operator.add]          # Retry cap
    cycle_status: str                                     # Current phase

# Build the Zantara Order graph
graph = StateGraph(CommanderState)
graph.add_node("observe", observe_node)          # LLM: interpret signals
graph.add_node("decide", decide_node)            # LLM + rules: generate plan
graph.add_node("validate", validate_node)        # DETERMINISTIC: Pydantic + rule engine
graph.add_node("act", act_node)                  # DETERMINISTIC: execute via MCP tools
graph.add_node("measure", measure_node)          # DETERMINISTIC: collect metrics
graph.add_node("learn", learn_node)              # LLM: synthesize patterns

graph.add_edge("observe", "decide")
graph.add_conditional_edges("decide", route_validation, {
    "validate": "validate",
    "skip": END,                                 # No actionable opportunities
})
graph.add_conditional_edges("validate", route_after_validation, {
    "act": "act",                                # APPROVED
    "decide": "decide",                          # REJECTED, retry (if revision_count < 3)
    "end": END,                                  # REJECTED, max retries reached
})
graph.add_edge("act", "measure")
graph.add_edge("measure", "learn")
graph.add_edge("learn", END)
```

**Key pattern**: `revision_count` with `Annotated[int, operator.add]` auto-increments on each retry. The `route_after_validation` function checks `state["revision_count"] < 3` before looping back. This prevents unbounded retry loops — the #1 cost explosion risk identified in research.

### 2.3 General-to-Commander Dispatch (Parent Graph)

Each **General** is a parent StateGraph that dispatches to Commander subgraphs:

```python
# Commander subgraphs compiled separately
seo_indexing_commander = build_indexing_commander().compile()
seo_ctr_commander = build_ctr_commander().compile()

# General wraps Commanders via function pattern (avoids LangGraph subgraph bugs)
def dispatch_to_indexing(state: GeneralState) -> GeneralState:
    result = seo_indexing_commander.invoke({
        "observations": state["domain_observations"],
        "revision_count": 0,
    })
    return {"commander_results": [result]}

general_graph = StateGraph(GeneralState)
general_graph.add_node("triage", triage_node)                    # Decide which Commanders to activate
general_graph.add_node("indexing_cmd", dispatch_to_indexing)      # Wrapper function pattern
general_graph.add_node("ctr_cmd", dispatch_to_ctr)
general_graph.add_node("consolidate", consolidate_results)
```

**Why wrapper function pattern**: Direct `add_node("name", compiled_subgraph)` has known bugs with state sharing across parent-child boundaries (Issues #4748, #4182). The wrapper function gives explicit control over state transformation.

**Implementation note**: The `revision_count` reducer (`Annotated[int, operator.add]`) increments on ANY state return containing a value — ensure only the validate→decide retry path returns `{"revision_count": 1}`. All other nodes should omit it.

**Session safety guards** (from VIGIL pattern, Section 5.3) must be embedded in the Commander graph as a conditional edge before `act`: `max_actions: 50`, `max_runtime: 600s`. When limits are reached, route to END with a status report instead of continuing.

### 2.4 Checkpointing Strategy for 2GB RAM

| Context              | Checkpointer              | Rationale                                                                                                                                                                          |
| -------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Production (Fly.io)  | `AsyncPostgresSaver`      | Uses existing nuzantara-postgres. Connection pool via `asyncpg(min_size=2, max_size=10)`. Note: existing KG LangGraph uses sync `PostgresSaver` — migrate to async during Phase 2. |
| Local dev (Pro)      | `SqliteSaver`             | Zero network latency, single writer is fine for dev                                                                                                                                |
| Cron jobs (OpenClaw) | File-based (`state.json`) | Agents run as scripts, not as persistent services. No need for DB checkpointing                                                                                                    |

**Memory budget analysis** (validated by research):

| Component                 | Estimated RAM | Notes                                                              |
| ------------------------- | ------------- | ------------------------------------------------------------------ |
| Python process            | ~150MB        | FastAPI + dependencies                                             |
| LangGraph graph objects   | ~5MB          | Compiled graphs are lightweight data structures                    |
| Checkpoint state (active) | ~10-50MB      | Depends on message history length. Cap with list-limiting reducers |
| Qdrant client             | ~50MB         | Connection pool + in-flight vectors                                |
| Remaining for workload    | ~1.7GB        | Ample headroom                                                     |

**Graph compilation is NOT the cold start bottleneck**. `StateGraph.compile()` takes milliseconds. The bottleneck is checkpoint backend initialization (asyncpg pool creation: ~1-2s). Strategy: pre-compile graphs at module level, lazy-init checkpoint pool on first request.

---

## 3. Pillar 2: The Zantara Order — Deterministic Validation

### 3.1 The Three-Gate Validation Pipeline

Every LLM output passes through three sequential gates before execution:

```
LLM Output (raw)
    │
    ▼
┌──────────────────┐
│ Gate 1: Schema   │  Pydantic v2 model_validator(mode='before')
│ (structural)     │  Fix missing fields, normalize formats, strip preamble
└────────┬─────────┘
         │ PASS
         ▼
┌──────────────────┐
│ Gate 2: Business │  Pydantic v2 field_validator + model_validator(mode='after')
│ Rules            │  Cross-field validation, corrections.jsonl enforcement
└────────┬─────────┘
         │ PASS
         ▼
┌──────────────────┐
│ Gate 3: Evidence │  Confidence scoring (ABSTAIN / CAUTIOUS / NORMAL)
│ Scoring          │  Source attribution, hallucination detection
└────────┬─────────┘
         │ PASS → ACT
         │ FAIL → VETO with structured audit
```

### 3.2 Gate 1: Schema Validation (Pydantic v2)

```python
from pydantic import BaseModel, model_validator, field_validator, Field

class ActionPlan(BaseModel):
    """Validated action plan from LLM DECIDE step."""
    actions: list[Action]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode='before')
    @classmethod
    def normalize_llm_output(cls, data: dict) -> dict:
        # Fix common LLM output issues
        if isinstance(data.get('actions'), dict):
            data['actions'] = [data['actions']]  # Wrap single action in list
        if 'confidence' not in data:
            data['confidence'] = 0.5  # Default to CAUTIOUS
        return data

class Action(BaseModel):
    action_type: str
    scope: str
    params: dict
    risk_level: str = Field(pattern=r'^(LOW|MEDIUM|HIGH)$')
```

**Why Pydantic v2**: Core written in Rust, 4-17x faster than v1. For single LLM response validation, overhead is microseconds vs seconds of LLM latency — negligible. Use `Annotated` constraints over `@field_validator` when possible (stays in Rust hot path).

### 3.3 Gate 2: Business Rules (Corrections Engine)

The corrections.jsonl pattern from V1 is validated by research as a lightweight deterministic policy engine (comparable to Agent RuleZ but simpler):

```python
class CorrectionRule(BaseModel):
    rule: str           # 'never_touch', 'max_batch', 'no_content_edit', 'require_approval'
    scope: str          # Glob pattern: '/lifestyle/*', '/kbli/*'
    value: int | None   # For numeric limits
    reason: str         # Human-readable rationale

def enforce_corrections(action: Action, rules: list[CorrectionRule]) -> ValidationResult:
    for rule in rules:
        if rule.rule == "never_touch" and glob_match(action.scope, rule.scope):
            return ValidationResult(
                approved=False,
                reason=f"VETO: {rule.rule} on {rule.scope} — {rule.reason}",
                rule_id=rule.rule,
                input_hash=sha256(action.json()),
            )
    return ValidationResult(approved=True, reason="All rules passed")
```

### 3.4 Gate 3: Evidence Scoring

The existing 3-tier system (ABSTAIN < 0.15, CAUTIOUS 0.15-0.60, NORMAL > 0.60) is validated by research. Enhancement: add source attribution scoring.

```python
from enum import Enum

class ConfidenceLevel(Enum):
    ABSTAIN = "abstain"      # Refuse to answer/act
    CAUTIOUS = "cautious"    # Act with disclaimer/reduced scope
    NORMAL = "normal"        # Full autonomous action

def score_evidence(
    plan: ActionPlan,
    retrieved_context: list[str],
    corrections: list[CorrectionRule],
) -> tuple[ConfidenceLevel, float]:
    # Signal 1: LLM self-reported confidence
    llm_confidence = plan.confidence

    # Signal 2: Source coverage (what fraction of actions are backed by data?)
    backed_actions = sum(1 for a in plan.actions if a.params.get("source"))
    source_ratio = backed_actions / max(len(plan.actions), 1)

    # Signal 3: Correction alignment (no corrections violated = higher confidence)
    violations = sum(1 for a in plan.actions
                     for r in corrections
                     if would_violate(a, r))
    correction_score = 1.0 - (violations / max(len(plan.actions), 1))

    # Weighted ensemble
    score = 0.4 * llm_confidence + 0.3 * source_ratio + 0.3 * correction_score

    if score < 0.15:
        return ConfidenceLevel.ABSTAIN, score
    elif score < 0.60:
        return ConfidenceLevel.CAUTIOUS, score
    return ConfidenceLevel.NORMAL, score
```

### 3.5 VETO Audit Trail

Every VALIDATE decision is logged with full reproducibility data:

```python
@dataclass
class VetoRecord:
    timestamp: str              # ISO 8601
    agent_id: str               # Which agent
    phase: str                  # 'validate'
    approved: bool
    confidence: float
    confidence_level: str       # ABSTAIN/CAUTIOUS/NORMAL
    rule_triggered: str | None  # Which correction rule (if any)
    input_hash: str             # SHA256 of the proposed action plan
    validator_version: str      # Git SHA of validation code
    reasoning: str              # Why approved or rejected
```

**Source**: "The Verifiable Orchestrator" (Applied Ingenuity, Feb 2026) — treating the LLM as an unreliable dependency with deterministic verification at every boundary.

---

## 4. Pillar 3: Agent Memory Architecture

### 4.1 Dual-Store Pattern: JSONL + Qdrant

Research validates a two-tier memory architecture:

| Store               | Purpose                                              | Query Pattern                         | Scale                     |
| ------------------- | ---------------------------------------------------- | ------------------------------------- | ------------------------- |
| **JSONL** (file)    | Action log, audit trail, source of truth             | Append-only, full scan, git-trackable | < 1,000 entries per agent |
| **Qdrant** (vector) | Semantic retrieval of patterns, cross-agent learning | "Find similar past situations"        | Consolidated patterns     |

**Why not SQLite**: For < 1,000 entries, JSONL is simpler (no schema migrations, human-readable, git-trackable). SQLite adds value at > 5,000 structured records where indexed queries matter.

**Why Qdrant for patterns**: When a Commander runs DECIDE, it needs "what happened last time we saw this pattern?" — semantic similarity search. JSONL cannot answer this; Qdrant can.

### 4.2 Memory Types (4-Type Framework)

Based on Paul Iusztin's framework (Dec 2025) and IBM's Trajectory-Informed Memory:

| Type           | Storage                               | Example                                              | Lifecycle                |
| -------------- | ------------------------------------- | ---------------------------------------------------- | ------------------------ |
| **Working**    | In-memory (LangGraph state)           | Current cycle's observations                         | Per-cycle                |
| **Episodic**   | JSONL (`memory.jsonl`)                | "Submitted 30 URLs, 28 OK, 2 rate limited"           | Permanent, with decay    |
| **Semantic**   | Qdrant (`agent_learnings` collection) | "Batch sizes >50 cause rate limiting after 3pm WITA" | Extracted from episodic  |
| **Procedural** | JSONL (`corrections.jsonl`)           | "Never touch /lifestyle/\* pages"                    | Manual + auto-discovered |

### 4.3 Episodic → Semantic Consolidation (LEARN Phase)

The LEARN phase performs memory consolidation — promoting recurring episodic patterns to semantic rules:

```
Episodic (memory.jsonl):
  Entry 1: "batch_50 at 14:00 → timeout" (2026-03-14)
  Entry 2: "batch_50 at 15:00 → timeout" (2026-03-14)
  Entry 3: "batch_30 at 07:00 → success" (2026-03-15)
  Entry 4: "batch_50 at 19:00 → timeout" (2026-03-14)
  Entry 5: "batch_30 at 08:00 → success" (2026-03-15)

         ↓ LEARN phase (LLM + statistics) ↓

Semantic (Qdrant agent_learnings):
  Pattern: "Google Indexing API rate limits batch_50 after ~150 daily submissions"
  Confidence: 0.85 (3/3 failures match pattern)
  Correction generated: {"rule": "max_indexing_batch", "value": 30, "reason": "auto-learned from 3 timeouts"}
```

**IBM Trajectory-Informed Memory** showed **+14.3pp improvement** in goal completion when agents use this pattern. For complex multi-step tasks: **+28.5pp (149% relative increase)**.

### 4.4 Qdrant Configuration for 2GB RAM

**Memory budget** (9 existing collections + 1 new `agent_learnings`):

| Component                      | Size        | Notes                                |
| ------------------------------ | ----------- | ------------------------------------ |
| 67K existing vectors × 6KB     | ~402MB      | `text-embedding-3-small` (1536 dims) |
| HNSW indexes                   | ~600MB      | ~1.5x vector size                    |
| Payloads + metadata            | ~50MB       | Flat payloads, small                 |
| Per-collection overhead × 10   | ~200MB      | WAL, segments, metadata              |
| **Total without quantization** | **~1.25GB** | Leaves ~750MB for Qdrant process     |

**Optimization for 2GB**:

1. **Scalar quantization** (int8) on largest collections → reduces vector memory from 402MB to ~100MB
2. `on_disk_payload: true` for collections with large text payloads
3. `full_scan_threshold: 10000` — brute-force scan for tiny collections (faster than HNSW)
4. New `agent_learnings` collection: small (< 1,000 points), no quantization needed

### 4.5 Flat Payload for Agent Memories (Qdrant)

```json
{
  "action_type": "submit_indexing_batch",
  "agent_id": "seo_guardian",
  "source_domain": "seo",
  "applicable_to": ["seo_guardian", "content_publisher"],
  "timestamp": 1710400000,
  "result_status": "success",
  "confidence": 0.85,
  "pattern_summary": "Batch sizes above 30 cause rate limiting after 150 daily submissions",
  "evidence_count": 3,
  "cycle_phase": "LEARN",
  "decay_weight": 1.0
}
```

**Cross-agent retrieval**: At DECIDE phase, each agent queries `agent_learnings` with filter `applicable_to CONTAINS self.agent_id` + semantic similarity to current context.

---

## 5. Pillar 4: Self-Healing Systems

### 5.1 Graduated Response Framework (L1-L5)

Based on LogicMonitor's Agentic AI Maturity Model (March 2026):

| Level                | Trigger                              | Action                                             | Confidence  | Reversible |
| -------------------- | ------------------------------------ | -------------------------------------------------- | ----------- | ---------- |
| **L1: Alert**        | Any anomaly                          | Log + Telegram                                     | Any         | N/A        |
| **L2: Auto-restart** | Health check fails 3x                | Fly.io Machines API `POST /stop` → `/start`        | > 80%       | Yes        |
| **L3: Scale**        | Memory > 85% sustained               | Machines API: increase RAM temporarily             | > 90%       | Yes        |
| **L4: Rollback**     | Error rate > 5x baseline post-deploy | `fly deploy --image <last_known_good>`             | > 95%       | Yes        |
| **L5: Escalate**     | L2-L4 failed OR unknown pattern      | Pause all automation, context dump, human required | < threshold | N/A        |

### 5.2 Infrastructure Captain: Health Monitor

```python
# Health check tiers (from OneUptime best practices + adversarial review findings)
HEALTH_CHECKS = {
    "startup": {
        "endpoint": "/startupz",
        "check": "Initialization complete (graph compiled, DB pool created)",
        "action_on_fail": "Block traffic until ready (critical for 35s cold start)",
    },
    "liveness": {
        "endpoint": "/healthz",
        "interval": "60s",
        "action_on_fail": "L1_alert",
    },
    "readiness": {
        "endpoint": "/readyz",
        "check": "DB pool + Qdrant + Redis + memory < 1.5GB",
        "action_on_fail": "L1_alert, refuse traffic if memory > 1.5GB (OOM prevention buffer)",
    },
    "deep": {
        "endpoint": "/health/deep",
        "check": "Actual test queries per dependency",
        "action_on_fail": "L2_restart if 3x consecutive",
    },
}
```

**Memory budget in readiness probe**: On a 2GB container, refuse traffic above 1.5GB to prevent OOM. This gives ~500MB buffer for spikes before the OOM killer fires.

### 5.3 Stage-Gated Self-Healing (VIGIL Pattern)

From VIGIL (Dec 2025) — prevents infinite repair loops:

```
detect → eb_updated → diagnosed → prompt_done → diff_done
  │                                                    │
  │  Illegal transitions produce EXPLICIT ERRORS       │
  │  (not LLM improvisation)                          │
  └────────────────────────────────────────────────────┘
```

**Safety constraints**:

- `max_retries_per_task: 3`
- `cooldown_on_failure: 60s`
- `session_max_actions: 50`
- `session_max_runtime: 600s` (10 min)
- `on_limit_reached: write state to handoff.json, send Telegram alert, STOP`
- Core identity (config.yaml) is **immutable** during self-healing

### 5.4 Fly.io Machines API for Programmatic Control

The Infrastructure Captain uses the Machines REST API:

```python
import httpx

FLY_API = "https://api.machines.dev/v1"
FLY_TOKEN = os.environ["FLY_API_TOKEN"]
APP_NAME = "nuzantara-rag"

async def restart_machine(machine_id: str) -> bool:
    """L2 action: programmatic machine restart via Fly.io API."""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {FLY_TOKEN}"}
        # Stop
        await client.post(f"{FLY_API}/apps/{APP_NAME}/machines/{machine_id}/stop", headers=headers)
        # Wait for stopped state
        await client.get(f"{FLY_API}/apps/{APP_NAME}/machines/{machine_id}/wait?state=stopped", headers=headers)
        # Start
        await client.post(f"{FLY_API}/apps/{APP_NAME}/machines/{machine_id}/start", headers=headers)
        # Wait for started state
        resp = await client.get(f"{FLY_API}/apps/{APP_NAME}/machines/{machine_id}/wait?state=started", headers=headers)
        return resp.status_code == 200
```

### 5.5 PostgreSQL Monitoring (2GB Instance)

The two metrics that predict **every** PostgreSQL outage (Philip McClarence, March 2026):

1. **WAL accumulation**: `SELECT pg_size_pretty(sum(size)) FROM pg_ls_waldir();`
2. **Vacuum lag**: `SELECT relname, n_dead_tup FROM pg_stat_user_tables WHERE n_dead_tup > 1000;`

Additional for 2GB:

- Connection count: `SELECT count(*) FROM pg_stat_activity;` (max ~100 on 2GB)
- Pool exhaustion: `SELECT state, count(*) FROM pg_stat_activity GROUP BY state;`

### 5.6 Single Points of Failure — Degraded Mode Map

_Integrated from adversarial architecture review (ChatGPT/Kimi findings)._

| SPOF                                | Detection                            | Degraded Mode                                               | Recovery                                      |
| ----------------------------------- | ------------------------------------ | ----------------------------------------------------------- | --------------------------------------------- |
| **Qdrant down**                     | `/readyz` check fails for Qdrant     | Fall back to PostgreSQL full-text search (`pg_trgm`)        | L2: auto-restart Qdrant container             |
| **PostgreSQL down**                 | Connection pool exhaustion / timeout | Return cached responses (Redis), refuse writes              | L2: auto-restart + L5: escalate if persistent |
| **Redis down**                      | PING timeout                         | Skip cache layer, direct DB queries (slower but functional) | L2: auto-restart                              |
| **LLM API down**                    | HTTP 5xx or timeout from provider    | Queue requests, return "service temporarily limited"        | L1: alert, wait for provider recovery         |
| **Fly.io region outage**            | External health check from Air fails | Air standby cron jobs activate (4 business jobs)            | Documented in Pro-Air Orchestration           |
| **OpenClaw crash**                  | Watchdog (`ai.openclaw.watchdog`)    | Cron jobs pause, Telegram alert                             | Watchdog auto-restarts within 60s             |
| **Agent graph compilation failure** | Exception in `StateGraph.compile()`  | Fall back to linear chain (sequential function calls)       | L1: alert + investigate                       |

---

## 6. The Six Macro Areas — Enhanced

### G1: CRM & Client Operations

| Commander            | Captains                                                      | Autonomy                  |
| -------------------- | ------------------------------------------------------------- | ------------------------- |
| **Client Intake**    | Lead scorer, Onboarding trigger, Drive folder creator         | L3 (auto + confirm)       |
| **Practice Manager** | Renewal tracker, Document reminder, Escalation handler        | L3                        |
| **Compliance Watch** | Expiry scanner, KITAS deadline checker, Tax filing reminder   | L4 (auto, alert critical) |
| **Client Health**    | Churn predictor, Re-engagement trigger, Satisfaction surveyor | L3                        |
| **Portal Sync**      | Profile updater, Document ingester, Timeline builder          | L2 (supervised)           |

**Cross-domain value**: Compliance Watch → publishes `{compliance_alert}` events → Comms Commander sends WhatsApp reminder. Client Health → publishes `{churn_risk}` → CRM Intake triggers re-engagement journey.

### G2: Intelligence & Knowledge

| Commander            | Captains                                                         | Autonomy |
| -------------------- | ---------------------------------------------------------------- | -------- |
| **RAG Orchestrator** | Query router, Context retriever, Answer synthesizer              | L4       |
| **Knowledge Graph**  | Entity extractor, Relation builder, Graph traverser              | L3       |
| **Intel Gatherer**   | Unified scraper, News enricher, Regulatory monitor               | L4       |
| **Legal Analyst**    | Legal doc ingester, Regulation classifier, Compliance mapper     | L3       |
| **Memory Curator**   | Episodic consolidator, Semantic extractor, Cross-agent publisher | L4       |

**Cross-domain value**: Intel Gatherer → publishes `{regulation_change}` → Legal Analyst classifies impact → CRM Compliance Watch alerts affected clients.

### G3: Content & Media

| Commander            | Captains                                           | Autonomy          |
| -------------------- | -------------------------------------------------- | ----------------- |
| **Content Creator**  | Article composer, Image generator, SEO optimizer   | L3                |
| **Distribution**     | Blog publisher, Newsletter builder, Social poster  | L3                |
| **Editorial Review** | Quality checker, Fact validator, Tone analyzer     | L2 (human review) |
| **Media Manager**    | Asset uploader, Image optimizer, Audio transcriber | L4                |

**Cross-domain value**: SEO Guardian → publishes `{keyword_opportunity}` → Content Creator generates article brief → Editorial Review validates → Distribution publishes → SEO Guardian submits to indexing.

### G4: SEO & Growth (V1 IMPLEMENTED — 5-phase loop, V2 adds VALIDATE gate)

| Commander               | Captains                                                     | Autonomy |
| ----------------------- | ------------------------------------------------------------ | -------- |
| **SEO Guardian** (live) | OBSERVE+DECIDE+ACT agent                                     | L4       |
| **Indexing Commander**  | KBLI submitter, Articles submitter, Coverage monitor         | L4       |
| **CTR Optimizer**       | Meta description updater, Title optimizer, Schema enhancer   | L3       |
| **Technical SEO**       | Sitemap validator, Core Web Vitals checker, Redirect manager | L3       |
| **Analytics**           | GSC reporter, GA4 tracker, Ranking monitor                   | L4       |

### G5: Communications & Outreach

| Commander            | Captains                                                 | Autonomy |
| -------------------- | -------------------------------------------------------- | -------- |
| **WhatsApp Agent**   | Context builder, Onboarding detector, Response handler   | L3       |
| **Telegram Agent**   | Alert dispatcher, Report formatter, Command handler      | L4       |
| **Email Agent**      | Composer, Template selector, Send scheduler              | L3       |
| **Social Monitor**   | Twitter/X listener, Instagram handler, Sentiment tracker | L3       |
| **Drive/Sheets Ops** | File organizer, Sheet updater, Template filler           | L4       |

**Cross-domain value**: CRM Client Health → publishes `{birthday_greeting}` → WhatsApp Agent sends personalized message. Intel Gatherer → publishes `{breaking_regulation}` → Telegram Agent alerts team.

### G6: Infrastructure & DevOps

| Commander             | Captains                                                         | Autonomy |
| --------------------- | ---------------------------------------------------------------- | -------- |
| **Health Monitor**    | Fly.io checker, PostgreSQL monitor, Qdrant monitor, Redis pinger | L4       |
| **Code Quality**      | Linter, Type checker, Test runner, Auto-fixer                    | L4       |
| **Deployment**        | Readiness checker, Rolling deployer, Rollback handler            | L3       |
| **Backup & Recovery** | PG dumper, Restore verifier, Tigris uploader                     | L4       |
| **Security**          | Dep auditor, Vulnerability scanner, Secret detector              | L3       |

**Cross-domain value**: Health Monitor detects Qdrant memory pressure → auto-triggers scalar quantization on largest collection. Code Quality finds broken test → Auto-fixer generates patch → Deployment handles rollout.

---

## 7. Implementation Roadmap

### Phase 0: Foundation (Current State — DONE)

- [x] SEO Guardian v1.0 (OBSERVE→DECIDE→ACT→MEASURE→LEARN)
- [x] 3 OpenClaw cron jobs (daily observe, daily measure, weekly learn)
- [x] 41 unit tests
- [x] File-based state (config.yaml, state.json, corrections.jsonl, memory.jsonl, patterns.json)

### Phase 1: Validation Layer + Concurrency Safeguards (Next)

- [ ] Scale Fly.io nuzantara-rag to 2GB RAM (current allocation)
- [ ] Add VALIDATE gate (Gate 1-3) to SEO Guardian (Pydantic ActionPlan model)
- [ ] Add Gate 0: Data Sanity Validator (pre-DECIDE baseline comparison)
- [ ] File I/O safety: `fcntl.flock` + atomic swap for state.json
- [ ] Length-capping LangGraph state reducers
- [ ] Implement VETO audit trail (VetoRecord dataclass)
- [ ] Add `zantara_trace_id` (UUID) for cross-agent observability

### Phase 2: CRM General (G1) — Revenue-Critical, Best Testing Ground

- [ ] Client Health Commander (upgrade existing cron to LangGraph agent)
- [ ] Compliance Watch Commander
- [ ] Earned autonomy tracking (trust_modifier from LEARN phase)
- **Why G1 first**: 984 clients = immediate ROI. Existing deterministic cron → autonomous agent.

### Phase 3: Intelligence General (G2) + Event Bus

- [ ] Intel Gatherer Commander (upgrade bali-intel-scraper cron)
- [ ] Memory Curator Commander (JSONL → Qdrant consolidation)
- [ ] Create `agent_events` PostgreSQL table (just-in-time: G2 broadcasts to G1)
- [ ] Scale to performance-1x 2GB if monitoring shows CPU pressure
- **Why event bus here**: First cross-domain flow: G2 intel → G1 compliance alerts.

### Phase 4: Content General (G3) + Comms General (G5)

- [ ] Content Creator Commander
- [ ] SEO→Content event flow (keyword opportunity → article)
- [ ] WhatsApp/Telegram agent upgrade

### Phase 5: Infrastructure General (G6)

- [ ] Health Monitor Commander (Fly.io Machines API integration)
- [ ] Code Quality Commander (upgrade existing nightly cron to LangGraph)
- [ ] Graduated response L1-L5
- **Why G6 last**: Stable bash scripts work fine. AI infra monitoring only justified when AI fleet is large enough.

### Phase 6: General-of-Generals (Supreme Command)

- [ ] Weekly coordination across all 6 Generals
- [ ] Cross-domain pattern learning
- [ ] Autonomy graduation tracking
- **Note**: This phase is intentionally under-specified. It depends on learnings from Phases 1-5 and will require its own dedicated spec before implementation.

---

## 8. Constraints & Safety Checklist

| Constraint                | Enforcement                                                                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fly.io RAM scaling        | Phase 0-2: 2GB shared-cpu-2x (current). Phase 3+: scale up only if monitoring shows pressure.                                                             |
| Async-first               | `httpx` only, `ainvoke`/`astream` for LangGraph, `asyncpg` for checkpointing                                                                              |
| Python 3.11+              | Type hints required, `TypedDict` for graph state, `match` statements                                                                                      |
| No hardcoded secrets      | Environment variables only, `.secrets/` in `.gitignore`                                                                                                   |
| KBLI 2025 compliance      | Flat payload, `text-embedding-3-small` frozen, PricingTool for all prices                                                                                 |
| Zero Hallucination        | 3-gate validation pipeline, ABSTAIN below 0.15 confidence                                                                                                 |
| Audit trail               | Every VALIDATE decision logged with input_hash + rule_id + timestamp                                                                                      |
| Kill switch               | `state.json` → `paused: true` stops all Commanders                                                                                                        |
| Retry cap                 | `revision_count < 3` on every LangGraph retry loop                                                                                                        |
| Session limits            | `max_actions: 50`, `max_runtime: 600s` per Commander run                                                                                                  |
| Latency budget (p95 < 3s) | OBSERVE: ~500ms (API calls) → DECIDE: ~1000ms (LLM) → VALIDATE: ~50ms (Pydantic) → ACT: ~500ms (MCP tools) → buffer: ~950ms                               |
| MCP integration           | Captains call Soldiers via existing 96 MCP tools. No new tool framework — `mcporter call` for cron, direct Python import for in-process                   |
| Tool count per Captain    | Max 7 MCP tools per Captain. LLMs degrade with >7 tools. Group tightly by domain.                                                                         |
| Subgraph timeout          | Every Commander `.ainvoke()` wrapped in `asyncio.wait_for(..., timeout=300)`. Timeout returns `{"cycle_status": "timeout_aborted"}` gracefully.           |
| File I/O safety           | `fcntl.flock(LOCK_EX)` on all JSONL writes. Atomic swap (`write tmp → fsync → os.replace`) for state.json.                                                |
| Blocking I/O in async     | Use `asyncio.to_thread()` for `json.dump`, `yaml.safe_load`, `subprocess.run` inside async LangGraph nodes. Never block the event loop.                   |
| LangGraph state reducers  | All list fields use length-capping reducers (`(existing + new)[-10:]`), never unbounded `operator.add`.                                                   |
| Gate 0: Data Sanity       | Pre-DECIDE validator compares OBSERVE output against 7-day rolling baseline in state.json. Variance >50% → ABSTAIN + L1 alert. Never pass garbage to LLM. |
| Event bus atomicity       | Use `FOR UPDATE SKIP LOCKED` for event consumption. Nightly cleanup: `DELETE WHERE status='consumed' AND created_at < NOW() - INTERVAL '7 days'`.         |
| General routing           | Deterministic triage (regex + Pydantic), never LLM-based. LLM routing is the #1 cause of flaky multi-agent systems.                                       |
| Service injection         | Pass services via LangGraph `config["configurable"]`, never module-level setters. Module-level breaks under concurrency.                                  |

---

## References

### Multi-Agent Orchestration

1. LangGraph 1.0 GA — https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available
2. agent-harness.ai Framework Benchmark — https://agent-harness.ai/blog/agentic-ai-frameworks-2026
3. LangGraph Deep Dive (Mager) — https://www.mager.co/blog/2026-03-12-langgraph-deep-dive/
4. Clean State Architecture — https://medium.com/@ladvishal1985/everything-ive-learned-about-clean-state-architecture-in-langgraph
5. Durable Agents at Enterprise Scale — https://medium.com/@topuzas/architecting-durable-agents-for-enterprise-scale
6. LangGraph Subgraph Docs — https://docs.langchain.com/oss/python/langgraph/subgraphs
7. Subgraph State Issues — GitHub #4748, #4182, #3020, #3587
8. Multi-Agent Communication (MarkTechPost) — https://www.marktechpost.com/2026/03/01/how-to-design-a-production-grade-multi-agent-communication-system

### Deterministic Validation

9. 12-Factor Agents — https://github.com/humanlayer/12-factor-agents
10. STAC Hybrid Loops — https://stacresearch.com/news/stop-building-agent-chains-start-building-hybrid-loops/
11. Instructor Library — https://python.useinstructor.com/concepts/validation/
12. Verifiable Orchestrator — https://appliedingenuity.substack.com/p/the-verifiable-orchestrator
13. Agent RuleZ — https://medium.com/spillwave-solutions/agent-rulez-a-deterministic-policy-engine
14. Kiro Incident — https://particula.tech/blog/ai-agent-production-safety-kiro-incident
15. Vectara HHEM v2.1 — https://www.vectara.com/blog/hhem-2-1

### Agent Memory

16. Empirica Memory with Qdrant — https://dev.to/soulentheo/why-your-ai-agent-needs-memory-that-decays
17. IBM Trajectory-Informed Memory — https://arxiv.org/html/2603.10600v1
18. Position: Episodic Memory (Pink et al.) — https://arxiv.org/pdf/2502.06975
19. Paul Iusztin 4 Memory Types — https://www.decodingai.com/p/how-does-memory-for-ai-agents-work
20. Mem0 Architecture — https://www.researchgate.net/publication/391246545
21. Qdrant Resource Optimization — https://qdrant.tech/articles/vector-search-resource-optimization

### Self-Healing Systems

22. VIGIL Self-Healing Runtime — https://arxiv.org/abs/2512.07094
23. LogicMonitor Agentic Maturity Model — https://www.logicmonitor.com/blog/agentic-ai-maturity-model-itops
24. LLM Patching Architectures (Texas A&M) — https://arxiv.org/abs/2603.01257
25. Fly.io Machines API — https://fly.io/docs/machines/api/machines-resource/
26. PostgreSQL WAL/Vacuum Monitoring — https://medium.com/@philmcc/wal-and-vacuum-monitoring
27. GUARDRAILS.md — https://guardrails.md/
28. Feng et al. L1-L5 Autonomy — https://arxiv.org/abs/2506.12469
29. Earned Autonomy (Schachter) — https://kenschachter.substack.com/p/earned-autonomy

---

**Last Updated**: 2026-03-14
**Next Step**: Implementation Plan (Phase 1: Validation Layer + Event Bus)

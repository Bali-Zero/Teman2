# Nuzantara Autonomous Agents - V2 Enhanced Architecture

**Deep Research & Architecture Enhancement Document**  
**Version:** 2.0-Enhanced  
**Date:** 2026-03-14  
**Status:** Research Phase Complete - Implementation Ready

---

## Executive Summary

Questo documento presenta l'evoluzione dell'architettura "Military-Grade" degli Agenti Autonomi di Nuzantara, frutto di un'intensa fase di Deep Research su best practices SOTA (State of the Art) 2025-2026. L'architettura V2 è ottimizzata per:

- **Stack Nuzantara**: FastAPI, Qdrant, PostgreSQL, Fly.io (2GB RAM limit)
- **Constraint rigorosi**: Async-first, Python 3.11+, stateless containers
- **Zero Hallucination**: Evidence-based validation con soglie deterministiche
- **Self-Healing**: Auto-recovery su Fly.io senza intervento umano

### Key Architectural Decisions (V2)

| Decision                    | Rationale                                                        | SOTA Reference                               |
| --------------------------- | ---------------------------------------------------------------- | -------------------------------------------- |
| **LangGraph over CrewAI**   | Explicit state control, checkpointing, deterministic graphs      | Stripe ($6B recovered), Microsoft Healthcare |
| **Pydantic v2 Strict Mode** | Runtime validation, AST parsing, model_validator                 | ACL 2025 findings on structured generation   |
| **Qdrant Flat Payload**     | 2-3x faster queries, 40% less memory vs Weaviate                 | Benchmark 1M vectors, 768 dims               |
| **Hierarchical Memory**     | 5-layer memory (Working→Semantic→Episodic→Relational→Procedural) | AgentOS architecture 2026                    |
| **Fly.io Native Health**    | Rolling deploys + machine_checks + auto-restart                  | Fly.io blueprints 2025                       |

---

## 1. Multi-Agent Orchestration: LangGraph vs Alternatives

### 1.1 Comparative Analysis

```
┌─────────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│    Dimension    │  LangGraph  │   CrewAI    │   AutoGen   │   OpenAI    │
│                 │             │             │             │    SDK      │
├─────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ Orchestration   │ Graph-based │ Role-based  │Conversational│  Handoffs   │
│ State Persistence│✅ Built-in  │ ❌ Limited  │ ❌ In-memory │ ⚠️ Context  │
│ Checkpointing   │ ✅ Time-travel│ ❌ No     │ ❌ No        │ ❌ No       │
│ Async Support   │ ✅ Native   │ ⚠️ Partial  │ ⚠️ Partial   │ ✅ Yes      │
│ Model Agnostic  │ ✅ Yes      │ ✅ Yes      │ ✅ Yes       │ ❌ OpenAI   │
│ Production Ready│ ✅ Highest  │ ⚠️ Medium   │ ⚠️ Medium    │ ✅ High     │
│ Learning Curve  │ Medium      │ Low         │ Medium       │ Low         │
│ Streaming       │ Per-node    │ Limited     │ Limited      │ Full        │
│ Debuggability   │ Graph viz   │ Logs only   │ Chat logs    │ Traces      │
│ Nuzantara Fit   │ ✅ OPTIMAL  │ ⚠️ Rigid    │ ⚠️ Chatty    │ ❌ Vendor   │
└─────────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

### 1.2 Why LangGraph for Nuzantara

**Evidence from Production:**

- **Stripe**: $6 billion in recovered payments (2024), 60% YoY improvement in retry success
- **Microsoft Healthcare**: Hours of specialist prep → minutes via multi-agent coordination
- **LangGraph Taxonomy** (2025): "Graph-based finite-state orchestration supporting cycles, branching, and multi-turn control with explicit runtime semantics"

**Critical Advantages for Nuzantara:**

1. **Deterministic State Management**

   ```python
   # TypedDict + Reducers = Predictable state transitions
   class AgentState(TypedDict):
       messages: Annotated[list, add_messages]  # Reducer function
       documents: list[str]  # Simple field
       confidence: Annotated[float, max]  # Custom reducer
   ```

   - Elimina "silent data loss" in workflow complessi
   - Supporta checkpointing per recovery post-crash

2. **Explicit Control Flow**
   - Ogni nodo è una funzione pura (input: state, output: state)
   - Edges condizionali per branching logico
   - Cycles supportati nativamente (ReAct loops)

3. **Production Features**
   - **Time-travel debugging**: Ripristino stato a qualsiasi punto
   - **Parallel branches**: Esecuzione concorrente di sub-agent
   - **Error boundaries**: Retry/fallback per nodo

4. **Fly.io Optimization**
   - Stateless by design (state in checkpoint, non in-memory)
   - Compatibile con 2GB RAM limit (grafo compilato, non interprete)

### 1.3 Bottleneck Analysis

| Bottleneck       | Mitigation            | Nuzantara Implementation         |
| ---------------- | --------------------- | -------------------------------- |
| Graph complexity | Modular subgraphs     | One subgraph per General         |
| State size       | Selective persistence | Only delta changes checkpointed  |
| Cold start       | Pre-compiled graphs   | Graph compilation at deploy time |
| Latency          | Parallel execution    | Async nodes with gather()        |

---

## 2. Deterministic Validation (The Zantara Order V2)

### 2.1 Evidence Scoring: From Research to Practice

**SOTA Research 2025:**

- **CONFACTCHECK** (ACL 2025): Kolmogorov-Smirnov test su token probabilities per detect hallucination
- **FinCH-ZK** (Amazon Science): Cross-model consistency con threshold τ=0.33/0.67
- **SelfCheckGPT**: Self-consistency con multiple samples

**Nuzantara Evidence Thresholds (Raffinate):**

```python
# Basato su ricerca CONFACTCHECK e requirement legali indonesiani
EVIDENCE_THRESHOLDS = {
    "ABSTAIN": 0.15,        # < 0.15: Rifiuto automatico
    "CAUTIOUS": 0.60,       # 0.15-0.60: Risposta con disclaimer
    "NORMAL": 0.75,         # 0.60-0.75: Risposta standard
    "CONFIDENT": 0.90,      # 0.75-0.90: Alta confidenza
    "CERTIFIED": 0.98,      # > 0.90: Solo per KBLI verificato
}
```

### 2.2 Pydantic v2 Strict Validation

**Pattern Ottimale per LLM Output:**

```python
from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Literal, Annotated

class KBLIValidationResult(BaseModel):
    """Esempio: Validazione output KBLI con constraint rigorosi."""

    kbli_code: Annotated[str, Field(pattern=r'^\d{5}$')]  # Strict regex
    title_id: str = Field(min_length=10, max_length=200)
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["official", "inferred", "ambiguous"]
    requires_disclaimer: bool

    @field_validator('kbli_code')
    @classmethod
    def validate_kbli_format(cls, v: str) -> str:
        """Validazione formato KBLI 2025."""
        if not v.isdigit() or len(v) != 5:
            raise ValueError(f"KBLI code must be 5 digits, got {v}")
        return v

    @model_validator(mode='after')
    def validate_confidence_consistency(self):
        """Cross-field validation: confidence vs source."""
        if self.source == "official" and self.confidence < 0.95:
            raise ValueError("Official sources must have confidence >= 0.95")
        if self.confidence < 0.60 and not self.requires_disclaimer:
            raise ValueError("Low confidence requires disclaimer")
        return self
```

**Vantaggi per Nuzantara:**

- **AST Parsing**: Validazione strutturale prima dell'esecuzione
- **Type Coercion**: Conversione automatica tipi (str → int dove sicuro)
- **Error Context**: Messaggi errore precisi per debugging
- **Performance**: Rust core di Pydantic v2 ~10x più veloce di v1

### 2.3 Zero Hallucination Protocol

**Layered Validation (3 Livelli):**

```
Level 1: Schema Validation (Pydantic)
    ↓ FAIL → Retry with stricter prompt

Level 2: Semantic Validation (Embedding Similarity)
    - Query: "What is KITAS?"
    - Response embedding vs KBLI corpus
    - Threshold: cosine_similarity > 0.75
    ↓ FAIL → Fallback to abstain

Level 3: Fact Verification (Token Probabilities)
    - KS-test su top-5 token probabilities
    - p-value < 0.05 → confident generation
    - p-value >= 0.05 → potential hallucination
    ↓ FAIL → Human escalation
```

---

## 3. Agent Memory & Qdrant Optimization

### 3.1 Memory Architecture: The 5-Layer Model

Basato su ricerca AgentOS 2026 e requisiti Nuzantara:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT MEMORY HIERARCHY                       │
├─────────────────┬─────────────────┬─────────────────────────────┤
│    Layer        │   Storage       │   TTL / Scope               │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Working Memory  │ Context Window  │ Session (ephemeral)         │
│                 │ (LLM tokens)    │ ~4K-128K tokens             │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Semantic Memory │ Qdrant          │ Long-term (permanent)       │
│                 │ Vector DB       │ Knowledge base              │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Episodic Memory │ PostgreSQL      │ 90 days                     │
│                 │ Relational      │ Past interactions           │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Relational Mem  │ Knowledge Graph │ Permanent                   │
│                 │ (Neo4j/NetworkX)│ Entity relationships        │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Procedural Mem  │ Code/Config     │ Versioned                   │
│                 │ (Git/DB)        │ Skills & workflows          │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### 3.2 Qdrant Flat Payload Strategy

**Best Practice 2025 (Vietato nested JSON):**

```python
# ❌ WRONG: Nested payload (anti-pattern per AGENTS.md)
{
    "kbli": {
        "code": "47911",
        "title": "...",
        "details": { "description": "..." }  # Nested!
    }
}

# ✅ CORRECT: Flat payload structure
{
    "kbli_code": "47911",
    "kbli_title_id": "Perdagangan Eceran...",
    "kbli_title_en": "Retail Sale...",
    "kbli_description": "...",
    "kbli_category": "G",
    "kbli_section": "Perdagangan",
    "vector_collection": "kbli_2025",
    "last_updated": "2025-01-15T00:00:00Z",
    "source_authority": "BPS",
    "confidence_score": 0.98
}
```

**Performance Benchmarks (1M vectors, 768 dims):**

| Metric         | Qdrant       | Weaviate | Nuzantara Choice           |
| -------------- | ------------ | -------- | -------------------------- |
| Query Latency  | **7ms**      | 15ms     | ✅ Qdrant 2x faster        |
| Filtered Query | **10ms**     | 25ms     | ✅ Qdrant 2.5x faster      |
| Index Build    | **8min**     | 12min    | ✅ Qdrant 1.5x faster      |
| Memory Usage   | **5GB**      | 9GB      | ✅ Qdrant 40% less         |
| Filtering      | **Superior** | Good     | ✅ Complex boolean queries |

### 3.3 Retrieval Strategy for KBLI Intelligence

**Hybrid Search Pattern:**

```python
# Step 1: Vector similarity (semantic)
vector_results = qdrant.search(
    collection="kbli_2025",
    vector=query_embedding,
    limit=20,
    with_payload=True
)

# Step 2: Payload filtering (structured)
filtered = qdrant.search(
    collection="kbli_2025",
    vector=query_embedding,
    query_filter={
        "must": [
            {"key": "kbli_category", "match": {"value": "G"}},
            {"key": "foreign_ownership", "range": {"gte": 0.51}}
        ]
    },
    limit=10
)

# Step 3: Reranking by confidence
reranked = sorted(
    filtered,
    key=lambda x: x.payload["confidence_score"] * x.score,
    reverse=True
)[:5]
```

---

## 4. Self-Healing on Fly.io

### 4.1 Fly.io Deployment Strategies

**Production-Ready Configuration:**

```toml
# fly.toml - Nuzantara Agent Deployment
[deploy]
  strategy = "rolling"  # or "canary" for risky changes
  max_unavailable = 1   # Keep at least N-1 machines healthy

[[services]]
  internal_port = 8000
  protocol = "tcp"

  # Health checks for traffic routing
  [[services.http_checks]]
    interval = "10s"
    timeout = "5s"
    grace_period = "30s"
    method = "get"
    path = "/health"
    protocol = "http"

  # Machine checks for deployment validation
  [[services.machine_checks]]
    command = ["/bin/bash", "-c", "curl -f http://$FLY_TEST_MACHINE_IP:8000/ready"]
    interval = "30s"
    timeout = "5s"

[checks]
  # Top-level checks for observability (no traffic impact)
  [checks.agent_health]
    port = 8000
    type = "http"
    interval = "30s"
    timeout = "10s"
    path = "/health"
```

### 4.2 Self-Healing Mechanisms

**Liveness → Readiness → Startup Probes:**

```python
# FastAPI health endpoints per pattern Kubernetes/Fly.io
from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI()

class HealthStatus(BaseModel):
    status: str
    version: str
    checks: dict

@app.get("/healthz", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """Liveness: Is the process running?"""
    return {"status": "alive"}

@app.get("/readyz", status_code=status.HTTP_200_OK)
async def readiness_probe():
    """Readiness: Is the app ready to serve traffic?"""
    checks = {
        "database": await check_db_connection(),
        "qdrant": await check_qdrant_connection(),
        "memory_usage": get_memory_usage() < 1.5,  # < 1.5GB
    }

    if not all(checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"not_ready": [k for k, v in checks.items() if not v]}
        )

    return {"status": "ready", "checks": checks}

@app.get("/startupz", status_code=status.HTTP_200_OK)
async def startup_probe():
    """Startup: Has the app finished initializing?"""
    # Check heavy initialization tasks
    return {"status": "initialized"}
```

### 4.3 Auto-Recovery for Agents

**Captain-Level Self-Healing:**

```python
# Pattern: Agent che monitora e ripara se stesso
import asyncio
import logging
from datetime import datetime, timedelta

class SelfHealingAgent:
    """Agent con capability di auto-diagnosi e recovery."""

    def __init__(self):
        self.failure_count = 0
        self.max_failures = 3
        self.last_health_check = datetime.now()
        self.logger = logging.getLogger("agent.self_heal")

    async def health_monitor(self):
        """Loop continuo di health monitoring."""
        while True:
            try:
                is_healthy = await self.run_diagnostics()

                if not is_healthy:
                    self.failure_count += 1
                    self.logger.warning(f"Health check failed ({self.failure_count}/{self.max_failures})")

                    if self.failure_count >= self.max_failures:
                        await self.attempt_recovery()
                else:
                    if self.failure_count > 0:
                        self.logger.info("Health restored, resetting failure count")
                    self.failure_count = 0

            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")

            await asyncio.sleep(30)  # Check ogni 30s

    async def run_diagnostics(self) -> bool:
        """Diagnostic suite completo."""
        diagnostics = [
            self.check_memory_usage(),      # < 1.8GB
            self.check_db_connection(),     # PostgreSQL responsive
            self.check_qdrant_connection(), # Vector DB reachable
            self.check_disk_space(),        # > 100MB free
            self.check_recent_errors(),     # < 10 errors/min
        ]
        results = await asyncio.gather(*diagnostics, return_exceptions=True)
        return all(r is True for r in results if not isinstance(r, Exception))

    async def attempt_recovery(self):
        """Tentativi di auto-recovery escalanti."""
        recovery_steps = [
            self.clear_caches,
            self.reconnect_databases,
            self.reload_configuration,
            self.restart_subsystems,
        ]

        for step in recovery_steps:
            try:
                self.logger.info(f"Attempting recovery: {step.__name__}")
                await step()

                # Verifica se il recovery ha funzionato
                if await self.run_diagnostics():
                    self.logger.info(f"Recovery successful via {step.__name__}")
                    self.failure_count = 0
                    return

            except Exception as e:
                self.logger.error(f"Recovery step failed: {e}")
                continue

        # Tutti i recovery falliti → Escalation
        self.logger.critical("All recovery attempts failed, escalating to human")
        await self.alert_human_operator()
```

---

## 5. Contextual Alignment: Nuzantara Golden Rules

### 5.1 Rule-by-Rule Compliance

| Golden Rule              | SOTA Alignment         | Implementation                 |
| ------------------------ | ---------------------- | ------------------------------ |
| **Async-First**          | LangGraph native async | `async def node_func(state)`   |
| **No Blocking I/O**      | httpx per HTTP         | `AsyncClient(timeout=30)`      |
| **Type Hints**           | Pydantic v2 + mypy     | `def func() -> AgentState`     |
| **No Hardcoded Secrets** | Fly.io secrets         | `env = os.environ["KEY"]`      |
| **Absolute Imports**     | Python best practice   | `from backend.core import ...` |
| **Qdrant Flat Payload**  | Qdrant 2025 guidelines | No nested JSON                 |
| **2GB RAM Limit**        | Stateless design       | Checkpoint to DB, not memory   |

### 5.2 KBLI 2025 Legal Compliance

**Constraint Specifici:**

- KBLI codes sono immutabili (BPS authority)
- Foreign ownership % varia per settore (Negative List)
- Le informazioni legali richiedono disclaimer

**Validazione Aggiuntiva:**

```python
KBLI_VALIDATION_RULES = {
    "code_format": r"^\d{5}$",  # Strict 5 digits
    "ownership_check": "cross_reference_negative_list",
    "required_disclaimer": "verify_with_bkpm",
    "max_confidence": 0.98,  # Never 100%
    "source_authority": "BPS Official 2025",
}
```

---

## 6. Architecture Enhancement Synthesis

### 6.1 V1 vs V2 Comparison

```
┌─────────────────────────────────────────────────────────────────────┐
│                     V1 → V2 ENHANCEMENTS                            │
├────────────────────────────────┬────────────────────────────────────┤
│           V1                   │              V2                    │
├────────────────────────────────┼────────────────────────────────────┤
│ Generic validator              │ Pydantic v2 strict mode            │
│ Simple threshold (0.6/0.85)    │ 5-tier evidence scoring            │
│ In-memory state                │ Checkpointed state (LangGraph)     │
│ Nested Qdrant payload          │ Flat payload (best practice)       │
│ Manual health checks           │ Self-healing probes                │
│ CrewAI role-based              │ LangGraph graph-based              │
│ Single-layer memory            │ 5-layer memory hierarchy           │
│ Sync fallback                  │ Full async with error boundaries   │
│ Generic retry                  │ Exponential backoff + circuit break│
└────────────────────────────────┴────────────────────────────────────┘
```

### 6.2 Single Points of Failure & Mitigations

| SPOF                   | Risk                        | Mitigation                                      |
| ---------------------- | --------------------------- | ----------------------------------------------- |
| **LangGraph Compiler** | Graph compilation failure   | Pre-compile at deploy; fallback to linear chain |
| **Qdrant Connection**  | Vector search unavailable   | Fallback to PostgreSQL full-text; cache layer   |
| **General Agent**      | Strategic decision deadlock | Timeout 30s + auto-escalation to human          |
| **Checkpoint DB**      | State loss on crash         | Async replication; local cache 30s TTL          |
| **Fly.io Region**      | Regional outage             | Multi-region deploy with DNS failover           |

### 6.3 Performance Optimizations

**Per Fly.io 2GB RAM Constraint:**

```python
# Ottimizzazione memoria LangGraph
from langgraph.checkpoint.sqlite import SqliteSaver

# Usa SQLite locale per checkpoint (non Redis)
checkpointer = SqliteSaver.from_conn_string(":memory:")  # In-memory SQLite

# Oppure PostgreSQL per persistence cross-machine
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver(conn_string=os.environ["DATABASE_URL"])

# Ottimizzazione Qdrant
QDRANT_CONFIG = {
    "optimizers_config": {
        "memmap_threshold": 50000,  # Sotto 2GB RAM
        "indexing_threshold": 10000,
    },
    "hnsw_config": {
        "ef_construct": 100,  # Bilanciato qualità/velocità
        "m": 16,              # Dimensione grafo
    }
}
```

---

## 7. V2 Architecture Schema

### 7.1 High-Level Diagram

```mermaid
graph TB
    subgraph "User Interface"
        UI[Web/Mobile]
        API[FastAPI Gateway]
    end

    subgraph "Command Structure"
        CS[Command Router]
        CM[Collective Memory]
    end

    subgraph "The Five Generals (LangGraph)"
        G1[Legal General<br/>StateGraph]
        G2[Corporate General<br/>StateGraph]
        G3[Tax General<br/>StateGraph]
        G4[Technical General<br/>StateGraph]
        G5[Intelligence General<br/>StateGraph]
    end

    subgraph "Deterministic Safety Layer"
        PV[Pydantic v2 Validator]
        ES[Evidence Scorer]
        SE[Safety Envelope]
    end

    subgraph "Memory & State"
        WM[Working Memory<br/>Context Window]
        SM[Semantic Memory<br/>Qdrant]
        EM[Episodic Memory<br/>PostgreSQL]
        PM[Procedural Memory<br/>Git/Config]
    end

    subgraph "Infrastructure (Fly.io)"
        HC[Health Checks]
        SH[Self-Healing]
        ZDD[Zero-Downtime Deploy]
    end

    UI --> API
    API --> CS
    CS --> G1
    CS --> G2
    CS --> G3
    CS --> G4
    CS --> G5

    G1 -.->|checkpoint| EM
    G2 -.->|checkpoint| EM

    G1 --> PV
    G2 --> PV
    G3 --> PV

    PV --> ES
    ES --> SE

    SE -.->|insights| CM

    G1 -.->|query| SM
    SM -.->|context| G1

    G1 -.->|skills| PM

    API -.->|health| HC
    HC -.->|trigger| SH
    SH -.->|restart| G1
```

### 7.2 Data Flow: KITAS Renewal Query

```
User: "Renew KITAS Work"
    ↓
FastAPI Gateway (async)
    ↓
Command Router → Score Generals → Legal General (0.92)
    ↓
LangGraph StateGraph (Legal General)
    ├── Node: Classify Query (deterministic)
    ├── Node: Delegate to Visa Commander
    │       └── SubGraph: KITAS Work Captain
    │           ├── Node: Check Documents (tool)
    │           ├── Node: Validate Eligibility (LLM)
    │           └── Node: Generate Roadmap (LLM)
    ├── Node: Synthesize Results
    └── Node: Safety Validation (Pydantic v2)
            ├── Schema Validation
            ├── Evidence Scoring (KS-test)
            └── Disclaimer Check
    ↓
Safety Envelope (validated_output)
    ↓
Response → User
```

---

## 8. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)

- [ ] Setup LangGraph with checkpointing (PostgreSQL)
- [ ] Implement Pydantic v2 validators for all domains
- [ ] Configure Qdrant flat payload collections
- [ ] Deploy Fly.io health checks

### Phase 2: The Five Generals (Week 3-4)

- [ ] Implement LegalImmigrationGeneral (StateGraph)
- [ ] Implement CorporateSetupGeneral
- [ ] Implement TaxComplianceGeneral
- [ ] Implement TechnicalEngineGeneral
- [ ] Implement IntelligenceGeneral

### Phase 3: Safety Layer (Week 5-6)

- [ ] Integrate Evidence Scoring (KS-test)
- [ ] Implement 5-tier confidence thresholds
- [ ] Add human escalation protocols
- [ ] Testing: Zero hallucination target

### Phase 4: Memory & Self-Healing (Week 7-8)

- [ ] Implement 5-layer memory hierarchy
- [ ] Add self-healing health monitors
- [ ] Configure auto-recovery procedures
- [ ] Load testing on Fly.io

### Phase 5: Production Readiness (Week 9-10)

- [ ] Integration tests with existing Nuzantara
- [ ] Performance benchmarking (< 3s p95)
- [ ] Documentation & runbooks
- [ ] Gradual rollout (canary)

---

## 9. Conclusion

L'architettura V2 Enhanced rappresenta un salto qualitativo rispetto alla V1, fondato su:

1. **LangGraph**: Produzione-ready con checkpointing e deterministic control flow
2. **Pydantic v2**: Validazione rigorosa con strict mode e AST parsing
3. **Evidence Scoring**: Protocollo zero-hallucination basato su ricerca SOTA
4. **Qdrant Flat Payload**: Performance ottimizzate per constraint Fly.io
5. **Self-Healing**: Auto-recovery integrato nel deployment Fly.io

### Key Metrics Target

| Metric              | Target  | Measurement             |
| ------------------- | ------- | ----------------------- |
| Query Latency (p95) | < 3s    | End-to-end response     |
| Hallucination Rate  | < 1%    | Automated evaluation    |
| Uptime              | 99.9%   | Fly.io health checks    |
| Memory Usage        | < 1.8GB | Container limit         |
| Recovery Time       | < 30s   | Self-healing activation |

**Prossimo Step:** Implementazione Phase 1 (Core Infrastructure).

---

## References

1. LangGraph Taxonomy (2025) - TechRxiv
2. CONFACTCHECK - ACL 2025 Hallucination Detection
3. FinCH-ZK - Amazon Science Cross-Model Consistency
4. Qdrant Performance Benchmarks 2025
5. Fly.io Deployment Blueprints 2025
6. AgentOS Memory Architecture 2026
7. Stripe Multi-Agent Case Study (2024)
8. Microsoft Healthcare Agent Orchestration

---

_Document Version: 2.0-Enhanced_  
_Classification: Internal - Nuzantara Architecture_  
_Author: Senior AI Architect_

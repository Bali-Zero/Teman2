# GraphRAG Evolution Architecture — Nuzantara v6.0

**Date:** 2026-04-03
**Author:** Bali Zero AI Team
**Status:** DESIGN PHASE — 2 rounds of 4-agent validation (NB-1 + Gemini + Codex + DeepSeek)
**Scope:** 5 workstreams, 0 downtime migration, $0 infra cost increase

---

## MULTI-AGENT VALIDATION RESULTS (2026-04-03)

### Round 1: NB-1 Oracolo (codebase grounding)

Revealed **critical corrections**:

| #   | Original Claim                     | NB-1 Verdict                                            | Action Taken                                                                           |
| --- | ---------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 1   | KG: 56K nodes, 161K edges          | ❌ **Stale**: actual is **87,198 nodes, 210,354 edges** | Updated all references                                                                 |
| 2   | `ENABLE_KG_LANGGRAPH` flag         | ❌ NB-1 says absent                                     | **Verified in code**: exists at `orchestrator.py:200`. NB-1 snapshot predates addition |
| 3   | 16 Qdrant collections              | ⚠️ Registry has 8 canonical, manager defines 18         | Corrected to "18 defined, ~12 effective"                                               |
| 4   | Auto-expand from response text     | ❌ **DANGEROUS feedback loop**                          | **REDESIGNED**: extract from source chunks, NOT LLM output                             |
| 5   | Lazy subgraph loading saves memory | ❌ StateGraph compile = ~5MB, not bottleneck            | **REVISED**: focus on LLM client + connection pool optimization                        |
| 6   | Merge tiny Qdrant collections      | ⚠️ Breaks scalar quantization + brute-force scan        | **REVISED**: keep tiny collections, only merge non-hybrid duplicates                   |
| 7   | Replace ChatOpenAI with httpx      | ❌ Breaks LangChain `.ainvoke()` in KG nodes            | **REVISED**: keep LangChain for KG, optimize elsewhere                                 |

### Round 1: Gemini Redteam + Codex GPT-5.3 + DeepSeek R1

| #   | Finding                                                   | Source         | Action                                        |
| --- | --------------------------------------------------------- | -------------- | --------------------------------------------- |
| 8   | Auto-expansion race conditions on concurrent INSERT       | Gemini         | Quarantine pattern (staging tables)           |
| 9   | Write to quarantine graph, promote after validation       | Codex          | Implemented kg_nodes_staging/kg_edges_staging |
| 10  | Growth rate 30-50/day not 180 (regex recall 20-30%)       | DeepSeek       | Corrected estimates                           |
| 11  | PPh brackets wrong for PT PMA (flat 22%, not progressive) | Gemini         | Tax schema redesigned                         |
| 12  | Shadow mode for QueryPlanner + kill-switch                | Codex+DeepSeek | Dual-run for 2 weeks                          |
| 13  | source_collection orphans after Qdrant delete             | Gemini         | UPDATE before delete + rollback column        |

### Round 2: Gemini Redteam + DeepSeek R1

| #   | Finding                                                     | Source   | Action                               |
| --- | ----------------------------------------------------------- | -------- | ------------------------------------ |
| 14  | Dangling edges if node rate-limited but edge promoted       | Gemini   | Atomic promotion: nodes BEFORE edges |
| 15  | Fasilitas Pasal 31E: 11% effective for PMI <50B IDR         | Gemini   | Added to tax schema                  |
| 16  | UMKM 0.5% has time limits (3/4/7 years) + 500M exemption    | Gemini   | Added validity_period + threshold    |
| 17  | PTKP (non-taxable income) missing from tax schema           | Gemini   | Added PTKP node with TK/K variants   |
| 18  | Shadow mode must be async (not in critical path)            | Gemini   | Clarified as fire-and-forget         |
| 19  | 48h Qdrant monitoring insufficient → extend to 30 days      | DeepSeek | Extended with rollback column        |
| 20  | 75% precision too low for legal → risk-tiered (90/80/75)    | DeepSeek | Bumped to 85% overall, 90% high-risk |
| 21  | Staging tables need retention policy (prune after 30 days)  | DeepSeek | Auto-prune + alerting added          |
| 22  | Promotion validation: schema + referential + business logic | DeepSeek | 5-check validation pipeline          |

---

## 0. Executive Summary

Nuzantara's RAG pipeline currently operates as three loosely coupled systems:

1. **Vector Search** (Qdrant, 16 collections, ~93K docs)
2. **Knowledge Graph** (PostgreSQL, 56K nodes, 161K edges) — disabled on Fly.io (OOM)
3. **LangGraph KG Orchestrator** (5 nodes, 4 subgraphs) — `ENABLE_KG_LANGGRAPH=false` in prod

This document designs the **GraphRAG Evolution**: a unified pipeline where vector retrieval
and graph reasoning work as a single coordinated system, the KG grows organically from
user queries, and the whole thing runs within 2GB RAM on Fly.io.

### Target Metrics

| Metric                 | Current            | Target           | How                                                |
| ---------------------- | ------------------ | ---------------- | -------------------------------------------------- |
| Query latency (p95)    | ~4.5s              | <3.0s            | Unified planner eliminates redundant routing       |
| KG coverage            | 56K nodes (static) | +500 nodes/week  | Auto-expansion from high-confidence responses      |
| KG in prod             | ❌ Disabled (OOM)  | ✅ Active        | Lazy subgraph loading, no full graph in memory     |
| Qdrant collections     | 16 (fragmented)    | 5 (consolidated) | Merge small collections, keep large ones           |
| Evidence score         | 6-factor static    | Graph-augmented  | KG context boosts confidence scoring               |
| Property/Tax subgraphs | ❓ Incomplete      | ✅ Complete      | Data extraction pipeline from legal_unified_hybrid |

---

## 1. Current Architecture Analysis

### 1.1 Query Flow (AS-IS)

```
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│ OrchestratorCore.process_query()             │
│  orchestrator_core.py                        │
│                                              │
│  ┌─────────────────┐  ┌──────────────────┐   │
│  │ FAQ Cache Check  │  │ Semantic Cache   │   │
│  │ (Redis exact)    │  │ (Qdrant similar) │   │
│  └────────┬────────┘  └────────┬─────────┘   │
│           │ miss                │ miss         │
│           ▼                    ▼              │
│  ┌──────────────────────────────────────┐    │
│  │ PARALLEL: asyncio.gather()           │    │
│  │  ├── EntityExtractor (heuristic)     │    │
│  │  ├── KGEnhancedRetrieval (legacy)    │    │
│  │  └── KGLangGraphOrchestrator (OFF)   │    │
│  └────────────────┬─────────────────────┘    │
│                   ▼                           │
│  ┌──────────────────────────────────────┐    │
│  │ IntentClassifier → RoutingManager    │    │
│  │  → model tier (FLASH/PRO/DeepThink)  │    │
│  │  → AgentState (skip_rag, category)   │    │
│  └────────────────┬─────────────────────┘    │
│                   ▼                           │
│  ┌──────────────────────────────────────┐    │
│  │ ReasoningEngine (ReAct loop)         │    │
│  │  ├── Tool: vector_search             │    │
│  │  ├── Tool: get_pricing               │    │
│  │  ├── Tool: knowledge_graph           │    │
│  │  ├── Tool: team_knowledge            │    │
│  │  ├── Tool: calculator                │    │
│  │  └── Tool: timesheet                 │    │
│  └────────────────┬─────────────────────┘    │
│                   ▼                           │
│  ┌──────────────────────────────────────┐    │
│  │ EvidenceScoring + Policy Enforcement │    │
│  │  <0.15 ABSTAIN | 0.15-0.6 CAUTIOUS  │    │
│  │  >0.6 NORMAL                         │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

### 1.2 Problems Identified

| #   | Problem                           | Impact                                        | Root Cause                                                          |
| --- | --------------------------------- | --------------------------------------------- | ------------------------------------------------------------------- |
| P1  | KG disabled in prod               | No graph reasoning on Fly.io                  | Full graph load → OOM on 2GB                                        |
| P2  | Fragmented routing                | 3 classifiers run independently               | EntityExtractor + IntentClassifier + RoutingManager not coordinated |
| P3  | KG is static                      | 56K nodes from batch extraction, never grows  | No feedback loop from RAG responses to KG                           |
| P4  | 16 Qdrant collections             | Query routing complexity, some tiny (29 docs) | Historical accumulation, no consolidation                           |
| P5  | Property/Tax subgraphs incomplete | Graph traversal misses property/tax domains   | No extraction pipeline for these domains                            |
| P6  | Evidence scoring ignores graph    | High-confidence KG paths don't boost score    | Scoring uses only tool call heuristics                              |

### 1.3 Current KG Schema (PostgreSQL)

```sql
-- Migration 028 + 029 + 055 + 064
CREATE TABLE kg_nodes (
    entity_id        TEXT PRIMARY KEY,
    entity_type      TEXT NOT NULL,        -- kbli, biaya, pasal, dokumen, undang_undang, etc.
    name             TEXT NOT NULL,
    description      TEXT,
    properties       JSONB DEFAULT '{}',
    confidence       FLOAT DEFAULT 1.0,    -- ⚠️ Currently hardcoded 0.9
    source_collection TEXT,
    source_chunk_ids TEXT[],               -- Added in migration 029
    created_at       TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ
);

CREATE TABLE kg_edges (
    relationship_id    TEXT PRIMARY KEY,
    source_entity_id   TEXT REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
    target_entity_id   TEXT REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
    relationship_type  TEXT NOT NULL,       -- REQUIRES, PART_OF, REFERENCES, HAS_FEE, HAS_DURATION, etc.
    properties         JSONB DEFAULT '{}',
    confidence         FLOAT DEFAULT 1.0,
    source_collection  TEXT,
    source_chunk_ids   TEXT[],             -- Added in migration 029
    created_at         TIMESTAMPTZ
);

-- Indexes: entity_type, name, source/target, relationship_type, reverse traversal (064)
```

**Stats (NB-1 validated 2026-03-25):** 87,198 nodes × 210,354 edges = ~297K rows total. At ~500 bytes/row avg ≈ 149MB raw data.

### 1.4 Current Qdrant Collections

| Collection                    | Docs   | Priority | Purpose                    |
| ----------------------------- | ------ | -------- | -------------------------- |
| legal_unified_hybrid          | 47,959 | HIGH     | Main legal KB (BM25+Dense) |
| kbli_2025_final               | 8,886  | HIGH     | KBLI business codes        |
| zantara_books                 | 8,923  | MEDIUM   | Reference books            |
| training_conversations_hybrid | 2,898  | HIGH     | Conversation training data |
| visa_oracle                   | 1,612  | HIGH     | Visa/immigration docs      |
| legal_architect               | 5,041  | HIGH     | Legal structured docs      |
| legal_unified                 | 5,041  | HIGH     | Legal (non-hybrid, legacy) |
| tax_genius                    | 895    | HIGH     | Tax docs                   |
| tax_genius_hybrid             | 332    | HIGH     | Tax (hybrid)               |
| balizero_news                 | 175    | HIGH     | Intel articles             |
| bali_zero_pricing_hybrid      | 29     | HIGH     | Pricing data               |
| property_listings             | 29     | MEDIUM   | Property data              |
| property_knowledge            | 29     | MEDIUM   | Property KB                |
| bali_zero_team                | 22     | HIGH     | Team info                  |
| immigration_circulars         | 4      | HIGH     | Immigration circulars      |
| collective_memories           | 0      | HIGH     | User shared knowledge      |

**Total: ~81,875 documents across 16 collections** (some overlap between legacy and hybrid versions).

---

## 2. Unified Query Planner

### 2.1 Design: Replace 3 Classifiers with 1 Planner

The current pipeline runs EntityExtractor, IntentClassifier, and KGLangGraph routing
independently. The new **QueryPlanner** replaces all three with a single deterministic
decision tree that produces a **QueryPlan** — a structured execution plan consumed by
the orchestrator.

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│ QueryPlanner.plan(query, context)   │
│                                     │
│  Step 1: Entity extraction          │
│  Step 2: Domain classification      │
│  Step 3: Complexity assessment      │
│  Step 4: Generate QueryPlan         │
└─────────────┬───────────────────────┘
              │
              ▼
    QueryPlan {
      domain: "visa",
      entities: ["KITAS", "E28A"],
      complexity: "multi_hop",
      collections: ["visa_oracle", "legal_unified_hybrid"],
      kg_strategy: "subgraph_visa",
      model_tier: "FLASH",
      confidence_boost: 0.15,  // from KG path
      estimated_latency_ms: 2500
    }
              │
              ▼
┌─────────────────────────────────────┐
│ OrchestratorCore.execute(plan)      │
│  PARALLEL:                          │
│    ├── Vector search (plan.collections) │
│    ├── KG traversal (plan.kg_strategy) │
│    └── Cache check                     │
│  MERGE → ReAct loop → Response         │
└─────────────────────────────────────┘
```

### 2.2 QueryPlan Schema

```python
@dataclass
class QueryPlan:
    """Output of QueryPlanner — deterministic execution plan."""

    # Identity
    query: str
    query_hash: str                          # For caching/dedup

    # Classification
    domain: str                              # visa | tax | property | kbli | company | general
    entities: list[ExtractedEntity]          # Typed entities with confidence
    complexity: str                          # simple | lookup | multi_hop | cross_domain

    # Execution Plan
    collections: list[str]                   # Qdrant collections to search (ordered by priority)
    kg_strategy: KGStrategy                  # none | entity_lookup | subgraph | full_traversal
    kg_subgraph: str | None                  # company | visa | property | tax
    kg_max_depth: int                        # 1 for lookup, 2-3 for traversal
    model_tier: str                          # FLASH | PRO | DEEP_THINK
    enable_reranking: bool                   # CrossEncoder reranking

    # Confidence Modifiers
    kg_confidence_boost: float               # Added to evidence score if KG path found
    min_evidence_threshold: float            # Override default 0.15 for domain-specific

    # Performance Budget
    max_latency_ms: int                      # Timeout for this query type
    parallel_kg: bool                        # Run KG in parallel with vector search


class KGStrategy(str, Enum):
    NONE = "none"                            # Skip KG entirely
    ENTITY_LOOKUP = "entity_lookup"          # Just resolve entities (1 SQL query)
    SUBGRAPH = "subgraph"                    # Run domain subgraph (company/visa/etc.)
    FULL_TRAVERSAL = "full_traversal"        # BFS multi-hop (complex queries)
    GOLDEN_ROUTE = "golden_route"            # Deterministic workflow path
```

### 2.3 Planner Decision Matrix

```
┌──────────────────────────────────┬────────────┬──────────────────────┬──────────────────────────────┐
│ Query Pattern                    │ Complexity │ KG Strategy          │ Collections                  │
├──────────────────────────────────┼────────────┼──────────────────────┼──────────────────────────────┤
│ "What is KITAS?"                 │ simple     │ entity_lookup        │ [visa_oracle]                │
│ "How much PT PMA?"              │ lookup     │ none (PricingTool)   │ [pricing_hybrid]             │
│ "KITAS for restaurant owner"    │ multi_hop  │ subgraph(visa)       │ [visa_oracle, legal_hybrid]  │
│ "PT PMA + KITAS + tax?"         │ cross_dom  │ full_traversal       │ [legal_hybrid, visa, tax]    │
│ "Hak Pakai in Canggu"           │ multi_hop  │ subgraph(property)   │ [property, legal_hybrid]     │
│ "What KBLI for restaurant?"     │ lookup     │ subgraph(company)    │ [kbli_2025_final]            │
│ "Latest immigration news"       │ simple     │ none                 │ [balizero_news]              │
│ "Buongiorno" (greeting)         │ simple     │ none                 │ [] (skip_rag=true)           │
└──────────────────────────────────┴────────────┴──────────────────────┴──────────────────────────────┘
```

### 2.4 Latency Budget

```
                              Target: <3.0s total
                    ┌─────────────────────────────────┐
                    │                                 │
    QueryPlanner    │ 50ms (heuristic, no LLM call)  │
                    │                                 │
                    ├─────────────────────────────────┤
                    │       PARALLEL PHASE             │
    Vector Search   │ ████████████ 800ms              │
    KG Subgraph     │ ██████████ 600ms                │
    Cache Check     │ ██ 50ms                         │
                    │                                 │
                    ├─────────────────────────────────┤
                    │                                 │
    ReAct Loop      │ ████████████████████ 1500ms     │
    (1 LLM call)    │ (tool results pre-fetched)     │
                    │                                 │
                    └─────────────────────────────────┘
                              Total: ~2.4s

    Current:  Classify(200ms) + Entity(100ms) + KG(disabled) + ReAct(3500ms) = ~4.5s
    Target:   Plan(50ms) + PARALLEL[Vector+KG](800ms) + ReAct(1500ms) = ~2.4s
    Savings:  ~2.1s (47% faster)
```

Key insight: currently the ReAct loop makes its own vector_search tool call (adding
a round-trip). With pre-fetched results, the LLM gets context in the first message
and can answer in a single generation pass for most queries.

### 2.5 Shadow Mode Rollout (Codex + DeepSeek recommendation)

> **Codex GPT-5.3:** "Dual-run old vs new, metrica planner_confidence, fallback automatico."
> **DeepSeek R1:** "A/B test 10% traffic, monitor classification accuracy, rollback procedure."

The QueryPlanner does NOT replace the legacy classifiers on day 1.
Instead, it runs in **shadow mode** for 2 weeks:

```
Query → Legacy pipeline (IntentClassifier + EntityExtractor + RoutingManager)
  │       → produces legacy_result (USED for response)
  │
  └── ASYNC fire-and-forget (Gemini Round 2: must NOT be in critical path)
        New QueryPlanner → produces plan (LOGGED to query_analytics, NOT used)
        # Planner is heuristic (<50ms), but runs ASYNC to avoid any latency impact
        # and to prevent rate limit exhaustion under load
```

Metrics collected (DeepSeek Round 2 composite metric — weighted 40/30/30):

- retrieval_precision: compare top-10 chunks from legacy vs planner collections (40%)
- collection_overlap: Jaccard similarity of collection sets (30%)
- abstain_rate_delta: change in ABSTAIN rate if planner's collections were used (30%)
- Also log: planner_match_rate, planner_fallback_rate per domain

Switch criteria (all must pass for 7 consecutive days):

- composite_score > 0.85
- planner_match_rate > 92%
- abstain_rate_delta < +2% (planner doesn't cause more ABSTAINs)
- No regressions in evidence_score distribution

Feature flag: USE_QUERY_PLANNER (env var, instant toggle, no deploy needed)

```

---

## 3. KG Auto-Expansion Loop

### 3.1 Concept

Every RAG response with `evidence_score > 0.6` was built from verified source chunks.
We extract entities and relationships **from those source chunks** (NOT from the LLM's
synthesized response — that would create a hallucination feedback loop) and upsert them
into the KG, creating an organic growth loop grounded in source documents.

> **NB-1 CRITICAL WARNING (2026-04-03):** Extracting from LLM output creates
> "dangerous AI feedback loop — hallucination amplification" (Risk C4).
> The LegalIngestionService uses 4-stage pipeline with coreference resolution.
> Auto-expansion MUST extract from original chunks, not generated text.

```

User Query → RAG Pipeline → Response (evidence > 0.6)
│
source_chunk_ids[] from tool results
│
▼ (fire-and-forget)
┌──────────────────────────┐
│ KGAutoExpansion │
│ │
│ 1. Retrieve original │
│ source chunks from │
│ Qdrant by chunk_ids │
│ │
│ 2. Extract entities from │
│ SOURCE CHUNKS (ground │
│ truth, not LLM output) │
│ │
│ 3. Resolve against │
│ existing KG entities │
│ │
│ 4. Upsert new nodes/edges │
│ with source_chunk_ids │
│ │
│ 5. Update confidence │
│ (multi-source boost) │
└──────────────────────────┘

```

### 3.2 Extraction Strategy

**Two modes:**

1. **Heuristic extraction** (free, fast, <10ms) — regex patterns from EntityExtractor
   - Good for: KBLI codes, visa types, tax concepts, legal references
   - Already implemented in `entity_extractor.py`

2. **LLM extraction** (costs, slow, ~500ms) — structured extraction via Qwen 3.5:9b local
   - Good for: new relationships, complex multi-entity statements
   - Only triggered for novel entities (not already in KG)

**Decision:** Use heuristic first. If heuristic finds entities NOT in KG → trigger LLM extraction
on Pro/Air only (local Ollama, $0 cost). On Fly.io: heuristic only.

### 3.3 Growth Rate Estimate — REVISED (DeepSeek R1 + Codex validated)

> **DeepSeek R1 correction:** Regex recall on legal Indonesian text is 20-30%,
> not 100%. Real growth rate is 30-50 nodes/day, not 180. Validated by:
> 87K nodes extracted from 48K docs = ~1.8 nodes/doc. Regex captures far less
> than LLM extraction.

| Metric | Estimate | Basis |
|--------|----------|-------|
| Queries/day | ~200 | Current production traffic |
| Evidence > 0.6 | ~60% | Based on current scoring distribution |
| Queries eligible | ~120/day | |
| Source chunks per query | ~2-3 avg | Tool results typically return 2-3 chunks |
| Chunks processed/day | ~300 | |
| Regex recall on legal text | ~20-30% | DeepSeek R1 estimate (heuristic, not LLM) |
| **Daily growth** | **~40 nodes + ~25 edges** | Conservative realistic estimate |
| Weekly growth | ~280 nodes + ~175 edges | |
| Monthly growth | ~1,200 nodes + ~750 edges | |

At this rate, the KG reaches **100K nodes in ~2.5 years** organically (vs 8 months
originally claimed). To accelerate: periodic batch extraction with Qwen 3.5:27b on Pro.

### 3.4 Quarantine Graph Pattern (Codex recommendation)

> **Codex GPT-5.3:** "Write to quarantine graph, promote asynchronously after validation."
> **Gemini redteam:** "Fire-and-forget INSERT without locks = race conditions under concurrent queries."

Auto-expanded entities do NOT write directly to `kg_nodes`/`kg_edges`.
Instead, they go to a **staging table** for batch validation and promotion.

```

Source Chunks → Heuristic Extraction → kg_nodes_staging / kg_edges_staging
│
(batch job, every 6h)
│
▼
Validation checks:
├── Dedup against existing KG
├── Entity normalization
├── Confidence threshold (>0.65)
└── Rate limit: max 50 nodes/day
│
▼
PROMOTE to kg_nodes / kg_edges

````

Benefits:
- **No race conditions** — staging uses `ON CONFLICT DO NOTHING` (idempotent)
- **No KG pollution** — bad extractions never reach production graph
- **Auditable** — staging table is reviewable before promotion
- **Rate limited** — max 50 nodes/day initially (DeepSeek recommendation)

Promotion rules (Gemini Round 2 + DeepSeek Round 2):
- **Nodes BEFORE edges** — always promote nodes first, then edges in same batch.
  Never promote an edge whose target node hasn't been promoted yet (dangling edge).
- **Atomic batch** — single transaction: promote N nodes → promote their edges → commit.
- **Validation checks** (DeepSeek):
  1. Schema compliance (required properties per entity_type)
  2. Referential integrity (source/target exist in prod KG)
  3. Business logic gates (tax rate bounds, property price sanity)
  4. Source provenance (extraction_source must be set)
- **Staging retention** — auto-prune rejected entries after 30 days.
  Alert if staging >100K rows or grows >5%/day.

### 3.4 Dedup & Quality Control

```python
# Dedup strategy:
# 1. Normalize entity_id: lowercase, strip whitespace, canonical form
#    "PT PMA" → "pt_pma", "KITAS" → "kitas", "UU 6/2023" → "uu_6_2023"
#
# 2. Before INSERT, check existence:
#    - entity_id exact match → UPDATE confidence (multi-source boost)
#    - name fuzzy match (>0.85 similarity) → MERGE (update source_chunk_ids)
#    - No match → INSERT with confidence = 0.7 (lower than batch-extracted 0.9)
#
# 3. Edge dedup:
#    - (source, target, relationship_type) is unique key
#    - Duplicate → increment confidence by 0.05 (corroboration bonus)
#    - Max confidence: 1.0
````

### 3.5 Confidence Model (replaces hardcoded 0.9)

```python
# Source of truth for confidence calculation:
confidence = base_confidence * recency_decay * source_multiplier

# base_confidence:
#   batch_extraction (Gemini): 0.85
#   auto_expansion (heuristic): 0.70
#   auto_expansion (LLM): 0.80
#   user_verified: 0.95

# recency_decay:
#   exp(-age_days / 180)  # 6-month half-life

# source_multiplier:
#   1 source: 1.0x
#   2 sources: 1.10x
#   3+ sources: 1.15x (capped)
```

---

## 4. Qdrant Collection Unification — Decision

### 4.1 Analysis

**Option A: Maintain 16 collections** (status quo)

- Pros: No migration risk, clear separation
- Cons: Complex routing, tiny collections waste resources, 16 client connections

**Option B: Unify into 1-2 collections** (aggressive)

- Pros: Simplest routing, single search call
- Cons: Massive re-indexing (93K docs), metadata filtering slower on single large collection

**Option C: Hybrid consolidation** ← **CHOSEN**

- Merge 8 small/duplicate collections into `nuzantara_general_hybrid`
- Keep 5 large specialized collections as-is
- Net: 16 → 6 collections

### 4.2 Consolidation Plan — REVISED after NB-1

> **NB-1 WARNING:** Tiny collections use `full_scan_threshold: 10000` for
> brute-force scanning (faster than HNSW for small data). Merging them forces
> HNSW overhead. Also, `_hybrid` collections have BM25 sparse vectors while
> others don't — mixing them causes schema mismatch.

**Revised strategy: DELETE duplicates, KEEP tiny collections as-is.**

```
KEEP (large, specialized, high-traffic):
  ├── legal_unified_hybrid     (47,959 docs)  — Main legal KB (BM25+Dense)
  ├── kbli_2025_final          (8,886 docs)   — KBLI codes
  ├── zantara_books            (8,923 docs)   — Reference books
  ├── training_conversations   (2,898 docs)   — Training data (BM25+Dense)
  └── visa_oracle              (1,612 docs)   — Visa docs

KEEP (tiny but optimized with brute-force scan, no merge needed):
  ├── bali_zero_pricing_hybrid (29 docs)   — Pricing (brute-force scan)
  ├── bali_zero_team           (22 docs)   — Team info (brute-force scan)
  ├── balizero_news            (175 docs)  — Intel articles
  ├── immigration_circulars    (4 docs)    — Immigration circulars
  └── tax_genius_hybrid        (332 docs)  — Tax docs (BM25+Dense)

DELETE (verified legacy duplicates only):
  ├── legal_architect     (duplicate of legal_unified_hybrid)
  ├── legal_unified       (non-hybrid legacy, replaced by _hybrid)
  ├── tax_genius          (non-hybrid, replaced by tax_genius_hybrid)
  ├── property_listings   (alias of property_knowledge)
  ├── legal_updates       (alias/duplicate)
  ├── legal_intelligence  (alias/duplicate)
  ├── tax_updates         (alias/duplicate)
  ├── tax_knowledge       (alias/duplicate)
  └── cultural_insights   (0 docs, unused)

RESULT: 18 defined → 10 effective collections
  Memory savings: ~30% fewer segment loads (9 duplicates removed)
  Routing: simplified (no aliases to resolve)
  Tiny collections: PRESERVED (brute-force scan is FASTER than HNSW for <100 docs)
```

### 4.3 Why NOT Full Unification (strengthened by NB-1)

Qdrant performs best when collections are sized appropriately for their workload:

- `legal_unified_hybrid` at 48K docs with BM25 sparse vectors needs dedicated HNSW index
- Tiny collections (<100 docs) use brute-force scan (`full_scan_threshold: 10000`) which is **faster** than HNSW — merging them would force index overhead
- `_hybrid` collections have sparse vector fields (BM25) while non-hybrid ones don't — mixing creates schema mismatch requiring nullable sparse vectors
- KBLI (9K docs) has unique payload fields (`kode_kbli`, `pma_status`, `skala_usaha`) that would pollute other collections
- Scalar quantization (int8) is tuned per-collection for the 2GB Qdrant constraint

### 4.4 Migration Safety — REVISED (Gemini critical finding + DeepSeek protocol)

> **Gemini CRITICAL:** `kg_nodes.source_collection` references collection names.
> Deleting collections WITHOUT updating this column creates orphan nodes.
> Auto-expansion's "Retrieve original source chunks from Qdrant by chunk_ids"
> will crash with `Collection Not Found`.

```
Phase 1: AUDIT — Verify which kg_nodes reference each collection
  SELECT source_collection, COUNT(*) FROM kg_nodes
  WHERE source_collection IN ('legal_architect', 'legal_unified', ...)
  GROUP BY source_collection;

Phase 2: BACKUP source_collection (Gemini Round 2 — enable rollback)
  ALTER TABLE kg_nodes ADD COLUMN IF NOT EXISTS source_collection_previous TEXT;
  UPDATE kg_nodes SET source_collection_previous = source_collection
  WHERE source_collection IN ('legal_architect', 'legal_unified', ...);

Phase 3: REMAP — Update source_collection to surviving equivalents
  -- Execute during maintenance window (03:00 WITA, low traffic)
  -- Same transaction as Qdrant rename to minimize gap
  UPDATE kg_nodes SET source_collection = 'legal_unified_hybrid'
  WHERE source_collection IN ('legal_architect', 'legal_unified',
    'legal_updates', 'legal_intelligence');
  UPDATE kg_nodes SET source_collection = 'tax_genius_hybrid'
  WHERE source_collection IN ('tax_genius', 'tax_updates', 'tax_knowledge');

Phase 4: SNAPSHOT — Backup Qdrant collections before rename (DeepSeek)
  qdrant-client snapshot create <collection_name>

Phase 5: RENAME — Suffix with _deprecated_YYYYMMDD (DeepSeek protocol)
  # Execute immediately after Phase 3 UPDATE in same maintenance window

Phase 6: MONITOR — Log all collection access for 30 DAYS (DeepSeek Round 2)
  # 48h is NOT enough — weekly batch jobs, federation agents, MCP tools
  # may access collections on specific days only
  # Signals for safe deletion: zero reads in Qdrant metrics for 14 days
  # + zero errors in application logs for 30 days + all federation agents updated

Phase 7: DELETE — Only after 30 days zero-access
  # Rollback available via source_collection_previous column if needed

Embedding: NO RE-INDEXING needed — same text-embedding-3-small (1536 dims)
```

---

## 5. KG in Production — Solving the OOM

### 5.1 Root Cause — REVISED after NB-1 validation

> **NB-1 CORRECTION:** "Graph compilation is NOT the cold start bottleneck.
> StateGraph.compile() takes milliseconds and compiled graph objects only consume ~5MB."
> The real bottleneck is asyncpg/psycopg3 pool init (~1-2s) and Qdrant clients (~50MB).

The OOM is caused by the **cumulative footprint** of enabling KG alongside the existing stack:

1. FastAPI + 90 routers + middleware: ~400MB
2. Qdrant client (multiple collections): ~150MB
3. Redis client: ~50MB
4. LangChain LLM client (ChatOpenAI with tiktoken tokenizer): ~200MB ← **main KG overhead**
5. asyncpg connection pool: ~100MB
6. StateGraph subgraphs: ~20MB total (4 × ~5MB) ← NOT the bottleneck
7. Total with KG: ~920MB → leaves only ~80MB headroom on 2GB

The LLM client (item 4) is the primary target for optimization, not the subgraphs.

### 5.2 Solution: LLM Client Optimization + Lazy Init (REVISED after NB-1)

**Why NOT Cloudflare Workers:**

- Adds network hop latency (~50ms)
- D1 (SQLite) can't handle concurrent graph traversals well
- Splits the data layer (PostgreSQL + D1), making consistency hard
- Introduces new infrastructure to maintain

**Why NOT lazy subgraph loading (as primary strategy):**

- NB-1 validated that StateGraph.compile() is ~5MB per subgraph
- Eviction/reloading adds complexity for negligible memory savings (~20MB total)
- Risk of breaking state-sharing (known LangGraph issues #4748, #4182)

**Revised strategy — target the real bottleneck (LLM client ~200MB):**

```python
# CURRENT: Load everything at startup
class KGLangGraphOrchestrator:
    async def initialize(self):
        self.company_subgraph = build_company_subgraph(...)   # ~100MB
        self.visa_subgraph = build_visa_subgraph(...)         # ~100MB
        self.property_subgraph = build_property_subgraph(...) # ~100MB
        self.tax_subgraph = build_tax_subgraph(...)           # ~100MB
        self.llm = ChatOpenAI(model="gpt-4o-mini")            # ~200MB
        # Total: ~600MB at startup

# PROPOSED: Load on first use, evict after timeout
class KGLangGraphOrchestrator:
    def __init__(self):
        self._subgraphs: dict[str, CompiledGraph] = {}
        self._subgraph_last_used: dict[str, float] = {}
        self._llm: Any = None
        self._eviction_timeout = 300  # 5 minutes

    async def get_subgraph(self, domain: str) -> CompiledGraph:
        """Lazy-load subgraph, evict stale ones."""
        # Evict subgraphs not used in 5 minutes
        now = time.time()
        for name, last_used in list(self._subgraph_last_used.items()):
            if now - last_used > self._eviction_timeout and name != domain:
                del self._subgraphs[name]
                del self._subgraph_last_used[name]
                logger.info(f"♻️ Evicted {name} subgraph (idle {now - last_used:.0f}s)")

        if domain not in self._subgraphs:
            builder = {
                "company": build_company_subgraph,
                "visa": build_visa_subgraph,
                "property": build_property_subgraph,
                "tax": build_tax_subgraph,
            }[domain]
            self._subgraphs[domain] = builder(self.db_pool, self._get_llm())
            logger.info(f"📦 Loaded {domain} subgraph on demand")

        self._subgraph_last_used[domain] = now
        return self._subgraphs[domain]
```

**Memory profile with lazy loading:**

```
Startup:           ~0MB (nothing loaded)
First visa query:  ~200MB (LLM client) + ~100MB (visa subgraph) = ~300MB
After 5min idle:   ~200MB (LLM stays, subgraph evicted)
Peak (2 subgraphs): ~400MB (LLM + 2 subgraphs) — fits in 2GB with FastAPI
```

### 5.3 LLM Client Optimization — REVISED after NB-1

> **NB-1 CRITICAL WARNING:** KG nodes (`kg_graph_nodes.py`) heavily depend on
> LangChain's `BaseChatModel` interface (`.ainvoke()`, `SystemMessage`, `HumanMessage`).
> Dropping `langchain_openai`/`langchain_anthropic` breaks tool binding (`.bind_tools()`)
> and state reducers (`add_messages`). Known LangGraph subgraph composition issues
> (#4748, #4182, #3020) make this even more fragile.

**Revised approach — keep LangChain for KG, optimize initialization:**

```python
# KEEP LangChain for KG nodes (they need .ainvoke, SystemMessage, etc.)
# But defer initialization until first KG query (lazy singleton):

_cached_reasoning_llm: Any = None  # Already exists in kg_langgraph_orchestrator.py

def get_llm_for_reasoning() -> Any:
    """Lazy singleton — only loads tiktoken/tokenizer on first call."""
    global _cached_reasoning_llm
    if _cached_reasoning_llm is not None:
        return _cached_reasoning_llm
    # This is the existing pattern — already lazy!
    # The real optimization: don't call this at startup.
    # Only load when ENABLE_KG_LANGGRAPH=true AND first KG query arrives.
    _cached_reasoning_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    return _cached_reasoning_llm
```

**The real memory win: defer LLM client init from startup to first-query.**
If no KG queries arrive (common for simple pricing/greeting queries),
the 200MB is never allocated. This is already partially implemented
(`get_llm_for_reasoning()` is a cached singleton) — we just need to ensure
it's not called during `lifespan()` initialization.

**Memory savings:** 200MB on startup → 0MB until first KG query. Peak unchanged.

### 5.4 Alternative Considered: Pre-computed Subgraph Snapshots

For the highest-traffic queries (top 50 workflows), pre-compute the KG traversal result
and store as JSON in Redis. This eliminates the need for live graph traversal for ~70%
of queries.

```
Top workflows (by frequency):
  1. PT PMA setup workflow          → Redis key: kg:workflow:pt_pma_setup
  2. KITAS work visa process        → Redis key: kg:workflow:kitas_work
  3. NPWP registration              → Redis key: kg:workflow:npwp_registration
  4. NIB/OSS licensing              → Redis key: kg:workflow:nib_oss
  ...

TTL: 24h (refreshed by nightly batch job on Pro)
Fallback: if cache miss → live subgraph traversal
```

This is complementary to lazy loading, not a replacement. Use both.

---

## 6. Property & Tax Subgraph Completion

### 6.1 Current State

| Subgraph | Status     | Nodes | Edges | Source                                    |
| -------- | ---------- | ----- | ----- | ----------------------------------------- |
| Company  | ✅ DONE    | ~12K  | ~25K  | KBLI extraction + batch                   |
| Visa     | ✅ DONE    | ~8K   | ~18K  | visa_oracle + imigrasi.go.id              |
| Property | ❓ PARTIAL | ~500  | ~800  | Minimal, mostly from legal_unified_hybrid |
| Tax      | ❓ PARTIAL | ~6K   | ~12K  | tax_genius + regulations                  |

### 6.2 Property Subgraph — Schema

```
Node Types:
  property_type     — Hak Pakai, HGB, Hak Milik, Hak Sewa, Hak Guna Usaha
  zoning_category   — Zona Hijau, Zona Kuning, Zona Merah, Zona Pariwisata
  regulation        — PP 18/2021, Permen ATR 18/2021, Perda Bali 3/2023
  document          — IMB, SLF, PBG, Sertifikat Tanah
  process_step      — Pengecekan Sertifikat, Akta Jual Beli, Balik Nama
  fee               — BPHTB (5%), PPAT fee, Balik Nama fee
  location          — Kabupaten Badung, Gianyar, Tabanan (linked to zoning)

Edge Types:
  REQUIRES          — "Hak Pakai REQUIRES Sertifikat Tanah"
  RESTRICTED_TO     — "Hak Milik RESTRICTED_TO WNI" (citizen only)
  LOCATED_IN        — "Zoning X LOCATED_IN Kabupaten Y"
  HAS_FEE           — "Balik Nama HAS_FEE 1% of transaction"
  GOVERNED_BY       — "Hak Pakai GOVERNED_BY PP 18/2021"
  PART_OF           — "Pengecekan Sertifikat PART_OF Hak Pakai workflow"
  DURATION          — "Hak Pakai DURATION 30+20+20 years"
```

### 6.3 Tax Subgraph — Schema

```
Node Types:
  tax_type          — PPh 21, PPh 23, PPh 25, PPh 29, PPN, PBB
  tax_obligation    — SPT Tahunan, SPT Masa, Bukti Potong
  entity_type       — PT PMA, PT Perorangan, CV, Freelancer
  rate_bracket      — WPOP progressive (5-35%) OR Badan Usaha flat (22%)
  regulation        — UU HPP 7/2021, PP 55/2022, PMK 66/2023
  document          — NPWP, EFIN, Faktur Pajak, Bukti Potong
  deadline          — SPT Tahunan (March 31), SPT Masa (20th monthly)

  ⚠️ CRITICAL (Gemini Round 1 + Round 2 — 3 additional legal errors found):

  rate_bracket MUST distinguish:
    - WPOP (Wajib Pajak Orang Pribadi): progressive 5%, 15%, 25%, 30%, 35%
      → Applied to NETTO income (after PTKP deduction, NOT gross)
    - Badan Usaha (PT PMA, CV, etc.):
      → Standard: 22% corporate tax
      → Fasilitas Pasal 31E: 11% EFFECTIVE for PMI with revenue <50B IDR
        (50% discount on portion of taxable income proportional to 4.8B/gross revenue)
      → MUST have `fasilitas_31e_eligible` boolean property
    - UMKM (PP 55/2022): 0.5% final tax with STRICT limits:
      → PT: max 3 years
      → CV/Firma: max 4 years
      → WPOP individual: max 7 years
      → Franchigia: first 500M IDR gross revenue/year is TAX FREE for WPOP
      → MUST have `validity_period_years` and `exemption_threshold_idr` properties

  NEW required node type (Gemini Round 2):
  ptkp             — Penghasilan Tidak Kena Pajak (non-taxable income threshold)
                     Variants: TK/0 (54M), K/0 (58.5M), K/1 (63M), K/2 (67.5M), K/3 (72M)
                     MANDATORY for WPOP progressive tax calculation

  Each rate_bracket node MUST have `applies_to_entity_type` property.
  Without this, the KG will recommend wrong tax rates with confidence boost.

Edge Types:
  APPLIES_TO        — "PPh 21 APPLIES_TO PT PMA employees"
  HAS_RATE          — "PPh Badan HAS_RATE flat_22pct" (with applies_to_entity_type=badan_usaha)
  HAS_FASILITAS     — "PT PMA (<50B) HAS_FASILITAS pasal_31e_discount"
  HAS_PTKP          — "WPOP (K/1) HAS_PTKP 63M IDR" (deducted before progressive rates)
  REQUIRES_DOCUMENT — "SPT Tahunan REQUIRES_DOCUMENT NPWP"
  GOVERNED_BY       — "PPh 21 GOVERNED_BY UU HPP 7/2021"
  DEADLINE          — "SPT Tahunan DEADLINE March 31"
  EXEMPTION         — "PP 55/2022 EXEMPTION for <4.8B revenue (UMKM only)"
  VALIDITY_LIMIT    — "UMKM 0.5% VALIDITY_LIMIT 3 years (PT)"
```

### 6.4 Extraction Pipeline

```
Source: legal_unified_hybrid (48K docs — contains property and tax regulations)

Step 1: Filter candidates via Qdrant metadata
  property: payload.category IN ["property", "agrarian", "spatial_planning", "real_estate"]
  tax: payload.category IN ["tax", "fiscal", "ppn", "pph"]

Step 2: Batch extraction via Qwen 3.5:27b (Pro local, $0 cost)
  - 500 docs/batch, ~2 min per batch
  - Structured output: { "entities": [...], "relationships": [...] }
  - Extraction prompt tuned per domain (property vs tax)

Step 3: Dedup and upsert into kg_nodes/kg_edges
  - Same dedup logic as auto-expansion (§3.4)
  - Source_chunk_ids tracked for traceability

Step 4: Validate via subgraph tests
  - backend/tests/services/rag/test_kg_subgraphs.py (58 tests)
  - Add property/tax specific assertions

Estimated (DeepSeek R1: 70-80% precision, 60-70% recall):
  Property: ~2,000 entities, ~3,000 edges from ~500 filtered docs
  Tax: ~3,000 entities, ~5,000 edges from ~800 filtered docs
  Time: ~4h total on Pro (Qwen 3.5:27b)
  Cost: $0 (local Ollama)

Step 5: MANDATORY human audit (Codex + DeepSeek consensus)
  - Random sample of 500 triples from extraction output
  - Check: entity normalization (PPh = Pajak Penghasilan = Income Tax)
  - Check: cross-reference resolution (Pasal X ayat Y → correct article)
  - Check: rate_bracket applies_to_entity_type (WPOP vs Badan Usaha)
  - Acceptance (DeepSeek Round 2 — risk-tiered thresholds):
    → High-risk (ownership rights, tax rates, legal obligations): ≥90% precision
    → Medium-risk (processing times, document lists, deadlines): ≥80% precision
    → Low-risk (descriptive facts, definitions, general info): ≥75% precision
    → Overall minimum: 85% precision on stratified gold set
  - Sample MUST be stratified by risk tier, not purely random
  - Qwen is a CANDIDATE GENERATOR, not a direct KG writer (Codex pattern)
```

---

## 7. Migration Plan — Zero Downtime

### Phase 0: Preparation (Day 1)

```
□ Create feature branch: graphrag-evolution-v6
□ Run baseline benchmarks:
    PYTHONPATH=. pytest backend/tests/services/rag/ -q --tb=no  # Current pass rate
    curl -w '%{time_total}' https://nuzantara-rag.fly.dev/api/agentic/query  # Latency baseline
□ Snapshot KG stats:
    SELECT entity_type, COUNT(*) FROM kg_nodes GROUP BY entity_type;
    SELECT relationship_type, COUNT(*) FROM kg_edges GROUP BY relationship_type;
```

### Phase 1: Unified Query Planner (Day 2-3)

```
□ Create backend/services/rag/agentic/query_planner.py
□ Create backend/services/rag/agentic/query_plan.py (dataclass)
□ Wire into OrchestratorCore (replaces extract_entities_and_kg_context)
□ Keep old routing as fallback (feature flag: USE_QUERY_PLANNER=true)
□ Tests: 20+ unit tests for planner decision matrix
□ Deploy with flag OFF → enable after 24h monitoring
```

### Phase 2: KG Auto-Expansion (Day 3-4)

```
□ Create backend/services/rag/kg_auto_expansion.py
□ Wire into OrchestratorCore as fire-and-forget post-response task
□ Add confidence model (replace hardcoded 0.9)
□ Migration 067: Add kg_nodes.extraction_source column (batch | auto_heuristic | auto_llm)
□ Tests: extraction accuracy, dedup, confidence calculation
□ Deploy: auto-expansion ON in prod (heuristic-only on Fly.io)
```

### Phase 3: KG Production Enablement (Day 4-5)

```
□ Refactor KGLangGraphOrchestrator → lazy subgraph loading
□ Replace ChatOpenAI with direct httpx API calls
□ Pre-compute top 50 workflow snapshots in Redis
□ Set ENABLE_KG_LANGGRAPH=true on Fly.io
□ Monitor: memory usage (fly logs), latency, error rate
□ Rollback plan: ENABLE_KG_LANGGRAPH=false (instant, no deploy needed)
```

### Phase 4: Qdrant Consolidation (Day 5-6)

```
□ Create migration script: scripts/qdrant_consolidate.py
□ Create nuzantara_general_hybrid collection
□ Copy + tag documents from 8 small collections
□ Update collection_registry.py routing
□ Parallel validation: query old+new, compare recall
□ Drop legacy collections after 48h validation
```

### Phase 5: Property & Tax Subgraph (Day 6-8, on Pro)

```
□ Create extraction script: scripts/extract_property_kg.py
□ Create extraction script: scripts/extract_tax_kg.py
□ Run on Pro via Qwen 3.5:27b (local, $0)
□ Validate: test_kg_subgraphs.py with new assertions
□ Update CLAUDE.md: Property ✅, Tax ✅
```

### Phase 6: Integration Testing & Tuning (Day 8-10)

```
□ End-to-end benchmark: 100 test queries across all domains
□ Compare: latency, evidence scores, answer quality
□ Tune: confidence boost weights, collection routing
□ RAGAS evaluation: compare before/after
□ Production burn-in: 72h monitoring before declaring GA
```

---

## 8. Expected Benchmarks

### 8.1 Latency

| Query Type        | Current        | Target | Method                        |
| ----------------- | -------------- | ------ | ----------------------------- |
| Simple (greeting) | 200ms          | 150ms  | Skip RAG, no change           |
| Lookup (pricing)  | 3.5s           | 1.5s   | Pre-fetched tool results      |
| Domain (visa)     | 4.5s           | 2.5s   | Unified planner + parallel KG |
| Cross-domain      | 6.0s           | 3.5s   | Parallel subgraphs + merge    |
| KG workflow       | N/A (disabled) | 2.0s   | Lazy subgraph + Redis cache   |

### 8.2 Memory Footprint (Fly.io 2GB)

| Component         | Current           | After                           |
| ----------------- | ----------------- | ------------------------------- |
| FastAPI + routers | 400MB             | 400MB                           |
| Qdrant client     | 150MB             | 100MB (fewer collections)       |
| Redis client      | 50MB              | 50MB                            |
| KG LangGraph      | 0 (disabled)      | 300MB peak (lazy)               |
| LLM client        | 200MB (LangChain) | 5MB (httpx direct)              |
| Headroom          | 200MB             | 145MB                           |
| **Total**         | **1.0GB**         | **1.0GB** (but with KG active!) |

### 8.3 KG Growth

| Timeline   | Nodes    | Edges    | Source                      |
| ---------- | -------- | -------- | --------------------------- |
| Now        | 87,198   | 210,354  | Batch extraction (static)   |
| +1 month   | 61,500   | 165,000  | Auto-expansion (~180/day)   |
| +3 months  | 72,300   | 171,800  | Accelerating (more queries) |
| +6 months  | 89,000   | 183,000  | + Property/Tax extraction   |
| +12 months | ~120,000 | ~210,000 | Organic growth plateau      |

---

## 9. Risk Analysis

| Risk                                    | Probability | Impact | Mitigation                                     |
| --------------------------------------- | ----------- | ------ | ---------------------------------------------- |
| KG OOM on Fly.io even with lazy loading | LOW         | HIGH   | Feature flag for instant disable               |
| Auto-expansion inserts garbage          | MEDIUM      | MEDIUM | Confidence threshold 0.7, manual review sample |
| Qdrant migration loses docs             | LOW         | HIGH   | Parallel validation before drop                |
| Query planner misroutes                 | MEDIUM      | MEDIUM | Fallback to old routing, A/B test              |
| Property/Tax extraction quality         | MEDIUM      | LOW    | Qwen 3.5:27b is good at structured extraction  |

---

## 10. Non-Goals (Explicit Exclusions)

- **Full re-embedding**: Embeddings are FROZEN (text-embedding-3-small). No re-indexing.
- **New infrastructure**: No Cloudflare Workers, no new databases. PostgreSQL + Qdrant + Redis.
- **ML-based query planning**: Heuristic/rule-based planner. No training data needed.
- **Real-time KG sync**: Auto-expansion is eventual consistency (fire-and-forget).
- **Graph database migration**: KG stays in PostgreSQL. No Neo4j/Neptune.
- **Fly.io upgrade**: Stay on 2GB shared-cpu-2x. $0 infra cost increase.

---

## Appendix A: File Map

```
NEW FILES:
  backend/services/rag/agentic/query_planner.py      — Unified query planner
  backend/services/rag/agentic/query_plan.py          — QueryPlan dataclass
  backend/services/rag/kg_auto_expansion.py            — Auto-expansion loop
  backend/migrations/migration_067_kg_extraction_source.py
  scripts/qdrant_consolidate.py                        — Collection merger
  scripts/extract_property_kg.py                       — Property KG extraction
  scripts/extract_tax_kg.py                            — Tax KG extraction

MODIFIED FILES:
  backend/services/rag/agentic/orchestrator_core.py   — Wire query planner + auto-expansion
  backend/services/rag/kg_langgraph_orchestrator.py   — Lazy subgraph loading
  backend/services/ingestion/collection_manager.py    — Updated collection definitions
  backend/core/collection_registry.py                  — Updated routing
  backend/services/rag/agentic/reasoning_utils.py     — KG confidence boost in evidence scoring
  backend/services/rag/confidence.py                   — Updated confidence model
```

---

_Prepared by: Claude Opus 4.6 + Bali Zero AI Team_
_Date: 2026-04-03_
_Status: AWAITING APPROVAL_

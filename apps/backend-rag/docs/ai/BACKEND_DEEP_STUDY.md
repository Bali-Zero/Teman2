# 🔬 BACKEND NUZANTARA - Studio Approfondito

> Analisi completa del backend RAG suddiviso in 8 macro-aree

---

## 📊 Overview

| Metrica             | Valore                                           |
| ------------------- | ------------------------------------------------ |
| **Linee di codice** | ~50,000+                                         |
| **Routers**         | 88 endpoint files                                |
| **Services**        | 26 domini                                        |
| **Core Engine**     | 3,617 LOC                                        |
| **LLM Providers**   | 5 (Gemini, Vertex, DeepSeek, Ollama, OpenRouter) |

---

## 1️⃣ APP - FastAPI Core

**Location:** `backend/app/`

### Struttura

```
app/
├── main.py              # Entry point (alias → main_cloud.py)
├── main_cloud.py        # App factory, lifecycle, CORS
├── dependencies.py      # DI container (14KB!)
├── metrics.py           # Prometheus metrics (48KB!)
├── streaming.py         # SSE streaming (24KB)
├── feature_flags.py     # Feature toggles
├── models.py            # Pydantic models
├── routers/             # 88 router files!
├── setup/               # Startup initialization
├── auth/                # Authentication
├── utils/               # Helpers
└── lifecycle/           # Startup/shutdown hooks
```

### Routers Principali (per categoria)

| Categoria     | Routers                                                    | Endpoints |
| ------------- | ---------------------------------------------------------- | --------- |
| **CRM**       | crm_clients, crm_practices, crm_interactions, crm_enhanced | ~80       |
| **Intel**     | intel (54KB!), intel_staging                               | ~40       |
| **RAG**       | agentic_rag, conversations, knowledge_visa                 | ~30       |
| **Portal**    | portal, portal_invite, auth                                | ~25       |
| **Analytics** | analytics, dashboard_summary                               | ~20       |
| **Memory**    | collective_memory, episodic_memory                         | ~15       |
| **Admin**     | admin_logs, admin_team_activity, debug                     | ~30       |
| **Agents**    | autonomous_agents, agents                                  | ~20       |
| **Content**   | article_composer, article_composer_v2                      | ~15       |
| **Health**    | health, feedback                                           | ~10       |

### File Critici

```python
# dependencies.py - DI Container (393 righe)
# Gestisce tutte le dependency injection per:
- Database connections (PostgreSQL)
- Vector store (Qdrant)
- Cache (Redis)
- LLM clients
- Services initialization

# metrics.py - Prometheus (48KB, 1200+ righe)
# Metriche per:
- Request latency
- LLM token usage
- Cache hit/miss
- Error rates
- Business KPIs
```

---

## 2️⃣ SERVICES - Business Logic

**Location:** `backend/services/`

### 26 Domini di Business

| Dominio               | Files | Responsabilità                                |
| --------------------- | ----- | --------------------------------------------- |
| **analytics**         | 14    | Team metrics, burnout detection, productivity |
| **article_composer**  | 5     | Blog/news AI generation                       |
| **autonomous_agents** | 2     | Background AI agents                          |
| **classification**    | 2     | Intent classification                         |
| **communication**     | 5     | Language detection, emotion analysis          |
| **compliance**        | 5     | Legal compliance tracking                     |
| **crm**               | 11    | Customer relationship management              |
| **ingestion**         | 12    | Document ingestion pipeline                   |
| **integrations**      | 12    | Google Drive, GitHub, messaging               |
| **intel**             | 5     | Intelligence gathering/approval               |
| **invoicing**         | 3     | Invoice generation                            |
| **journey**           | 5     | Client journey tracking                       |
| **knowledge_graph**   | 7     | Entity extraction, graph building             |
| **llm_clients**       | 6     | LLM provider wrappers                         |
| **memory**            | 11    | Episodic + collective memory                  |
| **misc**              | 25    | Various utilities                             |
| **monitoring**        | 6     | Health checks, alerts                         |
| **multimodal**        | 1     | PDF vision                                    |
| **oracle**            | 12    | Main RAG oracle service                       |
| **portal**            | 3     | Client portal                                 |
| **pricing**           | 4     | Dynamic pricing                               |
| **rag**               | 4     | RAG utilities                                 |
| **response**          | 3     | Response formatting                           |
| **routing**           | 13    | Query routing intelligence                    |
| **search**            | 5     | Semantic search, citations                    |
| **tools**             | 3     | Tool definitions                              |

### Services Chiave

```python
# oracle/oracle_service.py - Il CUORE del RAG
class OracleService:
    """
    Main RAG orchestrator:
    1. Query understanding
    2. Route selection
    3. Context retrieval (Qdrant)
    4. LLM generation
    5. Response formatting
    """

# routing/golden_router_service.py - Router intelligente
class GoldenRouterService:
    """
    Decide quale knowledge base interrogare:
    - visa_knowledge
    - business_knowledge
    - legal_knowledge
    - politics_knowledge
    - etc.
    """

# memory/memory_orchestrator.py - Gestione memoria
class MemoryOrchestrator:
    """
    Combina:
    - Short-term (conversation context)
    - Long-term (PostgreSQL)
    - Semantic (Qdrant vectors)
    """
```

---

## 3️⃣ CORE - RAG Engine

**Location:** `backend/core/`

### Componenti (3,617 LOC totali)

| File                   | LOC   | Funzione                           |
| ---------------------- | ----- | ---------------------------------- |
| **qdrant_db.py**       | 1,225 | Vector database operations         |
| **parsers.py**         | 502   | Document parsing (PDF, DOCX, etc.) |
| **cache.py**           | 415   | Multi-level caching                |
| **bm25_vectorizer.py** | 366   | Sparse vector search               |
| **embeddings.py**      | 346   | Text → vectors                     |
| **exceptions.py**      | 327   | Custom exceptions                  |
| **chunker.py**         | 251   | Text chunking strategies           |
| **reranker.py**        | 184   | Result reranking                   |

### qdrant_db.py - Il Motore Vector

```python
class QdrantDB:
    """
    Gestisce tutte le operazioni su Qdrant:

    Collections:
    - visa_knowledge
    - business_knowledge
    - legal_knowledge
    - politics_knowledge
    - team_knowledge
    - pricing_knowledge
    - client_memory

    Operazioni:
    - create_collection()
    - upsert_vectors()
    - search_similar()
    - hybrid_search()  # Dense + Sparse
    - delete_by_metadata()
    """
```

### embeddings.py - Generazione Vettori

```python
class EmbeddingService:
    """
    Providers supportati:
    - Google text-embedding-004 (default)
    - OpenAI text-embedding-3-large
    - Local (Ollama)

    Features:
    - Batch processing
    - Caching
    - Fallback chain
    """
```

---

## 4️⃣ LLM - AI Providers

**Location:** `backend/llm/`

### Provider Chain

```
                    ┌─────────────┐
                    │  zantara_   │
                    │  ai_client  │ (28KB - Main orchestrator)
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌─────▼─────┐      ┌─────▼─────┐
   │  Gemini │       │   Vertex  │      │ DeepSeek  │
   │ genai_  │       │           │      │           │
   │ client  │       │           │      │           │
   └─────────┘       └───────────┘      └───────────┘
        │                                     │
   ┌────▼────┐                          ┌─────▼─────┐
   │ Ollama  │                          │OpenRouter │
   │ (local) │                          │           │
   └─────────┘                          └───────────┘
```

### zantara_ai_client.py - Orchestratore (28KB)

```python
class ZantaraAIClient:
    """
    Unified LLM interface:

    - Multi-provider fallback
    - Token counting
    - Rate limiting
    - Cost tracking
    - Streaming support
    - Tool/function calling
    - Structured output (JSON mode)

    Modelli configurati:
    - gemini-2.0-flash (default)
    - gemini-1.5-pro (complex)
    - deepseek-chat (cheap)
    - ollama/qwen2.5 (local)
    """
```

### genai_client.py - Google AI (20KB)

```python
class GenAIClient:
    """
    Direct Google GenAI SDK integration:
    - Grounding with Google Search
    - Multimodal (images)
    - Code execution
    - Function calling
    """
```

---

## 5️⃣ DB - Database Layer

**Location:** `backend/db/`

### Struttura

```
db/
├── __init__.py          # Connection pool
├── migrate.py           # Migration runner
├── migration_base.py    # Base migration class
├── migration_manager.py # Auto-migration system
├── utils.py             # DB utilities
├── migrations_v2/       # Current migrations
└── migrations_legacy_archive/  # Old migrations
```

### Schema PostgreSQL

```sql
-- Principali tabelle:
- users                 -- Utenti sistema
- conversations        -- Chat history
- messages             -- Singoli messaggi
- memory_facts         -- Fatti estratti
- intel_articles       -- News articles
- crm_clients          -- CRM clients
- crm_interactions     -- Client interactions
- crm_practices        -- Pratiche (visa, business)
- portal_users         -- Portal access
- analytics_events     -- Telemetry
- feedback             -- User feedback
```

---

## 6️⃣ MIDDLEWARE - Request Processing

**Location:** `backend/middleware/`

| File                    | LOC  | Funzione                    |
| ----------------------- | ---- | --------------------------- |
| **hybrid_auth.py**      | 800+ | API key + JWT + Portal auth |
| **rate_limiter.py**     | 250  | Redis-based rate limiting   |
| **activity_logging.py** | 200  | Request/response logging    |
| **request_tracing.py**  | 170  | Correlation IDs             |
| **error_monitoring.py** | 200  | Error tracking              |

### hybrid_auth.py - Sistema Auth

```python
class HybridAuthMiddleware:
    """
    Multi-strategy authentication:

    1. API Key (header: X-API-Key)
       - Per integrazioni esterne
       - Scoped permissions

    2. JWT (header: Authorization: Bearer)
       - Per frontend/mobile
       - User identity

    3. Portal Token
       - Per client portal
       - Client-scoped access

    4. Service Account
       - Per microservices interni
    """
```

---

## 7️⃣ AGENTS - Autonomous AI

**Location:** `backend/agents/`

### Struttura

```
agents/
├── agents/              # Agent definitions
│   ├── client_value_predictor.py
│   ├── compliance_monitor.py
│   ├── knowledge_graph_builder.py
│   ├── proactive_outreach.py
│   └── ...
├── services/            # Agent services
│   ├── agent_executor.py
│   ├── agent_registry.py
│   └── ...
└── config/              # Agent configs
```

### Agent Types

| Agent                     | Funzione                        | Schedule  |
| ------------------------- | ------------------------------- | --------- |
| **ClientValuePredictor**  | Predice valore lifetime cliente | Daily     |
| **ComplianceMonitor**     | Monitora scadenze documenti     | Hourly    |
| **KnowledgeGraphBuilder** | Costruisce grafo conoscenza     | On-demand |
| **ProactiveOutreach**     | Suggerisce follow-up            | Daily     |
| **IntelCollector**        | Raccoglie news/updates          | Every 4h  |

---

## 8️⃣ PLUGINS - Extensibility

**Location:** `backend/plugins/`

### Plugin System

```
plugins/
├── __init__.py          # Plugin loader
├── bali_zero/           # Pricing plugin
│   ├── pricing_plugin.py
│   └── ...
└── team/                # Team management
    ├── list_members_plugin.py
    ├── search_member_plugin.py
    └── ...
```

### Core Plugin System (`core/plugins/`)

```python
# registry.py
class PluginRegistry:
    """
    Dynamic plugin loading:
    - Auto-discovery
    - Dependency injection
    - Lifecycle management
    """

# executor.py
class PluginExecutor:
    """
    Esegue plugins con:
    - Timeout handling
    - Error isolation
    - Result caching
    """
```

---

## 🔄 Request Flow

```
Request
   │
   ▼
┌─────────────────┐
│   Middleware    │ (auth, rate limit, tracing)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Router      │ (FastAPI endpoint)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Dependencies  │ (DI container)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Services     │ (business logic)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌───────┐
│ Core  │  │  LLM  │
│(Qdrant│  │Client │
│Cache) │  │       │
└───────┘  └───────┘
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│   Database      │ (PostgreSQL)
└─────────────────┘
```

---

## 📈 Metriche Chiave

```
Endpoint più grandi (per complessità):
1. intel.py           - 54KB (intelligence hub)
2. crm_clients.py     - 52KB (CRM principale)
3. crm_enhanced.py    - 48KB (CRM avanzato)
4. conversations.py   - 31KB (chat)
5. agentic_rag.py     - 30KB (RAG orchestrator)

Services più complessi:
1. oracle/            - 12 files (RAG core)
2. routing/           - 13 files (query routing)
3. misc/              - 25 files (utilities)
4. memory/            - 11 files (memory system)
5. ingestion/         - 12 files (document pipeline)
```

---

## 🎯 Entry Points per Studio

### Per capire il RAG:

1. `services/oracle/oracle_service.py`
2. `core/qdrant_db.py`
3. `core/embeddings.py`
4. `app/routers/agentic_rag.py`

### Per capire il CRM:

1. `app/routers/crm_clients.py`
2. `services/crm/`
3. `app/routers/crm_practices.py`

### Per capire l'Auth:

1. `middleware/hybrid_auth.py`
2. `app/auth/`
3. `app/routers/auth.py`

### Per capire gli LLM:

1. `llm/zantara_ai_client.py`
2. `llm/genai_client.py`
3. `services/llm_clients/`

### Per capire la Memory:

1. `services/memory/memory_orchestrator.py`
2. `services/memory/episodic_memory_service.py`
3. `app/routers/collective_memory.py`

---

_Documento generato il 2026-01-28_
_"Production-Ready or Nothing" 🦞_

# 🧠 AI ONBOARDING PROTOCOL - NUZANTARA PROJECT

**ATTENTION NEW AI AGENT:**
You have been instantiated as a core contributor to the **Nuzantara** platform. This document defines your operational parameters, the system architecture, and the standards you must uphold.

---

## ⚖️ LEGGE ZERO - LA REGOLA FONDAMENTALE

> **Se non sai o non capisci qualcosa del sistema — come è stata fatta, come si usa, dove si trova — il DevAI NON PRESUME.**
>
> **Si ferma e studia la codebase. Legge la documentazione recente.**

Questa è la legge più importante. Prima di modificare, suggerire, o implementare qualsiasi cosa:

1. **STOP** — Non inventare. Non assumere. Non "intuire".
2. **SEARCH** — Usa `Grep`, `Glob`, `Read` per trovare il codice esistente.
3. **STUDY** — Leggi `docs/LIVING_ARCHITECTURE.md`, i file correlati, i test.
4. **ASK** — Se dopo lo studio rimane ambiguità, chiedi all'utente.

**Violare questa legge produce codice duplicato, bug, e regressioni.**

---

## 1. 🌍 PROJECT MISSION
**Nuzantara** is an enterprise-grade **Intelligent Business Operating System** designed for **Bali Zero**.
It is not merely a chatbot; it is a comprehensive platform integrating RAG (Retrieval-Augmented Generation), complex business logic, CRM capabilities, and multi-channel communication (WhatsApp, Web, Instagram, API).

**Core Objectives:**
- **Reliability:** Systems must be robust, fail-safe, and self-healing.
- **Scalability:** Architecture must support growing data and user loads.
- **Maintainability:** Code must be clean, typed, and well-documented.

## 🏗️ SYSTEM ARCHITECTURE

The project is a **Monorepo** managed with `npm workspaces` and Docker.
For a complete 4D understanding of the system (Space, Time, Logic, Scale), refer to [docs/SYSTEM_MAP_4D.md](docs/SYSTEM_MAP_4D.md).

### 2.1 Core Services

| Service | Path | Stack | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Backend RAG** | `apps/backend-rag` | **Python 3.11+** (FastAPI) | ✅ **PRIMARY** | The central intelligence engine. 34 routers (213 endpoints), 152 services, 26 migrations (62 tables). Handles Agentic RAG (ReAct pattern), AI orchestration, Vector DB (Qdrant), CRM, and business logic. |
| **Frontend** | `apps/mouth` | **Next.js 16** (React 19) | ✅ **PRIMARY** | The modern user interface. Uses Tailwind CSS 4, TypeScript, shadcn/ui components, and lightweight state management. |


### 2.2 Infrastructure
- **Database:** PostgreSQL (asyncpg with connection pooling, 23 tables), Qdrant Cloud (Vector, **53,757 documents** across 4 active collections), Redis (Cache/Queue).
- **Deployment:** Fly.io (Docker-based, multi-region Singapore).
- **Testing & Deployment:** Local testing and manual deployment workflow. All testing and deployment is done locally - no automated CI/CD pipelines. Deploy via `flyctl deploy` from local machine.
- **Observability:** Prometheus, Grafana, Jaeger, Alertmanager.

---

## 3. 📜 OPERATIONAL STANDARDS

### 3.1 Coding Guidelines
- **Python:**
    -   Use **Type Hints** everywhere (`def func(x: int) -> str:`).
    -   Use `async/await` for I/O bound operations (FastAPI).
    -   Follow PEP 8.
-   **TypeScript:**
    -   Strict typing required (no `any`).
    -   Use Functional Components with Hooks for React.
-   **General:**
    -   **No Hardcoding:** Use `os.getenv()` or `process.env`.
    -   **Error Handling:** Fail gracefully. Use try/catch and log errors.

### 3.2 File System Discipline
-   **Root (`/`) is Restricted:** Do not create files in the root unless explicitly instructed.
-   **Documentation:** Place docs in `docs/`.
-   **Scripts:** Place utility scripts in `scripts/` or service-specific `scripts/` folders.

### 3.3 Testing & Verification
-   **Test Coverage:** The project maintains **95.01%** test coverage (exceeding 90% target).
    -   `reasoning.py`: 96.30% coverage
    -   `feedback.py`: 89.61% coverage
    -   72+ comprehensive tests covering all critical paths
    -   Run coverage tests: `cd apps/backend-rag && pytest --cov=services.rag.agentic.reasoning --cov=app.routers.feedback --cov-report=html`
-   **Sentinel:** The project uses a `sentinel` script for quality control.
    -   Run `./sentinel` to verify integrity before requesting review.
-   **Logs:** Check logs (`fly logs` or local output) to verify behavior.

### 3.4 Fly.io Operations
-   **NEVER run `flyctl` from root.** It will fail due to missing context.
-   **ALWAYS use the helper scripts:**
    -   `./scripts/fly-backend.sh <command>`
    -   `./scripts/fly-frontend.sh <command>`

### 3.5 🚨 NO CI/CD DEPLOYMENT
-   **DIVIETO ASSOLUTO:** Non usare MAI CI/CD automatizzati per il deploy in produzione.
-   **WORKFLOW:** Il deploy è **SOLO MANUALE** e **DA LOCALE** tramite `flyctl deploy`.
-   **MOTIVO:** Manteniamo il controllo totale sulla build e sui tempi di rilascio.

---

## 4. 🧩 KEY FEATURES & MODULES

### 4.1 RAG Engine (Agentic RAG v6.0)
Located in `apps/backend-rag/backend/services/rag/agentic/`. Implements ReAct pattern for intelligent query processing.

**Core Components:**
- **AgenticRagOrchestrator** (`orchestrator.py`): Central brain. Coordinates ReAct loop, tool execution, and response generation.
- **ReasoningEngine** (`reasoning.py`): ReAct loop (Thought→Action→Observation). Native function calling with regex fallback.
- **LLMGateway** (`llm_gateway.py`): Multi-tier LLM cascade: Gemini 3 Flash Preview → 2.0 Flash fallback.
- **Tools** (`tools.py`): VectorSearchTool, PricingTool, TeamKnowledgeTool, CalculatorTool, VisionTool.

**Supporting Services:**
- **SearchService**: Hybrid search (Dense 0.7 + BM25 Sparse 0.3) with federated collection routing.
- **RerankerService**: Ultra-precision re-ranking using ZeroEntropy (zerank-2).
- **GenAIClient** (`llm/genai_client.py`): Unified wrapper for Google's `google-genai` SDK v1.56+.

### 4.2 Intelligent Router
Located in `apps/backend-rag/backend/services/intelligent_router.py`. Orchestrates incoming requests, routing them to the appropriate AI model or tool based on intent.
- Wraps `AgenticRAGOrchestrator` for all chat operations
- Supports streaming via SSE (Server-Sent Events)

### 4.3 Debug & Monitoring Tools
Located in `apps/backend-rag/backend/app/routers/debug.py` and `apps/backend-rag/backend/app/utils/`.

**Debug Endpoints** (`/api/debug/*`):
- Request tracing and correlation IDs
- RAG pipeline debugging
- Database query monitoring
- Qdrant collection inspection
- **PostgreSQL Debug** (NEW): Comprehensive database inspection
  - Connection testing and pool statistics
  - Schema inspection (tables, columns, indexes, foreign keys)
  - Database statistics (sizes, row counts, indexes)
  - Read-only query execution (SELECT only, with security validation)
  - Performance metrics (slow queries, locks, connections)

**Authentication**: All debug endpoints require `ADMIN_API_KEY` (configured in Fly.io secrets).
- Production: Available when `ADMIN_API_KEY` is set
- Development/Staging: Available with `ADMIN_API_KEY` or JWT token

See [Debug Guide](../docs/DEBUG_GUIDE.md) for complete documentation.
- Integrates with CRM context, memory, and agent data

### 4.3 Jaksel Personality Module
A specialized module that applies "Jakarta Selatan" persona to ALL responses.
- **Primary Endpoint:** `https://jaksel.balizero.com` (Oracle Cloud VM + Ollama)
- **Model:** `zantara:latest` (Gemma 9B Fine-tuned)
- **Fallback:** Gemini 3 Flash Preview with style-transfer prompt (now integrated in Agentic RAG)

### 4.4 CRM System
Full-featured Customer Relationship Management:
- **Clients:** CRUD operations, search, filtering
- **Practices:** Service/product management (KITAS, PT PMA, Visas)
- **Interactions:** Call, email, meeting logging
- **Shared Memory:** Team-wide knowledge access
- **Auto-CRM:** AI-powered entity extraction from conversations

### 4.5 Agent System
Autonomous agents for business automation (10 total):
- **Tier 1 Agents:** Conversation Trainer, Client Value Predictor, Knowledge Graph Builder
- **Orchestration Agents:** Client Journey Orchestrator, Proactive Compliance Monitor
- **Advanced Agents:** Autonomous Research Service, Cross-Oracle Synthesis Service, Knowledge Graph Builder
- **Automation Agents:** Auto Ingestion Orchestrator

### 4.6 Plugin System
Located in `apps/backend-rag/backend/core/plugins/`:
- Base plugin interface with lifecycle management
- Auto-discovery from `backend/plugins/` directory
- Current plugins: Bali Zero Pricing, Team Member Search/List

### 4.7 Ultra Hybrid Features (v5.4)
New capabilities for high-trust enterprise responses:
- **Quality Routing:** Automatically selects the best model (Flash vs Pro vs Reasoning) based on intent.
- **Evidence Pack:** All business answers include verifiable citations [1] and source links.
- **Standard Output:** Enforced markdown templates for Visa, Tax, and Company Setup queries.
- **Privacy:** Automated PII redaction in all logs.

### 4.8 Observability Stack

Full monitoring e tracing per production debugging:

| Servizio | Porta | Funzione |
|----------|-------|----------|
| **Prometheus** | 9090 | Metrics collection (scrape 15s) |
| **Grafana** | 3001 | Dashboards e visualizzazione |
| **Alertmanager** | 9093 | Alert routing e notifiche |
| **Jaeger** | 16686 | Distributed tracing (OpenTelemetry) |

**Dashboard Disponibili** (5 totali):
- `rag-dashboard.json` - RAG latency, cache hit rate, tool calls
- `system-health-dashboard.json` - CPU, RAM, uptime
- `qdrant-health-dashboard.json` - Vector DB metrics
- `error-tracking-dashboard.json` - 4xx/5xx per endpoint
- `security-dashboard.json` - Failed logins, rate limits

**Metriche Esposte** (`/metrics`):
```
zantara_rag_pipeline_duration_seconds    # RAG totale
zantara_llm_prompt_tokens_total          # Token usage
zantara_cache_hits_total                 # Cache performance
zantara_http_requests_total              # Request count
```

**Comandi Utili:**
```bash
# Avvia stack monitoring locale
docker compose up prometheus grafana jaeger

# Accesso
open http://localhost:3001   # Grafana (admin/changeme123)
open http://localhost:9090   # Prometheus
open http://localhost:16686  # Jaeger
```

**Alert Critici** (vedi [ALERTS_RUNBOOK.md](operations/ALERTS_RUNBOOK.md)):
- `CriticalQdrantErrorRate` - Error rate > 5% per 2m
- `CriticalQdrantSearchLatency` - Latency > 1000ms per 2m
- `QdrantMetricsEndpointDown` - Backend unreachable

---

## 5. 📁 KEY DIRECTORIES

| Directory | Purpose |
| :--- | :--- |
| `apps/backend-rag/backend/app/routers/` | **34** API routers (213 endpoints) |
| `apps/backend-rag/backend/services/` | **152** business services |
| `apps/backend-rag/backend/services/rag/agentic/` | **Core**: Orchestrator, ReAct, LLM Gateway, Tools |
| `apps/backend-rag/backend/services/memory/` | Memory system (Facts, Episodic, Collective) |
| `apps/backend-rag/backend/core/` | Core utilities (embeddings, chunking, plugins) |
| `apps/backend-rag/backend/llm/` | LLM clients: `genai_client.py` (Google) |
| `apps/backend-rag/backend/migrations/` | **26** database migrations |
| `apps/backend-rag/backend/middleware/` | Auth, rate limiting, error monitoring |
| `apps/mouth/src/app/` | Next.js App Router pages |
| `apps/mouth/src/components/` | React components (shadcn/ui based) |
| `apps/mouth/src/lib/api/` | API client layer (Zantara SDK) |
| `docs/` | Project documentation |
| `scripts/` | Deployment, testing, analysis scripts |

---

## 6. 📖 ESSENTIAL FILES (Read First!)

**Per nuovi AI/sviluppatori - leggi questi file in ordine:**

### Tier 1: Documentazione (5 min)
```
docs/AI_ONBOARDING.md              # ← SEI QUI - Regole e struttura
docs/ai/AI_HANDOVER_PROTOCOL.md    # Golden rules, tech stack
docs/SYSTEM_MAP_4D.md              # Mappa completa del sistema
```

### Tier 2: Configurazione (2 min)
```
apps/backend-rag/backend/app/core/config.py   # Tutte le env vars
apps/backend-rag/fly.toml                      # Deploy config
```

### Tier 3: Core Architecture - Agentic RAG (10 min)
```
apps/backend-rag/backend/services/rag/agentic/
├── orchestrator.py      # Il cervello - coordina tutto
├── reasoning.py         # ReAct loop (Thought→Action→Observation)
├── llm_gateway.py       # LLM cascade (Flash→Lite→OpenRouter)
├── tools.py             # I 5 tool disponibili
└── __init__.py          # Exports pubblici
```

### Tier 4: Entry Points (3 min)
```
apps/backend-rag/backend/app/main_cloud.py              # FastAPI app
apps/backend-rag/backend/services/intelligent_router.py # Request routing
apps/backend-rag/backend/services/memory/orchestrator.py # Memory system
```

---

## 7. 🚀 IMMEDIATE ACTION PROTOCOL

1.  **Read Essential Files:** Segui l'ordine in Section 6 sopra.
2.  **Context Acquisition:** Read `task.md` (if present) to understand the current objective.
3.  **Architecture Reference:** Check `docs/LIVING_ARCHITECTURE.md` for auto-generated API documentation.
4.  **Environment Check:** Verify that critical environment variables (API keys, DB URLs) are loaded.
5.  **Execution:** Proceed with your task, adhering strictly to the standards above.

**Maintain the standard. Build for the future.**

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

The project is a **Monorepo** managed with `pnpm workspaces` (unified package manager) and Docker.
For a complete 4D understanding of the system (Space, Time, Logic, Scale), refer to [docs/SYSTEM_MAP_4D.md](docs/SYSTEM_MAP_4D.md).

### 2.1 Core Services

| Service | Path | Stack | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Backend RAG** | `apps/backend-rag` | **Python 3.11+** (FastAPI) | ✅ **PRIMARY** | The central intelligence engine. 38 routers (250 endpoints), 169 services, 32 migrations (65+ tables). Handles Agentic RAG (ReAct pattern), AI orchestration, Vector DB (Qdrant), CRM, and business logic. |
| **Frontend** | `apps/mouth` | **Next.js 16** (React 19) | ✅ **PRIMARY** | The modern user interface. Uses Tailwind CSS 4, TypeScript, shadcn/ui components, and lightweight state management. |
| **Intel Scraper** | `apps/bali-intel-scraper` | **Python 3.11** | ✅ **ACTIVE** | News processing pipeline: RSS → Scoring → Claude Validation → Enrichment → Image Gen → SEO/AEO → Telegram Approval → Publish. Cost: ~$0.06/article. |


### 2.2 Infrastructure
- **Database:** PostgreSQL (asyncpg with connection pooling, 65+ tables), Qdrant Cloud (Vector, **54,154 documents** across 7 active collections), Redis (Cache/Queue).
- **Deployment:** Fly.io (Docker-based, multi-region Singapore).
- **Testing & Deployment:** Local testing and manual deployment workflow. All testing and deployment is done locally - no automated CI/CD pipelines. Deploy via `flyctl deploy` from local machine.
- **Observability:** Prometheus, Grafana, Jaeger, Alertmanager.

### 2.3 Qdrant Collections (Knowledge Base)

| Collezione | Docs | Scopo | Query Router Keywords |
|------------|------|-------|----------------------|
| `visa_oracle` | ~1,612 | Immigration, KITAS, KITAP | visa, kitas, kitap, immigration |
| `legal_unified_hybrid` | ~5,041 | Laws, regulations (PP, UU) | legal, law, regulation |
| `kbli_unified` | ~8,886 | Business classification codes | kbli, business code |
| `tax_genius` | 332 | PPh 21, PPN/VAT, taxes | tax, pajak, pph, ppn |
| `bali_zero_pricing` | ~29 | Service pricing | price, cost, quanto costa |
| `bali_zero_team` | ~22 | Team members | team, who, contact |

**Routing:** `backend/services/routing/query_router.py` routes queries to collections based on keywords.
**Ingestion:** Use `scripts/ingest_tax_genius.py` as template for new collections.

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
-   **Data vs. Logic (Knowledge Governance):**
    -   **NO Hardcoded Volatile Data:** Business facts belong in the Knowledge Base, not the Python/TS logic.
    -   **Prices:** Never write specific prices (e.g., `price = "10M"`) in code.
    -   **Identity/Team:** Never hardcode employee names or specific roles in logic checks.
    -   **Regulations:** Specific visa/tax numbers or thresholds must be retrieved via RAG.
    -   **Contact/Location:** Use `settings` or KB for addresses and phone numbers.
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

### 3.5 🚨 SEMI-AUTOMATED CI/CD
-   **DIVIETO ASSOLUTO:** Non usare MAI CI/CD automatizzati per il deploy in produzione.
-   **PIPELINE:** La CI (GitHub Actions) esegue **verifiche obbligatorie** (Lint, Test, Security).
-   **DEPLOY:** Il deploy è **SOLO MANUALE** e **DA LOCALE** tramite `flyctl deploy`.
-   **MOTIVO:** Manteniamo il controllo totale sulla build e sui tempi di rilascio.

---

## 4. 🧩 KEY FEATURES & MODULES

### 4.1 RAG Engine (Agentic RAG v6.5)
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

Full monitoring, tracing, e quality control per production debugging:

| Servizio | Porta | Funzione | Auto-Start |
|----------|-------|----------|------------|
| **Prometheus** | 9090 | Metrics collection (scrape 15s) | `docker compose up` |
| **Grafana** | 3001 | Dashboards (auto-provisioned) | `docker compose up` |
| **Alertmanager** | 9093 | Alert routing e notifiche | `docker compose up` |
| **Jaeger** | 16686 | Distributed tracing (OpenTelemetry) | `docker compose up` |
| **SonarQube** | 9000 | Code quality analysis | `docker compose up` |

**Grafana Dashboard Auto-Provisioning:**
I dashboard sono caricati automaticamente all'avvio. Non serve import manuale.

**Dashboard Disponibili** (6 totali in `config/grafana/dashboards/`):
- `rag-dashboard.json` - RAG latency, cache hit rate, tool calls
- `system-health-dashboard.json` - CPU, RAM, uptime
- `qdrant-health-dashboard.json` - Vector DB metrics
- `error-tracking-dashboard.json` - 4xx/5xx per endpoint
- `security-dashboard.json` - Failed logins, rate limits
- `lock-contention-dashboard.json` - Race conditions, memory locks

**Metriche Esposte** (`/metrics` - ~50 metriche Prometheus):
```
zantara_rag_pipeline_duration_seconds    # RAG totale
zantara_llm_prompt_tokens_total          # Token usage
zantara_cache_hits_total                 # Cache performance
zantara_http_requests_total              # Request count
zantara_memory_lock_contention_seconds   # Lock contention
zantara_llm_fallback_count_total         # Model fallbacks
```

**Comandi Utili:**
```bash
# Avvia TUTTO lo stack monitoring
docker compose up prometheus grafana alertmanager jaeger sonarqube

# Accesso UI
open http://localhost:3001   # Grafana (admin/changeme123)
open http://localhost:9090   # Prometheus
open http://localhost:9093   # Alertmanager
open http://localhost:16686  # Jaeger
open http://localhost:9000   # SonarQube (admin/admin)
```

**Alert Critici** (vedi [ALERTS_RUNBOOK.md](operations/ALERTS_RUNBOOK.md)):
- `CriticalQdrantErrorRate` - Error rate > 5% per 2m
- `CriticalQdrantSearchLatency` - Latency > 1000ms per 2m
- `QdrantMetricsEndpointDown` - Backend unreachable

### 4.9 Sentinel (Quality Control)

**Sentinel** è il guardian della qualità del codice. Esegui SEMPRE prima di chiedere review.

```bash
# Esegui quality check completo
./sentinel

# Output salvato in: sentinel-results/sentinel-run-TIMESTAMP.log
```

**Fasi Sentinel:**
1. **Auto-Healing** - Ruff linting + formatting automatico
2. **Testing** - Pytest con coverage
3. **Health Checks** - Qdrant connectivity

**Enhanced Mode** (opzionale - richiede setup):
```bash
# Installa tool avanzati (semgrep + codeql)
./scripts/setup-deep-analysis.sh

# Poi sentinel userà automaticamente la modalità enhanced
./sentinel
```

### 4.10 Intel Scraper Pipeline (BaliZero News)

Located in `apps/bali-intel-scraper/scripts/`. Automated news processing for BaliZero.

**Pipeline Flow (7 Steps):**
```
RSS Fetcher → LLAMA Scorer → Claude Validator → Claude Enricher →
Image Generator → SEO/AEO Optimizer → Telegram Approval → Publish
```

**Key Components:**

| Step | File | Purpose | Cost |
|------|------|---------|------|
| 1. RSS Fetch | `rss_fetcher.py` | Fetch from RSS feeds | $0 |
| 2. Scoring | `professional_scorer.py` | Keyword scoring + heuristics | $0 |
| 3. Validation | `claude_validator.py` | AI gate for ambiguous articles | ~$0.01 |
| 4. Enrichment | `article_deep_enricher.py` | Full article rewrite, Executive Brief | ~$0.05 |
| 5. Image | `gemini_image_generator.py` | Cover image via Gemini | $0 |
| 5.5. SEO/AEO | `seo_aeo_optimizer.py` | Schema.org, meta tags, FAQ, entities | $0 |
| 6. Approval | `telegram_approval.py` | Telegram notification with buttons | $0 |
| 7. Publish | `intel_pipeline.py` | POST to BaliZero API | $0 |

**SEO/AEO Optimizer (NEW):**
Optimizes for both traditional search (Google, Bing) AND AI search engines (ChatGPT, Claude, Perplexity, Gemini):
- Schema.org JSON-LD (Article, FAQ, Organization, Breadcrumb)
- OpenGraph and Twitter meta tags
- TL;DR summary for AI citation
- FAQ generation for featured snippets
- Entity extraction for knowledge graphs
- Keyword extraction

**Documentation:** `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md`

### 4.11 Telegram Integration

**Bot:** `@zantara_bot`

**Approval System:**
- Sends HTML preview of articles before publishing
- Inline buttons: ✅ Approve | ❌ Reject | ✏️ Request Changes
- Multi-recipient support (comma-separated chat IDs)
- HTML preview looks like final published article

**Configuration (Fly.io Secrets):**
```bash
# View current secrets
fly secrets list -a nuzantara-rag

# Set Telegram approval chat ID
fly secrets set TELEGRAM_APPROVAL_CHAT_ID=8290313965 -a nuzantara-rag

# For multiple recipients
fly secrets set TELEGRAM_APPROVAL_CHAT_ID="8290313965,ANOTHER_ID" -a nuzantara-rag
```

**Current Approvers:**
- Zero (Chat ID: 8290313965)
- Dea (Chat ID: 6217157548)
- Damar (Chat ID: 1813875994)

**Local Development:**
Create `.env` in `apps/bali-intel-scraper/`:
```bash
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}  # From Fly.io secrets
TELEGRAM_CHAT_ID=8290313965
PREVIEW_BASE_URL=https://balizero.com/preview
```

---

## 5. 📁 KEY DIRECTORIES

| Directory | Purpose |
| :--- | :--- |
| `apps/backend-rag/backend/app/routers/` | **38** API routers (250 endpoints) |
| `apps/backend-rag/backend/services/` | **169** business services |
| `apps/backend-rag/backend/services/rag/agentic/` | **Core**: Orchestrator, ReAct, LLM Gateway, Tools |
| `apps/backend-rag/backend/services/memory/` | Memory system (Facts, Episodic, Collective) |
| `apps/backend-rag/backend/core/` | Core utilities (embeddings, chunking, plugins) |
| `apps/backend-rag/backend/llm/` | LLM clients: `genai_client.py` (Google) |
| `apps/backend-rag/backend/migrations/` | **32** database migrations |
| `apps/backend-rag/backend/middleware/` | Auth, rate limiting, error monitoring |
| `apps/mouth/src/app/` | Next.js App Router pages |
| `apps/mouth/src/components/` | React components (shadcn/ui based) |
| `apps/mouth/src/lib/api/` | API client layer (Zantara SDK) |
| `apps/bali-intel-scraper/scripts/` | Intel pipeline: RSS, scoring, enrichment, SEO, Telegram |
| `apps/bali-intel-scraper/docs/` | Pipeline documentation |
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

## 7. 🚨 CRITICAL FIXES (Dec 2025) - MUST READ

> **ATTENZIONE:** Prima di modificare `reasoning.py` o il sistema di evidence scoring, leggi:
> `docs/operations/AGENTIC_RAG_FIXES.md`

### 7.1 Evidence Score System

Il sistema usa un **evidence_score** (0.0-1.0) per decidere se rispondere:

| Soglia | Valore | Comportamento |
|--------|--------|---------------|
| **ABSTAIN** | < 0.3 | Rifiuta di rispondere |
| **WEAK** | 0.3-0.6 | Risponde con cautela |
| **CONFIDENT** | > 0.6 | Risposta normale |

### 7.2 Trusted Tools (Bypass Evidence Check)

Questi tool bypassano l'evidence check perché forniscono evidence propria:

| Tool | Descrizione | File |
|------|-------------|------|
| `calculator` | Calcoli matematici | `tools.py` |
| `get_pricing` | Prezzi servizi | `zantara_tools.py` |
| `team_knowledge` | Team members | `zantara_tools.py` |

**NON modificare il trusted tools check senza capire il flusso completo.**

### 7.3 Fix Recenti Applicati

| Data | Fix | File | Versione |
|------|-----|------|----------|
| 2025-12-30 | Evidence threshold 0.8→0.3 | `reasoning.py` | v1175 |
| 2025-12-31 | Trusted tools bypass | `reasoning.py` | v1177 |
| 2025-12-31 | LLM Gateway images param | `llm_gateway.py` | v1178 |
| 2025-12-31 | Image gen URL cleaning | `chat.api.ts` | v1179 |

### 7.4 Debug Patterns nei Log

```bash
fly logs -a nuzantara-rag | grep -E "Evidence|Trusted|ABSTAIN"
```

| Pattern | Significato |
|---------|-------------|
| `🛡️ [Uncertainty] Evidence Score: X.XX` | Score calcolato |
| `🧮 [Trusted Tool] X used successfully` | Bypass attivo |
| `🛡️ [Uncertainty] Triggered ABSTAIN` | Sistema rifiuta |
| `🔧 [Native Function Call] Detected: X` | Tool chiamato |

---

## 8. 🔧 TROUBLESHOOTING COMUNI

### 8.1 "Mi dispiace, non ho trovato informazioni..."

**Causa:** Evidence score < 0.3 e nessun trusted tool usato.

**Diagnosi:**
```bash
fly logs -a nuzantara-rag | grep "Evidence Score"
```

**Soluzioni:**
1. Verifica che le collezioni Qdrant abbiano documenti rilevanti
2. Se è un calcolo/prezzo/team, verifica che il tool giusto sia stato chiamato
3. Controlla `trusted_tool_names` in `reasoning.py`

### 8.2 "Sorry, there was an error processing your request"

**Causa:** Errore interno nel backend (LLM, tool, o parametri).

**Diagnosi:**
```bash
fly logs -a nuzantara-rag | grep -E "Error|Exception|TypeError"
```

**Cause comuni:**
- `TypeError: unexpected keyword argument` → Parametro mancante in funzione
- `ResourceExhausted` → Quota LLM esaurita, fallback dovrebbe attivarsi
- `Connection refused` → Qdrant/Postgres non raggiungibile

### 8.3 Frontend mostra "Offline"

**Causa:** SSE connection intermittente o backend non risponde.

**Soluzioni:**
1. Verifica health: `curl https://nuzantara-rag.fly.dev/health`
2. Ricarica la pagina
3. Controlla logs per errori di connessione

### 8.4 Tool non viene chiamato

**Causa:** LLM non riconosce l'intent o tool non registrato.

**Diagnosi:**
```bash
fly logs -a nuzantara-rag | grep "Native Function Call"
```

**Soluzioni:**
1. Verifica che il tool sia in `gemini_tools` nel `LLMGateway`
2. Controlla la descrizione del tool (deve essere chiara per l'LLM)
3. Verifica `tool_config` in `llm_gateway.py`

---

## 9. 🚀 IMMEDIATE ACTION PROTOCOL

1.  **Read Essential Files:** Segui l'ordine in Section 6 sopra.
2.  **Read Critical Fixes:** Leggi Section 7 per i fix recenti.
3.  **Context Acquisition:** Read `task.md` (if present) to understand the current objective.
4.  **Architecture Reference:** Check `docs/LIVING_ARCHITECTURE.md` for auto-generated API documentation.
5.  **Environment Check:** Verify that critical environment variables (API keys, DB URLs) are loaded.
6.  **Execution:** Proceed with your task, adhering strictly to the standards above.

**Maintain the standard. Build for the future.**

---

## 10. 📚 DOCUMENTATION INDEX

| Doc | Path | Quando Leggerlo |
|-----|------|-----------------|
| AI Onboarding | `docs/AI_ONBOARDING.md` | Sempre all'inizio |
| System Map 4D | `docs/SYSTEM_MAP_4D.md` | Per capire architettura |
| **Agentic RAG Fixes** | `docs/operations/AGENTIC_RAG_FIXES.md` | Prima di toccare reasoning.py |
| **Observability Guide** | `docs/operations/OBSERVABILITY_GUIDE.md` | Per debugging e monitoring |
| AI Handover Protocol | `docs/ai/AI_HANDOVER_PROTOCOL.md` | Per golden rules |
| Deploy Checklist | `docs/operations/DEPLOY_CHECKLIST.md` | Prima di deploy |
| Alerts Runbook | `docs/operations/ALERTS_RUNBOOK.md` | Quando scattano alert |
| **Intel Pipeline** | `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md` | Per scraper news + SEO/AEO + Telegram |

---

**Last Updated:** 2026-01-04 | **Deployed Version:** v1180

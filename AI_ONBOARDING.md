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

---

## 2. 🏗️ SYSTEM ARCHITECTURE

The project is a **Monorepo** managed with `npm workspaces` and Docker.

### 2.1 Core Services

| Service | Path | Stack | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Backend RAG** | `apps/backend-rag` | **Python 3.11+** (FastAPI) | ✅ **PRIMARY** | The central intelligence engine. 216 Python files, 27 routers, 73 services, 8 migrations. Handles RAG, AI orchestration, Vector DB (Qdrant), CRM, and business logic. |
| **Frontend** | `apps/mouth` | **Next.js 16** (React 19) | ✅ **PRIMARY** | The modern user interface. Uses Tailwind CSS 4, TypeScript, shadcn/ui components, and lightweight state management. |


### 2.2 Infrastructure
- **Database:** PostgreSQL (asyncpg with connection pooling), Qdrant Cloud (Vector, ~25k documents), Redis (Cache/Queue).
- **Deployment:** Fly.io (Docker-based, multi-region Singapore).
- **Testing & Deployment:** Local testing and manual deployment workflow (see [docs/WORKFLOW.md](docs/WORKFLOW.md)). All testing and deployment is done locally - no automated CI/CD pipelines.
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
-   **Sentinel:** The project uses a `sentinel` script for quality control.
    -   Run `./sentinel` to verify integrity before requesting review.
-   **Logs:** Check logs (`fly logs` or local output) to verify behavior.

### 3.4 Fly.io Operations
-   **NEVER run `flyctl` from root.** It will fail due to missing context.
-   **ALWAYS use the helper scripts:**
    -   `./scripts/fly-backend.sh <command>`
    -   `./scripts/fly-frontend.sh <command>`

---

## 4. 🧩 KEY FEATURES & MODULES

### 4.1 RAG Engine
Located in `apps/backend-rag/backend/services/`. Handles context retrieval from Qdrant to ground AI responses in business data.
- **SearchService**: Multi-collection vector search with tier-based access control
- **AgenticRagOrchestrator**: Central brain (v2). Routes queries (Fast/Pro/DeepThink), orchestrates Hybrid Search + Reranking, and generates Evidence Packs.
- **GoldenRouterService**: High-confidence answer routing
- **RerankerService**: Ultra-precision re-ranking using ZeroEntropy (zerank-2) or Jina v2.

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
- **Fallback:** Gemini 2.5 Flash with style-transfer prompt (now integrated in Agentic RAG)

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

---

## 5. 📁 KEY DIRECTORIES

| Directory | Purpose |
| :--- | :--- |
| `apps/backend-rag/backend/app/routers/` | 27 API routers |
| `apps/backend-rag/backend/services/` | 73 business services |
| `apps/backend-rag/backend/core/` | Core utilities (embeddings, chunking, plugins) |
| `apps/backend-rag/backend/llm/` | LLM client wrapper, retry handler, prompt manager |
| `apps/backend-rag/backend/migrations/` | 8 database migrations |
| `apps/backend-rag/backend/middleware/` | Auth, rate limiting, error monitoring |
| `apps/mouth/src/app/` | Next.js App Router pages |
| `apps/mouth/src/components/` | React components (shadcn/ui based) |
| `apps/mouth/src/lib/api/` | API client layer |
| `apps/mouth/src/lib/store/` | Zustand state management |
| `docs/` | Project documentation (100+ files) |
| `scripts/` | Deployment, testing, analysis scripts |
| `config/` | Prometheus, Alertmanager configuration |

---

## 6. 🚀 IMMEDIATE ACTION PROTOCOL

1.  **Context Acquisition:** Read `task.md` (if present) to understand the current objective.
2.  **Architecture Reference:** Check `docs/LIVING_ARCHITECTURE.md` for auto-generated API documentation.
3.  **Environment Check:** Verify that critical environment variables (API keys, DB URLs) are loaded.
4.  **Execution:** Proceed with your task, adhering strictly to the standards above.

**Maintain the standard. Build for the future.**

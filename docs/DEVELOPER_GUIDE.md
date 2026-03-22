# Developer Onboarding Guide — Nuzantara

**Version:** 5.2.0
**Last Updated:** 2026-02-26
**Audience:** New developers and AI assistants joining the project

---

## What is Nuzantara?

Nuzantara (codename "Zantara") is a production AI-powered business intelligence platform for **Bali Zero**, an Indonesian business consulting firm. It provides:

- **AI Chat** across 5 channels (Web, Telegram, WhatsApp, Instagram, Twitter/X)
- **KBLI Navigator** — Indonesian business classification search and analysis
- **CRM** — Client and practice management with RBAC
- **Client Portal** — Self-service document uploads and status tracking
- **Knowledge Graph** — 56,113 nodes, 161,173 edges of Indonesian business regulations
- **RAG Pipeline** — Agentic Retrieval-Augmented Generation with tool use

**Production URLs:**

- Frontend: https://kita.balizero.com (Vercel)
- Backend: https://nuzantara-rag.fly.dev (Fly.io, Singapore)
- API Docs: https://nuzantara-rag.fly.dev/docs (Swagger)

---

## Prerequisites

| Tool       | Version | Purpose                        |
| ---------- | ------- | ------------------------------ |
| Python     | 3.11+   | Backend                        |
| Node.js    | 20+     | Frontend                       |
| Git        | 2.40+   | Version control                |
| Fly CLI    | latest  | Backend deployment             |
| Vercel CLI | latest  | Frontend deployment (optional) |
| Docker     | latest  | Qdrant local (optional)        |

---

## Repository Structure

```
nuzantara/                              # Monorepo root
├── apps/
│   ├── backend-rag/                    # Python FastAPI backend (Fly.io)
│   │   ├── backend/
│   │   │   ├── app/                    # FastAPI app
│   │   │   │   ├── core/              # Config, constants, logging
│   │   │   │   ├── modules/           # Feature modules (notifications, knowledge, CRM)
│   │   │   │   ├── routers/           # 83+ API route files
│   │   │   │   └── setup/             # App factory, service init, router registration
│   │   │   ├── channels/             # Chat channel adapters (Telegram, WhatsApp, etc.)
│   │   │   ├── db/                    # Database repositories
│   │   │   ├── generals/             # Multi-agent task system
│   │   │   ├── middleware/            # Auth, logging, rate limiting, error monitoring
│   │   │   ├── migrations/           # Database migrations (V2 system)
│   │   │   ├── services/             # 228+ business logic services
│   │   │   │   ├── rag/agentic/      # Core: Orchestrator, ReAct loop, LLM Gateway
│   │   │   │   ├── knowledge_graph/  # KG extraction pipeline
│   │   │   │   ├── memory/           # 3-tier memory system
│   │   │   │   ├── crm/              # CRM business logic
│   │   │   │   └── integrations/     # Google Drive, Zoho
│   │   │   └── tests/                # 477 test files
│   │   ├── Dockerfile
│   │   ├── fly.toml
│   │   └── requirements.txt
│   │
│   ├── mouth/                          # Next.js frontend (Vercel)
│   │   └── src/
│   │       ├── app/                   # App Router pages
│   │       ├── components/            # React components
│   │       ├── hooks/                 # Custom hooks (useChatStreaming, etc.)
│   │       └── lib/                   # API clients, utilities
│   │
│   ├── nuzantara-mcp/                 # MCP Server (7 tools, 3 prompts)
│   ├── bali-intel-scraper/            # News/intelligence pipeline
│   └── kbli-voice/                    # KBLI decision engine
│
├── docs/                               # Documentation (you are here)
├── data/source_documents/              # KBLI JSON, legal PDFs
└── CLAUDE.md                           # AI assistant configuration
```

---

## Getting Started

### Backend Setup

```bash
# 1. Clone and enter
cd apps/backend-rag

# 2. Create virtualenv (MANDATORY — Golden Rule #1)
python3.11 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Set environment variables
export DATABASE_URL="postgres://..."
export QDRANT_URL="http://localhost:6333"
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."
export JWT_SECRET="dev-secret"
export EMBEDDING_MODEL="text-embedding-3-small"

# 5. Run backend
PYTHONPATH=. python -m uvicorn backend.app.main_cloud:app --reload --port 8000

# 6. Verify
curl http://localhost:8000/health
```

### Frontend Setup

```bash
cd apps/mouth
npm install
npm run dev
# Open http://localhost:3000
```

### Running Tests

```bash
cd apps/backend-rag
source venv/bin/activate

# Core tests (MUST pass — 82 tests, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q

# Channel tests (43 tests)
PYTHONPATH=. pytest backend/tests/channels/ -q

# All RAG tests (244 tests)
PYTHONPATH=. pytest backend/tests/services/rag/ -q

# Frontend tests
cd apps/mouth && npm test
```

**Note:** Test debt cleaned 2026-03-20 (0 failures). Previously ~448 pre-existing failures from rogue AI refactors, resolved by Windsurf cleanup.

---

## The 10 Golden Rules

These exist because we hit real production problems without them.

| #   | Rule                      | Why                                                  |
| --- | ------------------------- | ---------------------------------------------------- |
| 1   | **Virtualenv mandatory**  | System Python conflicts cause cryptic import errors  |
| 2   | **No root execution**     | Use `PYTHONPATH=. python -m backend.module`          |
| 3   | **Absolute imports only** | `from backend.core import config`, never relative    |
| 4   | **Async first**           | Use `httpx`, never `requests`. All I/O must be async |
| 5   | **Type hints required**   | Every function must have full type annotations       |
| 6   | **No hardcoded secrets**  | Use `os.getenv()` or secrets manager                 |
| 7   | **Data/logic separation** | Business logic separate from data access             |
| 8   | **Clean logging**         | `logger.info()`, never `print()`                     |
| 9   | **Quality standards**     | Tests + error handling for production features       |
| 10  | **Verify sources**        | Never presume — check actual data before concluding  |

---

## Architecture Overview

### Request Flow (Chat Query)

```
User sends message
        │
        ▼
┌─────────────────┐
│  Channel Adapter │  (Telegram/WhatsApp/Web/Instagram/Twitter)
│  Normalize input │
└────────┬────────┘
         │ ChannelMessage
         ▼
┌─────────────────┐
│ ConversationEngine│  (channel-agnostic processing)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│            AgenticRAGOrchestrator                │
│                                                  │
│  1. Query Gates (security, greetings, FAQ)      │
│  2. Intent Routing (Flash/Pro/DeepThink)        │
│  3. Context: Entity + KG + Memory (parallel)    │
│  4. System Prompt Construction                   │
│  5. LLM Gateway: Gemini Pro→Flash→Lite→OpenRouter│
│  6. ReAct Loop: Think→Tool→Observe→...→Answer   │
│  7. Evidence Scoring (ABSTAIN if <0.15)         │
│  8. Analytics Logging                            │
└────────┬────────────────────────────────────────┘
         │ CoreResult
         ▼
┌─────────────────┐
│  Channel Adapter │  (format for platform constraints)
│  Send response   │
└─────────────────┘
```

### Key Subsystems

| Subsystem            | Key Files                                   | Purpose                                        |
| -------------------- | ------------------------------------------- | ---------------------------------------------- |
| **Orchestrator**     | `services/rag/agentic/orchestrator*.py`     | 7 manager classes for query processing         |
| **LLM Gateway**      | `services/rag/agentic/llm_gateway.py`       | Multi-provider fallback (Gemini→OpenRouter)    |
| **Evidence Scoring** | `services/rag/agentic/reasoning.py`         | Confidence thresholds, ABSTAIN capability      |
| **Memory**           | `services/memory/orchestrator.py`           | 3-tier: personal facts + collective + episodic |
| **Knowledge Graph**  | `services/knowledge_graph/pipeline.py`      | NLP extraction, coreference, quality filter    |
| **KG LangGraph**     | `services/rag/kg_langgraph_orchestrator.py` | BFS traversal, domain subgraphs (feature flag) |
| **Channels**         | `channels/base.py` + adapters               | Abstract channel → concrete adapters           |
| **Generals**         | `generals/task_coordinator.py`              | Multi-agent task queue (PostgreSQL-backed)     |
| **Auth**             | `middleware/hybrid_auth.py`                 | Fail-closed, 3 auth methods, public whitelist  |

---

## Critical Knowledge

### Embedding Model (FROZEN)

**Model:** `text-embedding-3-small` (OpenAI, 1536 dimensions)

This is **immutable**. Changing it would invalidate all 58,880 vectors across 7 Qdrant collections. If search quality seems poor, the embedding model mismatch is the first thing to check:

```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool | grep model
# Must return: "text-embedding-3-small"
```

### KBLI Flat Payload

The `kbli_2025_final` Qdrant collection uses **flat payloads** (not nested under `metadata`/`text`). The KBLI router queries Qdrant directly, bypassing `SearchService`.

```json
{
  "kode_kbli": "56101",
  "judul": "Restoran",
  "content": "...",
  "pma_status": "Terbuka"
}
```

### Pricing Source of Truth

All client-facing prices come from `PricingTool` (backed by `bali_zero_official_prices_2025.json`). The Knowledge Graph contains government fees (PNBP), not Bali Zero prices. **Never expose KG fees to clients.**

### Auth Middleware (Fail-Closed)

`hybrid_auth.py` returns 503 (not 200) on any internal error. Public endpoints are explicitly whitelisted. Adding a new public endpoint requires a documented justification.

---

## Common Development Workflows

### Adding a New API Endpoint

1. Create router in `backend/app/routers/new_feature.py`
2. Add business logic in `backend/services/new_feature/`
3. Register router in `backend/app/setup/router_registration.py`:
   ```python
   from backend.app.routers import new_feature
   app.include_router(new_feature.router, prefix="/api/new-feature", tags=["New Feature"])
   ```
4. Add tests in `backend/tests/`
5. If endpoint should be public, add to `hybrid_auth.py` public endpoints list **with justification comment**

### Modifying the RAG Pipeline

Read first:

- `services/rag/agentic/orchestrator.py` — entry point
- `services/rag/agentic/reasoning.py` — evidence scoring
- `services/rag/agentic/tools.py` — available tools

The orchestrator is split into 7 files. Start from `orchestrator.py` and follow the delegation chain.

### Adding a New Chat Channel

1. Create adapter in `channels/new_channel/adapter.py`
2. Implement 4 abstract methods from `BaseChannel`:
   - `receive_message(raw_event)` → `ChannelMessage`
   - `send_response(channel_id, response)` → void
   - `send_status_update(channel_id, status)` → void
   - `stream_response(channel_id, stream)` → void
3. Set 4 abstract properties: `channel_name`, `supports_markdown`, `supports_media`, `max_message_length`
4. Register in `ChannelRouter`
5. Add webhook route in `routers/`

### Running Database Migrations

```bash
cd apps/backend-rag
source venv/bin/activate

# Create new migration
# File goes in backend/migrations/ with sequential number
# Follow the pattern in existing migrations

# Apply all pending migrations
PYTHONPATH=. python -m backend.db.migrate apply-all
```

---

## Deployment

### Backend (Fly.io)

```bash
# 1. Pre-deploy checks (MANDATORY)
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q

# 2. Deploy
fly deploy -a nuzantara-rag --strategy rolling

# 3. Post-deploy verification
sleep 60  # wait for init
curl -s https://nuzantara-rag.fly.dev/health
```

### Frontend (Vercel)

Auto-deploys from `apps/mouth/` on push to `main`. No manual deploy needed.

### Git Commits

Pre-commit hooks run prettier on all files. Use `--no-verify` for non-JS commits:

```bash
git commit --no-verify -m "fix: restore missing import in dependencies.py"
```

---

## Debugging

### Check Evidence Scoring

```bash
fly logs -a nuzantara-rag | grep -E "Evidence|Trusted|ABSTAIN"
```

### Check Embedding Model

```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool | grep model
```

### Import Chain Test (Most Important Single Check)

```bash
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

If this fails, the entire production app will crash at startup.

### Slow Query Investigation

```bash
# Check latency
curl -s https://nuzantara-rag.fly.dev/api/monitoring/latency?days=1

# Check RAG quality
curl -s https://nuzantara-rag.fly.dev/api/monitoring/retrieval-quality?time_range=1h
```

---

## Key Documentation

| Document                   | Path                                    | When to Read              |
| -------------------------- | --------------------------------------- | ------------------------- |
| **This Guide**             | `docs/DEVELOPER_GUIDE.md`               | First day                 |
| **API Reference**          | `docs/API_REFERENCE.md`                 | Building integrations     |
| **Architecture Decisions** | `docs/ARCHITECTURE_DECISION_RECORDS.md` | Understanding "why"       |
| **Operations Runbook**     | `docs/RUNBOOK.md`                       | Incidents and deployments |
| **AI Onboarding**          | `docs/AI_ONBOARDING.md`                 | AI assistant setup        |
| **CLAUDE.md**              | `CLAUDE.md` (root)                      | Claude Code configuration |
| **KG Architecture**        | `docs/KG_LANGGRAPH_ARCHITECTURE.md`     | Knowledge Graph deep dive |
| **Database Architecture**  | `docs/DATABASE_ARCHITECTURE_V2.md`      | Schema reference          |

---

## FAQ

**Q: Why do ~448 unit tests fail?**
A: Pre-existing failures from rogue AI refactors (Gemini, Windsurf, Cursor). They removed imports, renamed functions, and deleted modules. Core tests (KG, Channels, RAG) are 100%. The unit test debt is tracked but not prioritized.

**Q: Why only 1 uvicorn worker?**
A: ML models (torch, sentence-transformers) consume ~2GB each. With a 2GB VM, even 1 worker is tight. See ADR-009.

**Q: Why Gemini instead of GPT-4?**
A: Cost. Gemini Flash is 5-10x cheaper for equivalent quality on our domain. OpenAI is only used for embeddings. See ADR-001.

**Q: Why is the KG LangGraph disabled?**
A: Feature flag (`ENABLE_KG_LANGGRAPH`). It's fully tested (82/82) but behind a flag for gradual rollout. See ADR-011.

**Q: How do I add a new public endpoint?**
A: Add to the whitelist in `middleware/hybrid_auth.py` with a comment explaining why it must be public. All other endpoints are authenticated by default (fail-closed).

**Q: Why `--no-verify` on git commits?**
A: Pre-commit hooks run prettier on ALL files, including Python and Markdown. Prettier fails on non-JS files. This is a known issue, not a hack.

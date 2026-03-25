# Nuzantara v5.2.0

Production AI-powered business intelligence platform for **Bali Zero** — Indonesian business services (visa, company setup, tax, property) in Bali, serving 5,000+ clients.

**Live:** [kita.balizero.com](https://kita.balizero.com)

## Architecture

Monorepo with 20 apps, powered by agentic RAG with Knowledge Graph.

```
nuzantara/
├── apps/
│   ├── backend-rag/          # Python FastAPI — RAG, KG, 88 routers, 244 services
│   ├── mouth/                # Next.js frontend — kita/my/prime.balizero.com
│   ├── nuzantara-mcp/        # MCP server v2.1 — 131 tools, 10 prompts, 8 chains
│   ├── nuzantara-mcp-advanced/ # Fly.io ops, diagnostics (14 tools)
│   ├── admin-dashboard/      # Admin UI (Next.js)
│   ├── bali-intel-scraper/   # Intel pipeline (local Pro, OpenClaw cron)
│   ├── evaluator/            # QA + Core Guardian V3
│   ├── war-room/             # Ops dashboard + Canva automation
│   ├── calendar/             # calendar.balizero.com
│   ├── drive/                # drive.balizero.com
│   ├── knowledge/            # knowledge.balizero.com
│   ├── mail/                 # mail.balizero.com
│   ├── web/                  # zantara.balizero.com
│   └── ...                   # graph-engine, kbli-voice, kbli-navigator, webapp
├── packages/
│   ├── core/                 # Shared libs + BZ design tokens
│   └── kb/                   # Knowledge base
├── docs/                     # Technical & operational docs
├── config/                   # Prometheus, Grafana, alerts
├── scripts/                  # Deploy, maintenance, analysis
└── data/                     # Shared datasets
```

## Tech Stack

<!-- DOCSYNC:TECH_STATS_START -->

| Layer               | Technology                                                          |
| ------------------- | ------------------------------------------------------------------- |
| **Backend**         | Python 3.11, FastAPI, 89 routers, 251 services                      |
| **Frontend**        | Next.js, TypeScript, Tailwind CSS                                   |
| **Databases**       | PostgreSQL (relational), Qdrant v1.17.0 (vector), Redis (cache)     |
| **Infrastructure**  | Fly.io (backend, Singapore), Vercel (frontend)                      |
| **LLM**             | Gemini 2.5 Flash (primary), Gemini 2.0 Flash (fallback), OpenRouter |
| **Embedding**       | `text-embedding-3-small` (1536 dims) — FROZEN                       |
| **Knowledge Graph** | 56,113 nodes, 161,173 edges, LangGraph orchestrator                 |
| **Vector Store**    | 10 collections, 93,283 documents                                    |

<!-- DOCSYNC:TECH_STATS_END -->

| **Vector Store** | 10 collections, 93,283 documents |

## Search Pipeline (enabled 2026-03-24)

```
Query → KeywordTranslator (IT→EN/ID, ~80 terms)
      → [IF >4 words] Gemini Flash multi-query expansion (2-3 alternatives)
      → Embedding (text-embedding-3-small)
      → BM25 sparse + Dense vector search
      → Reciprocal Rank Fusion (RRF, k=60)
      → CrossEncoder reranking (ms-marco-MiniLM-L-6-v2, top-20→top-5)
      → LLM response generation
```

## Quick Start

### Backend

```bash
cd apps/backend-rag
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/mouth
npm install
npm run dev
```

### Verify

```bash
# Import chain (must pass before any deploy)
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# Health check (production)
curl https://nuzantara-rag.fly.dev/health
```

## Deploy

| Target       | Command                                                | Auto         |
| ------------ | ------------------------------------------------------ | ------------ |
| **Backend**  | `cd apps/backend-rag && fly deploy --strategy rolling` | No           |
| **Frontend** | `git push origin main`                                 | Yes (Vercel) |

## Production (Fly.io)

| App                  | CPU       | RAM | Region    |
| -------------------- | --------- | --- | --------- |
| `nuzantara-rag`      | shared-2x | 2GB | Singapore |
| `nuzantara-postgres` | shared-1x | 2GB | Singapore |
| `nuzantara-qdrant`   | shared-1x | 2GB | Singapore |

## Feature Flags (Fly.io secrets)

<!-- DOCSYNC:FEATURE_FLAGS_START -->

| Flag                     | Value  | Effect                                 |
| ------------------------ | ------ | -------------------------------------- |
| `ENABLE_HYBRID_SEARCH`   | `true` | BM25+Dense+RRF in VectorSearchTool     |
| `ENABLE_RERANKER`        | `true` | CrossEncoder local reranking           |
| `ENABLE_BM25`            | `true` | Sparse vectors for hybrid search       |
| `ENABLE_QUERY_EXPANSION` | `true` | LLM multi-query expansion + RRF        |
| `ENABLE_KG_LANGGRAPH`    | `true` | Knowledge Graph LangGraph orchestrator |

<!-- DOCSYNC:FEATURE_FLAGS_END -->

## Communication Channels

| Channel   | Status     | Backend                     |
| --------- | ---------- | --------------------------- |
| Web Chat  | Live       | Fly.io                      |
| WhatsApp  | Live       | Fly.io (Meta Cloud API)     |
| Telegram  | Live       | Pro OpenClaw (@Balizerobot) |
| Instagram | Live       | Fly.io                      |
| X/Twitter | CRC broken | Fly.io                      |

## Documentation

| Doc                                | Purpose                                      |
| ---------------------------------- | -------------------------------------------- |
| `CLAUDE.md`                        | AI agent rules, golden rules, system context |
| `docs/AI_ONBOARDING.md`            | Technical reference for AI assistants        |
| `docs/LIVING_ARCHITECTURE.md`      | Auto-generated API + service catalog         |
| `docs/RAG_ARCHITECTURE_DIAGRAM.md` | Search pipeline diagrams                     |

## Prerequisites

- Node.js 20+ / npm 10+
- Python 3.11+
- Docker (optional, for local stack)

## License

Private. Bali Zero internal use.

# Nuzantara v5.2.0

Production AI-powered business intelligence platform for **Bali Zero** — Indonesian business services (visa, company setup, tax, property) in Bali, serving 5,000+ clients.

**Live:** [kita.balizero.com](https://kita.balizero.com)

## Architecture

Monorepo powered by agentic RAG with Knowledge Graph. App/router/service counts are not
committed in this file — get them live with `python scripts/docs_sync.py --json`.

```
nuzantara/
├── apps/
│   ├── backend-rag/          # Python FastAPI — RAG, KG, WR2 pipeline (deploy Fly.io)
│   ├── mouth/                # Next.js frontend — kita/my/prime.balizero.com
│   ├── nuzantara-mcp/        # MCP server v2.1
│   ├── nuzantara-mcp-advanced/ # Fly.io ops, diagnostics
│   ├── admin-dashboard/      # Admin UI (Next.js)
│   ├── bali-intel-scraper/   # Intel pipeline (local Pro, OpenClaw cron)
│   ├── evaluator/            # QA + Core Guardian V3
│   ├── mata-garuda/          # Meta-agent Lamarckian 5-layer
│   ├── web/                  # zantara.balizero.com
│   ├── kb/                   # Knowledge base
│   └── ...                   # graph-engine, kbli-navigator, wa-mirror, zantara-media, …
├── packages/
│   ├── core/                 # Shared libs + BZ design tokens
│   └── cell-core/            # Biology framework (base for living agents)
├── docs/                     # Technical & operational docs
├── config/                   # Prometheus, Grafana, alerts
├── scripts/                  # Deploy, maintenance, analysis
└── data/                     # Shared datasets
```

## Tech Stack

- Backend: Python 3.11+ · FastAPI · Postgres 17 (Fly.io) · Redis
- Vector DB: Qdrant · embeddings `text-embedding-3-small`, 1536 dims (FROZEN)
- Knowledge Graph + agentic RAG · LangGraph
- Frontend: Next.js on Vercel · macOS/SwiftUI control surfaces

Counts (routers, services, tests, collections, vectors, KG nodes) are **not committed
here** on purpose: they moved on nearly every backend PR, so the committed line was
stale on `main` more often than it was right. Read them live instead:

```bash
python scripts/docs_sync.py --json
```

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

<!-- hand-maintained: no docs_sync generator for this table; source of truth = `fly secrets list -a nuzantara-rag` -->

| Flag                     | Value  | Effect                                 |
| ------------------------ | ------ | -------------------------------------- |
| `ENABLE_HYBRID_SEARCH`   | `true` | BM25+Dense+RRF in VectorSearchTool     |
| `ENABLE_RERANKER`        | `true` | CrossEncoder local reranking           |
| `ENABLE_BM25`            | `true` | Sparse vectors for hybrid search       |
| `ENABLE_QUERY_EXPANSION` | `true` | LLM multi-query expansion + RRF        |
| `ENABLE_KG_LANGGRAPH`    | `true` | Knowledge Graph LangGraph orchestrator |

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

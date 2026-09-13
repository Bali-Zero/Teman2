# Project overview, architecture and tech stack

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

**Name:** Nuzantara (Zantara)  
**Version:** 5.2.0  
**Type:** Production AI-powered business intelligence platform for Bali Zero  
**URL:** https://kita.balizero.com

### Architecture

**Monorepo structure:**

- `apps/mouth/` - Next.js frontend (Vercel)
- `apps/backend-rag/` - Python FastAPI RAG backend (Fly.io)
- `apps/admin-dashboard/` - Admin UI
- `apps/webapp/` - Web application
- `apps/bali-intel-scraper/` - Intelligence gathering
- `apps/nuzantara-mcp/` - MCP server v2.1 (inspect the server for its live capability inventory)
- `apps/nuzantara-mcp-advanced/` - Advanced MCP (Fly.io ops, diagnostics)
- `apps/nuzantara-mcp-browser/` - Browser automation MCP
- `apps/graph-engine/` - Graph processing engine
- `apps/kbli-voice/` - KBLI voice interface
- `apps/evaluator/` - Quality assurance
- `apps/zantara-media/` - Editorial content system
- `packages/core/` - Core libraries

### Tech Stack

- **Backend:** Python 3.11+, FastAPI. Live counts: `python3 scripts/docs_sync.py --json`
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** live counts are generated, not stored in this file
- **Vector Collections:** canonical registry: `backend/core/collection_registry.py`; live counts: `python3 scripts/docs_sync.py --json`
- **Embedding Model:** `text-embedding-3-small` (1536 dims) — **NEVER CHANGE**

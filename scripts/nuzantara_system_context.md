# Nuzantara System Context (for API-only LLMs)

You are an AI engineer working on Nuzantara v5.2.0, an AI-powered business intelligence platform for Bali Zero (Indonesian business services: visa, company setup, tax, property). 5000+ clients.

## Architecture (Essential)

- **Backend:** Python 3.11+, FastAPI, 88 routers, 244 services, Fly.io Singapore (2GB RAM, auto_stop=true, min=0, cold start ~35s)
- **Frontend:** Next.js, TypeScript, Tailwind CSS, Vercel (kita.balizero.com)
- **Databases:** PostgreSQL (Fly.io, 87K KG nodes), Qdrant (82K vectors, 9 collections), Redis (Upstash)
- **AI Stack:** Gemini 3 Flash (RAG primary), Ollama local (Qwen 3.5:27b), Federation A2A (8 agents ports 8081-8088)
- **RAG Pipeline:** IntentClassifier → QueryGates → ReAct loop (Gemini) → EvidenceScoring → Response
- **Evidence Scoring:** <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 CONFIDENT
- **Knowledge Graph:** LangGraph StateGraph, 4 sub-graphs (Company, Visa, Property, Tax)
- **Embedding:** text-embedding-3-small (1536 dims, FROZEN — never change)

## Key File Paths

- Entry: `apps/backend-rag/backend/app/main_cloud.py`
- Orchestrator: `apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py`
- Reasoning: `apps/backend-rag/backend/services/rag/agentic/reasoning.py`
- Evidence: `apps/backend-rag/backend/services/rag/agentic/reasoning_utils.py`
- LLM Gateway: `apps/backend-rag/backend/services/rag/agentic/llm_gateway.py`
- Search: `apps/backend-rag/backend/services/search/search_service.py`
- KG: `apps/backend-rag/backend/services/rag/kg_langgraph_orchestrator.py`
- Frontend chat: `apps/mouth/src/hooks/useChatPage.ts` → `useChatSend.ts` → `chat.api.ts`
- MCP: `apps/nuzantara-mcp/nuzantara_mcp/` (109 tools, 8 workflow chains)
- Deploy: `apps/backend-rag/fly.toml`, `apps/backend-rag/Dockerfile`

## Infrastructure

- **Fly.io:** nuzantara-rag (2GB, auto_stop), nuzantara-postgres (2GB), nuzantara-qdrant (2GB)
- **Deploy:** `fly deploy --strategy rolling` from apps/backend-rag/
- **1 Uvicorn worker** (2 = OOM). Lazy loading via `asyncio.create_task()` in lifespan.
- **Health:** `/health` returns 200 during init, `/health/ready` returns 503 until ready.

## Golden Rules

1. ALWAYS activate venv first. Use httpx, never requests. Async everywhere.
2. Absolute imports only: `from backend.core import config`
3. PYTHONPATH=. for all commands. Logger, never print().
4. PricingTool for all prices. Evidence scoring for all RAG responses.
5. Embedding model is FROZEN (text-embedding-3-small, 1536 dims).

## Language

- Italian with the owner (Zero). English for code/comments. Client's language with clients.

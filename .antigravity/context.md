# Nuzantara - Antigravity IDE Context

## Project Identity

**Name:** Nuzantara (Zantara)  
**Version:** 5.2.0  
**Type:** Production AI Business Intelligence Platform  
**Owner:** Bali Zero  
**URL:** https://zantara.balizero.com

## Architecture Overview

### Monorepo Structure
```
nuzantara/
├── apps/
│   ├── mouth/              → Next.js frontend (Vercel)
│   ├── backend-rag/        → FastAPI RAG backend (Fly.io)
│   ├── admin-dashboard/    → Admin interface
│   ├── webapp/             → Web application
│   ├── bali-intel-scraper/ → Intelligence gathering
│   ├── nuzantara-mcp/      → MCP server (7 tools, 3 prompts)
│   └── evaluator/          → QA system
└── packages/
    ├── kb/                 → Knowledge base
    └── core/               → Shared libraries
```

### Technology Matrix

| Layer | Technology | Scale |
|-------|------------|-------|
| Backend | FastAPI, Python 3.11+ | 68 routers, 228 services, 477 tests |
| Frontend | Next.js, TypeScript | App Router, Tailwind CSS |
| Database | PostgreSQL | Relational data |
| Vectors | Qdrant | 7 collections, ~58,880 vectors |
| Cache | Redis | Session & query cache |
| Knowledge Graph | Neo4j/Custom | 56,113 nodes, 161,173 edges |
| Embeddings | OpenAI text-embedding-3-small | 1536 dimensions (FROZEN) |
| Deploy | Fly.io (backend), Vercel (frontend) | Multi-region |

## Development Protocols

### Python Backend (CRITICAL)

```bash
# ALWAYS activate virtualenv first
source venv/bin/activate

# Run backend
cd apps/backend-rag
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000

# Testing
PYTHONPATH=. pytest tests/ -v --cov=backend

# Type checking
mypy backend/

# Linting
ruff check backend/ --fix
```

### Frontend

```bash
cd apps/mouth
npm run dev      # Local development
npm run build    # Production build
npm test         # Run tests
```

### The 10 Golden Rules

1. ✅ **Virtualenv mandatory** — Never use system Python
2. ✅ **PYTHONPATH execution** — `PYTHONPATH=. python -m backend.module`
3. ✅ **Absolute imports** — `from backend.core import config`
4. ✅ **Async-first** — Use `httpx`, never `requests`
5. ✅ **Type everything** — Full type hints required
6. ✅ **No secrets in code** — Environment variables only
7. ✅ **Separate data/logic** — Clean architecture
8. ✅ **Logger, not print** — Structured logging via `logger`
9. ✅ **Quality gates** — Tests + error handling mandatory
10. ✅ **Verify sources** — Never presume, always check

## Domain-Specific Knowledge

### KBLI (Indonesian Business Codes)

**Storage:** Qdrant vector DB  
**Format:** FLAT payloads (NOT nested)

```json
{
  "code": "47911",
  "title_id": "Perdagangan Eceran Melalui Internet",
  "title_en": "Retail Sale via Internet",
  "description": "...",
  "category": "G",
  "section": "Perdagangan"
}
```

### Pricing System

- **Source:** PricingTool only
- **Reference files:** `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md`
- **Rule:** Never hardcode or cache prices

### Evidence Scoring

| Score | Action | Behavior |
|-------|--------|----------|
| < 0.15 | ABSTAIN | Refuse to answer |
| 0.15 - 0.60 | CAUTIOUS | Answer with disclaimer |
| > 0.60 | NORMAL | Confident response |

### Embedding Model

**Model:** `text-embedding-3-small`  
**Dimensions:** 1536  
**Status:** FROZEN (58,880 vectors depend on it)  
**Change policy:** Prohibited without full re-indexing plan

## Multi-Agent Coordination

### Agent Roles

- **Claude Code:** Architecture, refactoring, complex logic
- **Cursor:** Rapid prototyping, UI components
- **Antigravity (you):** System orchestration, multi-file operations
- **Gemini:** Research, documentation, analysis

### Handoff Protocol

When coordinating with other agents:
1. Share current context (this file + relevant code)
2. Specify exact files/paths involved
3. State expected outcomes
4. Request verification after completion

## Deployment Topology

### Production

- **Backend:** Fly.io app `nuzantara-rag` (Asia region)
- **Frontend:** Vercel (auto-deploy from `main` branch)
- **Databases:** Fly.io managed PostgreSQL + Qdrant + Redis

### Environment Variables (required)

```bash
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://...
QDRANT_URL=https://...
QDRANT_API_KEY=...
REDIS_URL=redis://...
JWT_SECRET=...
FLY_API_TOKEN=...
```

## Testing Strategy

```bash
# Fast: Unit tests
PYTHONPATH=. pytest tests/unit/ -v

# Medium: Integration tests  
PYTHONPATH=. pytest tests/integration/ -v

# Slow: E2E tests
PYTHONPATH=. pytest tests/e2e/ -v

# Coverage (target: >80%)
PYTHONPATH=. pytest --cov=backend --cov-report=html tests/
```

## Code Patterns

### Backend (Python)

```python
from typing import List, Optional
from backend.core.logging import logger
import httpx

async def query_qdrant(
    collection: str,
    vector: List[float],
    limit: int = 10
) -> Optional[List[dict]]:
    """Query Qdrant vector database."""
    try:
        async with httpx.AsyncClient() as client:
            response = await qdrant_client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit
            )
            logger.info(f"Qdrant query: {collection}, results: {len(response)}")
            return response
    except Exception as e:
        logger.error(f"Qdrant query failed: {collection}", exc_info=True)
        raise
```

### Frontend (TypeScript)

```typescript
interface QueryResult {
  id: string;
  score: number;
  payload: Record<string, unknown>;
}

async function searchKBLI(query: string): Promise<QueryResult[]> {
  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Search failed:', error);
    return [];
  }
}
```

## Common Operations

### Add New Router

```bash
# Create router file
touch apps/backend-rag/backend/routers/new_feature.py

# Create service
touch apps/backend-rag/backend/services/new_feature_service.py

# Create tests
touch apps/backend-rag/tests/test_new_feature.py

# Register in main.py
# Include router in FastAPI app
```

### Database Migration

```bash
cd apps/backend-rag
source venv/bin/activate

# Create migration
alembic revision --autogenerate -m "Add new table"

# Review migration file
# Edit alembic/versions/xxx_add_new_table.py

# Apply migration
alembic upgrade head

# Rollback (if needed)
alembic downgrade -1
```

## Owner Context

- **Codename:** Zero
- **Real name:** PRIVATE (never expose)
- **Language protocol:** Italian with owner, client's native language otherwise
- **Privacy:** High sensitivity, protect personal information

## Critical Paths

| Path | Purpose |
|------|---------|
| `apps/backend-rag/backend/routers/` | API endpoints (68 files) |
| `apps/backend-rag/backend/services/` | Business logic (228 files) |
| `apps/backend-rag/tests/` | Test suite (477 files) |
| `apps/mouth/app/` | Next.js pages |
| `apps/mouth/components/` | React components |
| `apps/nuzantara-mcp/` | MCP server implementation |

## Resources

- API Docs: http://localhost:8000/docs (Swagger)
- Architecture: `docs/architecture.md`
- Pricing Reference: `PRICING_REFERENCE.md`
- Visa Types: `VISA_TYPES_REFERENCE.md`
- Golden Rules: `AI_ONBOARDING.md`

---

**Last updated:** 2026-02-13  
**Maintainer:** Bali Zero AI Team  
**For:** Antigravity IDE multi-agent orchestration

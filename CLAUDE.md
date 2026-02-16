# CLAUDE.md - Nuzantara Project Context for Claude Code

## 1. Project Overview

**Name:** Nuzantara (Zantara)  
**Version:** 5.2.0  
**Type:** Production AI-powered business intelligence platform for Bali Zero  
**URL:** https://zantara.balizero.com

### Architecture

**Monorepo structure:**
- `apps/mouth/` - Next.js frontend (Vercel)
- `apps/backend-rag/` - Python FastAPI RAG backend (Fly.io)
- `apps/admin-dashboard/` - Admin UI
- `apps/webapp/` - Web application
- `apps/bali-intel-scraper/` - Intelligence gathering
- `apps/nuzantara-mcp/` - MCP server (7 tools, 3 prompts, 1 resource)
- `apps/evaluator/` - Quality assurance
- `packages/kb/` - Knowledge base
- `packages/core/` - Core libraries

### Tech Stack

- **Backend:** Python 3.11+, FastAPI, 68 routers, 228 services, 477 tests
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** 56,113 nodes, 161,173 edges
- **Vector Collections:** 7 collections, ~58,880 vectors
- **Embedding Model:** `text-embedding-3-small` (1536 dims) — **NEVER CHANGE**

## 2. Golden Rules (ENFORCE STRICTLY)

1. **Virtualenv Mandatory** - Never use system Python. Always activate venv first.
2. **No Root Execution** - Use `PYTHONPATH=. python -m backend.module`, never run modules directly.
3. **Path Discipline** - Absolute imports only: `from backend.core import config`, never relative.
4. **Async First** - Use `httpx` for HTTP, never `requests`. All I/O must be async.
5. **Type Hints Required** - Every function must have full type annotations.
6. **No Hardcoded Secrets** - Use environment variables or secrets manager.
7. **Data/Logic Separation** - Business logic separate from data access layer.
8. **Clean Logging** - Use `logger`, never `print()` statements.
9. **Quality Standards** - Tests, error handling, graceful degradation required.
10. **Verify Sources** - Never presume, always verify against actual data sources.

## 3. Development Commands

### Backend (FastAPI)

```bash
# Activate virtualenv
source venv/bin/activate  # or: . venv/bin/activate

# Run backend locally
cd apps/backend-rag
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000

# Run tests
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. pytest tests/test_specific.py::test_function -v

# Type checking
mypy backend/

# Linting
ruff check backend/
ruff format backend/

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend (Next.js)

```bash
cd apps/mouth
npm run dev        # Development server
npm run build      # Production build
npm run start      # Production server
npm run lint       # ESLint
npm run test       # Jest tests
```

### Deployment

```bash
# Backend to Fly.io
fly deploy --config apps/backend-rag/fly.toml --app nuzantara-rag

# Frontend to Vercel (auto-deploy on git push to main)
vercel --prod
```

## 4. Critical Paths

### Backend Structure

```
apps/backend-rag/
├── backend/
│   ├── core/          # Core configuration, dependencies
│   ├── routers/       # API endpoints (68 routers)
│   ├── services/      # Business logic (228 services)
│   ├── models/        # Pydantic models
│   ├── db/            # Database access layer
│   ├── utils/         # Utility functions
│   └── main.py        # FastAPI app entry
├── tests/             # 477 test files
├── alembic/           # Database migrations
├── requirements.txt   # Python dependencies
└── fly.toml          # Fly.io configuration
```

### Frontend Structure

```
apps/mouth/
├── app/              # Next.js App Router
├── components/       # React components
├── lib/              # Utilities
├── public/           # Static assets
└── styles/           # Tailwind CSS
```

## 5. Domain-Specific Knowledge

### KBLI (Indonesian Business Classification)

**Storage:** Qdrant vector collection  
**Format:** **FLAT payload structure**, NOT nested  
**Fields:** `code`, `title_id`, `title_en`, `description`, `category`, `section`

❌ **WRONG:**
```json
{
  "code": "47911",
  "details": {
    "title": "...",
    "description": "..."
  }
}
```

✅ **CORRECT:**
```json
{
  "code": "47911",
  "title_id": "Perdagangan Eceran...",
  "title_en": "Retail Sale...",
  "description": "...",
  "category": "G",
  "section": "Perdagangan"
}
```

### Pricing System

**CRITICAL:** All prices MUST come from `PricingTool`.  
**Never:** Hardcode, guess, or cache prices outside the tool.  
**Files:** Reference only `PRICING_REFERENCE.md` and `VISA_TYPES_REFERENCE.md`.

### Evidence Scoring System

Classification confidence thresholds:

- **< 0.15:** `ABSTAIN` - Insufficient confidence, refuse to answer
- **0.15 - 0.60:** `CAUTIOUS` - Provide answer with clear uncertainty disclaimer
- **> 0.60:** `NORMAL` - Confident answer

### Embedding Model

**Model:** `text-embedding-3-small` (OpenAI)  
**Dimensions:** 1536  
**CRITICAL:** This model is FROZEN. Changing it would invalidate 58,880 existing vectors.  
**Never:** Switch to another model without explicit authorization and full re-indexing plan.

## 6. MCP Server

**Location:** `apps/nuzantara-mcp/`  
**Capabilities:**
- **7 Tools:** Query routing, pricing lookup, visa info, KBLI search, etc.
- **3 Prompts:** Business setup, visa consultation, pricing inquiry
- **1 Resource:** Knowledge base access

**Usage:**
```typescript
// Tool invocation example
const result = await mcpServer.callTool("pricing-lookup", {
  serviceType: "kitas",
  visaType: "investor"
});
```

## 7. Deployment Architecture

### Production Stack

- **Frontend:** Vercel (CDN, Edge Functions)
- **Backend:** Fly.io `nuzantara-rag` (Asia region)
- **Databases:**
  - PostgreSQL: Fly.io managed
  - Qdrant: Fly.io app
  - Redis: Upstash or Fly.io

### Environment Variables

**Required:**
- `OPENAI_API_KEY` - For embeddings
- `DATABASE_URL` - PostgreSQL connection
- `QDRANT_URL`, `QDRANT_API_KEY` - Vector DB
- `REDIS_URL` - Cache
- `JWT_SECRET` - Authentication
- `FLY_API_TOKEN` - Deployment (CI/CD)

## 8. Testing Strategy

```bash
# Unit tests (fast)
PYTHONPATH=. pytest tests/unit/ -v

# Integration tests (slower)
PYTHONPATH=. pytest tests/integration/ -v

# E2E tests (slowest)
PYTHONPATH=. pytest tests/e2e/ -v

# Coverage report
PYTHONPATH=. pytest --cov=backend --cov-report=html tests/
```

**Standards:**
- Unit tests: > 80% coverage
- Critical paths: 100% coverage
- All new features: tests required before merge

## 9. Code Style & Patterns

### Python (Backend)

```python
# Good: Async, typed, clean logging
from typing import List, Optional
from backend.core.logging import logger
import httpx

async def fetch_kbli_data(code: str) -> Optional[dict]:
    """Fetch KBLI data from Qdrant."""
    try:
        async with httpx.AsyncClient() as client:
            result = await qdrant.search(
                collection_name="kbli",
                query_vector=embedding,
                limit=1
            )
            logger.info(f"KBLI search successful: {code}")
            return result[0] if result else None
    except Exception as e:
        logger.error(f"KBLI search failed: {code}", exc_info=True)
        raise
```

### TypeScript (Frontend)

```typescript
// Good: Type-safe, error handling
interface KBLIResponse {
  code: string;
  title_en: string;
  description: string;
}

async function fetchKBLI(code: string): Promise<KBLIResponse | null> {
  try {
    const response = await fetch(`/api/kbli/${code}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('KBLI fetch failed:', error);
    return null;
  }
}
```

## 10. Common Pitfalls

❌ **AVOID:**
- Running Python without virtualenv
- Using `requests` instead of `httpx`
- Nested payload structures in Qdrant
- Hardcoded prices or visa info
- `print()` debugging in production code
- Relative imports
- Blocking I/O operations
- Missing type hints

✅ **DO:**
- Always activate venv first
- Use `httpx` for all HTTP calls
- Flat payloads in Qdrant
- `PricingTool` for all pricing
- `logger` for all logging
- Absolute imports
- Async/await everywhere
- Full type annotations

## 11. Owner Information

**Owner:** Zero (internal codename)  
**Privacy:** Real name is PRIVATE, never reveal in client communications.  
**Language:** Italian with owner, client's language with everyone else.

## 12. Resources

- **Architecture:** `docs/architecture.md`
- **API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Golden Rules:** This file + `AI_ONBOARDING.md`
- **Pricing:** `PRICING_REFERENCE.md`
- **Visa Info:** `VISA_TYPES_REFERENCE.md`

---

## 13. Pre-Deploy Checklist

Before any production deployment:

```bash
# 1. Check for rogue AI changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test critical import chain (dependencies.py is imported by ALL routers)
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core KG tests (82 tests, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q

# 4. Deploy
fly deploy --strategy rolling
```

**Known test debt:** ~448 pre-existing failures in `tests/unit/` from rogue AI refactors (Gemini/Windsurf). These do NOT affect production. Details in `memory/session-2026-02-16-hotfix-and-tests.md`.

---

**Last Updated:** 2026-02-16
**Maintained by:** Bali Zero AI Team

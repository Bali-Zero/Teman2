# AI ONBOARDING GUIDE - Nuzantara Project

**Last Updated:** 2026-01-10  
**Purpose:** Quick-start guide for AI assistants working on Project Nuzantara

> **READ THIS FIRST** before making any changes to the codebase.

---

## 🎯 QUICK START CHECKLIST

When starting a new session, verify you understand:

- [ ] **Project Structure:** Monorepo with `apps/backend-rag` (FastAPI) and `apps/mouth` (Next.js)
- [ ] **Golden Rules:** No root execution, absolute imports, async-first, type hints required
- [ ] **Critical Files:** `reasoning.py` (evidence scoring), `llm_gateway.py` (LLM routing)
- [ ] **Toolkit:** Sentinel (quality control), Scribe (documentation), Observability stack
- [ ] **Deployment:** Backend on Fly.io (Singapore), Frontend on Vercel

---

## 📋 THE GOLDEN RULES (MUST FOLLOW)

### 1. NO ROOT EXECUTION
```bash
# ❌ WRONG
python script.py

# ✅ CORRECT
cd apps/backend-rag
python -m backend.scripts.script_name
```

### 2. PATH DISCIPLINE
```python
# ❌ WRONG - Relative imports
from ..core import config

# ✅ CORRECT - Absolute imports
from backend.core import config
```

**Always run from `apps/backend-rag` root with `PYTHONPATH=.`**

### 3. ASYNC FIRST
```python
# ❌ WRONG - Blocking requests
import requests
response = requests.get(url)

# ✅ CORRECT - Async httpx
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### 4. TYPE HINTS REQUIRED
```python
# ❌ WRONG
def process_query(query):
    return result

# ✅ CORRECT
def process_query(query: str) -> dict[str, Any]:
    return result
```

### 5. NO HARDCODING
```python
# ❌ WRONG
api_key = "sk-1234567890"

# ✅ CORRECT
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

### 6. SEPARATION OF DATA AND LOGIC
- **Volatile Data** (prices, names, addresses) → Knowledge Base (Qdrant/Postgres) or `settings`
- **Business Logic** → `backend/services/`
- **Never** hardcode data in code

---

## 🏗️ PROJECT STRUCTURE

```
nuzantara/
├── apps/
│   ├── backend-rag/          # CORE: FastAPI Backend
│   │   ├── backend/
│   │   │   ├── app/          # FastAPI entrypoint (main_cloud.py)
│   │   │   ├── core/         # Config, Security, Logging
│   │   │   ├── services/     # Business Logic
│   │   │   │   ├── rag/agentic/  # CORE: Orchestrator, ReAct, LLM Gateway
│   │   │   │   └── memory/       # Memory Orchestrator
│   │   │   └── api/          # Routers/Endpoints
│   │   └── scripts/          # Maintenance scripts
│   │
│   ├── mouth/                # Frontend: Next.js 16 + React 19
│   │   └── src/
│   │       ├── app/          # Pages (chat, dashboard, clienti)
│   │       ├── components/   # UI components
│   │       └── lib/          # API clients, store
│   │
│   ├── bali-intel-scraper/   # News processing pipeline
│   └── zantara-media/        # Editorial content system
│
├── docs/                     # Documentation
│   ├── ai/                   # AI handover protocols
│   └── operations/           # Runbooks, guides
│
└── scripts/                  # Root-level utilities
```

---

## 🛠️ THE TOOLKIT

### Sentinel (Quality Control)
```bash
# From project root
./sentinel

# What it does:
# 1. Auto-healing (Ruff check + fix)
# 2. Testing (Pytest with coverage)
# 3. Health checks (Qdrant, DB)

# Output: sentinel-results/sentinel-run-TIMESTAMP.log
```

**RULE:** Always run Sentinel before asking for review.

### Scribe (Documentation Generator)
```bash
python apps/core/scribe.py

# Generates: docs/LIVING_ARCHITECTURE.md
# Use to understand codebase structure
```

### Observability Stack
```bash
# Start all services
docker compose up -d

# Services:
# - Grafana: http://localhost:3001 (admin/changeme123)
# - Prometheus: http://localhost:9090
# - Jaeger: http://localhost:16686
# - Qdrant UI: http://localhost:6333/dashboard
```

**Full guide:** `docs/operations/OBSERVABILITY_GUIDE.md`

---

## ⚠️ CRITICAL FIXES & KNOWN ISSUES

### Evidence Score System

**File:** `backend/services/rag/agentic/reasoning.py`

The system uses `evidence_score` (0.0-1.0) to decide responses:
- **< 0.3** → ABSTAIN (refuses to answer)
- **0.3-0.6** → Cautious response
- **> 0.6** → Normal response

**Threshold changed:** 0.8 → 0.3 (v1175, 2025-12-30)

### Trusted Tools (Bypass Evidence Check)

These tools bypass evidence scoring because they provide their own evidence:

| Tool | Location | Purpose |
|------|----------|---------|
| `calculator` | `tools.py` | Mathematical calculations |
| `get_pricing` | `zantara_tools.py` | Bali Zero service pricing |
| `team_knowledge` | `zantara_tools.py` | Team member search/list |

**Implementation:** `reasoning.py:867-883`

**⚠️ DO NOT modify trusted tools check without understanding the full flow.**

### CRM RBAC (Role-Based Access Control)

**File:** `backend/app/routers/crm_practices.py`

| Role | Access |
|------|--------|
| Admin (`zero@balizero.com`, `admin@balizero.com`) | All clients and practices |
| Team Member | Only clients with `assigned_to` = own email |

### Date Conversion Fix (v1490, 2026-01-10)

**Files:** `crm_enhanced.py`, `crm_clients.py`

PostgreSQL DATE fields must be converted explicitly when using asyncpg:
```python
# ✅ CORRECT
date_value = row['date_field'].isoformat() if row['date_field'] else None
```

---

## 🔍 DEBUGGING PATTERNS

### Check Evidence Scoring
```bash
fly logs -a nuzantara-rag | grep -E "Evidence|Trusted|ABSTAIN"
```

**Log patterns:**
- `🛡️ [Uncertainty] Evidence Score: X.XX` → Score calculated
- `🧮 [Trusted Tool] X used successfully` → Bypass active
- `🛡️ [Uncertainty] Triggered ABSTAIN` → System refused

### Common Import Errors
```bash
# Error: ImportError: attempted relative import with no known parent package
# Solution: Run with PYTHONPATH=.
cd apps/backend-rag
PYTHONPATH=. python -m backend.scripts.script_name
```

### Fly.io Crashes
**Common causes:**
1. Missing `PORT` env var → Check `fly.toml`
2. Missing `QDRANT_URL` → Check secrets
3. Database connection → Check `DATABASE_URL`

**Debug:**
```bash
fly logs -a nuzantara-rag
fly ssh console -a nuzantara-rag
```

---

## 📚 ESSENTIAL DOCUMENTATION

| Document | Path | When to Read |
|----------|------|--------------|
| **AI Handover Protocol** | `docs/ai/AI_HANDOVER_PROTOCOL.md` | Always (this is the brain) |
| **System Map 4D** | `docs/SYSTEM_MAP_4D.md` | To understand architecture |
| **Observability Guide** | `docs/operations/OBSERVABILITY_GUIDE.md` | For debugging/monitoring |
| **Deploy Checklist** | `docs/operations/DEPLOY_CHECKLIST.md` | Before deploying |
| **Intel Pipeline** | `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md` | For news scraper |

---

## 🚀 COMMON WORKFLOWS

### Adding a New API Endpoint

1. **Create router** in `backend/app/routers/`
   ```python
   from fastapi import APIRouter
   router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])
   
   @router.get("/")
   async def list_items() -> list[dict]:
       # Implementation
   ```

2. **Add business logic** in `backend/services/`
   ```python
   # backend/services/my_service.py
   async def get_items() -> list[dict]:
       # Business logic here
   ```

3. **Register router** in `backend/app/main_cloud.py`
   ```python
   from backend.app.routers import my_router
   app.include_router(my_router.router)
   ```

4. **Add tests** in `backend/tests/api/`
5. **Run Sentinel** before committing

### Modifying RAG Pipeline

**⚠️ CRITICAL:** Read `docs/operations/AGENTIC_RAG_FIXES.md` first (if it exists)

**Key files:**
- `backend/services/rag/agentic/reasoning.py` - Evidence scoring
- `backend/services/rag/agentic/llm_gateway.py` - LLM routing
- `backend/services/rag/agentic/orchestrator.py` - Main orchestrator

**Test changes:**
```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/services/rag/agentic/ -v
```

### Frontend Changes

**Structure:**
- Pages: `apps/mouth/src/app/`
- Components: `apps/mouth/src/components/`
- API clients: `apps/mouth/src/lib/api/`

**Run locally:**
```bash
cd apps/mouth
npm run dev
```

**Deploy:**
```bash
# Automatic via Vercel on push to main
# Or manually:
./scripts/fly-frontend.sh deploy
```

---

## 🔐 ENVIRONMENT VARIABLES

**Critical variables (check before running):**

| Variable | Purpose | Where Used |
|----------|---------|------------|
| `DATABASE_URL` | PostgreSQL connection | Backend |
| `QDRANT_URL` | Vector DB connection | Backend |
| `OPENAI_API_KEY` | Embeddings | Backend |
| `GOOGLE_API_KEY` | Gemini LLM | Backend |
| `JWT_SECRET_KEY` | Auth tokens | Backend |
| `PORT` | Server port | Fly.io |

**Check secrets:**
```bash
fly secrets list -a nuzantara-rag
```

---

## ✅ PRE-COMMIT CHECKLIST

Before asking for review:

- [ ] Ran `./sentinel` and it passed
- [ ] All new functions have type hints
- [ ] No hardcoded secrets or URLs
- [ ] Used async/await (no blocking calls)
- [ ] Absolute imports only
- [ ] Tests added/updated
- [ ] Documentation updated (if needed)

---

## 🆘 GETTING HELP

### If Something Breaks

1. **Check logs:**
   ```bash
   fly logs -a nuzantara-rag | tail -100
   ```

2. **Check observability:**
   - Grafana dashboards
   - Prometheus metrics
   - Jaeger traces

3. **Check documentation:**
   - `docs/operations/` for runbooks
   - `docs/ai/AI_HANDOVER_PROTOCOL.md` for context

4. **Search codebase:**
   ```bash
   # Use grep or codebase_search
   grep -r "function_name" apps/backend-rag/backend/
   ```

### Common Questions

**Q: Where do I put new code?**  
A: Business logic → `backend/services/`, API endpoints → `backend/app/routers/`

**Q: How do I test locally?**  
A: `docker compose up -d` for services, then `cd apps/backend-rag && PYTHONPATH=. python -m backend.app.main_cloud`

**Q: How do I deploy?**  
A: See `docs/operations/DEPLOY_CHECKLIST.md`

**Q: Why is my import failing?**  
A: Make sure you're using absolute imports and running from `apps/backend-rag` with `PYTHONPATH=.`

---

## 📝 NOTES FOR AI ASSISTANTS

1. **Always read the handover protocol** (`docs/ai/AI_HANDOVER_PROTOCOL.md`) - it's the "brain" of the project
2. **Use the toolkit** - Sentinel, Scribe, Observability stack are your friends
3. **Follow the golden rules** - They exist for good reasons
4. **Check critical fixes** - Especially evidence scoring and trusted tools
5. **Test before asking** - Run Sentinel, check logs, verify locally

---

**Remember:** This is a production system. Be careful, test thoroughly, and use the observability tools to verify your changes.

**Last Updated:** 2026-01-10

# AI ONBOARDING GUIDE - Nuzantara Project

**Last Updated:** 2026-01-21  
**Purpose:** Quick-start guide for AI assistants working on Project Nuzantara

**System Stats (Updated 2026-01-21):**

- Router Files: 61
- Services: 204 Python files
- Test Files: 278
- Migrations: 51
- API Endpoints: 393
- Test Cases: ~4255

> **READ THIS FIRST** before making any changes to the codebase.

---

## 🎯 QUICK START CHECKLIST

When starting a new session, verify you understand:

- [ ] **Virtualenv:** `.venv` created and activated (`source .venv/bin/activate`)
- [ ] **Project Structure:** Monorepo with `apps/backend-rag` (FastAPI) and `apps/mouth` (Next.js)
- [ ] **Golden Rules:** No root execution, absolute imports, async-first, type hints required
- [ ] **Critical Files:** `reasoning.py` (evidence scoring), `llm_gateway.py` (LLM routing)
- [ ] **Toolkit:** Sentinel (quality control), Scribe (documentation), Observability stack
- [ ] **Deployment:** Backend on Fly.io (Singapore), Frontend on Vercel

---

## 📋 THE GOLDEN RULES (MUST FOLLOW)

### 1. VIRTUALENV IS MANDATORY

**⚠️ CRITICAL:** Always use the project's virtualenv. Never use system Python or pyenv directly.

```bash
# ✅ CORRECT - Always activate virtualenv first
cd apps/backend-rag
source .venv/bin/activate  # or: . .venv/bin/activate

# Verify you're in venv
which python  # Should show: .../apps/backend-rag/.venv/bin/python

# Install/update dependencies
pip install -r requirements.txt

# Run commands
python -m backend.scripts.script_name
```

**Why:** Isolated dependencies prevent conflicts, ensure reproducibility, and match production Docker environment.

**Setup (first time only):**

```bash
cd apps/backend-rag
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. NO ROOT EXECUTION

```bash
# ❌ WRONG
python script.py

# ✅ CORRECT
cd apps/backend-rag
source .venv/bin/activate  # MUST activate venv first
python -m backend.scripts.script_name
```

### 3. PATH DISCIPLINE

```python
# ❌ WRONG - Relative imports
from ..core import config

# ✅ CORRECT - Absolute imports
from backend.core import config
```

**Always run from `apps/backend-rag` root with virtualenv activated and `PYTHONPATH=.`**

### 4. ASYNC FIRST

```python
# ❌ WRONG - Blocking requests
import requests
response = requests.get(url)

# ✅ CORRECT - Async httpx
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### 5. TYPE HINTS REQUIRED

```python
# ❌ WRONG
def process_query(query):
    return result

# ✅ CORRECT
def process_query(query: str) -> dict[str, Any]:
    return result
```

### 6. NO HARDCODING

```python
# ❌ WRONG
api_key = "sk-1234567890"

# ✅ CORRECT
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

### 7. SEPARATION OF DATA AND LOGIC

- **Volatile Data** (prices, names, addresses) → Knowledge Base (Qdrant/Postgres) or `settings`
- **Business Logic** → `backend/services/`
- **Never** hardcode data in code

### 8. PRODUCTION-READY STANDARD (MANDATORY)

**⚠️ CRITICAL:** Every implementation MUST follow the Production-Ready Standard.

This is NOT optional - it's the baseline for enterprise code quality:

```
Code that works ✅
Code testable ✅
Code debuggable ✅
Code documented ✅
Code maintainable ✅
```

**The 5 Pillars:**

| Pillar                        | Requirement                                         | Why                                   |
| ----------------------------- | --------------------------------------------------- | ------------------------------------- |
| **1. Test Coverage**          | Unit tests + Integration test for every new feature | Confidence in code, catch regressions |
| **2. Structured Logging**     | INFO/WARNING/ERROR logs at key steps                | Debuggability in production           |
| **3. Metrics & KPIs**         | Track performance + success rates                   | Measurability, optimization           |
| **4. Complete Documentation** | Code comments + Technical docs + Session notes      | Maintainability for future team       |
| **5. Error Handling**         | Try/except + graceful degradation                   | Resilience, no silent failures        |

**Example: Lead Assignment Agent (2026-01-18)**

When implementing the Lead Assignment Agent, the complete deliverable included:

- ✅ **340 lines** of production code (`lead_assignment_agent.py`)
- ✅ **345 lines** of tests (7 unit + 1 integration test)
- ✅ **450 lines** of technical documentation
- ✅ **Structured logging** at every workflow step
- ✅ **Performance metrics** defined (assignment time, notification rate, etc.)
- ✅ **Error handling** with graceful degradation

**Total: 1,500+ lines for a feature that could be "done" in 150 lines.**

**This 10x effort multiplier is THE STANDARD for Nuzantara.**

**Note:** For simpler features (e.g., a single API endpoint), you might have:

- 50 lines of code
- 80 lines of tests
- 100 lines of documentation
- **Total: 230 lines** (still ~4x multiplier, but more manageable)

The key is: **every feature should be testable, debuggable, documented, and maintainable** - the exact multiplier depends on complexity.

#### When to Apply Production-Ready Standard:

**ALWAYS apply for:**

- New features (workflows, services, agents)
- Production systems (CRM, RAG, Auth)
- Multi-team code (will be maintained by others)
- Critical paths (client data, payments, compliance)

**Can skip for:**

- Quick debugging scripts (one-time use)
- Prototypes explicitly marked as "experimental"
- Trivial helper functions (<10 lines)

#### Production-Ready Checklist:

Before marking a feature "complete":

- [ ] **Tests written** - Unit tests for each function, integration test for full flow
- [ ] **Logging added** - INFO logs for success paths, WARNING for edge cases, ERROR for failures
- [ ] **Metrics defined** - Performance KPIs, success rates, error rates
- [ ] **Documentation created**:
  - [ ] Code docstrings with examples
  - [ ] Technical doc in `docs/` with architecture, deployment, troubleshooting
  - [ ] Session notes in `CLAUDE.md` or relevant memory file
- [ ] **Error handling** - Try/except blocks, graceful fallbacks, clear error messages
- [ ] **Type safety** - Type hints on all functions, TypedDict for complex state

**Remember:** "Leave it better than you found it" is not just philosophy - it's project policy.

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
# IMPORTANT: Ensure virtualenv is activated first
cd apps/backend-rag
source .venv/bin/activate  # MUST activate venv
cd ../..  # Back to project root
./sentinel

# What it does:
# 1. Auto-healing (Ruff check + fix)
# 2. Testing (Pytest with coverage) - requires venv
# 3. Health checks (Qdrant, DB)

# Output: sentinel-results/sentinel-run-TIMESTAMP.log
```

**RULE:** Always run Sentinel before asking for review. **Virtualenv MUST be activated** for tests to run correctly.

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

| Tool             | Location           | Purpose                   |
| ---------------- | ------------------ | ------------------------- |
| `calculator`     | `tools.py`         | Mathematical calculations |
| `get_pricing`    | `zantara_tools.py` | Bali Zero service pricing |
| `team_knowledge` | `zantara_tools.py` | Team member search/list   |

**Implementation:** `reasoning.py:867-883`

**⚠️ DO NOT modify trusted tools check without understanding the full flow.**

### CRM RBAC (Role-Based Access Control)

**File:** `backend/app/routers/crm_practices.py`

| Role                                              | Access                                      |
| ------------------------------------------------- | ------------------------------------------- |
| Admin (`zero@balizero.com`, `admin@balizero.com`) | All clients and practices                   |
| Team Member                                       | Only clients with `assigned_to` = own email |

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
# Solution:
# 1. First check virtualenv is activated
which python  # Should show .../apps/backend-rag/.venv/bin/python
# 2. If not, activate it
cd apps/backend-rag
source .venv/bin/activate
# 3. Run with PYTHONPATH=.
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

| Document                 | Path                                                     | When to Read                        |
| ------------------------ | -------------------------------------------------------- | ----------------------------------- |
| **AI Handover Protocol** | `docs/ai/AI_HANDOVER_PROTOCOL.md`                        | Always (this is the brain)          |
| **System Map 4D**        | `docs/SYSTEM_MAP_4D.md`                                  | To understand architecture          |
| **Observability Guide**  | `docs/operations/OBSERVABILITY_GUIDE.md`                 | For debugging/monitoring            |
| **Deploy Checklist**     | `docs/operations/DEPLOY_CHECKLIST.md`                    | Before deploying                    |
| **Intel Pipeline**       | `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md` | For news scraper                    |
| **ZANTARA Fluidity**     | `docs/ZANTARA_FLUIDITY_AND_STRENGTH.md`                  | Miglioramenti fluidità (2026-01-19) |
| **Test Best Practices**  | `docs/TEST_CONFIGURATION_BEST_PRACTICES.md`              | Configurazione test (2026-01-19)    |

---

## 🚀 COMMON WORKFLOWS

### Setup Environment (First Time)

```bash
# 1. Create virtualenv
cd apps/backend-rag
python3 -m venv .venv

# 2. Activate virtualenv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Verify setup
which python  # Should show: .../apps/backend-rag/.venv/bin/python
python --version  # Should show: Python 3.11.x
```

**⚠️ IMPORTANT:** Always activate venv before any Python command:

```bash
cd apps/backend-rag
source .venv/bin/activate  # Do this EVERY time
```

### Adding a New API Endpoint

1. **Activate virtualenv** (if not already active)
2. **Create router** in `backend/app/routers/`

   ```python
   from fastapi import APIRouter
   router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

   @router.get("/")
   async def list_items() -> list[dict]:
       # Implementation
   ```

3. **Add business logic** in `backend/services/`

   ```python
   # backend/services/my_service.py
   async def get_items() -> list[dict]:
       # Business logic here
   ```

4. **Register router** in `backend/app/main_cloud.py`

   ```python
   from backend.app.routers import my_router
   app.include_router(my_router.router)
   ```

5. **Add tests** in `backend/tests/api/`
6. **Run tests** (with venv active): `source .venv/bin/activate && pytest tests/...`
7. **Run Sentinel** before committing (with venv active)

### Modifying RAG Pipeline

**⚠️ CRITICAL:** Read `docs/operations/AGENTIC_RAG_FIXES.md` first (if it exists)

**Key files:**

- `backend/services/rag/agentic/reasoning.py` - Evidence scoring
- `backend/services/rag/agentic/llm_gateway.py` - LLM routing
- `backend/services/rag/agentic/orchestrator.py` - Main orchestrator

**Test changes:**

```bash
cd apps/backend-rag
source .venv/bin/activate  # MUST activate venv first
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

| Variable         | Purpose               | Where Used |
| ---------------- | --------------------- | ---------- |
| `DATABASE_URL`   | PostgreSQL connection | Backend    |
| `QDRANT_URL`     | Vector DB connection  | Backend    |
| `OPENAI_API_KEY` | Embeddings            | Backend    |
| `GOOGLE_API_KEY` | Gemini LLM            | Backend    |
| `JWT_SECRET_KEY` | Auth tokens           | Backend    |
| `PORT`           | Server port           | Fly.io     |

**Check secrets:**

```bash
fly secrets list -a nuzantara-rag
```

---

## ✅ PRE-COMMIT CHECKLIST

Before asking for review:

### Basic Requirements

- [ ] **Virtualenv activated** (`source .venv/bin/activate`)
- [ ] Ran `./sentinel` and it passed
- [ ] All new functions have type hints
- [ ] No hardcoded secrets or URLs
- [ ] Used async/await (no blocking calls)
- [ ] Absolute imports only

### Production-Ready Standard (for non-trivial features)

- [ ] **Tests written** - Unit tests for each function, integration test for full flow
- [ ] **Logging added** - INFO logs for success paths, WARNING for edge cases, ERROR for failures
- [ ] **Metrics defined** - Performance KPIs, success rates, error rates documented
- [ ] **Documentation created**:
  - [ ] Code docstrings with examples
  - [ ] Technical doc in `docs/` (if new system/feature)
  - [ ] Session notes in `CLAUDE.md` or relevant memory file
- [ ] **Error handling** - Try/except blocks, graceful fallbacks, clear error messages
- [ ] **Type safety** - Type hints on all functions, TypedDict for complex state

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
A: `docker compose up -d` for services, then `cd apps/backend-rag && source .venv/bin/activate && PYTHONPATH=. python -m backend.app.main_cloud`

**Q: How do I deploy?**  
A: See `docs/operations/DEPLOY_CHECKLIST.md`

**Q: Why is my import failing?**  
A: Check: 1) Virtualenv activated (`which python` shows `.venv/bin/python`), 2) Using absolute imports, 3) Running from `apps/backend-rag` with `PYTHONPATH=.`

---

## 📝 NOTES FOR AI ASSISTANTS

1. **Always read the handover protocol** (`docs/ai/AI_HANDOVER_PROTOCOL.md`) - it's the "brain" of the project
2. **Use the toolkit** - Sentinel, Scribe, Observability stack are your friends
3. **Follow the golden rules** - They exist for good reasons
4. **Check critical fixes** - Especially evidence scoring and trusted tools
5. **Test before asking** - Run Sentinel, check logs, verify locally

---

**Remember:** This is a production system. Be careful, test thoroughly, and use the observability tools to verify your changes.

---

## 📚 RECENT UPDATES (2026-01-19)

### Nuovi Documenti

- **`docs/ZANTARA_FLUIDITY_AND_STRENGTH.md`** - Documentazione completa miglioramenti fluidità e proattività
- **`docs/TEST_CONFIGURATION_BEST_PRACTICES.md`** - Best practices per configurazione test e gestione secrets

### Miglioramenti Documentati

- ✅ Threshold ABSTAIN: 0.3 → 0.2 (maggiore fluidità)
- ✅ Messaggio ABSTAIN proattivo (suggerisce alternative)
- ✅ Proattività nel prompt (suggerisce sempre prossimi passi)
- ✅ FollowupService con logging e metriche complete
- ✅ 57+ test per verificare fluidità e forza

**Last Updated:** 2026-01-19

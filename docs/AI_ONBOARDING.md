# AI ONBOARDING GUIDE - Nuzantara Project

**Last Updated:** 2026-02-07
**Purpose:** Quick-start guide for AI assistants working on Project Nuzantara

**System Stats:**

- Router Files: 68
- Services: 228 Python files
- Test Files: 477
- Qdrant Collections: `kbli_2025_final` (9,612 docs), `legal_unified_hybrid`, `visa_oracle`, `tax_genius_hybrid`
- Knowledge Graph: 34,606 nodes, 30,628 edges (PostgreSQL)

> **READ THIS FIRST** before making any changes to the codebase.

---

## QUICK START CHECKLIST

When starting a new session, verify you understand:

- [ ] **Virtualenv:** `.venv` created and activated (`source .venv/bin/activate`)
- [ ] **Project Structure:** Monorepo with `apps/backend-rag` (FastAPI) and `apps/mouth` (Next.js)
- [ ] **Golden Rules:** No root execution, absolute imports, async-first, type hints required
- [ ] **Critical Knowledge:** Embedding model must be `text-embedding-3-small`, KBLI has flat payload
- [ ] **Deployment:** Backend on Fly.io (`nuzantara-rag`, Singapore), Frontend on Vercel

---

## THE GOLDEN RULES (MUST FOLLOW)

### 1. VIRTUALENV IS MANDATORY

Always use the project's virtualenv. Never use system Python or pyenv directly.

```bash
cd apps/backend-rag
source .venv/bin/activate

# Verify
which python  # Should show: .../apps/backend-rag/.venv/bin/python

# Setup (first time only)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. NO ROOT EXECUTION

```bash
# WRONG
python script.py

# CORRECT
cd apps/backend-rag
source .venv/bin/activate
python -m backend.scripts.script_name
```

### 3. PATH DISCIPLINE

```python
# WRONG - Relative imports
from ..core import config

# CORRECT - Absolute imports
from backend.core import config
```

Always run from `apps/backend-rag` root with virtualenv activated and `PYTHONPATH=.`

### 4. ASYNC FIRST

```python
# WRONG - Blocking
import requests
response = requests.get(url)

# CORRECT - Async
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### 5. TYPE HINTS REQUIRED

```python
# WRONG
def process_query(query):
    return result

# CORRECT
def process_query(query: str) -> dict[str, Any]:
    return result
```

### 6. NO HARDCODING

```python
# WRONG
api_key = "sk-1234567890"

# CORRECT
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

### 7. SEPARATION OF DATA AND LOGIC

- **Volatile Data** (prices, names, addresses) -> Knowledge Base (Qdrant/Postgres) or `settings`
- **Business Logic** -> `backend/services/`
- **Never** hardcode data in code

### 8. CLEAN LOGGING

- **Backend:** Never use `print()`. Always use `logger.info()`, `logger.warning()`, etc.
- **Frontend:** Never leave `console.log()` in production. Remove before commit.

### 9. QUALITY STANDARD

Write code that works, is testable, and handles errors. Scale effort to complexity:

**For production features** (new services, agents, workflows):
- Tests for core logic (unit + integration)
- Structured logging at key steps
- Error handling with graceful degradation
- Type hints on all functions

**Can skip for:**
- One-off scripts, prototypes, trivial helpers (<10 lines)

The goal is pragmatic quality, not ceremony. A well-tested 50-line service beats a 1,500-line over-documented one.

---

## CRITICAL KNOWLEDGE (PREVENTS REAL BUGS)

### Embedding Model - MUST be `text-embedding-3-small`

All ingestion scripts use `text-embedding-3-small` (1536 dims). Different OpenAI embedding models produce **incompatible vector spaces** even at the same dimensions. If you see bad search results, check:

```bash
# Verify the running model matches ingestion
curl https://nuzantara-rag.fly.dev/health | jq '.embeddings.model'
# Must return: "text-embedding-3-small"

# Fly.io secret must match
fly secrets list -a nuzantara-rag | grep EMBEDDING_MODEL
```

The Fly.io secret `EMBEDDING_MODEL` was previously set to `text-embedding-ada-002` which caused silent search quality degradation. This was fixed 2026-02-06.

### KBLI Collection - Flat Payload (NOT Nested)

The `kbli_2025_final` collection in Qdrant has a **flat payload structure**:

```json
{
  "kode_kbli": "56101",
  "judul": "Restoran",
  "content": "...",
  "sektor_id": "I",
  "pma_status": "Terbuka",
  "skala_usaha": "Menengah",
  "kategori_risiko": "Menengah Rendah"
}
```

This is **NOT** nested under `metadata`/`text` like other collections. Consequences:

- `SearchService.search_collection()` assumes nested payloads - **do not use it for KBLI**
- KBLI router bypasses SearchService and queries Qdrant REST API directly via `_search_kbli_qdrant()`
- If you need to add a new collection with flat payloads, follow the KBLI pattern

**Key files:**
- Ingestion: `scripts/ingestion/ingest_kbli_2025_final.py`
- Router: `backend/app/routers/kbli_notebook.py` (public, no auth)
- KG data: PostgreSQL `kg_nodes` with entity_id `kbli:{code}`, `kg_edges` for relationships
- Qdrant is source of truth for `pma_status` and `kategori_risiko` (not PostgreSQL KG)

### Pricing - ONLY from PricingTool

Bali Zero client-facing prices come **exclusively** from:
- File: `backend/data/bali_zero_official_prices_2025.json`
- Tool: `PricingTool` (Tool #2 in orchestrator)

The Knowledge Graph contains `HAS_FEE` relationships with **government fees** (PNBP), not Bali Zero prices. Never expose KG fee data to clients.

### Auth Middleware

**File:** `backend/middleware/hybrid_auth.py`

Public endpoints use `path.startswith(endpoint)` matching. Currently public:
- `/api/v1/kbli-notebook/` (KBLI search, inspect, chat)
- `/health`, `/health/detailed`, `/health/ready`, `/health/live`

Agentic RAG (`/api/agentic-rag/query`) requires JWT authentication.

---

## PROJECT STRUCTURE

```
nuzantara/
├── apps/
│   ├── backend-rag/          # CORE: FastAPI Backend (Fly.io)
│   │   ├── backend/
│   │   │   ├── app/          # FastAPI entrypoint (main_cloud.py)
│   │   │   │   └── routers/  # 68 route files
│   │   │   ├── core/         # Config, Security, Logging
│   │   │   ├── services/     # Business Logic (228 files)
│   │   │   │   ├── rag/agentic/  # CORE: Orchestrator, ReAct, LLM Gateway
│   │   │   │   ├── knowledge_graph/  # KG extraction + query
│   │   │   │   └── memory/       # Memory Orchestrator
│   │   │   └── tests/        # 477 test files
│   │   └── scripts/          # Maintenance + ingestion scripts
│   │
│   ├── mouth/                # Frontend: Next.js + React (Vercel)
│   │   └── src/
│   │       ├── app/          # Pages (chat, portal, dashboard, documents)
│   │       ├── components/   # UI components
│   │       └── lib/          # API clients, store
│   │
│   ├── nuzantara-mcp/        # MCP Server (FastMCP, stdio transport)
│   │   └── nuzantara_mcp/
│   │       └── server.py     # 7 tools, 3 prompts, 1 resource
│   │
│   ├── bali-intel-scraper/   # News processing pipeline
│   └── zantara-media/        # Editorial content system
│
├── docs/                     # Documentation
├── scripts/                  # Root-level utilities
└── source_documents/         # KBLI JSON, legal PDFs
```

---

## DEPLOYMENT

### Backend (Fly.io)

```bash
cd apps/backend-rag
fly deploy --strategy rolling
```

- App: `nuzantara-rag` (2 machines, Singapore)
- Health: `GET /health` shows runtime state
- Secrets: `fly secrets list -a nuzantara-rag`
- Logs: `fly logs -a nuzantara-rag`

### Frontend (Vercel)

Auto-deploys from `apps/mouth/` on push to main. No manual deploy needed.

### Git Commits

Pre-commit hooks run prettier on all files. Prettier fails on non-JS files (Python, .txt, .md with non-standard formatting). Use `--no-verify` when committing non-JS changes:

```bash
git commit --no-verify -m "your message"
```

This is a known issue, not a hack. The hook validates JS/TS formatting which is correct behavior - it just doesn't know to skip non-JS files.

---

## MCP SERVER (Nuzantara RAG)

**Package:** `apps/nuzantara-mcp/` (FastMCP 2.x, stdio transport)

Exposes the Fly.io backend as MCP tools for AI agents (OpenClaw, Claude Code).

**Tools:**
| Tool | Endpoint | Auth |
| --- | --- | --- |
| `search_kbli` | `GET /api/v1/kbli-notebook/search` | Public |
| `inspect_kbli` | `GET /api/v1/kbli-notebook/inspect/{code}` | Public |
| `chat_kbli` | `POST /api/v1/kbli-notebook/chat` | Public |
| `ask_legal` | `POST /api/agentic-rag/query` | JWT |
| `check_health` | `GET /health` | Public |
| `check_health_detailed` | `GET /health/detailed` | Public |
| `get_qdrant_metrics` | `GET /health/metrics/qdrant` | Public |

**Run locally:**
```bash
pip install -e apps/nuzantara-mcp/
nuzantara-mcp  # starts stdio server
```

**FastMCP 2.x gotcha:** Use `instructions=` not `description=` in the constructor.

---

## CRITICAL FIXES & KNOWN ISSUES

### Evidence Score System

**File:** `backend/services/rag/agentic/reasoning.py`

The system uses `evidence_score` (0.0-1.0) to decide responses:

- **< 0.3** -> ABSTAIN (refuses to answer)
- **0.3-0.6** -> Cautious response
- **> 0.6** -> Normal response

### Trusted Tools (Bypass Evidence Check)

These tools bypass evidence scoring because they provide their own evidence:

| Tool | Location | Purpose |
| --- | --- | --- |
| `calculator` | `tools.py` | Mathematical calculations |
| `get_pricing` | `zantara_tools.py` | Bali Zero service pricing |
| `team_knowledge` | `zantara_tools.py` | Team member search/list |

**Implementation:** `reasoning.py:867-883`

**DO NOT modify trusted tools check without understanding the full flow.**

### CRM RBAC (Role-Based Access Control)

**File:** `backend/app/routers/crm_practices.py`

| Role | Access |
| --- | --- |
| Admin (`zero@balizero.com`, `admin@balizero.com`) | All clients and practices |
| Team Member | Only clients with `assigned_to` = own email |

### Date Conversion Fix

**Files:** `crm_enhanced.py`, `crm_clients.py`

PostgreSQL DATE fields must be converted explicitly when using asyncpg:

```python
date_value = row['date_field'].isoformat() if row['date_field'] else None
```

---

## DEBUGGING PATTERNS

### Check Evidence Scoring

```bash
fly logs -a nuzantara-rag | grep -E "Evidence|Trusted|ABSTAIN"
```

### Check Embedding Model

```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool | grep model
```

### Common Import Errors

```bash
# Error: ImportError: attempted relative import with no known parent package
# Fix: activate venv + PYTHONPATH
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m backend.scripts.script_name
```

### Fly.io Crashes

Common causes:
1. Missing `PORT` env var -> Check `fly.toml`
2. Missing `QDRANT_URL` -> Check secrets
3. Database connection -> Check `DATABASE_URL`

```bash
fly logs -a nuzantara-rag
fly ssh console -a nuzantara-rag
```

### Rogue Changes from Other AI Tools

Other AI tools (Gemini, Windsurf) have historically broken shared files like `logging_utils.py` (removing `get_logger`) and `db/utils.py` (removing `db_retry`). Before deploying, check for unexpected modifications:

```bash
git diff --name-only HEAD -- apps/backend-rag/backend/
```

If many files were modified unexpectedly, restore and re-apply only your changes:

```bash
git checkout HEAD -- apps/backend-rag/backend/
# Then re-apply your targeted changes
```

---

## ENVIRONMENT VARIABLES

**Critical variables (check before running):**

| Variable | Purpose | Where Used |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection | Backend |
| `QDRANT_URL` | Vector DB connection | Backend |
| `OPENAI_API_KEY` | Embeddings (`text-embedding-3-small`) | Backend |
| `EMBEDDING_MODEL` | Must be `text-embedding-3-small` | Backend |
| `GOOGLE_API_KEY` | Gemini LLM | Backend |
| `JWT_SECRET_KEY` | Auth tokens | Backend |
| `PORT` | Server port | Fly.io |

```bash
fly secrets list -a nuzantara-rag
```

---

## COMMON WORKFLOWS

### Adding a New API Endpoint

1. Create router in `backend/app/routers/`
2. Add business logic in `backend/services/`
3. Register router in `backend/app/main_cloud.py`
4. Add tests in `backend/tests/`
5. If endpoint should be public, add to `hybrid_auth.py` public endpoints list

### Modifying RAG Pipeline

Read `docs/operations/AGENTIC_RAG_FIXES.md` first (if it exists).

**Key files:**
- `backend/services/rag/agentic/reasoning.py` - Evidence scoring
- `backend/services/rag/agentic/llm_gateway.py` - LLM routing
- `backend/services/rag/agentic/orchestrator.py` - Main orchestrator

### Adding a New Qdrant Collection

If the payload is flat (like KBLI), bypass `SearchService` and query Qdrant REST API directly. If nested (`text` + `metadata` keys), use `SearchService.search_collection()`.

Always use `text-embedding-3-small` for embeddings. Verify with `GET /health`.

### Frontend Changes

- Pages: `apps/mouth/src/app/`
- Components: `apps/mouth/src/components/`
- API clients: `apps/mouth/src/lib/api/`

```bash
cd apps/mouth
npm run dev
```

---

## PRE-COMMIT CHECKLIST

- [ ] Virtualenv activated
- [ ] All new functions have type hints
- [ ] No hardcoded secrets or URLs
- [ ] Used async/await (no blocking calls)
- [ ] Absolute imports only
- [ ] Tests pass for modified code
- [ ] `--no-verify` used only for non-JS file commits (not to skip failing tests)

---

## ESSENTIAL DOCUMENTATION

| Document | Path | When to Read |
| --- | --- | --- |
| **AI Handover Protocol** | `docs/ai/AI_HANDOVER_PROTOCOL.md` | Always (project brain) |
| **System Map 4D** | `docs/SYSTEM_MAP_4D.md` | Architecture overview |
| **Observability Guide** | `docs/operations/OBSERVABILITY_GUIDE.md` | Debugging/monitoring |
| **Deploy Checklist** | `docs/operations/DEPLOY_CHECKLIST.md` | Before deploying |
| **Database Architecture** | `docs/DATABASE_ARCHITECTURE_V2.md` | DB schema reference |
| **KG Value Assessment** | `docs/KG_VALUE_ASSESSMENT_2026_01_18.md` | Knowledge Graph details |
| **Intel Pipeline** | `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md` | News scraper |

---

## NOTES FOR AI ASSISTANTS

1. **Read the critical knowledge section** - embedding model and KBLI payload structure prevent real production bugs
2. **Follow the golden rules** - they exist because we hit real problems without them
3. **Check for rogue changes** before deploying - other AI tools may have modified shared files
4. **Use `--no-verify` for non-JS commits** - prettier pre-commit hook is known to fail on Python/markdown
5. **Don't over-document** - code that speaks for itself doesn't need a 450-line report. Focus on why, not what.

**Remember:** This is a production system serving real clients. Be careful with changes, verify the embedding model matches, and test your work.

# CLAUDE.md - Nuzantara Project Context for Claude Code

## 0. Machine Identification (IMPORTANT)

**You MUST identify which machine you are running on at session start.**

Two machines exist on the local network:

| Machine | User             | Hostname      | Role                       |
| ------- | ---------------- | ------------- | -------------------------- |
| **Pro** | `nuzantara`      | `Nuzantara`   | Development (48GB, M4 Pro) |
| **Air** | `antonellosiano` | `Nuzantara-9` | Server H24 (16GB, M4)      |

**At every session start, run this check:**

```bash
echo "Machine: $(whoami)@$(hostname)" && \
OTHER=$(if [ "$(whoami)" = "nuzantara" ]; then echo "air"; else echo "pro"; fi) && \
ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE" && \
LOCAL_HEAD=$(git log --oneline -1 2>/dev/null) && \
REMOTE_HEAD=$(ssh -o ConnectTimeout=3 $OTHER 'cd ~/Desktop/projects/nuzantara 2>/dev/null || cd ~/Desktop/nuzantara 2>/dev/null; git log --oneline -1' 2>/dev/null) && \
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then echo "Git sync: OK ($LOCAL_HEAD)"; else echo "Git sync: OUT OF SYNC! Local=$LOCAL_HEAD Remote=$REMOTE_HEAD"; fi
```

This tells you:

- `whoami` = `nuzantara` → you are on **Pro**
- `whoami` = `antonellosiano` → you are on **Air**
- Whether the other machine is reachable via SSH
- Whether both repos are on the same commit

**Always prefix your first response with which machine you're on**, e.g. "[Pro]" or "[Air]".
If the peer is unreachable or out of sync, **warn the user immediately**.

**SSH between machines:** `ssh air` (from Pro) / `ssh pro` (from Air) — uses mDNS, works on any WiFi.
See `docs/PRO_AIR_CONNECTION.md` for full details.

---

## 1. Project Overview

**Name:** Nuzantara (Zantara)
**Version:** 5.2.0
**Type:** Production AI-powered business intelligence platform for Bali Zero
**Business:** Indonesian business services (visa, company setup, tax, property) in Bali — 5000+ clients
**URL:** https://kita.balizero.com

### Architecture

**Monorepo structure (20 apps):**

- `apps/mouth/` - Next.js frontend (Vercel) — kita.balizero.com + my.balizero.com + prime.balizero.com
- `apps/backend-rag/` - Python FastAPI RAG backend (Fly.io)
- `apps/nuzantara-mcp/` - MCP server v2.1 (109 tools, 10 prompts, 5 resources, 8 chains)
- `apps/nuzantara-mcp-advanced/` - Advanced MCP (Fly.io ops, diagnostics, 14 tools)
- `apps/nuzantara-mcp-browser/` - Browser automation MCP
- `apps/bali-intel-scraper/` - Intel pipeline (runs LOCALLY on Pro via OpenClaw, NOT Fly)
- `apps/evaluator/` - Quality assurance + Core Guardian V3
- `apps/war-room/` - Operations dashboard + Canva automation
- `apps/graph-engine/` - Graph processing engine
- `apps/kbli-voice/` - KBLI voice interface
- `apps/zantara-media/` - Editorial content system
- `apps/admin-dashboard/` - Admin UI
- `apps/webapp/` - Web application
- `apps/kbli-navigator/` - KBLI 2025 Navigator interface
- `apps/calendar/` - Subdomain satellite (calendar.balizero.com)
- `apps/drive/` - Subdomain satellite (drive.balizero.com)
- `apps/knowledge/` - Subdomain satellite (knowledge.balizero.com)
- `apps/mail/` - Subdomain satellite (mail.balizero.com)
- `apps/web/` - Subdomain satellite (zantara.balizero.com)
- `packages/core/` - Core libraries + BZ design tokens + BZLogo
- `packages/kb/` - Knowledge base

### Tech Stack

<!-- DOCSYNC:BACKEND_STATS_START -->

- **Backend:** Python 3.11+, FastAPI, 90 routers, 253 services, 419 test files
<!-- DOCSYNC:BACKEND_STATS_END -->
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** 56,113 nodes, 161,173 edges
<!-- DOCSYNC:VECTOR_STATS_START -->
- **Vector Collections:** 10 live on Fly.io (93,283 documents), 11 defined in code
<!-- DOCSYNC:VECTOR_STATS_END -->
- **Embedding Model:** `text-embedding-3-small` (1536 dims) — **NEVER CHANGE**
- **Search Pipeline:** Hybrid (BM25+Dense+RRF) + CrossEncoder reranking (enabled 2026-03-24)

### Key Terms (for new AI agents)

- **OpenClaw**: The agent runtime (macOS native). Runs cron jobs, Telegram polling, background tasks. Gateway at `loopback:18789`. Config in `~/.openclaw/`.
- **mcporter**: MCP-to-OpenClaw bridge tool. Wraps MCP tool calls for OpenClaw consumption. Wrappers in `~/.local/bin/`.
- **Bali Zero**: The client-facing business brand. Indonesian business services (visa, company setup, tax, property) in Bali.
- **Zantara**: The AI assistant persona used in all client-facing channels.

### Verify Setup (run on first session)

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no 2>/dev/null && echo "✅ Tests OK"
```

If both pass, you're ready to work.

---

## 2. Claude Code Behavior Rules (IMPORTANT)

**DO NOT ask the user to write code.** You are authorized to edit, write, and execute code directly.

- Use `Edit`, `Write`, `Bash` without asking permission
- `defaultMode: acceptEdits` means act first, ask if blocked
- Only ask if you genuinely need user input (e.g., choosing between multiple valid approaches)
- **NEVER** ask "should I write this?" or "do you want me to...?" — just do it

### Browser Automation Rules (ENFORCE STRICTLY)

- **ALWAYS use `mcp__claude-in-chrome__*` tools** for any browser interaction
- **NEVER fall back to `mcp__playwright__*` autonomously** — only if user explicitly orders it
- **Text before screenshot**: use `get_page_text`, `find`, `javascript_tool`, `read_console_messages` first
- Screenshots (`computer`) only for visual QA (layout, colors, logo) — never for content/debug
- If Claude-in-Chrome fails → run recovery steps from the `browser` skill, then report to user
- See skill: `browser` (`~/.claude/skills/browser.md`)

**Exception:** Only ask for decisions on:

- Architecture choices with trade-offs (use `AskUserQuestion`)
- Production deployments (use risk/reversibility judgment)
- Destructive operations (rm, git reset --hard, etc.)

### Federation Orchestrator (AUTOMATICO)

**Per task complessi, usa l'orchestratore LangGraph:**

```bash
python scripts/federation_orchestrator.py "task description"
# oppure con --telegram CHAT_ID per output su Telegram
# oppure con --no-confirm per skip conferma umana
```

L'orchestratore classifica il task (Haiku), lancia i dispatch necessari (Gemini search/explore, Codex sandbox), assembla il contesto, e lo salva in `ai-dispatch-output/`. Se il rischio è alto, forza un red team review.

**Trigger che DEVONO passare dall'orchestratore (non fare a mano):**

| Trigger                                            | L'orchestratore lancia    | Motivo                                 |
| -------------------------------------------------- | ------------------------- | -------------------------------------- |
| KBLI, visa, normativa indonesiana                  | Gemini `search`           | Claude hallucina su regolamenti        |
| Refactor che tocca 3+ app del monorepo             | Gemini `explore`          | 1M ctx mappa tutte le dipendenze       |
| **Grounding Architettura / Regola Oracolo**        | **NotebookLM `oracolo`**  | **Ground Truth da NB-1 (citations)**   |
| **Deep Research (nuove tech 2026)**                | **NotebookLM `research`** | **Autonomous web research (sources)**  |
| Alembic migration / schema change                  | Codex `sandbox`           | Testa upgrade+downgrade in isolamento  |
| Pre-deploy Fly.io (backend)                        | Gemini `redteam`          | Mai deploy senza red team              |
| Fix a `dependencies.py` o `service_initializer.py` | Codex `sandbox`           | Import chain = single point of failure |

**Task semplici** (fix un bug, aggiorna un componente): procedi direttamente senza orchestratore.

### Escalations (leggere a inizio sessione)

Controlla `shared/escalations.json` — se ci sono pending, gestiscili prima di altro lavoro.

## 3. Golden Rules (ENFORCE STRICTLY)

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
11. **Async HTTP Clients** - NEVER instantiate `httpx.AsyncClient()` inside methods or loops. Always use a persistent client managed at the service level (pattern: `_get_client`) and register its closure in the `lifespan` of `app_factory.py`.

## 4. Development Commands

### Backend (FastAPI)

```bash
# Activate virtualenv (ALWAYS .venv, not venv)
cd apps/backend-rag
source .venv/bin/activate

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
# Backend to Fly.io (CANONICAL command — always use this form)
cd apps/backend-rag && fly deploy --strategy rolling

# Frontend to Vercel (auto-deploy on git push to main, no manual deploy needed)
git push origin main
```

## 5. Critical Paths

### Backend Structure

```
apps/backend-rag/
├── backend/
│   ├── app/                # ⚠️ FastAPI app (routers, services, setup live HERE)
│   │   ├── routers/        # API endpoints (88 routers)
│   │   ├── services/       # App-level services (CRM, auth, metrics)
│   │   ├── setup/          # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py # ⚠️ Imported by ALL routers — test before deploy
│   │   ├── main.py         # FastAPI app entry (alias for main_cloud.py)
│   │   └── main_cloud.py   # Actual entrypoint for Fly.io
│   ├── services/           # Core business logic (244 services total)
│   │   ├── rag/agentic/    # Orchestrator, ReAct, LLM Gateway
│   │   ├── knowledge_graph/ # KG extraction + query
│   │   └── ...             # analytics, compliance, journey, memory, social
│   ├── channels/           # 7 channels (whatsapp, telegram, instagram, twitter, web, gchat, slack)
│   ├── core/               # Config, security, logging
│   ├── llm/                # LLM clients (Gemini, Ollama, OpenRouter)
│   ├── prompts/            # ⭐ Prompt Single Source of Truth (zantara_core.py)
│   ├── middleware/          # Auth, rate-limit, tracing
│   └── migrations/         # Alembic migrations (up to 060)
├── tests/                  # 385 test files
├── .venv/                  # ⚠️ Python virtualenv (ALWAYS .venv, not venv)
├── requirements.txt
└── fly.toml
```

**IMPORTANT:** Routers are in `backend/app/routers/`, NOT `backend/routers/`. Services span both `backend/services/` (core) and `backend/app/services/` (app-level).

### Prompt Architecture (Single Source of Truth)

```
backend/prompts/
├── __init__.py              # Re-exports ZANTARA_MASTER_TEMPLATE, CREATOR_PERSONA, TEAM_PERSONA
├── zantara_core.py          # ⭐ THE file — all prompt sections as composable constants
├── channel_overlays.py      # Per-channel config (word limits, markdown, emoji)
├── few_shot_examples.py     # Consolidated few-shot examples
├── zantara_persona.py       # Backward compat wrapper → imports from zantara_core
├── whatsapp_persona.py      # Dynamic builder for WhatsApp context → imports from zantara_core
└── zantara_prompt_builder.py # Legacy builder → imports from zantara_core
```

**Rule:** To add/edit ANY Zantara prompt rule, edit ONLY `zantara_core.py`. All consumers import from it.

**Sections in `zantara_core.py`:**
`SECURITY_BOUNDARY` · `TOOL_USAGE_POLICY` · `SYSTEM_INSTRUCTIONS` · `KNOWLEDGE_GOVERNANCE` ·
`LANGUAGE_PROTOCOL` · `GREETING_RULES` · `CITATION_RULES` · `INTERNAL_MONOLOGUE` ·
`ESCALATION_PROTOCOL` · `CRASH_PROTOCOL` · `CLOSING_PHRASES` · `CREATOR_PERSONA` ·
`TEAM_PERSONA` · `ZANTARA_MASTER_TEMPLATE`

### Frontend Structure

```
apps/mouth/
├── app/              # Next.js App Router
├── components/       # React components
├── lib/              # Utilities
├── public/           # Static assets
└── styles/           # Tailwind CSS
```

## 6. Domain-Specific Knowledge

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

✅ **CORRECT (actual Qdrant fields):**

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

<!-- DOCSYNC:EMBEDDING_FROZEN_START -->

**CRITICAL:** This model is FROZEN. Changing it would invalidate 93,283 existing vectors.

<!-- DOCSYNC:EMBEDDING_FROZEN_END -->

**Never:** Switch to another model without explicit authorization and full re-indexing plan.

## 7. MCP Servers

**Primary:** `apps/nuzantara-mcp/` (v2.1, FastMCP, stdio transport)
**Status:** **Federation v3 Phase 2 ACTIVE** (2026-03-23)
**Capabilities:**

- **131 Tools** total across Federation bridge (118 Nuzantara + 13 Advanced)
- **10 Prompts** for guided workflows
- **5 Resources** for knowledge base access
- **8 Workflow Chains** for deterministic automation (daily_ops_autopilot, new_client_onboarding, practice_lifecycle_check, intel_pipeline, weekly_report, client_health_monitor, compliance_autopilot, journey_accelerator)

**Additional MCP servers:**

- `apps/nuzantara-mcp-advanced/` — Fly.io ops, deployment readiness, code search, diagnostics (14 tools)
- `apps/nuzantara-mcp-browser/` — Browser automation
- `ga4-analytics` — GA4 property 505466833 (BALI ZERO WEB stream, G-S3H2M6VXWT)
- `google-search-console` — 19 SEO tools, SA auth, site owner on balizero.com
- `ocr-tesseract` — Document OCR with Indonesian language support

**MCP Bridge (OpenClaw):** 129 tools connected via mcporter wrappers in `~/.local/bin/`. macOS provenance fix applied.

## 8. Deployment Architecture

### Production Stack

- **Frontend:** Vercel (CDN, Edge Functions)
- **Backend:** Fly.io `nuzantara-rag` (Singapore, shared-cpu-2x, **2GB RAM**, auto_stop=true, min=0)
- **Databases:**
  - PostgreSQL: Fly.io `nuzantara-postgres` (**2GB RAM**, v0.1.0, upgraded 2026-03-14)
  - Qdrant: Fly.io `nuzantara-qdrant` (2GB, v1.17.0, upgraded 2026-03-24)
  - Redis: Upstash or Fly.io

### Fly.io — SOLO 3 APP (updated 2026-03-14)

| App                  | CPU       | RAM | Auto-stop     | Note                    |
| -------------------- | --------- | --- | ------------- | ----------------------- |
| `nuzantara-rag`      | shared-2x | 2GB | ✅ yes, min=0 | Cold start ~35s         |
| `nuzantara-postgres` | shared-1x | 2GB | no            | v0.1.0, backup → Tigris |
| `nuzantara-qdrant`   | shared-1x | 2GB | no            | v1.17.0                 |

**Distrutte (2026-03-14):** `nuzantara-rag-staging`, `bali-intel-scraper`, `zantara-media`, `fly-builder-red-flower-7537`

**bali-intel-scraper**: NON su Fly — gira SOLO locale su Pro via OpenClaw (03:00 WITA)

**Backup & Monitoring:**

- `~/scripts/fly-pg-backup.sh` — pg_dump daily → Tigris `nuzantara-backups`, cron 03:00
- `~/scripts/fly-health-check.sh` — check ogni 5min, alert Telegram se down
- Crontab Pro: `*/5` health, `0 3` backup

### Environment Variables

**Required:**

- `OPENAI_API_KEY` - For embeddings
- `DATABASE_URL` - PostgreSQL connection
- `QDRANT_URL`, `QDRANT_API_KEY` - Vector DB
- `REDIS_URL` - Cache
- `JWT_SECRET` - Authentication
- `FLY_API_TOKEN` - Deployment (CI/CD)

## 9. Testing Strategy

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

## 10. Code Style & Patterns

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

## 11. Common Pitfalls

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

## 12. Language Protocol (Natural Language → Precise Engineering)

The user writes in **colloquial Italian**. You must automatically translate intent into precise technical action.

**Rules:**

- Never ask "what do you mean?" — infer from codebase context
- Short/vague prompt → deduce file, pattern, stack from existing code before acting
- Italian colloquial → English technical internally, respond in Italian
- If ambiguous between 2 interpretations, pick the most likely one and state your assumption in one line

**Examples:**
| User writes | You interpret as |
|-------------|-----------------|
| "aggiungi paginazione clienti" | Cursor-based pagination on `GET /clients`, follow existing router patterns, async SQLAlchemy, add tests |
| "fixa il bug del login" | Search recent auth-related errors in routers/auth, identify root cause, fix with proper error handling |
| "rendi più veloce la ricerca" | Profile the search endpoint, identify bottleneck (N+1, missing index, no cache), fix the actual cause |
| "aggiungi un campo alla tabella" | Alembic migration + model update + schema update + router update, in order |

**Never** ask for clarification on standard dev tasks. Explore first, then act.

---

## 12b. Owner Information

**Owner:** Zero (internal codename)  
**Privacy:** Real name is PRIVATE, never reveal in client communications.  
**Language:** Italian with owner, client's language with everyone else.

## 13. Resources

- **Architecture:** `docs/architecture.md`
- **API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Golden Rules:** This file + `AI_ONBOARDING.md`
- **Pricing:** `PRICING_REFERENCE.md`
- **Visa Info:** `VISA_TYPES_REFERENCE.md`

### KBLI Navigator (Frontend)

| Route             | Description                             |
| ----------------- | --------------------------------------- |
| `/kbli`           | KBLI 2025 Navigator homepage (Next.js)  |
| `/kbli/[code]`    | KBLI code detail page (1,563 SSG pages) |
| `/kbli-navigator` | **Redirect** → `/kbli` (permanent 301)  |
| `/kbli-explorer`  | AI chat explorer (complementary)        |

## 13b. Communication Channels (7 channels)

| Channel     | Adapter                | Webhook                 | Status                   |
| ----------- | ---------------------- | ----------------------- | ------------------------ |
| WhatsApp    | `whatsapp/adapter.py`  | `/webhook/whatsapp`     | ✅ Live (Meta Cloud API) |
| Telegram    | `telegram/adapter.py`  | `/api/telegram/webhook` | ✅ Live (@Balizerobot)   |
| Instagram   | `instagram/adapter.py` | `/webhook/instagram`    | ✅ Live                  |
| X/Twitter   | `twitter/adapter.py`   | `/webhook/twitter`      | ❌ CRC broken            |
| Web Chat    | `web/adapter.py`       | `/api/webhook/chat`     | ✅ Live                  |
| Google Chat | `gchat/adapter.py`     | TBD                     | 🔧 Scaffold              |
| Slack       | `slack/adapter.py`     | TBD                     | 🔧 Scaffold              |

**Channel ownership:**

- **Web/WhatsApp/Instagram**: Backend Fly.io (Gemini 3 Flash + RAG)
- **Telegram**: Pro OpenClaw @Balizerobot (Opus 4.6 + SOUL.md persona) — Pro polls, Air/Fly send only
- **X/Twitter**: Backend Fly.io — currently broken (CRC authentication failure)

**WhatsApp /send** re-enabled (2026-03-16) with 3 safety gates: JWT auth, 20 msgs/phone/hour rate limit, CRM recipient validation.

## 13c. Subdomain Ecosystem

6 Vercel subdomains + SSO via `nz_access_token` httpOnly cookie on `.balizero.com`:

| Subdomain                | App            | Purpose                          |
| ------------------------ | -------------- | -------------------------------- |
| `kita.balizero.com`      | mouth          | Workspace (main)                 |
| `my.balizero.com`        | mouth (portal) | Client portal                    |
| `prime.balizero.com`     | mouth (prime)  | Spatial intelligence (3D maps)   |
| `mail.balizero.com`      | mail           | Email interface                  |
| `calendar.balizero.com`  | calendar       | Calendar                         |
| `drive.balizero.com`     | drive          | File management                  |
| `knowledge.balizero.com` | knowledge      | Knowledge base                   |
| `zantara.balizero.com`   | web            | AI chat (rewrites `/` → `/chat`) |

## 13d. Local AI (Ollama-First)

- **Core client:** `backend/llm/ollama_client.py` — **CRITICAL:** set `think: false` for Qwen 3.5
- **Models:** qwen3.5:27b (vision), qwen3.5:9b (fast), gemma3:12b, deepseek-r1:1.5b
- **Vision:** qwen2.5vl:7b ONLY (qwen3.5 Q4_K_M strips vision weights)
- **Vision API:** `"images": [base64_string]` in message object (NOT OpenAI-style)
- **Pattern:** Ollama local → fallback Gemini API. On Fly.io: Gemini always.

## 13e. CRM RBAC (Updated 2026-03-21)

| Role                                                                | Access                                                 |
| ------------------------------------------------------------------- | ------------------------------------------------------ |
| Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`, role=admin) | All clients and practices                              |
| Team Member (role != admin)                                         | Only practices where `clients.assigned_to` = own email |

**Implementation:** `crm_utils.can_view_all_practices()` + SQL `AND c.assigned_to = $email`. Server-side only, frontend unchanged.

---

## 14. Frontend Deploy — QA Automatico (OBBLIGATORIO)

**Ogni volta che fai deploy che impatta il frontend (Vercel), DEVI automaticamente:**

1. Aspetta che il deploy sia live (curl 200/307 sulle URL impattate)
2. Screenshot con `mcp__claude-in-chrome__*` tools (navigate + computer) di ogni app modificata
3. Verifica visivamente: colori corretti, logo presente, nessun elemento rotto
4. Se trovi problemi → fixa e rideploya senza aspettare conferma
5. Report finale con screenshot inline

**URL da monitorare:**

- `https://kita.balizero.com` — workspace principale
- `https://my.balizero.com` — portal clienti
- `https://prime.balizero.com` — spatial intelligence
- `https://calendar.balizero.com` — calendar
- `https://mail.balizero.com` — mail
- `https://drive.balizero.com` — drive
- `https://knowledge.balizero.com` — knowledge
- `https://zantara.balizero.com` — AI chat

**Non serve che l'utente lo chieda — è parte del processo di deploy.**

---

## 15. Pre-Deploy Checklist

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

**Test debt cleaned (2026-03-20):** Windsurf cleanup brought test suite to 0 failed, 0 errors (was 48 failed + 17 errors). Core tests (KG 82/82, Channels 43/43, RAG 244/244) remain 100%.

**Core Guardian V3:** Autonomous code quality agent runs every 3h, fixing deterministic lint issues (DTZ005/DTZ003/ANN204) in worktree isolation. Files: `apps/evaluator/core_guardian/`. Do NOT interfere with its fixes.

---

**Last Updated:** 2026-03-24
**Maintained by:** Bali Zero AI Team

---

## 16. AI Dispatch System (ENFORCE PROACTIVELY)

> `scripts/ai-dispatch.sh` v3 — 3-tier taxonomy. Run `./scripts/ai-dispatch.sh help` per comandi.

### 3-Tier Taxonomy (v3.1, 2026-03-25)

**AGENTS** — Autonomous runtimes, dispatchable via ai-dispatch.sh:

| Agente                          | Ruolo                                         | Dispatch command                           |
| ------------------------------- | --------------------------------------------- | ------------------------------------------ |
| **Tu (Claude Code, Opus 4.6)**  | Il Re — orchestra, sintetizza, decide, esegue | Diretto (IS the orchestrator)              |
| **Gemini 3.1 Pro CLI**          | Il Consigliere — 1M ctx, read-only            | `explore`, `search`, `redteam`, `gemini-*` |
| **Codex 5.4 CLI**               | Il Soldato — sandbox kernel-level             | `sandbox`, `codex-*`                       |
| **Claude CLI (Opus 4.6)**       | Il Giudice — review, redteam, read-only       | `claude-review`, `claude-redteam`          |
| **DeepSeek R1 671b (API)**      | Il Pensatore — chain-of-thought reasoning     | `reasoning`                                |
| **Aider (OpenRouter/DeepSeek)** | Il Mercenario — multi-model coding            | `aider-fix`, `aider-refactor`              |

**SERVICES** — Stateless tools, called by orchestrator directly (NOT dispatched by classifier):

| Servizio       | Ruolo                            | Comandi                              |
| -------------- | -------------------------------- | ------------------------------------ |
| **NotebookLM** | L'Oracolo — citations grounded   | `oracolo`, `oracolo-nb`, `research`  |
| **GWS CLI**    | Il Segretario — Google Workspace | Chiamato direttamente da Claude Code |
| **OCR**        | Scanner — text extraction        | MCP `mcp__ocr-tesseract__*`          |
| **Websearch**  | Deep web search + content        | `websearch`                          |
| **Canva**      | Design automation                | MCP `mcp__claude_ai_Canva__*`        |
| **GitKraken**  | Git workflow intelligence        | MCP `gk mcp` — see rules below       |

**PIPELINES** — Scheduled/triggered, NOT dispatchable:

| Pipeline              | Schedule/Trigger                 |
| --------------------- | -------------------------------- |
| **Core Guardian V3**  | every 3h (OpenClaw)              |
| **Intel Scraper**     | 03:00 WITA (Pro OpenClaw)        |
| **War Room**          | manual (Claude Code + Canva MCP) |
| **SEO Guardian**      | manual (`audit_geo_aeo()`)       |
| **NLM Daily Refresh** | 04:30 WITA (Pro OpenClaw)        |

### GitKraken MCP — Usage Rules (ENFORCE)

GitKraken MCP (`gk mcp`) is installed and provides 23 tools. Use them in these situations:

| Situazione                        | Tool GitKraken da usare            | Invece di                       |
| --------------------------------- | ---------------------------------- | ------------------------------- |
| Committing changes                | `gitlens_commit_composer`          | Manual `git add` + `git commit` |
| Check outstanding PRs             | `gitlens_launchpad`                | `gh pr list`                    |
| Starting work from a GitHub issue | `gitlens_start_work`               | Manual `git checkout -b`        |
| Reviewing a PR                    | `gitlens_start_review`             | Manual checkout + read          |
| Creating a PR                     | `pull_request_create`              | `gh pr create`                  |
| Getting PR details/comments       | `pull_request_get_detail/comments` | `gh pr view`                    |
| Checking assigned issues          | `issues_assigned_to_me`            | `gh issue list --assignee`      |
| Git blame on a file               | `git_blame`                        | `git blame` bash                |

**Rule:** Prefer GitKraken MCP over raw git/gh commands when the GitKraken tool provides richer context (e.g., `gitlens_launchpad` prioritizes PRs by urgency, `commit_composer` organizes changes intelligently).

### Pattern di Dispatch

1. **SERIALE**: Claude→Gemini analizza→Claude decide→Codex esegue→Claude valida
2. **PARALLELO**: `./scripts/ai-dispatch.sh parallel explore:"q1" search:"q2"` → Tu sintetizzi
3. **RED TEAM** (obbligatorio pre-deploy): `redteam "soluzione"` → Se problemi: rivedi. Se clean: deploy.
4. **MIGRATION**: `codex-migrate "desc"` → Genera e testa upgrade+downgrade in sandbox
5. **NORMATIVA**: `search "KBLI 2025"` → Gemini Google Search grounded con fonti
6. **REASONING**: `reasoning "complex architecture problem"` → DeepSeek R1 671b chain-of-thought

### Sicurezza

- Gemini: `--sandbox --approval-mode plan` → read-only. MAI scrive sul repo.
- Codex: `--sandbox read-only` o `workspace-write`. MAI `--dangerously-bypass`.
- File OFF LIMITS per tutti gli agenti: `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`
- Output: ogni comando salva in `./ai-dispatch-output/` con metriche (JSON strutturato)
- Cache: explore/search cachati 24h. Redteam/sandbox mai cachati.

### Fallback

- Timeout Gemini (>120s): riprova con prompt semplificato
- Timeout Codex (>180s): riprova, poi esegui tu con cautela
- Rate limit: segnala all'umano, retry dopo reset giornaliero

### Federation Protocol

- **Escalation**: Air scrive finding in `shared/escalations.json`, Pro legge a inizio sessione
- **Git sync**: post-commit hook → `ssh air 'cd ~/Projects/nuzantara && git pull --ff-only'`
- **CLAUDE.md**: IDENTICO su entrambe — git-tracked, push/pull obbligatorio
- **A2A Plan**: pilot con Damar — Gemini CLI agent per team member, Claude Code supervisor

---

## 17. Anthropic API — Best Practices (Feb 2026)

### Adaptive Thinking (OBBLIGATORIO su Opus 4.6 / Sonnet 4.6)

`budget_tokens` è **deprecato** sui modelli 4.6. Usare sempre:

```python
# ✅ CORRETTO — adaptive thinking
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    thinking={"type": "adaptive"},
    output_config={"effort": "medium"},  # "max" | "high" | "medium" | "low"
    messages=[...]
)

# ❌ DEPRECATO — non usare su 4.6
thinking={"type": "enabled", "budget_tokens": 10000}
```

- `effort="medium"` → raccomandato per workflow RAG/tool
- `effort="high"` → default, per query complesse
- `effort="max"` → solo per i problemi più difficili (solo Opus 4.6)
- L'interleaved thinking (tra tool call) è **automatico** su Opus 4.6 con adaptive

### Prompt Caching KBLI / Knowledge Base (-90% costo)

Ogni volta che scrivi chiamate API che includono il knowledge base KBLI, system prompt largo,
o definizioni di tool che non cambiano, usa `cache_control`:

```python
# ✅ System prompt con cache (risparmio 90% su letture successive)
system=[
    {
        "type": "text",
        "text": KBLI_SYSTEM_PROMPT_OR_KNOWLEDGE,
        "cache_control": {"type": "ephemeral", "ttl": 3600}  # 1 ora per batch
    }
]

# Monitoraggio cache
print(response.usage.cache_read_input_tokens)     # token da cache
print(response.usage.cache_creation_input_tokens)  # token scritti in cache
```

Prezzi Sonnet 4.6: scrittura 5min $3.75/MTok, scrittura 1h $6.00/MTok, **lettura $0.30/MTok**.
Minimo cacheable: 1.024 token.

### Batch API per elaborazioni massive (50% sconto)

Per test suite, analisi bulk KBLI, valutazioni:

```python
# Stacking: Batch 50% off + cache reads 90% off = costi minimi
batch = client.messages.batches.create(requests=[...])
```

### Tool Use — pattern corretti

```python
# Strict schema per produzione
tools = [{"name": "...", "strict": True, "input_schema": {...}}]

# Fine-grained streaming per tool con output grande
tools = [{"name": "kbli_search", "eager_input_streaming": True, ...}]

# Tool result caching per documenti grandi
{"type": "tool_result", "content": [{"type": "text", "text": doc, "cache_control": {"type": "ephemeral"}}]}
```

### Modelli consigliati per Nuzantara

| Uso                       | Modello                     | Perché                                       |
| ------------------------- | --------------------------- | -------------------------------------------- |
| RAG complesso, reasoning  | `claude-sonnet-4-6`         | Knowledge cutoff gen 2026, adaptive thinking |
| Routing / classificazione | `claude-haiku-4-5-20251001` | $1/$5 MTok, velocissimo                      |
| Task critici              | `claude-opus-4-6`           | 128K output, effort=max                      |
| Spiegazioni KBLI          | `claude-haiku-4-5-20251001` | Già configurato in kbli_notebook.py          |

---

## 18. CRITICAL OPERATIONAL RULES — Non Documentate Altrove

> Queste regole non sono deducibili dal codice. Sono qui per tutti gli agenti AI (Claude, Gemini, Codex, Windsurf).

### Virtualenv (CRITICAL)

- **Air:** `venv` (NON `.venv`) — path: `apps/backend-rag/venv/bin/python`
- **Pro:** potrebbe essere `.venv` — verificare con `ls apps/backend-rag/ | grep venv`
- **pip rotto su Air:** usare `/Users/antonellosiano/.pyenv/shims/python3 -m pip` invece di `pip`
- **Nei cron su Air:** usare path assoluto `venv/bin/python` NON `source venv/bin/activate`

### Drive Polling (CRITICAL)

- Drive polling gira **SOLO su Air** via cron ogni 5min (`scripts/drive_poll_cron.sh`)
- **NON mettere su Fly.io scheduler** — incompatibile con `auto_stop=true` (perde `page_token` a ogni cold start)
- `page_token` è salvato in `system_settings` table — perderlo causa re-scan completo Drive
- Circuit breaker attivo: 3 failures → circuit OPEN + Telegram alert → auto-recovery 5min

### Drive OAuth (CRITICAL)

- Token OAuth in `google_drive_tokens` table — scade ogni ~90 giorni
- **Watchdog attivo:** `scripts/drive_token_watchdog.py` — alert 7gg prima via Telegram
- Re-auth: `https://kita.balizero.com/settings/integrations`
- Se scade silenziosamente → nessun documento viene processato → clienti non vedono file

### OCR Multi-page (IMPORTANT)

- Leggere **SEMPRE tutte le pagine** del PDF, non solo pagina 0
- I direttori delle PT/CV (perseroan) sono tipicamente in pagina 2-3 dell'akta
- Timeout: 120s per PDF > 3 pagine
- Vision model: `qwen2.5vl:7b` ONLY (qwen3.5 Q4_K_M strips vision weights)

### Cache Invalidation (IMPORTANT)

- Pattern **obbligatorio** dopo ogni mutation:
  ```python
  await invalidate_cache("zantara:namespace:*")
  ```
- Namespace attivi: `zantara:crm_clients_stats:*`, `zantara:crm_practices:*`
- Mutation senza invalidation → dati stale → confusione clienti
- Core Guardian AST audit: `apps/evaluator/core_guardian/checks/cache_invalidation_audit.py`

### KG Subgraph Status (2026-03-26)

| Subgraph | Stato             | Note                                                    |
| -------- | ----------------- | ------------------------------------------------------- |
| Company  | ✅ wired KG reale | Query asyncpg su kg_nodes/kg_edges                      |
| Visa     | ⚠️ parziale       | Sezione RPTKA ancora hardcoded in `kg_subgraph_visa.py` |
| Property | ❓ da verificare  |                                                         |
| Tax      | ❓ da verificare  |                                                         |

### Cron Air (aggiornato 2026-03-26)

| Job                | Schedule      | Script                                   |
| ------------------ | ------------- | ---------------------------------------- |
| Ollama start       | 01:00         | `ollama_cron_window.sh start`            |
| Auto test          | 02:15         | `auto_test.sh`                           |
| Sentinel           | 03:00         | `auto_sentinel.sh`                       |
| KB Ingest          | 05:00         | `auto_kb_ingest.sh`                      |
| Ollama stop        | 06:05         | `ollama_cron_window.sh stop`             |
| **RAG Canary**     | **\*/6h :30** | **`rag_canary.py`**                      |
| **System Doctor**  | **08:00**     | **`system_doctor.py --notify-telegram`** |
| **Drive Watchdog** | **\*/6h :00** | **`drive_token_watchdog.py`**            |
| Judgement Day      | Sun 16:00     | `auto_judgement_day.sh`                  |
| **RAGAS Eval**     | **Sun 06:00** | **`ragas_eval.py`**                      |

### GitHub Secrets richiesti per CI/CD

- `FLY_API_TOKEN` — per `fly-deploy.yml`
- `TELEGRAM_BOT_TOKEN` — per alert deploy
- `TELEGRAM_OWNER_CHAT_ID` — chat ID owner (413539912)

**Last Updated:** 2026-03-27

---

## 19. Claude Code Escalation Tasks (leggere a inizio sessione)

Quando il DLQ Autopilot non riesce a fixare un job (Aider fallisce o confidenza bassa),
crea un file in `~/.agent/decisions/claude_tasks/`. **Leggi sempre questa directory
a inizio sessione**, esattamente come `shared/escalations.json`.

```bash
ls ~/.agent/decisions/claude_tasks/ 2>/dev/null | head -10
```

Ogni file contiene `job`, `error_summary`, `log_tail`, `files_implicated`,
`dlq_reasoning` (output Claude CLI reasoning), `fix_instruction`, `test_cmd`.

**Regola:** lavora sui claude_tasks in ordine di `priority` (HIGH prima), poi `created_at`.
Dopo aver fixato: cancella il file con `rm ~/.agent/decisions/claude_tasks/<filename>.json`
e verifica con `test_cmd`.

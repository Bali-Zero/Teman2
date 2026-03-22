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
**URL:** https://kita.balizero.com

### Architecture

**Monorepo structure:**

- `apps/mouth/` - Next.js frontend (Vercel)
- `apps/backend-rag/` - Python FastAPI RAG backend (Fly.io)
- `apps/admin-dashboard/` - Admin UI
- `apps/webapp/` - Web application
- `apps/bali-intel-scraper/` - Intelligence gathering
- `apps/nuzantara-mcp/` - MCP server v2.1 (96 tools, 10 prompts, 5 resources, 8 chains)
- `apps/nuzantara-mcp-advanced/` - Advanced MCP (Fly.io ops, diagnostics)
- `apps/nuzantara-mcp-browser/` - Browser automation MCP
- `apps/graph-engine/` - Graph processing engine
- `apps/kbli-voice/` - KBLI voice interface
- `apps/evaluator/` - Quality assurance
- `apps/zantara-media/` - Editorial content system
- `packages/kb/` - Knowledge base
- `packages/core/` - Core libraries

### Tech Stack

- **Backend:** Python 3.11+, FastAPI, 86 routers, 236 services, 414 test files
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** 56,113 nodes, 161,173 edges
- **Vector Collections:** 9 live on Fly.io (66,595 documents), 11 defined in code
- **Embedding Model:** `text-embedding-3-small` (1536 dims) — **NEVER CHANGE**

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

### Delegation Checkpoint — 5 Domande Pre-Task (ENFORCE)

**Prima di QUALSIASI task, rispondi a queste 5 domande:**

1. **Questo task richiede di leggere/esplorare più di 5 file?**
   → Sì: `./scripts/ai-dispatch.sh explore "question"`. Gemini 1M ctx, gratis.

2. **Questo task richiede informazioni esterne in tempo reale?**
   → Sì: `./scripts/ai-dispatch.sh search "query"`. Google Search grounded con citazioni.

3. **Questo task comporta rischio per il repo se il codice è sbagliato?**
   → Sì: `./scripts/ai-dispatch.sh sandbox "task"`. Codex in sandbox kernel-level.

4. **Questo task beneficerebbe di due prospettive indipendenti?**
   → Sì: `./scripts/ai-dispatch.sh parallel explore:"q1" search:"q2"`. Tu sintetizzi.

5. **Questo task è un deploy o una modifica critica?**
   → Sì: `./scripts/ai-dispatch.sh redteam "soluzione proposta"`. Mai deploy senza red team.

**Se TUTTE le risposte sono "No"**: fai tu direttamente. Non delegare per sport.

## 4. Golden Rules (ENFORCE STRICTLY)

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

## 5. Development Commands

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
│   ├── prompts/       # ⭐ Prompt Single Source of Truth (see below)
│   ├── routers/       # API endpoints (86 routers)
│   ├── services/      # Business logic (236 services)
│   ├── models/        # Pydantic models
│   ├── db/            # Database access layer
│   ├── utils/         # Utility functions
│   └── main.py        # FastAPI app entry (alias for main_cloud.py)
├── tests/             # 414 test files
├── alembic/           # Database migrations
├── requirements.txt   # Python dependencies
└── fly.toml          # Fly.io configuration
```

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
**CRITICAL:** This model is FROZEN. Changing it would invalidate 66,595 existing vectors.  
**Never:** Switch to another model without explicit authorization and full re-indexing plan.

## 6. MCP Servers

**Primary:** `apps/nuzantara-mcp/` (v2.1, FastMCP, stdio transport)
**Capabilities:**

- **96 Tools** across 17 modules (CRM, portal, intel, content, analytics, knowledge, comms, drive, workflows, admin, health, journey, pricing, compliance, generals, memory, heartbeat)
- **10 Prompts** for guided workflows
- **5 Resources** for knowledge base access
- **8 Workflow Chains** for deterministic automation (daily_ops_autopilot, new_client_onboarding, practice_lifecycle_check, intel_pipeline, weekly_report, client_health_monitor, compliance_autopilot, journey_accelerator)

**Additional MCP servers:**

- `apps/nuzantara-mcp-advanced/` — Fly.io ops, deployment readiness, code search, diagnostics
- `apps/nuzantara-mcp-browser/` — Browser automation

## 7. Deployment Architecture

### Production Stack

- **Frontend:** Vercel (CDN, Edge Functions)
- **Backend:** Fly.io `nuzantara-rag` (Singapore, shared-cpu-2x, **2GB RAM**, auto_stop=true, min=0)
- **Databases:**
  - PostgreSQL: Fly.io `nuzantara-postgres` (**2GB RAM**, v0.1.0, upgraded 2026-03-14)
  - Qdrant: Fly.io `nuzantara-qdrant` (2GB, v1.12.1 — upgrade TODO)
  - Redis: Upstash or Fly.io

### Fly.io — SOLO 3 APP (updated 2026-03-14)

| App                  | CPU       | RAM | Auto-stop     | Note                    |
| -------------------- | --------- | --- | ------------- | ----------------------- |
| `nuzantara-rag`      | shared-2x | 2GB | ✅ yes, min=0 | Cold start ~35s         |
| `nuzantara-postgres` | shared-1x | 2GB | no            | v0.1.0, backup → Tigris |
| `nuzantara-qdrant`   | shared-1x | 2GB | no            | v1.12.1                 |

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
    console.error("KBLI fetch failed:", error);
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

## 11. Language Protocol (Natural Language → Precise Engineering)

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

### KBLI Navigator (Frontend)

| Route             | Description                             |
| ----------------- | --------------------------------------- |
| `/kbli`           | KBLI 2025 Navigator homepage (Next.js)  |
| `/kbli/[code]`    | KBLI code detail page (1,563 SSG pages) |
| `/kbli-navigator` | **Redirect** → `/kbli` (permanent 301)  |
| `/kbli-explorer`  | AI chat explorer (complementary)        |

---

## 13. Frontend Deploy — QA Automatico (OBBLIGATORIO)

**Ogni volta che fai deploy che impatta il frontend (Vercel), DEVI automaticamente:**

1. Aspetta che il deploy sia live (curl 200/307 sulle URL impattate)
2. Screenshot con Playwright (`mcp__playwright__browser_navigate` + `browser_take_screenshot`) di ogni app modificata
3. Verifica visivamente: colori corretti, logo presente, nessun elemento rotto
4. Se trovi problemi → fixa e rideploya senza aspettare conferma
5. Report finale con screenshot inline

**URL da monitorare:**

- `https://kita.balizero.com` — workspace principale
- `https://calendar.balizero.com` — calendar
- `https://mail.balizero.com` — mail
- `https://drive.balizero.com` — drive
- `https://knowledge.balizero.com` — knowledge
- `https://my.balizero.com` — portal clienti

**Non serve che l'utente lo chieda — è parte del processo di deploy.**

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

**Last Updated:** 2026-03-01
**Maintained by:** Bali Zero AI Team

---

## 15. AI Dispatch System (ENFORCE PROACTIVELY)

> `scripts/ai-dispatch.sh` v2 — Universale Pro+Air. Run `./scripts/ai-dispatch.sh help` per comandi.

### Ruoli

| Agente                         | Ruolo                                         | Forza                                                 |
| ------------------------------ | --------------------------------------------- | ----------------------------------------------------- |
| **Tu (Claude Code, Opus 4.6)** | Il Re — orchestra, sintetizza, decide, esegue | Refactor multi-file, deploy, decisioni architetturali |
| **Gemini 3.1 Pro CLI**         | Il Consigliere — 1M ctx, read-only            | `codebase_investigator`, `google_web_search` grounded |
| **Codex 5.4 CLI**              | Il Soldato in Fortezza — sandbox kernel-level | Fix isolati, migration, test in ambiente sicuro       |

### Pattern di Dispatch

1. **SERIALE**: Claude→Gemini analizza→Claude decide→Codex esegue→Claude valida
2. **PARALLELO**: `./scripts/ai-dispatch.sh parallel explore:"q1" search:"q2"` → Tu sintetizzi
3. **RED TEAM** (obbligatorio pre-deploy): `redteam "soluzione"` → Se problemi: rivedi. Se clean: deploy.
4. **MIGRATION**: `codex-migrate "desc"` → Genera e testa upgrade+downgrade in sandbox
5. **NORMATIVA**: `search "KBLI 2025"` → Gemini Google Search grounded con fonti

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

---

## 16. Anthropic API — Best Practices (Feb 2026)

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

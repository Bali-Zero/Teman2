# AI ONBOARDING GUIDE - Nuzantara Project

**Last Updated:** 2026-03-22
**Purpose:** Quick-start guide for AI assistants working on Project Nuzantara

**System Stats:**

- Router Files: 88
- Services: 244 Python files
- Test Files: 385
- Qdrant Collections: 9 live on Fly.io (11 defined in code), 66,595 total documents
- Knowledge Graph: 56,113 nodes, 161,173 edges (PostgreSQL)
- Fly.io: 3 apps (Singapore) — nuzantara-rag, nuzantara-postgres, nuzantara-qdrant
- DB Migrations: 060
- MCP Server: 109 tools, 10 prompts, 5 resources, 8 workflow chains
- Communication Channels: 7 (WhatsApp, Telegram, Instagram, X/Twitter, Web, Google Chat, Slack)
- Autonomous Scheduler: 11 tasks via OpenClaw cron (mcporter calls, NOT lobster)
- Core Test Pass Rate: 100% (KG 82/82, Channels 43/43, RAG 244/244)
- Core Guardian V3: Autonomous code quality agent (3 fixers, every 3h, $0 cost)

> **READ THIS FIRST** before making any changes to the codebase.

---

## QUICK START CHECKLIST

**FIRST: Identify your machine and check connectivity.** Run this before anything else:

```bash
echo "Machine: $(whoami)@$(hostname)" && \
OTHER=$(if [ "$(whoami)" = "nuzantara" ]; then echo "air"; else echo "pro"; fi) && \
ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE" && \
LOCAL_HEAD=$(git log --oneline -1 2>/dev/null) && \
REMOTE_HEAD=$(ssh -o ConnectTimeout=3 $OTHER 'cd ~/Desktop/projects/nuzantara 2>/dev/null || cd ~/Desktop/nuzantara 2>/dev/null; git log --oneline -1' 2>/dev/null) && \
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then echo "Git sync: OK ($LOCAL_HEAD)"; else echo "Git sync: OUT OF SYNC! Local=$LOCAL_HEAD Remote=$REMOTE_HEAD"; fi
```

Expected output:

- **Machine:** `nuzantara@Nuzantara` (Pro) or `antonellosiano@Nuzantara-9` (Air)
- **Peer:** The other machine — must show connected, not UNREACHABLE
- **Git sync:** Must show OK. If OUT OF SYNC, run `git pull` on the behind machine before working.

**Always prefix your first response with [Pro] or [Air].** Warn the user if peer is unreachable or repos are out of sync.

See [`docs/PRO_AIR_CONNECTION.md`](PRO_AIR_CONNECTION.md) for SSH setup and troubleshooting.

Then verify you understand:

- [ ] **Virtualenv:** `.venv` created and activated (`source .venv/bin/activate`)
- [ ] **Project Structure:** Monorepo with 20 apps, core: `apps/backend-rag` (FastAPI) and `apps/mouth` (Next.js)
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

### 10. NEVER PRESUME - ALWAYS VERIFY SOURCES

**CRITICAL:** When analyzing data, answering questions, or making claims about the system:

**WRONG:**

```python
# Assuming without verification
"The database contains outdated PT PMA data"
"This price is incorrect"
"The model is not working properly"
```

**CORRECT:**

```python
# Verify first, then conclude
# 1. Query the actual data source (Qdrant, Postgres, logs)
# 2. Read the exact document/chunk being referenced
# 3. Check the context and metadata
# 4. ONLY THEN make a conclusion with evidence

# Example: "After checking Qdrant collection 'bali_zero_pricing_hybrid',
# document ID xyz contains: [actual content]. This shows..."
```

**Never say "the database is wrong" without:**

- [ ] Querying the actual collection
- [ ] Reading the exact chunk/document
- [ ] Checking metadata (source, date, version)
- [ ] Understanding the full context

**Evidence-based analysis only.** Speculation and assumptions lead to wrong fixes.

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

Public endpoints use `path.startswith(endpoint)` matching. **40 public endpoint patterns** including:

- `/api/v1/kbli-notebook/` (KBLI search, inspect, chat)
- `/health`, `/api/health` (health checks)
- `/webhook/whatsapp`, `/webhook/instagram`, `/webhook/twitter` (channel webhooks)
- `/api/agentic-rag/stream` (chat streaming)
- `/api/blog/` (blog/marketing)
- `/api/portal/invite/` (portal invitations)
- `/api/auth/team/login`, `/api/auth/login` (authentication)
- Various OAuth callbacks (Zoho, Google Drive)
- Various test endpoints (`/test/*`)

Protected infra (require admin API key): `/docs`, `/openapi.json`, `/redoc`, `/metrics`

Agentic RAG (`/api/agentic-rag/query`) requires JWT authentication.

---

## PROJECT STRUCTURE

```
nuzantara/
├── apps/
│   ├── backend-rag/             # CORE: FastAPI Backend (Fly.io)
│   │   ├── backend/
│   │   │   ├── app/             # FastAPI entrypoint (main_cloud.py)
│   │   │   │   ├── routers/     # 88 route files
│   │   │   │   └── modules/     # identity, knowledge, notifications
│   │   │   ├── channels/        # 7 channels: whatsapp, telegram, instagram, twitter, web, gchat, slack
│   │   │   ├── core/            # Config, Security, Logging
│   │   │   ├── generals/        # Multi-agent task coordinator
│   │   │   ├── prompts/         # Prompt Single Source of Truth (zantara_core.py)
│   │   │   ├── services/        # Business Logic (244 files)
│   │   │   │   ├── rag/agentic/ # CORE: Orchestrator, ReAct, LLM Gateway
│   │   │   │   ├── knowledge_graph/  # KG extraction + query
│   │   │   │   ├── social/      # X/Twitter monitoring
│   │   │   │   ├── compliance/  # 5 compliance services
│   │   │   │   ├── journey/     # 5 journey services
│   │   │   │   └── memory/      # Memory Orchestrator
│   │   │   └── migrations/      # Migration files (up to 060)
│   │   ├── tests/               # 385 test files
│   │   └── scripts/             # Maintenance + ingestion scripts
│   │
│   ├── mouth/                   # Frontend: Next.js + React (Vercel) — kita.balizero.com
│   │   └── src/
│   │       ├── app/             # Page routes (blog, workspace, portal, kbli)
│   │       ├── components/      # UI components
│   │       └── lib/             # API clients, store
│   │
│   ├── nuzantara-mcp/           # MCP Server v2.1 (FastMCP, stdio)
│   │   └── nuzantara_mcp/       # 109 tools, 10 prompts, 5 resources, 8 chains
│   │
│   ├── nuzantara-mcp-advanced/  # Advanced MCP (Fly.io ops, diagnostics, 14 tools)
│   ├── nuzantara-mcp-browser/   # Browser automation MCP
│   ├── bali-intel-scraper/      # News pipeline (runs LOCALLY on Pro via OpenClaw, NOT Fly)
│   ├── evaluator/               # Quality assurance + Core Guardian V3
│   ├── graph-engine/            # Graph processing engine
│   ├── kbli-voice/              # KBLI voice interface
│   ├── war-room/                # Operations dashboard + Canva automation
│   ├── zantara-media/           # Editorial content system
│   ├── admin-dashboard/         # Admin UI
│   ├── webapp/                  # Web application
│   ├── calendar/                # Subdomain satellite (calendar.balizero.com)
│   ├── drive/                   # Subdomain satellite (drive.balizero.com)
│   ├── knowledge/               # Subdomain satellite (knowledge.balizero.com)
│   ├── mail/                    # Subdomain satellite (mail.balizero.com)
│   ├── kbli-navigator/          # KBLI 2025 Navigator interface
│   └── web/                     # Subdomain satellite (zantara.balizero.com)
│
├── packages/
│   ├── core/                    # Core libraries + BZ design tokens + BZLogo
│   └── kb/                      # Knowledge base
│
├── docs/                        # Documentation
├── scripts/                     # Root-level utilities + ai-dispatch.sh
└── data/source_documents/       # KBLI JSON, legal PDFs
```

---

## QDRANT COLLECTIONS

**9 collections live on Fly.io** (66,595 total documents), 11 defined in `CollectionManager` (`backend/services/ingestion/collection_manager.py`):

| Collection                      | Priority | Docs    | Purpose                            |
| ------------------------------- | -------- | ------- | ---------------------------------- |
| `collective_memories`           | high     | dynamic | Conversation memories              |
| `bali_zero_pricing_hybrid`      | high     | 29      | Service pricing                    |
| `bali_zero_team`                | high     | 22      | Team member profiles               |
| `visa_oracle`                   | high     | 1,612   | Visa requirements                  |
| `kbli_2025_final`               | high     | 8,886   | KBLI business codes (FLAT payload) |
| `tax_genius`                    | high     | 895     | Tax knowledge                      |
| `legal_unified`                 | high     | 5,041   | Legal documents                    |
| `legal_unified_hybrid`          | high     | 47,959  | Legal hybrid search                |
| `tax_genius_hybrid`             | high     | 332     | Tax hybrid search                  |
| `training_conversations_hybrid` | high     | 2,898   | Training data                      |
| `immigration_circulars`         | high     | 4       | Immigration circulars              |

**Aliases** (map to existing collections): `legal_architect`, `kb_indonesian`, `kbli_comprehensive`, `zantara_books`, `cultural_insights`, `tax_updates`, `tax_knowledge`, `property_listings`, `property_knowledge`, `legal_updates`, `legal_intelligence`.

---

## DEPLOYMENT

### Backend (Fly.io)

```bash
cd apps/backend-rag
fly deploy --strategy rolling
```

- **SOLO 3 Fly.io apps** (updated 2026-03-14):

| App                  | CPU       | RAM | Auto-stop     | Note                    |
| -------------------- | --------- | --- | ------------- | ----------------------- |
| `nuzantara-rag`      | shared-2x | 2GB | ✅ yes, min=0 | Cold start ~35s         |
| `nuzantara-postgres` | shared-1x | 2GB | no            | v0.1.0 (upgraded from v0.0.66 after OOM) |
| `nuzantara-qdrant`   | shared-1x | 2GB | no            | v1.12.1                 |

- **Destroyed (2026-03-14):** `nuzantara-rag-staging`, `bali-intel-scraper`, `zantara-media`, `fly-builder-red-flower-7537`
- **Cost:** ~$35-40/mo (was ~$81/mo, -50%)
- Health: `GET /health` shows runtime state
- Secrets: `fly secrets list -a nuzantara-rag`
- Logs: `fly logs -a nuzantara-rag`
- **1 worker only** in Dockerfile (2 workers = OOM on 2GB VM)
- **Lazy loading:** Heavy imports deferred to background init; health returns `"initializing"` while loading
- **Backup:** pg_dump daily → Tigris `nuzantara-backups` via `~/scripts/fly-pg-backup.sh` (cron 03:00)
- **Health monitor:** `~/scripts/fly-health-check.sh` every 5min, alerts via Telegram

**CRITICAL:** `bali-intel-scraper` runs ONLY locally on Pro via OpenClaw cron (03:00 WITA), NOT on Fly.io.

### Frontend (Vercel)

Auto-deploys from `apps/mouth/` on push to main. No manual deploy needed.

**Vercel build notes:**

- `outputFileTracingExcludes` in `next.config.ts` prevents 580 MB of public assets bundling into serverless functions
- KBLI data must live inside `apps/mouth/data/` (not root `source_documents/`) for Vercel build access

### Git Commits

Pre-commit hooks run prettier on all files. Prettier fails on non-JS files (Python, .txt, .md with non-standard formatting). Use `--no-verify` when committing non-JS changes:

```bash
git commit --no-verify -m "your message"
```

This is a known issue, not a hack. The hook validates JS/TS formatting which is correct behavior - it just doesn't know to skip non-JS files.

---

## MCP SERVER (Nuzantara RAG)

**Package:** `apps/nuzantara-mcp/` (FastMCP 2.x, stdio transport, v2.1)

Full-spectrum AI business intelligence and automation platform. **109 tools** across 17 modules:

| Module       | Capabilities                                      |
| ------------ | ------------------------------------------------- |
| `crm`        | Client management, practices, timelines           |
| `portal`     | Client portal dashboard, messages, documents      |
| `intel`      | Scraping, staging, publishing, search, trends     |
| `content`    | Article composition, publishing, newsletters      |
| `analytics`  | Completion rates, SLA, revenue, team productivity |
| `knowledge`  | KBLI search/inspect/chat, legal Q&A, visa types   |
| `comms`      | Email, WhatsApp, Telegram                         |
| `drive`      | Google Drive files, folders, storage              |
| `workflows`  | Execution plans, autonomous step approval         |
| `admin`      | Clock in/out, team hours, admin logs, health      |
| `health`     | System health, Qdrant metrics                     |
| `journey`    | Client journey tracking, pricing                  |
| `pricing`    | Service pricing, invoicing                        |
| `compliance` | Regulatory compliance tracking                    |
| `generals`   | Multi-agent LAM memory, grounding                 |
| `memory`     | Episodic memory (save, recall, list, delete)      |
| `heartbeat`  | 8 deterministic workflow chains                   |

**8 Workflow Chains:** `daily_ops_autopilot`, `new_client_onboarding`, `practice_lifecycle_check`, `intel_pipeline`, `weekly_report`, `client_health_monitor`, `compliance_autopilot`, `journey_accelerator`

**🆕 Chain Onboarding Enhancements (2026-03-02):**

The `chain_new_client_onboarding` workflow now includes:

1. **Intelligent Visa Determination (Step 3)**: Replaced hardcoded keyword matching with PricingTool consultation. Queries `/api/agents/pricing/calculate` with business context, falls back to keyword matching if service unavailable. Logs include `pricing_consulted` flag for tracking.

2. **Auto-Trigger from WhatsApp**: New `whatsapp_onboarding_detector.py` service detects "new client" intent in messages (multilingual: EN/IT/ID keywords like "new client", "nuovo cliente", "klien baru", "moving to bali"). Auto-triggers chain + sends confirmation + notifies admin via Telegram.

3. **Auto-Trigger from Web Form**: `POST /api/crm/clients` with `status=lead|prospect` and non-empty `service_interest` automatically prepares onboarding payload. Logs intent without blocking client creation.

See `docs/architecture/CHAIN_ONBOARDING_IMPROVEMENTS.md` for full implementation details.

**Additional MCP servers:**

- `apps/nuzantara-mcp-advanced/` — Fly.io ops, deployment readiness, code search, diagnostics (14 tools)
- `apps/nuzantara-mcp-browser/` — Browser automation
- `ga4-analytics` — GA4 property 505466833 (BALI ZERO WEB stream, G-S3H2M6VXWT)
- `google-search-console` — 19 SEO tools, SA auth, site owner on balizero.com
- `ocr-tesseract` — Document OCR with Indonesian language support

**MCP Bridge (OpenClaw):** 129 tools connected via mcporter wrappers in `~/.local/bin/`. macOS provenance fix applied for LaunchAgent compatibility.

**Run locally:**

```bash
pip install -e apps/nuzantara-mcp/
nuzantara-mcp  # starts stdio server
```

**FastMCP 2.x gotcha:** Use `instructions=` not `description=` in the constructor.

---

## COMMUNICATION CHANNELS

**7 omnichannel integrations** in `backend/channels/`:

| Channel      | Adapter                | Webhook                 | Status         |
| ------------ | ---------------------- | ----------------------- | -------------- |
| WhatsApp     | `whatsapp/adapter.py`  | `/webhook/whatsapp`     | ✅ Live (Meta Cloud API) |
| Telegram     | `telegram/adapter.py`  | `/api/telegram/webhook` | ✅ Live (@Balizerobot) |
| Instagram    | `instagram/adapter.py` | `/webhook/instagram`    | ✅ Live        |
| X/Twitter    | `twitter/adapter.py`   | `/webhook/twitter`      | ❌ CRC broken  |
| Web Chat     | `web/adapter.py`       | `/api/webhook/chat`     | ✅ Live        |
| Google Chat  | `gchat/adapter.py`     | TBD                     | 🔧 Scaffold   |
| Slack        | `slack/adapter.py`     | TBD                     | 🔧 Scaffold   |

Each channel has `adapter.py`, `config.py`, `formatter.py` following a consistent pattern.

**Channel ownership:**
- **Web/WhatsApp/Instagram**: Backend Fly.io (Gemini 3 Flash + RAG)
- **Telegram**: Pro OpenClaw @Balizerobot (Opus 4.6 + SOUL.md persona) — Pro polls, Air/Fly send only
- **X/Twitter**: Backend Fly.io — currently broken (CRC authentication failure)

**WhatsApp /send** re-enabled (2026-03-16) with 3 safety gates: JWT auth, 20 msgs/phone/hour rate limit, CRM recipient validation.

X/Twitter social monitoring via `services/social/x_monitor_service.py` + `routers/x_monitor.py`.

---

## CHAT STREAMING (Unified Endpoint)

**Endpoint:** `POST /api/agentic-rag/stream` (SSE)

Single source of truth for all chat streaming. Features:

- Timeout: 120s request, 300s idle, 600s max total
- Abort handling via AbortController
- 13+ event types (token, sources, metadata, thinking, tool_call, reasoning_step, etc.)
- Vision support (base64 images)
- Automatic conversation persistence
- Correlation ID for end-to-end tracing

**Frontend:** `useChatStreaming.ts` -> `api.sendMessageStreaming()`

---

## LANGGRAPH KNOWLEDGE GRAPH (PHASES 1-4 COMPLETE)

**Status:** **PRODUCTION READY** (2026-02-09)

**Implementation:** Agentic Knowledge Graph system built on LangGraph for intelligent query routing and workflow synthesis.

### Architecture Overview

**5 Core Nodes:**

1. `understand_query_node` - Extract intent, entities, citizenship (LLM)
2. `resolve_entities_node` - Map entities to KG via fuzzy match (PostgreSQL similarity)
3. `traverse_graph_node` - BFS graph traversal (REQUIRES, ENABLES, PART_OF)
4. `reason_over_graph_node` - LLM analyzes chains for answer
5. `synthesize_workflow_node` - Convert chains to executable workflow

**4 Domain-Specific Subgraphs:**

- **Company Subgraph:** PT PMA, Perorangan, CV setup workflows
- **Visa Subgraph:** KITAS, KITAP, VITAS requirements
- **Property Subgraph:** Hak Pakai, HGB, rental regulations
- **Tax Subgraph:** PPh, PPN, NPWP compliance

### Key Files

| File                                                | Purpose                     | Lines |
| --------------------------------------------------- | --------------------------- | ----- |
| `backend/services/rag/kg_graph_state.py`            | TypedDict state definitions | 100   |
| `backend/services/rag/kg_graph_nodes.py`            | 5 core nodes + helpers      | 550   |
| `backend/services/rag/kg_langgraph_orchestrator.py` | StateGraph + routing        | 500+  |
| `backend/services/rag/kg_subgraph_company.py`       | Company setup workflows     | 420   |
| `backend/services/rag/kg_subgraph_visa.py`          | Visa workflows              | 448   |
| `backend/services/rag/kg_subgraph_property.py`      | Property workflows          | 163   |
| `backend/services/rag/kg_subgraph_tax.py`           | Tax compliance workflows    | 475   |
| `backend/services/rag/confidence.py`                | 6-factor confidence scoring | 250   |

### Production Integration

**Feature Flag:** `ENABLE_KG_LANGGRAPH` env var (default: disabled for backward compatibility)

**Orchestrator Integration:**

- 3-way parallel execution: Entity Extraction + KG Legacy + KG LangGraph
- Workflow output formatted and added to system prompt as "SUGGESTED WORKFLOW"
- File: `backend/services/rag/agentic/orchestrator_core.py` (lines 154-254)

**Routing Priority:**

1. Domain subgraphs (keyword match)
2. Golden routes (high-confidence paths)
3. Graph traversal (BFS)
4. END (no results)

### Performance

| Metric             | Value  |
| ------------------ | ------ |
| Subgraph execution | <350ms |
| 3-hop traversal    | <500ms |
| LLM reasoning      | <2s    |
| Full pipeline      | <3s    |

### Test Coverage

**Tests:** 82/82 passing (100%)

- Phase 1: 35 tests (kg_graph_nodes, orchestrator)
- Phase 3: 23 tests (subgraphs)
- Phase 2: 24 tests (confidence scoring)

**Files:**

- `backend/tests/services/rag/test_kg_langgraph.py`
- `backend/tests/services/rag/test_kg_subgraphs.py`
- `backend/tests/services/rag/test_confidence.py`

### Confidence Scoring (Phase 2)

**6-Factor Dynamic Scoring:**

- Chain base confidence (30%)
- Entity confidence (20%)
- Relationship strength (20%)
- Multi-source boost (15%)
- Recency (10%)
- Intent clarity (5%)

**Warning Levels:**

- High: >=0.80
- Medium: >=0.55
- Low: >=0.35
- Very Low: <0.35

---

## PROMPT ARCHITECTURE (Single Source of Truth)

```
backend/prompts/
├── __init__.py              # Re-exports ZANTARA_MASTER_TEMPLATE, CREATOR_PERSONA, TEAM_PERSONA
├── zantara_core.py          # THE file — all prompt sections as composable constants
├── channel_overlays.py      # Per-channel config (word limits, markdown, emoji)
├── few_shot_examples.py     # Consolidated few-shot examples
├── zantara_persona.py       # Backward compat wrapper -> imports from zantara_core
├── whatsapp_persona.py      # Dynamic builder for WhatsApp context -> imports from zantara_core
└── zantara_prompt_builder.py # Legacy builder -> imports from zantara_core
```

**Rule:** To add/edit ANY Zantara prompt rule, edit ONLY `zantara_core.py`. All consumers import from it.

**Sections in `zantara_core.py`:**
`SECURITY_BOUNDARY` - `TOOL_USAGE_POLICY` - `SYSTEM_INSTRUCTIONS` - `KNOWLEDGE_GOVERNANCE` -
`LANGUAGE_PROTOCOL` - `GREETING_RULES` - `CITATION_RULES` - `INTERNAL_MONOLOGUE` -
`ESCALATION_PROTOCOL` - `CRASH_PROTOCOL` - `CLOSING_PHRASES` - `CREATOR_PERSONA` -
`TEAM_PERSONA` - `ZANTARA_MASTER_TEMPLATE`

---

## CRITICAL FIXES & KNOWN ISSUES

### Evidence Score System

**File:** `backend/services/rag/agentic/reasoning.py`

The system uses `evidence_score` (0.0-1.0) to decide responses:

- **< 0.15** -> ABSTAIN (refuses to answer)
- **0.15-0.6** -> Cautious response
- **> 0.6** -> Normal response

**Tools-available bypass:** If LLM had tools and produced an answer, trust it (fixes English query ABSTAIN bug, deployed v2131).

### Trusted Tools (Bypass Evidence Check)

These tools bypass evidence scoring because they provide their own evidence:

| Tool             | Location           | Purpose                   |
| ---------------- | ------------------ | ------------------------- |
| `calculator`     | `tools.py`         | Mathematical calculations |
| `get_pricing`    | `zantara_tools.py` | Bali Zero service pricing |
| `team_knowledge` | `zantara_tools.py` | Team member search/list   |

**Implementation:** `reasoning.py:867-883`

**DO NOT modify trusted tools check without understanding the full flow.**

### CRM RBAC (Role-Based Access Control) — Updated 2026-03-21

**File:** `backend/app/routers/crm_practices.py` + `crm_utils.py`

| Role                                                              | Access                                      |
| ----------------------------------------------------------------- | ------------------------------------------- |
| Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`, role=admin) | All clients and practices                   |
| Team Member (role != admin)                                       | Only practices where `clients.assigned_to` = own email |

**Implementation:** `crm_utils.can_view_all_practices()` + SQL `AND c.assigned_to = $email`. Server-side only, frontend unchanged.

### Date Conversion Fix

**Files:** `crm_enhanced.py`, `crm_clients.py`

PostgreSQL DATE fields must be converted explicitly when using asyncpg:

```python
date_value = row['date_field'].isoformat() if row['date_field'] else None
```

### Lazy Loading (Fly.io Startup)

**Problem:** Heavy Python imports (torch, sentence-transformers, 70+ routers) loaded synchronously caused crash-loops.

**Solution:** Lazy imports + background init via `asyncio.create_task()` in `lifespan()`. Health returns `"initializing"` (HTTP 200) while services load.

**Key files:**

- `backend/app/setup/app_factory.py` — `_background_init()` + lazy router imports
- `backend/app/setup/service_initializer.py` — All 20+ service imports inside functions
- `backend/app/setup/router_registration.py` — All 70+ router imports inside `include_routers()`
- `Dockerfile` — `--workers 1` (DO NOT change without upgrading VM)

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
4. OOM with 2 workers -> Must use `--workers 1`

```bash
fly logs -a nuzantara-rag
fly ssh console -a nuzantara-rag
```

### Rogue Changes from Other AI Tools (CRITICAL - Updated 2026-02-16)

Other AI tools (Gemini, Windsurf, Cursor) have **repeatedly** broken production code by:

- Removing imports they consider "unused" (e.g., `Any` from typing -- caused production crash 2026-02-16)
- Renaming/deleting functions (e.g., `get_logger`, `db_retry`, `invalidate_cache`)
- Deleting entire modules (e.g., `backend.services.integrations.service`)

**2026-02-16 Incident:** 10 files had `Any` removed from typing imports. `dependencies.py` (imported by ALL routers) crashed the entire production app at startup. Hotfix: commits `bdf83fc54` + `b4abe9108`.

**Pre-existing test debt:** Test cleanup by Windsurf (2026-03-20): 0 failed, 0 errors (was 48 failed + 17 errors). ~385 test files remain after consolidation.

**Core Guardian V3** (2026-03-20): Autonomous code quality agent runs every 3h, fixing deterministic lint issues (DTZ005/DTZ003/ANN204). Files: `apps/evaluator/core_guardian/`. Safety: worktree isolation, flock, circuit breaker (3 failures → 24h cooldown).

**Before deploying, ALWAYS run:**

```bash
# 1. Check for unexpected changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test critical import chain (most important single check)
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core tests (82 tests, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```

If many files were modified unexpectedly, restore and re-apply only your changes:

```bash
git checkout HEAD -- apps/backend-rag/backend/
# Then re-apply your targeted changes
```

---

## ENVIRONMENT VARIABLES

**Critical variables (check before running):**

| Variable          | Purpose                               | Where Used |
| ----------------- | ------------------------------------- | ---------- |
| `DATABASE_URL`    | PostgreSQL connection                 | Backend    |
| `QDRANT_URL`      | Vector DB connection                  | Backend    |
| `OPENAI_API_KEY`  | Embeddings (`text-embedding-3-small`) | Backend    |
| `EMBEDDING_MODEL` | Must be `text-embedding-3-small`      | Backend    |
| `GOOGLE_API_KEY`  | Gemini LLM                            | Backend    |
| `JWT_SECRET_KEY`  | Auth tokens                           | Backend    |
| `PORT`            | Server port                           | Fly.io     |

```bash
fly secrets list -a nuzantara-rag
```

---

## COMMON WORKFLOWS

### Adding a New API Endpoint

1. Create router in `backend/app/routers/`
2. Add business logic in `backend/services/`
3. Register router in `backend/app/setup/router_registration.py` (NOT `main_cloud.py`)
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

Collection config lives in `CollectionManager` (`backend/services/ingestion/collection_manager.py`).

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

## PRE-DEPLOY CHECKLIST (CRITICAL)

- [ ] `git diff --name-only HEAD -- apps/backend-rag/backend/` -- No rogue changes
- [ ] `python -c "from backend.app.dependencies import get_current_user; print('OK')"` -- Import chain OK
- [ ] `PYTHONPATH=. pytest backend/tests/services/rag/ -q` -- Core KG tests pass
- [ ] `fly deploy --strategy rolling` -- Rolling deploy (not all-at-once)
- [ ] `curl https://nuzantara-rag.fly.dev/health` -- Health check after deploy

---

## ESSENTIAL DOCUMENTATION

| Document                      | Path                                                     | When to Read                   |
| ----------------------------- | -------------------------------------------------------- | ------------------------------ |
| **AI Configuration Files**    | `CLAUDE.md`, `.cursorrules`, `.antigravity/context.md`   | First session (AI setup)       |
| **AI Handover Protocol**      | `docs/ai/AI_HANDOVER_PROTOCOL.md`                        | Always (project brain)         |
| **LangGraph KG Architecture** | `docs/KG_LANGGRAPH_ARCHITECTURE.md`                      | Knowledge Graph implementation |
| **System Map 4D**             | `docs/SYSTEM_MAP_4D.md`                                  | Architecture overview          |
| **Observability Guide**       | `docs/operations/OBSERVABILITY_GUIDE.md`                 | Debugging/monitoring           |
| **Deploy Checklist**          | `docs/operations/DEPLOY_CHECKLIST.md`                    | Before deploying               |
| **Database Architecture**     | `docs/DATABASE_ARCHITECTURE_V2.md`                       | DB schema reference            |
| **KG Value Assessment**       | `docs/KG_VALUE_ASSESSMENT_2026_01_18.md`                 | Knowledge Graph ROI            |
| **Intel Pipeline**            | `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md` | News scraper                   |
| **Chain Onboarding**          | `docs/architecture/CHAIN_ONBOARDING_IMPROVEMENTS.md`     | Onboarding workflow details    |
| **Cicatrix Scars**            | `.claude/rules/cicatrix-scars.md`                        | 20 known bugs/gotchas (auto-extracted) |
| **Documentation Archive**     | `docs/archive/MANIFEST.md`                               | Old docs & reports             |

---

## NOTES FOR AI ASSISTANTS

1. **Read the critical knowledge section** - embedding model and KBLI payload structure prevent real production bugs
2. **Follow the golden rules** - they exist because we hit real problems without them
3. **Check for rogue changes** before deploying - other AI tools may have modified shared files
4. **Use `--no-verify` for non-JS commits** - prettier pre-commit hook is known to fail on Python/markdown
5. **Don't over-document** - code that speaks for itself doesn't need a 450-line report. Focus on why, not what.
6. **Check the archive** - Old session reports and transient docs are in `docs/archive/MANIFEST.md`
7. **LangGraph KG is production-ready** - 82 tests passing, 4 subgraphs deployed, feature flag controlled
8. **Test import chain before deploy** - `python -c "from backend.app.dependencies import get_current_user"` prevents production crashes
9. **Test debt cleaned** (2026-03-20) - Windsurf cleanup: 0 failed, 0 errors. Core tests (KG, Channels, RAG) are 100%
10. **Router registration** is in `backend/app/setup/router_registration.py`, NOT in `main_cloud.py`
11. **Lazy loading** - backend uses deferred imports and background init. Health returns 200 during startup.
12. **MCP server has 109 tools** (nuzantara-mcp) + 14 (nuzantara-mcp-advanced) = 123 total. Plus GA4, GSC, OCR external MCP servers.
13. **bali-intel-scraper** runs ONLY on Pro locally via OpenClaw cron, NOT on Fly.io (destroyed 2026-03-14)
14. **Cicatrix scars** - `.claude/rules/cicatrix-scars.md` has 20 auto-extracted known bugs/gotchas. Read before modifying referenced files.
15. **Core Guardian V3** - autonomous code quality agent runs every 3h at $0 cost. Do NOT interfere with its worktree-isolated fixes.
16. **RBAC** - admin/accounting see all practices, team members see only assigned. Server-side only (`crm_utils.can_view_all_practices()`).
17. **AI Dispatch** - `./scripts/ai-dispatch.sh` delegates to Gemini (explore/search) and Codex (sandbox). See CLAUDE.md §15 for patterns.
18. **Pro-Air federation** - post-commit hook syncs Air via SSH. Health monitoring bidirectional. Hot standby failover on Air.

**Remember:** This is a production system serving 5000+ real clients. Be careful with changes, verify the embedding model matches, and test your work.

**Cross-Reference:** See `CLAUDE.md` for Claude Code specific configuration, AI dispatch system, and delegation checkpoint.

---

## PRO-AIR FEDERATION (Updated 2026-03-22)

| Machine | User             | Hostname      | Role                       | RAM   |
| ------- | ---------------- | ------------- | -------------------------- | ----- |
| **Pro** | `nuzantara`      | `Nuzantara`   | Development (primary)      | 48GB  |
| **Air** | `antonellosiano` | `Nuzantara-9` | Server H24                 | 16GB  |

- **SSH:** `ssh air` (from Pro) / `ssh pro` (from Air) — mDNS, works on any WiFi
- **Git sync:** post-commit hook → `ssh air 'cd ~/Projects/nuzantara && git pull --ff-only'`
- **Health:** Pro→Air via `~/monitor-air.sh`, Air→Pro via `monitor-pro.sh`
- **Hot standby:** 4 business cron jobs on Air (disabled), activated after 15min Pro downtime
- **Cron distribution:** Pro 11 active (business+dev), Air 8 active (infra+intel) + 4 standby
- **OpenClaw:** Pro polls Telegram (sole listener), Air sends only (no 409 conflict)

---

## LOCAL AI (Ollama-First, 2026-03-08)

- **Core client:** `backend/llm/ollama_client.py` — **CRITICAL:** set `think: false` for Qwen 3.5
- **Models:** qwen3.5:27b (vision), qwen3.5:9b (fast), gemma3:12b, deepseek-r1:1.5b
- **Vision:** qwen2.5vl:7b ONLY (qwen3.5 Q4_K_M strips vision weights)
- **Vision API:** `"images": [base64_string]` in message object (NOT OpenAI-style)
- **Pattern:** Ollama local → fallback Gemini API. On Fly.io: Gemini always.

---

## SUBDOMAIN ECOSYSTEM

6 Vercel subdomains with SSO via `nz_access_token` httpOnly cookie on `.balizero.com`:

| Subdomain                  | App           | Purpose            |
| -------------------------- | ------------- | ------------------ |
| `kita.balizero.com`        | mouth         | Workspace (main)   |
| `mail.balizero.com`        | mail          | Email interface    |
| `calendar.balizero.com`    | calendar      | Calendar           |
| `drive.balizero.com`       | drive          | File management    |
| `knowledge.balizero.com`   | knowledge     | Knowledge base     |
| `zantara.balizero.com`     | web           | AI chat (rewrites `/` → `/chat`) |
| `my.balizero.com`          | mouth (portal) | Client portal      |
| `prime.balizero.com`       | mouth (prime)  | Spatial intelligence (3D maps) |

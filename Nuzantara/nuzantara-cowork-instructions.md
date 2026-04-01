# Nuzantara — Project Instructions for Claude Cowork

## Who I Am

I'm Zero, founder and owner of **Bali Zero** (balizero.com) — an Indonesian business services company in Bali with 5,000+ clients. We handle visa processing, company setup (PT PMA/PMDN), tax compliance, property advisory, and everything an expat or foreign investor needs to operate legally in Indonesia.

I'm Italian, write in colloquial Italian, and expect Claude to respond in Italian. Technical discussions happen in English internally. I work from Bali and run an AI-first operation — Nuzantara is the AI platform that powers the entire business.

---

## The Nuzantara Universe

**Nuzantara** (codename; the AI assistant is called **Zantara**) is a production AI-powered business intelligence platform — version 5.2, running live at **kita.balizero.com**. It's a monorepo with ~20 apps spanning frontend, backend, AI pipelines, MCP servers, and automation. Everything is built, maintained, and operated by me with the help of AI agents.

### The Monorepo Structure

```
nuzantara/
├── apps/
│   ├── mouth/              → Main frontend (Next.js) — balizero.com
│   ├── backend-rag/        → Python FastAPI backend — Fly.io
│   ├── nuzantara-mcp/      → MCP server (105 tools, 8 autopilot chains)
│   ├── nuzantara-mcp-advanced/ → DevOps MCP (13 tools)
│   ├── evaluator/          → Quality assurance + NLM pipelines
│   ├── bali-intel-scraper/ → Regulatory intelligence scraper
│   ├── war-room/           → Marketing automation (carousel generator)
│   ├── cell/               → CELL organism (autonomous memory)
│   ├── graph-engine/       → Knowledge Graph operations
│   ├── kbli-navigator/     → KBLI 2025 code explorer
│   ├── drive/              → Google Drive satellite
│   ├── mail/               → Email satellite
│   ├── calendar/           → Calendar satellite
│   ├── knowledge/          → Knowledge base satellite
│   ├── web/                → Zantara chat satellite
│   └── admin-dashboard/    → Internal data inspector
├── packages/
│   ├── core/               → Shared utilities + BZ design tokens
│   └── kb/                 → Knowledge base content
├── scripts/                → 60+ automation scripts
└── shared/                 → Escalation management
```

---

## Backend — The Brain

**Stack:** Python 3.11+, FastAPI, 105 routers, 250+ services, 400+ test files. Deployed on **Fly.io** (Singapore region).

### Router Domains (105 routers)

- **CRM** (13): Client management, practices, companies, interactions, documents, analytics, Drive folders
- **Portal** (7): Self-service client portal — billing, documents, visa status, timeline, notifications
- **Intelligence** (9): News ingestion, article composition, newsletter, intel scraping, legal ingest
- **Communications** (7): WhatsApp, Telegram, Instagram, Twitter/X, Zoho email, messaging identity
- **Knowledge/RAG** (10): Agentic RAG, KBLI notebook, Knowledge Graph, oracle (universal legal Q&A), collective memory
- **Analytics** (7): Revenue, team productivity, query analytics, CRM analytics, system observability
- **Admin** (14): Drive auth/health, team activity, conversation cleanup, debug endpoints, webhooks
- **Workflows** (7): Autonomous agents, execution plans, cron notifiers, workflow queue
- **Content/Media** (5): Image generation, audio, voice, media proxy
- **Other** (26): Auth, federation, HR, pricing, compliance, sessions, dashboards

### Service Architecture

Business logic lives in two layers:

- `backend/services/` — Core domain logic (RAG pipeline, Knowledge Graph, search, memory, intel, ingestion)
- `backend/app/services/` — Application-level services (CRM, auth, metrics, notifications)

### Prompt Architecture

All LLM prompts live in a single source of truth: **`backend/prompts/zantara_core.py`**. Sections: security boundary, tool usage policy, language protocol, greeting rules, citation rules, escalation protocol, crash protocol, creator persona, team persona.

### Channels (7)

Zantara speaks to clients through 7 channels:

- **WhatsApp** ✅ Live — Fly.io (Gemini Flash + RAG + triage)
- **Telegram** ✅ Live — Pro OpenClaw (Opus 4.6 + SOUL.md personality)
- **Instagram** ✅ Live — Fly.io adapter
- **Web Chat** ✅ Live — Fly.io (main chat at zantara.balizero.com)
- **X/Twitter** ❌ Broken (CRC validation fail)
- **Google Chat / Slack** 🔧 Scaffold only

---

## Databases & Data

### PostgreSQL (Fly.io, 2GB)

The relational backbone. Key tables:

- **clients** — 5,000+ records. UUID, email, phone, assigned_to, status, tags, custom_fields
- **companies** — 2,000+. Legal type, tax_id, KBLI codes, linked to clients
- **practices** — Active cases (visa renewals, company setup, tax filings). Status workflow: draft → active → completed
- **interactions** — Every touchpoint: calls, emails, WhatsApp messages, meetings. Channel + summary + date
- **company_docs** — 1,800+ documents linked to companies (akta, NPWP, NIB, licenses)
- **kg_nodes / kg_edges** — Knowledge Graph stored in PostgreSQL (56,113 nodes, 161,173 edges)
- **episodes** — LAM episodic memory for the autonomous agent (CELL)
- **system_settings** — Feature flags and runtime config

### Qdrant (Fly.io, 2GB) — Vector Search

8 canonical collections, 93,000+ documents:

- **kbli_2025_final_hybrid** — 1,563 KBLI business activity codes with PMA status, risk categories
- **visa_oracle** — Visa requirements, processes, durations, costs
- **legal_unified_hybrid_hybrid** — 68,000+ legal document chunks (regulations, circulars)
- **bali_zero_pricing_hybrid** — Service pricing (the ONLY source of truth for prices)
- **tax_genius_hybrid** — Indonesian tax regulations
- **training_conversations_hybrid** — Q&A pairs for RAG training
- **immigration_circulars** — Immigration-specific regulations
- **intel_authoritative_sources** — News and regulatory updates

**Embedding model:** `text-embedding-3-small` (1536 dims) — FROZEN. Never change without re-indexing plan.

**Search pipeline:** Hybrid (BM25 keyword + Dense vector + Reciprocal Rank Fusion) → CrossEncoder reranking → Evidence scoring.

### Google Drive

Structured document storage for every client:

- Root folder per client (auto-created)
- Subfolders: Visa Documents, Company Documents, Tax, Property
- Service Account integration with OAuth fallback
- Bidirectional sync: documents uploaded via portal → Drive; Drive changes → DB update
- 6,242 documents hashed, deduplication active

### Redis

Caching layer. Namespaces: `zantara:crm_clients_stats:*`, `zantara:crm_practices:*`. Cache invalidation mandatory after every mutation.

---

## Frontend Ecosystem

All frontends are **Next.js** (16.x) + **React 19**, deployed on **Vercel** with auto-deploy on git push. SSO across all subdomains via `nz_access_token` httpOnly cookie on `.balizero.com`.

### Main App — mouth/ (balizero.com, kita.balizero.com)

The flagship. Everything lives here:

- **Landing page** — balizero.com (company website + blog)
- **Blog** — 100+ articles on immigration, business setup, tax, property, lifestyle, digital nomad life in Bali
- **Workspace** (kita.balizero.com) — The internal CRM + operations dashboard:
  - `/clients/` — Full client management with profiles, documents, OCR extraction
  - `/omnichannel/` — Unified view of WhatsApp, Telegram, Instagram, email conversations
  - `/intelligence/` — News room, article composer, system pulse, visa oracle, analytics
  - `/admin/` — Team activity tracking, CELL diagnostics
  - `/settings/` — Integrations (Drive, Zoho, API keys), roles, users, backup
- **Portal** (my.balizero.com) — Client self-service:
  - Document uploads with OCR (passport → auto-extract name, nationality, expiry)
  - Case tracking with timeline
  - Messaging with assigned consultant
  - Visa status dashboard
- **Chat** — Zantara AI assistant with RAG, agentic reasoning, tool use

### Satellite Apps

Each is a focused Next.js app on its own subdomain:

| App           | URL                    | Purpose                                                        |
| ------------- | ---------------------- | -------------------------------------------------------------- |
| **drive**     | drive.balizero.com     | Google Drive file explorer — grid/list view, folder navigation |
| **mail**      | mail.balizero.com      | Email interface — Zoho integration, HTML sanitization          |
| **calendar**  | calendar.balizero.com  | Google Calendar integration — scheduling, events               |
| **knowledge** | knowledge.balizero.com | Knowledge base — company licenses, KITAS guides, blueprints    |
| **web**       | zantara.balizero.com   | Zantara AI chat (standalone chat interface)                    |

### Prime Intelligence — prime.balizero.com

3D interactive map of Bali with **zoning intelligence**:

- PostGIS spatial queries (`ST_Contains` on `bali_zoning_layers`)
- Click any point → get zoning classification, allowed land use, restrictions
- WebGL-based (Chrome only), Google Maps 3D

### KBLI Navigator — balizero.com/kbli

1,563 statically generated pages for Indonesian KBLI 2025 business activity codes:

- Search by code, keyword, sector
- Each code shows: description, PMA eligibility, risk category, required licenses
- SEO pipeline: 200/1,563 URLs indexed in Google so far
- Deadline: KBLI 2025 transition by June 18, 2026

---

## AI & LLM Layer

### LLM Providers (6)

- **Gemini** (Google) — Primary for Zantara chat (Flash), web search (grounded), exploration (2M context)
- **Claude** (Anthropic) — Orchestration (Claude Code), KBLI chat (Haiku), critical reasoning (Opus)
- **Ollama** (Local) — qwen3.5:27b (KG extraction), qwen3.5:9b (fast routing), gemma3:12b (JSON), qwen2.5vl:7b (vision OCR)
- **DeepSeek** — War Room preprocessor, deep reasoning tasks
- **OpenRouter** — Multi-model aggregator for API calls
- **Vertex AI** — GCP managed inference (fallback)

### Knowledge Graph

56,113 nodes, 161,173 edges. Built from legal documents, regulations, KBLI codes:

- **Node types:** KBLI (20%), Biaya/Fees (17.5%), Pasal/Articles (11.4%), Dokumen (10.6%), UU/Laws (8.1%)
- **Edge types:** REQUIRES (26.8%), PART_OF (24.8%), REFERENCES (15%), HAS_FEE (4.9%)
- **Subgraphs:** Company ✅, Visa ✅, Property (partial), Tax (partial)
- Extraction via qwen3.5:27b with 2-step fix for output reliability

### RAG Pipeline

The core intelligence loop:

1. User query → Intent classification (Haiku)
2. Hybrid search: BM25 + Dense vector across relevant collections
3. Reciprocal Rank Fusion to merge results
4. CrossEncoder reranking for precision
5. Evidence scoring: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL
6. KG subgraph traversal for structured knowledge
7. LLM synthesis with citations and source attribution

---

## MCP Servers — The Automation Layer

### nuzantara-mcp (Primary — 105 tools, 8 chains)

Full-spectrum business automation. Claude and other AI agents use these tools to:

- Manage CRM (create/update clients, practices, interactions)
- Run the client portal (dashboard, documents, messages)
- Search intelligence and publish articles
- Calculate pricing (PricingTool is the ONLY source of truth)
- Send communications (WhatsApp, email, Telegram)
- Manage Google Drive and Sheets
- Execute autonomous workflows with safety levels (SAFE/CRITICAL/IRREVERSIBLE)

**8 Deterministic Autopilot Chains** (no LLM decisions — pure IF/THEN/ELSE):

1. **Daily Ops Autopilot** — Expiry checks, agent health, critical intel, team metrics → daily report email
2. **New Client Onboarding** — CRM creation → KBLI matching → visa recommendation → Drive setup → practice creation
3. **Practice Lifecycle Check** — Visa renewals, document reminders, escalations
4. **Intel Pipeline** — Scraper jobs → RAG assessment → auto-approval → article composition
5. **Compliance Autopilot** — Multi-channel notifications (WhatsApp/email/portal) → auto-renewal creation
6. **Journey Accelerator** — Full client journey from first contact to completion
7. **Weekly Report** — CRM stats + revenue + team productivity + intelligence trends → email
8. **Client Health Monitor** — Scoring, re-engagement, portal updates, birthday greetings

### nuzantara-mcp-advanced (DevOps — 13 tools)

Deployment, diagnostics, testing:

- Fly.io status, logs, health analysis, recovery actions
- Backend testing (pytest), linting (ruff), type checking
- Codebase search and documentation discovery

---

## Intelligence & Automation Pipelines

### NotebookLM Deep Research (11 notebooks)

Automated knowledge grounding via Google NotebookLM:

- **NB-2:** Immigration & Visa — regulations, circulars, government social feeds
- **NB-3:** Company & Licensing — business formation, KBLI compliance
- **NB-4:** Tax & Compliance — Indonesian tax law
- **NB-5:** Property & Zoning — land use, Hak Pakai, foreign ownership
- **NB-6:** Operations — internal procedures
- **NB-7:** Editorial & Market — content strategy
- **NB-8:** Expat Life — lifestyle content
- **NB-11:** Ops Grounding — operational data from database
- **NB-12:** Intel Grounding — business intelligence
- **NB-13:** Telemetry — system performance

Daily pipelines per domain. T4 Social Monitor scrapes government social feeds every 6 hours. DB→NLM sync runs daily at 04:30 WITA.

### Bali Intel Scraper

Regulatory intelligence pipeline:

- Multi-source scraping of Indonesian government websites, regulations, news
- Deduplication, scoring, validation
- Automatic RAG ingestion and article composition
- Runs locally on Pro (not Fly.io) via OpenClaw cron at 03:00 WITA

### War Room — Marketing Automation

7-phase pipeline producing Instagram carousel content:

1. Topic selection (Exa + NLM + Grok → DeepSeek synthesis)
2. Research (news + social signals + audience insights)
3. Pre-processing (DeepSeek R1:32b local)
4. Brain Trust (Gemini strategist + Claude director)
5. Image generation (Fireworks Flux.1 Dev)
6. Canva carousel builder (11 slides via MCP)
7. Delivery to Telegram (Zero in Italian, Damar in Indonesian)

### Core Guardian V3

Automated quality assurance — runs every 3 hours in a git worktree:

- Empty catch audit, RBAC audit, API contract audit
- Cache invalidation audit, dead code audit
- Auto-fixes lint issues

---

## Infrastructure

### Hardware — Two-Machine Setup

- **Pro** (nuzantara@Nuzantara): Mac Studio M4 Pro 48GB — primary development machine
- **Air** (antonellosiano@Nuzantara-9): Mac Mini M4 16GB — 24/7 server for crons, pipelines, monitoring

Git sync: Pro commits → Air auto-pulls. Air commits → pushes to Pro. GitHub pushes only from Pro.

### Cloud

- **Fly.io** (3 apps): nuzantara-rag (backend, 2GB, auto-stop), nuzantara-qdrant (2GB), nuzantara-postgres (2GB). ~$35-40/mo
- **Vercel**: All frontend apps (auto-deploy on git push)
- **Backups**: Daily pg_dump → Tigris object storage

### AI Agent Runtime — OpenClaw

Agent runtime on macOS:

- Pro: 2 agents (main Opus 4.6, coder Qwen27b)
- Air: 3 agents (main Opus 4.6, coder Qwen27b, qa-visual Gemini Pro)
- @Balizerobot Telegram: Pro polls exclusively, Air+Fly send only
- Gateway: loopback:18789

### Federation Architecture v3.1

Multi-agent orchestration with 3-tier taxonomy:

- **AGENTS (7):** Claude Code (orchestrator), Gemini (explore/search), Codex (sandbox), Claude CLI (review), Aider (multi-model), DeepSeek (reasoning)
- **SERVICES (5):** NotebookLM, Google Workspace, OCR, Web Search, Canva
- **PIPELINES (5):** Core Guardian, Intel Scraper, War Room, SEO Guardian, NLM Refresh

All agents called via CLI only (never SDK/API). Delegation model: Gemini explores → Claude Code decides → Claude Code or Codex executes.

---

## Domain Knowledge

### Indonesian Business Services

- **Visa types:** KITAS (limited stay), KITAP (permanent), B211 (visit), investor visa, retirement visa, work permits (RPTKA/IMTA)
- **Company types:** PT PMA (foreign), PT PMDN (local), CV, UD, representative office
- **KBLI:** Klasifikasi Baku Lapangan Usaha Indonesia — every business activity has a 5-digit code with PMA eligibility, risk category, and license requirements
- **Compliance:** Quarterly tax reporting, annual LKPM investment activity report, visa renewals, work permit renewals
- **Key regulations:** UU Cipta Kerja, PP 5/2021 (OSS/RBA), KBLI 2025, immigration law (Permenkumham/Permen Imipas)

### Client Lifecycle

1. First contact (WhatsApp/web/referral) → Zantara triage
2. Onboarding → CRM record + KBLI matching + visa recommendation
3. Document collection → Drive folders + OCR extraction
4. Practice creation → Active case with timeline
5. Processing → Government submissions, follow-ups
6. Completion → Document delivery, compliance calendar setup
7. Ongoing → Renewal alerts, compliance monitoring, re-engagement

---

## Communication Rules

- **Language with me:** Italian (colloquial). Translate intent into precise technical action.
- **Language with team:** Bahasa Indonesia (emails to @balizero.com except zero@)
- **Language with clients:** Match their language
- **Email sender:** Always `zantara@balizero.com`, from_name "Zantara"
- **Tone in Indonesian:** Casual jaksel (Jakarta Selatan) slang — mix Bahasa with English loanwords naturally
- **All prices:** From PricingTool only. Never hardcode or guess.
- **Image style:** Title-driven, vivid saturated colors, bright. Never dark/moody. Reference: @balizero0 Instagram.

---

## Operational Rules

- Never use Anthropic/OpenAI API credits — subscriptions only (Claude Max, Gemini CLI, ChatGPT Plus). For API: OpenRouter or DeepSeek credits.
- AI agents always called via CLI (gemini, codex, claude commands) — never via SDK/API.
- Ask before launching batch API calls to paid services — state call count + estimated cost.
- Never set ANTHROPIC_API_KEY in system env — Claude CLI uses OAuth.
- Web search: Exa primary (full content + citations), Brave fallback. Never suggest Perplexity.
- Embedding model is FROZEN: text-embedding-3-small (1536 dims, 93,283 vectors). Never change.
- After any frontend deploy: auto-screenshot with browser tools, verify visual integrity.
- Delegation mindset: Gemini explores → Claude decides → Claude/Codex executes.

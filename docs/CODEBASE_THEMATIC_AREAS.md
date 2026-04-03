# Nuzantara Codebase — Thematic Areas Analysis

> Generated: 2026-04-03 | Monorepo: 19 apps, 2 packages, ~2,500+ files

---

## Overview

The Nuzantara codebase is organized as a monorepo serving the Bali Zero business intelligence platform. Below is a breakdown into **10 coherent thematic areas**, each with its scope, key components, and file counts.

---

## 1. RAG Backend & API Core

**Scope:** Central FastAPI application — the brain of the platform. Handles all API requests, business logic, RAG pipeline, and service orchestration.

**Location:** `apps/backend-rag/` (1,316 .py files)

| Sub-area | Path | Files | Description |
|----------|------|-------|-------------|
| **Routers (API)** | `backend/app/routers/` | 98 | REST endpoints: CRM, portal, auth, analytics, agents, channels, webhooks |
| **Core Services** | `backend/services/` | 347 | Business logic: RAG, search, KG, pricing, compliance, CRM, invoicing, intel, memory, analytics |
| **App Services** | `backend/app/services/` | ~10 | Application-level: auth, CRM, HR, metrics |
| **App Setup** | `backend/app/setup/` | ~5 | Factory, router registration, service initializer |
| **Core** | `backend/core/` | 28 | Config, security, logging, base classes |
| **Database** | `backend/db/` + `migrations/` | 88 | ORM models, Alembic migrations (up to 060) |
| **Prompts** | `backend/prompts/` | 7 | Prompt SSOT (`zantara_core.py`) — system instructions, persona, tools policy |
| **Middleware** | `backend/middleware/` | 6 | Request/response processing |
| **Tests** | `backend/tests/` | 507 | Unit, integration, service tests |

**Key routers by domain:**
- **CRM:** `crm_clients`, `crm_practices`, `crm_company`, `crm_interactions`, `crm_analytics`, `crm_documents`, `crm_notifications`
- **Portal:** `portal`, `portal_billing`, `portal_drive`, `portal_invite`, `portal_taxes`, `portal_visa`
- **AI/RAG:** `agentic_rag`, `agent`, `agents`, `dream`, `oracle_universal`, `naga`
- **Channels:** `whatsapp_chat`, `telegram`, `instagram_chat`, `twitter`, `webhooks`
- **Content:** `article_composer`, `blog_ask`, `news`, `newsletter`
- **Admin:** `admin_*` (drive, logs, team, Zoho), `dashboard`, `health`
- **Analytics:** `analytics`, `crm_analytics`, `intel_analytics`, `workflow_analytics`, `team_analytics`

---

## 2. Omnichannel Communication

**Scope:** Multi-channel message handling — WhatsApp, Telegram, Instagram, Twitter/X, Web Chat, Google Chat, Slack.

**Locations:**
- `apps/backend-rag/backend/channels/` (25 .py files)
- Related routers in `backend/app/routers/`

| Channel | Status | Handler | Notes |
|---------|--------|---------|-------|
| WhatsApp | Live | `channels/whatsapp/` | Gemini 3 Flash + RAG on Fly.io |
| Telegram | Live | `channels/telegram/` | Opus 4.6 + SOUL.md on Pro/OpenClaw |
| Instagram | Live | `channels/instagram/` | Fly.io |
| X/Twitter | Broken | `channels/twitter/` | CRC issue |
| Web Chat | Live | `channels/web/` | Fly.io |
| Google Chat | Scaffold | — | Planned |
| Slack | Scaffold | — | Planned |

**Supporting modules:**
- `channels/base.py` — base channel class
- `channels/formatters/` — response formatting per channel
- `channels/optimizations.py` — performance tuning
- `channels/router.py` — channel routing logic

---

## 3. Frontend & User Experience

**Scope:** Next.js web application — workspace, portal, blog, KBLI explorer, marketing pages.

**Locations:**
- `apps/mouth/` (~822 files) — main frontend
- `apps/kbli-navigator/` (55 files) — standalone KBLI explorer

| Area | Path | Components | Description |
|------|------|------------|-------------|
| **Workspace** | `src/app/(workspace)/` | dashboard, analytics, admin, HR, clients, intel, settings | Protected business workspace |
| **Portal** | `src/app/portal/` | login, register, authenticated area | Client-facing portal |
| **Chat** | `src/app/chat/` + `components/chat/` | 30 components | AI chat interface |
| **Blog/Marketing** | `src/app/(blog)/` + `src/app/(marketing)/` | 21 blog components | Content & SEO pages |
| **KBLI** | `src/app/kbli/` + `components/kbli/` | 10 components | 1,563 SSG classification pages |
| **Dashboard** | `components/dashboard/` | 27 components | Widgets, layout, stats |
| **UI Library** | `components/ui/` | 20 components | Shadcn/UI (button, dialog, tabs, badge...) |
| **CRM UI** | `components/crm/` | ~7 components | Client management UI |
| **Social Channels** | `components/instagram/`, `telegram/`, `twitter/`, `whatsapp/` | Various | Channel-specific UI |

**Subdomains served:**
`kita.balizero.com` (workspace) · `my.balizero.com` (portal) · `prime.balizero.com` (3D maps) · `mail` · `calendar` · `drive` · `knowledge` · `zantara`

---

## 4. AI & LLM Infrastructure

**Scope:** LLM clients, agent frameworks, RAG pipeline, knowledge graph, vector search, embeddings.

**Locations:**
- `apps/backend-rag/backend/llm/` (22 .py files)
- `apps/backend-rag/backend/services/rag/`
- `apps/backend-rag/backend/services/knowledge_graph/`
- `apps/backend-rag/backend/services/search/`
- `apps/backend-rag/backend/services/llm_clients/`
- `apps/backend-rag/backend/agents/` (31 .py files)
- `apps/graph-engine/` (71 files)

| Component | Description |
|-----------|-------------|
| **LLM Clients** | Ollama, Gemini, OpenRouter wrappers |
| **RAG Pipeline** | Hybrid search (BM25+Dense+RRF) + CrossEncoder reranking |
| **Knowledge Graph** | 108K nodes, 243K edges. LangGraph subgraphs (Company, Visa, Property, Tax) |
| **Vector Store** | Qdrant — 10 collections, 93K documents, `text-embedding-3-small` (1536 dims) |
| **Agents** | Autonomous agents, agentic RAG, Naga reasoning engine |
| **Graph Engine** | Standalone graph processing app with subgraphs, graders, observability |
| **Memory** | Episodic memory, collective memory, conversation tracking |

**Models in use:**
- Claude Opus 4.6 (critical), Sonnet 4.6 (RAG), Haiku 4.5 (routing)
- Ollama local: qwen3.5:27b/9b, gemma3:12b, qwen2.5vl:7b (vision)
- Gemini (search, redteam, fallback)

---

## 5. MCP Servers & Tool Ecosystem

**Scope:** Model Context Protocol servers exposing tools, prompts, resources, and workflows to AI agents.

**Locations:**
- `apps/nuzantara-mcp/` (42 files) — primary MCP v2.1
- `apps/nuzantara-mcp-advanced/` (5 files) — Fly.io ops, diagnostics

| MCP Module | Tools | Scope |
|------------|-------|-------|
| `tools/admin.py` | Admin ops | System administration |
| `tools/analytics.py` | Analytics | Reporting & metrics |
| `tools/crm.py` | CRM | Client management |
| `tools/compliance.py` | Compliance | Regulatory checks |
| `tools/content.py` | Content | Content management |
| `tools/drive.py` | Drive | Google Drive integration |
| `tools/federation.py` | Federation | Multi-agent federation |
| `tools/google_bridge.py` | Google | Workspace integration |
| `tools/health.py` | Health | System monitoring |
| `tools/intel.py` | Intelligence | Business intelligence |
| `tools/invoicing.py` | Invoicing | Billing |
| `tools/journey.py` | Journey | Customer lifecycle |
| `tools/knowledge.py` | Knowledge | KB management |
| `tools/langsmith.py` | LangSmith | Tracing |
| `tools/legal.py` | Legal | Legal compliance |
| `tools/memory.py` | Memory | Agent memory |
| `tools/portal.py` | Portal | Portal ops |
| `tools/pricing.py` | Pricing | Price management |
| `tools/sheets.py` | Sheets | Google Sheets |
| `tools/workflows.py` | Workflows | Orchestration |

**Totals:** 131 tools, 10 prompts, 5 resources, 8 chains

---

## 6. Business Domain Services

**Scope:** Domain-specific business logic for Indonesian business services.

**Locations:** `apps/backend-rag/backend/services/` (sub-directories)

| Domain | Path | Description |
|--------|------|-------------|
| **CRM** | `services/crm/` | Client management, practices, interactions, documents, notifications |
| **Pricing** | `services/pricing/` | PricingTool (SSOT for all prices) |
| **Compliance** | `services/compliance/` | UU PDP, regulatory checks |
| **Invoicing** | `services/invoicing/` | Billing, invoice generation |
| **Portal** | `services/portal/` | Client portal backend |
| **Journey** | `services/journey/` | Customer lifecycle tracking |
| **Documents** | `services/documents/` | Document management, OCR |
| **KBLI** | `services/` + `kbli_eye.py` | Business classification (KBLI 2025) |
| **WhatsApp** | `whatsapp_context_builder.py`, `whatsapp_onboarding_detector.py` | Channel-specific business logic |

**Domain schemas** (`packages/shared-schemas/`): Tax, Property, Visa, KBLI, Company

---

## 7. Intelligence & Data Pipeline

**Scope:** Web scraping, content ingestion, data processing, evaluation, and SEO.

**Locations:**
- `apps/bali-intel-scraper/` (74 files)
- `apps/evaluator/` (83 files)
- `apps/backend-rag/backend/services/intel/`
- `apps/backend-rag/backend/services/ingestion/`

| Component | Path | Description |
|-----------|------|-------------|
| **Intel Scraper** | `apps/bali-intel-scraper/` | Browser automation, RSS feeds, incremental scraping, proxy rotation |
| **SEO Guardian** | `apps/evaluator/seo_guardian_*` | SEO validation, auto-fixer, learning module |
| **Core Guardian V3** | `apps/evaluator/core_guardian/` | Code quality checks (runs every 3h) |
| **Red Team** | `apps/evaluator/red_team_evaluator.py` | Adversarial testing |
| **Judgement Day** | `apps/evaluator/judgement_day.py` | Content quality assessment |
| **Article Composer** | `services/article_composer/` | Content generation pipeline |
| **Ingestion** | `services/ingestion/` | Document & knowledge ingestion |
| **Intel Analytics** | Routers + services | Intel reporting |

---

## 8. Operations, Monitoring & Automation

**Scope:** Infrastructure management, health checks, automated maintenance, CI/CD.

**Locations:**
- `apps/war-room/` (12 files)
- `config/` (20 files — Prometheus, Grafana, AlertManager, Nginx)
- `scripts/` (45 files — 16 shell, 29 Python)
- `.github/` — CI/CD workflows

| Area | Key Components |
|------|---------------|
| **War Room** | Operations dashboard, pipeline orchestrator |
| **Monitoring** | Prometheus + Grafana + AlertManager stack |
| **Health** | `fly-health-check.sh` (5min), `system_doctor.py` (daily), RAG canary (6h) |
| **Backups** | `fly-pg-backup.sh`, `fly-qdrant-backup.sh` → Tigris |
| **Sentinel** | `nuzantara-sentinel.py` — circuit breaker, alerter, classifier, repairer |
| **Cron Jobs** | 10+ scheduled: ollama, auto-test, sentinel, KB ingest, drive watchdog, judgement day |
| **AI Dispatch** | `ai-dispatch.sh` — routes tasks to Claude/Gemini/Codex/DeepSeek |
| **Federation** | `federation_orchestrator.py` — multi-agent task dispatch |
| **Self-Healing** | `backend/self_healing/` — auto-recovery mechanisms |

**Fly.io deployment:** 3 apps (nuzantara-rag, nuzantara-postgres, nuzantara-qdrant)
**Vercel:** Frontend auto-deploy on push to main

---

## 9. Autonomous Agents & Multi-Agent Systems

**Scope:** Autonomous agent architectures, team coordination, cell-based agents.

**Locations:**
- `apps/cell/` (71 files)
- `apps/team-agent/` (16 files)
- `apps/backend-rag/backend/agents/` (31 files)
- `apps/backend-rag/backend/services/autonomous_agents/`

| Agent System | Description |
|-------------|-------------|
| **Cell** | Biological cell metaphor: sensors (input), metabolism (processing), memory, effectors (output), lifecycle |
| **Team Agent** | Multi-agent coordination, onboarding, MCP wrapper bridge |
| **Backend Agents** | Autonomous execution agents within the RAG backend |
| **Autonomous Agents** | Self-directed task execution with workflow orchestration |

**Architecture:** Agents consume MCP tools, use shared schemas, coordinate via federation protocol and escalation system (`shared/escalations.json`).

---

## 10. Knowledge, Data & Configuration

**Scope:** Knowledge base, reference data, shared schemas, documentation, configuration.

**Locations:**
- `packages/shared-schemas/` (16 files)
- `packages/core/` (4 files)
- `data/` — knowledge graph, reference, source documents, NLM responses
- `docs/` — 80+ documentation files
- `skills/` (10 skill definitions)
- `config/prompts/` — prompt templates

| Area | Contents |
|------|----------|
| **Shared Schemas** | Pydantic models: messages, state, events, grading, tools + 5 domain schemas |
| **Core Utils** | Currency, date, expiry utilities (TypeScript) |
| **Knowledge Graph Data** | `data/knowledge_graph/` — graph data files |
| **Reference Data** | `data/reference/` — pricing, visa types, KBLI gold standard |
| **Source Documents** | `data/source_documents/` — ingested documents |
| **NLM Responses** | `data/notebooklm_responses/` — cached NLM outputs |
| **Documentation** | 80+ docs: architecture, API, CRM, deployment, compliance, SEO, AI strategy |
| **Skills** | 10 Claude Code skills: domain knowledge, email, calendar, git helper |

---

## Cross-cutting Concerns

| Concern | Where it lives |
|---------|---------------|
| **Authentication** | `backend/core/security`, `backend/app/routers/auth.py`, SSO via `nz_access_token` |
| **RBAC** | CRM role-based access (Admin, Team) |
| **Caching** | Redis + `services/caching/` — namespace invalidation required after mutations |
| **Logging** | `backend/core/` — structured logging (never `print()`) |
| **Events** | `services/events/` + `routers/event_bus.py` — event-driven patterns |
| **Observability** | Sentry, Prometheus, LangSmith tracing |
| **i18n** | `apps/mouth/src/i18n/` — internationalization |

---

## Summary Table

| # | Thematic Area | Primary Locations | ~Files |
|---|--------------|-------------------|--------|
| 1 | RAG Backend & API Core | `apps/backend-rag/` | 1,316 |
| 2 | Omnichannel Communication | `backend/channels/` | 25 |
| 3 | Frontend & UX | `apps/mouth/`, `apps/kbli-navigator/` | 877 |
| 4 | AI & LLM Infrastructure | `backend/llm/`, `services/rag/`, `apps/graph-engine/` | 150+ |
| 5 | MCP Servers & Tools | `apps/nuzantara-mcp/`, `apps/nuzantara-mcp-advanced/` | 47 |
| 6 | Business Domain Services | `backend/services/crm/`, `pricing/`, `compliance/`... | 100+ |
| 7 | Intelligence & Data Pipeline | `apps/bali-intel-scraper/`, `apps/evaluator/` | 157 |
| 8 | Operations & Automation | `apps/war-room/`, `scripts/`, `config/` | 77 |
| 9 | Autonomous Agents | `apps/cell/`, `apps/team-agent/`, `backend/agents/` | 118 |
| 10 | Knowledge, Data & Config | `packages/`, `data/`, `docs/`, `skills/` | 200+ |

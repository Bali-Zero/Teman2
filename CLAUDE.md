# CLAUDE.md - Nuzantara Project Context for Claude Code

> **Read `SYMBIOSIS.md` first.** It defines the principles that govern this entire ecosystem. If what you're about to do contradicts a principle there, stop.
> **Before building anything new, read `VADEMECUM.md`.** It has the operative checklist for every element type: automations, agents, routers, migrations, deploys. No exceptions.
> **Need to find where X lives?** See [`INDEX.md`](INDEX.md) — it's the atlas of organs, tissues, nerves. Start there before asking.

## 0. Machine Identification (IMPORTANT)

| Machine | User             | Hostname      | Role                            |
| ------- | ---------------- | ------------- | ------------------------------- |
| **Pro** | `nuzantara`      | `Nuzantara`   | Server H24 + Dev (48GB, M4 Pro) |
| **Air** | `antonellosiano` | `Nuzantara-9` | Server H24 (16GB, M4)           |

**At every session start, run:**

```bash
echo "Machine: $(whoami)@$(hostname)" && \
OTHER=$(if [ "$(whoami)" = "nuzantara" ]; then echo "air"; else echo "pro"; fi) && \
ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE"
```

- `whoami` = `nuzantara` → **Pro** · `whoami` = `antonellosiano` → **Air**
- Always prefix first response with "[Pro]" or "[Air]"
- SSH: `ssh air` / `ssh pro` (mDNS). Details: `docs/PRO_AIR_CONNECTION.md`

---

## 1. Project Overview

**Name:** Nuzantara (Zantara) · **Version:** 5.2.0
**Type:** Production AI-powered business intelligence platform for Bali Zero
**Business:** Indonesian business services (visa, company setup, tax, property) in Bali — 5000+ clients
**URL:** https://kita.balizero.com

### Architecture — Monorepo

<!-- DOCSYNC:LIVING_ORGANS_START -->
**Apps:** 23 · **Packages:** 5

| App | Ruolo |
| --- | ----- |
| `admin-dashboard` | A standalone Next.js application to inspect and control Nuzantara data. |
| `admin-dashboard-local` | Pro-only LLM cost dashboard. **Not deployed anywhere.** |
| `backend-rag` | **Production-Ready AI-Powered RAG System for Business Intelligence** |
| `bali-intel-scraper` | Intelligence pipeline for Bali Zero news and regulatory updates. |
| `cell` |  |
| `cell-observatory-collector` | Pro-local Python service that listens to `cell_pulse_observed` PG channel, |
| `crm-cell` | Sprint 3 W2 — light cell wrapping the existing CRM modules |
| `evaluator` | Security and quality evaluation tools for the Nuzantara RAG system. |
| `graph-engine` | Graph processing engine for Knowledge Graph operations. |
| `kb` |  |
| `kbli-navigator` |  |
| `mata-garuda` | > Intelligence Super Hub — OSINT blindato, CLI-only, Lamarckian meta-agent |
| `mouth` | > **The face of Nuzantara** - A Next.js 16 + React 19 frontend for the Nuzantara AI ecosystem |
| `nlm-bridge` |  |
| `nuzantara-mcp` | Primary MCP server for Zantara AI assistant. FastMCP, stdio transport. |
| `nuzantara-mcp-advanced` | Advanced MCP (Model Context Protocol) server for Nuzantara operations, deployment, and diagnostics. |
| `nuzantara-mcp-browser` | FastMCP server exposing Nuzantara's stealth Playwright browser manager |
| `openclaw-hgt-coordinator` |  |
| `organism` | See `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` for full design. |
| `osint-nexus-ui` |  |
| `team-agent` |  |
| `web` | Vercel subdomain satellite app. AI chat interface (rewrites / to /chat). |
| `zantara-media` | Mata Garuda Layer 4.5 — Asset indexer + multi-channel curator. |
<!-- DOCSYNC:LIVING_ORGANS_END -->

See [`INDEX.md`](INDEX.md) for the full atlas including packages, tessuti dati, cron schedule, and top-of-mind organs.

### Tech Stack

<!-- DOCSYNC:BACKEND_STATS_START -->
- **Backend:** Python 3.11+, FastAPI, 261 routers, 544 services, 917 test files
<!-- DOCSYNC:BACKEND_STATS_END -->
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** 108,068 nodes, 242,827 edges
<!-- DOCSYNC:VECTOR_STATS_START -->
- **Vector Collections:** 12 live on Fly.io (104,154 documents), 12 defined in code
<!-- DOCSYNC:VECTOR_STATS_END -->
- **Embedding Model:** `text-embedding-3-small` (1536 dims) — **NEVER CHANGE** (would invalidate 93,283 vectors)
- **Search Pipeline:** Hybrid (BM25+Dense+RRF) + CrossEncoder reranking

### Key Terms

- **OpenClaw**: Agent runtime (macOS). Cron, Telegram, background tasks. Gateway `loopback:18789`.
- **mcporter**: MCP-to-OpenClaw bridge. Wrappers in `~/.local/bin/`.
- **Bali Zero**: Client-facing brand. Indonesian business services in Bali.
- **Zantara**: AI assistant persona for all client-facing channels.

### Verify Setup (first session only)

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no 2>/dev/null && echo "✅ Tests OK"
```

---

## 2. Claude Code Behavior Rules (IMPORTANT)

**DO NOT ask the user to write code.** Act first, ask if blocked.

- Use `Edit`, `Write`, `Bash` without asking permission
- **NEVER** ask "should I write this?" — just do it

### Autonomous Operations — read `AUTONOMOUS_OPS.md` at project root

The user has pre-authorized a specific scope of autonomous action (commits,
push, PRs, auto-merge when CI green, deploy via `fly-deploy.yml`, post-deploy
browser QA). **Do not ask for confirmation** on anything listed as
"autonomous" for the active Level in that file. Only ask for confirmation on
items listed as "requires confirmation" or unlisted (conservative default).

Read `AUTONOMOUS_OPS.md` fully before acting on: git push, PR operations,
deploy, `fly ssh`, or any change to shared state. Check the "active since"
date — if stale (>30 days), fall back to conservative mode and ask the user
to re-certify. The user is not a developer; their veto is NOT the safety
layer — the guardrails listed in that file are.

### Browser Automation Rules

- **ALWAYS** `mcp__claude-in-chrome__*` — **NEVER** `mcp__playwright__*` (unless user orders)
- Text before screenshot: `get_page_text`, `find`, `javascript_tool` first
- Screenshots only for visual QA (layout, colors, logo)

### Federation Orchestrator (AUTOMATICO)

`python scripts/federation_orchestrator.py "task"` — classifies, dispatches, assembles.

**Triggers that MUST go through orchestrator:**

| Trigger                                   | Dispatches            | Why                             |
| ----------------------------------------- | --------------------- | ------------------------------- |
| KBLI, visa, normativa                     | Gemini `search`       | Claude hallucina su regolamenti |
| Refactor 3+ app                           | Gemini `explore`      | 1M ctx mappa dipendenze         |
| Grounding / Regola Oracolo                | NotebookLM `oracolo`  | Ground Truth NB-1               |
| Deep Research                             | NotebookLM `research` | Autonomous web research         |
| Alembic migration                         | Codex `sandbox`       | Testa upgrade+downgrade         |
| Pre-deploy Fly.io                         | Gemini `redteam`      | Mai deploy senza red team       |
| Fix dependencies.py / service_initializer | Codex `sandbox`       | Import chain SPOF               |

**Simple tasks** (bug fix, update component): proceed directly.

### Preflight SDD (task non triviali)

| Trigger                                                | Level |
| ------------------------------------------------------ | ----- |
| 3+ file in app diverse                                 | L1    |
| Nuova feature                                          | L1    |
| dependencies.py / service_initializer.py               | L2    |
| Refactor 3+ app, migration, KBLI/visa, pre-deploy      | L2    |
| Nuova architettura, feature critica (auth/billing/RAG) | L3    |

`./scripts/ai-dispatch.sh preflight "desc"` (L2), `preflight-l1` (L1), `preflight-l3` (L3)
Escape: `SKIP_PREFLIGHT=1` (logged in `audit.jsonl`)

### Escalations

Check `shared/escalations.json` at session start — handle pending before other work.

## 3. MOS — Memory Operating System

Il SessionStart hook carica automaticamente le ultime 5 memorie importanti (importance >= 7) da SQLite.

**CLI `mem`** (`~/.claude/scripts/mem`) per operazioni manuali:

| Comando                                    | Cosa fa                   | Latenza |
| ------------------------------------------ | ------------------------- | ------- |
| `mem recent`                               | Ultime memorie importanti | <10ms   |
| `mem query "testo"`                        | Cerca per testo (FTS5)    | <10ms   |
| `mem save decision "scelta X perché Y" 8`  | Salva decisione           | <10ms   |
| `mem save discovery "trovato bug in X" 7`  | Salva scoperta            | <10ms   |
| `mem save unresolved "da investigare Z" 6` | Salva TODO                | <10ms   |
| `mem entities "nome"`                      | Cerca entità              | <10ms   |
| `mem sessions`                             | Ultime sessioni           | <10ms   |
| `mem stats`                                | Statistiche DB            | <10ms   |

Per dominio (visa, tax, KBLI): `notebook_query` su NB-2..8 (3-8s)
Per architettura deep: `notebook_query` su NB-1 (3-8s)
Per sessioni storiche: `notebook_query` su NB-14 (3-8s)

**Regola:** `mem` PRIMA di NotebookLM. NLM solo per dominio o cross-query.

### Salvataggio proattivo (OBBLIGATORIO)

Claude DEVE salvare proattivamente in MOS senza che l'utente lo chieda. Esegui `~/.claude/scripts/mem save` immediatamente quando:

- **decision**: scelta architetturale, tecnologia selezionata, approccio scelto tra alternative
- **discovery**: bug trovato, comportamento inatteso, insight tecnico non ovvio
- **fact**: configurazione infra verificata, credenziali/endpoint confermati, versioni accertate
- **unresolved**: problema non risolto, TODO da investigare, workaround temporaneo

Importance: 8-10 decisioni architetturali, 7-8 scoperte e fatti, 5-6 unresolved.
File changes tracciati automaticamente — non serve salvarli.
**NON chiedere all'utente se salvare. Salva e basta.**

## 4. Golden Rules (ENFORCE STRICTLY)

1. **Virtualenv Mandatory** — Never system Python. Always activate venv.
2. **No Root Execution** — `PYTHONPATH=. python -m backend.module`
3. **Path Discipline** — Absolute imports only: `from backend.core import config`
4. **Async First** — `httpx` not `requests`. All I/O async.
5. **Type Hints** — Full annotations on every function.
6. **No Hardcoded Secrets** — env vars or secrets manager.
7. **Data/Logic Separation** — Business logic ≠ data access.
8. **Clean Logging** — `logger` never `print()`.
9. **Verify Sources** — Never presume, verify against actual data.
10. **Async HTTP Clients** — NEVER `httpx.AsyncClient()` in methods/loops. Persistent `_get_client`, close in `lifespan`.
11. **Flat Qdrant Payloads** — Never nested. Use `kode_kbli`, `judul`, `content`, `pma_status` etc.
12. **PricingTool Only** — All prices from `PricingTool`. Never hardcode/guess.

## 5. Critical Paths

### Backend Structure

```
apps/backend-rag/
├── backend/
│   ├── app/                # FastAPI app
│   │   ├── routers/        # API endpoints (HTTP routers — flat files)
│   │   ├── services/       # App-level services (CRM, auth, metrics)
│   │   ├── setup/          # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py # ⚠️ Imported by ALL routers — test before deploy
│   │   └── main.py         # Entrypoint (alias for main_cloud.py)
│   ├── services/           # Core business logic (domain services, subpackages)
│   ├── channels/           # 4 live (whatsapp, telegram, instagram, web) + .disabled-2026-04-30/ (twitter — CRC broken; gchat/slack scaffolds never wired)
│   ├── core/               # Config, security, logging
│   ├── llm/                # LLM clients (Gemini, Ollama, OpenRouter)
│   ├── prompts/            # ⭐ Prompt SSOT (zantara_core.py)
│   └── migrations/         # Custom migration system (migration_NNN_*.py; runner: backend/db/migration_manager.py)
├── tests/                  # Unit + integration tests (backend/tests — separate from top-level apps/backend-rag/tests)
├── .venv/                  # ⚠️ ALWAYS .venv, not venv
└── fly.toml
```

> Absolute counts for routers / services / tests / migrations live in the DOCSYNC-marked block in §1 (auto-regenerated by `scripts/docs_sync.py`). Don't hardcode them here — they drift.

**IMPORTANT:** Routers in `backend/app/routers/`, NOT `backend/routers/`. Services in both `backend/services/` and `backend/app/services/`.

### Prompt Architecture

Edit ONLY `backend/prompts/zantara_core.py`. All consumers import from it.
Sections: `SECURITY_BOUNDARY` · `TOOL_USAGE_POLICY` · `SYSTEM_INSTRUCTIONS` · `KNOWLEDGE_GOVERNANCE` · `LANGUAGE_PROTOCOL` · `GREETING_RULES` · `CITATION_RULES` · `INTERNAL_MONOLOGUE` · `ESCALATION_PROTOCOL` · `CRASH_PROTOCOL` · `CLOSING_PHRASES` · `CREATOR_PERSONA` · `TEAM_PERSONA` · `ZANTARA_MASTER_TEMPLATE`

## 6. Domain-Specific Knowledge

### KBLI — Flat payload, fields: `kode_kbli`, `judul`, `content`, `sektor_id`, `pma_status`, `skala_usaha`, `kategori_risiko`

### Pricing — All from `PricingTool`. Ref: `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md`

### Evidence Scoring — `<0.15` ABSTAIN · `0.15-0.60` CAUTIOUS · `>0.60` NORMAL

<!-- DOCSYNC:EMBEDDING_FROZEN_START -->
### Embedding — `text-embedding-3-small` (1536 dims) FROZEN. Never change without re-indexing plan.
<!-- DOCSYNC:EMBEDDING_FROZEN_END -->

## 7. MCP Servers

- **Primary:** `apps/nuzantara-mcp/` (v2.1, 115 tools, 10 prompts, 5 resources, 8 chains)
- **Advanced:** `apps/nuzantara-mcp-advanced/` (Fly.io ops, 14 tools)
- **Browser:** `apps/nuzantara-mcp-browser/` (FastMCP, 6 tools over shared `packages/browser-core` stealth manager -- default remains `mcp__claude-in-chrome__*`; use `mcp__nuzantara-browser__*` only from non-interactive contexts or when explicitly ordered)
- **GA4:** property 505466833 (G-S3H2M6VXWT)
- **GSC:** 19 SEO tools, SA auth, site owner balizero.com
- **OCR:** tesseract with Indonesian support
- **Bridge (OpenClaw):** 129 tools via mcporter wrappers

## 8. Deployment Architecture

### Fly.io — 2 APP ONLY (Qdrant migrated to Qdrant Cloud)

| App                  | CPU       | RAM | Auto-stop  | Note                    |
| -------------------- | --------- | --- | ---------- | ----------------------- |
| `nuzantara-rag`      | shared-2x | 2GB | off, min=1 | Always-on, EventBus     |
| `nuzantara-postgres` | shared-1x | 2GB | no         | v0.1.0, backup → Tigris |

- **Frontend:** Vercel (auto-deploy on `git push origin main`)
- **Backend deploy:** `cd apps/backend-rag && fly deploy --strategy rolling`
- **bali-intel-scraper**: ONLY local on Pro via OpenClaw (03:00 WITA)
- **Backup:** `~/scripts/fly-pg-backup.sh` daily → Tigris
- **Health:** `~/scripts/fly-health-check.sh` every 5min → Telegram alert

### Env Vars Required

`OPENAI_API_KEY` · `DATABASE_URL` · `QDRANT_URL` · `QDRANT_API_KEY` · `REDIS_URL` · `JWT_SECRET` · `FLY_API_TOKEN`

## 9. Language Protocol

The user writes in **colloquial Italian**. Translate intent into precise technical action.

- Never ask "what do you mean?" — infer from codebase context
- Italian colloquial → English technical internally, respond in Italian
- If ambiguous, pick most likely interpretation, state assumption in one line

**Owner:** Zero (codename). Real name PRIVATE. Italian with owner, client's language otherwise.

## 10. Resources & Routes

- **API Docs:** `http://localhost:8000/docs`
- **Pricing:** `PRICING_REFERENCE.md` · **Visa:** `VISA_TYPES_REFERENCE.md`
- **KBLI:** `/kbli` (homepage), `/kbli/[code]` (1,563 SSG pages), `/kbli-navigator` → 301 → `/kbli`

### Channels (4 live)

| Channel    | Status   | Ownership                         |
| ---------- | -------- | --------------------------------- |
| WhatsApp   | ✅ Live  | Fly.io (Gemini 3 Flash + RAG)     |
| Telegram   | ✅ Live  | Pro OpenClaw (Opus 4.6 + SOUL.md) |
| Instagram  | ✅ Live  | Fly.io                            |
| Web Chat   | ✅ Live  | Fly.io                            |

> Twitter (CRC broken), Google Chat (scaffold), and Slack (scaffold)
> quarantined under `apps/backend-rag/backend/channels/.disabled-2026-04-30/`
> — see README in that directory for reactivation criteria. None of these
> are enrolled in the Innervation Genoma registry.

### Subdomains (8)

`kita.balizero.com` (workspace) · `my.balizero.com` (portal) · `prime.balizero.com` (3D maps) · `mail` · `calendar` · `drive` · `knowledge` · `zantara` (AI chat). SSO via `nz_access_token` httpOnly cookie on `.balizero.com`.

### Local AI (Ollama-First)

- `backend/llm/ollama_client.py` — **CRITICAL:** `think: false` for Qwen 3.5
- Models: gemma4:26b (MoE, KG/JSON), qwen3.5:9b (fast), deepseek-r1:32b (reasoning), qwen2.5vl:7b (vision)
- Vision: **qwen2.5vl:7b ONLY** (qwen3.5 Q4_K_M strips vision weights). API: `"images": [base64]`
- Pattern: Ollama local → fallback Gemini. On Fly.io: Gemini always.

### CRM RBAC

Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`) → all. Team → only `assigned_to` matches.

### Team Bali Zero (operational reference)

| Member | Email | Role | Perimeter |
|---|---|---|---|
| Antonello (Zero) | `zero@balizero.com` / `antonellosiano@gmail.com` | Owner / Architect | All |
| Asya | `asya@balizero.com` | Platform / Backend | All except prod secrets rotation |
| Surya | `surya@balizero.com` | Tax operations | Tax practices, CoreTax |
| Ari Firda | `ari.firda@balizero.com` | Visa/Immigration | Visa practices, KITAS |
| Adit | `adit@balizero.com` | Operations / Welcome | Office, contracts, onboarding |
| Sahira | `sahira@balizero.com` | Sales / WhatsApp | Lead handoff, client comms |
| Krisna | `krisna@balizero.com` | LKPM / Reporting | LKPM allowlist (migration 110), Telegram @KrissTzy |
| Damar | `damar@balizero.com` | Marketing / War Room | Canva, social, dispatch carousels |
| Vino | `vino@balizero.com` | Marketing | Social, content support |
| Veronika | `tax@balizero.com` | Tax team manager | Tax team coordination |
| Rina | `rina@balizero.com` | Reception | Front desk, scheduling |
| Ruslana | `ruslana@balizero.com` | Strategic / English content | Strategy, English copy. Telegram chat_id 3743891689 |
| **Subhi Darajat** ⭐ NEW | `subhi@balizero.com` | **Growth Systems Owner** (probation 90gg 2026-04-30 → 2026-07-29) | `apps/mouth/(blog\|marketing\|kbli\|visa\|property\|tax-calendar)/**` + GA4/GSC + organic distribution. NO backend RAG, NO organs_registry.yaml (Innervation Genoma — file renamed 2026-05-08 IG-3 from `genome.yaml`), NO secrets. See `~/.claude/projects/-Users-nuzantara/memory/subhi-{task-routing,rbac-permissions,contact}.md` |

**Email language to team** (`feedback_email_language.md`): Bahasa Indonesia for all `@balizero.com` except `zero@`/`antonellosiano@`. Subhi: bahasa default, italiano OK as fallback.

**Email sending** (REGOLA FISSA): always `from=zantara@balizero.com` (alias of `zero@balizero.com`) via Brevo `/api/notifications/send-email` + `X-API-Key: REDACTED-ROTATED-KEY`. Never `notifications@`, `subhi@` for automated/transactional sends.

## 10. Frontend Deploy — QA Automatico (OBBLIGATORIO)

After any frontend deploy, automatically:

1. Wait for deploy live (curl 200/307)
2. Screenshot with `mcp__claude-in-chrome__*` of each modified app
3. Verify: colors, logo, no broken elements
4. Fix and redeploy if issues found
5. Final report with screenshots

URLs: `kita` · `my` · `prime` · `calendar` · `mail` · `drive` · `knowledge` · `zantara` — all `.balizero.com`

## 11. Pre-Deploy Checklist

```bash
git diff --name-only HEAD -- apps/backend-rag/backend/    # 1. Check rogue changes
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"  # 2. Import chain
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q  # 3. Core tests
fly deploy --strategy rolling  # 4. Deploy
```

Core Guardian V3 runs every 3h fixing lint issues in worktree. Do NOT interfere.

**Migration PRs**: any PR touching `apps/backend-rag/backend/db/migrations_v2/*.sql`
also runs **Squawk migration lint** (`.github/workflows/migration-lint.yml`,
PR #306) at PR-check time, ~90s after push. It catches dangerous Postgres
operations (DROP COLUMN, ALTER without DEFAULT, non-CONCURRENT index, etc.)
before the pre-deploy gate even runs. To bypass on a legitimate destructive
change: `-- squawk-ignore: <rule-name>` on the offending statement. Full
reference: [`docs/oss-injections-2026-04-26.md`](docs/oss-injections-2026-04-26.md).

**WR2 image-generator backend** (Sprint 1.6 W3, 2026-05-03): `WR2_IMAGE_BACKEND` selects FlowKit (`auto` default — opt-in primary, falls back to Playwright) / `flowkit` / `playwright`. See [`docs/wr2/flowkit-integration.md`](docs/wr2/flowkit-integration.md).

## 12. AI Dispatch System

> `./scripts/ai-dispatch.sh help` for full commands. Details: `docs/AI_DISPATCH_REFERENCE.md`

**Agents:** Claude Code (orchestrator) · Gemini Pro CLI (explore/search/redteam) · Codex CLI (sandbox) · Claude CLI (review) · DeepSeek R1 (reasoning) · Aider (multi-model coding)
**Services:** NotebookLM · GWS CLI · OCR · Websearch · Canva · GitKraken
**Pipelines:** Core Guardian (3h) · Intel Scraper (03:00) · War Room · SEO Guardian · NLM Refresh (04:30)

### GitKraken MCP — prefer over raw git/gh when richer context available

`gitlens_commit_composer` · `gitlens_launchpad` · `gitlens_start_work` · `gitlens_start_review` · `pull_request_create`

### Security

- Gemini: `--sandbox --approval-mode plan` → read-only
- Codex: `--sandbox read-only` or `workspace-write`. NEVER `--dangerously-bypass`
- Off-limits: `zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`

### Federation Protocol

- Escalation: Air → `shared/escalations.json` → Pro reads at session start
- Git sync: post-commit hook. Pro→Air auto-pull. Air→Pro push. GitHub: only Pro→origin.
- CLAUDE.md: IDENTICAL on both — git-tracked

## 13. Anthropic API — Quick Reference

> Full patterns: `docs/ANTHROPIC_API_REFERENCE.md`

### Adaptive Thinking (REQUIRED on 4.6)

```python
thinking={"type": "adaptive"}, output_config={"effort": "medium"}  # NOT budget_tokens
```

### Models for Nuzantara

| Use                     | Model                       |
| ----------------------- | --------------------------- |
| RAG, reasoning          | `claude-sonnet-4-6`         |
| Routing, classification | `claude-haiku-4-5-20251001` |
| Critical tasks          | `claude-opus-4-6`           |

### Prompt Caching — use `cache_control: {"type": "ephemeral"}` on large system prompts / KBLI KB

## 14. CRITICAL OPERATIONAL RULES

> Not derivable from code. For ALL AI agents.

### Virtualenv

- **Air:** `venv` (NOT `.venv`) — `apps/backend-rag/venv/bin/python`
- **Pro:** `.venv` — verify with `ls apps/backend-rag/ | grep venv`
- **pip on Air:** `/Users/antonellosiano/.pyenv/shims/python3 -m pip`

### Drive Polling (Air only)

- Cron every 5min (`scripts/drive_poll_cron.sh`). **NOT on Fly.io** (auto_stop loses page_token)
- `page_token` in `system_settings` table — loss = full re-scan
- Circuit breaker: 3 failures → OPEN + Telegram alert → auto-recovery 5min

### Drive OAuth

- Token in `google_drive_tokens` table — expires ~90 days
- Watchdog: `scripts/drive_token_watchdog.py` alerts 7 days before
- Re-auth: `https://kita.balizero.com/settings/integrations`

### OCR Multi-page

- **ALWAYS all pages** — directors typically page 2-3 of akta. Timeout: 120s for >3 pages.
- Vision: `qwen2.5vl:7b` ONLY

### Cache Invalidation

```python
await invalidate_cache("zantara:namespace:*")  # REQUIRED after every mutation
```

Namespaces: `zantara:crm_clients_stats:*`, `zantara:crm_practices:*`

### LLM Structured Output Pattern (PR #311)

For any LLM call expected to return **structured data** (list, dict, enum,
yes/no), use `client.generate_structured()` instead of prompt-engineered JSON
+ `try/except json.loads`. Pydantic v2 validates the response; on
`ValidationError` the call retries once with the parser feedback in the
prompt. Catches silent JSON-decode failures that previously fell through to
fallback heuristics.

```python
from pydantic import BaseModel
from backend.llm.genai_client import get_genai_client, LLMStructuredOutputError

class GraderVerdict(BaseModel):
    reasoning: str  # ALWAYS first — forces think-before-commit
    relevant: bool
    confidence: float

client = get_genai_client()
try:
    verdict = await client.generate_structured(
        contents=prompt, response_schema=GraderVerdict, endpoint="rag.grader.X"
    )
except LLMStructuredOutputError:
    # Schema failed twice — fall back to your default heuristic.
    ...
```

OUT of scope today: KG entity extraction (deeply nested, qwen3.5 fails),
Claude OAuth CLI (no SDK to wrap). Reference:
[`docs/oss-injections-2026-04-26.md`](docs/oss-injections-2026-04-26.md).

### Observability Env Vars (PR #312)

When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are unset, observability is
**dormant** (~1ms no-op per call). To activate on Fly:

```bash
fly secrets set -a nuzantara-rag \
  LANGFUSE_PUBLIC_KEY="<your-pk>" LANGFUSE_SECRET_KEY="<your-sk>" \
  LANGFUSE_HOST="https://us.cloud.langfuse.com"
```

Defaults are **PII-hidden** (`hide_input_messages`/`hide_output_messages` ON
because Bali Zero queries contain NPWP/NIB/passport/names — UU PDP scope).
Opt-in for debugging: `LANGFUSE_TRACE_LLM_MESSAGES=true`.

Per-provider kill-switch (no redeploy, takes effect on next restart):
- `LANGFUSE_INSTRUMENT_GOOGLE_GENAI=false` — disable Gemini auto-trace
- `LANGFUSE_INSTRUMENT_OPENAI=false` — disable DeepSeek/Ollama auto-trace
- `LANGFUSE_INSTRUMENT_ANTHROPIC=false` — disable Anthropic auto-trace
- `LANGFUSE_ENABLED=false` — disable everything (full kill-switch)

Reference: [`docs/oss-injections-2026-04-26.md`](docs/oss-injections-2026-04-26.md).

### KG Subgraph Status

Company ✅ · Visa ✅ · Property ✅ · Tax ✅

### Cron Air

| Job               | Schedule     | Script                               |
| ----------------- | ------------ | ------------------------------------ |
| Ollama start/stop | 01:00/06:05  | `ollama_cron_window.sh`              |
| Auto test         | 02:15        | `auto_test.sh`                       |
| Sentinel          | 03:00        | `auto_sentinel.sh`                   |
| Indexing Sweep    | 00:30        | `daily_indexing_cron.sh` (Phase 1: articles 200/day, Phase 2: KBLI 600/day → Telegram) |
| KB Ingest         | 05:00        | `auto_kb_ingest.sh`                  |
| RAG Canary        | \*/6h :30    | `rag_canary.py`                      |
| System Doctor     | 08:00        | `system_doctor.py --notify-telegram` |
| Drive Watchdog    | \*/6h :00    | `drive_token_watchdog.py`            |
| Judgement Day     | Sun 16:00    | `auto_judgement_day.sh`              |
| RAGAS Eval        | Sun 06:00    | `ragas_eval.py`                      |
| KG Quality        | \*/48h 04:00 | `auto_kg_quality.sh`                 |

### GitHub Secrets

`FLY_API_TOKEN` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_OWNER_CHAT_ID` (1125336968 — Zero's `@zero0101010101010` chat with `@Balizerobot`, verified live 2026-04-07)

## 15. Escalation Tasks

Check `~/.agent/decisions/claude_tasks/` at session start. Work by `priority` (HIGH first), then `created_at`. Delete file after fix + verify with `test_cmd`.

## 16. Research Capture Convention

Quando l'assistente produce una ricerca sostanziosa per un caso cliente Bali Zero, va salvata — non deve morire nella scrollback.

**Dove:** `~/Desktop/nuzantara/research/{property,visa,tax,hr,compliance}/YYYY-MM-DD-topic-slug.md`

**Frontmatter obbligatorio:**
```yaml
---
date: YYYY-MM-DD
domain: property|visa|tax|hr|compliance
client_case: <breve descrizione>
sources: <n>
---
```

**Trigger (proponi save quando TUTTI veri):** risposta ≥ ~400 parole sostanziali · ≥ 3 fonti distinte · contiene checklist/procedura/lista documenti · dominio in {property, visa/immigration, tax, HR, compliance} · legata a caso cliente o scenario concreto.

**Formato proposta (una riga):** *"Questa mi sembra da salvare in `research/<domain>/` — procedo? (y/n)"*

**Su y:**
1. Scrivi file con frontmatter + body verbatim
2. Appendi una riga in `~/.claude/projects/-Users-nuzantara/memory/MEMORY.md` sotto `## Research Captures` (formato: `- YYYY-MM-DD <domain> <slug> → research/<domain>/<file>.md — <one-line summary>`)
3. **Solo se domain=property:** push del body come text source su NotebookLM NB-5 (`d9438180-5e63-4e2a-a473-6061101f6a8d`) via `mcp__notebooklm-mcp__source_add`. Altri domini: non toccare i NB curati.

**Non promuovere mai automaticamente a KB ufficiale** (`apps/backend-rag/backend/kb/`): quello è curato, le research capture restano in `research/` come livello "ad-hoc auditable".

---

**Last Updated:** 2026-04-24
**Maintained by:** Bali Zero AI Team

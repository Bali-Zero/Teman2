# CLAUDE.md - Nuzantara Project Context for Claude Code

## 0. Machine Identification (IMPORTANT)

| Machine | User             | Hostname      | Role                       |
| ------- | ---------------- | ------------- | -------------------------- |
| **Pro** | `nuzantara`      | `Nuzantara`   | Development (48GB, M4 Pro) |
| **Air** | `antonellosiano` | `Nuzantara-9` | Server H24 (16GB, M4)      |

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

### Architecture — Monorepo (20 apps)

- `apps/mouth/` - Next.js frontend (Vercel) — kita/my/prime.balizero.com
- `apps/backend-rag/` - Python FastAPI RAG backend (Fly.io)
- `apps/nuzantara-mcp/` - MCP server v2.1 (109 tools, 10 prompts, 5 resources, 8 chains)
- `apps/nuzantara-mcp-advanced/` - Advanced MCP (Fly.io ops, diagnostics, 14 tools)
- `apps/nuzantara-mcp-browser/` - Browser automation MCP
- `apps/bali-intel-scraper/` - Intel pipeline (runs LOCALLY on Pro via OpenClaw, NOT Fly)
- `apps/evaluator/` - Quality assurance + Core Guardian V3
- `apps/war-room/` - Operations dashboard + Canva automation
- `apps/graph-engine/` - Graph processing engine
- `apps/kbli-voice/` · `apps/zantara-media/` · `apps/admin-dashboard/` · `apps/webapp/`
- `apps/kbli-navigator/` - KBLI 2025 Navigator
- `apps/calendar/` · `apps/drive/` · `apps/knowledge/` · `apps/mail/` · `apps/web/` - Subdomain satellites
- `packages/core/` - Core libraries + BZ design tokens + BZLogo
- `packages/kb/` - Knowledge base

### Tech Stack

<!-- DOCSYNC:BACKEND_STATS_START -->

- **Backend:** Python 3.11+, FastAPI, 90 routers, 253 services, 419 test files
<!-- DOCSYNC:BACKEND_STATS_END -->
- **Frontend:** Next.js, TypeScript, Tailwind CSS
- **Databases:** PostgreSQL (relational), Qdrant (vector), Redis (cache)
- **Infrastructure:** Fly.io (backend), Vercel (frontend)
- **Knowledge Graph:** 108,068 nodes, 242,827 edges
<!-- DOCSYNC:VECTOR_STATS_START -->
- **Vector Collections:** 10 live on Fly.io (93,283 documents), 11 defined in code
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
- Only ask for: architecture trade-offs, production deploys, destructive ops

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
│   │   ├── routers/        # API endpoints (88 routers)
│   │   ├── services/       # App-level services (CRM, auth, metrics)
│   │   ├── setup/          # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py # ⚠️ Imported by ALL routers — test before deploy
│   │   └── main.py         # Entrypoint (alias for main_cloud.py)
│   ├── services/           # Core business logic (244 services)
│   ├── channels/           # 7 channels (whatsapp, telegram, instagram, twitter, web, gchat, slack)
│   ├── core/               # Config, security, logging
│   ├── llm/                # LLM clients (Gemini, Ollama, OpenRouter)
│   ├── prompts/            # ⭐ Prompt SSOT (zantara_core.py)
│   └── migrations/         # Alembic (up to 060)
├── tests/                  # 385 test files
├── .venv/                  # ⚠️ ALWAYS .venv, not venv
└── fly.toml
```

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

- **Primary:** `apps/nuzantara-mcp/` (v2.1, 131 tools, 10 prompts, 5 resources, 8 chains)
- **Advanced:** `apps/nuzantara-mcp-advanced/` (Fly.io ops, 14 tools)
- **Browser:** `apps/nuzantara-mcp-browser/`
- **GA4:** property 505466833 (G-S3H2M6VXWT)
- **GSC:** 19 SEO tools, SA auth, site owner balizero.com
- **OCR:** tesseract with Indonesian support
- **Bridge (OpenClaw):** 129 tools via mcporter wrappers

## 8. Deployment Architecture

### Fly.io — 3 APP ONLY

| App                  | CPU       | RAM | Auto-stop  | Note                    |
| -------------------- | --------- | --- | ---------- | ----------------------- |
| `nuzantara-rag`      | shared-2x | 2GB | off, min=1 | Always-on, EventBus     |
| `nuzantara-postgres` | shared-1x | 2GB | no         | v0.1.0, backup → Tigris |
| `nuzantara-qdrant`   | shared-1x | 2GB | no         | v1.17.0                 |

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

### Channels (7)

| Channel             | Status        | Ownership                         |
| ------------------- | ------------- | --------------------------------- |
| WhatsApp            | ✅ Live       | Fly.io (Gemini 3 Flash + RAG)     |
| Telegram            | ✅ Live       | Pro OpenClaw (Opus 4.6 + SOUL.md) |
| Instagram           | ✅ Live       | Fly.io                            |
| X/Twitter           | ❌ CRC broken | Fly.io                            |
| Web Chat            | ✅ Live       | Fly.io                            |
| Google Chat · Slack | 🔧 Scaffold   | —                                 |

### Subdomains (8)

`kita.balizero.com` (workspace) · `my.balizero.com` (portal) · `prime.balizero.com` (3D maps) · `mail` · `calendar` · `drive` · `knowledge` · `zantara` (AI chat). SSO via `nz_access_token` httpOnly cookie on `.balizero.com`.

### Local AI (Ollama-First)

- `backend/llm/ollama_client.py` — **CRITICAL:** `think: false` for Qwen 3.5
- Models: qwen3.5:27b, qwen3.5:9b, gemma3:12b, deepseek-r1:1.5b
- Vision: **qwen2.5vl:7b ONLY** (qwen3.5 Q4_K_M strips vision weights). API: `"images": [base64]`
- Pattern: Ollama local → fallback Gemini. On Fly.io: Gemini always.

### CRM RBAC

Admin (`zero@`, `antonellosiano@`, `asya@balizero.com`) → all. Team → only `assigned_to` matches.

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

### KG Subgraph Status

Company ✅ · Visa ✅ · Property ✅ · Tax ✅

### Cron Air

| Job               | Schedule    | Script                               |
| ----------------- | ----------- | ------------------------------------ |
| Ollama start/stop | 01:00/06:05 | `ollama_cron_window.sh`              |
| Auto test         | 02:15       | `auto_test.sh`                       |
| Sentinel          | 03:00       | `auto_sentinel.sh`                   |
| KB Ingest         | 05:00       | `auto_kb_ingest.sh`                  |
| RAG Canary        | \*/6h :30   | `rag_canary.py`                      |
| System Doctor     | 08:00       | `system_doctor.py --notify-telegram` |
| Drive Watchdog    | \*/6h :00   | `drive_token_watchdog.py`            |
| Judgement Day     | Sun 16:00   | `auto_judgement_day.sh`              |
| RAGAS Eval        | Sun 06:00   | `ragas_eval.py`                      |

### GitHub Secrets

`FLY_API_TOKEN` · `TELEGRAM_BOT_TOKEN` · `TELEGRAM_OWNER_CHAT_ID` (413539912)

## 15. Escalation Tasks

Check `~/.agent/decisions/claude_tasks/` at session start. Work by `priority` (HIGH first), then `created_at`. Delete file after fix + verify with `test_cmd`.

---

**Last Updated:** 2026-03-31
**Maintained by:** Bali Zero AI Team

# INDEX — L'Atlante dei Libri Sacri

> **Loaded first** in ogni sessione. Se il tuo bisogno non è qui, aggiorna questo file.
> **Ultima revisione manuale:** 2026-07-02

---

## Cosa cerchi?

| Bisogno                                       | Dove guardare                                                                       | Come                                                                     |
| --------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Perché fare X?                                | [SYMBIOSIS.md](SYMBIOSIS.md)                                                        | Filosofia, "prima di toccare"                                            |
| Come fare X?                                  | [VADEMECUM.md](VADEMECUM.md)                                                        | Checklist operativa per ogni tipo di elemento                            |
| Dove vive X?                                  | Questa pagina, sezione "Organi" sotto                                               | Mappa statica top-level                                                  |
| Metriche live (count routers/servizi/vector)? | [README.md](README.md) §Tech Stack + [docs/AI_ONBOARDING.md](docs/AI_ONBOARDING.md) | Auto-sincronizzate via `docs_sync.py` (marker rimossi da CLAUDE.md, F44) |
| Dettagli tecnici di un'app?                   | `apps/<nome>/README.md` o `apps/<nome>/CLAUDE.md`                                   | File locali all'app                                                      |
| Quando X è stato fatto?                       | `git log` + MOS (`~/.claude/scripts/mem query "X"`)                                 | Git + memoria persistente                                                |
| Policy AI dispatch / federazione?             | [docs/AI_DISPATCH_REFERENCE.md](docs/AI_DISPATCH_REFERENCE.md)                      | Dispatch, fallback, timeout                                              |
| Cicatrici / bug ricorrenti?                   | [.claude/rules/cicatrix-scars.md](.claude/rules/cicatrix-scars.md)                  | Trauma + antibody per file chiave                                        |
| Stato della documentazione (live/stale)?      | [docs/DOCS_INVENTORY.md](docs/DOCS_INVENTORY.md)                                    | Auto-generato, refresh settimanale via docs-guardian                     |

## Organi principali (top of mind)

### Biology framework

- **`packages/cell-core/`** — Framework biologico base (lifecycle, genome, pulse, homeostasis, safety, memory protocols). **BASE per tutti gli agenti viventi**. Maturation 5 fasi (embrione→anziano). Vedi `packages/cell-core/cell_core/__init__.py` per API pubblica.
- **`apps/mata-garuda/`** — Meta-agent Lamarckian 5-layer (Harvester → Kognitif → Nexus → Analista → Distribuzione). Usa cell-core. Sentinel cell + Sensors + Actors.
- **`apps/cell/`** — Organism cell implementation. PulseLoop istanziato. Telegram alerts, skill accumulation.

### Production workloads

- **`apps/backend-rag/`** — RAG backend (FastAPI, deploy Fly.io; count routers/services in README.md §Tech Stack auto-sync). Prompt SSOT: `backend/prompts/zantara_core.py`. Include WR2 pipeline (`backend/services/{war_room,council,visual,canva_renderer,review,publisher}/`).
- **`apps/mouth/`** — Next.js frontend (Vercel). kita/my/prime.balizero.com.
- **`apps/bali-intel-scraper/`** — Intel pipeline daily 03:00 WITA (solo Pro, NOT Fly). Articoli MDX → GitHub → Vercel.
- **`apps/zantara-media/`** — Curator Agent GARUDA (Sprint 5.1 LIVE). Drive indexer + Qdrant `garuda_assets` + Postgres `garuda_index`.

### Intelligence

- **`apps/evaluator/`** — Core Guardian V3/V5 (auto-calibration), NLM deep research (10 pipelines NB-1..10).
- **`packages/core/`** — BZ design tokens, BZLogo, libraries condivise.

### MCP

- **`apps/nuzantara-mcp/`** — MCP v2.1 primary (115 tools, 10 prompts, 5 resources, 8 chains).
- **`apps/nuzantara-mcp-advanced/`** — Fly.io ops, diagnostics (14 tools).
- **`apps/nuzantara-mcp-browser/`** — Browser automation via `packages/browser-core`.

## Se stai per...

| Azione                       | Leggi prima                                                                       | Note                                                      |
| ---------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Scrivere codice nuovo        | SYMBIOSIS §"Prima di toccare" → VADEMECUM §corrispondente                         | Sempre                                                    |
| Creare cron/automation       | VADEMECUM §1 + verifica `scripts/automation_catalog.json`                         | Minimo vitale: produces/consumes/catalog                  |
| Creare agente vivente        | VADEMECUM §2 + **usa `packages/cell-core/`** (non reimplementare)                 | PulseLoop, Genome, Maturation già esistono                |
| Creare router FastAPI        | VADEMECUM §3 + `backend/app/dependencies.py` import check                         | Routers in `backend/app/routers/`, NOT `backend/routers/` |
| Alembic migration            | VADEMECUM + `ai-dispatch.sh codex-migrate`                                        | Testa upgrade+downgrade                                   |
| Deploy production Fly.io     | VADEMECUM §Pre-Deploy + `./scripts/ai-dispatch.sh claude-redteam`                 | Mai senza red team                                        |
| Frontend deploy Vercel       | CLAUDE.md §11 (Deploy Lifecycle) + `mcp__claude-in-chrome__*`                     | Screenshot obbligatorio post-deploy                       |
| Federation dispatch          | Skill `federation-dispatch` (~/.claude/skills/) + `./scripts/ai-dispatch.sh help` | No-skip rule se user ordina                               |
| Debuggare bug                | Skill `superpowers:systematic-debugging` + cicatrix-scars                         | Root cause > patch                                        |
| Modificare `zantara_core.py` | **FERMATI**. È SSOT prompt, OFF-LIMITS diretto.                                   | Solo via revisione esplicita Zero                         |

## Tessuti (dati)

### Qdrant (vector, Fly Cloud)

10+ collection: `balizero_news`, `visa_oracle`, `tax_genius_hybrid`, `kbli_2025_final_hybrid`, `legal_unified_hybrid_hybrid`, `immigration_circulars`, `bali_zero_pricing_hybrid`, `training_conversations_hybrid`, `intel_authoritative_sources`, `garuda_assets` (nuovo Sprint 5.1). Embedding **`text-embedding-3-small` 1536d — FROZEN, mai cambiare**.

### Postgres (Fly `nuzantara-postgres`)

Tabelle core: `articles`, `kg_nodes`/`kg_edges` (108K/242K), `garuda_index`/`garuda_indexer_state`, `publication_history`/`publication_assets`, `crm_clients`/`crm_practices`, `conversations`/`messages`, `google_drive_tokens`, `system_settings`, `lkpm_receipts`, `routing_stats`/`failed_queries`, `post_publish_queue`.

### Filesystem state

- `~/.agent/decisions/` — agent state, DLQ, escalation
- `shared/escalations_pro.jsonl`, `shared/escalations_air.jsonl` — federation bus
- `apps/evaluator/nlm_deep_research/*_state.json` — NB pipelines state

### GitHub

- `Balizero1987/Teman2` — intel articles MDX → Vercel auto-deploy

## Cron schedule (50+ jobs, sintesi)

- **03:00 WITA** intel-scraper daily (Pro)
- **04:30 WITA** GARUDA indexer daily (Pro, Sprint 5.1)
- **Sun 05:00 WITA** GARUDA GC weekly (cron `0 21 * * 6` UTC)
- **02:10-02:50 WITA** NLM NB-2..10 pipeline (Mon-Sat)
- **21:30/22:00 WITA** gap_scanner + freshness_monitor
- **every 3h** Core Guardian
- **every 5min** log-anomaly-detector, drive-poll (Pro), sentinel
- **Dettagli completi:** `docs/AUTOMATIONS_REFERENCE.md` + `scripts/automation_catalog.json`

## Organi enumerabili (auto-generato — non editare a mano)

> Sezioni sincronizzate da `scripts/docs_sync.py`; il gate CI `docs-sync.yml` fallisce se stale.
> Rigenera con `python scripts/docs_sync.py`.

### Apps (tutte, enumerate da disco)

<!-- DOCSYNC:LIVING_ORGANS_START -->
**Apps:** 33 · **Packages:** 6

| App | Ruolo |
| --- | ----- |
| `admin-dashboard` | A standalone Next.js application to inspect and control Nuzantara data. |
| `admin-dashboard-local` | Pro-only LLM cost dashboard. **Not deployed anywhere.** |
| `autonomous-lab` |  |
| `backend-rag` | **Production-Ready AI-Powered RAG System for Business Intelligence** |
| `bali-intel-scraper` | Intelligence pipeline for Bali Zero news and regulatory updates. |
| `bali-zero-magazine` | Private editorial observatory for Bali Zero, built on |
| `cell` |  |
| `cell-observatory-collector` | Pro-local Python service that listens to `cell_pulse_observed` PG channel, |
| `crm-cell` | Sprint 3 W2 — light cell wrapping the existing CRM modules |
| `evaluator` | Security and quality evaluation tools for the Nuzantara RAG system. |
| `graph-engine` | Graph processing engine for Knowledge Graph operations. |
| `kb` |  |
| `kbli-navigator` | > **PRODUCTION = `apps/mouth`** → https://balizero.com/kbli (`/kbli-navigator` 301s there). |
| `mata-garuda` | > Intelligence Super Hub — OSINT blindato, CLI-only, Lamarckian meta-agent |
| `mouth` | > **The face of Nuzantara** - A Next.js 16 + React 19 frontend for the Nuzantara AI ecosystem |
| `nlm-bridge` |  |
| `nuz-status-mac` | Native macOS control surface for Nuzantara operational health. |
| `nuzantara-lex` | > Second body of the organism. "Avvocato Totale" — the Indonesian labor-law |
| `nuzantara-mcp` | Primary MCP server for Zantara AI assistant. FastMCP, stdio transport. |
| `nuzantara-mcp-advanced` | Advanced MCP (Model Context Protocol) server for Nuzantara operations, deployment, and diagnostics. |
| `nuzantara-mcp-browser` | FastMCP server exposing Nuzantara's stealth Playwright browser manager |
| `openclaw-hgt-coordinator` |  |
| `organism` | See `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` for full design. |
| `osint-nexus-ui` |  |
| `remediator` |  |
| `team-agent` |  |
| `wa-dashboard` | Local-only Next.js 16 app for the Bali Zero team WhatsApp inbox. |
| `wa-dashboard-m1` | Replica del pattern M1 single-page (`~/bin/wa-viewer/`) puntata al DB di produzione |
| `wa-meta-inbox` | Desktop-local UI for the **BALI ZERO WhatsApp Business (Meta API)** number |
| `wa-mirror` | **Status**: capture bridge scaffold + read-only CRM API v1 (2026-05-17) |
| `web` | Vercel subdomain satellite app. AI chat interface (rewrites / to /chat). |
| `wr2-control-app` | A native **macOS 27 (Tahoe) SwiftUI** app to launch and monitor the Bali Zero **WR2 carousel |
| `zantara-media` | Mata Garuda Layer 4.5 — Asset indexer + multi-channel curator. |
<!-- DOCSYNC:LIVING_ORGANS_END -->

### Workflow riusabili (`infra/workflows/`)

<!-- DOCSYNC:WORKFLOWS_INDEX_START -->
| File | Name | Description |
| ---- | ---- | ----------- |
| `infra/workflows/kbli-batch-a-lot.js` | kbli-batch-a-lot | GARUDA-FILIERA Batch A calibration-enforced lot runner (D1 crosswalk proposal -> D5 blind refutation -> D2 self-confirming extraction) over evidence already pulled by dossier_pull.py, gated on membership and reporting m1-m4 control limits per lot |
| `infra/workflows/kbli-pilot-a1.js` | kbli-pilot-a1 | GARUDA-FILIERA per-code adjudication (D1 crosswalk proposal -> D5 blind refutation -> D2 self-confirming extraction) over evidence already pulled by dossier_pull.py |
| `infra/workflows/modus-bench.js` | modus-bench | Self-refinement sweep for the modus master loop: internal scars/memory × external frontier watch → adversarially verified, operator-gated amendment proposals |
| `infra/workflows/verify-template.js` | verify-template | Reusable generator≠grader workflow: gather N angles → adversarially verify each → synthesize survivors |
<!-- DOCSYNC:WORKFLOWS_INDEX_END -->

### Skill repo (`.claude/skills/`)

<!-- DOCSYNC:SKILLS_INDEX_START -->
| Skill | Description (truncated) |
| ----- | ----------------------- |
| `.claude/skills/agent-session-discipline/` | Use at session start when working on a feature/fix that involves code changes. Creates an isolated worktree via L1 broker (scripts/agent_start.py) to prevent... |
| `.claude/skills/bot/` | "Zantara WA bot corner — the live shared context for ALL work on the Zantara WhatsApp Meta bot (+62 821-3465-159): outbox/inbox pipeline, agentic RAG brain, ... |
| `.claude/skills/intake/` | "Intake corner — the live shared context for the document-intake organism (WhatsApp/Drive docs → OCR → classify → extract → route → attach-to-client). Load B... |
| `.claude/skills/karpathy-discipline/` | Use BEFORE any feature implementation, refactor, bug fix, or non-trivial code change. Applies 4 Karpathy principles to reduce common LLM coding mistakes (sil... |
| `.claude/skills/kbli-navigator/` | "KBLI Navigator corner — the live shared context AND the full plan-to-the-end for ALL KBLI corpus/product work (dataset, gold, KG, editorial, kbli pages on b... |
| `.claude/skills/modus/` | USE FOR EVERY non-trivial mandate — feature, fix, refactor, research, audit, ops, content — coding or not. The master operating loop of the organism: TRIAGE ... |
| `.claude/skills/reuse-first/` | Use BEFORE implementing/building/writing-from-scratch any non-trivial component (queue, OCR, adapter, entity-resolution, review-UI, scraper, parser, etc.). C... |
| `.claude/skills/skill-catalog/` | Use when a user request does NOT match any currently-loaded skill — BEFORE answering "I don't have a skill for that". The full Claude Code skill ecosystem (T... |
| `.claude/skills/sota-architecture-loop/` | Use BEFORE architecting code, designing a feature, or making a structural/architectural decision. Evidence-backed 8-step loop (frame → ground → reason → coun... |
| `.claude/skills/visaoracle/` | "Corner for Visa Oracle v2 — the immigration Decision Tree rebuild (Bali Zero flagship). Load FIRST on any Visa Oracle / visa funnel work. Holds live state, ... |
| `.claude/skills/workflow/` | Strategic multi-agent orchestration playbook — the Workflow tool wired to the full cross-family arsenal (Sonnet 5 implementers, Codex red-team, Gemini agy wi... |
| `.claude/skills/wr2/` | "WR2 corner — the live shared context for the War Room 2 editorial organism (intel → carousel → Instagram). Load BEFORE touching any WR2 script, the Control ... |
<!-- DOCSYNC:SKILLS_INDEX_END -->

### LaunchAgents — copertura documentale

<!-- DOCSYNC:AUTOMATION_COVERAGE_START -->
`127 plist tracked in infra/launchagents/ · 97 documented in automation_catalog.json + AUTOMATIONS_REFERENCE.md (76% coverage)`
<!-- DOCSYNC:AUTOMATION_COVERAGE_END -->

Runbook operativi: indice auto-generato in [docs/runbooks/README.md](docs/runbooks/README.md).

## Machine & env

- **Pro** (`nuzantara@Nuzantara`, M4 Pro 48GB): Dev primario + Server H24. Venv `.venv` in `apps/backend-rag/`.
- **Mini-Pro2** (`nuzantara@Mini-Pro2`, M4 Pro 24GB): Server H24, Ollama dedicato, cron pesanti.
- SSH: `ssh pro` / `ssh mini` (Tailscale `100.93.236.6` for Mini, `100.107.22.111` for Pro from Mini).
- Git sync: Pro↔Mini Tailscale sync. GitHub: only Pro→origin.
- **Air decommissioned 2026-05-05** — handed off to Ari/Bali Zero. Historical references in code/scripts are archaeology, NOT active.

## 5 Libri sacri — 5 funzioni cognitive

| Libro                             | Funzione                | Quando                                       |
| --------------------------------- | ----------------------- | -------------------------------------------- |
| **SYMBIOSIS.md**                  | Filosofia (il _perché_) | Prima di toccare qualunque cosa              |
| **VADEMECUM.md**                  | Procedura (il _come_)   | Quando costruisci X                          |
| **INDEX.md** (questo)             | Mappa (il _cosa/dove_)  | Quando cerchi X                              |
| **CLAUDE.md**                     | Context + golden rules  | Caricato automaticamente ogni sessione       |
| `.claude/rules/cicatrix-scars.md` | Memoria delle ferite    | Prima di modificare file che hanno cicatrici |

**Regola:** se una domanda non trova risposta in questi 5 libri + MOS (`mem query`) + NLM NB-14, c'è un gap — aggiorna il libro giusto.

## Aggiornamento

Questo file è **mantenuto manualmente**. Si aggiorna quando:

- Nasce/muore un'app (`apps/*/`)
- Un nuovo pattern di riferimento emerge
- Una sezione diventa obsoleta

Le metriche quantitative (router count, vector count, etc.) vivono tra marker `<!-- DOCSYNC:* -->` in `README.md` (più `docs/AI_ONBOARDING.md`, `docs/DOCS_INVENTORY.md`, ecc.) — NON più in CLAUDE.md, da cui i marker sono stati rimossi (F44) — e sono auto-sincronizzate da `scripts/docs_sync.py`.

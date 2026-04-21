# INDEX — L'Atlante dei Libri Sacri

> **Loaded first** in ogni sessione. Se il tuo bisogno non è qui, aggiorna questo file.
> **Ultima revisione manuale:** 2026-04-15

---

## Cosa cerchi?

| Bisogno                                       | Dove guardare                                                      | Come                                          |
| --------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------- |
| Perché fare X?                                | [SYMBIOSIS.md](SYMBIOSIS.md)                                       | Filosofia, "prima di toccare"                 |
| Come fare X?                                  | [VADEMECUM.md](VADEMECUM.md)                                       | Checklist operativa per ogni tipo di elemento |
| Dove vive X?                                  | Questa pagina, sezione "Organi" sotto                              | Mappa statica top-level                       |
| Metriche live (count routers/servizi/vector)? | [CLAUDE.md](CLAUDE.md) §Tech Stack                                 | Auto-sincronizzate via `docs_sync.py`         |
| Dettagli tecnici di un'app?                   | `apps/<nome>/README.md` o `apps/<nome>/CLAUDE.md`                  | File locali all'app                           |
| Quando X è stato fatto?                       | `git log` + MOS (`~/.claude/scripts/mem query "X"`)                | Git + memoria persistente                     |
| Policy AI dispatch / federazione?             | [docs/AI_DISPATCH_REFERENCE.md](docs/AI_DISPATCH_REFERENCE.md)     | Dispatch, fallback, timeout                   |
| Cicatrici / bug ricorrenti?                   | [.claude/rules/cicatrix-scars.md](.claude/rules/cicatrix-scars.md) | Trauma + antibody per file chiave             |

## Organi principali (top of mind)

### Biology framework

- **`packages/cell-core/`** — Framework biologico base (lifecycle, genome, pulse, homeostasis, safety, memory protocols). **BASE per tutti gli agenti viventi**. Maturation 5 fasi (embrione→anziano). Vedi `packages/cell-core/cell_core/__init__.py` per API pubblica.
- **`apps/mata-garuda/`** — Meta-agent Lamarckian 5-layer (Harvester → Kognitif → Nexus → Analista → Distribuzione). Usa cell-core. Sentinel cell + Sensors + Actors.
- **`apps/cell/`** — Organism cell implementation. PulseLoop istanziato. Telegram alerts, skill accumulation.

### Production workloads

- **`apps/backend-rag/`** — RAG backend (FastAPI, deploy Fly.io; count routers/services in CLAUDE.md §Tech Stack auto-sync). Prompt SSOT: `backend/prompts/zantara_core.py`. Include WR2 pipeline (`backend/services/{war_room,council,visual,canva_renderer,review,publisher}/`).
- **`apps/mouth/`** — Next.js frontend (Vercel). kita/my/prime.balizero.com.
- **`apps/bali-intel-scraper/`** — Intel pipeline daily 03:00 WITA (solo Pro, NOT Fly). Articoli MDX → GitHub → Vercel.
- **`apps/zantara-media/`** — Curator Agent GARUDA (Sprint 5.1 LIVE). Drive indexer + Qdrant `garuda_assets` + Postgres `garuda_index`.

### Intelligence

- **`apps/evaluator/`** — Core Guardian V3/V5 (auto-calibration), NLM deep research (10 pipelines NB-1..10).
- **`apps/federation/`** — A2A protocol multi-agent. Pro↔Air.
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
| Frontend deploy Vercel       | CLAUDE.md §10 (Frontend Deploy QA) + `mcp__claude-in-chrome__*`                   | Screenshot obbligatorio post-deploy                       |
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
- **every 5min** log-anomaly-detector, drive-poll (Air), sentinel
- **Dettagli completi:** `docs/AUTOMATIONS_REFERENCE.md` + `scripts/automation_catalog.json`

## Machine & env

- **Pro** (`nuzantara@Nuzantara`, M4 Pro 48GB): Dev + Server H24. Venv `.venv` in `apps/backend-rag/`.
- **Air** (`antonellosiano@Nuzantara-9`, M4 16GB): Server H24. Venv `venv` (non `.venv`).
- SSH: `ssh pro` / `ssh air` via mDNS.
- Git sync: post-commit hook Pro→Air auto-pull. GitHub: only Pro→origin.

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

Le metriche quantitative (router count, vector count, etc.) vivono invece in CLAUDE.md tra marker `<!-- DOCSYNC:* -->` e sono auto-sincronizzate da `scripts/docs_sync.py`.

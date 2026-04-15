# Libri Sacri Canonici — Sprint 5.1.5

**Status:** SUPERSEDED v1 (draft) — replaced by lean implementation 2026-04-15
**Date:** 2026-04-15
**Author:** Zero + Claude Opus 4.6
**Sprint:** 5.1.5 — precursore di Sprint 5.2 (Curator)
**Duration:** 1 settimana (non eseguito)

> **⚠️ Questa spec non è stata implementata.** Dopo federation review (5 modelli: Codex, DeepSeek, Claude, Gemini, Exa) sono emersi 20 critiche + 8 bug bloccanti. Il design è stato sostituito da un'implementazione **lean** (3-4 ore invece di 7 giorni), fatta direttamente nel repo senza nuova spec:
>
> - `INDEX.md` statico (<150 righe), discovery manuale
> - `scripts/docs_sync.py` implementato davvero (pattern DOCSYNC già specificato in `docs/DOCSYNC_SENTINEL.md` ma senza script fino ad ora)
> - Marker `LIVING_ORGANS` aggiunto a `CLAUDE.md`, auto-sincronizzato
> - Nessun nuovo cron, nessun post-commit hook (violavano "minimo vitale" VADEMECUM)
> - No FISIOLOGIA, no STORIA-CLINICA (deferred — non ne abbiamo ancora bisogno)
>
> **Questa spec resta come memoria storica** dell'analisi federation review. Le 20 critiche + 8 bug sono salvati in MOS (importance 9-10). Commit lean: vedi git log dopo `eea5aef28`.

---

## 0. Problema

L'organismo Nuzantara ha già 2 libri sacri (SYMBIOSIS.md, VADEMECUM.md), ma **la conoscenza dell'organismo non è discoverable in modo garantito**.

Evidenza concreta: durante brainstorm Sprint 5.2 del 2026-04-15, Claude ha "scoperto" `packages/cell-core/` (framework biologico completo con 12 moduli, 5 fasi lifecycle, Genome, PulseLoop) **a metà conversazione**, nonostante sia pacchetto chiave dell'organismo. Questo è sintomo di un **fallimento epistemologico strutturale**:

- `CLAUDE.md` elenca 20 apps ma non menziona `packages/cell-core/`
- `SYMBIOSIS.md` lo cita ma solo in un frammento (§L0 Cellular) non sempre caricato
- `VADEMECUM.md §2` lo spiega ma richiede di saperlo già cercare
- **Nessun indice canonico** di "cosa-c'è-e-dove"

Conseguenza: ogni sessione parte da zero → regressione perpetua → riscoperte tardive → decisioni sub-ottimali.

---

## 1. Obiettivo

Creare **3 nuovi libri sacri + 1 meta-atlante** che risolvano il problema alla radice, con meccanismi di **auto-aggiornamento** per evitare staleness.

### Libri da creare

| Nome                  | Ruolo                                                                    | Aggiornamento           | Target size                     |
| --------------------- | ------------------------------------------------------------------------ | ----------------------- | ------------------------------- |
| **INDEX.md**          | Meta-atlante: "dove guardo per X?"                                       | Manuale, ~ogni 2 sprint | <200 righe                      |
| **ANATOMIA.md**       | "Il cosa e dove" — mappa statica degli organi, tessuti, nervi            | Auto-scan settimanale   | <800 righe                      |
| **FISIOLOGIA.md**     | "Il come funzionano insieme" — contratti inter-organo, flussi principali | Manual + auto cross-ref | <600 righe                      |
| **STORIA-CLINICA.md** | "Il cosa è successo" — eventi vitali diacronici                          | Auto-append da hook     | rolling 12 mesi, archivi yearly |

### Files esistenti (invariati o con modifiche minori)

| File           | Ruolo attuale                 | Modifica in Sprint 5.1.5                                                                 |
| -------------- | ----------------------------- | ---------------------------------------------------------------------------------------- |
| `SYMBIOSIS.md` | Il perché (principi)          | Nessuna modifica                                                                         |
| `VADEMECUM.md` | Il come (checklist operativa) | Aggiunta cross-link a ANATOMIA quando menziona cell-core, Mata Garuda, War Room, Curator |
| `CLAUDE.md`    | Context setup + golden rules  | Aggiunto blocco top: "Read INDEX.md first" + lista top 10 organi                         |

---

## 2. Architettura

### 2.1 Struttura file

```
/Users/nuzantara/Desktop/nuzantara/
├── SYMBIOSIS.md              (esistente, invariato)
├── VADEMECUM.md              (esistente, micro-modifiche cross-link)
├── CLAUDE.md                 (esistente, top block aggiornato)
├── INDEX.md                  (NEW)
├── ANATOMIA.md               (NEW, auto-scan sections)
├── FISIOLOGIA.md             (NEW, manual + auto cross-ref)
├── STORIA-CLINICA.md         (NEW, auto-append from hooks)
└── scripts/
    ├── generate_anatomia.py  (NEW — weekly cron)
    ├── check_sacred_books_links.sh  (NEW — weekly cron)
    └── append_storia_clinica.py     (NEW — hook helper)
```

### 2.2 Relazioni e dipendenze

```
CLAUDE.md (always loaded)
    ↓
INDEX.md ← top-level atlas, loaded first
    ↓
    ├─→ SYMBIOSIS.md (philosophy, when-to-stop)
    ├─→ VADEMECUM.md (checklist, when-building)
    ├─→ ANATOMIA.md (map, when-finding-organ)
    ├─→ FISIOLOGIA.md (contracts, when-organs-interact)
    └─→ STORIA-CLINICA.md (timeline, when-asking-history)
```

### 2.3 Auto-update mechanisms

| Meccanismo                    | Trigger                                               | Target                              |
| ----------------------------- | ----------------------------------------------------- | ----------------------------------- |
| `generate_anatomia.py`        | Cron settimanale (Sun 05:30 WITA)                     | ANATOMIA.md sezioni `<!-- AUTO -->` |
| `append_storia_clinica.py`    | Git post-commit hook (file in `apps/*`, `packages/*`) | STORIA-CLINICA.md append            |
| `check_sacred_books_links.sh` | Cron settimanale (Sun 06:00 WITA)                     | Broken links → Telegram             |

---

## 3. Contenuti dettagliati

### 3.1 INDEX.md (<200 righe)

Struttura:

```markdown
# INDEX — L'Atlante dei Libri Sacri

> **Loaded first** in ogni sessione. Se il tuo bisogno non è qui, aggiornalo.

## Cosa cerchi?

| Bisogno                      | Libro                   | Sezione                |
| ---------------------------- | ----------------------- | ---------------------- |
| Perché faccio X?             | SYMBIOSIS.md            | "Prima di toccare"     |
| Come fare X?                 | VADEMECUM.md            | §N corrispondente      |
| Dove vive X?                 | ANATOMIA.md             | Organi / Tessuti       |
| Come parla X con Y?          | FISIOLOGIA.md           | Contratti inter-organo |
| Quando X è stato fatto?      | STORIA-CLINICA.md       | Timeline               |
| Quale sessione ha toccato X? | `mem query` / NLM NB-14 | —                      |

## Organi principali (top-of-mind)

- `packages/cell-core/` — framework biologico base (lifecycle, genome, pulse, homeostasis)
- `apps/mata-garuda/` — meta-agent Lamarckian 5-layer
- `apps/cell/` — organism cell implementation (uses cell-core)
- `apps/war-room/` — carosello marketing pipeline
- `apps/zantara-media/` — Curator Agent (Sprint 5.1 GARUDA indexer completato)
- `apps/bali-intel-scraper/` — intel pipeline daily
- `apps/backend-rag/` — RAG backend (90 routers, 253 services)
- `apps/evaluator/` — Core Guardian + NLM deep research
- `apps/federation/` — A2A protocol multi-agent

## Se stai per...

| Azione                 | Leggi prima                                                 |
| ---------------------- | ----------------------------------------------------------- |
| Scrivere codice nuovo  | SYMBIOSIS §"Prima di toccare" → VADEMECUM §corrispondente   |
| Creare cron/automation | VADEMECUM §1 + verifica `automation_catalog.json`           |
| Creare agente          | VADEMECUM §2 + riusa `cell-core` (vedi ANATOMIA §cell-core) |
| Creare router FastAPI  | VADEMECUM §3                                                |
| Deploy production      | VADEMECUM §Pre-Deploy + SYMBIOSIS §"Rispetta il passato"    |
| Federation dispatch    | `superpowers:federation-dispatch` skill                     |
| Fixare bug             | `superpowers:systematic-debugging` skill                    |

## 5 Libri, 5 Funzioni Cognitive

1. **SYMBIOSIS** — Filosofia: _come pensare prima di fare_
2. **VADEMECUM** — Procedura: _checklist operativa_
3. **ANATOMIA** — Mappa: _cosa esiste e dove_
4. **FISIOLOGIA** — Fisica: _come gli organi comunicano_
5. **STORIA-CLINICA** — Memoria: _cosa è successo e perché_

**Regola d'oro:** se una domanda non trova risposta in questi 5 libri + MOS + NLM NB-14, c'è un gap — aggiorna il libro corretto.

---

**Last updated:** <!-- AUTO: YYYY-MM-DD -->
**Broken links:** <!-- AUTO: <N> -->
```

### 3.2 ANATOMIA.md (<800 righe)

Struttura:

```markdown
# ANATOMIA — Mappa degli Organi, Tessuti, Nervi

> Tutto ciò che vive nell'organismo Nuzantara, organizzato per funzione.

## Sezioni

1. Organi (cell-core modules, agents, services)
2. Tessuti (laghi di dati: Qdrant, Postgres, filesystem)
3. Sistema nervoso (event bus, Redis streams, A2A, MCP)
4. Sistema linfatico (cron, scheduled jobs, heartbeats)
5. Tiroide (config, env vars, secrets inventory)
6. Indice onnisciente (per ogni organo: file, test, classe, deps, consumer, fase)

---

## 1. Organi

### 1.1 cell-core (framework base) ⭐ FONDAMENTALE

**Location:** `packages/cell-core/`
**Scope:** Biological lifecycle engine — base per tutti gli agenti viventi
**Phase:** adulto (API stabile, test presenti)

**Moduli esposti (`cell_core/__init__.py`):**
| Modulo | Classi principali | Ruolo |
|--------|-------------------|-------|
| `lifecycle.py` | `Maturation` | Gating fasi embrione→anziano (5 threshold) |
| `pulse.py` | `PulseLoop` | Runner sense→think→act→reflect→dream→mature |
| `genome.py` | `Genome` | DNA record_skill, inherit_genome, silence_skill |
| `homeostasis.py` | `HomeostaticController`, `TrendDetector` | Stress/energy/arousal EMA |
| `safety.py` | `SafetyGate`, `DNAInterpreter` | DNA integrity + kill switches |
| `identity.py` | `SelfModel`, `SelfModelManager` | Persistence across restarts |
| `memory_sqlite.py` | (implementations) | STM/LTM/Episodic stores |
| `protocols.py` | `Sensor`, `Thinker`, `Actor`, `*Store` | Contratti da implementare per cellule custom |
| `reasoner.py` | `ReasonerFramework`, `TierConfig` | Ragionamento tiered |
| `types.py` | `Phase`, `Episode`, `Proposal`, etc. | Tipi condivisi |

**Dipendenze runtime:** `dependencies = []` (core minimal), optional `asyncpg` + `redis`

**Usato da:**

- `apps/mata-garuda/` (sentinel_cell.py)
- `apps/cell/` (PulseLoop istanziato)
- Nuove cellule: **MUST use cell-core**, non reimplementare

**VADEMECUM:** vedi §2 "Nuovo agente cell-core"

---

### 1.2 Mata Garuda (meta-agent)

**Location:** `apps/mata-garuda/`
**Scope:** Intelligence Super Hub, 5 layer (Harvester → Kognitif → Nexus → Analista → Distribuzione) + Lamarckian meta-agent
**Phase:** giovane (Sprint 1-2 done, Sprint 3 Lamarckian loop in design)

**Cellule attive:**

- `sentinel_cell.py` — daily pulse, Telegram alerts
- `sensors/` — arxiv, github, rss, youtube
- `actors/` — sentinel_actor
- `tools/` — nlm_tools, knowledge_tools, stream_tools, etc.

**GENOME evolution:** mutazioni richiedono review Zero (Sprint 3+)

---

### 1.3 Curator Agent (zantara-media)

**Location:** `apps/zantara-media/`
**Scope:** GARUDA Drive folder asset indexer (Sprint 5.1 completo, LIVE production)
**Phase:** embrione (Layer 4.5 Mata Garuda)

**Componenti live:**

- `zantara_media/indexer/*.py` — Drive client, handlers (PDF/image/video/audio), embedder, writers, pipeline, orchestrator
- `zantara_media/security/dlp.py` — PII detection (3-layer: filename/regex/LLM)
- `zantara_media/maintenance/gc.py` — tombstone garbage collector
- `zantara_media/cli/garuda_{indexer,bootstrap,gc}.py` — CLI entry points
- `zantara_media/alerts.py` — Telegram CRITICAL alerts

**Cron:**

- `garuda-indexer` daily 04:30 WITA (20:30 UTC)
- `garuda-gc` Sunday 05:00 WITA (Sun 21:00 UTC)

---

### 1.4 War Room (marketing pipeline)

**Location:** `apps/war-room/`
**Scope:** Multi-source intelligence → Instagram carousel in 10-15 min
**Phase:** adulto (production-live, Canva MCP manual apply)

**Pipeline (8 agents sequenziali):**

1. `00_topic_selector.py` (DeepSeek + xAI Grok + NLM NB-7)
2. `09/10/11_researcher.py` (Exa + xAI + NLM)
3. `015_qwen_preprocessor.py` (DeepSeek R1:32b local)
4. `03_gemini_strategist.py` → 3 concept
5. `04_claude_director.py` → copy + slides JSON
6. `05_image_brainstorm.py` (Fireworks Flux.1 Dev)
7. `06_canva_builder.py` → canva_pending.json
8. `07_delivery.sh` → Telegram Zero (IT) + Damar (ID)

**Output:** `canva_pending.json` applicato manualmente via Claude Desktop MCP Canva

---

### 1.5 Backend RAG

**Location:** `apps/backend-rag/`
**Scope:** FastAPI RAG con 90 routers, 253 services, 419 test files
**Phase:** adulto (production Fly.io, kita.balizero.com)

**Struttura critica:**

- `backend/app/routers/` — 88 routers (NON `backend/routers/`)
- `backend/services/` — 244 services core logic
- `backend/app/services/` — 9 services app-level (CRM, auth, metrics)
- `backend/app/dependencies.py` — **SPOF importato da ogni router**
- `backend/prompts/zantara_core.py` — Prompt SSOT (OFF-LIMITS diretto)

### 1.6-1.N (altri 15+ organi — auto-generate)

<!-- AUTO-GENERATED BY scripts/generate_anatomia.py — DO NOT EDIT BELOW THIS LINE -->

[... lista automatica di tutti i `apps/*/` con overview da README.md ...]

<!-- END AUTO-GENERATED -->

---

## 2. Tessuti (Data Lakes)

### 2.1 Qdrant (vector search)

**Host:** Qdrant Cloud `5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333`

<!-- AUTO: live query `GET /collections` -->

| Collection                      | Size                  | Scope               | Consumer                        |
| ------------------------------- | --------------------- | ------------------- | ------------------------------- |
| `balizero_news`                 | ~2831                 | Intel articles      | blog, War Room                  |
| `garuda_assets`                 | 0 (new)               | GARUDA Drive assets | Curator (sprint 5.2+)           |
| `bali_zero_pricing_hybrid`      | ?                     | Pricing KB          | RAG                             |
| `visa_oracle`                   | ?                     | Visa domain         | RAG                             |
| `tax_genius_hybrid`             | ?                     | Tax domain          | RAG                             |
| `kbli_2025_final_hybrid`        | ?                     | KBLI codes          | RAG /kbli                       |
| `legal_unified_hybrid_hybrid`   | 30065 **unprocessed** | Legal regs          | ⚠️ lago profondo senza consumer |
| `immigration_circulars`         | ?                     | Imigrasi            | RAG                             |
| `training_conversations_hybrid` | ?                     | Dialog logs         | Conversation trainer            |
| `intel_authoritative_sources`   | ?                     | T1 sources          | —                               |

<!-- END AUTO -->

### 2.2 Postgres (relational)

**Host:** Fly `nuzantara-postgres.flycast:5432`, DB `nuzantara_rag`

<!-- AUTO: live introspection -->

Tabelle core:

- `articles` + `post_publish_queue` (intel scraper)
- `garuda_index`, `garuda_indexer_state`, `publication_history`, `publication_assets` (Curator)
- `kg_nodes`, `kg_edges` + `*_staging` (Knowledge Graph 108K nodi)
- `google_drive_tokens` (OAuth)
- `system_settings` (Drive page_token)
- `crm_clients`, `crm_practices`, `crm_audit_log` (CRM)
- `conversations`, `messages` (chat history)
- `routing_stats`, `failed_queries` (gap detection)
- `lkpm_receipts` (LKPM tracking Q1 2026)
- ... [auto-list]
<!-- END AUTO -->

### 2.3 Filesystem (state, output)

- `~/.agent/decisions/` — agent state, DLQ, escalation
- `shared/escalations_pro.jsonl`, `shared/escalations_air.jsonl` — federation bus
- `apps/war-room/output/` — canva_pending, slides, images
- `apps/evaluator/nlm_deep_research/*_state.json` — 9+ NB pipelines state

### 2.4 GitHub (published content)

- `Balizero1987/Teman2` — intel MDX → Vercel auto-deploy (kita.balizero.com)

---

## 3. Sistema Nervoso

### 3.1 Event Bus

**Module:** `apps/backend-rag/backend/services/events/event_bus.py`
**Mechanism:** Hybrid PostgreSQL `LISTEN/NOTIFY` (cross-process) + in-process pub/sub (zero-latency app events)
**Channels:** cross-chain context, compliance_alert, eventbus_handler

### 3.2 Redis Streams

**Host:** local Redis (Pro), remote Redis (Fly)
**Streams noti:**

- `garuda:raw` — Mata Garuda intelligence ingestion
- `nexus:gaps` — 552+ entries KG gap detection
- `bridge:inbound`, `bridge:outbound` — Pro↔Fly bridge

### 3.3 A2A Protocol (Federation)

**Module:** `apps/federation/a2a_service.py`
**Endpoint:** FastAPI JSON-RPC su pro.local:9000 (⚠️ pianificato, non attivo)
**Heartbeat:** `apps/federation/launcher.py` ping 30s, kill+restart dopo 3 failures
**Agent Cards:** `agents/*/agent_card.json` generati da `federation_capability_table.py`

### 3.4 MCP (Model Context Protocol)

**MCP servers connessi (claude-in-chrome, claude.ai, OpenClaw):**

- Canva (mcp.canva.com) — carousel builder
- Google Drive (api.anthropic.com/mcp/gdrive)
- GA4, GSC, OCR, 115+ NuzMCP tools
- Filesystem, brave-search, context7, sequential-thinking, memory

---

## 4. Sistema Linfatico (Cron)

<!-- AUTO: crontab -l parsed -->

### Tier 1: Producers core

- bali-intel-scraper — 03:00 daily
- War Room — triggered
- garuda-indexer — 04:30 daily
- garuda-gc — Sunday 05:00

### Tier 2: NLM Deep Research (10 pipelines)

- NB-1..10 refresh — 01:10-22:00 WITA
- gap_scanner layer A/B + remediate
- freshness_monitor daily 22:00
- multimodal / yt_monitor / peraturan_ingestion

### Tier 3: Intelligence radar

- intel-radar hourly
- intel-feed-processor \*/30min
- imigrasi/pajak/oss-monitor
- bi-exchange-rate daily
- fact-checker \*/1h

### Tier 4: System health / meta

- Core Guardian \*/3h
- system-doctor, daily-ops, compliance-ops, tech-orchestrator
- seo-guardian, client-health-monitor
- log-anomaly-detector \*/5min
- MOS maintenance, sync-damar, sync-ruslana

**Totale:** ~50+ cron jobs. Dettagli: `scripts/automation_catalog.json` + `docs/AUTOMATIONS_REFERENCE.md`.

<!-- END AUTO -->

---

## 5. Tiroide (Config, Env, Secrets)

### 5.1 Env Vars required

`OPENAI_API_KEY`, `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `REDIS_URL`, `JWT_SECRET`, `FLY_API_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`, `DEEPSEEK_API_KEY` (in war-room/.env)

### 5.2 Locations

- Primary: `apps/backend-rag/.env`
- Complementari: `apps/war-room/.env`, `apps/bali-intel-scraper/.env`, `apps/cell/.env`
- Secrets Fly: `fly secrets list -a nuzantara-rag`

---

## 6. Indice Onnisciente (per ogni organo)

<!-- AUTO-GENERATED — scan apps/*/pyproject.toml + README.md overview -->

[Tabella generata con: nome, path, pyproject version, primi 200 char README, test count, last commit touched]

<!-- END AUTO -->

---

**Last updated:** <!-- AUTO -->
**Generated by:** `scripts/generate_anatomia.py` (Sun 05:30 WITA)
```

### 3.3 FISIOLOGIA.md (<600 righe)

Struttura:

````markdown
# FISIOLOGIA — Come gli Organi Comunicano

> Contratti inter-organo, flussi principali, protocolli di riproduzione e morte.

## Sezioni

1. Regola delle 2 chiamate (no god-object)
2. Contratti inter-organo canonici (schemas Pydantic)
3. Flussi principali (6 flussi chiave)
4. Protocolli di riproduzione (fork cellula, inherit_genome)
5. Protocolli di morte (senescence, archiviazione, zombie)
6. Homeostasi globale

---

## 1. Regola delle 2 chiamate

Ogni organo può chiamare **direttamente max 2 altri organi**. Per catene più lunghe → orchestratore (es. `federation_orchestrator.py`).

**Violazione:** >5 call chain di 3+/giorno → organo entra in "modalità osservazione" 1h.

**Perché:** evitare god-object. Un organo che chiama N altri direttamente diventa bottleneck cognitivo + SPOF.

---

## 2. Contratti inter-organo (Pydantic schemas)

### Curator ↔ Experience Library

```python
class ExperienceQuery(BaseModel):
    trajectory_type: Literal["success", "failure", "partial"]
    skill_id: Optional[str] = None
    recency_days: int = 30
    min_confidence: float = 0.15  # RAG ABSTAIN threshold

class ExperienceResponse(BaseModel):
    trajectories: List[Dict]
    statistical_summary: Dict[str, float]
    recommendation_hash: str  # Track se Curator ignora
```
````

### Curator ↔ Skill Registry (Genome)

```python
class SkillLookup(BaseModel):
    pattern: str  # task signature
    min_confidence: float = 0.7
    scope: Literal["Project", "Personal"] = "Project"

class SkillResponse(BaseModel):
    skills: List[{id, procedure, confidence, uses, last_used}]
    suggested_new: Optional[str]  # se nessun match, LLM propone nuovo
```

### Critic ↔ Anything

```python
class CriticRequest(BaseModel):
    output: Any  # da valutare
    context: Dict
    threshold: float = 0.6

class CriticResponse(BaseModel):
    verdict: Literal["accept", "reject", "resubmit"]
    confidence: float
    reason: str
```

---

## 3. Flussi principali

### 3.1 Input utente → RAG → risposta

```
User message
  → channel adapter (TG/IG/WA/Web)
  → RAG orchestrator (backend/services/rag/agentic/)
  → intent classifier + tool selection
  → retrieval (Qdrant + KG)
  → LLM response generation
  → evidence_scoring (0.15/0.60 thresholds)
  → channel output
  → post: _reflect_and_save + KG auto_expansion (fire-and-forget)
```

### 3.2 Cron producer → consumer loop

```
Cron scheduled (es. intel-scraper 03:00)
  → producer script (scan, enrich)
  → write to lake (Qdrant + Postgres + GitHub)
  → (mancante: event Redis su nuovo record significativo)
  → (mancante: downstream consumer notify)
```

### 3.3 Fallimento → riflessione → skill

```
Agent action fails
  → log structured failure
  → post-run reflection (claude CLI JSON output)
  → store in SQLite KB (type='reflection')
  → if confidence > 0.8: genome.record_skill() as 'scar'
  → next iteration: inject reflection in prompt context
```

### 3.4 Drive change → indexing → available for Curator

```
Drive file change
  → drive-poll cron */5min (Air)
  → page_token in system_settings
  → /api/intel/scraper/submit (authenticated)
  → garuda-indexer 04:30 WITA
  → Qdrant garuda_assets + Postgres garuda_index
  → (Curator: future) consume for enrichment
```

### 3.5 War Room pipeline

```
Intel pre-seed → 8 agents sequenziali → canva_pending.json
  → Telegram alert manual apply
  → Claude Desktop MCP Canva
  → published carousel
  → (mancante: engagement feedback loop)
```

### 3.6 Agent health → sentinel → auto-repair

```
Every 5min: sentinel monitor 31 jobs
  → classify failure (regex + Claude CLI)
  → retry OR dispatch Aider/Codex fix
  → escalate to Telegram after 3 consecutive failures
  → DLQ after max retries
```

---

## 4. Protocolli di Riproduzione

### Fork cellula

```python
# Parent cell triggers fork
child_id = parent.fork(config=ChildConfig(...))
inherited_skills = parent.genome.inherit_genome(
    parent_cell=parent.id,
    min_confidence=0.7,
    scope='Project'  # germline
)
child.genome.bulk_insert(inherited_skills)
```

### Scope rules

- `scope='Project'` = germline (trasferibile a figlie)
- `scope='Personal'` = somatic (solo cellula originale)

---

## 5. Protocolli di Morte

### Curator inattivo 90 giorni

1. Test 100 query random
2. success_rate <40% → archivia immediata
3. 40-60% → downgrade a embrione + riaddestra 50 casi
4. > 60% → mantieni, -70% CPU priority

### Skill success_rate <0.5 per 30 giorni

1. Cerca skill simili (embedding cosine >0.85 con success >0.7)
2. Match → auto-merge proposal (review umana)
3. No match → isola (non in produzione, accessibile per analisi)

### Morte definitiva

- success_rate <0.15 (ABSTAIN threshold) per 60 giorni
- - 0 access a Experience Library
- → archivia

---

## 6. Homeostasi Globale

**cell_core.HomeostaticController** gestisce stato singolo organo:

- `stress` (0-1, EMA)
- `energy` (0-1, recovery 0.02/tick)
- `arousal` (0-1, decay 0.03/tick)

**Organism-wide homeostasis (future):** aggregator di stress di N cellule → se >50% cellule stressed → Telegram alert + pause non-critical operations.

**Circadian rhythm:** awake → drowsy → asleep window configurato per cellula (sleep_hours in CellConfig).

---

**Last updated:** 2026-04-15
**Manual update required when:** nuovo contratto inter-organo, nuovo flusso principale, cambio protocollo morte.

````

### 3.4 STORIA-CLINICA.md (rolling 12 mesi)

Struttura (auto-append + manual entry):

```markdown
# STORIA CLINICA — Eventi Vitali Diacronici

> Append-only timeline. Nascite, morti, mutazioni, cicatrici, maturazioni.
> Rolling 12 mesi. Archivi annuali in `docs/history/storia-clinica-YYYY.md`.

---

## 2026-04

### 2026-04-15
- **[mutazione]** Sprint 5.1.5 Libri Sacri approvato. INDEX + ANATOMIA + FISIOLOGIA + STORIA-CLINICA generati (commit: TBD)
- **[cicatrix]** Federation dispatch ai-dispatch.sh: bugs noti — codex-review wrapper passa --sandbox (fix: usare codex exec), gemini explore 180s timeout (fix: usare search), DeepSeek SIGTERM 143 con seatbelt (fix: timeout esteso)
- **[mutazione]** Skill `federation-dispatch.md` creata in `~/.claude/skills/` — no-skip rule quando user ordina dispatch
- **[fact]** Qdrant Cloud production collection `garuda_assets` creata (1536d Cosine + 6 payload indexes)
- **[fact]** Fly Postgres production migration 109_garuda_curator.sql applicata
- **[nascita]** Cron GARUDA indexer + GC installati (crontab Pro)
- **[fact]** First run garuda-indexer PRODUCTION: token 4908555 → 4908559 → 4908563, 0 errors, 2 tombstone processati
- **[bug fix]** drive_client.py OAuth schema allineato a google_drive_tokens reale (commit 0c87cb093)
- **[bug fix]** Qdrant point ID must be UUID — drive_file_id_to_point_id uuid5 mapping (commit d3171d2c0)
- **[pushato]** 35 commit origin/main (commit 4ac4d0e61 head) — Sprint 5.1 COMPLETO pubblico

### 2026-04-14
- **[nascita]** Sprint 5.1 Curator Agent GARUDA completo (commit ffda3a283 Day 1, 7f7149b63 Day 2-6, 337f684bc Day 7)
- **[mutazione]** Spec Curator v2 scritto dopo red team Gemini + Codex (14 fixes)
- **[fact]** GARUDA Drive folder creata (root: 1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN + 7 subfolders)

<!-- AUTO-APPENDED entries go below -->

---

## Legenda

- **[nascita]** — nuovo organo, file, endpoint, collezione, cron
- **[morte]** — archiviazione, rimozione, deprecation
- **[mutazione]** — cambio significativo (API, schema, behavior)
- **[cicatrix]** — incidente critico con lezione appresa
- **[maturazione]** — fase lifecycle embrione→neonato→...
- **[fact]** — fatto verificato importante (config, credenziali, versione)
- **[bug fix]** — fix con commit reference
````

---

## 4. Implementation

### 4.1 `scripts/generate_anatomia.py`

```python
"""Auto-generate ANATOMIA.md sections marked with <!-- AUTO -->.

Scans:
  - packages/*/pyproject.toml → nome, version, description
  - apps/*/pyproject.toml + README.md (first ## Overview) → apps catalog
  - Qdrant live (get_collections) → tessuti vettoriali
  - Postgres introspection → tessuti relazionali
  - crontab -l → sistema linfatico parsed by tier
  - automation_catalog.json → sovrapporre descrizioni

Update only sections between <!-- AUTO-GENERATED --> and <!-- END AUTO --> markers.
Preserve all manual content above/below markers.

Runs:
  Cron: 30 5 * * 0 (Sun 05:30 WITA = Sat 21:30 UTC)
  Manual: python scripts/generate_anatomia.py
"""
```

### 4.2 `scripts/append_storia_clinica.py`

```python
"""Append entry to STORIA-CLINICA.md.

Called from:
  - git post-commit hook (via `scripts/git-hooks/post-commit-storia.sh`)
  - manually: python scripts/append_storia_clinica.py --type nascita --msg "..."
  - from other scripts (e.g., escalation handlers)

Entry format:
  ### YYYY-MM-DD
  - **[type]** message (commit: hash if git event)
"""
```

### 4.3 `scripts/check_sacred_books_links.sh`

```bash
#!/bin/bash
# Check broken links in libri sacri
# Cron: 0 6 * * 0 (Sun 06:00 WITA = Sat 22:00 UTC)

FILES="SYMBIOSIS.md VADEMECUM.md INDEX.md ANATOMIA.md FISIOLOGIA.md STORIA-CLINICA.md"
BROKEN=()
for f in $FILES; do
  # Extract markdown links + file paths + anchor refs
  # Verify each resolves (file exists, anchor exists, URL 200)
  ...
done

if [ ${#BROKEN[@]} -gt 0 ]; then
  # Telegram alert
  ...
fi
```

### 4.4 Modifiche a CLAUDE.md

Aggiungi in cima (dopo i 2 riferimenti esistenti a SYMBIOSIS/VADEMECUM):

```markdown
> **Read `INDEX.md` first.** It's the atlas — tells you which sacred book answers your need.
> **ANATOMIA.md** = map of all organs. **FISIOLOGIA.md** = how they talk. **STORIA-CLINICA.md** = what happened.
```

### 4.5 Git hooks

`.git/hooks/post-commit` (or template in `scripts/git-hooks/`):

```bash
#!/bin/bash
# Auto-append to STORIA-CLINICA if commit touches significant files
CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD)
if echo "$CHANGED" | grep -qE "^(apps/[^/]+/__init__|packages/[^/]+/__init__|scripts/openclaw-cron/|migrations_v2/.*\.sql)"; then
    MSG=$(git log -1 --pretty=%s)
    HASH=$(git rev-parse --short HEAD)
    python scripts/append_storia_clinica.py --type mutazione --msg "$MSG (commit: $HASH)"
fi
```

---

## 5. Build Plan (7 giorni)

### Day 1 — INDEX.md + CLAUDE.md top block

- Scrivi `INDEX.md` (200 righe, statico)
- Modifica `CLAUDE.md` aggiungendo 5 righe top-level pointer
- Cross-link test: ogni riferimento risolve

### Day 2 — ANATOMIA.md (static sections + skeletons AUTO)

- Scrivi tutte le sezioni "Organi" manuali (cell-core, mata-garuda, curator, war-room, backend-rag, evaluator, federation, cell, bali-intel-scraper)
- Scheletri `<!-- AUTO-GENERATED -->` delle sezioni tessuti/linfatico
- Prime bozze testuali sezione tiroide

### Day 3 — `generate_anatomia.py` + prima run

- Implementa script (scan apps, packages, crontab, Qdrant live, Postgres live)
- Prima esecuzione → popolate sezioni AUTO
- Test: diff non banale ma stabile

### Day 4 — FISIOLOGIA.md

- Scrivi tutti i contratti inter-organo (Pydantic schemas inline)
- 6 flussi principali
- Protocolli riproduzione + morte
- Homeostasi globale

### Day 5 — STORIA-CLINICA.md + hook

- Scrivi scheletro + backfill ultimi 30 giorni da `git log` + MOS memory importance>=8
- Implementa `append_storia_clinica.py`
- Installa post-commit hook
- Test: commit touch dummy → verifica append

### Day 6 — `check_sacred_books_links.sh` + cron

- Implementa link checker
- Installa cron Sun 06:00 + Sun 05:30 WITA
- Test: rompi link temporaneamente → verifica alert Telegram

### Day 7 — Arricchimento federation + review multi-modello

- Exa deep research (quali pattern documentali organici esistono in sistemi simili?)
- xAI Grok (reality check: useful or cosmetic?)
- NLM Deep Research (arricchimento con best practice Anthropic / Microsoft / Google org-docs)
- Review cycle:
  - Claude CLI Opus 4.6 max effort → strutturale
  - Codex 5.4 xhigh → tecnico (scripts, hooks, cron safety)
  - Gemini 3.1 Pro → consistency 1M ctx cross-file
  - DeepSeek R1 → critico pattern holes
- Consolida feedback → revisione finale
- Commit + push

---

## 6. Deliverables

Al termine Sprint 5.1.5:

- [ ] `INDEX.md` live, cross-link testati
- [ ] `ANATOMIA.md` con sezioni statiche + AUTO popolate
- [ ] `FISIOLOGIA.md` con 6+ contratti + 6 flussi
- [ ] `STORIA-CLINICA.md` con backfill 30gg + hook attivo
- [ ] `scripts/generate_anatomia.py` + cron Sun 05:30
- [ ] `scripts/append_storia_clinica.py` + git post-commit hook
- [ ] `scripts/check_sacred_books_links.sh` + cron Sun 06:00
- [ ] `CLAUDE.md` aggiornato con INDEX.md pointer
- [ ] `VADEMECUM.md` cross-link aggiunti dove menziona cell-core/Mata Garuda/ecc.
- [ ] Review multi-modello completa + feedback consolidato
- [ ] Commit + push

---

## 7. Success Criteria

**Misurabili:**

1. **Zero discovery tardiva:** nuova sessione Claude deve identificare cell-core entro 3 letture (CLAUDE.md → INDEX.md → ANATOMIA §cell-core)
2. **Staleness prevention:** diff settimanale ANATOMIA AUTO < 20% (altrimenti drift rapido)
3. **Broken links:** 0 tolleranza post-commit (check weekly)
4. **STORIA auto-append:** ogni sprint ≥1 entry auto-generate

**Qualitativi:**

- VADEMECUM §2 riferisce ANATOMIA §cell-core (no context lost)
- INDEX max 200 righe = sempre leggibile in un colpo d'occhio
- FISIOLOGIA permette di scrivere nuovo agente conoscendo esattamente i contratti

---

## 8. Risks

| Rischio                                       | Mitigazione                                                                                               |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| ANATOMIA AUTO sbaglia scan → info fasulla     | Dry-run + diff review prima di commit auto                                                                |
| STORIA-CLINICA crescita ingestibile           | Rolling 12 mesi, archivi annuali                                                                          |
| INDEX diventa obsoleto tra due update manuali | Alert se >90 giorni senza update manuale                                                                  |
| Documenti non vengono letti comunque          | CLAUDE.md top 5 righe obbligatorie — hook SessionStart già esiste                                         |
| Tempo-costo scrittura > valore                | Check mid-sprint (Day 4): se INDEX+ANATOMIA base non funzionano come discovery device, ferma e riprogetta |

---

## 9. Dependencies (prerequisiti)

- ✅ `crontab -l` accessibile
- ✅ Qdrant Cloud API accessibile
- ✅ Fly proxy postgres funzionante
- ✅ Git hooks attivabili
- ✅ Telegram bot attivo per alert
- ✅ `automation_catalog.json` esistente

Nessuna dipendenza nuova.

---

## 10. References

- Cicatrice di partenza: "scoperta tardiva di cell-core" durante Sprint 5.2 brainstorm (2026-04-15)
- `SYMBIOSIS.md` §L0 Cellular — cita cell-core ma non abbastanza prominente
- `VADEMECUM.md` §2 — checklist cell-core già esiste
- `packages/cell-core/cell_core/__init__.py` — API pubblica framework
- Analog: Microsoft "Dependabot" style docs auto-generation
- Analog: OpenAPI auto-generated API docs
- Paper (SOTA round 3): Full-Body AI-Agent (arxiv 2025) — architettura con coordinazione organi

---

**End of spec v1. Next: enrichment federation + review multi-modello.**

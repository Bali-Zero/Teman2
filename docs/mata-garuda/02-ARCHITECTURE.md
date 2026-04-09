# Mata Garuda — Architecture

> Data: 2026-04-08 (v0.1) | 2026-04-09 (v0.2 — meta-agent layer)
> Sessioni: S01 brainstorming, S04 AutoAgent patterns

## 5 Layer + Meta-Agent (trasversale)

```
                  ┌───────────────────────────────┐
                  │  META-AGENT LAYER (v0.2)      │
                  │  ─────────────────────        │
                  │  • Registry dinamico          │
                  │  • Create/Run/Edit agents     │
                  │  • Lamarckian feedback        │
                  │  • GENOME.md per agente       │
                  │  • CLI runtime (claude/gemini)│
                  │                               │
                  │  Orchestra ↓                  │
                  └───┬───────────┬─────────┬─────┘
                      │           │         │
                      ▼           ▼         ▼
                   Layer 1     Layer 2   Layer 4
                  Harvester   Kognitif  Analista
                  agents      workers   agents
```

```
LAYER 1: HARVESTER (Raccolta)
┌─────────────────────────────────────────────────────────────┐
│  Esistenti (estendere)              Nuovi                   │
│  ├─ Intel Scraper (609 fonti)       ├─ Regulation Watcher   │
│  ├─ War Room Researcher (Exa+xAI)  ├─ Pasal.id MCP        │
│  ├─ OSINT Scrapers (.go.id)        ├─ Social Listener      │
│  └─ NLM Deep Research              ├─ Telegram Channels     │
│                                     ├─ Tavily (1000/mo free)│
│                                     └─ peraturan.go.id FAISS│
│                                                             │
│  Formato output: HarvestItem JSON → Redis Stream            │
└──────────────────────┬──────────────────────────────────────┘
                       │ garuda:raw
                       ▼
LAYER 2: KOGNITIF (Processing)
┌─────────────────────────────────────────────────────────────┐
│  Workers Python async su Redis consumer groups              │
│                                                             │
│  1. Dedup        — hash + semantic similarity (Ollama)      │
│  2. Classifier   — gemma4:26b → topic, priority             │
│  3. Scorer       — quality_gate.yaml esistente              │
│  4. NER          — OSINT NER esteso (qwen3.5:9b locale)    │
│  5. Embedder     — text-embedding-3-small → Qdrant          │
│  6. Contradiction— verifica vs KB esistente                  │
│  7. SemanticDiff — per fonti .go.id monitorate              │
│                                                             │
│  LLM Router:                                                │
│    Ollama (bulk) → Claude CLI (enrichment)                  │
│    → Gemini CLI (grounding) → DeepSeek API (reasoning)      │
└──────────────────────┬──────────────────────────────────────┘
                       │ garuda:enriched + garuda:osint (blindato)
                       ▼
LAYER 3: NEXUS (Knowledge Unificato)
┌─────────────────────────────────────────────────────────────┐
│  Neo4j (OSINT graph, SOLO locale Pro)                       │
│  Qdrant (vectors, Fly.io)                                   │
│  PostgreSQL (metadata, Fly.io)                              │
│  NLM (6+ notebook domain, cervello analitico)               │
│  SQLite (MOS memoria locale)                                │
│                                                             │
│  KG Linker Agent (LangGraph):                               │
│    articolo → entity extraction → graph update              │
│    → relationship inference → temporal tracking             │
│                                                             │
│  NLM Feeder:                                                │
│    articoli classificati → auto-add al NB domain giusto     │
│    → query periodiche per sintesi cross-topic               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
LAYER 4: ANALISTA (Intelligence Products)
┌─────────────────────────────────────────────────────────────┐
│  Agent              Output              Schedule  Autonomia │
│  ├─ Daily Briefing  MD briefing         07:00     L1        │
│  ├─ Reg Alert       semantic diffs      real-time L1        │
│  ├─ Contradiction   KB conflict flags   real-time L1        │
│  ├─ Dossier Update  entity updates      on-data   L1        │
│  ├─ Weekly Digest   strategic summary   Sun 08:00 L1        │
│  ├─ Anomaly Detect  pattern alerts      continuous L1       │
│  ├─ WR Topic Agent  carousel topics     Wed/Sat   L2        │
│  ├─ NLM Expander    new NB / sources    weekly    L2        │
│  └─ Source Health   deactivate/find     daily     L2        │
│                                                             │
│  LLM: Claude CLI (briefing) + Gemini CLI (grounding)        │
│       + DeepSeek API (reasoning) + Ollama (bulk)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
LAYER 5: DISTRIBUZIONE (Channel Strategy)
┌─────────────────────────────────────────────────────────────┐
│  Canale              Audience          Contenuto   Lingua   │
│  ├─ TG Privato Zero  Solo Zero        Everything  IT       │
│  ├─ TG Channel BZ    Clienti/public   Curated news ID/EN   │
│  ├─ Instagram        Public           Carousel    EN/ID    │
│  ├─ X/Twitter        Public           Threads     EN       │
│  ├─ Newsletter       Clienti email    Weekly dig  EN       │
│  ├─ Blog BZ          Public           Long-form   EN/ID    │
│  ├─ WhatsApp Bcast   Clienti urgenti  Breaking    EN/ID    │
│  ├─ LinkedIn         Professional     Thought ld  EN       │
│  ├─ Zantara RAG      AI assistant     KB updates  -        │
│  ├─ OSINT Feed       Solo Zero locale Graph data  -        │
│  └─ MCP garuda.query AI assistants    API         -        │
└─────────────────────────────────────────────────────────────┘
```

## Meta-Agent Layer (v0.2 — 2026-04-09)

Il **meta-agent layer** è il sistema nervoso autonomo di Mata Garuda. NON è un layer dati (come i 5 layer Harvester→Distribuzione), è un **piano di controllo trasversale** che governa ciclo di vita degli agenti.

> Patterns ispirati da HKUDS/AutoAgent (vedi [40c](40c-AUTOAGENT-EVAL.md), [40d](40d-AUTOAGENT-PATTERNS.md))
> + agent-taxonomy GENOME.md philosophy (vedi [40b](40b-AGENT-TAXONOMY.md))
> + Vincoli Mata Garuda: CLI-only, no Docker generico, OSINT blindato

### Componenti

```
mata_garuda/
├── registry.py          # Singleton + @register_agent decorator (~70 LOC)
├── types.py             # Agent, Response, Result Pydantic models (~30 LOC)
├── runtime/
│   ├── cli_runtime.py   # subprocess wrapper claude/gemini/codex (~150 LOC)
│   ├── loop.py          # MetaChain loop semplificato (~80 LOC)
│   └── lamarckian.py    # case_resolved/not_resolved + GENOME hook (~140 LOC)
├── agents/
│   ├── __init__.py      # recursive auto-import (~30 LOC)
│   ├── meta_agent.py    # crea/edit altri agenti via NL (~50 LOC)
│   ├── dummy_agent.py   # template per create_agent (~40 LOC)
│   └── {layer1,2,4}/    # agenti operativi raggruppati per layer
│       └── GENOME.md    # 1 GENOME per agente (Lamarckian)
├── tools/
│   ├── meta_tools.py    # list/create/delete/run agents (~140 LOC)
│   └── {harvester,...}  # tool operativi
└── feedback/
    └── {agent}.md       # log fallimenti per Lamarckian mutation
```

### Flusso di esecuzione di un agente

```
1. User/Cron → request to agent X
   │
   ▼
2. registry.agents['get_X'](model='claude') → Agent instance
   │
   ▼
3. cli_runtime.run(agent_X, messages, ctx)
   │
   ├─ subprocess: `claude --print "system+history"`
   ├─ parse stdout → tool calls (JSON in text se non native)
   └─ esegue tool → next iteration
   │
   ▼
4. loop termina con case_resolved OR case_not_resolved
   │
   ├─ resolved → return result
   │
   └─ not_resolved → lamarckian.handle_failure()
        │
        ├─ append failure to feedback/X.md
        ├─ if attempts >= 3:
        │    escalate to meta_agent
        │    meta_agent reads feedback/X.md
        │    proposes mutation to agents/X/GENOME.md
        │    requires human review (Zero)
        │    if approved: mutation applied
        │    measure fitness: success rate next 10 runs
        │    if degraded: auto-revert
        └─ else: retry with hint
```

### Vincoli architetturali

| Vincolo | Implementazione |
|---|---|
| LLM CLI-only | `cli_runtime.py` usa `subprocess.run(['claude', '--print', ...])`. NESSUNA chiamata HTTP a Anthropic/Google API. DeepSeek API ammessa per reasoning specifico. |
| OSINT blindato | Meta-agent instructions: "NEVER create agents that touch frontend/clients/team channels". Tool `create_agent` rifiuta path che matchano `frontend/`, `apps/mouth/`, `channels/`. |
| No Docker generico | Agenti girano in-process Python (venv), NON in container. Sandboxing via permessi venv + path whitelist. |
| Stack minimale | Solo `pydantic` come dependency esterna del meta-agent core. ChromaDB/browsergym/litellm RIFIUTATI. |
| Lamarckian | Ogni agente ha `agents/{name}/GENOME.md`. Mutazioni proposte automaticamente, applicate solo dopo review umana. Fitness misurata su 10 run successivi. |
| Self-contained validation | `create_agent` esegue `python -c "import mata_garuda.agents.X"` prima di registrare l'agente. Validazione locale, no Docker. |

### Cosa il meta-agent NON fa

- ❌ NON crea agenti che esfiltrano dati al cloud (firewall path/imports)
- ❌ NON modifica agenti esistenti senza review umana se la mutazione tocca > 20% LOC
- ❌ NON esegue codice arbitrario via `execute_command` su path fuori da `mata_garuda/`
- ❌ NON forka processi long-running senza ack del registry
- ❌ NON tocca `apps/` del monorepo Nuzantara — Mata Garuda è isolato

### Differenze chiave vs HKUDS/AutoAgent originale

| Aspetto | HKUDS/AutoAgent | Mata Garuda |
|---|---|---|
| LLM provider | litellm (HTTP API) | subprocess CLI |
| Sandboxing | Docker container `tjbtech1/metachain:latest` | venv + path whitelist |
| Self-update | Git clone mirror del repo nel container | File system locale + GENOME.md |
| Memory | ChromaDB embedded | NLM (cervello) + Qdrant (vectors) esistenti |
| Tool count | 100+ in `autoagent/tools/` | Solo quelli necessari per Mata Garuda layers |
| Browser env | browsergym 0.13.0 (pinned vecchio) | playwright nudo via `bali-intel-scraper` esistente |
| Vincoli OSINT | Nessuno | Hard-coded in tool `create_agent` |
| Stima LOC | ~50.000 | ~580 |

---

## Stream Redis

| Stream | Contenuto | Accesso |
|--------|-----------|---------|
| garuda:raw | Articoli grezzi da tutti gli harvester | Workers Layer 2 |
| garuda:classified | Articoli con topic, score, priority | Workers Layer 2 + Analyst |
| garuda:enriched | Articoli con NER, embedding, verification | Layer 3 + 4 |
| garuda:osint | Feed per OSINT enrichment | SOLO processi locali Pro |
| garuda:alerts | Alert high-priority (regulation changes, etc.) | Dispatchers Layer 5 |
| garuda:digest | Intelligence products formattati | Dispatchers Layer 5 |

## Firewall OSINT

```
garuda:enriched ──► garuda:osint (one-way IN al graph locale)
                     │
                     ▼
              Neo4j locale Pro
              OSINT Nexus UI (localhost:3333)
              TG privato Zero
              ╳ MAI → frontend, clienti, team, cloud, API
```

## Database Roles

| DB | Dove | Cosa ci mette Mata Garuda |
|----|------|---------------------------|
| PostgreSQL (Fly.io) | Cloud | article metadata, scores, classification, states |
| Qdrant (Fly.io) | Cloud | article vectors per RAG search |
| Neo4j (locale Pro) | SOLO locale | OSINT entities + news entity links (blindato) |
| NLM (Google) | Cloud (ma dati pubblici) | Articoli come source, sintesi, deep research |
| Redis (locale/Fly.io) | Entrambi | Streams bus, cache, dedup |
| SQLite (MOS) | Locale Pro | Decision log, memory |

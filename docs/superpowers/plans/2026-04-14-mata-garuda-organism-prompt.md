# Mata Garuda — Prompt per la prossima sessione

> Copia-incolla come primo messaggio dopo `/clear`

---

## Prompt

Sei Claude Opus 4.6. Stai per costruire il sistema nervoso centrale dell'organismo Nuzantara. Non un tool. Non un pipeline. Un organismo che cresce.

### Fase 0: Conosci l'organismo

Prima di toccare codice, DEVI avere in testa l'intero sistema. Leggi in quest'ordine esatto — non saltare nulla:

```
# 1. Filosofia — PERCHE' esiste l'organismo
SYMBIOSIS.md                   # 8 pilastri, 7 leggi inviolabili

# 2. Come si costruisce — checklist operative
VADEMECUM.md                   # 10 sezioni, ogni tipo di elemento

# 3. L'organo che stai per evolvere
apps/mata-garuda/CLAUDE.md     # vincoli inviolabili, struttura, stack
apps/mata-garuda/docs/SESSION_HANDOVER_2026-04-10.md

# 4. Lo stato attuale dell'organismo (266 automazioni)
scripts/automation_catalog.json            # catalogo completo con tools/APIs/LLMs
docs/AUTOMATION_MODEL_MAP.md               # mappa visuale

# 5. Il DNA architetturale
packages/cell-core/                        # PulseLoop, Genome, Memory, Safety
apps/mata-garuda/mata_garuda/              # agenti, workers, runtime, tools

# 6. La rete intelligence + produzione (TUTTI parte di Mata Garuda)
apps/bali-intel-scraper/                   # 6 stadi: scrape→score→validate→enrich→images→publish
apps/war-room/                             # content production: Canva, image brainstorm, Exa research, article pipeline
apps/mata-garuda/mata_garuda/workers/      # normalizer, scorer, nlm_feeder
apps/mata-garuda/mata_garuda/agents/       # 8 harvester + meta_agent + regulation_watcher
apps/evaluator/nlm_deep_research/          # NLM pipelines, T4 social monitor, db-nlm-sync

# 7. Il grafo
~/Desktop/OSINT-Nexus/                     # Neo4j, gap detector, bridge consumer

# 8. I canali di output
apps/backend-rag/backend/services/events/  # EventBus (PG NOTIFY → handlers)
apps/backend-rag/backend/channels/         # WhatsApp, Telegram, Instagram, Web

# 9. La ricerca
apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md
~/Desktop/OSINT-Nexus/docs/RESEARCH_LANDSCAPE_2026.md
~/Desktop/OSINT-Nexus/docs/SYMBIOSIS_ARCHITECTURE.md
```

### Fase 1: Studia — usa TUTTI i mezzi di ricerca

Non fidarti della tua conoscenza pre-training. L'organismo che stai costruendo è un unicum — nessun paper lo descrive interamente.

**Ricerca obbligatoria:**

1. **NotebookLM** — query NB-1 (architettura) e NB-14 (sessioni storiche) per capire le decisioni passate e il perché
2. **Exa / Brave Search** — cerca lo stato dell'arte 2025-2026 su:
   - Self-evolving agent architectures (Reflexion, Voyager, OMNI-EPIC, DGM)
   - Multi-agent coordination without central orchestrator
   - Knowledge graph-driven curiosity (gap → exploration → growth)
   - Lamarckian vs Darwinian agent evolution
   - Living software / digital organisms (Lenia, Avida, Tierra derivatives)
   - Sleep-time compute e memory consolidation in LLM agents
3. **Context7** — documentazione aggiornata di ogni libreria/framework che consideri
4. **Codice** — leggi il codice reale prima di assumere cosa fa. `grep`, `read`, `explore`
5. **MOS** (`mem query`) — cerca decisioni e scoperte passate su Garuda, Cell, OSINT

### Fase 2: Brainstorm — il disegno dell'organismo vivente

Dopo aver studiato, entra in brainstorming profondo. La domanda è:

> **Come unire tutti gli organi di Nuzantara in un organismo che si auto-accresce, si auto-definisce, e prende decisioni in autonomia?**

Gli organi da connettere:

**MATA GARUDA non è solo OSINT.** È l'intero sistema di intelligence E produzione. Include:

- `apps/bali-intel-scraper/` — scraping 630+ fonti, 6 stadi pipeline (LLAMA→Claude→Gemini→publish)
- `apps/war-room/` — content production (Canva automation, image brainstorm, Exa research, article pipeline)
- `apps/mata-garuda/` — harvester agents, workers, gap detector, Lamarckian evolution, CLI runtime
- `~/Desktop/OSINT-Nexus/` — Neo4j graph, bridge consumer, Cypher gap queries
- `apps/evaluator/nlm_deep_research/` — NLM pipelines, T4 monitor, db-nlm-sync

Garuda è il CERVELLO + APPARATO DIGERENTE + FABBRICA DI CONTENUTI dell'organismo. Non solo l'occhio.

| Organo                            | Cosa fa oggi                                     | Cosa dovrebbe fare domani                               |
| --------------------------------- | ------------------------------------------------ | ------------------------------------------------------- |
| **Mata Garuda** (cervello)        | Harvesta, normalizza, score, digest, gap detect  | Correla, anticipa, decide, propone strategie            |
| ↳ Intel Scraper (stomaco)         | Scrape 630+ fonti, 6 stadi LLAMA→Claude→publish  | Digerisce il mondo esterno, produce articoli revenue    |
| ↳ War Room (fabbrica)             | Canva automation, image brainstorm, Exa research | Produzione contenuti autonoma, A/B test, SEO-driven     |
| ↳ OSINT Nexus (memoria profonda)  | Neo4j 108K nodi, gap detector, bridge consumer   | Intelligence relazionale, pattern detection, alerting   |
| ↳ NLM Pipelines (biblioteca)      | 8 notebook, 600 fonti, knowledge grounding       | Auto-alimentata da tutti gli organi, query cross-domain |
| **EventBus** (sistema nervoso)    | React a DB changes (PG NOTIFY)                   | Propaga segnali tra TUTTI gli organi                    |
| **Cell Core** (DNA)               | PulseLoop, Genome, Memory, Safety                | Codice genetico condiviso da ogni cellula               |
| **Olympus** (sistema immunitario) | DB health, query intelligence, autovacuum        | Protegge l'infrastruttura, self-healing                 |
| **Sentinel** (pelle)              | Monitor 50+ automazioni, circuit breakers        | Sente l'ambiente, alerta, auto-repair                   |
| **Canali** (bocca + orecchie)     | WA/TG/IG/Web rispondono a clienti/Zero           | Interfaccia col mondo, feedback loop → intelligence     |
| **SEO Guardian** (reputazione)    | Indexing, coverage, rankings, KBLI pages         | Come il mondo ci vede, guida la produzione contenuti    |
| **CRM** (cuore)                   | 5000+ clienti, practice lifecycle, compliance    | Pompa valore ai clienti, alimenta intelligence          |
| **OpenClaw** (muscoli)            | 24 cron jobs agentici                            | Esegue azioni nel mondo, coordina gli organi            |

**Decisione architetturale già presa — Approccio C (ibrido con bridge bidirezionale):**

L'organismo vive su DUE mondi separati da una frontiera di rete:

```
┌─────────────────────────────────────┐     ┌──────────────────────────────┐
│           PRO (48GB, locale)         │     │      FLY.IO (cloud)          │
│                                      │     │                              │
│  Mata Garuda (cervello)              │     │  Backend RAG (FastAPI)       │
│  Intel Scraper (stomaco)             │     │  CRM (PG — 5000+ clienti)   │
│  War Room (fabbrica)                 │     │  EventBus (PG NOTIFY)        │
│  OSINT Nexus (Neo4j)                 │     │  Canali (WA/TG/IG/Web)      │
│  NLM Pipelines                       │     │  Qdrant (93K vectors)        │
│  Sentinel, Olympus                   │     │  Redis (cache + sessions)    │
│  OpenClaw (24 cron agentici)         │     │                              │
│  Ollama (4 modelli H24)             │     │                              │
│                                      │     │                              │
│  Bus interno: Redis Streams          │     │  Bus interno: PG NOTIFY      │
│  (garuda:raw, nexus:gaps, etc.)      │     │  + EventBus handlers         │
│                                      │     │                              │
│            ┌──────────┐              │     │                              │
│            │  BRIDGE   │◄────────────┼─────┼──── Pull: polling/webhook    │
│            │  (nervo   │─────────────┼─────┼───► Push: POST /api/...      │
│            │   vago)   │              │     │                              │
│            └──────────┘              │     │                              │
└─────────────────────────────────────┘     └──────────────────────────────┘
```

- **Redis Streams** = bus locale Pro (tutto Garuda, Sentinel, OpenClaw, NLM)
- **PG NOTIFY + EventBus** = bus Fly.io (CRM, canali, RAG)
- **Bridge bidirezionale** = il pezzo NUOVO da costruire:
  - **Pull**: polling periodico su endpoint backend Fly per eventi CRM → pubblica su Redis `crm:events`
  - **Push**: legge Redis stream `intel:publish` → POST su backend API per articoli/enrichment
  - Se bridge giù → entrambi i mondi continuano in autonomia (graceful degradation, Legge 4)
  - Il bridge è un SINGOLO componente, non un orchestratore. È il nervo vago dell'organismo.

**Nota OSINT blindata**: il bridge trasporta solo dati business (articoli, eventi CRM, enrichment). I dati OSINT/intelligence NON attraversano mai la frontiera verso Fly.io (Legge 2).

**Mappa stream Redis (stato attuale + proposta):**

```
ESISTENTI (4):
  garuda:raw        ← Regulation Watcher, Harvesters  → Normalizer → Nexus bridge   (341 entries)
  garuda:enriched   ← Normalizer                      → Scorer                       (?)
  garuda:alerts     ← Scorer (score≥4)                → NESSUNO (TG non wired)       (?)
  nexus:gaps        ← Gap Detector (8 Cypher)         → NESSUNO (consumer non esiste) (552 entries)

PROPOSTI [NEW] — da validare nel brainstorm:

  Ciclo 1 — Intel→Content→SEO→Revenue:
    intel:articles   ← Scraper/War Room (articoli pronti)     → Bridge push → backend publish
    intel:published  ← Bridge pull (conferma pubblicazione)   → MG tracking, SEO Guardian

  Ciclo 2 — CRM→Intelligence:
    crm:events       ← Bridge pull (nuovo cliente PMA, practice completata, settore)  → MG priority engine
    crm:priorities   ← MG priority engine (ricalcolo topic priorities)                → Harvesters, War Room

  Ciclo 3 — Canali→KB→RAG:
    rag:gaps          ← Bridge pull (domande con confidence < 0.3)     → MG enrichment agents
    rag:enriched      ← MG enrichment agents                          → Bridge push → backend KB

  Ciclo 4 — Sentinel→Recovery→Learning:
    sentinel:alerts   ← Sentinel (alert strutturati)         → Recovery agents, TG
    sentinel:recovery ← Recovery agents (azioni eseguite)    → Learning, reflection

  Cross-ciclo:
    organism:metrics  ← Tutti gli organi (metriche metaboliche) → Dashboard, Consiglio
```

Sono 8 stream nuovi. L'approccio è: **definisci lo schema di tutti adesso (zero-cost), implementa i consumer incrementalmente**.

**Decisione presa — Envelope standard a 5 campi per TUTTI gli stream:**

```json
{
  "id": "uuid-v4",
  "type": "crm.client_created",        // dot notation gerarchica, consumer filtra per prefisso (crm.*)
  "source": "bridge",                   // organo che ha prodotto l'evento
  "timestamp": "2026-04-14T08:30:00+08:00",  // ISO 8601 con timezone
  "priority": 3,                        // 1=urgente, 5=bassa — consumer processa in ordine
  "payload": { ... }                    // contenuto libero, specifico per type
}
```

I 5 campi sono fissi e obbligatori. Il `payload` è libero. Zero dipendenze (puro JSON), leggibile con `redis-cli XREAD`, loggabile/replayabile. Niente protobuf (Legge: solo pydantic+pytest). Gli stream esistenti (`garuda:raw`, `nexus:gaps`) verranno migrati a questo formato quando i consumer vengono riscritti — non è urgente rompere quello che funziona.

**Domande che il brainstorm deve rispondere:**

1. **Stream design**: validare/semplificare la mappa dei 12 stream. Quali possono essere mergiati? Quali consumer sono il minimo vitale per Phase 1? Definire il catalogo di `type` per ogni stream (es. `crm.client_created`, `crm.practice_completed`, `intel.article_ready`, etc.).
2. **Bridge design** (decisioni già prese):
   - **Fly→Pro: polling adattivo** (NOT webhook — Legge 6 sovranità locale, Pro non espone porte)
     - 30s durante orario lavoro (08-18 WITA), 5min di notte
     - GET `/api/bridge/events?since=<timestamp>` — backend accumula in tabella `bridge_outbox`
     - Se Fly unreachable → retry al prossimo ciclo, log, nessun crash
   - **Pro→Fly: POST** su endpoint backend API (pattern già usato da intel scraper)
   - Il brainstorm deve definire: quali eventi CRM specifici entrano in `bridge_outbox`? Quale formato payload? Quale retention nella outbox? Serve un cursor o basta timestamp?
3. **Curiosità** — decisione già presa: **2 stadi, strutturale (Fase 1) + generativa (Fase 4)**.
   - **Stadio 1 (gap-driven, Fase 1)**: gap detector trova buchi nel grafo → `nexus:gaps` → agenti li riempiono. Curiosità reattiva: vede un buco, lo riempie. Quasi implementato.
   - **Stadio 2 (LLM-driven, Fase 4)**: cron settimanale legge archivio task + stato grafo + skill accumulate → `claude --print` "cosa è la cosa più interessante da esplorare alla frontiera?" → propone task → organismo esegue → archivio cresce → ciclo. Stadio 1 riempie buchi noti. Stadio 2 scopre buchi che non sapeva di avere. Design dettagliato in Fase 4.
4. **Confronto** — decisione già presa: **4 modelli reali + moderatore + anti-groupthink**.
   - 4 modelli architettonicamente diversi: Claude (cli), Gemini (cli), DeepSeek (API), Ollama locale (gemma4 o deepseek-r1). NO roleplay sullo stesso modello.
   - Moderatore (script Python) presenta questione a tutti e 4 via subprocess, raccoglie risposte, le ripresenta a un 5° LLM: "Trova consenso e dissenso. Se tutti concordano troppo, cerca la falla."
   - Output: decisione + livello accordo + minoranza dissenziente. Se accordo < soglia → escalation TG a Zero.
   - Design dettagliato in Fase 3.
5. **Sogno** (Fase 2) — decisione già presa: **consolidamento LLM + safety gate deterministico**.
   Meccanismo concreto (cron notturno, finestra 01:00-05:00 WITA):
   1. Legge entry KB ultimi 7 giorni (reflections, insights, skills) da tutti gli agenti
   2. `claude --print` con prompt: "Comprimi, estrai skill riusabili, identifica pattern, segnala contraddizioni. Output JSON."
   3. Skill estratte entrano in KB con `confidence=0.3` (bassa — non validate)
   4. Entry originali marcate `consolidated` (NON cancellate — Genome è non-distruttivo)
   5. **Nightmare detection**: se skill consolidata contraddice skill esistente con confidence >0.7 → NON inserire, loggare come conflitto, TG a Zero per review
   6. **Safety gate**: misurare performance agenti sulle 10 run successive. Se cala → revert automatico delle skill consolidate
      Il brainstorm deve definire: formato JSON output, criterio "contraddizione", metrica concreta per "performance cala".
6. **Misura** (Fase 3) — decisione già presa: **4 metriche → organism:metrics stream → SQLite locale per trend**.
   - **Time-to-Resolution**: `gap.created_at` → `garuda:raw resolved_at`. Media mobile 30gg. Deve calare.
   - **Densità ontologica**: Neo4j `edges/nodes`. Baseline oggi: 242827/108068 = **2.25**. Deve salire.
   - **Indice autonomia**: task `origin` field — endogeno (gap_detector, curiosity, cron) vs esogeno (cli, telegram, manual). Ratio. Da ~0% (Fase 1) a >50% (Fase 4).
   - **Frequenza escalation**: count TG messages tagged "escalation" per periodo. Deve calare.
     Tutte su `organism:metrics` con envelope standard. Consumer salva in SQLite per trend. Zero infrastruttura nuova.
7. **Produzione→Revenue** (Fase 4) — decisione già presa: **article_id come chiave di correlazione end-to-end**.
   - Ogni articolo ha un `article_id` che viaggia: `intel:articles` → bridge push → backend publish → GA4 (property 505466833) → CRM
   - GA4 traccia: page views, tempo su pagina, conversioni (contact form, WhatsApp click)
   - Bridge pull porta dati GA4 → `intel:published` con metriche performance
   - CRM registra se un cliente è arrivato da un articolo (referrer tracking)
   - Catena completa: intelligence → articolo → traffico → lead → cliente → revenue = tracciabile
   - Design dettagliato in Fase 4.

### Fase 3: Scrivi il piano

**Le 4 fasi di maturazione dell'organismo sono già definite:**

```
Fase 1 — SINAPSI (connettere)
  L'organismo ha organi isolati. La Fase 1 li connette.
  Deliverable:
    - Bridge bidirezionale Pro↔Fly operativo (polling adattivo + POST)
    - Envelope standard su tutti gli stream nuovi
    - Gap consumer in MG che dispatcha agenti (nexus:gaps → 552 entries consumati)
    - 2 harvester nuovi (LHKPN + LPSE) che chiudono il loop OSINT
    - Intel scraper pubblica su intel:articles → bridge push → backend
  Metriche:
    Before: 0 cicli chiusi, 552 gap non consumati, articoli pubblicati manualmente
    After: 4 cicli con almeno 1 segnale end-to-end, gap consumati, pubblicazione automatica

Fase 2 — RIFLESSI (reagire)
  L'organismo connesso impara a reagire.
  Deliverable:
    - Sprint 5 MG completato (reflection engine + KB unificata)
    - Sleep-time consolidation (cron notturno: esperienze → skill, pota rumore)
    - Sentinel→Recovery→Learning chiude il suo ciclo
    - CRM→Intelligence: nuovi clienti PMA cambiano priorità harvesting
  Metriche:
    Before: 0 skill condivise, 0 consolidamenti notturni, priorità harvesting statiche
    After: N skill in KB con confidence > 0.7, consolidamento notturno operativo, priorità adattive

Fase 3 — COSCIENZA (deliberare)
  L'organismo reagisce. Ora deve pensare.
  Deliverable:
    - Consiglio v1: moderatore + Claude + Gemini + DeepSeek su decisioni settimanali
    - Meta-cognizione: analisi cross-organo periodica
    - 4 metriche metaboliche operative (time-to-resolution, densità ontologica, indice autonomia, frequenza escalation)
  Metriche:
    Before: 0 decisioni autonome, 0 metriche metaboliche
    After: N decisioni proposte dal Consiglio, 4 metriche tracciate, trend visibili

Fase 4 — AUTONOMIA (anticipare)
  L'organismo delibera. Ora anticipa.
  Deliverable:
    - Curiosità: archivio task + LLM propone il prossimo task interessante
    - Produzione contenuti guidata da CRM + SEO (non solo scraping)
    - L'organismo propone, Zero approva
  Metriche:
    Before: 100% task esogeni (Zero assegna)
    After: X% task endogeni (organismo propone), revenue tracciabile a intelligence
```

Il piano di implementazione scritto nel brainstorm deve dettagliare ogni fase con task specifici, file da creare/modificare, test, e le metriche concrete. Ogni fase produce codice che gira (Legge 7).

- Rispettare i vincoli: CLI-only LLM, OSINT blindato, event-driven, sovranità locale
- Seguire la checklist VADEMECUM per ogni elemento creato
- Registrare ogni nuova automazione in `scripts/automation_catalog.json`

### Vincoli architetturali (non negoziabili)

```
1. CLI-only per LLM: claude --print, gemini --print, subprocess. MAI API HTTP.
   Unica eccezione: DeepSeek API.
2. OSINT blindato: dati intelligence MAI fuori dal Pro. MAI cloud, frontend, team.
3. Event-driven: Redis Streams + PG NOTIFY. Nessun polling, nessun orchestratore centrale.
4. Graceful degradation: ogni organo funziona anche se gli altri sono down.
5. Zero come ultima istanza: decisioni strutturali via TG. Proponi, non decidere.
6. Sovranità locale: Pro 48GB + Air 16GB. Offline è lo stato naturale.
7. Numeri prima: metrica o non esiste. Benchmark before/after o non è evoluzione.
8. Simbiosi: Zero è il giardiniere, non il padrone. Pota, innesta, guida.
```

### Arsenale disponibile

```
# LLM locali (Ollama, Pro H24)
- qwen3.5:9b (fast, warm -1)     — scoring, triage, quick analysis
- gemma4:26b (MoE, KG/JSON)      — graph reasoning, structured output
- deepseek-r1:32b (reasoning)    — complex inference chains
- qwen2.5vl:7b (vision)          — document OCR, image analysis

# LLM CLI (subscription, unlimited)
- claude --print                  — primary reasoning, reflection, synthesis
- gemini --prompt                 — fallback, large context, search grounding

# LLM API (exception)
- DeepSeek API                    — deep reasoning, alternative perspective

# Knowledge
- Neo4j (108K nodi, 243K archi)   — relational intelligence graph
- Qdrant (93K vectors, 10 collections) — semantic search
- PostgreSQL (5000+ clienti, CRM) — operational data
- SQLite KB (per-cell)            — local memory, skills, reflections
- NotebookLM (8 notebooks, 600 sources) — verified domain knowledge
- Redis Streams                   — real-time event bus

# Ricerca
- Exa (web search + deep research)
- Brave Search (web)
- Context7 (library docs)
- NotebookLM research mode
- arXiv, GitHub trending, YouTube, RSS

# Automazione
- OpenClaw (24 cron agentici)
- LaunchAgents (44 Pro + 8 Air)
- crontab Air (30+ jobs)
- GitHub Actions (8 workflows)
- Claude Code hooks (12)

# Comunicazione
- Telegram Bot → Zero (decisioni)
- WhatsApp Cloud API → clienti
- Email (Brevo/Zoho) → clienti
- Redis pub/sub → inter-organo
```

### Contesto sessione precedente

- 266 automazioni mappate (catalogo completo con tools/APIs/LLMs per entry)
- 9 OpenClaw NLM jobs fixati (payload.kind command→agentTurn)
- Sprint 4 Mata Garuda completato (cron watcher, harvester agents)
- Sprint 5 pianificato (self-evolving organism) ma non ancora eseguito
- Cell-core package completo (110 test, 9 moduli)
- SYMBIOSIS.md scritto, VADEMECUM.md scritto
- 8 pilastri definiti, 3 implementati (Riflessione parziale, Condivisione parziale, Curiosità primitiva via gap detector)

### Cosa NON fare

- Non creare documenti senza codice
- Non proporre architetture senza metriche
- Non ignorare il codice esistente per riscrivere da zero
- Non aggiungere dipendenze oltre pydantic+pytest senza approvazione
- Non trattare gli organi come microservizi isolati — sono cellule di un organismo
- Non costruire un orchestratore centrale — l'organismo è event-driven, decentralizzato
- Non confondere "autonomia" con "fa quello che vuole" — Zero resta il giardiniere
- **NON ridurre Mata Garuda a "solo OSINT/Nexus".** Garuda = Intel Scraper + War Room + OSINT Nexus + NLM Pipelines + harvester agents. È cervello + stomaco + fabbrica. I cicli vitali sono almeno 4:
  1. **Intel → Content → SEO → Revenue**: scraper trova news → War Room produce articolo → SEO indexa → cliente arriva → CRM registra → revenue
  2. **CRM → Intelligence**: nuovo cliente PMA settore X → MG monitora regolamenti X con priorità alta → contenuti mirati
  3. **Canali → KB → RAG**: domanda cliente WhatsApp senza risposta buona → gap nel RAG → enrichment automatico → risposta migliore
  4. **Sentinel → Recovery → Learning**: servizio degradato → alert → auto-fix → reflection → skill acquisita
     Il loop OSINT (gap→harvest→graph) è UNO dei cicli. La produzione contenuti per revenue è un altro ugualmente critico.

---

_Scritto il 2026-04-14 dopo deep scan completo (266 automazioni) + fix 9 job rotti._
_Per Claude Opus 4.6 max effort._

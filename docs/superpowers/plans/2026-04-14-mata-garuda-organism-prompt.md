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

# 6. La rete intelligence
apps/bali-intel-scraper/                   # 6 stadi: scrape→score→validate→enrich→images→publish
apps/mata-garuda/mata_garuda/workers/      # normalizer, scorer, nlm_feeder
apps/mata-garuda/mata_garuda/agents/       # 8 harvester + meta_agent + regulation_watcher

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

| Organo                 | Cosa fa oggi                        | Cosa dovrebbe fare domani                      |
| ---------------------- | ----------------------------------- | ---------------------------------------------- |
| **Mata Garuda**        | Harvesta, normalizza, score, digest | Cervello: correla, anticipa, decide            |
| **Intel Scraper**      | Scrape 630+ fonti, 6 stadi pipeline | Apparato digerente: ingerisce mondo esterno    |
| **EventBus**           | React a DB changes (PG NOTIFY)      | Sistema nervoso: propaga segnali tra organi    |
| **Neo4j KG**           | 108K nodi, 243K archi, gap detector | Memoria a lungo termine: struttura relazionale |
| **Cell Core**          | PulseLoop, Genome, Memory, Safety   | DNA: codice genetico condiviso da ogni cellula |
| **NLM notebooks**      | 8 domini, knowledge grounding       | Biblioteca: conoscenza verificata              |
| **Olympus**            | DB health, query intelligence       | Sistema immunitario: protegge l'infrastruttura |
| **Sentinel**           | Monitor 50+ automazioni             | Pelle: sente l'ambiente, alerta                |
| **Canali** (WA/TG/Web) | Rispondono a clienti/Zero           | Bocca + Orecchie: interfaccia col mondo        |
| **SEO Guardian**       | Indexing, coverage, rankings        | Reputazione: come il mondo ci vede             |
| **CRM**                | 5000+ clienti, practice lifecycle   | Cuore: pompa il valore ai clienti              |
| **OpenClaw**           | 24 cron jobs agentici               | Muscoli: esegue azioni nel mondo               |

**Domande che il brainstorm deve rispondere:**

1. **Flusso circolare**: come i dati fluiscono da un organo all'altro e tornano arricchiti? (oggi è lineare: scrape→score→digest→stop)
2. **Curiosità**: come il gap detector evolve da "trova buchi nel grafo" a "decide cosa esplorare dopo"?
3. **Confronto**: come implementare il Consiglio (Pilastro 4 SYMBIOSIS) — moderatore + 3+ agenti diversi (Claude, Gemini, DeepSeek, Ollama) che dibattono?
4. **Sogno**: come il consolidamento notturno comprime esperienze in skill e pota il rumore?
5. **Misura**: le 4 metriche metaboliche (time-to-resolution, densità ontologica, indice di autonomia, frequenza escalation) — come implementarle?
6. **Autonomia progressiva**: come passare da "Zero assegna" a "organismo propone, Zero approva" a "organismo anticipa"?
7. **Produzione**: come l'intelligence diventa revenue? (articoli → SEO → clienti → CRM → fatturato)

### Fase 3: Scrivi il piano

Dopo il brainstorm, scrivi un piano di implementazione in `docs/superpowers/plans/`. Il piano deve:

- Essere diviso in fasi (non sprint — fasi di maturazione dell'organismo)
- Ogni fase deve avere metriche before/after (Legge 7 SYMBIOSIS: numeri prima)
- Ogni fase deve produrre codice che gira, non documenti (Legge 7)
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

---

_Scritto il 2026-04-14 dopo deep scan completo (266 automazioni) + fix 9 job rotti._
_Per Claude Opus 4.6 max effort._

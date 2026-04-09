# Mata Garuda — Session Log

## S01 — 2026-04-08 — Brainstorming Iniziale

**Durata**: ~2h
**Partecipanti**: Zero + Claude Opus (lead) + Gemini 2.5 Pro (brainstorm) + 4 explorer agents
**Metodo**: Esplorazione parallela (4 agenti) + 12 ricerche web + Gemini brainstorm + sintesi

### Cosa e' stato fatto
1. Esplorato intero monorepo Nuzantara (23 app)
2. Letto in dettaglio: scraper pipeline, OSINT Nexus, backend RAG, War Room, graph engine
3. 12 ricerche web su architetture, tool, API, piattaforme
4. Gemini 2.5 Pro brainstorm completo (236 righe, "Project Argos")
5. DeepSeek API: key expired. Codex CLI: stdin incompatibile.
6. Sintesi architettura "Mata Garuda" a 5 layer
7. Feedback Zero: 8 punti critici che hanno riformulato la proposta
8. Creata cartella docs/mata-garuda/ con 10 documenti dettagliati

### Decisioni prese
- Nome: Mata Garuda
- LLM: CLI only (Claude, Gemini, Codex), DeepSeek API ok, MAI API Anthropic/Google
- OSINT: blindato, one-way IN, mai frontend/clienti/team
- NLM: cervello analitico centrale con 6+ notebook domain
- Bus: Redis Streams
- Autonomia: L1-L4 con escalation

### Feedback Zero — 8 punti
1. ✅ CLI only per Claude/Gemini — corretto, salvato in memoria
2. ✅ OSINT blindato — firewall architetturale, stream separato
3. ✅ NLM sottovalutato — elevato a cervello analitico centrale
4. ✅ xAI: keep per War Room, non core
5. ✅ Tavily free tier: 1000/mese, integrare
6. ✅ Troppi cannoni, pochi bersagli — riformulato con target concreti
7. ✅ Organismo autonomo — L1-L4 con auto-espansione
8. ✅ Strategia canali — 8 canali con agent dedicati

### Questioni aperte per prossima sessione
- CLI throughput/rate limits
- NLM Deep Research limiti
- Stato canali (TG channel, X CRC, LinkedIn)
- Newsletter tool selection
- Build order dettagliato per Fase 1
- Micro-approfondimento su Regulation Watcher (semantic diff architecture)

## S04 — 2026-04-09 — HKUDS/AutoAgent Discovery

**Durata**: ~30min
**Metodo**: GitHub MCP API only (no clone)
**Obiettivo**: valutare se forkare HKUDS/AutoAgent come runtime del meta-agent Mata Garuda

**Cosa è stato fatto**:
1. Verificato repo metadata: 9065⭐, 1278 forks, MIT, last push 2025-10-16, paper arXiv 2502.05957
2. Letto README.md (20KB) integralmente
3. Mappato struttura `autoagent/` directory
4. Letto `core.py` integralmente (~700 LOC) — heart con litellm
5. Letto `main.py` (case_resolved/case_not_resolved pattern)
6. Letto `agents/meta_agent/agent_editor.py` (40 righe — sorprendentemente compatto)
7. Letto `agents/__init__.py` (registry recursive walk)
8. Letto `constant.py` (env vars, NOT_USE_FN_CALL list, model defaults)
9. Verificato `setup.cfg` (litellm==1.55.0 pinned, dipendenze pesanti)
10. Verificato LICENSE: MIT
11. Mappato `environment/` (docker_env.py 13KB + local_env.py 4KB + browser_env.py 28KB)
12. Mappato `memory/` (5 backend ChromaDB)

**Verdetto**: ISPIRAZIONE, NON FORK
- Litellm è il cuore (700 LOC) — conversione CLI-only snatura il progetto
- Docker container default + auto-clone mirror su GitHub = conflitto OSINT blindato
- Stack pesante: chromadb, browsergym, faster_whisper, sentence_transformers, docling
- Reimplementare il pattern in 150 LOC Python pulito conviene 3-4x

**4 pattern da estrarre**:
1. Meta-agent loop (`agent_editor.py` 40 righe)
2. Registry recursive (`agents/__init__.py` 30 righe)
3. case_resolved/case_not_resolved fitness signal (`main.py`)
4. Browser env standalone (browsergym + playwright) — valutare per scraper OSINT

**Sinergia confermata**: agent-taxonomy GENOME.md = "cosa", AutoAgent meta-agent pattern = "come". Complementari.

**File prodotti**:
- 40c-AUTOAGENT-EVAL.md (~7KB, analisi completa)

**Open questions per S05**:
- `local_env.py` di AutoAgent è first-class? (riduce vincolo Docker se sì)
- browsergym standalone gestibile? (vs playwright nudo)
- Provare AutoAgent in `auto deep-research` mode una volta come benchmark di qualità?
- case_resolved/case_not_resolved come fitness signal merita doc dedicato?

**Prossimi micro-step**:
- [x] 40d-AUTOAGENT-PATTERNS.md — codice estratto dei 4 pattern (DONE 2026-04-09)
- [ ] 02-ARCHITECTURE.md — aggiornare meta-agent layer
- [ ] 50-BUILD-ORDER.md — sequenziare implementazione meta-agent runtime in 3 sprint
- [ ] POC: `mata_garuda/registry.py` (~70 LOC) come primo file

**S04 cont. (3) — Architecture v0.2 + Build Order + POC**:
- 02-ARCHITECTURE.md aggiornato a v0.2 con META-AGENT LAYER trasversale
- 50-BUILD-ORDER.md creato: 4 sprint (~9-10gg lavoro focalizzato)
  - Sprint 1 (~2gg): walking skeleton — registry+types+dummy+CLI runtime
  - Sprint 2 (~2gg): meta-agent + create/list/run tools + path firewall
  - Sprint 3 (~2gg): Lamarckian feedback + GENOME hook + fitness tracking
  - Sprint 4 (~3gg): POC reale Regulation Watcher integrato bali-intel-scraper
- POC Sprint 1 scritto in `docs/mata-garuda/poc/` (reference code, non installabile):
  - registry.py (~180 LOC) — singleton + decorator + recursive walk
  - types.py (~50 LOC) — Agent/Response/Result Pydantic
  - dummy_agent.py (~80 LOC) — template per meta-agent
  - dummy_agent_GENOME.md (~50 LOC) — esempio GENOME Lamarckian-ready
- **POC validato end-to-end**: 6 test smoke pass (singleton, decorator, FunctionInfo, callable round-trip, JSON serialize, tool registration)
- **Decisione architettonica aperta**: dove vive `mata_garuda/` package?
  - (a) `apps/mata-garuda/` monorepo
  - (b) `~/Desktop/mata-garuda/` standalone
  - (c) repo Git separato `Balizero1987/mata-garuda` privato (RACCOMANDATO)
  - **Da decidere PRIMA di Sprint 1 reale**

**S04 cont. (2) — 40d-AUTOAGENT-PATTERNS.md** (~30min):
- Letto registry.py (~200 LOC), dummy_agent.py, edit_agents.py (~500 LOC), types.py, local_env.py
- **Open question RISOLTA**: local_env.py NON è first-class — richiede conda installato + env hard-coded `auto`, è solo un mock di Docker. Conferma: reimplementare conviene.
- 4 pattern documentati con codice estratto + adattamento Mata Garuda CLI-only:
  1. Registry recursive (~70 LOC)
  2. Meta-agent (~50 LOC) + create_agent tool (~80 LOC)
  3. case_resolved/not_resolved + Lamarckian feedback hook (~140 LOC)
  4. Browser env: idea pattern (observation triple, action grammar, element IDs) — NON forkare, integrare in `bali-intel-scraper` esistente
- Stima totale Mata Garuda meta-agent: ~580 LOC vs ~50.000 di AutoAgent (~85x meno)
- Sinergia con agent-taxonomy GENOME.md confermata: case_not_resolved → feedback.md → meta_agent → mutation review

---

## S03 — 2026-04-09 — indonesia-civic-stack Deep Dive

**Durata**: ~1h
**Arsenale**:
- Clone diretto di 2 repo GitHub (`indonesia-civic-stack`, `indonesia-gov-apis`, `agent-taxonomy`)
- Install `pip install "indonesia-civic-stack[all]"` — 100+ dependencies, Playwright + Camoufox 298MB
- Test diretti su 13 moduli (Pro machine, Bali IP)
- Gemini 2.5 Pro CLI (valutazione modulo per modulo)
- DeepSeek API deepseek-chat (evaluation + integration strategy)
- Agente Exa processing file 188KB research

**Risultati test reali**:
- ✅ OK: BPOM, BMKG, BPJPH, JDIH (4 moduli perfetti)
- ⚠️ Degraded: KPU, KSEI, DJPB, LPSE (4 moduli con errori interni ma risultati wrappati)
- ❌ Fail: SIMBG, LHKPN, AHU, OSS, OJK (5 moduli rotti)
- ⏸️ Not tested: BPS (serve API key)
- **Utilizzabilita effettiva: ~60%**

**SCOPERTA GAME-CHANGING**: `agent-taxonomy` (stesso autore suryast)
- Framework Lamarckian per self-improvement AI agent
- Citato da @karpathy Marzo 2026
- Pattern `failure → rule → habit → identity`
- GENOME.md versionato, fitness metrics, auto-revert
- Integrabile come meta-agent di Mata Garuda
- URL: github.com/suryast/agent-taxonomy, agent-taxonomist.dev

**Ecosistema civic-stack completo**:
- Reference: indonesia-gov-apis (131⭐)
- Code: indonesia-civic-stack (1⭐, 1.1.0)
- Intelligence: (civic-signal-monitor non esiste, era allucinazione Exa)
- Status: status.datarakyat.id (live monitoring 52 portali)
- B2C: halalkah.id (9.57M), legalkah.id

**Competitor tools scoperti**:
- `setiapam/bps-mcp-server` — 32 tool BPS (vs 3 civic-stack)
- `Ansvar-Systems/indonesian-law-mcp` — 13 tool legal TypeScript

**Decisioni**:
1. Dual-layer architecture: civic-stack primario per modules OK, nostri scrapers per AHU/OSS/OJK/LHKPN
2. MCP separato (civic-stack alongside nuzantara-mcp, non merge)
3. bps-mcp-server invece di civic-stack per BPS
4. Implementare GENOME.md pattern per ogni Mata Garuda agent
5. Scrapare status.datarakyat.id per health monitoring

**File prodotti**:
- 40a-CIVIC-STACK-EVAL.md (9KB, analisi completa 46 tool)
- 40b-AGENT-TAXONOMY.md (5KB, pattern Lamarckian per Mata Garuda)

## S02 — 2026-04-08 — Deep Research Vision

**Durata**: ~1.5h (parallelo massivo)
**Arsenale impiegato**:
- 8 Web Search (Brave) — Palantir, Bloomberg, Recorded Future, Babel Street, AutoAgent, OpenBB, spaCy ID, LangGraph
- 3 Exa Advanced Search (1.2MB totali) → 3 agenti processing
- 1 Exa Deep Research Pro ($1.41, 121 pagine, 33 ricerche)
- 4 NLM Deep Research (376 fonti, 4 notebook creati e importati)
- 1 DeepSeek API (deepseek-chat, 16KB output)
- 1 Gemini 2.5 Pro CLI (97 righe output)
- Codex CLI: stdin non supportato (non utilizzabile per brainstorm)

**Scoperte game-changer**:
1. `suryast/indonesia-civic-stack` — MCP 46 tool per 14 fonti gov
2. `foundry-ontology-open` — reference open source dell'ontologia Palantir
3. PROTEUS — agente self-modifying completo, single Python file, Ollama
4. Thompson Sampling per source discovery con surprisal scoring
5. STIXAgent — LangGraph multi-agent report generation (peer-reviewed)
6. SPRE Controller — priority classification con cost-utility formula
7. `worldmonitor` — dashboard intelligence open source
8. `indonesian-embedding-small` — embedding model HuggingFace per bahasa

**01-VISION.md aggiornato**: ora ~22KB con sezioni su self-improving (PROTEUS, Thompson Sampling,
AlphaEvolve), briefing generation (Feedly, STIXAgent, SPRE), Palantir replicazione tecnica
completa (6 microservizi mappati), Google Drive 30TB strategy.

**Prossimi micro-punti**:
- [ ] indonesia-civic-stack: test dei 46 tool
- [ ] foundry-ontology-open: studio del codice
- [ ] PROTEUS: fork e adattamento per meta-agent Mata Garuda
- [ ] Build order: Fase 1 dettagliata con task specifici
- [ ] 02-ARCHITECTURE.md: aggiornare con nuovi pattern scoperti

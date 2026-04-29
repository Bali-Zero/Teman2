# NotebookLM (NB-1: Codebase & Architecture) — Audit zero-crash analysis

**Notebook:** NB-1 — Nuzantara Codebase & Architecture (`f6ecd115-dd89-4c9b-b3dd-071e0e2f1876`)
**52 sources, snapshot 2026-03-23**
**Conversation ID:** `20cd6007-21e6-42d3-8271-ec8edabf2e5c`

> Ground truth corrections applied to my (Opus) initial assumptions.
> Sources cited inline as `[N]` — full reference table at end.

---

Come Senior Platform Engineer di Nuzantara v5.2.0, procedo con l'audit forense basato rigorosamente sullo snapshot dei bundle sorgente del 2026-03-23. I documenti o PR non presenti nel codice sono esplicitamente dichiarati come non valutabili.

Ecco i 10 punti di fragilità (SPOF) in cui un errore si propaga senza recovery automatica, correggendo alcune tue assunzioni errate basandomi sul codice reale.

### 1. Fly.io App Crash Modes & Restart Loops

- **Failure Mode:** `RuntimeError` durante il boot del processo RAG. In `backend.app.setup.service_initializer.py`, l'inizializzazione sincrona `_init_critical_services` lancia esplicitamente un'eccezione non gestita se `SearchService` o `ZantaraAIClient` falliscono l'avvio [1].
- **Blast Radius:** 100% API downtime. Tutte le 88 route FastAPI dipendenti dall'app principale diventano irraggiungibili. L'host Fly.io innesca un restart loop continuo.
- **Current Detection:** GitHub Action `cron-fly-restart-detector.yml` schedulata ogni 15 minuti, che legge lo stato delle macchine via CLI [2].
- **Current Recovery:** Nessuna recovery interna per la macchina fallata. Su region outage subentrano i task di Air come standby [3].
- **Urgent Fix:** Gestire il fallimento di `_init_critical_services` con un fallback "degraded mode" (come fatto per i non-critical services) per consentire a uvicorn di fare bind sulla porta e servire almeno gli endpoint di `/health` e `/api/api`, interrompendo il restart loop di Fly.io.

### 2. FastAPI `dependencies.py` SPOF & Async Client Leak

- **Failure Mode:** Violazione della Golden Rule #10. L'istanziazione di `httpx.AsyncClient` all'interno di loop e body (invece di usare client persistenti) causa l'esaurimento dei socket TCP. Inoltre, `dependencies.py` usa un approccio `fail-fast` sollevando `HTTPException` globale se il servizio richiesto non è in `app.state` [4, 5].
- **Blast Radius:** Latenza `p95` severa per esaurimento pool; crash a cascata di tutte le route che usano `Depends(get_search_service)` se lo state si corrompe.
- **Current Detection:** Metriche Prometheus in `app.metrics.py` (es. `zantara_ai_latency_seconds`) [6].
- **Current Recovery:** Riavvio automatico del container tramite il demone locale `self_healing/backend_agent.py` su fallimento check [7].
- **Urgent Fix:** Convertire tutte le iniezioni di `httpx` in un client globale persistente con gestione esplicita nel lifespan `on_shutdown` per la chiusura controllata, come implementato correttamente in `email_http.py` [8].

### 3. Migration system v2 deploy ordering bug PR #307

- **UNKNOWN:** Dichiaro esplicitamente che **non trovo l'informazione nelle fonti**. Nel repository esiste un linter delle migrazioni (Squawk) in `.github/workflows/migration-lint.yml` [9] e viene menzionata una validazione runtime che ha "catturato la PR #302" [10]. Non esiste traccia del PR #307 o di un baco di ordinamento v2 nei sorgenti forniti.

> **Opus addendum:** PR #307 è documentato in `.claude/rules/cicatrix-scars.md` (post-snapshot 2026-04-26). NB-1 snapshot è 2026-03-23, ergo PR #307 NON è in NB-1. La cicatrix è autoritativa.

### 4. EventBus Redis Streams (Symbiosis Law 4) — CORREZIONE CRITICA

- **Failure Mode (Correzione Architetturale):** Il nostro `EventBus` **non usa Redis Streams**. L'infrastruttura si affida esclusivamente a **PostgreSQL LISTEN/NOTIFY** mappato su canali come `war_room.event` e `intel.event` [11, 12]. Il failure mode reale è la caduta o il partizionamento della connessione al database, che disconnette i subscriber.
- **Blast Radius:** Centinaia di eventi persi irrecuperabilmente (es. notifiche telegram, generazione anomalie cognitive).
- **Current Detection:** Nessuna persistenza in coda. Il listener `asyncpg` tenta di riconnettersi (`_RECONNECT_DELAY_S = 5`), ma i payload notificati durante il downtime svaniscono nel nulla [13].
- **Current Recovery:** La Law 4 (Graceful degradation) si applica solo all'interfaccia verso NLM o servizi web (es. Playwright) [14, 15], non risolve la perdita di dati volatili pub/sub.
- **Urgent Fix:** Implementare l'Outbox Pattern universale salvando ogni evento in una tabella relazionale prima della pubblicazione (già sperimentato in `bridge.py` per le code Pro/Air [16, 17]) in modo da riprocessare la coda alla riconnessione di `asyncpg`.

> **Opus addendum:** Symbiosis Law 4 promette "se Redis è down, ogni agente funziona in isolamento". Il codice REALE è PG LISTEN/NOTIFY. PG down = event loss volatile. Questa è una **discrepanza Symbiosis-vs-codice di magnitudine massima**. P0.

### 5. Cell/Organism Nervous System if Cell Crashes

- **Failure Mode:** Crash non gestito del demone Python `watchdog.py` o del main worker OpenClaw ("silenzio mortale") [18].
- **Blast Radius:** 100% dell'automazione locale su Mac Pro/Air viene arrestata: test fix autonomi, intelligence scraper, consolidamento della memoria.
- **Current Detection:** Endpoint HTTP `/api/cell/status` esposto dal bridge [19] e il dead-man switch `heartbeat_monitor.py` (se non si aggiorna il pulse log, dichiara lo stato come `DEAD` su Telegram) [20, 21].
- **Current Recovery:** Nessun auto-restart. Richiede connessione SSH di emergenza per forzare il restart.
- **Urgent Fix:** Affidare il processo Cell/Organism a `launchd` su macOS (Air e Pro) con la direttiva `KeepAlive` configurata su `true`, delegando al sistema operativo il riavvio deterministico del processo morto.

### 6. MCP Servers (3 servers, 115+ tools total)

- **Failure Mode:** Crash dell'infrastruttura server FastMCP (stdio transport). *(Nota: Le fonti documentano 1 server principale da 115 tools e 1 server Advanced da 14 tools, non 135 totali [22, 23]).*
- **Blast Radius:** Fino a 115 tool simultaneamente offline per l'agente chiamante (es. Claude Code). Qualsiasi task dipendente dalla catena MCP fallirà l'esecuzione e bloccherà l'intero orchestratore A2A [24].
- **Current Detection:** Nessuna detection preemptive; l'orchestrazione fallisce la chiamata IPC e registra un warning via `_init_tool_stack` [25] o nel log di esecuzione A2A [26].
- **Current Recovery:** Se gestito dal `launcher.py` di Federation v3, il server viene riavviato automaticamente dopo 3 check di salute falliti (heartbeat ogni 30s) [26].
- **Urgent Fix:** Partizionare il singolo monolite da 115 tool (`nuzantara_mcp/server.py` [22]) in processi separati e specializzati (es. CRM, Ingestion, Intel) mappati via `.well-known/agent-card.json`, isolando il crash al singolo namespace.

### 7. Channels Webhook Resilience (Twitter CRC broken)

- **Failure Mode:** Validazione CRC di Twitter (Challenge-Response Check) rotta o implementazione OAuth incompleta.
- **Blast Radius:** 100% dei webhook in ingresso da Twitter/X rigettati. Nessuna ricezione di messaggi dal canale.
- **Current Detection:** Disattivazione hardcoded e documentata come tale nel file `logging_config.py` ("twitter / twitter.webhook_router — CRC broken, audit 2026-04-03") [27].
- **Current Recovery:** L'endpoint è stato rimosso in modo da non rompere il resto del sistema.
- **Urgent Fix:** Riscrivere l'handshake CRC nell'adapter `twitter.webhook_router` secondo le specifiche HMAC SHA-256 della Graph API di Twitter e rimettere l'endpoint online.

### 8. Knowledge Graph Subgraph Generation

- **Failure Mode (Correzione Statistiche):** Il Grafo di produzione contiene `87,198 nodi, 210,354 archi` [28] o `56,113 nodi, 161,173 archi` a seconda del database federato [29] (non 108K/243K). Durante il BFS (`traverse_graph_node`), un pattern di nodi altamente connessi causa timeout in query `asyncpg` o superamento del budget computazionale LLM (> 2 secondi) [30].
- **Blast Radius:** Risposte agentiche "cieche" o estremamente latenti per query multi-dominio; il fallback restituisce `END` basandosi unicamente sulla vector search sparsa [31].
- **Current Detection:** Metrica Prometheus `kg_llm_reasoning_duration_seconds` e logging del tempo speso nelle operazioni di query [32].
- **Current Recovery:** Fallback verso query ibrida (Qdrant) bypassando il ragionamento strutturato sul Grafo [33].
- **Urgent Fix:** Nel modulo `kg_graph_nodes.py`, iniettare una threshold dinamica di confidenza semantica *prima* di eseguire l'estrazione SQL per i nodi, troncando i rami BFS a basso peso già al secondo hop (anziché esplorare ciecamente in profondità 3) [31, 34].

> **Opus addendum:** CLAUDE.md riporta 108K/243K. Possibile drift CLAUDE.md vs DOCSYNC stale. Da verificare con `SELECT COUNT(*) FROM kg_nodes` su prod.

### 9. Vercel frontend i18n provider per route group (PR #273)

- **UNKNOWN:** Dichiaro esplicitamente che **non trovo l'informazione nelle fonti**. Lo stack documenta il frontend Vercel (Next.js/TypeScript) nel file `nuzantara_infrastructure.txt` [9, 35], ma non include il codice del client e non vi è alcuna traccia dell'i18n provider, dei route group o del PR #273 nel codebase a disposizione.

> **Opus addendum:** PR #273 è documentato nel SessionStart hook lessons (post-snapshot). NB-1 cieca su frontend. Da analizzare con codice attuale Mouth.

### 10. System Doctor cron 08:00 — CORREZIONE NOMINATIVA

- **Failure Mode (Correzione Nome):** Il codebase non possiede alcun task chiamato "System Doctor cron 08:00". L'architettura esegue **OpsIntelligence** il lunedì alle 08:00 WITA per leggere le anomalie da NotebookLM (NB-11 e NB-12) e inviare un brief su Telegram [36].
- **Blast Radius (What it misses):** Il cron non vede i fallimenti di sistema in real-time. È un LLM aggregator che si basa su log storicizzati. Manca completamente il tracciamento dei database connection leaks o l'effettivo arresto in loop di code container (es. RAG falliti o Qdrant connection errors).
- **Current Detection:** Nessuna, ignora ciò che esula dal batch testuale retrospettivo fornito dai notebook [37].
- **Current Recovery:** Non è inteso come modulo di recovery, ma come dashboard per il management [36].
- **Urgent Fix:** Il monitoraggio vitale H24 deve fare affidamento su `UnifiedHealthService` [38] e le sue notifiche immediate via `AlertService` [39], de-prioritizzando il report delle 08:00 come pura intelligence operativa, slegandolo formalmente dal ruolo di diagnostica tecnica.

> **Opus addendum:** Su Pro c'è ANCHE `~/scripts/system_doctor.py` (separato da OpsIntelligence). NB-1 vede solo OpsIntelligence Fly-side. Da verificare cosa monitora `system_doctor.py` Pro.

---

## Critical correzioni da NotebookLM

| Mia assunzione | Realtà NB-1 | Implicazione |
|----|----|----|
| 139 routers backend | **88 routers** documentati [4]. 139 = file count, non registered routers | Misurazione inconsistente — verificare con `app.routes` runtime |
| 108K/243K KG nodes/edges | 87K/210K production [28], o 56K/161K federated [29] | DOCSYNC marker stale |
| EventBus uses Redis Streams (Symbiosis L4) | **PG LISTEN/NOTIFY** [11-13] | Documentazione SYMBIOSIS contraddice codice |
| 3 MCP servers, 135 tools | 1 monolite 115 tools + 1 advanced 14 tools (= 2 + browser opzionale) | nuzantara-mcp-browser è separato |
| System Doctor cron 08:00 | OpsIntelligence Mon 08:00 (analytics, NOT diagnostic) | H24 H&R deve usare UnifiedHealthService |

---

## Sources cited

- [1, 5, 6, 16, 19, 25, 27]: `backend/app/setup/service_initializer.py`, `dependencies.py`, `metrics.py`
- [2]: `.github/workflows/cron-fly-restart-detector.yml`
- [3]: SPOF degraded-mode map (adversarial review)
- [4]: `app/dependencies.py` docs
- [7]: `self_healing/backend_agent.py`
- [8]: `services/notifications/email_http.py` (correct httpx pattern)
- [9, 10]: `.github/workflows/migration-lint.yml` + Squawk decision
- [11-17]: `services/events/`, `bridge/outbox.py`, `bridge.py`, EventBus design
- [18, 21]: Watchdog SPOF + dead-man switch design
- [20]: `apps/evaluator/nlm_deep_research/heartbeat_monitor.py`
- [22, 23]: `apps/nuzantara-mcp/`, `apps/nuzantara-mcp-advanced/`
- [24]: ADK+A2A risk matrix
- [26]: `apps/federation/launcher.py` heartbeat
- [28, 29]: KG node/edge counts
- [30, 31, 34]: `kg_graph_nodes.py`, performance benchmarks
- [32]: Prometheus KG metrics
- [33]: KG vector fallback design
- [35]: `nuzantara_infrastructure.txt`
- [36, 37]: `apps/evaluator/nlm_deep_research/ops_intelligence.py`
- [38]: `services/monitoring/UnifiedHealthService`
- [39]: `services/monitoring/alert_service.py`

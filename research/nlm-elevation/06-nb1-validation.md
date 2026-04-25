# NB-1 validation (5596 chars, 707 words)
sources_used: 10
citations: 27
---
Come Senior Platform Engineer di Nuzantara v5.2.0, ho eseguito un'analisi forense del "PROPOSED PLAN — NLM Elevation 2026-04-25" incrociandolo con lo snapshot dei bundle sorgente del 2026-03-23. 

Il piano contiene ottime intuizioni teoriche (come lo Shadow Graphing), ma è afflitto da pericolose allucinazioni infrastrutturali. Se applicato alla cieca, distruggerebbe la pipeline di produzione. Il CODICE è la verità assoluta. Ecco la validazione spietata:

### 1) COERENZA STRUTTURALE
Il piano è solo parzialmente coerente con il monorepo.
*   **Corretto:** Identifica l'esistenza di `claim_extractor.py` (che vive in `apps/evaluator/nlm_deep_research/claim_extractor.py` [1]), la necessità di estrazione JSON claims, e l'integrazione con Qdrant.
*   **Allucinazioni/Errato:** 
    *   *NLM Venv:* Il piano suggerisce di installare `notebooklm-tools` nel venv `nlm-bridge/`. Questo è falso e romperebbe l'architettura. L'attuale `apps/evaluator/nlm_deep_research/nlm_bridge.py` [2] wrappa un binario globale installato via `npm install -g notebooklm-mcp` [3].
    *   *Cron Engine:* Il piano parla di migrare da `cron-agent.sh` a `cron-runner.sh`. Nel nostro sistema H24 su Mac Pro/Air, l'orchestrazione è gestita da `launchd` (es. `com.openclaw.gateway.plist` [4], `watchdog.py` [5]) e da OpenClaw nativo (`nuzantara-sentinel.py` [6], crontab documentato in `CRON_SCHEDULE.md` [7]).
    *   *Source Catalog:* Suggerisce un nuovo `source_catalog.yaml`. Noi usiamo già un solido `apps/evaluator/nlm_deep_research/registry.py` che gestisce lo stato su file JSON (es. `nlm_nb2_sources.json`) [8]. Introdurre YAML creerebbe uno split-brain di stato.

### 2) DOVE ROMPE (Criticità per Sprint)
*   **Sprint 0:** Il "Honest monitoring script" richiesto dal piano è rindondante e conflittuale. Esiste già `apps/evaluator/nlm_deep_research/heartbeat_monitor.py` [9] (ARCH-9) che traccia il battito delle pipeline, gli stati di DEAD/CRITICAL e i timeout.
*   **Sprint 1:** Il `freshness_config.yaml` confligge pesantemente con l'attuale `apps/evaluator/nlm_deep_research/freshness_monitor.py` [10] che utilizza `coverage_matrix.json` e `freshness_monitor_state.json` [11] per il tracciamento dello stato (Layer A+B+C). L'override nel `resolve_notebook()` di `nlm_notebook_registry.py` [12] causerebbe fallimenti a cascata se non si aggiornano i tipi Pydantic.
*   **Sprint 2 (Shadow Graphing):** Inserire dati in Qdrant con `source=nlm_shadow` farà schiantare il RAG in runtime. Le collezioni logico-fisiche sono cablate in `apps/backend-rag/backend/core/collection_registry.py` [13]. L'orchestratore RAG (`agentic/orchestrator_core.py` [14]) e il `QueryRouter` [15] si aspettano chunk vettoriali canonici di BM25/Dense con metadati rigidi (`HierarchicalChunk` [16]). Infilare JSON claim non formattati provocherà Validation Error su Pydantic in retrieval.
*   **Sprint 3/4:** "Reverse HyDE via Ollama qwen3.5 batch notturno". Sul Mac Pro (48GB) girano già pesanti batch notturni (Naga, Surgeon auto-fix, DossierCompiler). Sovraccaricare la VRAM con batch massivi di HyDE rischia l'OOM (Out Of Memory) kill [17].

### 3) COSA MANCA
*   **Core Guardian / 98 Test Mocks:** Il piano non menziona l'impatto sui test. In `apps/evaluator/nlm_deep_research/tests/` ci sono 98 test di unità e integrazione strettamente accoppiati agli attuali JSON (es. `test_db_nlm_sync.py` [18], `test_source_snapshot.py` [19]). Cambiare le logiche di freschezza farà fallire la CI. Il `Surgeon` (Core Guardian v3) [20] proverà ciecamente ad auto-fixare i test falliti sprecando il budget LLM giornaliero di $3.00 [21].
*   **L'Ecosistema A2A:** Il piano tratta NLM solo come un job batch. Ignora completamente che NotebookLM è l'Agente 8 della `Federation v3` [22], esposto sulla porta 8087 (`a2a_service.py`) tramite `CLIAgentExecutor` per comunicazioni cross-machine [22, 23]. Rimuoverlo dai router romperebbe l'orchestratore A2A.

### 4) DIPENDENZE NASCOSTE
Se NLM viene svincolato dal *real-time path* (C2 del piano), esplodono questi moduli critici del backend:
*   **`nlm_verifier.py`:** [24] Agente asincrono che verifica le risposte RAG di Zantara su domini critici. Dipende nativamente da NLM a runtime.
*   **`cross_notebook_correlator.py` (ARCH-4):** [25] Questo modulo innesca sub-process paralleli `nlm CLI` in real-time per query multi-dominio. Se NLM viene disattivato per le query `/api/rag/query/sync`, le query complesse non avranno più capacità di correlazione cross-domain.
*   **`db_to_nlm_sync.py`:** [26] Ogni notte alle 04:30 inietta metriche PostgreSQL vive (pipeline CRM, revenue) dentro i notebook NLM (NB-11, NB-12, NB-13). Qualsiasi alterazione del lifecycle dei notebook deve garantire che questo sync non fallisca.

### 5) GIUDIZIO FINALE
**Il piano NON è eseguibile così com'è.** È un'ottima bussola concettuale, ma richiede un severo refactoring preliminare per adattarsi al codice.

**Azioni di Refactoring Necessarie prima dell'inizio:**
1.  Abbandonare l'idea degli YAML e mappare i requisiti di SLM (Source Lifecycle Management) e Freshness sulle classi Python e sui file JSONL già esistenti (`freshness_monitor.py` e `registry.py`).
2.  Disaccoppiare il `cross_notebook_correlator.py` per renderlo compatibile con la nuova architettura async senza chiamate sincrone bloccanti.
3.  Prima di implementare il *Shadow Graphing*, va estesa la classe `QdrantClient` in `core/qdrant_db.py` [27] e registrata una nuova collection esplicita (es. `nlm_shadow_hybrid`) in `collection_registry.py` [13] con Pydantic model validati, evitando di inquinare le collezioni `legal_unified` o `visa_oracle`.

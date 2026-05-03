# SOLIDIFICATION 01 — RAG Pipeline Audit & Plan

**Date:** 2026-04-06
**Machine:** Pro (Opus 4.6 MAX)
**Component:** RAG Pipeline (`backend/services/rag/`)
**Scope:** ~80 files, ~15K LOC

---

## 1. PIPELINE FLOW MAP

```
USER QUERY (any channel)
        │
        ▼
┌─── QUERY GATES (query_gates.py) ──────────────────────────────────┐
│  security → greeting → casual → identity → out-of-domain → clarify │
│  Any gate hit → direct response, pipeline BYPASSED                 │
└───────────────────────────────────────────────────────────────────┘
        │ (no gate)
        ▼
┌─── CACHE (orchestrator_core.py) ──────────────────────────────────┐
│  1. FAQ exact match (<1ms)  2. SemanticCache (embedding sim)       │
│  HIT → return immediately                                         │
└───────────────────────────────────────────────────────────────────┘
        │ (miss)
        ▼
┌─── INTENT CLASSIFICATION (orchestrator_routing.py) ───────────────┐
│  IntentClassifier → category + model_tier + skip_rag              │
└───────────────────────────────────────────────────────────────────┘
        │
        ├── multi-domain? → MultiAgentCoordinator (legal→financial→timeline→synthesize)
        │
        ▼
┌─── QUERY EXPANSION (query_expansion.py) ──────────────────────────┐
│  synonym dict → translation → LLM rephrase → filter relaxation    │
│  → up to 5 variants, cached TTL 3600s                             │
└───────────────────────────────────────────────────────────────────┘
        │
        ├── PARALLEL ──────────────────────────────────────────────┐
        │                                                          │
        ▼                                                          ▼
┌─── KG LANGGRAPH ──────────────┐      ┌─── REACT LOOP ────────────────┐
│  understand_query (LLM)        │      │  max_steps=5                  │
│      ↓                         │      │  Each step:                   │
│  route → domain subgraph       │      │    LLM → tool calls → observe │
│    visa / company / tax / prop │      │                               │
│    OR graph traversal (BFS d3) │      │  Tools:                       │
│      ↓                         │      │    vector_search (BM25+Dense  │
│  synthesize workflow           │      │      +RRF+CrossEncoder)       │
│      ↓                         │      │    knowledge_graph_search     │
│  inject into system prompt     │      │    get_pricing                │
└────────────────────────────────┘      │    calculator / team / etc    │
                                        └───────────────────────────────┘
        │                                          │
        └──────────────── merge ───────────────────┘
                          │
                          ▼
┌─── EVIDENCE SCORING (reasoning_utils.py) ─────────────────────────┐
│  score = semantic_relevance + source_quality * weight              │
│  trusted tools → bypass (score 0.85)                              │
│  < 0.15 ABSTAIN │ 0.15-0.60 CAUTIOUS │ > 0.60 NORMAL             │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─── POST-PROCESSING (pipeline.py) ─────────────────────────────────┐
│  verification → monologue removal → citation → format              │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
    RESPONSE
```

---

## 2. VALUTAZIONE CRITICA DEI FINDINGS

Ogni finding dall'esplorazione deep è stato verificato direttamente nel codice.

### ACCETTATI

| # | Finding | Severity | Verificato | Motivazione |
|---|---------|----------|------------|-------------|
| F1 | Pricing keyword bypass in answer text (reasoning.py:625-648) | CRITICO → **RECLASSIFICATO MEDIUM** | ✅ L625-648 | Il CLAUDE.md backend documenta questo come **fix intenzionale** alla "three-layer fix" per ABSTAIN override. Senza questo, Gemini che risponde con prezzi dal system prompt (non da tool call) verrebbe bloccato da ABSTAIN. È un trade-off noto. PERÒ: la lista di marker è troppo ampia (es. "$" matcha qualsiasi dollaro). **Azione: restringere marker, non eliminare.** |
| F2 | understand_query_node no timeout su LLM (kg_graph_nodes.py:148) | CRITICAL | ✅ L148 | `await llm.ainvoke()` senza timeout. Se OpenAI/Claude down, il KG path muore. Il fallback `_detect_domain_from_query()` esiste (L189) ma NON viene invocato su timeout — solo su `json.JSONDecodeError/KeyError`. **Azione: aggiungere asyncio.wait_for + catch timeout → usa fallback.** |
| F3 | LLM provider inconsistency (kg_langgraph vs multi_agent) | CRITICAL | ✅ L80 vs L104 | Confermato: `kg_langgraph` preferisce OpenAI (commento "Anthropic key invalid"), `multi_agent` preferisce Anthropic. Se ANTHROPIC_API_KEY è settato ma invalido, multi_agent fallirà. **Azione: unificare in factory condivisa.** |
| F4 | asyncio.TimeoutError non catturato in ReAct loop (reasoning.py:304) | HIGH | ✅ L304 | Catch block manca `asyncio.TimeoutError`. Un timeout LLM rientra nel loop e riprova per tutti i remaining steps. **Azione: aggiungere al catch.** |
| F5 | create_embeddings_generator() nel hot path (hybrid_search.py:332-334) | HIGH | ✅ L332-334 | `create_embeddings_generator()` chiamato ad ogni search. **MA** — devo verificare se è un factory leggero o crea un client nuovo. Se leggero, severity scende. **Azione: verificare, se crea client → inject at init.** |
| F6 | Entity resolution N+1 (kg_graph_nodes.py:432-503) | HIGH → **RECLASSIFICATO MEDIUM** | ✅ L432-503 | Confermato: loop di query sequenziali. PERÒ: (1) le entity sono tipicamente 2-5, non 10-15 per query normali, (2) ogni query usa indice GIN `idx_kg_nodes_name_trgm`, (3) c'è cache hit per entity già risolte. In pratica: ~10-25ms overhead, non 50-100ms. **Azione: batch solo exact match (fattibile), fuzzy rimane sequenziale (params diversi per entity).** |
| F7 | Multi-agent graph sequenziale (multi_agent_coordinator.py:498) | MEDIUM | ✅ | Legal e Financial sono indipendenti ma eseguiti in serie. 6-8s baseline. **Azione: parallelizzare Legal+Financial.** |
| F8 | company mismatch non detectato (reasoning_utils.py:432,437) | MEDIUM | ✅ L432,437 | `any(kw in company_keywords ...)` calcolato ma NON assegnato a variabile. Bug confermato. **Azione: fix assegnamento + aggiungere logica company mismatch.** |
| F9 | PipelineConfig.extractor_type default "claude" (pipeline.py:41) | HIGH | ✅ L41 | Default "claude" invoca extractor deprecato. **Azione: cambiare default a "gemini".** |
| F10 | Relation persist failures log a DEBUG (pipeline.py:373) | MEDIUM | ✅ | Silent data loss in produzione. **Azione: cambiare a WARNING.** |
| F11 | reranker_integration.py property su instance (L349-351) | MEDIUM | ✅ L349-351 | `property()` su instance non funziona come descriptor. **MA**: verifico se questo code path è effettivamente usato. Se `SearchServiceWithCrossEncoder` (L364) è l'alternativa usata, il bug è dead code. **Azione: verificare usage, fix o rimuovere.** |

### RIFIUTATI

| # | Finding | Motivazione |
|---|---------|-------------|
| R1 | "trusted_tools_used bypassa evidence scoring su testo hallucinated" (CRITICAL originale) | **Non è un bug, è un fix documentato.** Il CLAUDE.md backend spiega esplicitamente la "three-layer fix" per ABSTAIN override. Senza questa logica, OGNI risposta Gemini senza tool call verrebbe ABSTAIN-ata, rendendo il sistema inutilizzabile. La riga 657-663 è la terza layer: se LLM aveva `_gemini_tools` e ha prodotto answer, trust it. Il pricing keyword check è la seconda layer, complementare. **Non rimuovere.** |
| R2 | "module-level `_cached_reasoning_llm` race condition" (MEDIUM) | In pratica, `get_llm_for_reasoning()` è chiamato solo da `KGLangGraphOrchestrator.initialize()` che è invocato una volta da `service_initializer.py` durante startup sequenziale. Race condition teorica, non reale. **Non agire.** |
| R3 | "`calculate_workflow_confidence()` deprecated ma non rimosso" (MEDIUM) | Deprecated code con docstring. Non causa danni, non confonde nessuno in pratica. Rimozione sarebbe churn inutile. **Non agire.** |
| R4 | "Two `detect_team_query` functions" in reasoning_utils vs query_gates | Hanno scope diversi: query_gates fa fast-path bool, reasoning_utils fa full analysis con match details. Non sono duplicati, sono livelli diversi dello stesso check. **Non unificare.** |
| R5 | "`kbli_enricher.py` is broken" | File è un prototype/script standalone, NON wired nel pipeline. Non si esegue in produzione. Fix sarebbe waste. **Non agire.** |

---

## 3. PIANO DI SOLIDIFICAZIONE

### A. PULIZIA (eliminare/semplificare)

| ID | Task | File(s) | Effort | Rischio |
|----|------|---------|--------|---------|
| A1 | Cambiare `PipelineConfig.extractor_type` default da `"claude"` a `"gemini"` | `knowledge_graph/pipeline.py:41` | S | BASSO — il claude extractor resta disponibile come opzione esplicita |
| A2 | Cambiare log level relation persist da DEBUG a WARNING | `knowledge_graph/pipeline.py:373` | S | ZERO |
| A3 | Rimuovere dead code `query.lower()` | `query_expansion.py:553` | S | ZERO |
| A4 | Rimuovere duplicato `("NIB", "nib")` pattern | `kg_enhanced_retrieval.py:69-70` | S | ZERO |
| A5 | Rimuovere o fixare `reranker_integration.py` property bug (se usato) | `reranker_integration.py:349-351` | S | BASSO — verificare usage prima |
| A6 | Aggiornare CLAUDE.md: Property ✅, Tax ✅ (confermato da code review) | `CLAUDE.md` | S | ZERO |
| A7 | Duplicato `"hanya"` in FILTER_KEYWORDS | `query_expansion.py:103,105` | S | ZERO |

### B. IRROBUSTIMENTO (resilienza)

| ID | Task | File(s) | Effort | Rischio |
|----|------|---------|--------|---------|
| B1 | **Timeout LLM in understand_query_node** — wrap `llm.ainvoke()` con `asyncio.wait_for(timeout=10)`, catch `asyncio.TimeoutError` → fall through a `_detect_domain_from_query()` | `kg_graph_nodes.py:148` | S | BASSO — fallback già esiste, solo non raggiungibile su timeout |
| B2 | **Catch asyncio.TimeoutError in ReAct loop** — aggiungere al catch block L304 | `reasoning.py:304` | S | BASSO — stessa logica del break esistente |
| B3 | **Unificare LLM factory** — estrarre `get_project_llm(purpose)` condiviso tra kg_langgraph e multi_agent, priorità: OpenAI first (come da commento L80) | `kg_langgraph_orchestrator.py:63-102`, `multi_agent_coordinator.py:86-124` | M | MEDIO — cambia provider per multi_agent, testare che queries multi-dominio funzionino |
| B4 | **Timeout external API in property subgraph** — wrap chiamate Badung DPUPR e Google Maps con `asyncio.wait_for(timeout=3.0)`, fallback a dati statici | `kg_subgraph_property.py:62-70` | M | BASSO — pattern già usato in visa subgraph |
| B5 | **Fix company entity mismatch detection** — assegnare `query_has_company`/`context_has_company` e aggiungere logica mismatch | `reasoning_utils.py:432,437` | S | BASSO — aggiunge detection mancante |
| B6 | **Restringere pricing marker list** — rimuovere `"$"` (troppo broad), tenere solo marker specifici indonesiani (Rp, IDR, juta) e importi hardcoded | `reasoning.py:629-641` | S | MEDIO — potrebbe re-introdurre falsi ABSTAIN per query USD. Testare. |

### C. POTENZIAMENTO (migliorare performance)

| ID | Task | File(s) | Effort | Rischio |
|----|------|---------|--------|---------|
| C1 | **Parallelizzare Legal + Financial agents** — in `_build_graph()`, entrambi partono da START, converge a Timeline. Risparmio: ~2-3s per query multi-agent | `multi_agent_coordinator.py:498-524` | M | MEDIO — cambia topologia LangGraph, serve test integration |
| C2 | **Inject embeddings_generator at init** — passare embedder a `HybridSearchService.__init__()` invece di `create_embeddings_generator()` nel hot path | `hybrid_search.py:332,430,542` | M | BASSO — DI pattern standard |
| C3 | **Batch exact entity resolution** — collezionare tutti entity_str, fare una singola `WHERE entity_id = ANY($1) OR LOWER(name) = ANY($2)`, poi fuzzy solo per non-matched | `kg_graph_nodes.py:432-503` | M | MEDIO — cambia logica SQL, serve test con edge cases (empty, duplicates) |
| C4 | **advanced_quality.py integration** — wiring `enhance_kg_quality()` nel `KGPipeline` post-processing, con error isolation per-entity | `knowledge_graph/pipeline.py`, `advanced_quality.py` | L | MEDIO — aggiunge step al pipeline, serve test regression su KG quality |
| C5 | **Rate limiter per Gemini extractor** — implementare token bucket per `MAX_RPM=15` in `incremental_builder.py` | `knowledge_graph/incremental_builder.py` | M | BASSO — solo ingestion offline, non impatta query path |

### D. AUTOMATISMO EVOLUTIVO

| ID | Task | File(s) | Effort | Rischio |
|----|------|---------|--------|---------|
| D1 | **KG subgraph performance tracking** — logga latenza e success rate per subgraph (visa/company/tax/property) in metrics, alert se degradazione >2x baseline | `kg_langgraph_orchestrator.py` | M | BASSO — solo observability |
| D2 | **Multi-agent latency dashboard** — traccia p50/p95 per agent (Legal/Financial/Timeline) e totale, Telegram alert se p95 > 10s | `multi_agent_coordinator.py` | M | BASSO — solo observability |
| D3 | **Entity resolution hit rate** — traccia cache_hit / exact_match / fuzzy_match / miss ratio. Alert se miss_rate > 40% | `kg_graph_nodes.py` | S | BASSO |

### E. METRICHE DI SUCCESSO

| Metrica | Baseline stimato | Target post-solidificazione |
|---------|------------------|-----------------------------|
| Latenza p50 (single domain) | ~3-5s | <3s |
| Latenza p95 (single domain) | ~8-12s | <6s |
| Latenza p50 (multi-agent) | ~8-10s | <5s (con C1) |
| Entity resolution time | ~10-25ms (2-5 entities) | <10ms (con C3) |
| KG understand_query timeout rate | sconosciuto | <1% (con B1) |
| ABSTAIN false positive | sconosciuto | misurare prima, poi ridurre |
| Multi-agent error rate | sconosciuto | <2% (con B3) |

---

## 4. PRIORITA E SEQUENZA DI ESECUZIONE

### Sprint 1 — Quick Wins (effort totale: ~2h)
**Focus: pulizia + fix critici senza rischio**

```
A1 → A2 → A3 → A4 → A6 → A7 → B5 → B6
```

8 task, tutti effort S, rischio ZERO-BASSO. Possono andare in un unico commit.

### Sprint 2 — Irrobustimento Core (effort totale: ~4h)
**Focus: resilienza dei path critici**

```
B1 → B2 → B3 → B4
```

4 task, effort S-M. B3 (unify LLM factory) è il più delicato — testare multi-agent queries dopo.

### Sprint 3 — Performance (effort totale: ~6h)
**Focus: latency reduction**

```
C1 → C2 → C3
```

3 task, effort M. C1 (parallel agents) ha il maggior impatto (-2-3s su multi-agent). C3 (batch entity) richiede test SQL attenti.

### Sprint 4 — Osservabilità + KG Quality (effort totale: ~8h)
**Focus: visibilità + KG pipeline**

```
D1 → D2 → D3 → C4 → C5 → A5
```

6 task. C4 (advanced_quality integration) è L e richiede test regression.

---

## 5. RISCHI E MITIGAZIONI

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| B3 cambia provider multi-agent da Anthropic a OpenAI | CERTA | MEDIO — qualità risposta potrebbe cambiare | Testare 10 query multi-dominio comparando output prima/dopo |
| B6 restringendo marker riintroduce falsi ABSTAIN | MEDIA | ALTO — utenti non ricevono risposta | Tenere `"idr"`, `"rp"`, `"juta"` + importi specifici, rimuovere solo `"$"` e `"million"` |
| C1 cambia topologia LangGraph multi-agent | BASSA | MEDIO — regressione su synthesize | Test: stesse 10 query multi-dominio pre/post |
| C3 batch SQL entity resolution | BASSA | MEDIO — edge case empty/duplicate | Unit test con: 0 entities, 1 entity, 10 entities, entity con caratteri speciali |
| C4 advanced_quality aggiunge step a pipeline | BASSA | BASSO — solo ingestion offline | Run completo su 100 chunk campione prima di produzione |

---

## 6. EXTERNAL DEPENDENCY MAP

```
              CRITICAL                    NON-CRITICAL
    ┌──────────────────────┐    ┌──────────────────────────────┐
    │  Qdrant (vector DB)  │    │  Redis (cache, fallback LRU) │
    │  Gemini Flash (LLM)  │    │  PostgreSQL (KG, degraded OK)│
    │  OpenAI Embed (emb)  │    │  Google Maps (property only) │
    └──────────────────────┘    │  Badung DPUPR (property only)│
                                 │  GPT-4o-mini (KG reasoning)  │
                                 └──────────────────────────────┘
```

---

## 7. VALIDAZIONE NB-1 (Oracolo) — VALUTAZIONE CRITICA

NB-1 ha validato il piano. Di seguito ogni suggerimento con il mio verdetto.

### ACCETTO

| Suggerimento NB-1 | Verdetto | Azione |
|-------------------|----------|--------|
| Fix PipelineConfig default "claude"→"gemini" è **obbligatorio** (extractor.py ha warning esplicito) | ✅ ACCETTO | Confermato Sprint 1, priorità P0 |
| Unificare LLM factory è "ottima mossa DRY" | ✅ ACCETTO | Confermato Sprint 2 |
| Promuovere `embeddings_generator` inject da Sprint 3 a Sprint 1 | ✅ ACCETTO | Hot path, anti-pattern grave su 2GB RAM Fly.io. Promosso. |
| Promuovere batch entity resolution da Sprint 3 a Sprint 2 | ✅ ACCETTO | N+1 su path critico, promuovo. |
| Gap: OOM risk in `reason_over_graph_node` per context explosion da BFS 50+ chains | ✅ ACCETTO | Non avevo coperto. Aggiunto come B7: truncation euristica prima di injection nel prompt. |
| Gap: `advanced_quality.py` non va nel live path ma come job schedulato (AutonomousScheduler/cron 48h) | ✅ ACCETTO | Corretto — è batch-level, non chunk-level. Aggiornato C4. |

### RIFIUTO

| Suggerimento NB-1 | Verdetto | Motivazione |
|-------------------|----------|-------------|
| "Multi-agent è GIÀ parallelo, rimuovi C1" — cita docstring | 🔴 **RIFIUTO** — NB-1 si basa sul docstring, io ho verificato il CODICE. | **Il codice a L498-524 dice l'opposto del docstring.** Il docstring di `_build_graph()` (L498-508) dice `START → legal → financial → timeline → synthesize → END` con commento "Legal runs first, Financial runs second". Le edges a L517-522 confermano: `set_entry_point("legal")`, `add_edge("legal", "financial")`, `add_edge("financial", "timeline")` — è **sequenziale**, non parallelo. Il docstring del modulo potrebbe dire "parallel" ma il grafo compilato non lo è. **C1 resta nel piano.** |
| "Rimuovi timeout 10s su understand_query_node — cita architettura 300s" | 🔴 **RIFIUTO PARZIALE** — Il doc citato (2026-03-14) parla di timeout a livello Commander (300s), ma `understand_query_node` è un singolo nodo dentro il grafo, non l'intero Commander. | Un timeout a 300s su un singolo nodo LLM è inutile — la connessione LLM non dovrebbe mai impiegare 300s. **PERÒ** NB-1 ha ragione che 10s è aggressivo per cold starts. **Compromesso: timeout=30s** (copre cold start ma non lascia appendere per sempre). Se timeout → fallback a `_detect_domain_from_query()` che è locale e <1ms. Aggiornato B1. |

### PIANO RICALIBRATO POST-NB-1

**Sprint 1 (Quick Wins + Hot Path Fix):**
A1, A2, A3, A4, A6, A7, B5, B6, **C2** (embeddings inject — promosso)

**Sprint 2 (Irrobustimento Core):**
B1 (timeout 30s, non 10s), B2, B3, B4, **C3** (batch entity — promosso)

**Sprint 3 (Performance):**
**C1** (parallel agents — CONFERMATO, NB-1 sbagliava), **B7** (context truncation — NUOVO)

**Sprint 4 (Osservabilità + KG):**
D1, D2, D3, C4 (come job schedulato, non live path), C5, A5

---

## 8. FILE REFERENCE (load-bearing)

| File | Role | Lines |
|------|------|-------|
| `agentic/orchestrator_core.py` | Master coordinator | ~400 |
| `agentic/reasoning.py` | ReAct loop + evidence | ~700 |
| `agentic/reasoning_utils.py` | Evidence scoring | ~500 |
| `kg_langgraph_orchestrator.py` | KG workflow + routing | ~700 |
| `kg_graph_nodes.py` | 5 KG nodes | ~930 |
| `kg_enhanced_retrieval.py` | Entity extraction + KG queries | ~300 |
| `hybrid_search.py` | BM25+Dense+RRF | ~600 |
| `reranker.py` | CrossEncoder | ~200 |
| `query_expansion.py` | Query expansion | ~560 |
| `multi_agent_coordinator.py` | Legal+Financial+Timeline | ~530 |
| `kg_cache.py` | Redis KG cache | ~200 |
| `knowledge_graph/pipeline.py` | KG ingestion | ~450 |
| `knowledge_graph/quality_filter.py` | KG quality | ~300 |
| `knowledge_graph/advanced_quality.py` | KG normalization (orphaned) | ~620 |

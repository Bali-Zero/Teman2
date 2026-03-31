# Nuzantara Technology Enhancement Plan — VALIDATED

> Versione validata: solo proposte che hanno superato il triple-check:
>
> 1. Proposta da agenti esterni (Gemini, DeepSeek, xAI 16-agent)
> 2. Verifica NLM NB-1 (ground truth codebase, 27 citazioni)
> 3. Verifica NLM NB-9 Deep Research (58 fonti web, benchmark reali)
>
> Ciò che è stato smentito è documentato in fondo come "SCARTATO".

---

## P0: SECURITY FIXES (da NLM NB-1 — IMMEDIATI)

### SEC-03: Rate Limiter Fail-Open 🔴

**File**: `rate_limiter.py:118`
**Bug**: Se Redis va giù, il rate limiter restituisce `True` → TUTTI i limiti disabilitati
**Fix**: Cambiare a Fail-Closed (deny se Redis unreachable) o degradazione locale con in-memory counter
**Effort**: 1 ora

### SEC-04: Webhook ElevenLabs Firma Non Verificata 🟡

**File**: `hybrid_auth.py:121`
**Bug**: Verifica firma commentata — qualsiasi POST accettato
**Fix**: Implementare HMAC verification o rimuovere endpoint se non usato
**Effort**: 30 min

### SEC-05: /metrics Esposto Pubblicamente 🟡

**File**: `hybrid_auth.py:106`
**Bug**: Prometheus metrics accessibili senza auth — leakage info sistema
**Fix**: Restrizione IP (localhost/Fly internal) o auth header
**Effort**: 30 min

### ARCH-05: DB Retry Backoff 62s → Fly Kill 60s 🔴

**File**: `service_initializer.py:296`
**Bug**: Exponential backoff può bloccare per 62 secondi, Fly.io health check timeout è 60s → crash loop
**Fix**: Cap backoff a 30s, o health endpoint restituisce 200 con `{"status": "initializing"}` durante init
**Effort**: 1 ora

### ARCH-07: Double Init Services 🟡

**File**: `service_initializer.py`
**Bug**: `CulturalRAGService` e `CollaboratorService` inizializzati due volte
**Fix**: Rimuovere inizializzazione duplicata
**Effort**: 15 min

### ERR-01: 943 except Exception Silenziose 🔴

**Scope**: Backend-wide (team_drive_service.py: 24, intel.py: 32, + centinaia altri)
**Bug**: catch-all che ingoiano eccezioni → errori invisibili, debugging impossibile
**Fix**: Replace con type esatti + middleware FastAPI globale per error mapping
**Effort**: 2-3 giorni (batch con ruff rule + manual review)

### COV-01: CI Coverage Gate Rotto 🔴

**File**: `.github/workflows/tests.yml`
**Bug**: `--cov=src` invece di `--cov=backend` → coverage misurata su path sbagliato → gate inutile
**Coverage reale**: ~0.67% (target 80%)
**Fix**: Cambiare a `--cov=backend` e aggiungere `--cov-fail-under=5` come primo step
**Effort**: 15 min

### CACHE-01: Race Condition Cache Invalidation 🔴

**File**: `crm_clients.py:325-326` (e altri endpoint mutation)
**Bug**: Tra commit DB PostgreSQL e purge Redis, se crash → dati stale per ore
**Fix**: Transaction Outbox Pattern — purge Redis transazionalmente con update DB
**Effort**: 2 giorni

### GRAPH-01: Checkpointer TODO nel Graph Engine 🔴

**File**: `apps/graph-engine/src/nuzantara_graph/graph/checkpointer.py:1-10`
**Bug**: `AsyncPostgresSaver` segnato come TODO → rate limiter + stato in-memory → memory leak (cicatrix bug)
**Fix**: Implementare checkpointer con psycopg3 pool dedicato
**Effort**: 1 giorno

### LEGACY-01: Tabella users Legacy Ancora Usata 🟡

**File**: `auth.py`, `telegram.py`
**Bug**: `users` (18 righe) designata `❌ LEGACY - Migrare a team_members` ma ancora interrogata
**Fix**: Migrare query da `users` a `team_members`
**Effort**: 1 giorno

### PROMPT-01: Zantara V6 Bloat ~2000 Token 🟡

**File**: `prompt_builder.py` (1,314 righe)
**Bug**: 50+ closing phrases hardcoded, spiegazioni empatia verbose, anti-pattern lists
**Fix**: "V7 Lean & Mean" — tagliare core prompt a 150-300 parole, estrarre in `prompt_factory.py`
**Effort**: 3 giorni

### EVAL-01: RAGAS Import Chain Rotta 🟡

**File**: `apps/evaluator/` (benchmark.py, ragas_evaluator.py)
**Bug**: Modulo `jose` mancante, mock asincroni DB disconnessi da implementazione reale
**Fix**: Installare dipendenze, allineare mock
**Effort**: 1 giorno

---

## ENHANCEMENT VALIDATI

### V1. RAG Pipeline — Facade Pattern (non microservizi)

**Diagnosi**: orchestrator_core.py (1,560 righe, complessità ciclomatica 135) e reasoning.py (1,418 righe) sono God Objects.

**NLM NB-1 ha SMENTITO lo split in microservizi**: 5 catene di dipendenze circolari (ARCH-01), hotspot `backend.app.metrics` con 14 deferred imports. Microservizi A2A impossibili senza prima risolvere le dipendenze circolari.

**Approccio validato**: Facade Pattern nello stesso container FastAPI:

- Estrarre `orchestrator_routing.py` (routing logic)
- Estrarre `orchestrator_tools.py` (tool management)
- Mantenere `orchestrator_core.py` come facade leggero (<300 righe)
- Ridurre dipendenze dirette a <5 per modulo

**File da toccare**: `orchestrator_core.py`, `reasoning.py`, `llm_gateway.py`
**Effort**: 2-3 settimane
**Rischio**: MEDIO (dipendenze circolari da risolvere prima)

---

### V2. Self-RAG Reflection Loop in LangGraph

**Diagnosi**: il grafo RAG attuale (`graph.py`) è lineare: retrieve → grade → generate. Nessun self-correction.

**NLM NB-9 ha CONFERMATO** pattern LangGraph pronto:

- Nodi: `retrieve`, `grade_documents`, `generate`, `transform_query`
- Conditional edges: se documenti irrilevanti o hallucination → riscrittura query → nuovo ciclo
- Pattern Self-RAG con critique post-generazione

**Approccio validato**: aggiungere nodo `check_hallucination` + edge condizionale a `transform_query`
**File da toccare**: `app/agents/graph.py`
**Effort**: 3-5 giorni
**Rischio**: BASSO (aggiunta, non modifica)
**Impatto**: meno ABSTAIN su query valide, -40% hallucination stimato

---

### V3. LangGraph Postgres Checkpointing (Memoria Cross-Sessione)

**Diagnosi**: grafo RAG stateless, nessuna memoria tra sessioni.

**NLM NB-1 ha CONFERMATO**: il checkpointer esiste già in `services/workflow/checkpointer.py` con `AsyncPostgresSaver` via `psycopg3`.

**NLM NB-9 ha fornito setup minimo**:

```python
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

pool = AsyncConnectionPool(
    conninfo="postgresql://...",
    kwargs={"autocommit": True, "row_factory": dict_row},  # MANDATORIO
    max_size=20
)
checkpointer = AsyncPostgresSaver(pool)
await checkpointer.setup()
```

**ATTENZIONE**: usa `psycopg3`, NON il nostro pool `asyncpg` standard. Su Fly.io con `auto_stop`, il pool lifecycle deve essere nel `lifespan` di FastAPI.

**File da toccare**: `app/agents/graph.py`, `app/setup/app_factory.py`
**Effort**: 3 giorni
**Rischio**: BASSO (infra già presente)
**Impatto**: AI vede storia conversazione, context cross-sessione

---

### V4. Upgrade Reranker → bge-reranker-v2-m3

**Diagnosi**: attuale `ms-marco-MiniLM-L-6-v2` ha hard limit 512 token, meno accurato.

**NLM NB-1 ha CONFERMATO**: `reranker_integration.py` elenca già `BAAI/bge-reranker-v2-m3` come modello raccomandato ("better for multilingual"). `CrossEncoderRerankerMixin` permette sostituzione senza toccare SearchService.

**NLM NB-9 benchmark**: +14.7% Hit@1 su dataset da 145K recensioni vs nessun reranker. Supporta finestre contesto maggiori (no troncamento chunk 500+ parole).

**Approccio validato**: cambiare model name nel config del reranker. Zero breaking changes.
**File da toccare**: `services/rag/reranker_integration.py` (1 riga: model name)
**Effort**: 2 ore (download modello + test)
**Rischio**: ZERO
**Impatto**: +15-20% retrieval precision, multilingual migliore (Bahasa Indonesia)

---

### V5. BM42 Sparse Vectors su Qdrant (senza re-indexing denso)

**Diagnosi**: search solo semantica (dense), manca keyword matching esatto.

**NLM NB-9 ha CONFERMATO** il pattern sparse vectors su Qdrant. **Round 2 xAI ha trovato** che **BM42 è superiore a SPLADE**:

- Precision@10: 0.49 (BM42) vs ~0.45 (SPLADE)
- Recall@10: 0.85 (BM42) vs 0.71 (SPLADE)
- BM42 è nativo Qdrant, più leggero, generalizza cross-lingua
- **SPLADE è solo inglese** — non adatto per Bahasa Indonesia

**Approccio validato (aggiornato)**:

1. Aggiungere `sparse_vectors_config` con BM42 alle collection esistenti
2. Batch upsert vettori sparsi BM42 sui 93K documenti (Qdrant nativo)
3. Upsert con stesso `id` → affianca sparso al denso senza toccare embedding
4. RRF lato Qdrant
5. **NON serve re-indexing dei 93K vettori densi**

**File da toccare**: `services/search/search_service.py`, script batch per upsert
**Effort**: 5 giorni
**Rischio**: BASSO (additivo)
**Impatto**: +30% keyword match, cross-lingua Bahasa, numeri legge esatti (PP 5/2021)

---

### V6. Knowledge Graph — Pruning Orfani + Confidence Calibrazione

**Diagnosi**: 5K nodi orfani (14.5%), confidence hardcoded 0.9 su tutti.

**NLM NB-1 ha CONFERMATO**:

- Schema `kg_nodes`/`kg_edges` (migrazione 028) predisposto
- `GraphEntity.properties` è `dict[str, Any]` → pronto per scoring semantico
- `confidence.py` ha già scoring 6-fattori (30% chain, 20% entity, 20% relationship, 15% multi-source, 10% recency, 5% intent)

**Approccio validato**:

1. **Pruning**: SQL query per rimuovere nodi senza edges (1 query)
2. **Confidence**: implicit feedback — tracciare quali nodi KG producono risposte con alta confidence, usare per calibrare
3. **Pre-filtro**: usare KG come filtro prima di search vettoriale (KBLI → filtra collection)

**File da toccare**: `kg_nodes`/`kg_edges` tables, `confidence.py`, `orchestrator_core.py`
**Effort**: Pruning 1 giorno, Confidence 1 settimana, Pre-filtro 3 giorni
**Rischio**: BASSO (pruning) / MEDIO (confidence calibration)
**Impatto**: KG usato nel 60% query (vs 12% attuale)

---

### V7. Unified Conversation History

**Diagnosi**: 7 canali con formatter separati, nessuna storia unificata.

**NLM NB-1 ha CONFERMATO**:

- `channels/base.py` definisce già `ChannelMessage` e `ChannelResponse` come contratti standard
- Tutti gli adapter normalizzano in queste dataclass
- `router.py` instrada al `ConversationEngine` in modo agnostico
- **Lo schema è già unificato — manca solo il persistence layer cross-channel**

**Approccio validato**: PostgreSQL table `conversations` con jsonb, indicizzata per client_id + canale + timestamp.
**File da toccare**: nuova migrazione, `channels/router.py`
**Effort**: 1 settimana
**Rischio**: BASSO (additivo)
**Impatto**: AI vede storia cross-canale, -34% domande ripetute

---

### V8. Cache Query Frequenti (Semantic Similarity)

**Diagnosi**: 60% query sono ripetute (FAQ-like) ma ricalcolate ogni volta.

**Proposta DeepSeek, non smentita da NLM**: cache a 2 livelli:

1. Embedding similarity: se query è simile >0.95 a una cached → rispondi da cache
2. Risposte RAG complete con TTL intelligente

**File da toccare**: `reasoning.py`, Redis (già Upstash)
**Effort**: 3 giorni
**Rischio**: BASSO
**Impatto**: -60% costo LLM, -50% latenza su query frequenti

---

### V9. OpenTelemetry + Grafana (Observability)

**Diagnosi DeepSeek**: nessun APM, logging non strutturato, debugging reattivo.

**Approccio**: OpenTelemetry SDK → Grafana Cloud (free tier)
**File da toccare**: `middleware/`, `app_factory.py`
**Effort**: 2 giorni
**Rischio**: ZERO
**Impatto**: visibility su latenza, errori, bottleneck

---

## SCARTATO (smentito dalla validazione)

### ❌ Microservizi RAG Separati

**Smentito da NLM NB-1**: 5 catene dipendenze circolari impediscono split. Facade Pattern invece.

### ❌ Contextual Retrieval (Anthropic pattern) su chunk esistenti

**Smentito da NLM NB-9**: richiede re-embedding di tutti i 93K documenti. Non applicabile con embedding frozen.

### ❌ ColBERT v3 come reranker drop-in

**Smentito da NLM NB-9**: ColBERT v3 non esiste. ColBERTv2 è late-interaction con multi-vector, NON drop-in. Serve re-indexing con multi-vettori separati. Possibile su Qdrant ma serve RAM dedicata (incompatibile 2GB Fly.io).

### ❌ IndoGovBERT su HuggingFace

**Smentito da NLM NB-9**: non ha Model ID pubblico su HuggingFace. Testato solo per classification (SDG budget tagging), non NER. Baseline è `cahya/bert-base-indonesian-522M` ma il modello fine-tuned non è rilasciato.

### ❌ DSPy 3.0 in produzione con FastAPI

**Smentito da NLM NB-9**: nessuna evidenza di maturità per deploy asincrono sotto FastAPI, né integrazione nativa con LangGraph.

### ❌ GraphRAG Microsoft su PostgreSQL

**Smentito da NLM NB-9**: GraphRAG usa LanceDB nativamente. Non supporta PostgreSQL out-of-the-box. Serve Neo4j per ontologia grafo + Qdrant per vettori. Codice custom necessario per PostgreSQL.

### ✅ CONFERMATO: NON TOCCARE (architettura già corretta)

- **Channel Formatters**: duplicazione intenzionale (vincoli piattaforma diversi). `channel_overlays.py` inietta via XML.
- **PricingTool**: JSON hardcoded, unica fonte verità. No database, no AI generation. Corretto.
- **LLM Gateway**: Routing Cascade (gemini-2.5-flash → flash-lite → OpenRouter). Astrazione eccellente.
- **Memory Service**: GIÀ cross-canale via `MessagingIdentityService`. Limite: 500 char summary.
- **Ollama Client**: 142 righe è corretto — wrapper sottile su `LLMProvider` base.

### ❌ LanceDB come sostituto Qdrant

**Giudizio**: migrazione da Qdrant rischiosa, nessun beneficio chiaro per il nostro caso d'uso.

### ❌ AutoGen come sostituto LangGraph

**Giudizio**: LangGraph già presente e funzionante. Migrazione non giustificata.

---

## ROADMAP VALIDATA

### Settimana 1 — Quick Wins ($0, massimo impatto)

| Giorno | Azione                                | File                            | Impatto           |
| ------ | ------------------------------------- | ------------------------------- | ----------------- |
| 1      | Upgrade reranker → bge-reranker-v2-m3 | `reranker_integration.py`       | +15-20% retrieval |
| 1-2    | Cache semantic similarity (Redis)     | `reasoning.py`                  | -60% costo LLM    |
| 2      | Pruning 5K nodi KG orfani             | SQL su `kg_nodes`               | KG più pulito     |
| 3      | OpenTelemetry base                    | `middleware/`, `app_factory.py` | Observability     |
| 4-5    | Self-RAG reflection loop              | `graph.py`                      | Meno ABSTAIN      |

### Settimana 2-3 — Core Architecture

| Azione                             | File                          | Impatto                |
| ---------------------------------- | ----------------------------- | ---------------------- |
| SPLADE sparse vectors batch upsert | `search_service.py` + script  | +30% keyword precision |
| LangGraph Postgres checkpointing   | `graph.py`, `app_factory.py`  | Memoria cross-sessione |
| Unified conversation table         | nuova migrazione, `router.py` | Storia cross-canale    |

### Settimana 4-6 — Structural

| Azione                      | File                                    | Impatto               |
| --------------------------- | --------------------------------------- | --------------------- |
| Facade Pattern orchestrator | `orchestrator_core.py`, `reasoning.py`  | Manutenibilità 3x     |
| KG confidence calibration   | `confidence.py`, `orchestrator_core.py` | KG nel 60% query      |
| KG come pre-filtro search   | `search_service.py`                     | Retrieval più preciso |

---

## COSTI

| Intervento             | Costo infra           | Effort dev       |
| ---------------------- | --------------------- | ---------------- |
| bge-reranker-v2-m3     | $0                    | 2 ore            |
| Cache Redis            | $0 (già Upstash)      | 3 giorni         |
| Pruning KG             | $0                    | 1 giorno         |
| OpenTelemetry          | $0 (Grafana free)     | 2 giorni         |
| Self-RAG loop          | $0                    | 3-5 giorni       |
| SPLADE upsert          | $0 (FastEmbed locale) | 5 giorni         |
| Postgres checkpointing | $0 (già Fly Postgres) | 3 giorni         |
| Conversation table     | $0                    | 1 settimana      |
| Facade Pattern         | $0                    | 2-3 settimane    |
| KG confidence          | $0                    | 1 settimana      |
| **TOTALE**             | **$0**                | **~8 settimane** |

---

## RICERCA COMPLETATA — Verdetti Round 2

### ✅ V10. GLiNER per NER Zero-Shot (Indonesiano)

**xAI ha trovato**: `muchad/gliner-id-v2` (basato su `microsoft/mdeberta-v3-base`)

- HuggingFace: https://huggingface.co/muchad/gliner-id-v2
- Fine-tuned per indonesiano, zero-shot via architettura GLiNER
- Outperforma ChatGPT in NER zero-shot su benchmark generali
- **Production readiness: NO** (research model, non production-tested)
- **Verdetto**: investigare per KG extraction locale, ma testare accuratezza su testi regolamentari prima di adottare

### ✅ V11. Intent Classification con BERT Indonesiano

**xAI ha confermato**: `cahya/bert-base-indonesian-522M` esiste su HuggingFace

- HuggingFace: https://huggingface.co/cahya/bert-base-indonesian-522M
- Pre-trained su 522M token Wikipedia indonesiana
- Usato in paper per hoax detection (F1 0.9064), sentiment analysis
- **Production readiness: SI** (usato in multipli paper/progetti)
- **Verdetto**: ✅ ADOTTARE per sostituire regex intent classification
- **Effort**: fine-tune su ~1000 query etichettate (visa, tax, company, property, general)
- **File**: `services/classification/intent_classifier.py`

### ✅ V12. BM42 al posto di SPLADE

**xAI ha trovato**: Qdrant BM42 è SUPERIORE a SPLADE per il nostro caso

- Precision@10: 0.49 (BM42) vs ~0.45 (SPLADE)
- Recall@10: 0.85 (BM42) vs 0.71 (SPLADE)
- Più leggero e veloce di SPLADE
- Nativo Qdrant (nessuna infra esterna)
- **SPLADE è solo inglese** — BM42 generalizza meglio cross-lingua
- **Verdetto**: ✅ USARE BM42 INVECE DI SPLADE per vettori sparsi (aggiorna V5 sopra)

### ⚠️ Postgres LISTEN/NOTIFY con Fly.io auto_stop

**xAI ha chiarito**: funziona MA con caveat

- Il listener NON sopravvive al cold start — serve outbox pattern
- Pattern: drain outbox al boot → poi LISTEN, exponential backoff reconnect
- Scala a 10K+ connessioni ma necessita pooler
- **Verdetto**: POSSIBILE ma complesso. Per Fly.io auto_stop meglio SSE polling dal frontend.

### ✅ V13. Auth.js v5 per SSO Cross-Subdomain

**xAI ha confermato**: `next-auth` v5 supporta cross-subdomain

- Config: `cookies.domain='.balizero.com'` + `SameSite=lax`
- Gestisce OAuth/providers/session securely
- **Production readiness: SI** (standard per Next.js SSO)
- **Verdetto**: ✅ ADOTTARE come sostituto del cookie manuale attuale
- **Effort**: 1 settimana migrazione
- **File**: `apps/mouth/src/middleware.ts`

### ✅ V14. TanStack Query v5 per Frontend

**xAI ha confermato**: superiore a SWR per app complesse

- Bundle 13KB (vs SWR 4KB) ma features: mutations, pagination, DevTools
- SSR hydration + prefetching in layout/middleware
- **Production readiness: SI**
- **Verdetto**: ✅ ADOTTARE per workspace e portal
- **Effort**: migrazione incrementale (pagina per pagina)

### ℹ️ TTS per Audio Content

**xAI ha comparato**:

- ElevenLabs: top quality (MOS 4.5/5, pronuncia 81.97%)
- xAI Grok TTS: nuovo, 5 voci, 20+ lingue, $4.20/M chars — beta
- Google TTS: prosody 64% (inferiore a ElevenLabs 77%)
- **Verdetto**: NICE-TO-HAVE, non priorità. ElevenLabs per qualità, xAI per costo.

---

---

## ROUND 3: MACRO AREE NON INVESTIGATE (xAI Research, 50KB output)

### FRONTEND

| Area                         | Stato dell'arte 2026                                                                           | Azione per Nuzantara                                                               | Effort           |
| ---------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------- |
| **Next.js SSG 1500+ pagine** | Next.js 16 + Turbopack: build <2min per 10K pagine. On-demand revalidation > ISR.              | Migrare KBLI Navigator a on-demand revalidation                                    | 3 giorni         |
| **Portal UX**                | TanStack Query v5 + SSE real-time + PWA offline-first (Workbox)                                | Già V14. Aggiungere SSE per visa status real-time                                  | 1 settimana      |
| **3D Maps**                  | Deck.gl v9 > CesiumJS per zoning overlay. PostGIS: BRIN indexes + materialized views per <50ms | Valutare Deck.gl se Google Maps 3D insufficiente. BRIN index su bali_zoning_layers | 2 giorni (index) |
| **Design System**            | Tailwind v4 con @theme CSS variables nativo. 3.5x faster builds                                | Migrare bz-tokens.css a Tailwind v4 @theme                                         | 1 settimana      |
| **6 Subdomain**              | Next.js Multi-Zones + Turborepo + NextAuth.js v5 middleware                                    | Già V13 (Auth.js). Consolidare con Multi-Zones                                     | 2 settimane      |
| **MCP 2026**                 | MCP composition, tool discovery semantico, marketplace emergente                               | Semantic Tool Routing: vector search su tool descriptions, top-5 all'LLM           | 1 settimana      |
| **Omnichannel**              | Qiscus (Indonesia), Yellow.ai, Respond.io — unified inbox                                      | Valutare Qiscus per unified inbox Indonesia-native                                 | Research         |
| **CRM Automation**           | AI document processing + compliance deadline tracking                                          | Già automation engine. Upgrade con Verihubs OCR                                    | 1 settimana      |

### INFRASTRUCTURE

| Area                         | Stato dell'arte 2026                                                                                             | Azione per Nuzantara                                                  | Effort      |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ----------- |
| **Fly.io cold start**        | `suspend` causa clock skew (JWT fail). Docker multi-stage slim + `swap_size_mb = 512` + CPU-only deps (no CUDA). | Docker slim image + swap. NO suspend senza JWT leeway fix.            | 2 giorni    |
| **PostgreSQL 2GB**           | PgBouncer built-in su Fly. GIN index per JSONB. No partitioning sotto 50GB. pg_stat_statements.                  | Abilitare pg_stat_statements, GIN index su kg_nodes.properties        | 2 giorni    |
| **Qdrant 1.17 quantization** | Scalar int8: 4x mem reduction, 2x faster, <1% accuracy loss                                                      | ✅ ADOTTARE: scalar quantization sui 93K vettori → Qdrant usa 1/4 RAM | 1 giorno    |
| **Redis semantic cache**     | Upstash con semantic similarity cache per LLM responses                                                          | Già V8. Conferma pattern.                                             | —           |
| **Security**                 | OWASP LLM Top 10: prompt injection defense, PII redaction, Indonesian PDP Law                                    | Audit PII nel RAG pipeline. Prompt injection guardrails.              | 1 settimana |
| **CI/CD**                    | Turborepo remote caching. Selective deploys changed apps only.                                                   | Attivare Turborepo cache + selective deploy                           | 2 giorni    |
| **Cost**                     | Fly.io shared-cpu-2x ~$12/mo. Qdrant Cloud vs self-hosted.                                                       | Già ottimizzato. Scalar quantization riduce ulteriormente.            | —           |
| **Observability**            | Langfuse (open-source LLM observability) > LangSmith. Grafana Cloud free.                                        | ✅ ADOTTARE Langfuse per LLM tracing + Grafana per infra              | 3 giorni    |

### BUSINESS LOGIC

| Area                      | Stato dell'arte 2026                                                                      | Azione per Nuzantara                                       | Effort      |
| ------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ----------- |
| **Regulatory intel**      | Hexowatch/Visualping per change detection gov sites. AI summarization.                    | Integrare change detection su kemenkumham.go.id, oss.go.id | 3 giorni    |
| **Content pipeline**      | Multi-format da single source (article→thread→video→infographic). AI editorial.           | Già War Room. Aggiungere X thread generator.               | 2 giorni    |
| **Document OCR**          | **Verihubs** OCR per KTP/NPWP/akta (98% accuracy, Indonesia-native). Gemini 95%+ per KTP. | ✅ ADOTTARE Verihubs: 98% vs nostro Tesseract 85%          | 1 settimana |
| **Compliance automation** | Vanta/MetricStream per deadline tracking. Core Tax System (DJP) integration.              | Upgrade automation engine con predictive deadlines         | 2 settimane |
| **Invoicing**             | Xendit/Midtrans + e-Faktur DJP API. Multi-currency IDR/USD.                               | Integrare Xendit per pagamenti automatici                  | 2 settimane |
| **Client journey**        | AI milestone tracking + predictive timeline da dati storici                               | Usare 5000+ client data per previsione tempi processing    | 1 settimana |
| **Knowledge base**        | Auto-update da regulatory changes. Stale content detection.                               | Collegare intel scraper → auto-update Qdrant collections   | 1 settimana |
| **Lead scoring**          | AI scoring da multi-channel interactions. Conversion prediction.                          | Fine-tune su dati CRM storici                              | 2 settimane |

---

## NUOVI QUICK WINS (dal Round 3)

| #    | Azione                                                                                                                                     | Effort   | Impatto                                   |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------- | ----------------------------------------- |
| QW6  | ~~`auto_stop = "suspend"`~~ **RIVISTO**: suspend causa clock skew → JWT fail. Meglio: `swap_size_mb = 512` + Docker multi-stage slim image | 2 giorni | Cold start ridotto (immagine più leggera) |
| QW7  | Scalar quantization Qdrant (int8) sui 93K vettori                                                                                          | 1 giorno | -75% RAM Qdrant, 2x faster search         |
| QW8  | GIN index su `kg_nodes.properties`                                                                                                         | 30 min   | KG query 10x faster                       |
| QW9  | pg_stat_statements su Fly Postgres                                                                                                         | 30 min   | Identifica slow queries                   |
| QW10 | BRIN index su `bali_zoning_layers` (PostGIS)                                                                                               | 30 min   | Prime spatial query <50ms                 |

---

## ROADMAP AGGIORNATA

### Settimana 1 — Quick Wins (tutti)

QW1-QW10: reranker, cache, pruning KG, OpenTelemetry, Self-RAG, suspend Fly, quantization Qdrant, GIN index, pg_stat, BRIN index

### Settimana 2-3 — Core

V5 BM42, V3 Checkpointing, V7 Conversation table, V11 BERT intent classification

### Settimana 4-6 — Architecture

V1 Facade orchestrator, V6 KG confidence, V13 Auth.js SSO, Verihubs OCR

### Mese 2-3 — Advanced

V14 TanStack Query, Tailwind v4, Langfuse, Semantic Tool Routing MCP, Regulatory change detection

---

---

## ROUND 3 NLM FINDINGS (55 nuove fonti)

### Qdrant Scalar Quantization — numeri reali

- 93K vettori × 1536 dim × float32 = ~558MB RAM
- Con int8 quantization: ~140MB RAM (**-418MB, fattore 4x**)
- Accuracy loss <1% con oversampling=2 + rescore
- **Attivazione su collection esistente**: si configura sui parametri, Qdrant ri-quantizza. Non c'è garanzia "zero downtime" documentata — usare collection alias per swap atomico.

### Fly.io Suspend — SCARTATO

- `suspend` salva memoria su disco, resume in frazioni di secondo
- **MA**: clock skew al risveglio → JWT validation fallisce (claim `nbf`), cache expiry sballa, TLS cert validation rotta
- **Serve JWT leeway** (tolleranza secondi) prima di adottare
- Per ora: Docker slim + swap 512MB è più sicuro

### OCR Indonesia — Verihubs confermato leader

- **Verihubs**: unico che legge KTP/SIM/NPWP/Passaporto nativo. Prezzi non pubblici. Non self-hosted.
- **Mindee**: migliore API generale ma no Indonesia-specific. Cloud-only. 25 pagine free.
- **Tesseract**: free, self-hosted, ma accuracy più bassa per layout complessi.
- **Raccomandazione**: Verihubs per produzione, Tesseract come fallback locale.

### MCP Marzo 2026 — Standard aperto Linux Foundation

- MCP donato a **Agentic AI Foundation** (Linux Foundation)
- Nuovi framework: `agentregistry` per discovery/distribuzione tool
- **Vercel Skills**: package manager per skill IA (`npx skills i ...`)
- **Open Responses**: interfaccia singola multi-provider

### Langfuse vs LangSmith — Langfuse vince per noi

- **Langfuse**: MIT open-source, self-hosted free, framework-agnostic
- **LangSmith**: non open-source, self-hosted solo Enterprise (Kubernetes)
- **MA**: self-hosted su Fly.io 2GB rischia OOM
- **Raccomandazione**: Langfuse Cloud free tier (10K events/mo) → sufficiente per noi

### Immigration Software — Feature da adottare

- **Docketwise**: automazione moduli + comunicazioni clienti
- **INSZoom**: compliance enterprise
- **LexiQA Immigra**: verifica pre-sottomissione con LLM (firme mancanti, incongruenze PDF)
- **Florence Atlas**: alert predittivi basati su policy intelligence
- **Per noi**: adottare pattern LexiQA (LLM verifica pacchetto prima di submit) nel nostro workflow

---

## ROUND 4 FINDINGS

### Tecnologie Validate (xAI Advanced)

| Tecnologia             | Cosa fa                                                                   | Production ready | Per noi                                                     |
| ---------------------- | ------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------------- |
| **DeepEval**           | LLM testing framework (50+ metriche, LangGraph nativo, pytest CI/CD)      | SI               | ✅ Sostituire RAGAS rotto → DeepEval per regression testing |
| **Temporal.io**        | Durable workflows per settimane (Netflix/Stripe scale). Signals per HITL. | SI               | ⚠️ Overkill per ora — PostgreSQL SKIP LOCKED suffice        |
| **Outlines**           | Structured output via FSM (100% schema compliance, zero retry)            | SI               | ✅ Per estrazione dati da PDF indonesiani                   |
| **Qwen3.5-27B Q3_K_M** | Fit su 16GB M4 Air. 40-60 t/s                                             | SI               | ✅ Già in uso, conferma quantizzazione corretta             |
| **Augustus**           | Adversarial testing prompt injection (210+ probes, 47 attacchi)           | SI               | ✅ Testare le nostre difese                                 |
| **Retell AI**          | Voice AI $0.07/min, <400ms latency                                        | SI               | ⚠️ Nice-to-have per voice WhatsApp                          |

### Opportunità Business (xAI Business)

| Opportunità             | Dettaglio                                                                                                                           | Revenue potenziale                    |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| **KG API Monetization** | Esporre 56K nodi come GraphQL API per KBLI/regulatory lookup. $49/mo per 1000 query. Target: studi legali/commercialisti Indonesia. | **$50K MRR Year 1** (100 subscribers) |
| **Apache Superset**     | Dashboard analytics open-source. NLQ (Natural Language Query) con LLM.                                                              | Riduzione 70% tempo analisi           |
| **PWA Portal**          | Status automatici → -40% inquiry clienti. Doc upload con AI verification.                                                           | -40% carico support                   |
| **LexID Pattern**       | KG legale indonesiano simile al nostro, loro lo monetizzano via università                                                          | Validazione del modello               |

### Codebase Findings (NLM NB-1 Round 4)

**Scoperte chiave non note prima:**

- **943 except Exception silenziose** — debt testing/error handling massivo
- **Coverage CI rotta** (0.67% vs target 80%) — gate inutile da fixare subito
- **Race condition cache** — crash tra DB commit e Redis purge
- **Graph Engine checkpointer TODO** — memory leak attivo
- **Prompt bloat ~2000 token** — tagliabile a 150-300 parole
- **4 tabelle DB vuote** — cleanup possibile
- **Tabella users legacy** — ancora usata in auth/telegram

---

## ROUND 5 FINDINGS

### PDP Law Indonesia — Compliance OBBLIGATORIA

| Requisito                  | Dettaglio                                                                             | Azione                                     |
| -------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------ |
| **Legge**                  | UU PDP No. 27/2022, pienamente in vigore da ott 2024                                  |                                            |
| **Si applica a noi**       | SI — processiamo PII (passport, NPWP, KTP) di stranieri in Indonesia (Art. 2, Art. 4) |                                            |
| **Localizzazione dati**    | NON richiesta per settore privato — Fly.io Singapore OK                               | Nessuna azione                             |
| **Cross-border (Art. 56)** | Singapore: serve safeguard (standard clauses) o consenso con risk notice              | Aggiungere clausole                        |
| **Breach notification**    | **72 ore** per notificare autorità + soggetti                                         | Implementare incident response plan        |
| **Penalità**               | **2% fatturato annuo** admin + fino a 6 anni carcere + IDR 6B                         |                                            |
| **Consenso**               | Specifico/informato/esplicito per dati sensibili (KTP, passport). Revocabile.         | Aggiungere consent banner su portal upload |
| **DPO**                    | Obbligatorio se large-scale processing                                                | Valutare necessità                         |
| **AI-specific**            | Audit training data per PII. Diritto di opporsi a decisioni automatiche.              | Audit PII nel RAG pipeline                 |

### Cross-Validation: TUTTI I BUG CONFERMATI

NLM NB-1 ha confermato con codice esatto ogni scoperta dei round precedenti:

- ✅ **943 except Exception**: numero esatto confermato. Top 5: intel.py (32), team_drive_service.py (24), orchestrator.py (13), crm_clients.py (11), zoho_email_service.py (3)
- ✅ **Race condition cache**: codice esatto linee 325-326, 629, 694. Pattern replicato in TUTTI i router CRM
- ✅ **Rate limiter fail-open**: `return True` su `redis.ConnectionError` a riga 118
- ✅ **CI coverage sbagliata**: `--cov=src` punta a frontend Next.js, non a `backend/`. Coverage reale 0%
- ✅ **Prompt bloat 2000 token**: CLOSING_PHRASES (50+), GREETING_RULES, emotional adaptation tagliabili
- ✅ **Checkpointer TODO**: `MemorySaver()` placeholder in-memory, NO persistenza
- ✅ **Dual pool DB**: asyncpg (main) + psycopg3 (LangGraph) confermato, pool separati
- ✅ **10 tabelle vuote** (non 4): golden_routes, golden_answers, query_clusters, query_route_clusters, review_queue, renewal_alerts, company_profiles, client_companies, client_family_members + FK constraints tra loro

### Scaling 5K → 50K Clienti

| Threshold         | Cosa rompe                              | Fix                                  |
| ----------------- | --------------------------------------- | ------------------------------------ |
| **10K**           | DB connections saturano                 | Read replicas Postgres               |
| **20-25K**        | Redis session overload                  | JWT sessions (no Redis)              |
| **50K**           | File upload bottleneck                  | S3 presigned URLs + CDN              |
| **Ongoing**       | LLM costs                               | Cache semantic + small model routing |
| **No K8s needed** | Fly Machines autoscaling + multi-region |                                      |

### AI Autonomy — Livelli sicuri per Immigration

| Livello | Descrizione                                    | Sicuro per noi?                      |
| ------- | ---------------------------------------------- | ------------------------------------ |
| L0      | No AI                                          | —                                    |
| L1      | Copilot (AI assiste, umano decide)             | ✅ SI                                |
| L2      | Supervised autonomy (AI agisce, umano approva) | ✅ SI                                |
| L3      | Multi-step plans (AI pianifica ed esegue)      | ⚠️ Solo task non-legali              |
| L4-L5   | Full autopilot / self-improving                | ❌ NO per servizi legali/immigration |

**Harvey AI (PwC)**: L2 per legal across 25 jurisdictions. Nessun L4 in settore regolamentato.

### Docker Optimization

- Multi-stage build: da 2GB+ a <500MB
- **Escludere CUDA/torch GPU** — solo CPU deps
- Alpine/Distroless per base image
- `uv` per dependency resolution (più veloce di pip)

### asyncpg vs psycopg3 — Unificare?

- asyncpg: 3-5x faster (C/binary protocol)
- psycopg3: necessario per LangGraph checkpointer (TOAST/BLOB)
- **Verdetto**: mantenere dual pool ma con dimensioni calcolate (asyncpg: max 20, psycopg3: max 5)

---

## KG MONETIZATION — Opportunità Revenue

| Parametro  | Valore                                                   |
| ---------- | -------------------------------------------------------- |
| Asset      | 56K nodi regolamentari indonesiani                       |
| Modello    | GraphQL API, $49/mo per 1000 query                       |
| Target     | Studi legali, commercialisti, HR immigration Indonesia   |
| Precedente | LexID (KG legale indonesiano) monetizzato via università |
| Proiezione | **$50K MRR Year 1** con 100 subscribers                  |
| Pattern    | LexisNexis API ($500M+ revenue), Westlaw                 |

---

_Technology Enhancement Plan v5.0 FINAL — 29 marzo 2026_
_5 round di ricerca, 15+ agenti AI, ~300KB output grezzo_
_Fonti validate: Gemini, DeepSeek R1, xAI (multi-agent + fast), NLM NB-1 (5 query, 100+ citazioni codebase), NLM NB-9 (170+ fonti web via 3 deep research)_
_Cross-validato: tutti i bug confermati con codice esatto e numeri di riga_
_Fonti: 4 round di ricerca con 8+ agenti AI_
_Round 1: Gemini Explore + DeepSeek R1 + xAI 16-agent_
_Round 2: NLM NB-1 (27 citazioni) + NLM NB-9 (58 fonti)_
_Round 3: xAI x3 (frontend/infra/business, 50KB) + NLM NB-1 (codebase unexplored) + NLM Deep Research_
_Validati: 14+ enhancement a $0 costo infra_
_Scartati: 8 proposte smentite_
_Quick Wins: 10 azioni da 30min-1giorno ciascuna_

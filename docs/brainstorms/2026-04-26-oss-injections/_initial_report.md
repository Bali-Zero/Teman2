# Report — Migliori parti di codice OSS da iniettare in Nuzantara
**Data:** 2026-04-26 · **Macchina:** Air · **Branch:** main · **Autore:** Claude Opus 4.7

---

## 0. Premessa metodologica

Questo non è "una lista di librerie cool". Per ogni candidato ho:
1. **Identificato il punto preciso** del nostro codice dove iniettare (file, riga, classe).
2. **Confrontato cosa fa oggi il nostro codice** con cosa fa la libreria.
3. **Verificato la licenza** (Apache-2.0 / MIT preferiti, AGPL/GPL flag).
4. **Stimato l'effort di integrazione** in giorni di lavoro reale.
5. **Misurato il rischio** (basso = drop-in, alto = refactor architetturale).

Le categorie sono ordinate per **ROI atteso decrescente** — quelle in alto sono le più impattanti per il valore di Nuzantara.

I 21 candidati totali sono raggruppati in **8 aree d'iniezione**.

**Assunzione di base:** non sostituiamo l'embedding `text-embedding-3-small` (frozen — invaliderebbe 93k vettori). Tutto il resto è negoziabile.

---

## 1. RAG — Retrieval, reranking, late interaction

### 1.1 ⭐⭐⭐ PyLate (LightOnAI) — late-interaction (ColBERT) production-ready
- **Repo:** `lightonai/pylate` · **Stelle:** ~3k+ · **Licenza:** Apache-2.0 · **Lingua:** Python
- **Cosa fa:** Wrapper su `sentence-transformers` per ColBERT/Modernlate-interaction. Indici PLAID compressi, multi-lingua via XLM-R, modelli pre-allenati su MS-MARCO + multilingual.
- **Stato attuale nostro:** `apps/backend-rag/backend/services/rag/reranker.py` usa solo `CrossEncoder` (BAAI/bge-reranker-v2-m3 o jina). Non abbiamo late-interaction. Sul tier 1 (RAG_VERIFIED) avremmo +5-8% recall@10 secondo benchmark Weaviate.
- **Dove iniettare:**
  - Nuovo file `backend/services/rag/late_interaction.py` con `PyLateReranker` mixin.
  - Hook in `reranker_registry.py` come tipo `MODEL_TYPE_LATE_INTERACTION`.
  - Indice PLAID separato per `legal_unified_hybrid` (3-fold storage cost: 90MB → 270MB, accettabile).
- **Effort:** 2-3 giorni · **Rischio:** medio (richiede nuovo indice). · **ROI:** alto sui top-k 50→10 squeeze.

### 1.2 ⭐⭐⭐ Qdrant + ColBERT nativo (Qdrant 1.10+)
- **Repo:** `qdrant/qdrant` · **Stelle:** 22k+ · **Licenza:** Apache-2.0
- **Cosa fa:** Qdrant 1.10 supporta multivector storage e Universal Query API: dense + sparse + ColBERT in **una singola query** con prefetch e fusion server-side.
- **Stato nostro:** Stiamo su `qdrant-client>=1.12.0` ma in `hybrid_search.py` facciamo client-side RRF su 2 query separate. Lascia 30-50ms su tavolo per query e impedisce ColBERT.
- **Dove iniettare:**
  - Refactor `hybrid_search.py:search_hybrid()` → `client.query_points(prefetch=[...], query=Fusion.RRF)`.
  - Una volta migrato, aggiungere prefetch ColBERT (vedi 1.1).
- **Effort:** 1 giorno · **Rischio:** basso (drop-in, retrocompatibile). · **ROI:** alto su latenza p95.

### 1.3 ⭐⭐ Reliable_RAG pattern — graph-aware chunking + RRF + ColBERT
- **Repo:** `Lokesh-Chimakurthi/Reliable_RAG` · **Stelle:** ~1k · **Licenza:** MIT
- **Cosa fa:** Pipeline production: semantic-double-merging chunking (LlamaIndex), Qdrant hybrid, ColBERT rerank via fastembed.
- **Stato nostro:** `kg_enhanced_retrieval.py` usa entity-pattern regex, non chunking semantico. La pipeline ingestion (`ingestion_service.py`) chunk-a a fixed-size.
- **Dove iniettare:** Adottare la `SemanticDoubleMergingSplitter` per `legal_unified_hybrid` re-ingestion (NON per i clientologici — non vale il rebuild).
- **Effort:** 1-2 giorni + 1 reingest notturno · **Rischio:** medio (test di regressione su 200 query da rag_canary).

### 1.4 ⭐⭐ FastEmbed + BM42 (Qdrant)
- **Repo:** `qdrant/fastembed` · **Stelle:** 3k+ · **Licenza:** Apache-2.0
- **Cosa fa:** ONNX-runtime embeddings/rerankers/sparse — 2-5x più veloce di sentence-transformers, senza torch in produzione.
- **Stato nostro:** `requirements-prod.txt` ESCLUDE già `sentence-transformers` (commento "optimized <8GB"), ma `reranker.py` lo importa e lo nostro Dockerfile poi lo include implicitamente. Su Fly.io il container è grosso.
- **Dove iniettare:** Sostituire `CrossEncoderReranker` con FastEmbed `Reranker` su prod. Tenere sentence-transformers solo per dev/training.
- **Effort:** 1 giorno · **Rischio:** basso · **ROI:** alto su immagine Docker (-2GB) e cold-start.

---

## 2. Knowledge Graph & Multi-hop

### 2.1 ⭐⭐⭐ Graphiti (getzep) — temporal knowledge graph
- **Repo:** `getzep/graphiti` · **Stelle:** 20k+ · **Licenza:** Apache-2.0 · **Backend:** Neo4j/FalkorDB
- **Cosa fa:** Costruzione real-time di KG da conversazioni. **Ogni fact ha un validity window** (`valid_from`, `invalid_at`) — esattamente il problema che oggi affrontiamo a mano per "il KITAS di Mario è scaduto, l'E33G è il nuovo".
- **Stato nostro:** Nostro KG è 108k nodi PostgreSQL custom (`backend/services/knowledge_graph/`). I subgraph `kg_subgraph_visa.py` etc. sono hard-coded. Non c'è temporal validity — un fatto "Mario ha KITAS valida" rimane true anche dopo expire.
- **Dove iniettare:**
  - **NON** sostituire l'attuale KG (troppo invasivo, troppi router lo usano).
  - **Sì** introdurre Graphiti per il **client memory** (sostituire l'attuale `services/conversation/` memory layer con tracciabilità temporale).
  - Esempio uso: "Mario ha cambiato indirizzo a Bali" → fact con `valid_from=2026-04-01`, vecchio fact `invalid_at=2026-04-01`.
- **Effort:** 5-7 giorni (richiede Neo4j su Fly.io OPPURE FalkorDB — nuova app) · **Rischio:** alto · **ROI:** trasformativo per CRM longitudinale.

### 2.2 ⭐⭐ Microsoft GraphRAG — community detection
- **Repo:** `microsoft/graphrag` · **Stelle:** 23k+ · **Licenza:** MIT
- **Cosa fa:** Costruzione KG da corpus + Leiden community detection + community summaries via LLM.
- **Stato nostro:** Abbiamo già fatto Louvain a `2026-04-07` (memoria GraphRAG v2: 6,310 cluster). Ma le **community summaries** sono ferme. `kg_subgraph_*.py` non hanno summary precomputati.
- **Dove iniettare:**
  - Cron settimanale che prende le 6,310 community e genera summary via DeepSeek (~$3 una tantum, $0.50/settimana per delta).
  - Aggiungere campo `community_summary` come prefetch in `kg_enhanced_retrieval.py` per query "global" (es. "panoramica visa Indonesia").
- **Effort:** 2-3 giorni · **Rischio:** basso · **ROI:** alto su query "global" che oggi sono il punto debole.

### 2.3 ⭐⭐ LightRAG (HKU) — dual-level retrieval
- **Repo:** `HKUDS/LightRAG` · **Stelle:** 12k+ · **Licenza:** MIT
- **Cosa fa:** Dual-level (low + high level) retrieval con dedup di entità. Più leggero di GraphRAG MS, fa entity merging automatico.
- **Stato nostro:** Entity dedup è manuale (`crm_automation_engine.py` quality fixes). Nessuna distinzione low/high level.
- **Dove iniettare:** Plug-in opzionale per CRM Guardian, NON per RAG (rischio doppione con esistenti).
- **Effort:** 3-4 giorni · **Rischio:** medio · **ROI:** medio.

---

## 3. Eval, prompt, observability

### 3.1 ⭐⭐⭐ Langfuse (self-hostable, OpenTelemetry-native)
- **Repo:** `langfuse/langfuse` · **Stelle:** 12k+ · **Licenza:** MIT (core), commerciale per cloud
- **Cosa fa:** Piattaforma osservabilità LLM end-to-end: tracing, eval, prompt management, dataset, playground. Riceve OTEL nativo.
- **Stato nostro:** Usiamo `langsmith>=0.4.0` (a pagamento, vendor-locked). `@traceable` solo su 3 file (`kg_graph_nodes.py`, `agentic/orchestrator_core.py`, test). Non abbiamo dashboard self-hosted.
- **Dove iniettare:**
  - Deploy Langfuse self-hosted come 4ª Fly.io app (~$15/mo) — Pro o Air locale come alternativa free.
  - Sostituire `from langsmith import traceable` con `langfuse.observe` in `services/rag/agentic/`.
  - Bonus: prompt versioning per `zantara_core.py` direttamente in Langfuse (oggi è tutto in-code).
- **Effort:** 3-4 giorni · **Rischio:** basso (parallel run langsmith+langfuse possibile) · **ROI:** **massimo** — vendor-unlock + dashboard self-hosted.

### 3.2 ⭐⭐⭐ OpenLLMetry (Traceloop) — auto-instrumentation OTEL
- **Repo:** `traceloop/openllmetry` · **Stelle:** 6k+ · **Licenza:** Apache-2.0 (recentemente acquisita ServiceNow, OSS continua)
- **Cosa fa:** Auto-instrument 40+ provider (OpenAI, Anthropic, LangChain, LlamaIndex). Una linea di codice → tutti gli LLM call tracciati con OTEL semantic-conventions.
- **Stato nostro:** Tracing manuale `@traceable` in 3 file. Ollama-client, gemini-client, deepseek-client zero strumentati. La nostra OTEL pipeline è custom.
- **Dove iniettare:**
  - `apps/backend-rag/backend/llm/__init__.py`: `from traceloop.sdk import Traceloop; Traceloop.init(app_name="zantara")`.
  - **Tutto** il tracing LLM diventa automatico, esce in formato standard, va a Langfuse (3.1).
- **Effort:** 0.5 giorni · **Rischio:** basso (può essere abilitato/disabilitato via env var) · **ROI:** **massimo** rispetto allo sforzo.

### 3.3 ⭐⭐ DeepEval (Confident AI)
- **Repo:** `confident-ai/deepeval` · **Stelle:** 8k+ · **Licenza:** Apache-2.0
- **Cosa fa:** Pytest-style LLM eval: G-Eval, hallucination, answer relevancy, RAGAS metrics tutti integrati. Si integra con CI.
- **Stato nostro:** `services/rag/evaluation/ragas_evaluator.py` esiste ma è una sola metrica + `auto_judgement_day.sh` settimanale. No CI gate.
- **Dove iniettare:**
  - Aggiungere `deepeval` a `requirements.txt` (dev only).
  - Convertire `tests/services/rag/test_confidence.py` style → `deepeval` test su 50 query gold.
  - GitHub Actions: pre-merge eval gate (se metrics scendono >5%, blocca merge).
- **Effort:** 2-3 giorni · **Rischio:** basso · **ROI:** alto su qualità retrieval long-term.

### 3.4 ⭐⭐ Inspect-AI (UK AISI)
- **Repo:** `UKGovernmentBEIS/inspect_ai` · **Stelle:** 3k+ · **Licenza:** MIT
- **Cosa fa:** Framework eval del UK AI Safety Institute: 200+ eval pre-built, supporto multi-modello, ottimo per safety/red-teaming.
- **Stato nostro:** Red-team manuale via Gemini CLI. No eval di safety strutturate.
- **Dove iniettare:** Cron mensile su Gemini per red-team (jailbreak, leak personas, prompt injection). Output → Telegram + Langfuse.
- **Effort:** 2 giorni · **Rischio:** basso · **ROI:** medio (alta importanza, bassa frequenza).

### 3.5 ⭐⭐ Promptfoo (now OpenAI, MIT)
- **Repo:** `promptfoo/promptfoo` · **Stelle:** 7k+ · **Licenza:** MIT
- **Cosa fa:** CLI per testing prompt: YAML config, GitHub Action per diff prompt nei PR, comparison cross-model.
- **Stato nostro:** Modifiche a `zantara_core.py` non hanno regression test. Ogni cambio è "deploy and pray".
- **Dove iniettare:**
  - File `promptfooconfig.yaml` con 30 query rappresentative (KBLI, visa, pricing).
  - GitHub Action su PR che tocca `backend/prompts/*.py` → diff dei risultati pre/post.
- **Effort:** 1 giorno · **Rischio:** basso · **ROI:** alto su safety dei prompt change.

---

## 4. Agent runtime & structured output

### 4.1 ⭐⭐⭐ PydanticAI (Pydantic team)
- **Repo:** `pydantic/pydantic-ai` · **Stelle:** 11k+ · **Licenza:** MIT
- **Cosa fa:** Agent framework type-safe: dependency injection, tool registration, streaming, multi-LLM. Da chi ha fatto Pydantic stesso (e abbiamo già `pydantic>=2.12.5`).
- **Stato nostro:** `services/rag/agentic/` è custom. `multi_agent_coordinator.py` è custom. `services/agents/team_agent_config.py` è custom RBAC. C'è LangGraph ma non PydanticAI.
- **Dove iniettare:**
  - **NON** sostituire LangGraph (lo usiamo già in produzione, è il KG orchestrator).
  - **Sì** usare PydanticAI per i **nuovi agenti** specializzati (visa-specialist, tax-specialist) che oggi sono prompt-engineered su Claude OAuth. Type-safety + tool registration = -50% codice.
- **Effort:** 4-5 giorni per migrare 2 agenti pilota · **Rischio:** medio · **ROI:** alto long-term.

### 4.2 ⭐⭐⭐ Instructor (567-labs)
- **Repo:** `567-labs/instructor` · **Stelle:** 11k+ · **Licenza:** MIT
- **Cosa fa:** Output strutturati garantiti via Pydantic. Retry automatico con error feedback se l'LLM emette JSON malformato. 3M download/mese.
- **Stato nostro:** Zero file usano `instructor` (verificato). Ogni JSON output è prompt-engineered + try/except + regex fallback. Vedi `kbli_eye.py`, `pdf_vision_service.py`, decine di altri.
- **Dove iniettare:**
  - Wrapper unico in `backend/llm/structured.py`: `async def structured_call(prompt: str, schema: type[BaseModel]) -> BaseModel`.
  - Migrare 5 hot-spot per primo: KBLI extraction, OCR akta parsing, KG entity extraction, classification, JSON tool args.
  - **Funziona con Claude OAuth CLI** via wrapping (ho controllato — i mode `JSON_SCHEMA` e `MD_JSON` non chiamano API native).
- **Effort:** 2-3 giorni per i 5 hot-spot · **Rischio:** basso · **ROI:** **massimo** — meno bug "JSON malformato".

### 4.3 ⭐⭐ Outlines (.txt) — constrained generation
- **Repo:** `dottxt-ai/outlines` · **Licenza:** Apache-2.0
- **Cosa fa:** Constrained sampling — l'LLM **non può** emettere JSON malformato perché il sampler scarta i token invalidi.
- **Stato nostro:** Solo per Ollama (locale) ha senso, le API non espongono i logits. Su Fly.io non si applica.
- **Dove iniettare:** `backend/llm/ollama_client.py` per qwen3.5/gemma4 quando facciamo classification offline.
- **Effort:** 1-2 giorni · **Rischio:** basso · **ROI:** medio (solo Ollama).

---

## 5. LLM Gateway / Routing

### 5.1 ⭐⭐⭐ LiteLLM (BerriAI) — drop-in proxy
- **Repo:** `BerriAI/litellm` · **Stelle:** 18k+ · **Licenza:** MIT
- **Cosa fa:** Proxy server unificato OpenAI-format per 100+ provider. Built-in retry, fallback, load balance, cost tracking, guardrails, caching. È **lo standard de-facto 2026**.
- **Stato nostro:** `provider_registry.py`, `adapters/registry.py`, `provider/openrouter.py`, `claude_oauth_client.py` — tutto custom. Funziona ma è 4 mesi di tech debt.
- **Dove iniettare:**
  - **NON** rimpiazzare `claude_oauth_client.py` (Claude OAuth CLI non è OpenAI-format, lo wrappiamo a parte).
  - **Sì** sostituire `genai_client.py` + `deepseek_client.py` + `providers/openrouter.py` con LiteLLM SDK (no proxy server, basta SDK).
  - Cost tracking automatico → Langfuse (vedi 3.1).
- **Effort:** 3-4 giorni · **Rischio:** medio (test parità su tutte e 3 le pipeline) · **ROI:** alto — meno codice custom da mantenere.

---

## 6. Document & multimodal ingestion

### 6.1 ⭐⭐⭐ Docling (IBM Research)
- **Repo:** `docling-project/docling` · **Stelle:** 25k+ · **Licenza:** MIT
- **Cosa fa:** PDF parsing state-of-the-art 2026. Layout detection, table extraction (94%+ accuracy), formula/figure understanding. Eredita da DocLayNet di IBM Research.
- **Stato nostro:** `services/multimodal/pdf_vision_service.py` usa Gemini Vision. È il bottleneck OCR akta multipagina (cron `daily_indexing_cron.sh` Phase 1).
- **Dove iniettare:**
  - Aggiungere Docling come **primo tier** OCR. Gemini Vision diventa fallback per scan a bassa qualità.
  - Su Air (16GB) gira locale, su Fly.io API → comunque più economico di Gemini per volumi.
- **Effort:** 2-3 giorni (test su 50 akta reali) · **Rischio:** medio · **ROI:** alto (-70% costo Gemini OCR + accuratezza tabelle).

### 6.2 ⭐⭐ Unstructured.io (open-source)
- **Repo:** `Unstructured-IO/unstructured` · **Stelle:** 12k+ · **Licenza:** Apache-2.0
- **Cosa fa:** ETL universale per documenti. Strategia `hi_res` per PDF complessi. Output uniforme `Title|NarrativeText|Table|ListItem`.
- **Stato nostro:** Per il legal scraper (`bali-intel-scraper`) usiamo BeautifulSoup. Buoni risultati ma manca struttura (title vs narrative).
- **Dove iniettare:** Pipeline `legal_ingestion_service.py` → Unstructured per markdown pulito → embedding di chunk semantici, non blob HTML.
- **Effort:** 2 giorni · **Rischio:** basso · **ROI:** medio sulla qualità del KB.

### 6.3 ⭐⭐ Trafilatura — web text extraction
- **Repo:** `adbar/trafilatura` · **Stelle:** 4k+ · **Licenza:** Apache-2.0
- **Cosa fa:** Best-in-class web scraping → boilerplate removal → markdown pulito. Migliore di readability/newspaper3k.
- **Stato nostro:** `bali-intel-scraper` ha pipeline custom Playwright + selector. Brittle.
- **Dove iniettare:** Sostituire estrazione body articoli (mantenendo Playwright per JS-heavy sites). 1 funzione `trafilatura.extract(html)` rimpiazza ~150 righe.
- **Effort:** 1 giorno · **Rischio:** basso · **ROI:** medio.

---

## 7. Ops, migrations, durable execution

### 7.1 ⭐⭐⭐ Atlas (Ariga) — schema-as-code
- **Repo:** `ariga/atlas` · **Stelle:** 7k+ · **Licenza:** Apache-2.0 · **Lingua:** Go
- **Cosa fa:** "Terraform per database". 50+ safety analyzer rilevano migration distruttive (e.g. drop column con dati, rename senza alias) PRIMA che vadano in prod. Linting nei PR.
- **Stato nostro:** `backend/db/migration_manager.py` è custom Python. Cicatrice attiva: PR #302 ha rilevato `migration 138 missing rollback_sql blocks deploy` — proprio il tipo di issue che Atlas cattura automaticamente.
- **Dove iniettare:**
  - **Non** sostituire il runner (troppo invasivo).
  - **Sì** integrare `atlas migrate lint` in `pre-deploy-gate` GitHub Actions. Fail il PR se Atlas trova issue distruttive.
- **Effort:** 1-2 giorni (Atlas binary in CI, configurato per Postgres) · **Rischio:** basso · **ROI:** alto (preveniva PR #302 prima del merge).

### 7.2 ⭐⭐⭐ Temporal Python SDK — durable execution
- **Repo:** `temporalio/sdk-python` · **Stelle:** 6k+ · **Licenza:** MIT
- **Cosa fa:** Workflows che sopravvivono a crash, replay deterministico, exactly-once semantics, scheduling integrato. Sostituisce Celery+RabbitMQ+Redis Beat per orchestrazione long-running.
- **Stato nostro:** `services/measurer/scheduler.py`, `notifications/funnel_email/scheduler.py`, `auto_practice` cron, `daily_indexing_cron.sh`, WR2 supervisor — tutti scheduler custom. Cicatrice: WR2 ha richiesto event-driven supervisor 2 settimane fa proprio per durabilità.
- **Dove iniettare:**
  - **Considerare** Temporal Cloud per il prossimo grosso flow (es. compliance-autopilot multi-step). NON migrare retroattivamente i 12 cron esistenti.
  - Alternativa più leggera: **Restate** (sidecar HTTP, no broker) — più adatto al nostro Pro/Air H24 setup.
- **Effort:** 5-7 giorni per il primo flow · **Rischio:** alto (architettura) · **ROI:** alto long-term per ogni flow >3 step.

### 7.3 ⭐⭐ Dramatiq + APScheduler — alternativa più leggera
- **Repo:** `Bogdanp/dramatiq` · **Licenza:** LGPL-3.0 ⚠️ (attenzione)
- **Cosa fa:** Task queue Python come Celery ma async-native, broker Redis (che già abbiamo).
- **Stato nostro:** Cron Air via `crontab` + bash. Funziona ma no retry, no DLQ, no observability.
- **Dove iniettare:** Per i cron che falliscono spesso (`daily_indexing_cron.sh` con Gemini quota errors), Dramatiq con retry esponenziale + DLQ.
- **Effort:** 3-4 giorni · **Rischio:** medio (LGPL — accettabile per backend non-distribuito) · **ROI:** medio.

### 7.4 ⭐⭐ Purgatory — async circuit breaker
- **Repo:** `mardiros/purgatory` · **Stelle:** ~200 · **Licenza:** BSD-3
- **Cosa fa:** Circuit breaker async pulito. Stati closed/open/half-open per protezione downstream.
- **Stato nostro:** `scripts/drive_token_watchdog.py` ha logica circuit breaker hand-rolled (3 fail → OPEN). Stesso pattern in `gemini_quota_manager.py`.
- **Dove iniettare:** Sostituire 2 implementazioni custom con Purgatory. Meno codice, primitive standardizzate.
- **Effort:** 0.5 giorni · **Rischio:** basso · **ROI:** medio (technical debt reduction).

---

## 8. Voice (per casi futuri tipo conversazione di stamattina)

### 8.1 ⭐⭐⭐ WhisperX
- **Repo:** `m-bain/whisperX` · **Stelle:** 14k+ · **Licenza:** BSD-2 (modello: vari)
- **Cosa fa:** Faster-whisper backend (70x real-time) + word-level timestamp + diarization (pyannote).
- **Stato nostro:** `audio_service.py` esiste ma usa pipeline base. Non abbiamo speaker diarization.
- **Dove iniettare:** Per WhatsApp voice notes — riconoscere chi parla in conversazioni multi-utente. Sul Pro (48GB) gira large-v2 in 2 secondi per audio di 1 minuto.
- **Effort:** 2-3 giorni · **Rischio:** basso · **ROI:** alto se WhatsApp business workflow lo richiede.

---

## 9. PII / Safety — già copertura buona, gaps minori

### 9.1 ⭐⭐ NeMo Guardrails (NVIDIA)
- **Repo:** `NVIDIA-NeMo/Guardrails` · **Stelle:** 4k+ · **Licenza:** Apache-2.0
- **Cosa fa:** Programmable guardrails: dialog flow control, topic policy, jailbreak detection, hallucination detection. Integra con Guardrails-AI validators.
- **Stato nostro:** `services/security/` ha audit/brute_force/token. **Zero** guardrails LLM input/output. SECURITY_BOUNDARY è solo prompt instruction (bypass-able).
- **Dove iniettare:**
  - Topic rails per i 7 channel: WhatsApp/Telegram non devono mai parlare di topic non-business.
  - Jailbreak detection sul `/api/chat` endpoint pre-LLM call.
- **Effort:** 3-4 giorni · **Rischio:** basso · **ROI:** alto su brand-safety e legal liability.

### 9.2 Già implementato bene: Microsoft Presidio
Stato attuale: `presidio-analyzer>=2.2.362`, `presidio-anonymizer>=2.2.362`. Abbiamo già la copertura PII migliore disponibile OSS. **Nessuna iniezione richiesta.**

---

## 10. Embedding model upgrade — opzione strategica

### 10.1 ⭐⭐ Qwen3-Embedding-4B (Qwen team, Apache-2.0)
- **Hugging Face:** `Qwen/Qwen3-Embedding-4B`
- **Cosa fa:** N°1 MTEB multilingual leaderboard (giugno 2025, score 70.58). Supporta indonesiano nativo. **Apache-2.0.**
- **Stato nostro:** `text-embedding-3-small` (1536 dim). 93k vettori esistenti. **CAMBIARE = INVALIDARE TUTTO.**
- **Decisione strategica:** Mantenere `text-embedding-3-small` come **principale**. Aggiungere Qwen3-Embedding-4B come **collezione parallela** solo per i nuovi corpus (es. legal scraper future). A/B test su 6 mesi → decisione informata.
- **Effort:** Solo per A/B parallelo: 5-7 giorni + 1 nuova Qdrant collection (Pro locale, no Fly cost) · **Rischio:** basso (parallelo, non sostitutivo) · **ROI:** sconosciuto (richiede A/B).

---

## SOMMARIO PRIORIZZATO

| # | Repo | Effort | ROI | Rischio | Quando |
|---|------|--------|-----|---------|--------|
| 1 | **Instructor** (4.2) | 2-3d | ⭐⭐⭐ | basso | **Subito** |
| 2 | **OpenLLMetry** (3.2) | 0.5d | ⭐⭐⭐ | basso | **Subito** |
| 3 | **Langfuse** self-host (3.1) | 3-4d | ⭐⭐⭐ | basso | Prossima settimana |
| 4 | **FastEmbed + BM42** (1.4) | 1d | ⭐⭐⭐ | basso | Prossima settimana |
| 5 | **Qdrant 1.10 multivector** (1.2) | 1d | ⭐⭐ | basso | Prossima settimana |
| 6 | **Atlas migrate lint** in CI (7.1) | 1-2d | ⭐⭐⭐ | basso | Prossima settimana |
| 7 | **Promptfoo** (3.5) | 1d | ⭐⭐ | basso | Prossima settimana |
| 8 | **Docling** OCR (6.1) | 2-3d | ⭐⭐⭐ | medio | 2-3 settimane |
| 9 | **PyLate** late-interaction (1.1) | 2-3d | ⭐⭐⭐ | medio | 2-3 settimane |
| 10 | **DeepEval** CI gate (3.3) | 2-3d | ⭐⭐ | basso | 2-3 settimane |
| 11 | **NeMo Guardrails** topic rails (9.1) | 3-4d | ⭐⭐ | basso | 1 mese |
| 12 | **GraphRAG community summaries** (2.2) | 2-3d | ⭐⭐ | basso | 1 mese |
| 13 | **LiteLLM SDK** unify clients (5.1) | 3-4d | ⭐⭐⭐ | medio | 1 mese |
| 14 | **Graphiti** temporal client memory (2.1) | 5-7d | ⭐⭐⭐ | alto | 2 mesi |
| 15 | **PydanticAI** new agents (4.1) | 4-5d | ⭐⭐⭐ | medio | 2 mesi |
| 16 | **Temporal/Restate** durable workflows (7.2) | 5-7d | ⭐⭐⭐ | alto | 3 mesi |

## RACCOMANDAZIONE OPERATIVA

**Sprint 1 (questa settimana):**
- Instructor (drop-in, alta resa)
- OpenLLMetry (mezza giornata, attiva tracing su tutto)
- Atlas lint in CI (preveniva PR #302)

**Sprint 2 (prossime 2 settimane):**
- Langfuse self-hosted (sostituisce LangSmith, libera vendor lock)
- Qdrant 1.10 Universal Query (latency ↓)
- FastEmbed (Docker -2GB, cold-start ↓)
- Promptfoo (PR gate per zantara_core.py)

**Sprint 3 (mese 1):**
- Docling OCR (sostituisce Gemini Vision come primo tier)
- DeepEval CI gate
- LiteLLM SDK (unifica genai/deepseek/openrouter clients)

**Tutto il resto** (Graphiti, PydanticAI, Temporal) è **strategico** — vale lo studio approfondito prima di committare.

---

## Note di metodo

Non ho proposto:
- ❌ Sostituire LangGraph (lo usiamo bene, costo migrazione > beneficio)
- ❌ Sostituire l'embedding model (93k vettori in gioco)
- ❌ Sostituire Qdrant (è già best-in-class)
- ❌ Sostituire Postgres con Neo4j (KG funziona su PG con jsonb, e Graphiti è additivo)
- ❌ Spostare il codice in Go/Rust per performance (l'effort non vale)

Il principio guida: **iniezioni additive che riducono codice custom** (Instructor, LiteLLM, Atlas, Docling) o **aggiungono capacità nuove** (Graphiti temporal, late-interaction reranking, durable execution). Mai "rewrite for the sake of rewrite".

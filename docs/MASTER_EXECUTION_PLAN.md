# NUZANTARA — PIANO ESECUZIONE SUPREMO

> "Un piano senza esecuzione è un'allucinazione. Un'esecuzione senza piano è panico."
>
> Questo documento traduce 12 round di ricerca (7,317 righe, 8 documenti strategici,
> 30+ agenti AI, ~$4 di costo) in ordini di marcia precisi.
>
> Ogni task ha: cosa fare, chi lo fa, da quale macchina, quali file toccare,
> come verificare che è fatto, e cosa si sblocca dopo.

---

## PRIORITÀ ASSOLUTE (non negoziabili)

```
COMPLIANCE > SECURITY > REVENUE > PERFORMANCE > FEATURES
```

Se la compliance non è a posto, tutto il resto è irrilevante.
Se la sicurezza ha buchi, il revenue è a rischio.
Se non c'è revenue, la performance non importa.

---

## FASE 0: SOPRAVVIVENZA LEGALE (Settimana 1)

> Senza PSE e DPO, operiamo illegalmente. Kominfo può bloccare balizero.com domani.

### 0.1 PSE Registration [OWNER: Zero] [MACCHINA: Browser Pro]
```
COSA: Registrare Bali Zero come PSE (Penyelenggara Sistem Elektronik)
DOVE: https://oss.go.id → Registrazione PSE Lingkup Privat
SERVE: NIB, NPWP azienda, descrizione sistema, security policy
TEMPO: 1 giorno compilazione + 5-14gg approvazione Kominfo
COSTO: $0 (o $300-500 con consulente locale)
VERIFICA: Ricevuta registrazione PSE da Kominfo
SBLOCCA: Operatività legale, prerequisito per tutto il resto
```

### 0.2 DPO Nomination [OWNER: Zero] [MACCHINA: —]
```
COSA: Nominare Data Protection Officer (obbligatorio post Sentenza CC 151/2024)
OPZIONI:
  A) CTO come interim DPO (gratis, immediato)
  B) DPO-as-a-Service: Defend IT360 (defendit360.co.id) ~$200-500/mo
  C) Avvocato locale: Hukumonline, SSEK, ABNR ~$1-2K setup
TEMPO: 1 giorno (opzione A), 1 settimana (opzione B/C)
VERIFICA: Lettera di nomina firmata, comunicazione a team
SBLOCCA: Compliance Art. 53 UU PDP, supervisione DPIA
```

### 0.3 Privacy Policy Update [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Aggiornare privacy policy balizero.com con requisiti Art. 21 UU PDP
FILE: apps/mouth/src/app/(blog)/privacy/page.tsx (o creare se non esiste)
CONTENUTO:
  - Categorie dati raccolti (passport, KTP, NPWP, phone, email)
  - Base legale per ogni processing (contratto Art. 20 + consenso Art. 21)
  - Diritti: accesso, rettifica, cancellazione, portabilità, revoca consenso
  - Periodo retention (5 anni post-servizio per docs, 2 anni chat)
  - Cross-border transfer (Fly.io Singapore, Google, OpenAI)
  - Contatti DPO
VERIFICA: Pagina live su balizero.com/privacy
SBLOCCA: Base legale per consent banner
```

---

## FASE 1: SICUREZZA CRITICA (Settimana 1-2)

> 4 falle di sicurezza scoperte da NLM NB-1. Fix prima di qualsiasi altra cosa.

### 1.1 Rate Limiter Fix [OWNER: Claude Code Air] [MACCHINA: Air → deploy Fly]
```
COSA: Fix fail-open quando Redis down → fail-open con in-memory fallback severo
FILE: backend/middleware/rate_limiter.py:118
CODICE:
  PRIMA:  except redis.ConnectionError: return True  # Lascia passare tutto
  DOPO:   except redis.ConnectionError:
            logger.warning("Redis down, using in-memory rate limiter")
            return _in_memory_rate_check(ip, limit=10)  # Limite severo locale
VERIFICA: Kill Redis locale, verificare che rate limiting funziona ancora
SBLOCCA: Protezione DoS anche senza Redis
```

### 1.2 Telegram PII Fix [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Rimuovere phone number in chiaro dalla notifica Telegram admin
FILE: backend/app/routers/telegram_webhook.py (o whatsapp_chat.py)
CODICE:
  PRIMA:  f"**Cliente:** {display_name} (+{phone})"
  DOPO:   f"**Cliente:** ID-{client_id} (+{phone[:4]}***)"
VERIFICA: Invia messaggio test, verificare che phone è mascherato nel log Telegram
SBLOCCA: Compliance trasmissione PII
TEMPO: 30 minuti
```

### 1.3 Gemini OCR Consent Gate [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Aggiungere consent check prima di inviare immagini passport/KTP a Gemini API
FILE: backend/services/multimodal/pdf_vision_service.py
       backend/app/routers/crm_enhanced.py (_auto_ocr_passport, _auto_ocr_npwp)
LOGICA:
  IF client ha consenso cross-border (consent_records table) → procedi con Gemini
  ELSE → usa solo Ollama locale, se fallisce → return error "OCR locale non disponibile"
  LOG: ogni invio a Gemini API → audit_logs (client_id, "CROSS_BORDER_OCR", timestamp)
VERIFICA: Upload passport senza consenso → errore. Con consenso → OCR funziona.
SBLOCCA: Compliance Art. 56 cross-border transfer
TEMPO: 1 giorno
```

### 1.4 Presidio PII Scanner [OWNER: Claude Code Air] [MACCHINA: Air → deploy Fly]
```
COSA: Microsoft Presidio come middleware su TUTTI gli output LLM
FILE: backend/middleware/pii_scanner.py (NUOVO)
DIPENDENZE: pip install presidio-analyzer presidio-anonymizer stanza
MODELLO: stanza.download('id')  # Indonesiano, ~200MB
REGEX CUSTOM:
  KTP:      r"\b\d{16}\b" (score 0.95)
  NPWP_NEW: r"\b0\d{15}\b" (score 0.9 — formato 16 cifre stranieri)
  NPWP_OLD: r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b" (score 0.9)
  PHONE_ID: r"\+62\d{8,12}" (score 0.8)
  PASSPORT: r"\b[A-Z]{1,2}\d{6,7}\b" (score 0.85)
INTEGRAZIONE: FastAPI middleware su tutti gli endpoint /api/agentic/* e /api/portal/*
VERIFICA: Query "il mio passport è AB1234567" → risposta con [PASSPORT_REDACTED]
SBLOCCA: Protezione PII leak in risposte AI
TEMPO: 2 giorni
```

### 1.5 Audit Logging [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Tabella audit immutabile per accesso a dati PII
FILE: backend/migrations/migration_067_audit_logs.py (NUOVA)
SCHEMA:
  CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT, client_id INTEGER,
    action TEXT NOT NULL,  -- READ, WRITE, DELETE, EXPORT, CROSS_BORDER
    resource TEXT NOT NULL, -- passport, ktp, npwp, profile, document
    ip_address INET, user_agent TEXT, details JSONB
  );
  CREATE RULE no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
  CREATE RULE no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
MIDDLEWARE: Log ogni accesso a endpoint che toccano PII (crm_clients, portal, ocr)
VERIFICA: Accedere a profilo cliente → riga in audit_logs
SBLOCCA: Compliance Art. 37 (monitoraggio attività), base per breach detection
TEMPO: 2 giorni
```

### 1.6 CI Coverage Fix [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Fix --cov=src → --cov=backend/ nel workflow GitHub Actions
FILE: .github/workflows/tests.yml
CODICE: Cambiare "pytest --cov=src" → "pytest --cov=backend/ --cov-fail-under=5"
VERIFICA: Push → CI esegue coverage su backend, fail se <5%
SBLOCCA: Gate test funzionante
TEMPO: 15 minuti
```

---

## FASE 2: QUICK WINS TECH (Settimana 2-3)

> 10 azioni a $0 che migliorano il sistema immediatamente.

### 2.1 Qdrant Scalar Quantization [OWNER: Claude Code Air/Pro] [MACCHINA: Air]
```
COSA: Attivare int8 quantization sui 93K vettori → -75% RAM (558MB → 140MB)
COME: Qdrant API → update collection config con quantization_config
PARAMETRI: scalar, type=int8, quantile=0.99, always_ram=true
VERIFICA: Qdrant dashboard → RAM usage ridotta. Search quality test su 100 query.
SBLOCCA: Spazio RAM per altri servizi su Fly.io 2GB
TEMPO: 1 giorno
```

### 2.2 KG Pruning [OWNER: Claude Code Air] [MACCHINA: Air → tunnel DB]
```
COSA: Eliminare ~5000 nodi orfani dal Knowledge Graph
SQL:
  DELETE FROM kg_nodes n
  WHERE NOT EXISTS (SELECT 1 FROM kg_edges e WHERE e.source_entity_id = n.entity_id OR e.target_entity_id = n.entity_id);
VERIFICA: SELECT COUNT(*) FROM kg_nodes → dovrebbe calare di ~5K
SBLOCCA: KG più pulito, GIN index più piccolo
TEMPO: 1 giorno (con backup prima)
```

### 2.3 GIN Index + pg_stat_statements [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Indice GIN su kg_nodes.properties + abilitare pg_stat_statements
SQL:
  CREATE INDEX CONCURRENTLY idx_gin_kg_properties ON kg_nodes USING GIN(properties);
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
VERIFICA: EXPLAIN ANALYZE su query KG → usa indice. pg_stat_statements → top slow queries visibili.
TEMPO: 30 minuti ciascuno
```

### 2.4 Fix Double Init [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Rimuovere doppia inizializzazione CulturalRAGService e CollaboratorService
FILE: backend/app/setup/service_initializer.py
VERIFICA: Startup log non mostra "Initializing CulturalRAG..." due volte
TEMPO: 15 minuti
```

### 2.5 Semantic Cache [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Cache risposte RAG per query semanticamente simili (>0.95 cosine)
FILE: backend/services/rag/agentic/reasoning.py (o nuovo cache middleware)
LOGICA:
  1. Embed query → cosine similarity con cache Redis (top-1)
  2. Se similarity > 0.95 → return cached response
  3. Else → process normalmente → cache result con TTL 1h
DIPENDENZA: Redis già disponibile (Upstash)
VERIFICA: Stessa domanda 2 volte → seconda risposta istantanea (<100ms)
SBLOCCA: -60% costo LLM, -50% latenza
TEMPO: 3 giorni
```

### 2.6 Prompt Compression V7 [OWNER: Claude Code Pro] [MACCHINA: Pro]
```
COSA: Comprimere ZANTARA_MASTER_TEMPLATE da ~2000 a ~300 token
FILE: backend/prompts/zantara_core.py
TAGLI:
  - CLOSING_PHRASES (50+ frasi → rimuovere, LLM varia da solo)
  - GREETING_RULES (verbose → 1 riga: "Greet only on first message")
  - Emotional adaptation (verbose → rimuovere, Claude/Gemini nativamente empatico)
  - Anti-pattern lists (→ condensare in 3 righe)
METODO: Usa Claude per comprimere: "Summarize this prompt to 300 tokens preserving core rules"
VERIFICA: A/B test su 100 query → quality parity (>95%)
SBLOCCA: -90% costo token con prompt caching ($720→$72/mese)
TEMPO: 3 giorni (incluso A/B test)
```

### 2.7 Prompt Caching Anthropic [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Attivare cache_control su system prompt nelle chiamate API Anthropic
FILE: backend/llm/ (dove si chiama Anthropic API)
CODICE:
  system=[{
    "type": "text",
    "text": ZANTARA_MASTER_TEMPLATE,
    "cache_control": {"type": "ephemeral"}
  }]
VERIFICA: response.usage.cache_read_input_tokens > 0 nelle chiamate successive
SBLOCCA: -90% costo input token ripetuti
TEMPO: 1 giorno
```

---

## FASE 3: ARCHITETTURA CORE (Settimana 3-6)

### 3.1 Self-RAG Reflection Loop [OWNER: Claude Code Pro] [MACCHINA: Pro → deploy Fly]
```
COSA: Aggiungere nodo check_hallucination + conditional edge al grafo LangGraph
FILE: backend/app/agents/graph.py
NODI: retrieve → grade → generate → check_hallucination → (OK → END | FAIL → transform_query → retrieve)
ATTIVAZIONE: Solo per CONFIDENCE < 0.30 (non tutte le query — limita latenza)
VERIFICA: Query con bassa confidence → retry automatico con query riscritta
SBLOCCA: Meno ABSTAIN, -40% hallucination
TEMPO: 1 settimana
```

### 3.2 BM42 Sparse Vectors [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Aggiungere vettori sparsi BM42 alle collection Qdrant esistenti
DIPENDENZE: pip install fastembed (Qdrant/bm42-all-minilm-l6-v2-attentions)
PROCEDURA:
  1. Aggiungere sparse_vectors_config alle collection
  2. Batch embed 93K documenti con BM42 (FastEmbed, locale)
  3. Upsert sparsi con stesso ID (non tocca densi)
  4. Attivare RRF in search_service.py
VERIFICA: Query "PP 5/2021" → match esatto (keyword) + semantico
SBLOCCA: +30% precision su query con numeri legge, cross-lingua Bahasa
TEMPO: 5 giorni
```

### 3.3 LangGraph Postgres Checkpointing [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Implementare AsyncPostgresSaver per memoria cross-sessione
FILE: backend/app/agents/graph.py, backend/app/setup/app_factory.py
DIPENDENZE: pip install langgraph-checkpoint-postgres psycopg[binary]
SETUP:
  pool = AsyncConnectionPool(conninfo=..., kwargs={"autocommit": True, "row_factory": dict_row})
  checkpointer = AsyncPostgresSaver(pool)
  await checkpointer.setup()
ATTENZIONE: Usa psycopg3, NON asyncpg. Pool separato. Lifecycle nel lifespan FastAPI.
VERIFICA: Conversazione multi-turno → AI ricorda contesto precedente
SBLOCCA: Memoria cross-sessione, base per conversation history
TEMPO: 3 giorni
```

### 3.4 Unified Conversation History [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Tabella PostgreSQL per storia conversazioni cross-canale
FILE: backend/migrations/migration_068_conversation_history.py (NUOVA)
SCHEMA:
  CREATE TABLE conversation_messages (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    channel TEXT NOT NULL, -- whatsapp, telegram, web, instagram
    direction TEXT NOT NULL, -- inbound, outbound
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  CREATE INDEX idx_conv_client ON conversation_messages(client_id, created_at DESC);
INTEGRAZIONE: channels/router.py → salva ogni messaggio dopo routing
VERIFICA: Messaggio WhatsApp + messaggio Web → entrambi visibili per stesso client_id
SBLOCCA: AI vede storia cross-canale, -34% domande ripetute
TEMPO: 1 settimana
```

### 3.5 RAG Facade Pattern [OWNER: Claude Code Pro] [MACCHINA: Pro]
```
COSA: Scomporre orchestrator_core.py (1,560 righe) in moduli
FILE:
  backend/services/rag/agentic/orchestrator_core.py → facade leggera (<300 righe)
  backend/services/rag/agentic/orchestrator_routing.py → routing logic (NUOVO)
  backend/services/rag/agentic/orchestrator_tools.py → tool management (NUOVO)
METODO: Estrarre prima check_gates_and_cache (L1002), poi tool dispatch, poi routing
ATTENZIONE: 5 dipendenze circolari (ARCH-01). Risolvere prima con deferred imports.
VERIFICA: Tutti i test esistenti passano. Import chain OK.
SBLOCCA: Manutenibilità 3x, sviluppo parallelo possibile
TEMPO: 2-3 settimane
```

---

## FASE 4: REVENUE (Mese 2-3)

### 4.1 Consent Banner + Crypto-Shredding [OWNER: Claude Code Air/Pro] [MACCHINA: entrambe]
```
COSA: Consent management su portal + crypto-shredding per audit log
FRONTEND: apps/mouth/src/app/portal/(authenticated)/layout.tsx → CookieConsent banner
BACKEND: consent_records table + middleware verifica consenso
CRYPTO: PII nel audit log cifrata con chiave per-utente. Cancellazione = elimina chiave.
TEMPO: 1 settimana
```

### 4.2 PII Encryption pgcrypto [OWNER: Claude Code Air] [MACCHINA: Air → DB]
```
COSA: Cifrare colonne PII in PostgreSQL
COLONNE: clients.passport_number, clients.npwp, clients.phone (le più critiche)
METODO: pgcrypto pgp_sym_encrypt/decrypt
KEY: fly secrets set ENCRYPTION_KEY=...
TEMPO: 1 settimana (migration + test + rollback plan)
```

### 4.3 WhatsApp Flows [OWNER: Claude Code Pro] [MACCHINA: Pro]
```
COSA: Implementare visa eligibility flow + document upload in WhatsApp
COMPONENTI: Flow JSON → screens → DocumentPicker → Xendit payment link
TEMPO: 2 settimane
```

### 4.4 Pricing Page + Tiers [OWNER: Claude Code Pro] [MACCHINA: Pro]
```
COSA: Pagina pricing su balizero.com con 3 tier (Basic/Standard/Premium)
PREZZI: $800 / $1,500 / $3,500 (setup) + $0 / $150 / $300 (retainer/mo)
COMPLIANCE-AS-A-SERVICE: $99 / $199 / $299 /mo
TEMPO: 3 giorni
```

### 4.5 KG API MVP [OWNER: Claude Code Air] [MACCHINA: Air]
```
COSA: Esporre Knowledge Graph come API pubblica (freemium)
ENDPOINT: /api/v1/kg/query (GraphQL o REST)
PRICING: Free 100 query/mese → $99/mo (1K query) → $499/mo (unlimited)
BILLING: Xendit/Stripe metered
TARGET: Studi legali, commercialisti, HR immigration Indonesia
PROIEZIONE: $50K MRR con 100 subscribers
TEMPO: 2-3 settimane
```

---

## FASE 5: SCALA (Mese 3-6)

### 5.1 BERT Intent Classification [MACCHINA: Pro (fine-tuning) → Air (ONNX serving)]
```
MODELLO: cahya/bert-base-indonesian-522M → fine-tune su ~1000 query etichettate
CATEGORIE: visa, tax, company, property, general
SERVING: ONNX export → FastAPI service separato (~300MB RAM)
SOSTITUISCE: regex in intent_classifier.py
```

### 5.2 KG Confidence Calibration [MACCHINA: Air]
```
METODO: Implicit feedback (tracking quali nodi producono risposte ad alta confidence)
IMPLEMENTAZIONE: confidence = confidence * 1.1 on use, * 0.9 on reject
```

### 5.3 Docker Slim + Prefect [MACCHINA: Air]
```
DOCKER: Multi-stage build, uv, Alpine/Distroless → immagine <200MB (da 1GB+)
WAR ROOM: Migrare da shell scripts a Prefect 3.0 @flow/@task
```

### 5.4 Langfuse LLM Observability [MACCHINA: Air]
```
TIER: Langfuse Cloud free (10K events/mese)
INTEGRAZIONE: LangGraph traces → Langfuse dashboard
```

### 5.5 Auth.js v5 SSO [MACCHINA: Pro]
```
COSA: Sostituire cookie manuale con Auth.js per SSO cross-subdomain
CONFIG: cookies.domain='.balizero.com'
CONSOLIDARE: 6 subdomain → 3 (kita, my, zantara)
```

---

## FASE X: X PREMIUM+ BLITZ (Parallelo, fino al 25 aprile)

> Questa fase corre IN PARALLELO a tutto il resto. Non blocca e non è bloccata.

### X.1 Pubblica Article #1 [OWNER: Zero] [MACCHINA: Pro browser]
```
FILE: docs/x-articles/001_KBLI_2025_DEADLINE.md → copia su X Articles
+ Thread promo da 001_PROMO_ASSETS.md
```

### X.2 Pubblica KBLI Decoded #001 [OWNER: Zero] [MACCHINA: Pro browser]
```
FILE: docs/x-articles/KBLI_DECODED_001_56101.md → copia su X Articles
```

### X.3 Setup X Pro Columns [OWNER: Zero] [MACCHINA: Pro browser]
```
8 colonne monitoring da X_PREMIUM_BLITZ_BATTLE_PLAN.md sezione Vector 3
```

### X.4 NLM Video [OWNER: Zero] [MACCHINA: Pro browser]
```
FILE: docs/nlm-sources/PRO_EXECUTION_INSTRUCTIONS.md (copiato su Pro)
Segui step-by-step: upload source → cinematic video → DaVinci Resolve post-prod
```

### X.5 Reply Farming [OWNER: Zero] [MACCHINA: Pro browser]
```
20 reply/giorno seguendo brand voice (docs/X_BRAND_VOICE.md)
Target account da Grok Research Sprint (X_PREMIUM_BLITZ_BATTLE_PLAN.md)
```

---

## ASSEGNAZIONE MACCHINE

| Macchina | Ruolo | Task principali |
|----------|-------|----------------|
| **Air** (Server H24) | Backend dev, deploy, DB operations, pipeline | Fase 1-3 backend, xAI pipeline, Qdrant ops |
| **Pro** (Dev 48GB) | Frontend, heavy AI, content, browser ops | Facade Pattern, BERT fine-tuning, X Blitz, NLM video |
| **Fly.io** | Production | Deploy dopo ogni fase completata |
| **Browser Pro** | Manual operations | PSE registration, X Articles, NLM, DPO |

---

## ORDINE DI BATTAGLIA (settimana per settimana)

```
SETTIMANA 1: SOPRAVVIVENZA
├── [Zero/Browser] PSE Registration + DPO Nomination
├── [Air] Rate limiter fix (1h)
├── [Air] Telegram PII fix (30min)
├── [Air] CI coverage fix (15min)
├── [Air] Presidio PII scanner (2gg)
├── [Air] Audit logging table (2gg)
├── [Air] Privacy policy page (1gg)
└── [Pro/Browser] X Article #1 + KBLI Decoded #1

SETTIMANA 2: STABILIZZAZIONE
├── [Air] Gemini OCR consent gate (1gg)
├── [Air] Qdrant scalar quantization (1gg)
├── [Air] KG pruning + GIN index (1gg)
├── [Air] Fix double init (15min)
├── [Air] pg_stat_statements (30min)
├── [Pro] Prompt compression V7 (3gg)
└── [Pro/Browser] X Articles #2-3 + Reply farming

SETTIMANA 3-4: PERFORMANCE
├── [Air] Semantic cache Redis (3gg)
├── [Air] Prompt caching Anthropic (1gg)
├── [Air] BM42 sparse vectors batch (5gg)
├── [Air] LangGraph Postgres checkpointing (3gg)
├── [Pro] Self-RAG reflection loop (5gg)
└── [Pro/Browser] X Articles + KBLI Decoded weekly

SETTIMANA 5-6: ARCHITETTURA
├── [Air] Unified conversation history (5gg)
├── [Pro] RAG Facade Pattern (2-3 sett)
├── [Air] Consent banner + crypto-shredding (5gg)
├── [Air] PII encryption pgcrypto (5gg)
└── [Pro/Browser] X Blitz finale (21-25 aprile)

MESE 2-3: REVENUE
├── [Pro] WhatsApp Flows (2 sett)
├── [Pro] Pricing page (3gg)
├── [Air] KG API MVP (2-3 sett)
├── [Pro] Compliance-as-a-Service package
└── [Air] Right to erasure endpoint

MESE 3-6: SCALA
├── [Pro] BERT intent classification
├── [Air] Docker slim + Prefect
├── [Air] Langfuse observability
├── [Pro] Auth.js SSO consolidation
└── [Air] KG confidence calibration
```

---

## METRICHE DI SUCCESSO

| Settimana | Metrica | Target |
|-----------|---------|--------|
| 1 | PSE filed + DPO nominato | SI/NO |
| 2 | PII scanner attivo + audit log funzionante | SI/NO |
| 3 | Qdrant RAM < 200MB + cache hit rate | >30% |
| 4 | Self-RAG ABSTAIN rate | <5% (da ~15%) |
| 6 | Prompt cost reduction | -80% |
| 8 | BM42 search precision | +30% su query keyword |
| 10 | X follower | +500 |
| 12 | KG API subscribers | 10+ |
| 16 | Monthly retainer clients | 100+ |
| 24 | MRR | $30K+ |

---

## RISCHI E MITIGAZIONI

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| PSE rifiutata | 10% | Consulente locale per revisione |
| Presidio non intercetta NPWP 16 cifre | 30% | Test con dataset reale prima di deploy |
| bge-reranker OOM su 2GB | 70% | DEFER — testare dimensione, eventualmente servizio separato |
| Facade Pattern rompe import chain | 40% | Risolvere dipendenze circolari PRIMA dello split |
| WhatsApp Flows rejection da Meta | 20% | Template review pre-submit |
| KG API zero subscribers | 50% | Validare con 10 clienti pilota prima di pricing page |

---

## BUDGET

| Voce | Costo | Note |
|------|-------|------|
| PSE Registration | $0-500 | Consulente opzionale |
| DPO (interim CTO) | $0 | O $200-500/mo se esterno |
| Presidio + Stanza | $0 | Open source |
| pgcrypto | $0 | Extension PostgreSQL |
| NLM Plus (1 mese video) | $0 | Abbiamo Ultra |
| xAI credits | ~$4 spesi / $25 free | $21 rimanenti |
| Fly.io | $35-40/mo | Già pagato |
| Vercel | $0 | Free tier |
| **TOTALE Fase 0-3** | **< $1,000** | |

---

*Piano Esecuzione Supremo v1.0 — 29 marzo 2026*
*Basato su: 12 round ricerca, 8 documenti strategici, 3 reviewer (Gemini+DeepSeek+Codex)*
*Compilato da: Claude Code (Opus 4.6) come Comandante Supremo*
*Per: Bali Zero / Nuzantara*

> "L'execution comincia lunedì. Non ci sono scuse."

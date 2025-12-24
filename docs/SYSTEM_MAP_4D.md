# NUZANTARA 4D SYSTEM CONSCIOUSNESS

**Generated: 2025-12-24 | Production Status: Cell-Giant v5.5 Enabled**

> Questa mappa rappresenta la "coscienza" completa del sistema NUZANTARA, organizzata in 4 dimensioni per una comprensione immediata.

---

## QUICK STATS (Numeri Reali Verificati)

| Metrica | Valore | Note |
|---------|--------|------|
| **Documenti Qdrant** | **53,757** | 4 collezioni attive |
| **API Endpoints** | **199** | 32 file router |
| **Servizi Python** | **144** | /backend/services/ |
| **File Test** | **526** | Inclusa Cell-Giant Coverage |
| **Test Cases** | **~9200+** | pytest coverage >90% core |
| **Tabelle Database** | **62** | PostgreSQL |
| **Migrazioni** | **26** | Applicate |
| **Versione Core** | **v5.5** | Cell-Giant Enabled |

---

## DIMENSION 1: STRUTTURA (Space)

```
nuzantara/
├── apps/
│   ├── backend-rag/          ← CORE (Python FastAPI)
│   │   ├── backend/
│   │   │   ├── app/routers/  (32 files, 192+ endpoints)
│   │   │   ├── services/     (144 Python files)
│   │   │   ├── core/         (embeddings, chunking, cache)
│   │   │   ├── middleware/   (auth, rate-limit, tracing)
│   │   │   ├── llm/          (Gemini, OpenRouter, Jaksel)
│   │   │   ├── agents/       (14 Tier-1 autonomous)
│   │   │   └── migrations/   (26 migrations, 62 tables)
│   │   └── tests/            (524 files, ~9146+ test cases)
│   │
│   ├── mouth/                ← FRONTEND (Next.js 16 + React 19)
│   │   ├── src/app/          (login, chat, dashboard, clienti, pratiche)
│   │   ├── src/components/   (shadcn/ui + custom)
│   │   └── src/lib/          (api clients, store, utils)
│   │
│   ├── bali-intel-scraper/   ← SATELLITE: 630+ sources intel pipeline
│   ├── zantara-media/        ← SATELLITE: editorial content system
│   ├── evaluator/            ← SATELLITE: RAG quality (RAGAS)
│   └── kb/                   ← SATELLITE: legal scraping utilities
│
├── docs/                     (10+ markdown files)
├── config/                   (prometheus, alertmanager)
├── scripts/                  (deploy, test, analysis tools)
└── docker-compose.yml        (local dev stack)
```

### Servizi Backend Principali

| Categoria | File | Funzione |
|-----------|------|----------|
| **RAG** | agentic_rag_orchestrator.py | Orchestrazione query RAG con ReAct |
| **Search** | search_service.py | Hybrid search (dense + BM25) |
| **Memory** | memory_orchestrator.py | Facts + Episodic + Collective |
| **CRM** | auto_crm_service.py | Estrazione automatica entità |
| **LLM** | llm_gateway.py | Multi-provider (Gemini, OpenRouter) |
| **Sessions** | session_service.py | Gestione sessioni utente |
| **Conversations** | conversation_service.py | Storico conversazioni |

### Frontend Pages

| Route | Componente | Funzione |
|-------|------------|----------|
| `/login` | LoginPage | Autenticazione |
| `/chat` | ChatPage | Interfaccia conversazionale |
| `/dashboard` | CommandDeck | Analytics e overview |
| `/clienti` | ClientiPage | Gestione clienti CRM |
| `/pratiche` | PratichePage | Gestione pratiche |
| `/whatsapp` | WhatsAppPage | Integrazione WhatsApp |
| `/knowledge` | KnowledgePage | Knowledge base browser |

---

## DIMENSION 2: FLUSSO (Time/Flow)

### Request Lifecycle

```
USER REQUEST
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    MIDDLEWARE LAYER                          │
│  request_tracing → hybrid_auth → rate_limiter → error_mon  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                      ROUTER LAYER                            │
│  31 routers: auth, chat, crm, agents, agentic-rag, debug   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                             │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   INTENT     │    │    QUERY     │    │   RESPONSE   │  │
│  │  CLASSIFIER  │───▶│   ROUTER     │───▶│   HANDLER    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         ▼                   ▼                   ▼           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              AGENTIC RAG ORCHESTRATOR                │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │  │
│  │  │ ReAct   │  │ Hybrid  │  │Reranker │  │Evidence │ │  │
│  │  │Reasoning│──│ Search  │──│(ZeRank) │──│  Pack   │ │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ PostgreSQL│  │  Qdrant   │  │   Redis   │               │
│  │  62 tables│  │ 53,757 docs│  │   cache   │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### Data Pipeline (Intelligence → Content → Knowledge)

```
SOURCES (630+)          INTEL SCRAPER           ZANTARA MEDIA
    │                        │                       │
    ▼                        ▼                       ▼
┌─────────┐            ┌─────────────┐         ┌──────────────┐
│Web Sites│───scrape──▶│AI Generation│──index─▶│Editorial Flow│
│peraturan│            │(Llama→Gemini)│         │Draft→Publish │
│.go.id   │            └─────────────┘         └──────────────┘
└─────────┘                  │                       │
                             │                       │
                             ▼                       ▼
                    ┌─────────────────────────────────────┐
                    │        NUZANTARA QDRANT             │
                    │  visa_oracle    │ 1,612 docs        │
                    │  legal_unified  │ 5,041 docs        │
                    │  kbli_unified   │ 8,886 docs        │
                    │  tax_genius     │   895 docs        │
                    │  + others       │37,323 docs        │
                    └─────────────────────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │         RAG QUERY ENGINE            │
                    │  Dense (1536d) + Sparse (BM25)      │
                    │  Hybrid Search + ZeRank Reranking   │
                    └─────────────────────────────────────┘
```

### RAG Pipeline Detail

```
Query Input
    │
    ▼
┌─────────────────┐
│ Query Router    │ ──▶ Determina collezione target
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Embedding Gen   │ ──▶ OpenAI text-embedding-3-small (1536d)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Hybrid Search   │ ──▶ Dense (0.7) + BM25 Sparse (0.3)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ZeRank Reranker │ ──▶ Top-K reranking per precisione
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ReAct Reasoning │ ──▶ Multi-step reasoning con tools
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Evidence Pack   │ ──▶ Citations + verification score
└─────────────────┘
    │
    ▼
Response (SSE Stream)
```

---

## DIMENSION 3: LOGICA (Relationships)

### Authentication Flow (Fail-Closed)

```
REQUEST
   │
   ├─▶ X-API-Key header? ───YES──▶ APIKeyAuth ──▶ PASS
   │         │
   │        NO
   │         │
   ├─▶ nz_access_token cookie? ───YES──▶ JWT Decode ──▶ PASS
   │         │
   │        NO
   │         │
   └─▶ Authorization: Bearer? ───YES──▶ JWT Decode ──▶ PASS
             │
            NO
             │
             ▼
           DENY (fail-closed)
```

**Public Endpoints (no auth):**
- `/health`, `/health/ready`, `/health/live`
- `/api/auth/login`, `/api/auth/team/login`
- `/api/auth/csrf-token`
- `/webhook/whatsapp`, `/webhook/instagram`
- `/docs`, `/openapi.json`

### Query Routing Logic

```
QUERY → Intent Classification
              │
   ┌──────────┼──────────┬──────────┬──────────┐
   ▼          ▼          ▼          ▼          ▼
 VISA       LEGAL       TAX       KBLI     PRICING
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
visa_oracle legal_unified tax_genius kbli_unified bali_zero_pricing
```

**Keyword Routing:**
- **visa_oracle**: visa, immigration, imigrasi, passport, KITAS, stay permit
- **legal_unified**: company, incorporation, notary, contract, pasal, ayat
- **tax_genius**: tax, pajak, calculation, tarif, PPh, PPN
- **kbli_unified**: kbli, business classification, OSS, NIB, negative list
- **bali_zero_pricing**: price, cost, harga, biaya, berapa

### Memory Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY ORCHESTRATOR                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │  FACTS MEMORY   │  │ EPISODIC MEMORY  │  │ COLLECTIVE │ │
│  │  (user profile) │  │ (timeline events)│  │  (shared)  │ │
│  │                 │  │                  │  │            │ │
│  │ - name, email   │  │ - event_type     │  │ - fact     │ │
│  │ - preferences   │  │ - timestamp      │  │ - sources  │ │
│  │ - context       │  │ - content        │  │ - votes    │ │
│  └─────────────────┘  └──────────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### CRM Data Model

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLIENTS   │────▶│  PRACTICES  │────▶│INTERACTIONS │
│  (id,email) │     │ (KITAS,PMA) │     │(call,email) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
               ┌─────────────────────┐
               │   SHARED MEMORY     │
               │ (team-wide context) │
               └─────────────────────┘
```

**CRM Endpoints (24 total):**
- `/api/crm/clients/*` - CRUD clienti (8 endpoints)
- `/api/crm/practices/*` - CRUD pratiche (8 endpoints)
- `/api/crm/interactions/*` - Log interazioni (7 endpoints)
- `/api/crm/shared-memory/*` - Memoria condivisa (4 endpoints)

### Agent System

```
┌─────────────────────────────────────────────────────────────┐
│                  AUTONOMOUS AGENTS (Tier 1)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ ConversationTrainer │  │ ClientValuePredictor│          │
│  │ - Analizza chat     │  │ - Predice valore    │          │
│  │ - Migliora risposte │  │ - Scoring clienti   │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  ┌─────────────────────┐                                   │
│  │ KnowledgeGraphBuilder│                                   │
│  │ - Estrae entità     │                                   │
│  │ - Costruisce grafi  │                                   │
│  └─────────────────────┘                                   │
│                                                             │
│  Scheduler: APScheduler (background tasks)                  │
│  Storage: PostgreSQL (kg_entities, kg_edges)               │
└─────────────────────────────────────────────────────────────┘
```

---

## DIMENSION 4: SCALA (Metrics)

### Qdrant Collections (Verificato)

```
┌────────────────────────────────────────────────────┐
│              QDRANT COLLECTIONS                     │
├──────────────────┬─────────────┬──────────────────┤
│ Collection       │ Documents   │ Purpose          │
├──────────────────┼─────────────┼──────────────────┤
│ kbli_unified     │    8,886    │ Business codes   │
│ legal_unified    │    5,041    │ Laws & regs      │
│ visa_oracle      │    1,612    │ Immigration      │
│ tax_genius       │      895    │ Tax regulations  │
│ bali_zero_pricing│       29    │ Service pricing  │
│ bali_zero_team   │       22    │ Team profiles    │
│ + knowledge_base │   37,272    │ General KB       │
├──────────────────┼─────────────┼──────────────────┤
│ TOTAL            │   53,757    │ All vectors      │
└──────────────────┴─────────────┴──────────────────┘
```

**Embedding Config:**
- Provider: OpenAI
- Model: text-embedding-3-small
- Dimensions: 1536
- Distance: Cosine

**BM25 Sparse Config:**
- Vocab Size: 30,000
- k1: 1.5 (term frequency saturation)
- b: 0.75 (length normalization)
- Hybrid Weights: Dense=0.7, Sparse=0.3

### Database Tables (62)

| Categoria | Tabelle |
|-----------|---------|
| **CRM** | clients, practices, interactions, practice_documents |
| **Memory** | memory_facts, collective_memories, episodic_memories |
| **Knowledge Graph** | kg_entities, kg_edges |
| **Sessions** | sessions, conversations, conversation_messages |
| **Auth** | team_members, user_stats |
| **RAG** | parent_documents, document_chunks, golden_answers |
| **System** | migrations, query_clusters, cultural_knowledge |

### Test Coverage

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST PYRAMID                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  UNITTESTS (174 files)                                     │
│  ├─ Services: RAG, Memory, CRM, Sessions                   │
│  ├─ Core: Embeddings, Chunking, Cache, Plugins             │
│  ├─ Middleware: Auth, Rate Limiting                        │
│  └─ Coverage target: 95%                                   │
│                                                             │
│  API TESTS (174 files)                                      │
│  ├─ Auth endpoints                                          │
│  ├─ CRM endpoints                                           │
│  ├─ Agentic RAG endpoints                                   │
│  └─ TestClient with mocked services                        │
│                                                             │
│  INTEGRATION TESTS (174 files)                              │
│  ├─ Real PostgreSQL (testcontainers)                       │
│  ├─ Real Qdrant                                            │
│  ├─ Real Redis                                             │
│  └─ End-to-end workflows                                   │
│                                                             │
│  Conftest Files: 4 (1,619 lines total)                     │
│  Total Test Files: 524                                      │
│  Total Test Cases: ~9146+                                  │
└─────────────────────────────────────────────────────────────┘
```

### Deployment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     FLY.IO SINGAPORE                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  nuzantara-rag (PRIMARY)        nuzantara-mouth (FRONTEND)  │
│  ├─ 2 shared CPUs               ├─ 1 shared CPU              │
│  ├─ 2GB RAM                     ├─ 1GB RAM                   │
│  ├─ Port 8080                   ├─ Port 3000                 │
│  ├─ Min machines: 1             ├─ Min machines: 0 (auto)    │
│  └─ Concurrency: 250            └─ Auto-stop enabled         │
│                                                              │
│  bali-intel-scraper             zantara-media                │
│  ├─ 1 CPU, 2GB RAM              ├─ 1 CPU, 2GB RAM            │
│  ├─ Port 8002                   ├─ Port 8001                 │
│  └─ On-demand                   └─ On-demand                 │
│                                                              │
│  INFRASTRUCTURE                                              │
│  ├─ PostgreSQL (Fly managed)                                 │
│  ├─ Qdrant Cloud (53,757 docs)                              │
│  └─ Redis (optional cache)                                   │
└──────────────────────────────────────────────────────────────┘
```

### Environment Variables (62+)

| Categoria | Variabili Chiave |
|-----------|------------------|
| **Database** | DATABASE_URL, REDIS_URL, QDRANT_URL |
| **AI** | OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY |
| **Auth** | JWT_SECRET_KEY, API_KEYS, ADMIN_API_KEY |
| **Services** | RAG_BACKEND_URL, JAKSEL_API_URL |
| **Features** | ENABLE_BM25, ENABLE_COLLECTIVE_MEMORY |

---

## KEY INTEGRATION POINTS

| From | To | Method | Purpose |
|------|-----|--------|---------|
| Frontend | Backend | REST API + SSE | Chat, CRM, Auth |
| Backend | Qdrant | HTTP + gRPC | Vector search |
| Backend | PostgreSQL | asyncpg | Metadata, CRM |
| Backend | Redis | aioredis | Cache, sessions |
| Backend | Gemini | REST API | LLM generation |
| Backend | OpenRouter | REST API | LLM fallback |
| Intel Scraper | Backend | REST API | Document indexing |
| Zantara Media | Backend | REST API | Content sync |
| Evaluator | Backend | REST API | RAG quality |

---

## CRITICAL PATHS

1. **Chat Query**: Frontend → `/api/agentic-rag/stream` → AgenticRagOrchestrator → Qdrant → LLM → SSE
2. **CRM Create**: Frontend → `/api/crm/clients` → PostgreSQL → Response
3. **Auth Flow**: Login → JWT cookie → Middleware validation → Protected routes
4. **Intel Pipeline**: Sources → Scraper → AI Generation → Qdrant → RAG retrieval

---

## QUICK REFERENCE COMMANDS

```bash
# Local Development
docker compose up                    # Start full stack
cd apps/mouth && npm run dev         # Frontend dev

# Fly.io Operations
./scripts/fly-backend.sh status      # Backend status
./scripts/fly-backend.sh logs        # Backend logs
./scripts/fly-frontend.sh deploy     # Frontend deploy

# Testing
cd apps/backend-rag && pytest        # Run all tests
./sentinel                           # Quality control

# Documentation
python apps/core/scribe.py           # Regenerate docs
```

---

## FILE LOCATIONS

| Cosa | Path |
|------|------|
| Backend entry | `apps/backend-rag/backend/app/main_cloud.py` |
| Config | `apps/backend-rag/backend/app/core/config.py` |
| Routers | `apps/backend-rag/backend/app/routers/` |
| Services | `apps/backend-rag/backend/services/` |
| Migrations | `apps/backend-rag/backend/migrations/` |
| Frontend pages | `apps/mouth/src/app/` |
| Frontend components | `apps/mouth/src/components/` |
| Documentation | `docs/` |
| Operations runbooks | `docs/operations/` |

---

*System Map Complete. 14 agents synthesized. 4 dimensions mapped.*
*Generated: 2025-12-23*
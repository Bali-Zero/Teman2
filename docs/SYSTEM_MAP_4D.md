# NUZANTARA 4D SYSTEM CONSCIOUSNESS

**Generated: 2026-02-02 | Updated: 2026-03-22**

> Questa mappa rappresenta la "coscienza" completa del sistema NUZANTARA, organizzata in 4 dimensioni per una comprensione immediata.

---

## DIMENSION 0: STRATEGIA (Omnichannel)

> **See full strategy:** [OMNICHANNEL_STRATEGY.md](../docs/architecture/OMNICHANNEL_STRATEGY.md)

### The Hydrated Frontend

The interface is liquid; intelligence is solid.

| Channel              | Tech              | Role                                  | Status |
| -------------------- | ----------------- | ------------------------------------- | ------ |
| **Web Command Deck** | Next.js + React   | Deep Work, Admin, Analytics           | ✅     |
| **Telegram**         | Bot API (OpenClaw)| Notifications, Approvals, Quick Tasks | ✅     |
| **WhatsApp**         | Meta Cloud API    | Client Communication, Docs            | ✅     |
| **Instagram**        | Meta API          | Brand Presence                        | ✅     |
| **X/Twitter**        | Twitter API       | Social Monitoring                     | ❌ CRC |
| **Google Chat**      | GChat API         | (Scaffold)                            | 🔧     |
| **Slack**            | Slack API         | (Scaffold)                            | 🔧     |

---

## QUICK STATS (Numeri Reali Verificati)

| Metrica                 | Valore      | Note                                  |
| ----------------------- | ----------- | ------------------------------------- |
| **Documenti Qdrant**    | **66,595**  | 9 collezioni live + 11 defined        |
| **API Endpoints**       | **88**      | Router files                          |
| **Servizi Python**      | **244**     | /backend/services/                    |
| **File Test**           | **385**     | unit/api/integration                  |
| **MCP Tools**           | **109+14**  | nuzantara-mcp + nuzantara-mcp-advanced|
| **Tabelle Database**    | **24+**     | PostgreSQL                            |
| **Migrazioni**          | **60**      | Applicate                             |
| **Knowledge Graph**     | **56,113 nodes / 161,173 edges** | PostgreSQL    |
| **Canali Comunicazione**| **7**       | WhatsApp, Telegram, IG, X, Web, GChat, Slack |
| **Fonti Intel**         | **630+**    | 12 categorie                          |
| **Fly.io Apps**         | **3**       | rag + postgres + qdrant (Singapore)   |

---

## DIMENSION 1: STRUTTURA (Space)

```
nuzantara/
├── apps/
│   ├── backend-rag/          ← CORE (Python FastAPI)
│   │   ├── backend/
│   │   │   ├── app/routers/  (88 router files)
│   │   │   ├── services/     (244 Python files)
│   │   │   ├── channels/     (7: whatsapp, telegram, instagram, twitter, web, gchat, slack)
│   │   │   ├── core/         (embeddings, chunking, cache)
│   │   │   ├── middleware/   (auth, rate-limit, tracing)
│   │   │   ├── llm/          (Gemini, Ollama, OpenRouter)
│   │   │   ├── prompts/      (zantara_core.py — Single Source of Truth)
│   │   │   └── migrations/   (60 migrations)
│   │   └── tests/            (385 test files)
│   │
│   ├── mouth/                ← FRONTEND (Next.js + React)
│   │   ├── src/app/          (workspace, portal, blog, kbli)
│   │   ├── src/components/   (shadcn/ui + custom)
│   │   └── src/lib/          (api clients, store, utils)
│   │
│   ├── nuzantara-mcp/        ← MCP Server v2.1 (109 tools, 10 prompts, 5 resources, 8 chains)
│   ├── nuzantara-mcp-advanced/ ← Advanced MCP (Fly.io ops, 14 tools)
│   ├── bali-intel-scraper/   ← Intel pipeline (LOCAL Pro only, NOT Fly)
│   ├── evaluator/            ← QA + Core Guardian V3
│   ├── war-room/             ← Ops dashboard + Canva automation
│   ├── zantara-media/        ← Editorial content system
│   ├── graph-engine/         ← Graph processing engine
│   └── calendar/drive/knowledge/mail/web/ ← Subdomain satellites
│
├── docs/                     (209+ markdown files)
├── config/                   (prometheus, alertmanager)
├── scripts/                  (deploy, test, analysis tools)
└── docker-compose.yml        (local dev stack)
```

### Servizi Backend Principali

| Categoria         | File                        | Funzione                            |
| ----------------- | --------------------------- | ----------------------------------- |
| **RAG**           | agentic_rag_orchestrator.py | Orchestrazione query RAG con ReAct  |
| **Search**        | search_service.py           | Hybrid search (dense + BM25)        |
| **Memory**        | memory_orchestrator.py      | Facts + Episodic + Collective       |
| **CRM**           | auto_crm_service.py         | Estrazione automatica entità        |
| **LLM**           | llm_gateway.py              | Multi-provider (Gemini, OpenRouter) |
| **Sessions**      | session_service.py          | Gestione sessioni utente            |
| **Conversations** | conversation_service.py     | Storico conversazioni               |

### Frontend Pages

| Route        | Componente    | Funzione                    |
| ------------ | ------------- | --------------------------- |
| `/login`     | LoginPage     | Autenticazione              |
| `/chat`      | ChatPage      | Interfaccia conversazionale |
| `/dashboard` | CommandDeck   | Analytics e overview        |
| `/clienti`   | ClientiPage   | Gestione clienti CRM        |
| `/pratiche`  | PratichePage  | Gestione pratiche           |
| `/whatsapp`  | WhatsAppPage  | Integrazione WhatsApp       |
| `/knowledge` | KnowledgePage | Knowledge base browser      |

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
│  88 routers: auth, chat, crm, agents, agentic-rag, debug   │
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
│  │  24+tables│  │ 66,595 docs│  │   cache   │               │
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
                    │  visa_oracle         │  1,612 docs  │
                    │  legal_unified       │  5,041 docs  │
                    │  legal_unified_hybrid│ 47,959 docs  │
                    │  kbli_2025_final     │  8,886 docs  │
                    │  tax_genius          │    895 docs  │
                    │  + 4 others          │  2,202 docs  │
                    │  TOTAL: 9 live       │ 66,595 docs  │
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
│ TOTAL            │   66,595    │ All vectors      │
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

### Database Tables (24)

| Categoria           | Tabelle                                              |
| ------------------- | ---------------------------------------------------- |
| **CRM**             | clients, practices, interactions, practice_documents |
| **Memory**          | memory_facts, collective_memories, episodic_memories |
| **Knowledge Graph** | kg_entities, kg_edges                                |
| **Sessions**        | sessions, conversations, conversation_messages       |
| **Auth**            | team_members, user_stats                             |
| **RAG**             | parent_documents, document_chunks, golden_answers    |
| **System**          | migrations, query_clusters, cultural_knowledge       |

### Test Coverage

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST PYRAMID                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  UNITTESTS (156 files)                                     │
│  ├─ Services: RAG, Memory, CRM, Sessions                   │
│  ├─ Core: Embeddings, Chunking, Cache, Plugins             │
│  ├─ Middleware: Auth, Rate Limiting                        │
│  └─ Coverage target: 95%                                   │
│                                                             │
│  API TESTS (156 files)                                      │
│  ├─ Auth endpoints                                          │
│  ├─ CRM endpoints                                           │
│  ├─ Agentic RAG endpoints                                   │
│  └─ TestClient with mocked services                        │
│                                                             │
│  INTEGRATION TESTS (156 files)                              │
│  ├─ Real PostgreSQL (testcontainers)                       │
│  ├─ Real Qdrant                                            │
│  ├─ Real Redis                                             │
│  └─ End-to-end workflows                                   │
│                                                             │
│  Conftest Files: 2 (1,619 lines total)                     │
│  Total Test Files: 468                                      │
│  Total Test Cases: ~5308+                                  │
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
│  ├─ Qdrant Cloud (66,595 docs)                              │
│  └─ Redis (optional cache)                                   │
└──────────────────────────────────────────────────────────────┘
```

### Environment Variables (63+)

| Categoria    | Variabili Chiave                                  |
| ------------ | ------------------------------------------------- |
| **Database** | DATABASE_URL, REDIS_URL, QDRANT_URL               |
| **AI**       | OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY |
| **Auth**     | JWT_SECRET_KEY, API_KEYS, ADMIN_API_KEY           |
| **Services** | RAG_BACKEND_URL, JAKSEL_API_URL                   |
| **Features** | ENABLE_BM25, ENABLE_COLLECTIVE_MEMORY             |

---

## KEY INTEGRATION POINTS

| From          | To         | Method         | Purpose           |
| ------------- | ---------- | -------------- | ----------------- |
| Frontend      | Backend    | REST API + SSE | Chat, CRM, Auth   |
| Backend       | Qdrant     | HTTP + gRPC    | Vector search     |
| Backend       | PostgreSQL | asyncpg        | Metadata, CRM     |
| Backend       | Redis      | aioredis       | Cache, sessions   |
| Backend       | Gemini     | REST API       | LLM generation    |
| Backend       | OpenRouter | REST API       | LLM fallback      |
| Intel Scraper | Backend    | REST API       | Document indexing |
| Zantara Media | Backend    | REST API       | Content sync      |
| Evaluator     | Backend    | REST API       | RAG quality       |

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

| Cosa                | Path                                          |
| ------------------- | --------------------------------------------- |
| Backend entry       | `apps/backend-rag/backend/app/main_cloud.py`  |
| Config              | `apps/backend-rag/backend/app/core/config.py` |
| Routers             | `apps/backend-rag/backend/app/routers/`       |
| Services            | `apps/backend-rag/backend/services/`          |
| Migrations          | `apps/backend-rag/backend/migrations/`        |
| Frontend pages      | `apps/mouth/src/app/`                         |
| Frontend components | `apps/mouth/src/components/`                  |
| Documentation       | `docs/`                                       |
| Operations runbooks | `docs/operations/`                            |

---

_System Map Complete. 46 agents synthesized. 4 dimensions mapped._
_Generated: 2026-02-02_

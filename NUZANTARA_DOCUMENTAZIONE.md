# 📚 NUZANTARA - DOCUMENTAZIONE TECNICA E DI BUSINESS

**Generated:** 2026-01-25
**Version:** 2.0

---

# PARTE 1: BUSINESS

## 🎯 Vision: Intelligent Business OS

Nuzantara è un **Sistema Operativo per consulenze moderne** ottimizzato per il contesto Indonesia/Bali. Risolve il problema della **conoscenza frammentata e operazioni disconnesse**.

---

## 💼 Value Propositions

### 1. Staff "Onnisciente"
**Problema:** Staff turnover alto, leggi che cambiano, training lungo.
**Soluzione:** RAG (Retrieval Augmented Generation) come esperto senior 24/7.

- Junior può chiedere "Quali implicazioni fiscali per X?" e ricevere risposta basata su documenti interni + leggi locali aggiornate.
- **Impatto:** Riduzione costi training, consistenza, meno errori.

### 2. CRM Automatizzato
**Problema:** Gestire centinaia di clienti, scadenze visa, documenti = manuale e soggetto a errori.
**Soluzione:** CRM integrato con Intelligence Engine.

- Monitoraggio automatico scadenze
- Alert proattivi
- Draft email automatiche
- **Impatto:** Scalabilità 10x con stesso headcount.

### 3. Omni-Channel
**Problema:** Clienti vogliono WhatsApp/Telegram ma i dati si perdono.
**Soluzione:** Integrazione diretta WhatsApp e Telegram.

- Messaggi fluiscono nel sistema centrale
- AI può suggerire risposte
- Log automatico interazioni
- **Impatto:** Esperienza cliente migliore, zero data loss.

---

## 👥 Target Users

| User | Interface | Use Case |
|------|-----------|----------|
| **Team Interno** | Workspace | Lavoro quotidiano, ricerche, CRM |
| **Clienti** | Portal | Tracking pratiche, documenti |
| **Management** | Dashboard | Pulse real-time del business |

---

## 🔑 Core Features

### 🧠 Intelligence Center
- **News Room:** Aggregazione news Indonesia/Bali
- **Visa Oracle:** Risposte accurate su visti
- **Article Composer:** Generazione contenuti AI-assisted

### 👥 CRM
- **Kanban Board:** Gestione pratiche visual
- **Client Profiles:** Storico completo
- **Google Drive Integration:** Documenti sincronizzati
- **Compliance Calendar:** Scadenze automatiche

### 💬 Comunicazione
- **Chat AI (Zantara):** Assistente intelligente
- **WhatsApp/Telegram:** Integrati nel sistema
- **Email (Zoho):** Inbox condivisa

---

# PARTE 2: ARCHITETTURA TECNICA

## 🏗️ Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        NUZANTARA                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                │
│  │  Mouth   │   │  Intel   │   │  Media   │   Frontends    │
│  │ (Next.js)│   │ Scraper  │   │ Service  │                │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘                │
│       │              │              │                       │
│       └──────────────┼──────────────┘                       │
│                      │                                      │
│                      ▼                                      │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                 BACKEND-RAG                           │ │
│  │                  (FastAPI)                            │ │
│  │  ┌─────────────────────────────────────────────────┐  │ │
│  │  │           Agentic RAG Orchestrator              │  │ │
│  │  │  ┌─────────┐ ┌──────────┐ ┌─────────────────┐   │  │ │
│  │  │  │ Intent  │ │ LLM      │ │ Tool Executor   │   │  │ │
│  │  │  │Classifier│ │ Gateway  │ │ (ReAct Pattern) │   │  │ │
│  │  │  └─────────┘ └──────────┘ └─────────────────┘   │  │ │
│  │  └─────────────────────────────────────────────────┘  │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │ │
│  │  │ Search  │ │ Memory  │ │ CRM     │ │ Integrations│  │ │
│  │  │ Service │ │ Handler │ │ Service │ │ (WA,TG,Zoho)│  │ │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └─────────────┘  │ │
│  └───────┼───────────┼───────────┼───────────────────────┘ │
│          │           │           │                         │
│          ▼           ▼           ▼                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │
│  │  Qdrant   │ │   Redis   │ │ PostgreSQL│ │   Gemini  │  │
│  │ (Vectors) │ │  (Cache)  │ │   (Data)  │ │   (LLM)   │  │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 RAG Pipeline

### Retrieval Augmented Generation

```
Query: "Qual è la procedura per KITAS investor?"
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  1. INTENT CLASSIFICATION                       │
│     • Simple → TIER_FLASH (fast/cheap)          │
│     • Complex → TIER_PRO                        │
│     • Reasoning → DeepThink                     │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  2. SEMANTIC CACHE CHECK                        │
│     • Hash query → check Redis                  │
│     • If hit → return cached response           │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  3. CONTEXT RETRIEVAL (Qdrant)                  │
│     • Embed query → vector                      │
│     • ANN search → top-k documents              │
│     • Rerank with Cohere (optional)             │
│     • Return: visa docs, regulations, FAQs      │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  4. PROMPT BUILDING                             │
│     • System prompt (persona, rules)            │
│     • Retrieved context                         │
│     • Conversation history                      │
│     • User query                                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  5. LLM CALL (with fallback)                    │
│     • Try: Gemini 2.5 Flash                     │
│     • Fallback: Gemini 2.0 Flash                │
│     • Last resort: OpenRouter (Claude Haiku)    │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  6. TOOL EXECUTION (if needed)                  │
│     • ReAct pattern: Thought→Action→Observe     │
│     • Tools: search, pricing, team lookup       │
│     • Loop until answer complete                │
└─────────────────────────────────────────────────┘
                    │
                    ▼
Response with sources and citations
```

---

## 📊 Data Architecture

### PostgreSQL (Structured Data)
```sql
-- Core tables
users           -- Auth, profiles
clients         -- CRM clients
practices       -- Active cases/pratiche
team_members    -- Staff directory
conversations   -- Chat history metadata

-- Relations
client_documents   -- GDrive links
practice_timeline  -- Status history
compliance_alerts  -- Scadenze
```

### Qdrant (Vector Store)
```python
collections = {
    "nuzantara_knowledge": {
        # Main knowledge base
        "vectors": 1536,  # text-embedding-3-small
        "payload": ["title", "content", "source", "category", "date"]
    },
    "bali_intel": {
        # News and regulations
        "vectors": 1536,
        "payload": ["headline", "summary", "source_url", "published_date"]
    },
    "training_conversations": {
        # Example Q&A pairs
        "vectors": 1536,
        "payload": ["question", "answer", "category"]
    },
    "legal_documents": {
        # Laws, regulations
        "vectors": 1536,
        "payload": ["law_number", "pasal", "content", "effective_date"]
    }
}
```

### Redis (Cache/Sessions)
```
Keys:
├── session:{id}          # User sessions
├── rate_limit:{ip}       # Rate limiting
├── semantic_cache:{hash} # Query cache
└── ws_channel:{id}       # WebSocket state
```

---

## 🤖 LLM Configuration

### Model Tiers
| Tier | Model | Use Case | Cost |
|------|-------|----------|------|
| FLASH | gemini-2.5-flash | Default queries | Low |
| FALLBACK | gemini-2.0-flash | When Flash fails | Lower |
| OPENROUTER | claude-3-haiku | Last resort | Variable |

### Fallback Cascade
```
Request
   │
   ▼
Gemini 2.5 Flash (primary)
   │
   ├── Success → Return
   │
   ▼ (quota/error)
Gemini 2.0 Flash
   │
   ├── Success → Return
   │
   ▼ (still failing)
OpenRouter (Claude Haiku)
   │
   └── Return (or error)
```

---

## 🔐 Authentication

```python
# Hybrid auth: Cookie + API Key
AUTH_METHODS = {
    "cookie": {
        "name": "nuzantara_session",
        "secure": True,
        "httponly": True,
        "samesite": "lax"
    },
    "api_key": {
        "header": "X-API-Key",
        "prefix": "nuz_"
    }
}

# JWT claims
{
    "sub": "user_id",
    "email": "user@example.com",
    "role": "admin|team|client",
    "exp": 1234567890
}
```

---

## 📡 API Endpoints (Key)

### RAG/Chat
```
POST /api/agentic-rag/query    # Non-streaming
POST /api/agentic-rag/stream   # SSE streaming
```

### CRM
```
GET    /api/crm/clients
POST   /api/crm/clients
GET    /api/crm/clients/{id}
PUT    /api/crm/clients/{id}
DELETE /api/crm/clients/{id}
```

### Intelligence
```
GET  /api/intel/staging        # Pending articles
POST /api/intel/approve/{id}   # Approve for publish
GET  /api/intel/published      # Published articles
```

### Team
```
GET  /api/team/members
POST /api/team/clock-in
POST /api/team/clock-out
```

---

## 🚀 Deployment

### Infrastructure
```yaml
# Fly.io (Backend)
backend:
  image: nuzantara-backend
  port: 8080
  env:
    - DATABASE_URL
    - QDRANT_URL
    - REDIS_URL
    - GOOGLE_API_KEY

# Vercel (Frontend)
frontend:
  framework: nextjs
  build: npm run build
  env:
    - NEXT_PUBLIC_API_URL
    - NEXT_PUBLIC_WS_URL
```

### External Services
- **Qdrant Cloud:** Vector database
- **Neon/Supabase:** PostgreSQL
- **Upstash:** Redis
- **Google AI:** Gemini models
- **Sentry:** Error tracking
- **Vercel Analytics:** Frontend metrics

---

## 📈 Monitoring

### Metrics (Prometheus)
```
# Request metrics
http_requests_total{method, endpoint, status}
http_request_duration_seconds{method, endpoint}

# RAG metrics
rag_queries_total{tier, model}
rag_latency_seconds{tier}
rag_cache_hits_total
rag_fallback_total{from_model, to_model}

# LLM metrics
llm_tokens_used{model, type}
llm_cost_usd{model}
```

### Alerts
- Error rate > 5%
- P95 latency > 5s
- LLM fallback rate > 10%
- Qdrant connection failures

---

## 🔧 Development

### Local Setup
```bash
# Backend
cd apps/backend-rag
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
uvicorn backend.app.main_cloud:app --reload

# Frontend
cd apps/mouth
npm install
npm run dev
```

### Testing
```bash
# Backend
pytest tests/ -v --cov=backend

# Frontend
npm run test
npm run e2e
```

### Environment Variables
```env
# Backend
DATABASE_URL=postgresql://...
QDRANT_URL=https://...
QDRANT_API_KEY=...
REDIS_URL=redis://...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...

# Frontend
NEXT_PUBLIC_API_URL=https://api.nuzantara.com
NEXT_PUBLIC_WS_URL=wss://api.nuzantara.com
```

---

## 📋 Key Files Reference

| Area | File | Purpose |
|------|------|---------|
| **Backend Entry** | `main_cloud.py` | FastAPI app |
| **RAG Core** | `orchestrator.py` | Query processing |
| **LLM** | `llm_gateway.py` | Model routing |
| **Search** | `search_service.py` | Qdrant queries |
| **Frontend Entry** | `app/layout.tsx` | Root layout |
| **Chat** | `app/chat/page.tsx` | Main chat UI |
| **Chat Logic** | `hooks/useChatPage.ts` | Chat orchestration |
| **API Client** | `lib/api/chat/chat.api.ts` | Backend calls |

---

## 📞 Support

- **Docs:** `/docs` folder in repo
- **API Docs:** `https://api.nuzantara.com/docs` (Swagger)
- **Monitoring:** Grafana dashboard

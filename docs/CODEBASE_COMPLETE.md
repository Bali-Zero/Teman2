# NUZANTARA - CODEBASE COMPLETA

> **Enterprise-grade Intelligent Business Operating System per Bali Zero**
>
> Documentazione tecnica completa del sistema - Generata per Claude Code Supremo

---

## INDICE

1. [Overview Architetturale](#1-overview-architetturale)
2. [Backend RAG (Python/FastAPI)](#2-backend-rag-pythonfastapi)
3. [Frontend Mouth (Next.js/React)](#3-frontend-mouth-nextjsreact)
4. [Database Layer](#4-database-layer)
5. [Vector Database (Qdrant)](#5-vector-database-qdrant)
6. [Caching & Queue (Redis)](#6-caching--queue-redis)
7. [Infrastructure & Deploy](#7-infrastructure--deploy)
8. [File Essenziali](#8-file-essenziali)
9. [API Reference](#9-api-reference)
10. [Configurazione Ambiente](#10-configurazione-ambiente)

---

## 1. OVERVIEW ARCHITETTURALE

```
                                    NUZANTARA ARCHITECTURE

    +------------------+     +------------------+     +------------------+
    |   FRONTEND       |     |   BACKEND RAG    |     |   DATA LAYER     |
    |   (mouth)        |     |   (FastAPI)      |     |                  |
    +------------------+     +------------------+     +------------------+
    |                  |     |                  |     |                  |
    | Next.js 16       |<--->| 27 Routers       |<--->| PostgreSQL       |
    | React 19         |     | 73+ Services     |     | (Fly.io)         |
    | TypeScript       | SSE | 6 Agents         |     |                  |
    | Tailwind CSS 4   |     | 136 Endpoints    |     | Qdrant Cloud     |
    | shadcn/ui        |     |                  |     | (25k+ docs)      |
    |                  |     | Gemini 2.5       |     |                  |
    +------------------+     +------------------+     | Redis            |
                                     |               | (Cache/Queue)    |
                                     v               +------------------+
                            +------------------+
                            |   EXTERNAL APIs  |
                            +------------------+
                            | Twilio (SMS/WA)  |
                            | SendGrid (Email) |
                            | Slack            |
                            | Google APIs      |
                            +------------------+
```

### Tech Stack Completo

| Layer | Tecnologia | Versione |
|-------|------------|----------|
| Frontend | Next.js | 16.0.8 |
| Frontend | React | 19.2.1 |
| Frontend | TypeScript | 5.x |
| Frontend | Tailwind CSS | 4.x |
| Backend | Python | 3.11+ |
| Backend | FastAPI | 0.115+ |
| Backend | Pydantic | 2.5.0 |
| AI Primary | Google Gemini | 2.5 Flash/Pro |
| Embeddings | OpenAI | text-embedding-3-small |
| Vector DB | Qdrant | Cloud |
| Database | PostgreSQL | 15+ (asyncpg) |
| Cache | Redis | 7.x |
| Deploy | Fly.io | Multi-region |
| Testing & Deployment | Automated Pipeline | - |
| Monitoring | Prometheus + Grafana | - |
| Tracing | Jaeger (OpenTelemetry) | - |

---

## 2. BACKEND RAG (Python/FastAPI)

### 2.1 Struttura Directory

```
apps/backend-rag/
├── backend/
│   ├── app/
│   │   ├── main_cloud.py          # Entry point principale (~1200 righe)
│   │   ├── models.py              # Pydantic models
│   │   ├── routers/               # 27 API routers
│   │   │   ├── agents.py          # Orchestrazione agenti
│   │   │   ├── auth.py            # Autenticazione JWT
│   │   │   ├── conversations.py   # CRUD conversazioni
│   │   │   ├── crm_clients.py     # CRM clienti
│   │   │   ├── crm_practices.py   # Pratiche (KITAS, PMA, Visa)
│   │   │   ├── crm_interactions.py# Log interazioni
│   │   │   ├── health.py          # Health checks
│   │   │   ├── memory_vector.py   # Memoria vettoriale
│   │   │   ├── team_activity.py   # Attività team
│   │   │   ├── websocket.py       # Real-time WS
│   │   │   └── ...
│   │   └── core/
│   │       ├── config.py          # Settings centralizzati (~500 righe)
│   │       ├── embeddings.py      # OpenAI embeddings
│   │       ├── chunking.py        # Document chunking
│   │       └── plugins/           # Plugin system
│   │
│   ├── services/                  # 73+ Business Services
│   │   ├── search_service.py      # Core RAG search (~600 righe)
│   │   ├── query_router.py        # Multi-collection routing (~900 righe)
│   │   ├── collection_manager.py  # Qdrant collections
│   │   ├── reranker_service.py    # Cross-encoder reranking
│   │   ├── semantic_cache.py      # Redis semantic cache
│   │   ├── conversation_service.py# Persistenza conversazioni
│   │   ├── memory_service_postgres.py # Memoria utente
│   │   ├── memory_fact_extractor.py   # Estrazione fatti
│   │   ├── auto_crm_service.py    # AI entity extraction (~700 righe)
│   │   ├── autonomous_scheduler.py # Background scheduler
│   │   ├── tool_executor.py       # Tool execution engine
│   │   ├── openrouter_client.py   # Fallback AI
│   │   ├── deepseek_client.py     # Alternative AI
│   │   ├── gemini_service.py      # Gemini wrapper
│   │   └── ...
│   │
│   ├── llm/                       # LLM Layer
│   │   ├── zantara_ai_client.py   # Primary Gemini client (~800 righe)
│   │   ├── prompt_manager.py      # Template management
│   │   ├── retry_handler.py       # Exponential backoff
│   │   └── token_estimator.py     # Token counting
│   │
│   ├── agents/                    # Agenti Autonomi
│   │   ├── conversation_trainer.py
│   │   ├── client_value_predictor.py
│   │   ├── knowledge_graph_builder.py
│   │   ├── proactive_compliance_monitor.py
│   │   ├── autonomous_research_service.py
│   │   └── cross_oracle_synthesis_service.py
│   │
│   ├── middleware/                # Middleware Stack
│   │   ├── hybrid_auth.py         # JWT + API Key auth
│   │   ├── rate_limiter.py        # Rate limiting
│   │   └── error_monitoring.py    # Error tracking
│   │
│   ├── db/
│   │   └── migrations/            # 22 SQL migrations
│   │
│   └── utils/                     # Helper utilities
│
├── tests/                         # Test Suite
│   ├── unit/
│   ├── integration/
│   ├── api/
│   └── e2e/
│
├── Dockerfile                     # Multi-stage Python image
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project config
└── fly.toml                       # Fly.io deployment
```

### 2.2 Entry Point: main_cloud.py

```python
# Sequenza di inizializzazione
1. Settings validation (config.py)
2. Database connection pool (asyncpg) - 20 base, 30 overflow
3. Redis client initialization
4. Qdrant vector DB connection
5. Core services:
   - ZantaraAIClient (Gemini)
   - SearchService (RAG)
   - ToolExecutor
6. Background tasks:
   - AutonomousScheduler (5 agenti)
   - Redis listener (pub/sub)
7. Health monitoring (ServiceRegistry)
8. Router registration (27 routers)
```

### 2.3 Servizi Principali

#### LLM & AI Services
| Servizio | File | Funzione |
|----------|------|----------|
| ZantaraAIClient | `llm/zantara_ai_client.py` | Gemini 2.5 Flash con retry |
| PromptManager | `llm/prompt_manager.py` | Template management |
| RetryHandler | `llm/retry_handler.py` | Exponential backoff |
| OpenRouterClient | `services/openrouter_client.py` | Fallback AI (free tier) |
| DeepSeekClient | `services/deepseek_client.py` | Alternative AI |

#### RAG & Search Services
| Servizio | Funzione |
|----------|----------|
| SearchService | Document retrieval con tier-based access |
| QueryRouter | 3-layer routing a 15+ collezioni |
| CollectionManager | Qdrant CRUD |
| RerankerService | Cross-encoder (disabilitato default, 5GB) |
| SemanticCache | Redis cache per query |
| AgenticRagOrchestrator | Pipeline completa RAG |

#### Memory & Conversation
| Servizio | Funzione |
|----------|----------|
| ConversationService | Persistenza PostgreSQL |
| MemoryServicePostgres | Facts, summary, counters utente |
| MemoryFactExtractor | Estrazione fatti da conversazioni |
| ContextWindowManager | Ottimizzazione context window |

#### CRM Services
| Servizio | Funzione |
|----------|----------|
| AutoCrmService | AI entity extraction |
| ClientJourneyOrchestrator | Multi-touch engagement |
| TeamAnalyticsService | Metriche team |
| TeamTimeSheetService | Time tracking |

### 2.4 Agenti Autonomi

```python
# AutonomousScheduler gestisce 5 agenti:

AGENTS = {
    "auto_ingestion": {
        "interval": "24h",
        "function": "auto_ingestion_orchestrator.run()",
        "purpose": "Daily regulatory updates"
    },
    "self_healing": {
        "interval": "30s",
        "function": "self_healing_agent.check()",
        "purpose": "Health monitoring"
    },
    "conversation_trainer": {
        "interval": "6h",
        "function": "conversation_trainer.train()",
        "purpose": "Learn from conversations"
    },
    "client_value_predictor": {
        "interval": "12h",
        "function": "client_predictor.predict()",
        "purpose": "Nurture high-value clients"
    },
    "knowledge_graph_builder": {
        "interval": "4h",
        "function": "kg_builder.build()",
        "purpose": "Build knowledge graphs"
    }
}
```

### 2.5 Middleware Stack

```python
# Ordine di esecuzione:
1. CORSMiddleware          # Cross-origin (dev/prod aware)
2. HybridAuthMiddleware    # JWT + API Key validation
3. RateLimitMiddleware     # Request rate limiting
4. ErrorMonitoringMiddleware # Error tracking + Sentry
```

**Authentication Flow:**
```
Request → Authorization: Bearer {JWT}  OR  X-API-Key: {key}
       → HybridAuthMiddleware validates
       → request.state.user_id, request.state.user_role
       → Endpoint handler
```

### 2.6 API Endpoints Principali

```
# Chat (SSE Streaming)
POST /api/chat/stream              # Main streaming chat
GET  /bali-zero/chat-stream        # Jaksel personality
POST /api/chat/completions         # OpenAI-compatible

# Auth
POST /api/auth/login
POST /api/auth/register
POST /api/auth/refresh-token
GET  /api/auth/me

# Conversations
POST /api/conversations/save
GET  /api/conversations/history
GET  /api/conversations/list
GET  /api/conversations/{id}
DELETE /api/conversations/{id}
DELETE /api/conversations/clear

# CRM
GET/POST /api/crm/clients
GET/PUT  /api/crm/clients/{id}
GET/POST /api/crm/practices
GET/POST /api/crm/interactions

# Health
GET /health
GET /ready
```

---

## 3. FRONTEND MOUTH (Next.js/React)

### 3.1 Struttura Directory

```
apps/mouth/
├── src/
│   ├── app/                       # Next.js App Router
│   │   ├── page.tsx               # Home
│   │   ├── layout.tsx             # Root layout
│   │   ├── chat/
│   │   │   └── page.tsx           # Chat interface
│   │   ├── login/
│   │   │   └── page.tsx           # Login page
│   │   ├── admin/
│   │   │   └── page.tsx           # Admin dashboard
│   │   └── globals.css            # Global styles
│   │
│   ├── components/                # React Components
│   │   ├── chat/
│   │   │   ├── MessageBubble.tsx  # Message display (~9.7k righe)
│   │   │   ├── ThinkingIndicator.tsx
│   │   │   └── ChatInput.tsx
│   │   ├── ui/                    # shadcn/ui
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── label.tsx
│   │   │   ├── dialog.tsx
│   │   │   └── ...
│   │   └── layout/
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── MainLayout.tsx
│   │
│   ├── hooks/                     # Custom Hooks
│   │   ├── useChat.ts             # Chat state (~8k righe)
│   │   ├── useWebSocket.ts        # WS connection (~5.5k righe)
│   │   ├── useConversations.ts
│   │   └── useTeamStatus.ts
│   │
│   ├── lib/                       # Utilities
│   │   ├── api.ts                 # Backend client (~20k righe)
│   │   ├── api.sse.ts             # SSE client
│   │   ├── monitoring.ts          # Analytics
│   │   └── utils.ts               # Helpers
│   │
│   └── types/                     # TypeScript
│       └── index.ts
│
├── Dockerfile
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

### 3.2 API Client Layer (lib/api.ts)

```typescript
// Configurazione
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://nuzantara-rag.fly.dev';
const TOKEN_KEY = 'auth_token';

// Auth Functions
login(email: string, password: string): Promise<LoginResponse>
logout(): Promise<void>
refreshToken(): Promise<TokenResponse>
getCurrentUser(): Promise<UserProfile>

// Chat Functions
sendMessage(message: string, conversationId?: string): Promise<Response>  // SSE
getConversationHistory(conversationId: string): Promise<ConversationHistoryResponse>
listConversations(userId: string): Promise<ConversationListResponse>
deleteConversation(conversationId: string): Promise<void>
clearChatHistory(): Promise<void>

// CRM Functions
getClients(): Promise<Client[]>
getClient(id: string): Promise<Client>
createClient(data: ClientCreate): Promise<Client>
updateClient(id: string, data: ClientUpdate): Promise<Client>
getPractices(): Promise<Practice[]>
logInteraction(type: string, clientId: string, content: string): Promise<Interaction>

// Team Functions
getTeamStatus(): Promise<TeamStatus>
getTeamAnalytics(): Promise<TeamAnalytics>
getWorkSessions(): Promise<WorkSession[]>
```

### 3.3 SSE Streaming

```typescript
// api.sse.ts
connectToSSE(conversationId: string): EventSource {
  const url = `${BASE_URL}/api/chat/stream?conversation_id=${conversationId}`;
  const eventSource = new EventSource(url);

  // Event types:
  // - 'message': Chunk di risposta
  // - 'thinking': Stato di elaborazione
  // - 'sources': Fonti citate
  // - 'done': Stream completato
  // - 'error': Errore

  return eventSource;
}
```

### 3.4 State Management

```typescript
// useChat.ts - Hook principale
const useChat = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // SSE stream handling
  // Message batching
  // Auto-save
  // Error recovery

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    loadConversation
  };
};
```

### 3.5 TypeScript Interfaces

```typescript
interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  status?: string;
  language_preference?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Source[];
}

interface ConversationHistoryResponse {
  success: boolean;
  messages: Message[];
  total_messages: number;
}

interface AgentStep {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: any;
}
```

---

## 4. DATABASE LAYER

### 4.1 PostgreSQL (Fly.io)

**Connessione:**
```
Host: nuzantara-postgres.flycast:5432
Database: nuzantara_rag
User: backend_rag_v2
Driver: asyncpg (async)
Pool: 20 base, 30 overflow
Timeout: 30s
```

### 4.2 Schema Principale

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    status VARCHAR(50) DEFAULT 'active',
    language_preference VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    messages JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User Memory (RAG)
CREATE TABLE user_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    facts JSONB DEFAULT '[]',
    summary TEXT,
    message_count INTEGER DEFAULT 0,
    last_interaction TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- CRM Clients
CREATE TABLE crm_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    company VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- CRM Practices
CREATE TABLE crm_practices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES crm_clients(id),
    type VARCHAR(100) NOT NULL,  -- KITAS, PT_PMA, VISA, etc.
    status VARCHAR(50) DEFAULT 'pending',
    documents JSONB DEFAULT '[]',
    timeline JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- CRM Interactions
CREATE TABLE crm_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES crm_clients(id),
    practice_id UUID REFERENCES crm_practices(id),
    type VARCHAR(50) NOT NULL,  -- call, email, meeting
    content TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Golden Answers (Cache high-confidence)
CREATE TABLE golden_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash VARCHAR(64) UNIQUE,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    confidence FLOAT,
    sources JSONB DEFAULT '[]',
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Knowledge Graphs
CREATE TABLE knowledge_graphs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    entities JSONB DEFAULT '[]',
    relationships JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Audit Trail
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Work Sessions
CREATE TABLE work_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_minutes INTEGER,
    activities JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4.3 Relazioni

```
users (1) ──→ (M) conversations
users (1) ──→ (M) user_memory
users (1) ──→ (M) work_sessions
users (1) ──→ (M) crm_interactions
users (1) ──→ (M) knowledge_graphs
users (1) ──→ (M) audit_trail

crm_clients (1) ──→ (M) crm_practices
crm_clients (1) ──→ (M) crm_interactions
crm_practices (1) ──→ (M) crm_interactions
```

---

## 5. VECTOR DATABASE (Qdrant)

### 5.1 Configurazione

```
URL: https://nuzantara-qdrant.fly.dev
API Key: QDD0rKHU2UMHqohUmn4iAI3umrZdQxoVI9sAufKaZyXWjZyeaBzCEpO5GlERjJHo
Embeddings: OpenAI text-embedding-3-small (1536 dimensioni)
Totale documenti: 25,458+
```

### 5.2 Collezioni

| Collezione | Documenti | Descrizione |
|------------|-----------|-------------|
| `kbli_unified` | 8,886 | Codici KBLI business classification |
| `legal_unified` | 5,041 | Framework legali, regolamenti, contratti |
| `visa_oracle` | 1,612 | Tipi visa Indonesia, requisiti |
| `tax_genius` | 895 | Codici fiscali, deduzioni, compliance |
| `bali_zero_team` | 43 | Knowledge team-specific |
| `bali_zero_pricing` | 29 | Pricing servizi |
| `property_unified` | 29 | Real estate data |
| `training_conversations` | - | Conversazioni per training |
| `bali_intel_immigration` | - | Intelligence immigrazione |
| `litigation_oracle` | - | Casi legali |
| `cultural_insights` | - | Contesto culturale Indonesia |
| `zantara_books` | - | Meta-knowledge (filosofia) |
| `kb_indonesian` | - | Knowledge base indonesiano |
| `tax_updates` | - | Aggiornamenti fiscali |
| `legal_updates` | - | Aggiornamenti legali |

### 5.3 Struttura Chunk

```json
{
  "id": "chunk_uuid",
  "vector": [0.123, -0.456, ...],  // 1536 dimensioni
  "payload": {
    "text": "... contenuto chunk (500 char) ...",
    "book_title": "Immigration Law Indonesia 2024",
    "book_author": "Legal Team",
    "tier": "A",                    // S/A/B/C/D
    "min_level": 1,                 // 0-3 access level
    "chunk_index": 42,
    "total_chunks": 150,
    "page_number": 23,
    "language": "en",
    "topics": ["visa", "work permit", "KITAS"],
    "file_path": "/data/books/immigration_2024.pdf",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### 5.4 Query Flow

```python
# 1. Query routing
query = "How to get KITAS?"
collections = QueryRouter.route(query)  # ["visa_oracle", "legal_unified"]

# 2. Embedding
embedding = openai.embed(query)  # 1536-dim vector

# 3. Search con filtri
results = qdrant.search(
    collection_name="visa_oracle",
    query_vector=embedding,
    query_filter={
        "must": [
            {"key": "min_level", "range": {"lte": user.access_level}},
            {"key": "tier", "match": {"any": user.allowed_tiers}}
        ]
    },
    limit=10
)

# 4. Rerank (opzionale)
if ENABLE_RERANKER:
    results = reranker.rerank(query, results)

# 5. Context assembly
context = "\n\n".join([r.payload.text for r in results])
```

### 5.5 Tier System

```
Tier S: Confidential (internal only)
Tier A: Premium (paid users)
Tier B: Standard (registered users)
Tier C: Basic (free users)
Tier D: Public (everyone)

Access Levels:
0: Public
1: Registered
2: Premium
3: Admin
```

---

## 6. CACHING & QUEUE (Redis)

### 6.1 Configurazione

```
URL: redis://localhost:6379 (local)
URL: redis://nuzantara-redis.fly.dev:6379 (prod)
Porta: 6379
```

### 6.2 Utilizzi

```python
# 1. Semantic Cache (RAG)
key: f"semantic_cache:{query_hash}"
value: {
    "answer": "...",
    "sources": [...],
    "confidence": 0.95,
    "created_at": "..."
}
ttl: 3600  # 1 ora

# 2. Rate Limiting
key: f"rate_limit:{user_id}:{endpoint}"
value: request_count
ttl: 60  # 1 minuto

# 3. Session Data
key: f"session:{session_id}"
value: {
    "user_id": "...",
    "role": "...",
    "expires_at": "..."
}
ttl: 86400  # 24 ore

# 4. Background Job Queue
key: "job_queue:default"
type: LIST
operations: LPUSH (enqueue), BRPOP (dequeue)

# 5. Pub/Sub
channel: "notifications"
subscribers: backend workers
```

### 6.3 Pattern Comuni

```python
# Cache-aside pattern
async def get_answer(query: str) -> str:
    cache_key = f"semantic_cache:{hash(query)}"

    # Check cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Compute
    answer = await rag_pipeline.process(query)

    # Store
    await redis.setex(
        cache_key,
        3600,
        json.dumps(answer)
    )

    return answer
```

---

## 7. INFRASTRUCTURE & DEPLOY

### 7.1 Docker Compose (Local)

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: [nuzantara_qdrant_data:/qdrant/storage]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes: [./config/prometheus:/etc/prometheus]

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    depends_on: [prometheus]
```

### 7.2 Fly.io Deployment

```toml
# fly.toml
app = "nuzantara-rag"
primary_region = "sin"  # Singapore

[build]
  dockerfile = "Dockerfile"

[env]
  ENVIRONMENT = "production"
  LOG_LEVEL = "INFO"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[[services]]
  protocol = "tcp"
  internal_port = 8080

  [[services.ports]]
    port = 80
    handlers = ["http"]
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.http_checks]]
    interval = 10000
    grace_period = "10s"
    method = "GET"
    path = "/health"
    protocol = "http"
    timeout = 2000
```

### 7.3 Testing & Deployment Pipeline

```yaml
# Example automated testing and deployment configuration
# Configure in your testing/deployment platform

stages:
  - test
  - deploy

test:
  script:
    - cd apps/backend-rag
    - pip install -r requirements.txt
    - pytest tests/ --cov=backend --cov-report=xml

deploy:
  script:
    - flyctl deploy --remote-only
  environment:
    FLY_API_TOKEN: ${FLY_API_TOKEN}
```

### 7.4 URLs Produzione

| Servizio | URL |
|----------|-----|
| Backend API | https://nuzantara-rag.fly.dev |
| Frontend | https://nuzantara-webapp.fly.dev |
| WebSocket | wss://nuzantara-rag.fly.dev/ws |
| Qdrant | https://nuzantara-qdrant.fly.dev |
| Jaksel Oracle | https://jaksel.balizero.com |
| Zantara | https://zantara.balizero.com |

---

## 8. FILE ESSENZIALI

### 8.1 Backend

| File | Righe | Descrizione |
|------|-------|-------------|
| `app/main_cloud.py` | ~1200 | Entry point FastAPI |
| `app/core/config.py` | ~500 | Settings centralizzati |
| `services/search_service.py` | ~600 | Core RAG search |
| `services/query_router.py` | ~900 | Multi-collection routing |
| `llm/zantara_ai_client.py` | ~800 | Gemini AI client |
| `services/auto_crm_service.py` | ~700 | AI entity extraction |
| `services/memory_service_postgres.py` | ~500 | User memory |
| `services/conversation_service.py` | ~400 | Conversation persistence |
| `services/autonomous_scheduler.py` | ~400 | Background jobs |
| `middleware/hybrid_auth.py` | ~300 | JWT + API Key auth |

### 8.2 Frontend

| File | Righe | Descrizione |
|------|-------|-------------|
| `lib/api.ts` | ~20k | Backend API client |
| `hooks/useChat.ts` | ~8k | Chat state management |
| `hooks/useWebSocket.ts` | ~5.5k | WS connection |
| `components/chat/MessageBubble.tsx` | ~9.7k | Message display |
| `app/chat/page.tsx` | ~500 | Chat page |

### 8.3 Configuration

| File | Descrizione |
|------|-------------|
| `.env.example` | Template variabili ambiente |
| `docker-compose.yml` | Local dev environment |
| `docker-compose.monitoring.yml` | Monitoring stack |
| `fly.toml` | Fly.io deployment |
| `config/prometheus/prometheus.yml` | Prometheus scrape config |
| `config/alertmanager/alertmanager.yml` | Alert routing |

### 8.4 Documentation

| File | Descrizione |
|------|-------------|
| `docs/LIVING_ARCHITECTURE.md` | Auto-generated API docs |
| `docs/AGENT_ARCHITECTURE.md` | Agent system design |
| `docs/AI_MODEL_STRATEGY.md` | AI model selection |
| `AI_ONBOARDING.md` | AI contributor guide |
| `README.md` | Project overview |

---

## 9. API REFERENCE

### 9.1 Authentication

```bash
# Login
POST /api/auth/login
Content-Type: application/json
{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}

# Get Current User
GET /api/auth/me
Authorization: Bearer {token}

Response:
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "User Name",
  "role": "user"
}
```

### 9.2 Chat (SSE Streaming)

```bash
# Send Message (Streaming)
POST /api/chat/stream
Authorization: Bearer {token}
Content-Type: application/json
{
  "message": "How do I get a KITAS?",
  "conversation_id": "uuid" // optional
}

Response (SSE):
event: thinking
data: {"status": "Searching knowledge base..."}

event: message
data: {"chunk": "To obtain a KITAS"}

event: message
data: {"chunk": " (Kartu Izin Tinggal Terbatas)"}

event: sources
data: {"sources": [{"title": "...", "url": "..."}]}

event: done
data: {"conversation_id": "uuid"}
```

### 9.3 Conversations

```bash
# List Conversations
GET /api/conversations/list?user_id={user_id}

# Get History
GET /api/conversations/history?conversation_id={id}

# Delete
DELETE /api/conversations/{id}
```

### 9.4 CRM

```bash
# List Clients
GET /api/crm/clients

# Create Client
POST /api/crm/clients
{
  "name": "Client Name",
  "email": "client@example.com",
  "phone": "+62123456789"
}

# Log Interaction
POST /api/crm/interactions
{
  "client_id": "uuid",
  "type": "call",
  "content": "Discussed KITAS renewal"
}
```

---

## 10. CONFIGURAZIONE AMBIENTE

### 10.1 Variabili Ambiente Complete

```bash
# === PLATFORM ===
ENVIRONMENT=development|production
PROJECT_NAME=nuzantara
API_V1_STR=/api/v1

# === AI/LLM ===
GOOGLE_API_KEY=AIzaSy...              # Required: Gemini
OPENAI_API_KEY=sk-proj-...            # Required: Embeddings
OPENROUTER_API_KEY=sk-or-v1-...       # Optional: Fallback
DEEPSEEK_API_KEY=sk-...               # Optional: Alternative
ZANTARA_AI_MODEL=gpt-4o-mini          # Model name

# === VECTOR DB ===
QDRANT_URL=https://nuzantara-qdrant.fly.dev
QDRANT_API_KEY=QDD0rKHU2U...

# === DATABASE ===
DATABASE_URL=postgresql://user:pass@host:5432/db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_TIMEOUT=30

# === REDIS ===
REDIS_URL=redis://localhost:6379

# === SECURITY ===
JWT_SECRET_KEY=07XoX6Eu24amE...       # Min 32 chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_HOURS=24
API_KEYS=key1,key2,key3

# === FEATURES ===
ENABLE_ANALYTICS=true
ENABLE_COLLECTIVE_MEMORY=true
ENABLE_WEB_SCRAPING=false
ENABLE_RERANKER=false                 # Saves 5GB if disabled

# === OBSERVABILITY ===
LOG_LEVEL=INFO
LOG_FILE=./data/zantara_rag.log
HEALTH_CHECK_INTERVAL=30
JAEGER_ENABLED=false

# === INTEGRATIONS ===
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
SENDGRID_API_KEY=SG...
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# === FLY.IO ===
FLY_API_TOKEN=FlyV1 fm2_lJPE...
```

### 10.2 Quick Start

```bash
# 1. Setup
cd nuzantara
cp .env.example .env
# Edit .env with your keys

# 2. Start services
docker-compose up -d

# 3. Backend
cd apps/backend-rag
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main_cloud:app --reload --port 8080

# 4. Frontend
cd ../mouth
npm install
npm run dev  # http://localhost:3000
```

---

## APPENDICE: COMANDI UTILI

### Backend

```bash
# Run tests
cd apps/backend-rag
pytest tests/ -v --cov=backend

# Format code
black backend/
isort backend/

# Type check
mypy backend/

# Run locally
uvicorn backend.app.main_cloud:app --reload --port 8080
```

### Frontend

```bash
# Development
npm run dev

# Build
npm run build

# Test
npm run test

# Lint
npm run lint
```

### Docker

```bash
# Start all
docker-compose up -d

# Logs
docker-compose logs -f backend

# Restart service
docker-compose restart qdrant

# Clean
docker-compose down -v
```

### Fly.io

```bash
# Deploy
fly deploy

# Logs
fly logs

# SSH
fly ssh console -a nuzantara-rag

# Secrets
fly secrets set KEY=value

# Scale
fly scale count 2
```

### Qdrant

```bash
# Collections info
curl https://nuzantara-qdrant.fly.dev/collections \
  -H "api-key: QDD0rKHU2U..."

# Search
curl https://nuzantara-qdrant.fly.dev/collections/visa_oracle/points/search \
  -H "api-key: QDD0rKHU2U..." \
  -H "Content-Type: application/json" \
  -d '{"vector": [...], "limit": 5}'
```

---

> **Documento generato da Claude Code Supremo**
>
> Ultima modifica: 2024-12-14

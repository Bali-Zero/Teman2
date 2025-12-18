# NUZANTARA - Complete Codebase Overview

> Comprehensive technical documentation for AI assistants (Gemini, Claude, etc.)
> Last updated: 2025-12-14

---

## PROJECT SUMMARY

**NUZANTARA** is a production-grade RAG (Retrieval-Augmented Generation) system with autonomous agents, knowledge graphs, CRM integration, multi-channel communications, and team analytics.

**Tech Stack:**
- **Backend**: Python 3.11+, FastAPI, PostgreSQL, Qdrant (vector DB), Redis
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS
- **AI**: Google Gemini 2.5 Flash/Pro, OpenAI Embeddings
- **Infrastructure**: Fly.io, Docker, Prometheus, Sentry

**Repository Structure:**
```
/nuzantara/
├── apps/
│   ├── backend-rag/     # Main RAG backend (Python/FastAPI)
│   ├── mouth/           # Frontend (Next.js)
│   ├── zantara-media/   # Editorial production system
│   ├── kb/              # Knowledge base tools
│   └── evaluator/       # RAG evaluation harness
├── docs/                # Documentation (142 files)
├── config/              # Infrastructure configs
└── scripts/             # Automation scripts
```

---

# PART 1: BACKEND CODEBASE

## 1.1 Entry Points & Configuration

### Main Application
**File:** `apps/backend-rag/backend/app/main_cloud.py` (~1200 lines)

```python
# Key features:
- FastAPI application with middleware stack
- Service initialization pipeline (SearchService, ZantaraAIClient, ToolExecutor)
- Main streaming endpoints: POST /api/chat/stream, GET /bali-zero/chat-stream
- Background tasks: Auto-CRM, Collective Memory
- Observability: Prometheus, OpenTelemetry/Jaeger
```

### Configuration
**File:** `apps/backend-rag/backend/app/core/config.py` (~500 lines)

```python
# Environment Variables:
ENVIRONMENT                # production/development
OPENAI_API_KEY            # For embeddings
GOOGLE_API_KEY            # Gemini AI
QDRANT_URL, QDRANT_API_KEY
DATABASE_URL              # PostgreSQL
REDIS_URL
JWT_SECRET_KEY
API_KEYS                  # Comma-separated
TWILIO_*, SENDGRID_API_KEY, SLACK_WEBHOOK_URL
```

---

## 1.2 Core Services Architecture

### LLM & AI Services

| Service | File | Purpose |
|---------|------|---------|
| **ZantaraAIClient** | `backend/llm/zantara_ai_client.py` | Primary Gemini AI interface with retry logic |
| PromptManager | `backend/llm/prompt_manager.py` | Prompt template management |
| RetryHandler | `backend/llm/retry_handler.py` | Exponential backoff retry |
| TokenEstimator | `backend/llm/token_estimator.py` | Token counting/cost estimation |
| OpenRouterClient | `backend/services/openrouter_client.py` | Fallback AI provider |
| DeepSeekClient | `backend/services/deepseek_client.py` | Alternative AI provider |

### RAG & Search Services

| Service | File | Purpose |
|---------|------|---------|
| **SearchService** | `backend/services/search_service.py` | Document retrieval from Qdrant |
| **QueryRouter** | `backend/services/query_router.py` | Smart query routing with fallbacks |
| CollectionManager | `backend/services/collection_manager.py` | Qdrant collection operations |
| RerankerService | `backend/services/reranker_service.py` | Search result ranking |
| SemanticCache | `backend/services/semantic_cache.py` | Redis-based semantic caching |

### Conversation & Memory

| Service | File | Purpose |
|---------|------|---------|
| **ConversationService** | `backend/services/conversation_service.py` | Store/retrieve conversation history |
| **MemoryServicePostgres** | `backend/services/memory_service_postgres.py` | Persistent user memory |
| ContextWindowManager | `backend/services/context_window_manager.py` | LLM context window management |
| MemoryFactExtractor | `backend/services/memory_fact_extractor.py` | Extract facts for memory |
| CollectiveMemoryWorkflow | `backend/services/collective_memory_workflow.py` | Multi-user memory synthesis |

### Autonomous Agents

| Agent | File | Purpose |
|-------|------|---------|
| **AutonomousScheduler** | `backend/services/autonomous_scheduler.py` | Coordinate all agents |
| AutonomousResearchService | `backend/services/autonomous_research_service.py` | Research & knowledge synthesis |
| ClientValuePredictor | `backend/agents/agents/client_value_predictor.py` | Predict client LTV |
| ConversationTrainer | `backend/agents/agents/conversation_trainer.py` | Learn from conversations |
| KnowledgeGraphBuilder | `backend/agents/agents/knowledge_graph_builder.py` | Build semantic graphs |

### CRM & Business Logic

| Service | File | Purpose |
|---------|------|---------|
| **AutoCRMService** | `backend/services/auto_crm_service.py` | Automatic CRM data extraction |
| AIExtractor | `backend/services/ai_crm_extractor.py` | AI-powered data extraction |
| ClientScoring | `backend/agents/services/client_scoring.py` | Client engagement scoring |
| ClientSegmentation | `backend/agents/services/client_segmentation.py` | Client segmentation |
| NurturingMessage | `backend/agents/services/nurturing_message.py` | Generate nurturing messages |

### Communication & Notifications

| Service | File | Purpose |
|---------|------|---------|
| **NotificationHub** | `backend/services/notification_hub.py` | Multi-channel notifications |
| WhatsAppNotification | `backend/agents/services/whatsapp_notification.py` | WhatsApp via Twilio |
| AlertService | `backend/services/alert_service.py` | System alerts |

### Monitoring & Health

| Service | File | Purpose |
|---------|------|---------|
| **HealthMonitor** | `backend/services/health_monitor.py` | Self-healing monitoring |
| ProactiveComplianceMonitor | `backend/services/proactive_compliance_monitor.py` | Compliance monitoring |
| CollectionHealthService | `backend/services/collection_health_service.py` | Qdrant health checks |

---

## 1.3 API Routers (29 routers)

### Core Chat Endpoints
```
POST /api/chat/stream          # Main streaming chat (SSE)
GET  /bali-zero/chat-stream    # Legacy streaming endpoint
POST /api/agentic-rag/query    # Agentic RAG queries
```

### Authentication
```
POST /api/auth/login           # Email + PIN login
POST /api/auth/logout          # Logout
GET  /api/auth/profile         # Get user profile
POST /api/auth/refresh         # Refresh token
```

### Conversations
```
GET  /api/conversations                    # List conversations
GET  /api/conversations/{id}               # Get single conversation
POST /api/conversations                    # Save conversation
DELETE /api/conversations/{id}             # Delete conversation
GET  /api/conversations/history/{session}  # Get history by session
```

### CRM
```
GET/POST /api/crm/clients              # Client CRUD
GET/POST /api/crm/interactions         # Interaction tracking
GET/POST /api/crm/practices            # Business practices
GET/POST /api/crm/shared-memory        # Shared memory
```

### Team & Activity
```
POST /api/team/clock-in                # Clock in
POST /api/team/clock-out               # Clock out
GET  /api/team/status                  # Get clock status
GET  /api/team/online-status           # Team online status (admin)
GET  /api/team/daily-hours             # Daily hours (admin)
GET  /api/team/weekly-summary          # Weekly summary (admin)
GET  /api/team/export-csv              # Export timesheet (admin)
```

### Oracle & Ingestion
```
POST /api/oracle/query                 # Universal oracle query
POST /api/ingest/documents             # Document ingestion
POST /api/ingest/legal                 # Legal document processing
```

### Health & Monitoring
```
GET  /health                           # Basic health check
GET  /health/status                    # Detailed status
GET  /health/verbose                   # Verbose health info
GET  /metrics                          # Prometheus metrics
```

---

## 1.4 Database Schema

### PostgreSQL Tables
```sql
-- Core tables
team_members          -- User accounts and profiles
conversations         -- Conversation history
user_memories         -- User-specific facts and preferences

-- CRM tables
clients               -- CRM client records
interactions          -- Client interactions
practices             -- Business practices

-- Knowledge tables
parent_documents      -- Source document metadata
cultural_knowledge    -- Cultural context data
query_clusters        -- Query grouping

-- Knowledge Graph
knowledge_graph_entities       -- KG nodes
knowledge_graph_relationships  -- KG edges

-- System
schema_migrations     -- Migration tracking
```

### Qdrant Collections
```
zantara_knowledge     # Main knowledge base
visa_immigration      # Visa/immigration docs
legal_documents       # Indonesian legal docs
training_conversations # Conversation examples
cultural_insights     # Cultural knowledge
```

---

## 1.5 Core Modules

### Legal Document Processing
**Location:** `backend/core/legal/`
```
chunker.py           # Legal document chunking (Pasal-aware)
cleaner.py           # Text cleaning
structure_parser.py  # Parse BAB/Pasal/Ayat hierarchy
metadata_extractor.py # Extract document metadata
constants.py         # Indonesian legal patterns (PASAL_PATTERN, etc.)
```

### Embeddings & Vector DB
**Location:** `backend/core/`
```
embeddings.py        # OpenAI embeddings generator
qdrant_db.py         # Qdrant vector DB interface
reranker.py          # Cross-encoder reranking
cache.py             # TTL-based caching layer
```

### Prompts
**Location:** `backend/prompts/`
```
zantara_system_prompt.md    # Main system prompt template
zantara_prompt_builder.py   # Dynamic prompt construction
jaksel_persona.py           # Indonesian personality/culture
```

---

## 1.6 Request Flow

```
Client Request
    │
    ▼
FastAPI App (main_cloud.py)
    │
    ▼
HybridAuthMiddleware (JWT/API key)
    │
    ▼
/api/chat/stream endpoint
    │
    ▼
IntelligentRouter
    ├──► SearchService (document retrieval)
    ├──► ZantaraAIClient (Gemini AI)
    ├──► ToolExecutor (tool calling)
    ├──► QueryRouter (smart routing)
    └──► Specialized Services
    │
    ▼
Streaming Response (SSE)
    │
    ▼
Background Tasks:
    ├─ Auto-CRM Processing
    └─ Collective Memory Workflow
```

---

# PART 2: FRONTEND CODEBASE

## 2.1 Application Structure

**Location:** `apps/mouth/`
**Framework:** Next.js 16 + React 19 + TypeScript + Tailwind CSS

```
src/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Landing (auth redirect)
│   ├── login/page.tsx     # Email + PIN login
│   ├── chat/page.tsx      # Main chat interface (~750 lines)
│   └── admin/page.tsx     # Admin dashboard
│
├── components/
│   ├── ui/                # Design system (Button, Input, Label)
│   ├── chat/
│   │   ├── MessageBubble.tsx    # Message display with sources
│   │   └── ThinkingIndicator.tsx
│   ├── layout/
│   │   └── Sidebar.tsx    # Conversation history
│   ├── FeedbackWidget.tsx # User feedback collection
│   └── MonitoringWidget.tsx # Dev monitoring
│
├── hooks/
│   ├── useChat.ts         # Chat state & streaming
│   ├── useConversations.ts # Conversation management
│   ├── useWebSocket.ts    # WebSocket with reconnect
│   └── useTeamStatus.ts   # Clock in/out
│
├── lib/
│   ├── api.ts             # Central API client (~750 lines)
│   ├── monitoring.ts      # Conversation metrics
│   └── utils.ts           # Utilities
│
└── types/
    └── index.ts           # TypeScript interfaces
```

---

## 2.2 Key Hooks

### useChat
```typescript
// State
messages: Message[]
input: string
isLoading: boolean
currentSessionId: string | null

// Methods
handleSend()              // Send message via streaming
handleImageGenerate()     // Generate images
loadConversation(id)      // Load saved conversation
clearMessages()           // Reset conversation
```

### useWebSocket
```typescript
// Features
- Automatic reconnection (5 attempts, 3s intervals)
- Heartbeat/ping support (30s)
- Bearer token authentication via subprotocol

// Returns
{ connect, disconnect, send, isConnected, isConnecting }
```

### useConversations
```typescript
// State
conversations: ConversationListItem[]
currentConversationId: number | null

// Methods
loadConversationList()
deleteConversation(id)
clearHistory()
```

---

## 2.3 API Client

**File:** `src/lib/api.ts`

```typescript
// Authentication
login(email, pin)         // Returns token + profile
logout()
getProfile()

// Chat
sendMessage(message)                    // Non-streaming
sendMessageStreaming(message, sessionId, callbacks)  // SSE streaming

// Conversations
listConversations(limit, offset)
getConversation(id)
saveConversation(messages, sessionId, metadata)
deleteConversation(id)
getConversationHistory(sessionId)

// Team Activity
clockIn()
clockOut()
getClockStatus()

// Admin (requires admin role)
getTeamStatus()
getDailyHours(date?)
getWeeklySummary(weekStart?)
getMonthlySummary(monthStart?)
exportTimesheet(startDate, endDate)

// Image Generation
generateImage(prompt)

// WebSocket
getWebSocketUrl()
getWebSocketSubprotocol()  // Bearer token
```

---

## 2.4 Key Types

```typescript
interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  imageUrl?: string;
  timestamp: Date;
  steps?: AgentStep[];        // Tool execution steps
  currentStatus?: string;     // Current processing status
}

interface Source {
  title?: string;
  content?: string;
}

type AgentStep =
  | { type: 'status'; data: string; timestamp: Date }
  | { type: 'tool_start'; data: { name: string; args: Record<string, unknown> }; timestamp: Date }
  | { type: 'tool_end'; data: { result: string }; timestamp: Date }

interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  language_preference?: string;
}

interface Conversation {
  id: number;
  title: string;
  created_at: string;
  message_count: number;
  preview?: string;
}
```

---

## 2.5 SSE Streaming Format

The backend streams responses via Server-Sent Events:

```
event: data
data: {"type": "status", "content": "Searching knowledge base..."}

event: data
data: {"type": "tool_start", "content": {"name": "search", "args": {...}}}

event: data
data: {"type": "tool_end", "content": {"result": "Found 5 documents"}}

event: data
data: {"type": "chunk", "content": "Here is the answer..."}

event: data
data: {"type": "sources", "content": [{"title": "...", "content": "..."}]}

event: done
data: {"session_id": "abc123"}
```

---

# PART 3: ESSENTIAL DOCUMENTATION

## 3.1 Architecture Decisions

### AI Model Strategy
- **Primary**: Google Gemini 2.5 Flash (unlimited quota, fast, cost-effective)
- **Fallback**: OpenRouter (multiple models), DeepSeek
- **Embeddings**: OpenAI text-embedding-3-small

### RAG Pipeline
1. Query → Semantic Cache check
2. Query Router determines collection(s)
3. SearchService retrieves from Qdrant
4. Reranker scores results (optional)
5. Context assembled with conversation history
6. ZantaraAIClient generates response
7. Background: Auto-CRM extraction, Memory update

### Authentication
- JWT tokens (7-day expiry)
- API key authentication (for services)
- PIN-based login (4-8 digits)
- Role-based access: user, admin, CEO

---

## 3.2 Key Collections (Qdrant)

| Collection | Documents | Purpose |
|------------|-----------|---------|
| zantara_knowledge | 25,000+ | Main knowledge base |
| visa_immigration | 5,000+ | Visa/immigration rules |
| legal_documents | 3,000+ | Indonesian laws (UU, PP, Perpres) |
| training_conversations | 500+ | Example conversations |
| cultural_insights | 200+ | Cultural knowledge |

---

## 3.3 Database Migrations

16 migrations applied:
- 001: cultural_knowledge, query_clusters tables
- 007: CRM schema (clients, interactions, practices)
- 010: team_members schema fixes
- 012: conversation_id in interactions
- 013: Agentic RAG tables
- 014: Knowledge graph tables
- 015-016: Document metadata columns

---

## 3.4 Environment Setup

### Backend Requirements
```bash
# Python 3.11+
cd apps/backend-rag
pip install -r requirements.txt

# Environment variables (.env)
DATABASE_URL=postgresql://...
QDRANT_URL=https://...
GOOGLE_API_KEY=...
OPENAI_API_KEY=...
JWT_SECRET_KEY=...
```

### Frontend Requirements
```bash
# Node.js 20+
cd apps/mouth
npm install

# Environment variables (.env.local)
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
```

### Running Locally
```bash
# Backend
cd apps/backend-rag
uvicorn backend.app.main_cloud:app --reload --port 8000

# Frontend
cd apps/mouth
npm run dev
```

---

## 3.5 Testing

### Backend Tests
```bash
cd apps/backend-rag
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/api/            # API tests
pytest --cov=backend         # With coverage
```

### Frontend Tests
```bash
cd apps/mouth
npm run test                 # Vitest unit tests
npm run test:e2e             # Playwright E2E
npm run test:coverage        # Coverage report
```

---

## 3.6 Deployment

### Fly.io Deployment
```bash
# Backend
fly deploy -a nuzantara-rag

# Frontend
fly deploy -a nuzantara-mouth
```

### Docker
```dockerfile
# Backend Dockerfile exists at apps/backend-rag/Dockerfile
# Frontend uses Next.js standalone output
```

---

## 3.7 Monitoring

### Prometheus Metrics
- Request latency (p50, p95, p99)
- Request count by endpoint
- Error rates
- Service health status

### Health Endpoints
```
GET /health              # Basic health
GET /health/status       # Service status
GET /health/verbose      # Full diagnostic
GET /metrics             # Prometheus format
```

### Sentry
- Error tracking enabled for both frontend and backend
- Source maps uploaded on build

---

# PART 4: QUICK REFERENCE

## 4.1 Common Patterns

### Adding a New Service
```python
# 1. Create service file in backend/services/
class MyService:
    def __init__(self, dependencies):
        self.deps = dependencies

    async def do_something(self) -> Result:
        pass

# 2. Register in main_cloud.py startup
app.state.my_service = MyService(deps)

# 3. Add health check if needed
service_health.register("my_service", lambda: app.state.my_service.health())
```

### Adding a New Router
```python
# 1. Create router in backend/app/routers/
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
async def get_items():
    pass

# 2. Register in main_cloud.py
from backend.app.routers import my_feature
app.include_router(my_feature.router)
```

### Adding a Frontend Page
```typescript
// 1. Create page in src/app/my-page/page.tsx
export default function MyPage() {
  return <div>My Page</div>
}

// 2. Add to navigation if needed (Sidebar.tsx or user menu)
```

---

## 4.2 Important Files Quick Reference

### Backend
```
backend/app/main_cloud.py           # App entry point
backend/app/core/config.py          # Configuration
backend/llm/zantara_ai_client.py    # AI client
backend/services/search_service.py  # RAG search
backend/services/query_router.py    # Query routing
backend/app/routers/               # All API endpoints
```

### Frontend
```
src/app/chat/page.tsx              # Main chat UI
src/hooks/useChat.ts               # Chat logic
src/lib/api.ts                     # API client
src/components/chat/MessageBubble.tsx  # Message display
```

### Documentation
```
docs/ARCHITECTURE.md               # Architecture overview
docs/LIVING_ARCHITECTURE.md        # Auto-generated API docs
docs/QUICK_START_GUIDE.md          # Getting started
docs/ai/AI_HANDOVER_PROTOCOL.md    # AI system prompt
```

---

## 4.3 Code Statistics

| Metric | Value |
|--------|-------|
| Backend Python files | 200+ |
| Backend lines of code | 100K+ |
| Frontend TypeScript files | 50+ |
| Frontend lines of code | 10K+ |
| API routers | 29 |
| Services | 48+ |
| Autonomous agents | 6 |
| Database migrations | 16 |
| Test files | 150+ |
| Documentation files | 142 |

---

*End of NUZANTARA Codebase Overview*

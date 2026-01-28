# 🏗️ NUZANTARA FULL STACK ARCHITECTURE

> Architettura completa Frontend + Backend

---

## 📊 Stack Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INFRASTRUCTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│   │   Vercel    │     │   Fly.io    │     │  Qdrant     │                   │
│   │  (Frontend) │     │  (Backend)  │     │  (Vectors)  │                   │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│          │                   │                   │                          │
│          │              ┌────┴────┐              │                          │
│          │              │PostgreSQL│              │                          │
│          │              │ (Fly.io) │              │                          │
│          │              └─────────┘              │                          │
│          │                   │                   │                          │
│          └───────────────────┴───────────────────┘                          │
│                              │                                              │
│                         ┌────┴────┐                                         │
│                         │  Redis  │                                         │
│                         │ (Cache) │                                         │
│                         └─────────┘                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎨 FRONTEND (mouth)

### Tech Stack
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **UI Components:** shadcn/ui
- **Deployment:** Vercel
- **Domain:** balizero.com

### Structure
```
mouth/src/
├── app/                 # Pages & Routes (Next.js App Router)
│   ├── (blog)/          # Public website
│   ├── (portal)/        # Client portal
│   ├── (workspace)/     # Team workspace
│   └── api/[...path]/   # API proxy to backend
├── components/          # 127 React components
├── hooks/               # 28 custom hooks
├── lib/                 # Utilities & API client
│   └── api/             # Domain API modules (30+ files)
├── providers/           # Context providers
└── types/               # TypeScript definitions
```

### Key Files
| File | Purpose |
|------|---------|
| `app/api/[...path]/route.ts` | Proxy ALL /api/* to backend |
| `lib/api/client.ts` | Base HTTP client |
| `hooks/useChatPage.ts` | Main chat orchestrator |
| `components/chat/MessageBubble.tsx` | Message rendering |

---

## ⚙️ BACKEND (backend-rag)

### Tech Stack
- **Framework:** FastAPI
- **Language:** Python 3.11+
- **Database:** PostgreSQL
- **Vector DB:** Qdrant
- **Cache:** Redis
- **LLM:** Google Gemini
- **Deployment:** Fly.io
- **Domain:** nuzantara-rag.fly.dev

### Structure
```
backend-rag/backend/
├── app/                 # FastAPI application
│   ├── routers/         # 62 endpoint files
│   ├── setup/           # Startup initialization
│   └── middleware/      # Auth, rate limiting
├── services/            # 26 business domains
├── core/                # RAG engine (Qdrant, embeddings)
├── llm/                 # AI providers (Gemini, etc.)
├── db/                  # Database & migrations
├── agents/              # Autonomous AI agents
└── plugins/             # Extensible plugins
```

### Key Files
| File | Purpose |
|------|---------|
| `app/routers/agentic_rag.py` | Main RAG endpoint |
| `services/oracle/oracle_service.py` | RAG orchestrator |
| `llm/zantara_ai_client.py` | LLM client |
| `core/qdrant_db.py` | Vector operations |

---

## 🔄 REQUEST FLOW

### Complete Request Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. USER ACTION                                                              │
│    User types message in chat input                                         │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. REACT COMPONENT                                                          │
│    ChatInputBar.tsx → calls handleSend()                                    │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. CUSTOM HOOK                                                              │
│    useChatPage.ts → manages state, calls chatApi.sendMessageStreaming()     │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. API MODULE                                                               │
│    chat.api.ts → builds request, handles SSE                                │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. API CLIENT                                                               │
│    client.ts → adds auth headers, CSRF token                                │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. API PROXY                                                                │
│    [...path]/route.ts → forwards to backend with cookies                    │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                   HTTPS / SSE
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. BACKEND MIDDLEWARE                                                       │
│    hybrid_auth.py → validates JWT/cookie, rate limiting                     │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. FASTAPI ROUTER                                                           │
│    agentic_rag.py → handles /api/agentic-rag/stream                         │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. SERVICE LAYER                                                            │
│    OracleService → orchestrates RAG pipeline                                │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ 10a. INTENT         │   │ 10b. VECTOR SEARCH  │   │ 10c. MEMORY         │
│ IntentClassifier    │   │ Qdrant → embeddings │   │ MemoryOrchestrator  │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
              │                         │                         │
              └─────────────────────────┼─────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 11. LLM CLIENT                                                              │
│     ZantaraAIClient → calls Gemini with context                             │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                   Google AI API
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 12. STREAMING RESPONSE                                                      │
│     Backend yields SSE events: token, sources, metadata, [DONE]             │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 13. FRONTEND RENDERING                                                      │
│     MessageBubble updates progressively with streaming text                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 AUTHENTICATION

### Auth Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AUTHENTICATION                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  PRIMARY: httpOnly Cookies                                                  │
│  ├── nz_access_token (JWT, httpOnly, secure, sameSite=lax)                  │
│  └── nz_csrf_token (non-httpOnly, for double-submit)                        │
│                                                                             │
│  BACKUP: localStorage (for WebSocket, offline)                              │
│  ├── auth_token (JWT)                                                       │
│  └── user_profile (cached profile)                                          │
│                                                                             │
│  HEADERS:                                                                   │
│  ├── Authorization: Bearer <token> (backup)                                 │
│  └── X-CSRF-Token: <csrf> (for POST/PUT/DELETE)                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Login Flow
```
1. POST /api/auth/login { email, password }
2. Backend validates → returns { token, user, csrf_token }
3. Backend sets httpOnly cookie: nz_access_token
4. Frontend stores token in localStorage (backup)
5. Frontend stores csrf_token in memory
```

### Request Auth Flow
```
1. Request made with credentials: 'include'
2. Browser automatically sends cookies
3. Frontend adds Authorization header (backup)
4. Frontend adds X-CSRF-Token for mutations
5. Backend validates cookie OR header
```

---

## 📡 API ENDPOINTS

### Core Domains

| Domain | Frontend Module | Backend Router | Endpoints |
|--------|-----------------|----------------|-----------|
| **Auth** | `auth/` | `auth.py` | login, logout, profile, check |
| **Chat/RAG** | `chat/` | `agentic_rag.py` | query, stream |
| **Conversations** | `conversations/` | `conversations.py` | list, get, save, delete |
| **CRM Clients** | `crm/` | `crm_clients.py` | CRUD, summary, profile |
| **CRM Practices** | `crm/` | `crm_practices.py` | CRUD, stats, renewals |
| **CRM Interactions** | `crm/` | `crm_interactions.py` | list, create, timeline |
| **Drive** | `drive/` | `google_drive.py` | files, upload, folders |
| **Intel/News** | `intelligence.api.ts` | `intel.py` | articles, publish |
| **Analytics** | `analytics/` | `analytics.py` | overview, rag, crm, team |
| **Admin** | `admin/` | `admin_*.py` | logs, team, system |
| **Portal** | `portal/` | `portal.py` | client portal |
| **Audio** | (inline) | `audio.py` | transcribe, speech |
| **Health** | (inline) | `health.py` | health, detailed |

### Endpoint Count
- **Frontend API Modules:** 30+ files
- **Backend Routers:** 62 files
- **Total Endpoints:** ~400

---

## 💾 DATA STORAGE

### PostgreSQL (Main DB)
```
Tables:
├── users              # System users
├── conversations      # Chat sessions
├── messages           # Chat messages
├── memory_facts       # Extracted facts
├── crm_clients        # CRM clients
├── crm_practices      # Visa/business cases
├── crm_interactions   # Client interactions
├── crm_family_members # Client families
├── crm_documents      # Client documents
├── intel_articles     # News articles
├── portal_users       # Portal access
├── analytics_events   # Telemetry
└── feedback           # User feedback
```

### Qdrant (Vector DB)
```
Collections:
├── visa_knowledge      # Visa/immigration
├── business_knowledge  # Business setup
├── legal_knowledge     # Indonesian laws
├── politics_knowledge  # Political news
├── pricing_knowledge   # Service pricing
├── team_knowledge      # Internal team
└── client_memory       # Per-client memory
```

### Redis (Cache)
```
Keys:
├── session:<id>        # Session data
├── rate_limit:<ip>     # Rate limiting
├── cache:<query_hash>  # Response cache
└── embedding:<text>    # Embedding cache
```

---

## 🤖 AI INTEGRATIONS

### LLM Providers

| Provider | Use Case | Model |
|----------|----------|-------|
| **Google Gemini** | Primary (RAG) | gemini-2.0-flash |
| **Google Vertex** | Enterprise | gemini-pro |
| **DeepSeek** | Cheap/fast | deepseek-chat |
| **Ollama** | Local dev | qwen2.5 |
| **OpenRouter** | Fallback | various |

### External APIs

| Service | Purpose |
|---------|---------|
| **Google Drive** | Document storage |
| **Google Search** | Grounding |
| **ElevenLabs** | Text-to-speech |
| **Whisper** | Speech-to-text |
| **Pollinations** | Image generation |

---

## 📊 MONITORING

### Frontend
- Sentry (errors)
- Web Vitals (performance)
- Custom logger

### Backend
- Prometheus metrics
- Structured logging
- Health endpoints

### Observability
```
Frontend → Sentry
Backend → Prometheus → Grafana
Logs → Structured JSON → Log aggregator
```

---

## 🚀 DEPLOYMENT

### Frontend (Vercel)
```bash
# Auto-deploy on push to main
git push origin main
# Vercel builds and deploys automatically
```

### Backend (Fly.io)
```bash
# Deploy
fly deploy

# Scale
fly scale count 2

# Logs
fly logs
```

### URLs
```
Production:
- Frontend: https://balizero.com
- Backend: https://nuzantara-rag.fly.dev

Development:
- Frontend: http://localhost:3000
- Backend: http://localhost:8080
```

---

## 📁 Key Files Reference

### Frontend
```
mouth/
├── src/app/api/[...path]/route.ts    # API proxy
├── src/lib/api/client.ts             # HTTP client
├── src/lib/api/chat/chat.api.ts      # Chat API
├── src/hooks/useChatPage.ts          # Chat hook
├── src/components/chat/              # Chat UI
└── .env.local                        # Environment
```

### Backend
```
backend-rag/
├── backend/app/main_cloud.py         # App entry
├── backend/app/routers/agentic_rag.py  # RAG endpoint
├── backend/services/oracle/          # RAG service
├── backend/llm/zantara_ai_client.py  # LLM client
├── backend/core/qdrant_db.py         # Vector DB
└── .env                              # Environment
```

---

## 🧪 TESTING

### Frontend
```bash
npm run test      # Vitest unit tests
npm run e2e       # Playwright E2E
```

### Backend
```bash
pytest            # All tests
./sentinel        # Quality checks (ruff + pytest)
```

---

*"Full stack, full power" 🏗️*

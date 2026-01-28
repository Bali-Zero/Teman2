# 🔗 COLLEGAMENTI FRONTEND ↔ BACKEND

> Mapping completo di come il frontend comunica con il backend

---

## 📊 Overview Architettura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (mouth)                               │
│                          Next.js 14+ / Vercel                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Components │ →  │   Hooks     │ →  │  API Modules│                  │
│  │  (127 TSX)  │    │ (28 hooks)  │    │  (30+ files)│                  │
│  └─────────────┘    └─────────────┘    └──────┬──────┘                  │
│                                                │                         │
│                                        ┌───────▼───────┐                 │
│                                        │  API Client   │                 │
│                                        │  (client.ts)  │                 │
│                                        └───────┬───────┘                 │
│                                                │                         │
│                                        ┌───────▼───────┐                 │
│                                        │  API Proxy    │                 │
│                                        │[...path]/route│                 │
│                                        └───────┬───────┘                 │
│                                                │                         │
└────────────────────────────────────────────────┼─────────────────────────┘
                                                 │
                                    HTTPS / SSE Streaming
                                                 │
┌────────────────────────────────────────────────▼─────────────────────────┐
│                           BACKEND (backend-rag)                          │
│                          FastAPI / Fly.io                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │   Routers   │ →  │  Services   │ →  │    Core     │                  │
│  │ (62 files)  │    │(26 domains) │    │  (RAG/LLM)  │                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────┐                │
│  │                     Database                         │                │
│  │            PostgreSQL + Qdrant + Redis              │                │
│  └─────────────────────────────────────────────────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Proxy Layer

### Come Funziona

Il frontend usa un **catch-all API route** che fa da proxy:

**File:** `src/app/api/[...path]/route.ts`

```typescript
// Tutte le chiamate /api/* vengono proxiate al backend
// Frontend: /api/crm/clients
// Backend:  https://nuzantara-rag.fly.dev/api/crm/clients

async function proxy(req: NextRequest): Promise<Response> {
  const backendBase = process.env.NUZANTARA_API_URL || 'https://nuzantara-rag.fly.dev';
  const targetUrl = `${backendBase}${url.pathname}${url.search}`;
  
  // Forward request con cookies e headers
  const response = await fetch(targetUrl, {
    method: req.method,
    headers: forwardedHeaders,
    body: req.body,
    credentials: 'include',
  });
  
  return new Response(response.body, {...});
}
```

### URL Configuration

```bash
# Frontend .env.local
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
NUZANTARA_API_URL=https://nuzantara-rag.fly.dev

# Development
NEXT_PUBLIC_API_URL=http://localhost:8080
```

---

## 🔐 Authentication Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                       LOGIN FLOW                                      │
└──────────────────────────────────────────────────────────────────────┘

1. User submits credentials
   Frontend: POST /api/auth/login
   ↓
2. Backend validates, returns JWT + sets httpOnly cookie
   Backend: POST /api/auth/login → { token, user, csrf_token }
   ↓
3. Frontend stores token in localStorage (backup) + cookie (primary)
   api.setToken(response.token)
   ↓
4. Subsequent requests include:
   - Cookie: nz_access_token (httpOnly, automatic)
   - Header: Authorization: Bearer <token> (backup)
   - Header: X-CSRF-Token: <csrf> (for POST/PUT/DELETE)
```

### Auth Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `POST /api/auth/login` | `auth.py: /login` | Login |
| `POST /api/auth/logout` | `auth.py: /logout` | Logout |
| `GET /api/auth/profile` | `auth.py: /profile` | Get user |
| `GET /api/auth/check` | `auth.py: /check` | Verify token |
| `POST /api/auth/refresh` | `auth.py: /refresh` | Refresh token |
| `GET /api/auth/csrf-token` | `auth.py: /csrf-token` | Get CSRF |

---

## 💬 Chat/RAG Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                       CHAT STREAMING FLOW                             │
└──────────────────────────────────────────────────────────────────────┘

1. User sends message
   useChatPage.handleSend("What is KITAS?")
   ↓
2. Hook calls API module
   chatApi.sendMessageStreaming(message, sessionId, callbacks)
   ↓
3. API module sends POST with SSE
   POST /api/agentic-rag/stream
   Body: { query, user_id, session_id, conversation_history }
   ↓
4. Backend processes:
   a. Intent classification
   b. Route selection (visa/business/legal)
   c. Vector search (Qdrant)
   d. LLM generation (Gemini)
   e. Stream response
   ↓
5. SSE Events flow back:
   data: {"type": "phase", "data": {"name": "searching"}}
   data: {"type": "token", "content": "KITAS"}
   data: {"type": "token", "content": " is"}
   data: {"type": "sources", "data": [...]}
   data: {"type": "metadata", "data": {...}}
   data: [DONE]
   ↓
6. Frontend updates UI progressively
   onChunk(accumulatedText)
   onStep(phase/status updates)
   onDone(fullResponse, sources, metadata)
```

### Chat Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `POST /api/agentic-rag/query` | `agentic_rag.py: /query` | Single response |
| `POST /api/agentic-rag/stream` | `agentic_rag.py: /stream` | SSE streaming |
| `GET /api/conversations/list` | `conversations.py: /list` | List convos |
| `GET /api/conversations/{id}` | `conversations.py: /{id}` | Get convo |
| `DELETE /api/conversations/{id}` | `conversations.py: /{id}` | Delete convo |
| `POST /api/conversations/save` | `conversations.py: /save` | Save message |

### SSE Event Types

| Event Type | Purpose | Example |
|------------|---------|---------|
| `token` | Text chunk | `{"type":"token","content":"Hello"}` |
| `sources` | RAG citations | `{"type":"sources","data":[...]}` |
| `metadata` | Response metadata | `{"type":"metadata","data":{...}}` |
| `phase` | Processing phase | `{"type":"phase","data":{"name":"searching"}}` |
| `status` | Status update | `{"type":"status","data":"Processing..."}` |
| `thinking` | AI thinking | `{"type":"thinking","data":"Analyzing..."}` |
| `tool_call` | Tool execution | `{"type":"tool_call","data":{"tool":"search"}}` |
| `tool_start` | Tool started | `{"type":"tool_start","data":{...}}` |
| `tool_end` | Tool completed | `{"type":"tool_end","data":{"result":"..."}}` |
| `image` | Generated image | `{"type":"image","data":{"url":"..."}}` |
| `error` | Error | `{"type":"error","data":{"message":"..."}}` |
| `keepalive` | Connection alive | `{"type":"keepalive"}` |

---

## 👥 CRM Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                       CRM DATA FLOW                                   │
└──────────────────────────────────────────────────────────────────────┘

Frontend Page                  API Module                  Backend
─────────────                  ──────────                  ───────
/clients/page.tsx
     │
     ├─► useEffect()
     │        │
     │        ▼
     │   crmApi.getClients()
     │        │
     │        ▼
     │   GET /api/crm/clients ──────────────────► crm_clients.py
     │        │                                         │
     │        │                                         ▼
     │        │                                   PostgreSQL
     │        │                                         │
     │        ◄─────────────── [Client[]] ◄────────────┘
     │
     ├─► onClick(client)
     │        │
     │        ▼
     │   crmApi.getClientSummary(id)
     │        │
     │        ▼
     │   GET /api/crm/clients/{id}/summary ────► crm_clients.py
     │                                                  │
     ◄──────────────── {summary} ◄─────────────────────┘
```

### CRM Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `GET /api/crm/clients` | `crm_clients.py` | List clients |
| `POST /api/crm/clients` | `crm_clients.py` | Create client |
| `GET /api/crm/clients/{id}` | `crm_clients.py` | Get client |
| `PATCH /api/crm/clients/{id}` | `crm_clients.py` | Update client |
| `DELETE /api/crm/clients/{id}` | `crm_clients.py` | Delete client |
| `GET /api/crm/clients/{id}/summary` | `crm_clients.py` | Full summary |
| `GET /api/crm/clients/{id}/profile` | `crm_clients.py` | Profile |
| `GET /api/crm/practices` | `crm_practices.py` | List practices |
| `POST /api/crm/practices` | `crm_practices.py` | Create practice |
| `GET /api/crm/practices/{id}` | `crm_practices.py` | Get practice |
| `PATCH /api/crm/practices/{id}` | `crm_practices.py` | Update practice |
| `GET /api/crm/interactions` | `crm_interactions.py` | List interactions |
| `POST /api/crm/interactions` | `crm_interactions.py` | Create interaction |

---

## 📁 Google Drive Integration

```
Frontend                       Backend                      Google Drive
────────                       ───────                      ────────────
useDrive()
    │
    ├─► listFiles(folderId)
    │        │
    │        ▼
    │   GET /api/drive/files ─────► google_drive.py ─────► Drive API
    │                                     │
    │   ◄─────────── [files] ◄───────────┘
    │
    ├─► uploadFile(file)
    │        │
    │        ▼
    │   POST /api/drive/upload ───► google_drive.py ─────► Drive API
    │   (multipart/form-data)             │
    │                                     │
    │   ◄─────────── {fileId} ◄──────────┘
```

### Drive Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `GET /api/drive/files` | `google_drive.py` | List files |
| `GET /api/drive/files/{id}` | `google_drive.py` | Get file |
| `POST /api/drive/upload` | `google_drive.py` | Upload file |
| `POST /api/drive/folders` | `google_drive.py` | Create folder |
| `DELETE /api/drive/files/{id}` | `google_drive.py` | Delete file |
| `GET /api/clients/{id}/drive-folder` | `crm_drive_folders.py` | Client folder |

---

## 📰 Intelligence/News Flow

### Article Composer (Streaming)

```
Frontend                       Backend
────────                       ───────
ArticleComposer
    │
    ├─► generateArticle(topic)
    │        │
    │        ▼
    │   POST /api/article-composer/compose ───► article_composer.py
    │   (streaming)                                    │
    │                                                  ▼
    │                                            Gemini LLM
    │                                                  │
    │   ◄─── SSE: {"type":"token"} ◄──────────────────┘
    │   ◄─── SSE: {"type":"token"}
    │   ◄─── SSE: [DONE]
```

### Intel Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `GET /api/intel/articles` | `intel.py` | List articles |
| `POST /api/intel/articles` | `intel.py` | Create article |
| `GET /api/intel/articles/{id}` | `intel.py` | Get article |
| `POST /api/intel/articles/{id}/publish` | `intel.py` | Publish |
| `POST /api/article-composer/compose` | `article_composer.py` | Generate AI |
| `GET /api/intel/analytics` | `intel.py` | Analytics |

---

## 📊 Analytics & Dashboard

### Dashboard Data Flow

```
Frontend                       Backend
────────                       ───────
useDashboardData()
    │
    ├─► loadStats()
    │        │
    │        ├─► GET /api/analytics/overview ─► analytics.py
    │        ├─► GET /api/analytics/crm ──────► analytics.py
    │        ├─► GET /api/analytics/team ─────► analytics.py
    │        └─► GET /api/analytics/system ───► analytics.py
    │
    │   ◄─── Promise.all([stats...])
```

### Analytics Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `GET /api/analytics/overview` | `analytics.py` | Overview stats |
| `GET /api/analytics/rag` | `analytics.py` | RAG metrics |
| `GET /api/analytics/crm` | `analytics.py` | CRM stats |
| `GET /api/analytics/team` | `analytics.py` | Team metrics |
| `GET /api/analytics/system` | `analytics.py` | System health |
| `GET /api/analytics/all` | `analytics.py` | All combined |
| `GET /api/health` | `health.py` | Health check |
| `GET /api/health/detailed` | `health.py` | Detailed health |

---

## 🔊 Audio/TTS Flow

```
Frontend                       Backend
────────                       ───────
useChatTTS()
    │
    ├─► playTTS(text)
    │        │
    │        ▼
    │   POST /api/audio/speech ────► audio.py
    │   Body: { text }                   │
    │                                    ▼
    │                              ElevenLabs API
    │                                    │
    │   ◄─── { audio_url } ◄────────────┘
    │
    │   new Audio(url).play()


useAudioRecorder()
    │
    ├─► transcribe(audioBlob)
    │        │
    │        ▼
    │   POST /api/audio/transcribe ───► audio.py
    │   (multipart/form-data)               │
    │                                       ▼
    │                                 Whisper API
    │                                       │
    │   ◄─── { text } ◄────────────────────┘
```

### Audio Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `POST /api/audio/transcribe` | `audio.py` | Speech-to-text |
| `POST /api/audio/speech` | `audio.py` | Text-to-speech |

---

## 🚀 Admin Flow

### Admin Endpoints

| Frontend | Backend | Purpose |
|----------|---------|---------|
| `GET /api/admin/logs/activity` | `admin_logs.py` | Activity logs |
| `GET /api/admin/team/overview` | `admin_team_activity.py` | Team overview |
| `GET /api/admin/team/timesheet` | `admin_team_activity.py` | Timesheet |
| `GET /api/admin/system/health` | `health.py` | System health |
| `GET /api/autonomous-agents/status` | `autonomous_agents.py` | Agents status |

---

## 🧩 Type Sharing

### TypeScript Types (Frontend)

```typescript
// lib/api/crm/crm.types.ts
interface Client {
  id: number;
  full_name: string;
  email: string;
  phone?: string;
  // ...
}

interface Practice {
  id: number;
  client_id: number;
  practice_type: string;
  status: string;
  // ...
}
```

### Pydantic Models (Backend)

```python
# app/routers/crm_clients.py
class ClientResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str]
    # ...

class PracticeResponse(BaseModel):
    id: int
    client_id: int
    practice_type: str
    status: str
    # ...
```

### Type Alignment

| Frontend Type | Backend Model | Notes |
|---------------|---------------|-------|
| `Client` | `ClientResponse` | 1:1 mapping |
| `Practice` | `PracticeResponse` | 1:1 mapping |
| `Message` | `MessageModel` | Slight differences |
| `Conversation` | `ConversationResponse` | 1:1 mapping |
| `AgentStep` | SSE event types | Event-based |

---

## 📍 Endpoint Mapping Table

### Complete Mapping

| Domain | Frontend API Module | Backend Router | Base Path |
|--------|--------------------|--------------------|-----------|
| **Auth** | `lib/api/auth/` | `auth.py` | `/api/auth` |
| **Chat** | `lib/api/chat/` | `agentic_rag.py` | `/api/agentic-rag` |
| **Conversations** | `lib/api/conversations/` | `conversations.py` | `/api/conversations` |
| **CRM Clients** | `lib/api/crm/` | `crm_clients.py` | `/api/crm/clients` |
| **CRM Practices** | `lib/api/crm/` | `crm_practices.py` | `/api/crm/practices` |
| **CRM Interactions** | `lib/api/crm/` | `crm_interactions.py` | `/api/crm/interactions` |
| **Drive** | `lib/api/drive/` | `google_drive.py` | `/api/drive` |
| **Intelligence** | `lib/api/intelligence.api.ts` | `intel.py` | `/api/intel` |
| **Articles** | `lib/api/articles.api.ts` | `article_composer.py` | `/api/article-composer` |
| **Analytics** | `lib/api/analytics/` | `analytics.py` | `/api/analytics` |
| **Admin** | `lib/api/admin/` | `admin_*.py` | `/api/admin` |
| **Team** | `lib/api/team/` | `admin_team_activity.py` | `/api/team` |
| **Portal** | `lib/api/portal/` | `portal.py` | `/api/portal` |
| **Knowledge** | `lib/api/knowledge/` | `knowledge_visa.py` | `/api/knowledge` |
| **Media** | `lib/api/media/` | `media.py` | `/api/media` |
| **Audio** | (inline) | `audio.py` | `/api/audio` |
| **Health** | (inline) | `health.py` | `/api/health` |
| **Feedback** | (inline) | `feedback.py` | `/api/feedback` |

---

## ⚠️ Critical Points

### 1. Proxy Configuration
```
SEMPRE usare /api/* prefix nel frontend
Il proxy catch-all redirige TUTTO al backend
```

### 2. Authentication
```
- Cookie-based auth (httpOnly) = PRIMARY
- Bearer token = BACKUP for WebSocket
- CSRF token = Required for POST/PUT/DELETE
```

### 3. Streaming
```
- SSE per chat streaming
- Content-Type: text/event-stream
- Keep connection alive con keepalive events
```

### 4. Error Handling
```typescript
// Frontend cattura errori HTTP
if (response.status === 401) {
  // Redirect to login
  window.location.replace('/login');
}

if (response.status === 422) {
  // FastAPI validation error
  throw new Error(`Validation: ${error.detail}`);
}
```

### 5. FormData Upload
```typescript
// NON settare Content-Type per FormData
// Il browser lo setta automaticamente con boundary
const formData = new FormData();
formData.append('file', file);
// Content-Type header viene RIMOSSO dal client
```

---

*"Frontend and Backend, united as one" 🔗*

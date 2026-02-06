# OpenAPI Documentation - Bali Zero API

Documentazione completa delle API di Bali Zero con specifica OpenAPI 3.0.

## 📋 Files Creati

- **`src/lib/api/openapi.yaml`** - Specifica OpenAPI 3.0 completa (30KB, 1186 righe)
- **`src/app/api/docs/openapi.yaml/route.ts`** - Endpoint per servire la spec
- **`scripts/validate-openapi.cjs`** - Script di validazione

## 🎯 API Documentate

### Tags (5 categorie)

- **Auth** - Autenticazione e gestione profilo
- **Portal** - Client portal operations
- **Chat** - AI conversational interface (SSE streaming)
- **CRM** - Customer relationship management
- **Drive** - Google Drive integration

### Endpoints (16 principali)

#### Auth

- `POST /api/auth/login` - Login con email/PIN
- `POST /api/auth/logout` - Logout
- `GET /api/auth/profile` - Get user profile

#### Portal (Client-facing)

- `GET /api/portal/dashboard` - Dashboard overview
- `GET /api/portal/timeline` - Activity timeline
- `GET /api/portal/visa` - Visa status
- `GET /api/portal/messages` - Messages list
- `POST /api/portal/messages` - Send message

#### Chat (AI)

- `POST /api/agentic-rag/stream` - **SSE streaming** (ReAct reasoning, tool calls, vision)
- `POST /api/agentic-rag/query` - Non-streaming version

#### CRM (Team-facing)

- `GET /api/crm/clients` - List clients
- `POST /api/crm/clients` - Create client
- `GET /api/crm/clients/{id}` - Get client details
- `GET /api/crm/practices` - List practices (with RBAC)
- `PATCH /api/crm/practices/{id}` - Update practice
- `GET /api/crm/interactions` - List interactions

#### Drive

- `POST /api/clients/{id}/create-drive-folder` - Create folder structure
- `POST /api/clients/{id}/drive-folder/{folderName}/upload` - Upload file

## 🔐 Autenticazione

Tre metodi supportati:

1. **httpOnly Cookie** (principale)
   - Cookie: `nz_access_token`
   - Secure, HttpOnly, SameSite=Lax

2. **Bearer Token** (fallback)

   ```
   Authorization: Bearer <JWT_TOKEN>
   ```

3. **API Key** (integrazioni)
   ```
   X-API-Key: <API_KEY>
   ```

## 🚀 Usage

### 1. Validare la Spec

```bash
# Validate OpenAPI spec
node scripts/validate-openapi.cjs
```

Output:

```
✅ OpenAPI spec is valid!
📊 Size: 30.74 KB
📏 Lines: 1186
📋 Endpoints: 16
🏷️  Tags: 5 (Auth, Portal, Chat, CRM, Drive)
```

### 2. Servire la Spec

La spec è automaticamente servita da Next.js:

```bash
# Start dev server
cd apps/mouth
npm run dev

# Access spec
curl http://localhost:3000/api/docs/openapi.yaml
```

### 3. Integrare Swagger UI (Opzionale)

#### Step 1: Installare dipendenze

```bash
cd apps/mouth
pnpm add swagger-ui-react
pnpm add -D @types/swagger-ui-react
```

#### Step 2: Creare pagina Swagger

Creare `src/app/api/docs/page.tsx`:

```typescript
'use client';

import dynamic from 'next/dynamic';
import 'swagger-ui-react/swagger-ui.css';

const SwaggerUI = dynamic(() => import('swagger-ui-react'), { ssr: false });

export default function ApiDocsPage() {
  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto py-8">
        <h1 className="text-3xl font-bold mb-4">Bali Zero API Documentation</h1>
        <SwaggerUI url="/api/docs/openapi.yaml" />
      </div>
    </div>
  );
}
```

#### Step 3: Accedere alla UI

```
http://localhost:3000/api/docs
```

## 📚 Schema Highlights

### LoginResponse

```yaml
LoginResponse:
  type: object
  properties:
    success: boolean
    data:
      properties:
        token: string (JWT)
        user: UserProfile
        csrfToken: string
```

### Chat Streaming (SSE)

```yaml
POST /api/agentic-rag/stream
Content-Type: application/json

{
  "query": "Come funziona il KITAS investor?",
  "user_id": "client@example.com",
  "session_id": "uuid",
  "enable_vision": false
}

Response: text/event-stream
data: {"type":"thinking","data":"Analyzing..."}
data: {"type":"token","content":"Il KITAS"}
data: {"type":"sources","data":[...]}
data: [DONE]
```

### Event Types (13)

- `token` - Response token
- `thinking` - AI reasoning
- `tool_call` - Tool invocation
- `observation` - Tool result
- `sources` - Citations
- `metadata` - Execution stats
- `image` - Generated image
- `error` - Error message
- `reasoning_step` - ReAct step
- `phase` - Processing phase
- `keepalive` - Connection keepalive
- `tool_start` - Tool execution start
- `tool_end` - Tool execution end

## 🎨 Tools per Testing

### Swagger Editor Online

```
https://editor.swagger.io/
```

Incolla il contenuto di `openapi.yaml` per testing interattivo.

### Postman

1. Import → Link → `http://localhost:3000/api/docs/openapi.yaml`
2. Auto-genera collection con tutti gli endpoints

### curl Examples

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"client@example.com","pin":"123456"}'

# Get Dashboard (with cookie)
curl http://localhost:8000/api/portal/dashboard \
  -H "Cookie: nz_access_token=<JWT>"

# Chat Streaming
curl -X POST http://localhost:8000/api/agentic-rag/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{"query":"Come funziona il KITAS?","user_id":"test@example.com"}' \
  --no-buffer
```

## 📊 Statistiche

- **Spec Size**: 30.74 KB
- **Total Lines**: 1,186
- **Endpoints**: 16 principali + 20+ varianti
- **Schemas**: 15+ componenti riutilizzabili
- **Tags**: 5 categorie
- **Authentication**: 3 metodi
- **Response Types**: JSON, SSE (text/event-stream)

## 🔄 Maintenance

### Aggiungere Nuovo Endpoint

1. Aggiungi il path in `openapi.yaml`:

   ```yaml
   /api/new-endpoint:
     get:
       tags: [YourTag]
       summary: Description
       operationId: uniqueId
       responses:
         '200':
           description: Success
   ```

2. Valida la spec:

   ```bash
   node scripts/validate-openapi.cjs
   ```

3. Testa l'endpoint nella UI Swagger

### Aggiornare Schema

1. Modifica `components/schemas` in `openapi.yaml`
2. Riutilizza con `$ref: '#/components/schemas/SchemaName'`
3. Valida e testa

## 🎯 Next Steps

1. ✅ OpenAPI spec creata e validata
2. ✅ Endpoint per servire la spec
3. ✅ Script di validazione
4. ⏳ (Opzionale) Installare Swagger UI
5. ⏳ (Opzionale) Creare pagina `/api/docs`
6. ⏳ (Opzionale) Configurare Postman collection

## 📖 Resources

- [OpenAPI 3.0 Spec](https://swagger.io/specification/)
- [Swagger UI](https://swagger.io/tools/swagger-ui/)
- [Swagger Editor](https://editor.swagger.io/)
- [Postman](https://www.postman.com/)

---

**Last Updated**: 2026-02-04
**Version**: 1.0.0
**Status**: ✅ Production Ready

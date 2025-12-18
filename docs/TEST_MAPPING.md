# Test Mapping - Nuzantara Codebase

Mappatura completa di tutti i test di funzionamento del sistema.

## 📋 Indice

1. [Test Backend](#test-backend)
2. [Test Frontend](#test-frontend)
3. [Test Database](#test-database)
4. [Test Integrazione](#test-integrazione)
5. [Test Funzionalità Specifiche](#test-funzionalità-specifiche)

---

## 🔧 Test Backend

### 1. Health & Infrastructure

#### Health Check
- **Endpoint**: `GET /health`
- **Test**: Verifica stato generale del sistema
- **Expected**: `200 OK`, `{"status": "healthy", ...}`
- **Comando**: `curl https://nuzantara-rag.fly.dev/health`

#### Database Connection
- **Endpoint**: `GET /health`
- **Test**: Verifica connessione database (da response)
- **Expected**: `"database": {"status": "connected"}`
- **Comando**: `curl https://nuzantara-rag.fly.dev/health | jq .database`

---

### 2. Authentication & Identity

#### Login
- **Endpoint**: `POST /api/auth/team/login`
- **Body**: `{"email": "zero@balizero.com", "pin": "010719"}`
- **Test**: Autenticazione utente
- **Expected**: `200 OK`, `{"token": "...", "user": {...}}`
- **Comando**:
```bash
curl -X POST https://nuzantara-rag.fly.dev/api/auth/team/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","pin":"010719"}'
```

#### Get User Profile (se disponibile)
- **Endpoint**: `GET /api/auth/profile`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Recupero profilo utente autenticato
- **Expected**: `200 OK`, `{"user": {...}}`

#### Team Stats (se disponibile)
- **Endpoint**: `GET /api/auth/team/stats`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Statistiche team
- **Expected**: `200 OK`

#### List Team Members (se disponibile)
- **Endpoint**: `GET /api/auth/team/members`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Lista membri team
- **Expected**: `200 OK`

---

### 3. Knowledge & RAG

#### List Collections
- **Endpoint**: `GET /api/knowledge/collections`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Lista collezioni knowledge base
- **Expected**: `200 OK`, `{"collections": [...]}`

#### Knowledge Stats
- **Endpoint**: `GET /api/knowledge/stats`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Statistiche knowledge base
- **Expected**: `200 OK`

---

### 4. Chat & Streaming

#### Chat Stream
- **Endpoint**: `GET /bali-zero/chat-stream?query=test`
- **Headers**: `Authorization: Bearer <token>`, `Accept: text/event-stream`
- **Test**: Stream chat SSE
- **Expected**: `200 OK`, `Content-Type: text/event-stream`
- **Comando**:
```bash
curl -N -H "Authorization: Bearer <token>" \
  "https://nuzantara-rag.fly.dev/bali-zero/chat-stream?query=test"
```

---

### 5. Dashboard & Stats

#### Dashboard Stats
- **Endpoint**: `GET /api/dashboard/stats`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Statistiche dashboard
- **Expected**: `200 OK`, `{"uptime_status": "...", "system_health": "...", ...}`
- **Comando**:
```bash
curl -H "Authorization: Bearer <token>" \
  https://nuzantara-rag.fly.dev/api/dashboard/stats
```

---

### 6. CRM Endpoints

#### List Clients
- **Endpoint**: `GET /api/crm/clients`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Lista clienti CRM
- **Expected**: `200 OK` o `404 Not Found`

#### List Practices
- **Endpoint**: `GET /api/crm/practices`
- **Headers**: `Authorization: Bearer <token>`
- **Test**: Lista pratiche CRM
- **Expected**: `200 OK` o `404 Not Found`

---

## 🌐 Test Frontend

### 1. Login Page

#### Visual Rendering
- **URL**: `https://zantara.balizero.com/` o `http://localhost:3000/`
- **Test**: Pagina login renderizza correttamente
- **Expected**: Form email + PIN visibile

#### Login Flow
- **Test**: Submit form con credenziali valide
- **Expected**: Redirect a `/chat` o `/dashboard`
- **Token salvato**: `localStorage.getItem('zantara_token')`

#### Error Handling
- **Test**: Submit con credenziali invalide
- **Expected**: Messaggio errore visualizzato

---

### 2. Chat Page

#### Page Load
- **URL**: `/chat`
- **Test**: Pagina chat carica correttamente
- **Expected**: Interfaccia chat visibile

#### Send Message
- **Test**: Invio messaggio
- **Expected**: Messaggio appare nella chat, risposta streamata

---

### 3. Dashboard Page

#### Page Load
- **URL**: `/dashboard`
- **Test**: Dashboard carica statistiche
- **Expected**: Statistiche visualizzate

---

## 🗄️ Test Database

### 1. Schema Verification

#### Team Members Table
- **Test**: Verifica colonne `team_members`
- **Colonne richieste**: `id`, `full_name`, `email`, `pin_hash`, `role`, `department`, `language`, `personalized_response`, `notes`, `last_login`, `failed_attempts`, `locked_until`, `active`, `created_at`, `updated_at`
- **Comando SQL**:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'team_members'
ORDER BY column_name;
```

#### User Sessions Table
- **Test**: Verifica colonne `user_sessions`
- **Colonne richieste**: `id`, `user_id`, `email`, `created_at`, `last_accessed`, `expires_at`, `ip_address`, `user_agent`, `is_active`

---

### 2. Data Integrity

#### User Data
- **Test**: Verifica presenza utente `zero@balizero.com`
- **Comando SQL**:
```sql
SELECT id, full_name, email, role, active
FROM team_members
WHERE email = 'zero@balizero.com';
```

#### PIN Hash Format
- **Test**: Verifica formato hash PIN (bcrypt)
- **Expected**: Hash inizia con `$2b$` o `$2a$`

---

## 🔗 Test Integrazione

### 1. Frontend → Backend

#### Login Flow
1. Frontend chiama `/api/auth/login` (Next.js route)
2. Route handler fa proxy a `https://nuzantara-rag.fly.dev/api/auth/team/login`
3. Backend autentica e ritorna token
4. Frontend salva token in `localStorage`
5. Frontend redirect a `/chat` o `/dashboard`

#### Chat Flow
1. Frontend chiama `/api/chat` o `/api/chat/stream`
2. Route handler fa proxy a backend SSE endpoint
3. Backend streama risposta
4. Frontend visualizza messaggi

---

### 2. Backend → Database

#### Query Execution
- **Test**: Verifica che tutte le query SQL funzionino
- **Query critiche**:
  - `SELECT ... FROM team_members WHERE email = ...`
  - `UPDATE team_members SET ...`
  - `INSERT INTO team_members ...`

---

## 🎯 Test Funzionalità Specifiche

### 1. Authentication

#### PIN Validation
- **Test**: PIN 4-8 cifre
- **Valid**: `010719`, `1234`, `12345678`
- **Invalid**: `123`, `123456789`, `abc123`

#### Token Generation
- **Test**: Token JWT valido dopo login
- **Expected**: Token decodificabile, contiene `userId`, `email`, `role`

#### Session Management
- **Test**: Sessione creata dopo login
- **Expected**: Record in `user_sessions` table

---

### 2. Security

#### CORS
- **Test**: Richieste da frontend accettate
- **Expected**: Headers CORS corretti

#### Token Validation
- **Test**: Endpoint protetti richiedono token valido
- **Expected**: `401 Unauthorized` senza token

---

## 📊 Esecuzione Test

### Script Automatico

```bash
# Esegui tutti i test
cd apps/backend-rag
python scripts/test_functionality.py
```

### Test Manuali

Vedi comandi curl sopra per ogni endpoint.

---

## ✅ Checklist Test Completi

- [ ] Health check OK
- [ ] Database connesso
- [ ] Login funziona
- [ ] Token generato correttamente
- [ ] Endpoint protetti richiedono autenticazione
- [ ] Chat stream funziona
- [ ] Dashboard stats disponibili
- [ ] Frontend login funziona
- [ ] Frontend chat funziona
- [ ] Database schema allineato
- [ ] Query SQL coerenti
- [ ] CORS configurato correttamente

---

## 📝 Note

- Tutti i test richiedono backend online (`https://nuzantara-rag.fly.dev`)
- Per test locali, usa `http://localhost:8000`
- Token valido necessario per endpoint protetti
- Alcuni endpoint potrebbero non esistere (404 OK per test)

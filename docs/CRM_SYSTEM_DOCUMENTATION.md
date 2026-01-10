# CRM System - Complete Documentation

**Last Updated**: 2026-01-05
**Version**: 2.0
**Maintainer**: Zero (zero@balizero.com)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Access Control & Security](#access-control--security)
4. [Core Features](#core-features)
5. [API Reference](#api-reference)
6. [Common Issues & Solutions](#common-issues--solutions)
7. [Troubleshooting](#troubleshooting)
8. [Database Schema](#database-schema)

---

## Overview

Il sistema CRM di Nuzantara gestisce clienti, famiglie, documenti, pratiche e interazioni per il team Bali Zero. È progettato per:

- **Multi-tenancy**: Ogni team member vede solo i propri clienti (tranne Zero)
- **Security-first**: Autenticazione obbligatoria, filtri server-side
- **Data integrity**: Sanitizzazione automatica date, validazione campi
- **Real-time updates**: Sentiment analysis, timeline interazioni

---

## Architecture

### Frontend (Next.js 13+)

```
apps/mouth/src/
├── app/(workspace)/clients/
│   ├── page.tsx           # Lista clienti (kanban + table view)
│   ├── [id]/page.tsx      # Dettaglio cliente
│   └── new/page.tsx       # Creazione cliente
├── components/crm/
│   └── ClientCard.tsx     # Card cliente nel kanban
└── lib/api/crm/
    ├── crm.api.ts         # API client
    └── crm.types.ts       # TypeScript types
```

### Backend (FastAPI)

```
apps/backend-rag/backend/app/routers/
├── crm_clients.py         # Gestione clienti (CRUD)
├── crm_enhanced.py        # Family members, Documents, Alerts
├── crm_interactions.py    # Timeline, Note, Comunicazioni
└── crm_practices.py       # Pratiche legali (KITAS, PT PMA, etc)
```

### Database (PostgreSQL)

```sql
-- Core tables
clients                    # Anagrafica clienti
client_family_members      # Familiari e dipendenti
documents                  # Documenti (passaporti, visti, etc)
interactions               # Timeline comunicazioni
practices                  # Pratiche legali in corso
```

---

## Access Control & Security

### Roles

| Role | Email Pattern | Permissions |
|------|--------------|-------------|
| **Super Admin** | `zero@balizero.com` | Full access - vede TUTTI i clienti |
| **Regular Member** | `*@balizero.com` | Vede solo clienti `assigned_to` loro |

### Authentication Flow

```typescript
// Frontend - Auth check
const user = await api.getProfile();  // JWT from cookies
const clients = await api.crm.getClients();  // Auto-filtered by backend

// Backend - Request validation
current_user = request.state.user  # Set by hybrid_auth middleware
if not current_user_email:
    raise HTTPException(401, "Authentication required")
```

### Access Control Logic

```python
# backend/app/routers/crm_clients.py:326-393

# 1. Authentication gate
if not current_user_email:
    raise HTTPException(401, "Authentication required")

# 2. Super admin bypass
SUPER_ADMINS = ["zero"]
is_super_admin = current_user_name in SUPER_ADMINS

# 3. Query filtering
if is_super_admin:
    # Zero sees ALL clients (no WHERE filter)
    query = "SELECT * FROM clients"
else:
    # Regular members: WHERE assigned_to = current_user_email
    query = "SELECT * FROM clients WHERE assigned_to = $1"
    params = [current_user_email]
```

### Security Features

✅ **Server-side filtering** - Impossibile bypassare da frontend
✅ **JWT validation** - Ogni richiesta verificata
✅ **SQL injection protection** - Parametrized queries
✅ **CORS whitelist** - Solo domini autorizzati
✅ **Rate limiting** - 100 req/min per IP

---

## Core Features

### 1. Client Management

#### Create Client

**Endpoint**: `POST /api/crm/clients`

**Required Fields**:
- `full_name` (string, min 2 chars)

**Optional Fields**:
- `email`, `phone`, `whatsapp`
- `nationality`, `passport_number`, `passport_expiry`, `date_of_birth`
- `company_name`, `address`, `notes`
- `status`: `lead | active | completed | lost | inactive`
- `client_type`: `individual | company`
- `assigned_to` (team member email)
- `tags` (array of strings)

**Date Sanitization**:
```python
# CRITICAL: Empty strings must be converted to None for PostgreSQL DATE columns
passport_expiry = client.passport_expiry if client.passport_expiry else None
date_of_birth = client.date_of_birth if client.date_of_birth else None
```

**Example Request**:
```typescript
const client = await api.crm.createClient({
  full_name: "Marco Rossi",
  email: "marco@example.com",
  phone: "+393331234567",
  nationality: "Italian",
  passport_expiry: "2028-12-31",  // or "" (converted to NULL)
  status: "lead",
  assigned_to: "adit@balizero.com"
}, "zero@balizero.com");  // created_by
```

#### Update Client

**Endpoint**: `PATCH /api/crm/clients/{client_id}`

**Field Mapping** (whitelist):
```python
ALLOWED_FIELDS = [
    "full_name", "email", "phone", "whatsapp", "company_name",
    "nationality", "passport_number", "passport_expiry", "date_of_birth",
    "status", "client_type", "assigned_to", "avatar_url",
    "address", "notes", "tags", "custom_fields"
]
```

**Date Sanitization** (UPDATE):
```python
date_fields = {"passport_expiry", "date_of_birth"}

for field, value in updates.dict(exclude_unset=True).items():
    if field not in field_mapping:
        raise HTTPException(400, f"Invalid field name: {field}")

    # Convert empty strings to None for date fields
    if field in date_fields and value == "":
        value = None
```

#### Delete Client

**Endpoint**: `DELETE /api/crm/clients/{client_id}`

**Behavior**: Soft delete (sets `status = inactive`)

**Frontend Refresh**:
```typescript
await api.crm.deleteClient(client.id, user.email);
router.push('/clients');
router.refresh();  // CRITICAL: Force data refetch
```

---

### 2. Family Members

Gestione familiari e dipendenti collegati al cliente (per pratiche family visa, dependent KITAS, etc).

#### Create Family Member

**Endpoint**: `POST /api/crm/clients/{client_id}/family`

**Required Fields**:
- `full_name` (string)
- `relationship`: `spouse | child | parent | dependent`

**Optional Fields**:
- `date_of_birth`, `nationality`, `passport_number`, `passport_expiry`
- `current_visa_type`, `visa_expiry`
- `email`, `phone`, `notes`

**Date Sanitization**:
```python
# backend/app/routers/crm_enhanced.py:338-366

# Sanitize date fields - convert empty strings to None
date_of_birth = data.date_of_birth if data.date_of_birth else None
passport_expiry = data.passport_expiry if data.passport_expiry else None
visa_expiry = data.visa_expiry if data.visa_expiry else None

INSERT INTO client_family_members (
    client_id, full_name, relationship,
    date_of_birth, passport_expiry, visa_expiry, ...
) VALUES (
    $1, $2, $3, $4, $5, $6, ...
)
```

**Example Request**:
```typescript
await api.crm.createFamilyMember(clientId, {
  full_name: "Anna Rossi",
  relationship: "spouse",
  nationality: "Italian",
  passport_number: "AB1234567",
  passport_expiry: "2027-06-15",  // or "" (auto NULL)
  visa_expiry: ""  // Empty → NULL in DB
});
```

#### Update Family Member

**Endpoint**: `PATCH /api/crm/clients/{client_id}/family/{member_id}`

**Date Sanitization** (UPDATE):
```python
# backend/app/routers/crm_enhanced.py:374-409

date_fields = {"date_of_birth", "passport_expiry", "visa_expiry"}

for field, value in data.model_dump(exclude_unset=True).items():
    # Convert empty strings to None for date fields
    if field in date_fields and value == "":
        value = None

    if value is not None:
        update_fields.append(f"{field} = ${param_num}")
        values.append(value)
        param_num += 1
```

---

### 3. Documents

Gestione documenti (passaporti, visti, contratti, certificates).

#### Create Document

**Endpoint**: `POST /api/crm/clients/{client_id}/documents`

**Required Fields**:
- `document_type` (string, e.g., "Passport", "KITAS", "PT PMA Deed")

**Optional Fields**:
- `document_category`: `immigration | pma | tax | personal | other`
- `file_name`, `file_id`, `file_url`, `google_drive_file_url`
- `expiry_date` (DATE)
- `family_member_id` (int) - Se documento di un familiare
- `practice_id` (int) - Se documento collegato a pratica
- `notes`

**Date Sanitization**:
```python
# backend/app/routers/crm_enhanced.py:482-508

# Sanitize date field - convert empty string to None
expiry_date = data.expiry_date if data.expiry_date else None

INSERT INTO documents (
    client_id, document_type, document_category,
    file_name, expiry_date, family_member_id, ...
) VALUES (
    $1, $2, $3, $4, $5, $6, ...
)
```

**Example Request**:
```typescript
await api.crm.createDocument(clientId, {
  document_type: "Passport",
  document_category: "immigration",
  file_name: "passport_marco_rossi.pdf",
  google_drive_file_url: "https://drive.google.com/file/d/...",
  expiry_date: "2028-12-31",  // or "" (auto NULL)
  family_member_id: 123  // Optional
});
```

---

### 4. Quick Notes

Aggiungi note veloci alla timeline del cliente.

**Endpoint**: `POST /api/crm/interactions/`

**Frontend Implementation**:
```typescript
// apps/mouth/src/app/(workspace)/clients/[id]/page.tsx:384-395

const onAddNote = async (note: string) => {
  const user = await api.getProfile();
  await api.crm.createInteraction({
    client_id: clientId,
    interaction_type: 'note',
    summary: note,
    team_member: user.email,
  });
  const interactionsData = await api.crm.getClientTimeline(clientId, 20);
  setInteractions(interactionsData);
  toast.success('Note Added');
};
```

**Backend**:
```python
# backend/app/routers/crm_interactions.py:128-209

INSERT INTO interactions (
    client_id, interaction_type, summary,
    team_member, direction, interaction_date
) VALUES (
    $1, 'note', $2, $3, 'outbound', NOW()
)

# Auto-update client's last_interaction_date
UPDATE clients SET last_interaction_date = NOW()
WHERE id = $1
```

**No Date Issues**: Usa `NOW()` server-side, no user input.

---

### 5. Avatar Fallback System

Fallback a 3 livelli per avatar cliente:

```typescript
// apps/mouth/src/components/crm/ClientCard.tsx:86-115

const countryFlag = getCountryFlag(client.nationality);

// Tier 1: Uploaded photo
{client.avatar_url ? (
  <img src={client.avatar_url} alt={client.full_name} />

// Tier 2: Country flag emoji
) : countryFlag ? (
  <div className="...text-2xl">{countryFlag}</div>

// Tier 3: White/gray circle
) : (
  <div className="...bg-white dark:bg-gray-300" />
)}
```

**Flag Mapping** (30+ countries):
```typescript
const NATIONALITY_FLAGS: Record<string, string> = {
  'Italian': '🇮🇹', 'Italy': '🇮🇹',
  'Russian': '🇷🇺', 'Russia': '🇷🇺',
  'Ukrainian': '🇺🇦', 'Ukraine': '🇺🇦',
  'American': '🇺🇸', 'USA': '🇺🇸',
  // ... 26 more countries
};
```

**Applied to**:
- `ClientCard.tsx` (kanban view)
- `clients/[id]/page.tsx` (detail page header)

---

## API Reference

### Clients Endpoints

| Method | Endpoint | Description | Auth | Filter |
|--------|----------|-------------|------|--------|
| GET | `/api/crm/clients` | List clients | Required | by assigned_to |
| POST | `/api/crm/clients` | Create client | Required | - |
| GET | `/api/crm/clients/{id}` | Get client detail | Required | - |
| PATCH | `/api/crm/clients/{id}` | Update client | Required | - |
| DELETE | `/api/crm/clients/{id}` | Soft delete client | Required | - |

### Family Members Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/crm/clients/{id}/family` | List family members |
| POST | `/api/crm/clients/{id}/family` | Add family member |
| PATCH | `/api/crm/clients/{id}/family/{member_id}` | Update member |
| DELETE | `/api/crm/clients/{id}/family/{member_id}` | Delete member |

### Documents Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/crm/clients/{id}/documents` | List documents |
| POST | `/api/crm/clients/{id}/documents` | Add document |
| PATCH | `/api/crm/clients/{id}/documents/{doc_id}` | Update document |
| DELETE | `/api/crm/clients/{id}/documents/{doc_id}` | Archive document |

### Interactions Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/crm/clients/{id}/timeline` | Get interaction timeline |
| POST | `/api/crm/interactions/` | Create interaction (note, call, etc) |

---

## Common Issues & Solutions

### Issue 1: "Failed to update - Database service temporarily unavailable"

**Symptom**: Modal shows error when creating/updating family member or document.

**Root Cause**: Empty string `''` sent to PostgreSQL DATE column.

```
asyncpg.exceptions.DataError:
invalid input for query argument $8: ''
('str' object has no attribute 'toordinal')
```

**Solution**: Date sanitization (IMPLEMENTED 2026-01-05)

```python
# BEFORE (❌ Causes error)
passport_expiry = data.passport_expiry  # Could be ''

# AFTER (✅ Fixed)
passport_expiry = data.passport_expiry if data.passport_expiry else None
```

**Applied to**:
- `crm_clients.py` - client creation/update
- `crm_enhanced.py` - family member creation/update
- `crm_enhanced.py` - document creation/update

---

### Issue 2: "All clients visible to all members"

**Symptom**: Team members see clients assigned to others.

**Root Cause**: Missing authentication check → filter bypass.

```python
# BEFORE (❌ Security hole)
current_user_email = current_user.get("email", "") if current_user else ""
# If email is empty → no filter applied → shows ALL clients
```

**Solution**: Authentication gate (IMPLEMENTED 2026-01-05)

```python
# AFTER (✅ Secure)
if not current_user_email:
    raise HTTPException(401, "Authentication required")

# Then apply filter
if not is_super_admin:
    query_parts.append("AND c.assigned_to = $1")
    params.append(current_user_email)
```

---

### Issue 3: "Delete client doesn't refresh page"

**Symptom**: Client deleted but still visible in list.

**Root Cause**: Next.js router cache not invalidated.

**Solution**: Add `router.refresh()` after navigation

```typescript
// BEFORE (❌ Stale data)
await api.crm.deleteClient(client.id, user.email);
router.push('/clients');

// AFTER (✅ Fresh data)
await api.crm.deleteClient(client.id, user.email);
router.push('/clients');
router.refresh();  // Force refetch
```

---

### Issue 4: "Invalid field name: company_name"

**Symptom**: Edit client modal fails when updating company_name.

**Root Cause**: Field missing from backend whitelist.

**Solution**: Add to field_mapping (FIXED 2026-01-05)

```python
# backend/app/routers/crm_clients.py:505-523

field_mapping = {
    "full_name": "full_name",
    "email": "email",
    "company_name": "company_name",  # ADDED
    "passport_expiry": "passport_expiry",  # ADDED
    "date_of_birth": "date_of_birth",  # ADDED
    # ... rest
}
```

---

## Troubleshooting

### Debug Mode

**Frontend**: Check browser console for API errors

```typescript
// apps/mouth/src/lib/api/crm/crm.api.ts
console.error('Failed to create client:', error);
```

**Backend**: Check logs for SQL errors

```bash
# Production logs
fly logs -a nuzantara-rag | grep -i "error\|exception"

# Local logs
tail -f backend/logs/app.log
```

### Common Error Patterns

#### 1. DataError: invalid input for query argument

```
asyncpg.exceptions.DataError: invalid input for query argument $8: ''
```

**Cause**: Empty string to DATE column
**Fix**: Add date sanitization (see Issue 1)

#### 2. HTTPException 401: Authentication required

```
{"detail": "Authentication required to view clients"}
```

**Cause**: Missing JWT or expired session
**Fix**: Re-login on frontend

#### 3. HTTPException 400: Invalid field name

```
{"detail": "Invalid field name: some_field"}
```

**Cause**: Field not in whitelist
**Fix**: Add to `field_mapping` in `crm_clients.py`

---

## Database Schema

### clients

```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    whatsapp VARCHAR(50),
    company_name VARCHAR(255),
    nationality VARCHAR(100),
    passport_number VARCHAR(50),
    passport_expiry DATE,              -- NULL allowed
    date_of_birth DATE,                -- NULL allowed
    status VARCHAR(50) DEFAULT 'lead', -- lead, active, completed, lost, inactive
    client_type VARCHAR(50) DEFAULT 'individual',  -- individual, company
    assigned_to VARCHAR(255),          -- team member email
    avatar_url TEXT,
    address TEXT,
    notes TEXT,
    tags TEXT[],                       -- Array of tags
    custom_fields JSONB,
    lead_source VARCHAR(50),
    service_interest TEXT[],
    first_contact_date TIMESTAMP DEFAULT NOW(),
    last_interaction_date TIMESTAMP,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_clients_assigned_to ON clients(assigned_to);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_email ON clients(email);
```

### client_family_members

```sql
CREATE TABLE client_family_members (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    relationship VARCHAR(50),          -- spouse, child, parent, dependent
    date_of_birth DATE,                -- NULL allowed
    nationality VARCHAR(100),
    passport_number VARCHAR(50),
    passport_expiry DATE,              -- NULL allowed
    current_visa_type VARCHAR(100),
    visa_expiry DATE,                  -- NULL allowed
    email VARCHAR(255),
    phone VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### documents

```sql
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    family_member_id INTEGER REFERENCES client_family_members(id),
    practice_id INTEGER REFERENCES practices(id),
    document_type VARCHAR(255) NOT NULL,
    document_category VARCHAR(50),     -- immigration, pma, tax, personal, other
    file_name VARCHAR(500),
    file_id VARCHAR(255),              -- Google Drive file ID
    file_url TEXT,
    google_drive_file_url TEXT,
    expiry_date DATE,                  -- NULL allowed
    notes TEXT,
    status VARCHAR(50) DEFAULT 'active',
    storage_type VARCHAR(50) DEFAULT 'google_drive',
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Best Practices

### 1. Date Field Handling

**❌ NEVER**:
```typescript
// Don't send empty strings for dates
const data = {
  passport_expiry: "",  // ❌ Will crash
  date_of_birth: ""     // ❌ Will crash
};
```

**✅ ALWAYS**:
```typescript
// Send undefined or valid date string
const data = {
  passport_expiry: formData.passport_expiry || undefined,  // ✅ OK
  date_of_birth: "1990-01-15"  // ✅ OK
};
```

**Backend will sanitize**:
```python
# Automatic conversion to None/NULL
passport_expiry = data.passport_expiry if data.passport_expiry else None
```

### 2. Access Control

**❌ NEVER**:
```typescript
// Don't implement filtering on frontend
const myClients = allClients.filter(c => c.assigned_to === user.email);
```

**✅ ALWAYS**:
```typescript
// Let backend filter (secure)
const clients = await api.crm.getClients();  // Auto-filtered by assigned_to
```

### 3. Refresh After Mutations

**❌ NEVER**:
```typescript
await api.crm.deleteClient(id);
router.push('/clients');  // ❌ Stale cache
```

**✅ ALWAYS**:
```typescript
await api.crm.deleteClient(id);
router.push('/clients');
router.refresh();  // ✅ Fresh data
```

---

## Changelog

### v2.0 (2026-01-05)

**Security Fixes**:
- ✅ Added authentication requirement for client list
- ✅ Enforced strict `assigned_to` filtering
- ✅ Removed Ruslana special-case logic

**Data Integrity Fixes**:
- ✅ Date sanitization in family member create/update
- ✅ Date sanitization in document create/update
- ✅ Date sanitization in client create/update

**UX Improvements**:
- ✅ Avatar fallback system (flag emoji → white circle)
- ✅ Delete client auto-refresh
- ✅ Team members dropdown updated (15 members)

**Bug Fixes**:
- ✅ Fixed "Invalid field name: company_name"
- ✅ Fixed "Database service temporarily unavailable"
- ✅ Fixed stale data after delete

---

## Support

**Maintainer**: Zero (zero@balizero.com)
**Deployment**: https://nuzantara-rag.fly.dev
**Frontend**: https://nuzantara-mouth.vercel.app (deployed on Vercel)
**Logs**: `fly logs -a nuzantara-rag`

**Emergency Rollback**:
```bash
# List releases
fly releases -a nuzantara-rag

# Rollback to previous
fly deploy -a nuzantara-rag --image registry.fly.io/nuzantara-rag:deployment-{VERSION}
```

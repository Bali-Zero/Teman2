# CRM System - Complete Documentation

**Last Updated**: 2026-02-07  
**Version**: 3.0 (Consolidated)  
**Maintainer**: Zero (zero@balizero.com)  
**Status**: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Access Control & Security](#access-control--security)
5. [Core Features](#core-features)
6. [API Reference](#api-reference)
7. [Database Schema](#database-schema)
8. [Common Issues & Solutions](#common-issues--solutions)
9. [Troubleshooting](#troubleshooting)
10. [Changelog](#changelog)

---

## Overview

The Nuzantara CRM system manages client relationships, practices (services), interactions, and documents for Bali Zero's immigration and business consulting services.

### Key Capabilities

- **Client Management**: Profiles, documents, family members
- **Practice Tracking**: KITAS, PT PMA, visas, renewals
- **Interactions**: Calls, emails, meetings, notes
- **Document Management**: Passports, visas, contracts with expiry alerts
- **Access Control**: Role-based visibility (Admin/Team)
- **Real-time Updates**: Sentiment analysis, timeline

---

## Quick Start

### Create a New Client

```typescript
const client = await api.crm.createClient(
  {
    full_name: "Marco Rossi",
    email: "marco@example.com",
    phone: "+393331234567",
    nationality: "Italian",
    passport_expiry: "2028-12-31",
    status: "lead",
    assigned_to: "adit@balizero.com",
  },
  "zero@balizero.com",
); // created_by
```

### List Clients (Auto-filtered)

```typescript
// Automatically filtered by assigned_to for team members
// Zero sees ALL clients
const clients = await api.crm.getClients();
```

### Add Family Member

```typescript
await api.crm.createFamilyMember(clientId, {
  full_name: "Anna Rossi",
  relationship: "spouse",
  nationality: "Italian",
  passport_expiry: "2027-06-15",
});
```

### Add Quick Note

```typescript
await api.crm.createInteraction({
  client_id: clientId,
  interaction_type: "note",
  summary: "Client called about visa renewal",
  team_member: user.email,
});
```

---

## Architecture

### Frontend (Next.js)

```
apps/mouth/src/
├── app/(workspace)/clients/
│   ├── page.tsx              # Lista clienti (kanban + table)
│   ├── [id]/page.tsx         # Client 360° profile page
│   └── new/page.tsx          # Creazione cliente
├── components/crm/
│   └── ClientCard.tsx        # Card cliente kanban
└── lib/api/crm/
    ├── crm.api.ts            # API client
    └── crm.types.ts          # TypeScript types
```

### Backend (FastAPI)

```
apps/backend-rag/backend/app/routers/
├── crm_clients.py            # Gestione clienti (CRUD)
├── crm_enhanced.py           # Family members, Documents
├── crm_interactions.py       # Timeline, Note
├── crm_practices.py          # Pratiche legali (RBAC)
└── crm_drive_folders.py      # Google Drive integration
```

### Database (PostgreSQL)

| Table                   | Purpose                        |
| ----------------------- | ------------------------------ |
| `clients`               | Anagrafica clienti             |
| `client_family_members` | Familiari e dipendenti         |
| `documents`             | Documenti (passaporti, visti)  |
| `interactions`          | Timeline comunicazioni         |
| `practices`             | Pratiche legali in corso       |
| `practice_documents`    | Documenti collegati a pratiche |

---

## Access Control & Security

### Roles

| Role            | Email Pattern                             | Permissions                                   |
| --------------- | ----------------------------------------- | --------------------------------------------- |
| **Super Admin** | `zero@balizero.com`, `admin@balizero.com` | Full access - ALL clients                     |
| **Team Member** | `*@balizero.com`                          | Only clients with `assigned_to` = their email |

### Authentication Flow

```typescript
// Frontend - Auth check
const user = await api.getProfile();
const clients = await api.crm.getClients(); // Auto-filtered

// Backend - Request validation
current_user = request.state.user
if not current_user_email:
    raise HTTPException(401, "Authentication required")
```

### Security Features

✅ Server-side filtering (cannot bypass from frontend)  
✅ JWT validation on every request  
✅ SQL injection protection (parametrized queries)  
✅ CORS whitelist  
✅ Rate limiting (100 req/min per IP)

---

## Core Features

### 1. Client Profile (360° View)

**Route**: `/clients/[id]`

**Tabs**:

1. **Overview** - 3 cards (Passport, Visa, Process)
2. **Documents** - Document list with previews
3. **Family** - Family members & dependents
4. **Timeline** - Activity history

**Overview Cards**:

| Card         | Info Displayed                                          |
| ------------ | ------------------------------------------------------- |
| **Passport** | Photo, number, expiry, OCR extraction button            |
| **Visa**     | Current type, expiry, alert color (red/yellow/green)    |
| **Process**  | Active practice, status, progress, estimated completion |

### 2. Client Management

#### Create Client

**Endpoint**: `POST /api/crm/clients`

**Required**: `full_name` (min 2 chars)

**Optional**:

- Contact: `email`, `phone`, `whatsapp`
- Identity: `nationality`, `passport_number`, `passport_expiry`, `date_of_birth`
- Business: `company_name`, `address`, `notes`
- Status: `status` (lead/active/completed/lost/inactive), `client_type` (individual/company)
- Assignment: `assigned_to` (team member email), `tags`

**Date Sanitization** (CRITICAL):

```python
# Empty strings → NULL for PostgreSQL DATE columns
passport_expiry = data.passport_expiry if data.passport_expiry else None
```

#### Update Client

**Endpoint**: `PATCH /api/crm/clients/{id}`

**Allowed Fields** (whitelist):

```python
ALLOWED_FIELDS = [
    "full_name", "email", "phone", "whatsapp", "company_name",
    "nationality", "passport_number", "passport_expiry", "date_of_birth",
    "status", "client_type", "assigned_to", "avatar_url",
    "address", "notes", "tags", "custom_fields"
]
```

#### Delete Client

**Endpoint**: `DELETE /api/crm/clients/{id}`

- Soft delete (sets `status = inactive`)
- Frontend must call `router.refresh()` after navigation

### 3. Family Members

**Endpoints**:

- `POST /api/crm/clients/{id}/family` - Add member
- `PATCH /api/crm/clients/{id}/family/{member_id}` - Update
- `DELETE /api/crm/clients/{id}/family/{member_id}` - Remove

**Relationships**: `spouse`, `child`, `parent`, `dependent`

### 4. Documents

**Endpoints**:

- `POST /api/crm/clients/{id}/documents` - Upload
- `GET /api/crm/clients/{id}/documents` - List
- `PATCH /api/crm/clients/{id}/documents/{doc_id}` - Update
- `DELETE /api/crm/clients/{id}/documents/{doc_id}` - Archive

**Categories**: `immigration`, `pma`, `tax`, `personal`, `other`

**Features**:

- Google Drive integration
- Expiry date tracking with alerts
- Thumbnail previews
- Family member linking

### 5. OCR Integration

**Endpoint**: `POST /api/crm/clients/extract-passport`

**Request**:

```json
{
  "client_id": 123,
  "image_url": "https://drive.google.com/file/d/xxx/view"
}
```

**Response**:

```json
{
  "success": true,
  "passport_number": "AB1234567",
  "passport_expiry": "2030-12-31",
  "message": "Passport data extracted and saved"
}
```

**Model**: `gemini-3-flash-preview`

### 6. Avatar Fallback System

3-tier fallback:

1. **Uploaded photo** (`avatar_url`)
2. **Country flag emoji** (based on nationality)
3. **White/gray circle** (default)

**Supported Flags**: 30+ countries (IT, US, RU, UA, etc.)

---

## API Reference

### Clients

| Method | Endpoint                            | Description    | Auth     | Filter         |
| ------ | ----------------------------------- | -------------- | -------- | -------------- |
| GET    | `/api/crm/clients`                  | List clients   | Required | by assigned_to |
| POST   | `/api/crm/clients`                  | Create client  | Required | -              |
| GET    | `/api/crm/clients/{id}`             | Get detail     | Required | -              |
| PATCH  | `/api/crm/clients/{id}`             | Update client  | Required | -              |
| DELETE | `/api/crm/clients/{id}`             | Soft delete    | Required | -              |
| POST   | `/api/crm/clients/extract-passport` | OCR extraction | Required | -              |

### Family Members

| Method | Endpoint                             | Description   |
| ------ | ------------------------------------ | ------------- |
| GET    | `/api/crm/clients/{id}/family`       | List members  |
| POST   | `/api/crm/clients/{id}/family`       | Add member    |
| PATCH  | `/api/crm/clients/{id}/family/{mid}` | Update member |
| DELETE | `/api/crm/clients/{id}/family/{mid}` | Delete member |

### Documents

| Method | Endpoint                                | Description      |
| ------ | --------------------------------------- | ---------------- |
| GET    | `/api/crm/clients/{id}/documents`       | List documents   |
| POST   | `/api/crm/clients/{id}/documents`       | Add document     |
| PATCH  | `/api/crm/clients/{id}/documents/{did}` | Update document  |
| DELETE | `/api/crm/clients/{id}/documents/{did}` | Archive document |

### Interactions (Timeline)

| Method | Endpoint                         | Description        |
| ------ | -------------------------------- | ------------------ |
| GET    | `/api/crm/clients/{id}/timeline` | Get interactions   |
| POST   | `/api/crm/interactions/`         | Create interaction |

### Practices

| Method | Endpoint                  | Description           |
| ------ | ------------------------- | --------------------- |
| GET    | `/api/crm/practices`      | List practices (RBAC) |
| POST   | `/api/crm/practices`      | Create practice       |
| GET    | `/api/crm/practices/{id}` | Get practice detail   |
| PATCH  | `/api/crm/practices/{id}` | Update practice       |

### Drive Folders

| Method | Endpoint                                     | Description          |
| ------ | -------------------------------------------- | -------------------- |
| POST   | `/clients/{id}/create-drive-folder`          | Create GDrive folder |
| GET    | `/clients/{id}/drive-folder`                 | Get folder info      |
| GET    | `/clients/{id}/drive-folder/structure`       | List contents        |
| POST   | `/clients/{id}/drive-folder/{folder}/upload` | Upload file          |

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
    status VARCHAR(50) DEFAULT 'lead',
    client_type VARCHAR(50) DEFAULT 'individual',
    assigned_to VARCHAR(255),          -- team member email
    avatar_url TEXT,
    address TEXT,
    notes TEXT,
    tags TEXT[],
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
    relationship VARCHAR(50),
    date_of_birth DATE,
    nationality VARCHAR(100),
    passport_number VARCHAR(50),
    passport_expiry DATE,
    current_visa_type VARCHAR(100),
    visa_expiry DATE,
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
    document_category VARCHAR(50),
    file_name VARCHAR(500),
    file_id VARCHAR(255),
    file_url TEXT,
    google_drive_file_url TEXT,
    expiry_date DATE,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'active',
    storage_type VARCHAR(50) DEFAULT 'google_drive',
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### interactions

```sql
CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50),      -- note, call, email, meeting
    summary TEXT,
    team_member VARCHAR(255),
    direction VARCHAR(50),             -- inbound, outbound
    interaction_date TIMESTAMP DEFAULT NOW(),
    sentiment_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### practices

```sql
CREATE TABLE practices (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    practice_type_code VARCHAR(50),    -- E28A, D1, etc.
    practice_type_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    assigned_to VARCHAR(255),
    start_date DATE,
    target_completion_date DATE,
    actual_completion_date DATE,
    estimated_value DECIMAL(12,2),
    notes TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Common Issues & Solutions

### Issue 1: "Failed to update - Database service temporarily unavailable"

**Symptom**: Error when creating/updating with dates

**Root Cause**: Empty string `''` to PostgreSQL DATE column

```
asyncpg.exceptions.DataError: invalid input for query argument $8: ''
```

**Solution**: Backend sanitizes dates automatically:

```python
passport_expiry = data.passport_expiry if data.passport_expiry else None
```

**Frontend**: Send `undefined` instead of empty string:

```typescript
const data = {
  passport_expiry: formData.passport_expiry || undefined, // ✅
};
```

### Issue 2: "All clients visible to all members"

**Root Cause**: Missing authentication check

**Solution**: Server-side filtering enforced in all routers

### Issue 3: "Delete client doesn't refresh page"

**Solution**: Add `router.refresh()` after navigation

```typescript
await api.crm.deleteClient(id);
router.push("/clients");
router.refresh(); // Force refetch
```

---

## Troubleshooting

### Debug Commands

```bash
# Production logs
fly logs -a nuzantara-rag | grep -i "error\|exception"

# Check specific client
fly logs -a nuzantara-rag | grep "client_id=123"

# Local logs
tail -f apps/backend-rag/logs/app.log
```

### Common Error Patterns

| Error                                         | Cause                  | Fix                   |
| --------------------------------------------- | ---------------------- | --------------------- |
| `DataError: invalid input for query argument` | Empty string to DATE   | Sanitize dates        |
| `HTTPException 401`                           | Missing/expired JWT    | Re-login              |
| `HTTPException 400: Invalid field name`       | Field not in whitelist | Add to ALLOWED_FIELDS |
| `HTTPException 403`                           | RBAC violation         | Check assigned_to     |

---

## Changelog

### v3.0 (2026-02-07)

- Consolidated `CRM_SYSTEM.md` and `CRM_SYSTEM_DOCUMENTATION.md`
- Added Drive Folders integration documentation
- Updated schema with latest fields
- Added practices endpoints

### v2.0 (2026-01-05)

**Security Fixes**:

- Added authentication requirement for client list
- Enforced strict `assigned_to` filtering
- Removed special-case logic

**Data Integrity**:

- Date sanitization in all create/update endpoints
- Fixed empty string → NULL conversion

**Features**:

- Avatar fallback system
- Delete client auto-refresh
- Team members dropdown updated

### v1.0 (2025-12-01)

- Initial CRM system
- Basic CRUD for clients, family, documents
- Timeline interactions

---

## Support

**Maintainer**: Zero (zero@balizero.com)  
**Deployment**: https://nuzantara-rag.fly.dev  
**Frontend**: https://kita.balizero.com  
**Logs**: `fly logs -a nuzantara-rag`

**Emergency Rollback**:

```bash
fly releases -a nuzantara-rag
fly deploy -a nuzantara-rag --image registry.fly.io/nuzantara-rag:deployment-{VERSION}
```

---

_Documentation consolidated on 2026-02-07. Previous versions archived in `docs/archive/`._

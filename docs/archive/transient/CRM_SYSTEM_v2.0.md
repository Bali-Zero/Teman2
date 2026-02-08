# CRM System Documentation

## Overview

The Nuzantara CRM system manages client relationships, practices (services), interactions, and documents for Bali Zero's immigration and business consulting services.

---

## Architecture

### Database Schema

| Table              | Purpose                                                   |
| ------------------ | --------------------------------------------------------- |
| `clients`          | Client profiles (name, email, phone, passport, visa info) |
| `practices`        | Services/engagements (PT PMA, KITAS, Visas)               |
| `interactions`     | Communication logs (calls, emails, meetings)              |
| `client_documents` | Document attachments (passports, visas, contracts)        |
| `team_members`     | Staff profiles and assignments                            |

### API Router

**Location:** `apps/backend-rag/backend/app/routers/crm_clients.py`

---

## API Endpoints

### Client Management

| Method | Endpoint                | Description                             |
| ------ | ----------------------- | --------------------------------------- |
| GET    | `/api/crm/clients`      | List clients with pagination            |
| GET    | `/api/crm/clients/{id}` | Get client profile with practices, docs |
| POST   | `/api/crm/clients`      | Create new client                       |
| PUT    | `/api/crm/clients/{id}` | Update client                           |
| DELETE | `/api/crm/clients/{id}` | Delete client                           |

### Document Operations

| Method | Endpoint                              | Description           |
| ------ | ------------------------------------- | --------------------- |
| GET    | `/api/crm/clients/{id}/documents`     | List client documents |
| POST   | `/api/crm/clients/{id}/documents`     | Upload document       |
| DELETE | `/api/crm/clients/documents/{doc_id}` | Delete document       |

### OCR & Extraction

| Method | Endpoint                            | Description                                      |
| ------ | ----------------------------------- | ------------------------------------------------ |
| POST   | `/api/crm/clients/extract-passport` | Extract passport data from image (Gemini Vision) |

---

## Frontend

### Client Profile Page

**Location:** `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx`

### Tabs

1. **Overview** - Client summary with 3 cards
2. **Documents** - Document list with image previews
3. **Family** - Family members (spouse, children)
4. **Process** - Practice details and timeline

### Overview Cards (2026-01-13)

Three equal-sized cards in passport-like 3:2 ratio:

1. **Passport Card**
   - Shows passport photo thumbnail
   - Passport number and expiry
   - OCR extraction button (auto-fills from photo)

2. **Visa Card**
   - Current visa type and expiry
   - Alert colors (red/yellow/green based on expiry)
   - Links to active practice if renewal in progress

3. **Process Card**
   - Active practice info (type, status, team member)
   - Progress indicator with pulsing animation
   - Estimated completion date

### Document Previews (2026-01-13)

Documents tab now shows:

- Thumbnail preview using Google Drive embed
- Alert color border based on expiry
- Click to open in Google Drive

---

## OCR Integration

### Passport Extraction Endpoint

**POST** `/api/crm/clients/extract-passport`

**Request:**

```json
{
  "client_id": 123,
  "image_url": "https://drive.google.com/file/d/xxx/view"
}
```

**Response:**

```json
{
  "success": true,
  "passport_number": "AB1234567",
  "passport_expiry": "2030-12-31",
  "message": "Passport data extracted and saved"
}
```

**Flow:**

1. Download image from Google Drive (converts view URL to download URL)
2. Convert to base64
3. Send to Gemini Vision with OCR prompt
4. Parse JSON response
5. Update client record in PostgreSQL
6. Return extracted data

**Gemini Model:** `gemini-3-flash-preview`

**Prompt:**

```
Analyze this passport image and extract the following information.
Return ONLY a JSON object with these fields:
{
  "passport_number": "the passport number or null if not found",
  "expiry_date": "expiry date in YYYY-MM-DD format or null if not found"
}
```

---

## Types (Frontend)

### ClientProfile

```typescript
interface ClientProfile {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  passport_number: string | null;
  passport_expiry: string | null;
  current_visa_type: string | null;
  current_visa_expiry: string | null;
  passport_image_url: string | null;
  practices: {
    id: number;
    status: string;
    expiry_date: string | null;
    practice_type_code: string;
    practice_type_name: string;
    alert_color: string | null;
  }[];
  documents: ClientDocument[];
  // ... other fields
}
```

### ClientDocument

```typescript
interface ClientDocument {
  id: number;
  document_type: string;
  document_name: string;
  expiry_date: string | null;
  google_drive_file_url: string | null;
  alert_color: string | null;
}
```

---

## Configuration

### Environment Variables

| Variable                     | Description                   |
| ---------------------------- | ----------------------------- |
| `GOOGLE_API_KEY`             | Gemini API key for Vision OCR |
| `GOOGLE_DRIVE_CLIENT_ID`     | OAuth client for Drive access |
| `GOOGLE_DRIVE_CLIENT_SECRET` | OAuth secret                  |

---

## Changelog

### 2026-01-13

- **3 Equal Cards**: Passport, Visa, Process cards with 3:2 aspect ratio
- **OCR Endpoint**: `POST /api/crm/clients/extract-passport` using Gemini Vision
- **Document Previews**: Thumbnail previews in Documents tab
- **TypeScript Fixes**: Proper typing for `ClientProfile['practices']`

---

## Related Files

| File                                                   | Purpose               |
| ------------------------------------------------------ | --------------------- |
| `backend/app/routers/crm_clients.py`                   | API router            |
| `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` | Profile page          |
| `backend/services/multimodal/pdf_vision_service.py`    | Vision service        |
| `backend/llm/genai_client.py`                          | Gemini client wrapper |

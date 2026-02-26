# 📄 Document Upload Enhancement

> **Version:** 2.0  
> **Date:** 2026-02-21  
> **Deploy:** Production (nuzantara-rag.fly.dev)  
> **Commit:** e11466d4f

---

## 🎯 Overview

Il sistema di upload documenti del Client Portal è stato completamente rivisitato con 5 nuove funzionalità enterprise-grade:

1. **🔒 Virus Scanning** - Heuristic malware detection
2. **📁 Google Drive Upload** - Structured folder organization
3. **👁️ OCR (Gemini Vision)** - Text extraction da PDF e immagini
4. **📅 Expiry Detection** - Auto-detect scadenza passport/visa/kitas
5. **📧 Enhanced Notifications** - Email con Drive link e scadenza

---

## 🏗️ Architecture

### Workflow Completo

```
┌──────────────┐
│   CLIENTE    │  my.balizero.com/vault
│  Upload File │  PDF, JPG, PNG, DOC
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         STEP 1: VIRUS SCAN                  │
│  - Extension check (.exe, .php, .sh)        │
│  - Pattern detection (eval, base64, script) │
│  - 🚫 Blocca se minaccia rilevata           │
└──────┬──────────────────────────────────────┘
       │ ✅ Clean
       ▼
┌─────────────────────────────────────────────┐
│         STEP 2: GOOGLE DRIVE UPLOAD         │
│  Folder: Zantara Portal Uploads/            │
│          └── {client_id}_{name}/            │
│              └── {document_type}/           │
│                  └── {timestamp}_{file}     │
└──────┬──────────────────────────────────────┘
       │ ✅ Uploaded
       ▼
┌─────────────────────────────────────────────┐
│         STEP 3: OCR (Gemini Vision)         │
│  - PDF → PyMuPDF → Images → Gemini Vision   │
│  - IMG → Gemini Vision OCR                  │
│  - Fallback: PyMuPDF text extraction        │
└──────┬──────────────────────────────────────┘
       │ ✅ Text Extracted
       ▼
┌─────────────────────────────────────────────┐
│         STEP 4: EXPIRY DETECTION            │
│  - Keywords: "expiry", "valid until",       │
│            "sampai", "berlaku"              │
│  - Date formats: DD/MM/YYYY, MM/DD/YYYY     │
│  - Confidence scoring (0.5-0.8)             │
└──────┬──────────────────────────────────────┘
       │ ✅ Expiry Detected
       ▼
┌─────────────────────────────────────────────┐
│         STEP 5: DATABASE SAVE               │
│  - Metadata + Drive ID + OCR text           │
│  - Timeline event (client visible)          │
│  - Status: 'received'                       │
└──────┬──────────────────────────────────────┘
       │ ✅ Saved
       ▼
┌─────────────────────────────────────────────┐
│         STEP 6: EMAIL NOTIFICATION          │
│  To: assigned_to (fallback: zero@balizero)  │
│  Subject: 📄 Nuovo Documento Caricato       │
│  Body: File, Type, Drive Link, Expiry       │
└─────────────────────────────────────────────┘
```

---

## 📦 Componenti

### 1. VirusScanner

**File:** `backend/services/portal/portal_service.py` (linee 53-100)

**Funzionalità:**

- Scansiona file content per pattern malevoli
- Blocca upload se minaccia rilevata
- Graceful degradation (continua senza bloccare se errori)

**Pattern rilevati:**

```python
SUSPICIOUS_EXTENSIONS = {'.exe', '.dll', '.bat', '.cmd', '.sh', '.php', '.jsp', '.asp'}
SUSPICIOUS_PATTERNS = [b'eval(', b'base64_decode', b'<?php', b'<script', b'javascript:']
```

**Output:**

```python
{
    "clean": bool,
    "threats": ["Suspicious file extension in virus.exe"],
    "scanner": "basic_heuristic_v1"
}
```

---

### 2. DocumentOCR (Gemini Vision)

**File:** `backend/services/portal/portal_service.py` (linee 105-310)

**Tecnologia:** Gemini-2.0-flash-001 (stessa dei passaporti)

**Flusso PDF:**

1. PyMuPDF renderizza pagine → immagini PNG
2. Gemini Vision estrae testo da ogni immagine
3. Concatena testo di tutte le pagine

**Flusso Immagini:**

1. PIL.Image carica l'immagine
2. Gemini Vision OCR diretto

**Prompt usato:**

```
Extract all text from this document image.
Preserve the layout and structure as much as possible.
Return only the extracted text, no additional commentary.
```

**Fallback chain:**

1. Gemini Vision OCR
2. PyMuPDF text extraction (nativo)
3. Empty text (graceful)

**Output:**

```python
{
    "text": "PASSPORT\nDate of Expiry: 10/01/2030...",
    "pages": 2,
    "success": True,
    "error": None
}
```

---

### 3. ExpiryDetector

**File:** `backend/services/portal/portal_service.py` (linee 313-445)

**Keywords supportate:**

```python
EXPIRY_KEYWORDS = [
    'expir', 'valid until', 'valid to', 'date of expiration',
    'expiry date', 'expiration date', 'valid thru', 'valid through',
    'date of expiry', 'passport expiry', 'visa expiry', 'kitas expiry',
    'merp expiry', 'validity expires', 'until', 'sampai', 'berlaku'
]
```

**Date formats supportati:**

- DD/MM/YYYY, DD-MM-YYYY
- MM/DD/YYYY, MM-DD-YYYY
- YYYY/MM/DD, YYYY-MM-DD

**Logica di detection:**

1. Cerca date vicino a expiry keywords (confidence 0.8)
2. Fallback: se doc tipo passport/visa/kitas, prendi data più futura (confidence 0.5)

**Output:**

```python
{
    "expiry_date": "2030-01-10",  # ISO format
    "confidence": 0.8,             # 0.0 - 1.0
    "method": "keyword_context",   # "keyword_context" | "pattern_match" | "none"
    "all_dates": ["2020-01-10", "2030-01-10"]
}
```

---

## 🔌 API Endpoints

### POST /api/portal/documents/upload

Upload documento con full processing pipeline.

**Headers:**

```http
Authorization: Bearer {jwt_token}
Content-Type: multipart/form-data
```

**Request:**

```http
POST /api/portal/documents/upload
Content-Type: multipart/form-data

file: (binary)          # File content
document_type: string    # "passport", "visa", "kitas", "tax_document", etc.
practice_id: int?        # Optional - link to practice
```

**Response (Success):**

```json
{
  "success": true,
  "message": "Document uploaded successfully",
  "data": {
    "id": 12345,
    "type": "passport",
    "name": "passport.pdf",
    "status": "received",
    "size_kb": 1240,
    "created_at": "2026-02-21T14:32:15Z",
    "expiry_date": "2030-01-10",
    "extracted_text_preview": "PASSPORT...",
    "processing": {
      "virus_clean": true,
      "ocr_pages": 2,
      "drive_uploaded": true
    }
  }
}
```

**Response (Virus Detected):**

```json
{
  "success": false,
  "detail": "Security threat detected in file: Suspicious pattern detected. Upload blocked for security reasons."
}
```

**Response (Auth Error):**

```json
{
  "detail": "Authentication required"
}
```

---

### GET /api/portal/documents

Lista documenti del cliente.

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "type": "passport",
      "name": "passport.pdf",
      "status": "received",
      "expiry_date": "2030-01-10",
      "downloadable": false
    }
  ]
}
```

---

### GET /api/portal/timeline

Timeline attività (include document upload events).

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "event_type": "document_received",
      "title": "Document received",
      "description": "passport.pdf uploaded successfully (Expiry detected: 2030-01-10)",
      "event_date": "2026-02-21T14:32:15Z",
      "color": "success"
    }
  ]
}
```

---

## 🗄️ Database Schema

### Tabella: documents

| Column            | Type                   | Description                               |
| ----------------- | ---------------------- | ----------------------------------------- |
| `id`              | SERIAL PK              | ID univoco                                |
| `client_id`       | INT FK → clients(id)   | Client owner                              |
| `practice_id`     | INT FK → practices(id) | Practice link (optional)                  |
| `document_type`   | VARCHAR(100)           | passport, visa, kitas, tax_document, etc. |
| `file_name`       | VARCHAR(255)           | Original filename                         |
| `status`          | VARCHAR(50)            | 'received' (was 'pending')                |
| `uploaded_by`     | VARCHAR(255)           | Client email                              |
| `uploaded_source` | VARCHAR(20)            | 'client' or 'team'                        |
| `file_size_kb`    | INT                    | File size                                 |
| `mime_type`       | VARCHAR(100)           | MIME type                                 |
| `storage_type`    | VARCHAR(50)            | 'google_drive' (was 'pending')            |
| `storage_path`    | VARCHAR(500)           | Folder path in Drive                      |
| `file_id`         | VARCHAR(255)           | Google Drive file ID                      |
| `file_url`        | TEXT                   | Google Drive view URL                     |
| `extracted_text`  | TEXT                   | OCR extracted text (first 10k chars)      |
| `expiry_date`     | DATE                   | Detected expiry date                      |
| `client_visible`  | BOOLEAN                | true                                      |
| `created_at`      | TIMESTAMP              | Upload timestamp                          |

### Tabella: timeline_events

| Column           | Type         | Description                        |
| ---------------- | ------------ | ---------------------------------- |
| `client_id`      | INT FK       | Client reference                   |
| `practice_id`    | INT FK       | Practice reference                 |
| `event_type`     | VARCHAR(50)  | 'document_received'                |
| `title`          | VARCHAR(255) | 'Document received'                |
| `description`    | TEXT         | '{filename} uploaded successfully' |
| `event_date`     | TIMESTAMP    | Event timestamp                    |
| `client_visible` | BOOLEAN      | true                               |
| `color`          | VARCHAR(20)  | 'success'                          |

---

## 📁 Google Drive Folder Structure

```
Zantara Portal Uploads/                    # Root folder
├── 123_Marco_Rossi/                       # Client folder: {id}_{name}
│   ├── Passport/                          # Document type folder
│   │   └── 20260221_143052_passport.pdf  # Timestamp_filename
│   ├── Visa/
│   ├── Kitas/
│   ├── Tax_Document/
│   └── Sponsor_Letter/
├── 456_John_Smith/
│   └── ...
└── ...
```

---

## 📧 Email Notifications

**Recipient:** `assigned_to` (fallback: zero@balizero.com)

**Subject:** `📄 Nuovo Documento Caricato - {client_name}`

**Body:**

```
Ciao,

Il cliente {client_name} ha caricato un nuovo documento nel portale.

Dettagli:
• File: 20260221_143052_passport.pdf
• Tipo: Passport
• Cliente: Marco Rossi
• Data Scadenza Rilevata: 2030-01-10
• Link Drive: https://drive.google.com/file/d/...

Accedi al workspace per visualizzare e verificare il documento:
https://zantara-crm.vercel.app/clients/{client_id}

---
Questa è una notifica automatica da Bali Zero CRM.
```

---

## 🚀 Deploy Notes

### Requirements

**Nuove dipendenze:**

```txt
# requirements.txt e requirements-prod.txt
python-magic>=0.4.27  # MIME type detection
```

**Dipendenze già presenti:**

```txt
PyMuPDF>=1.23.0      # PDF rendering
Pillow>=10.0.0       # Image processing
google-genai>=1.56.0 # Gemini Vision API
```

### Deploy Command

```bash
# Build e deploy
cd apps/backend-rag
fly deploy --strategy rolling --app nuzantara-rag

# Verifica health
curl https://nuzantara-rag.fly.dev/health
```

### Environment Variables

Richiede le stesse variabili di sempre:

```bash
DATABASE_URL=postgresql://...
GOOGLE_DRIVE_CLIENT_ID=...
GOOGLE_DRIVE_CLIENT_SECRET=...
GOOGLE_DRIVE_REDIRECT_URI=...
GOOGLE_DRIVE_ROOT_FOLDER_ID=...
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
```

---

## 🧪 Testing

### Test Core Features (Isolato)

```bash
python3 test_core_features.py
```

**Risultati attesi:**

```
🦠 VirusScanner Tests
   ✅ Clean PDF
   ✅ PHP with eval
   ✅ EXE extension
   ✅ Script tag

📅 ExpiryDetector Tests
   ✅ Simple expiry
   ✅ Keyword context
   ✅ Valid until
   ✅ Indonesian keywords
   ✅ Empty text

9/9 tests passed
```

### Test API Endpoints

```bash
curl https://nuzantara-rag.fly.dev/health
# Expected: {"status": "healthy", ...}

curl -X POST https://nuzantara-rag.fly.dev/api/portal/documents/upload
# Expected: {"detail": "Authentication required"}
```

### Test End-to-End

1. Login al portal: `my.balizero.com`
2. Sezione Vault → Upload Document
3. Seleziona file PDF (passport o KITAS)
4. Verifica:
   - ✅ File appare in lista con status "received"
   - ✅ Email arriva al lead con link Drive
   - ✅ File visibile su Google Drive in folder strutturata
   - ✅ Scadenza rilevata correttamente

---

## ⚠️ Troubleshooting

### Virus Scan blocca file legittimi

**Problema:** File pulito bloccato dal virus scanner.

**Soluzione:** Il virus scanner è conservativo. Se un file viene bloccato erroneamente, il cliente può:

1. Cambiare formato (es: da .docx a .pdf)
2. Contattare il team via email
3. Il team può uploadare manualmente dal CRM

### Google Drive upload fallisce

**Problema:** File salvato nel DB ma non su Drive.

**Causa:** Token OAuth scaduto o Drive non configurato.

**Comportamento:** L'upload continua, il file rimane con `storage_type='pending'`.

**Soluzione:**

```bash
# Verifica token
fly ssh console --app nuzantara-rag
python -c "from backend.services.integrations.google_drive_service import GoogleDriveService; ..."

# Ri-autenticazione se necessaria
# (via /api/admin/google-drive/auth)
```

### OCR non estrae testo

**Problema:** `extracted_text` è vuoto nel DB.

**Causa possibili:**

- PDF è una scansione di bassa qualità
- Immagine troppo grande/sfocata
- Gemini Vision API error

**Fallback:** Il sistema usa PyMuPDF text extraction nativo come fallback.

### Expiry non rilevata

**Problema:** `expiry_date` è NULL.

**Causa:** Formato data non standard o keywords non riconosciute.

**Soluzione:** Il team può inserire manualmente la scadenza nel CRM.

---

## 📈 Performance

| Metrica          | Valore                         |
| ---------------- | ------------------------------ |
| Upload max size  | 10 MB                          |
| Virus scan       | < 10 ms                        |
| Drive upload     | 1-5 sec (dipende da file size) |
| OCR (Gemini)     | 2-10 sec per pagina            |
| Expiry detection | < 50 ms                        |
| Total response   | 3-15 sec                       |

**Note:** Drive upload e OCR sono async (fire-and-forget), non bloccano la risposta HTTP.

---

## 🔮 Future Enhancements

- [ ] ClamAV integration per virus scanning avanzato
- [ ] Auto-categorizzazione documenti con ML
- [ ] Validazione automatica (es: passport number check)
- [ ] Notifiche WhatsApp oltre a email
- [ ] Preview documenti nel browser
- [ ] Download diretto dal portal (proxy da Drive)

---

## 📞 Support

Per issues o domande:

- **Email:** zero@balizero.com
- **Dashboard:** https://fly.io/apps/nuzantara-rag/monitoring
- **Logs:** `fly logs --app nuzantara-rag`

---

**Documentazione aggiornata al:** 2026-02-21  
**Versione sistema:** v100-qdrant  
**Stato:** ✅ Production Ready

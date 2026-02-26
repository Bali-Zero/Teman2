# Changelog - Document Upload Enhancement

## [2.0.0] - 2026-02-21

### 🚀 New Features

#### 1. Virus Scanning

- Heuristic malware detection
- Pattern matching for suspicious content
- Extension blocking (.exe, .php, .sh, etc.)
- Immediate upload blocking on threat detection

#### 2. Google Drive Upload

- Automatic folder structure creation
- Client-organized folders: `{client_id}_{name}/`
- Document type subfolders
- Timestamp-based filenames to prevent collisions

#### 3. OCR (Gemini Vision)

- Same technology used for passport processing
- PDF text extraction via page rendering
- Image text extraction
- PyMuPDF fallback for native PDF text

#### 4. Expiry Detection

- Automatic detection of passport/visa/kitas expiry dates
- Multi-format date parsing (DD/MM/YYYY, YYYY-MM-DD, etc.)
- Multi-language keyword support (English + Indonesian)
- Confidence scoring

#### 5. Enhanced Email Notifications

- Google Drive link in notification
- Detected expiry date in email body
- Direct link to client workspace

### 🗄️ Database Changes

#### Modified Table: `documents`

```sql
-- New columns
ALTER TABLE documents ADD COLUMN storage_path VARCHAR(500);
ALTER TABLE documents ADD COLUMN file_id VARCHAR(255);
ALTER TABLE documents ADD COLUMN file_url TEXT;
ALTER TABLE documents ADD COLUMN extracted_text TEXT;
ALTER TABLE documents ADD COLUMN expiry_date DATE;

-- Status change: 'pending' → 'received'
```

### 📦 Dependencies

#### Added

- `python-magic>=0.4.27` - MIME type detection

#### Already Present

- `PyMuPDF` - PDF rendering
- `Pillow` - Image processing
- `google-genai` - Gemini Vision API

### 🔧 API Changes

#### Response Format Update

```json
// New fields in upload response
{
  "data": {
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

### 🐛 Bug Fixes

- Removed Amanda from team members (personale uscito)

### 📚 Documentation

- Complete technical documentation in `docs/DOCUMENT_UPLOAD_ENHANCEMENT.md`
- API endpoint specifications
- Database schema documentation
- Troubleshooting guide

### 🧪 Testing

- 9/9 core feature tests passing
- 4/4 API endpoint tests passing
- Deploy verification complete

---

## Deploy Information

```
Date: 2026-02-21
Commit: e11466d4f
Environment: Production
URL: https://nuzantara-rag.fly.dev/
Status: ✅ Online
```

### Deploy Checklist

- [x] Code committed
- [x] Tests passing
- [x] Requirements updated
- [x] Docker image built (445 MB)
- [x] Rolling deploy completed
- [x] Health checks passing
- [x] Database connected
- [x] Documentation complete

---

### Migration Notes

No database migration required - new columns are added dynamically with backward compatibility.

If `storage_path` column doesn't exist:

- Upload continues with metadata only
- Logs warning for missing column
- Graceful degradation

---

**Previous Version:** 1.0 (basic upload with metadata only)  
**Current Version:** 2.0 (full processing pipeline)

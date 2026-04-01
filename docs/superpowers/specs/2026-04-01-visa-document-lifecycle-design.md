# Visa Document Lifecycle System — Design Spec

**Date:** 2026-04-01
**Status:** Draft
**Author:** Claude Opus 4.6
**NLM Grounding:** NB-2 Immigration & Visa (60 sources, verified)

## Problem Statement

When a team member creates a client and uploads visa documents on kita.balizero.com:

1. **No file upload** — AddDocumentModal only accepts Drive URLs (paste-only)
2. **No automatic Drive subfolder structure** for Actual/Previous visa
3. **OCR extracts visa expiry to `documents` table** but never syncs to `clients.visa_expiry_date` — so **expiry notifications don't fire** for visas
4. **No bidirectional sync** — files uploaded directly to Drive aren't reflected in frontend
5. **No visa rotation** — when a new visa replaces the old one, no automatic archival

## Design Decisions

| Decision           | Choice                                                                  | Rationale                                                                                            |
| ------------------ | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Upload UX          | Improved AddDocumentModal with drag-and-drop                            | Single component reused everywhere, allows metadata entry                                            |
| Visa rotation      | Automatic: new upload → old moves to Previous Visa/                     | Keeps Drive organized for team members working in both Drive and frontend                            |
| Subfolder creation | On-demand (first upload creates if missing)                             | Avoids backfill migration for 5000+ existing clients                                                 |
| Bidirectional sync | Frontend→Drive via upload endpoint; Drive→Frontend via DrivePollService | Already have poll infra (5min cron on Air)                                                           |
| Visa history       | Full retention in Previous Visa/                                        | **Legally required**: 3 years of continuous KITAS needed for KITAP conversion (PP-31-2013 Pasal 167) |

## Architecture

### 1. Drive Subfolder Structure

New subfolders added under `01_Immigration/`:

```
01_Immigration/
├── Actual Visa/       ← current visa document (max 1 file)
├── Previous Visa/     ← historical visa documents (unbounded)
├── (other immigration files at root level)
```

**File:** `service_account_drive_service.py` — add to `STANDARD_SUBFOLDERS`:

- `"01_Immigration/Actual Visa"`
- `"01_Immigration/Previous Visa"`

New clients get these subfolders at creation. Existing clients get them on first visa upload (base64 endpoint already creates missing subfolders).

### 2. Frontend: AddDocumentModal with Drag-and-Drop

**Current state:** Text input for Google Drive URL only.
**New state:** Drag-and-drop zone + file picker. File converted to base64, sent to `POST /clients/{id}/documents/upload` (existing Path 2 endpoint).

**Changes to `AddDocumentModal.tsx`:**

- Add drag-and-drop zone (accepts PDF, JPG, PNG, max 10MB)
- File → base64 via FileReader
- Call `api.crm.uploadDocumentBase64()` instead of `api.crm.createDocument()`
- Keep Drive URL field as fallback (for files already in Drive)
- Pre-fill `document_category` and `document_type` based on context

**Pre-fill behavior:**
| Opened from | Pre-fill |
|-------------|----------|
| VisaCard "Upload" (Overview) | `category=immigration`, `type=visa`, `subfolder_hint=Actual Visa` |
| ImmigrationTab "Add Visa" | `category=immigration`, `type=visa`, `subfolder_hint=Actual Visa` |
| ImmigrationTab "Add Previous" | `category=immigration`, `type=visa`, `subfolder_hint=Previous Visa` |
| ImmigrationTab generic "Add" | `category=immigration`, type empty |
| Other tabs | No pre-fill |

**New API method in `crm.api.ts`:**

```typescript
async uploadDocumentBase64(clientId: number, data: {
  file: string;          // base64
  file_name: string;
  mime_type: string;
  document_type?: string;
  document_category?: string;
  subfolder_hint?: string;
  expiry_date?: string;
  family_member_id?: number;
}): Promise<{ document_id: number; file_url: string; ocr_triggered: boolean }>
```

### 3. Backend: Visa Rotation in Upload Endpoint

**File:** `crm_enhanced_documents.py` — modify `upload_document_base64()`

**New parameter:** `subfolder_hint` (optional string: `"Actual Visa"`, `"Previous Visa"`, or null)

**Rotation logic** (when `subfolder_hint == "Actual Visa"`):

1. Query `documents` table for existing Actual Visa: `WHERE client_id = $1 AND subfolder = 'Actual Visa' AND is_archived = false`
2. If found:
   a. Move file in Drive: `files.update(fileId, removeParents=actual_folder_id, addParents=previous_folder_id)`
   b. Update DB record: `SET subfolder = 'Previous Visa'`
3. Upload new file to `Actual Visa/` subfolder
4. Create new `documents` record with `subfolder = 'Actual Visa'`
5. Trigger OCR

**New DB column:** `documents.subfolder` (VARCHAR, nullable) — tracks which subfolder within the category folder.

**New Drive service method:** `move_file(file_id, from_parent_id, to_parent_id)` in `service_account_drive_service.py`.

### 4. OCR → Client Expiry Sync (Bug Fix)

**Current bug:** `_auto_ocr_visa()` saves `expiry_date` to `documents.expiry_date` but never updates `clients.visa_expiry_date`. The `visa_expiry_team_notifier` reads from `clients` → notifications never fire for visas.

**Fix in `crm_enhanced.py`** — after successful visa OCR:

```python
# Sync extracted data to clients table
await conn.execute("""
    UPDATE clients
    SET visa_expiry_date = $1,
        current_visa_type = $2,
        current_visa_sponsor = $3,
        updated_at = NOW()
    WHERE id = $4
""", expiry_date, visa_type, sponsor, client_id)
```

**OCR extraction fields** (enhanced from NLM guidance):
| Field | Source | Storage | Used By |
|-------|--------|---------|---------|
| `expiry_date` | "berlaku sampai" / "s/d" | `documents.expiry_date` + `clients.visa_expiry_date` | Notifier, frontend alerts |
| `visa_type` | KITAS/KITAP/B211/C1/etc | `documents.ocr_extracted_data` + `clients.current_visa_type` | Notifier email template |
| `sponsor` | Penjamin field | `documents.ocr_extracted_data` + `clients.current_visa_sponsor` | One Sponsor Policy check (SE 3/836/2026) |
| `visa_number` | Document number | `documents.ocr_extracted_data` | Reference |
| `issue_date` | Date of issuance | `documents.ocr_extracted_data` | History tracking |

### 5. Alembic Migration

**New migration:** `migration_061_visa_lifecycle.py`

```sql
-- New columns on clients
ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_visa_type VARCHAR(50);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_visa_sponsor VARCHAR(255);

-- New column on documents for subfolder tracking
ALTER TABLE documents ADD COLUMN IF NOT EXISTS subfolder VARCHAR(100);

-- Index for fast actual visa lookup
CREATE INDEX IF NOT EXISTS idx_documents_client_subfolder
    ON documents(client_id, subfolder) WHERE is_archived = false;
```

### 6. DrivePollService: Bidirectional Sync

**File:** `drive_poll_service.py` — enhance file processing

When poll detects a new file in a client's `Actual Visa/` subfolder:

1. Set `subfolder = 'Actual Visa'` on the new `documents` record
2. Check for existing Actual Visa document in DB
3. If exists → update old record: `subfolder = 'Previous Visa'` (file is already in correct Drive folder if user organized it manually)
4. Trigger OCR → sync to `clients.visa_expiry_date`

When poll detects a new file in `Previous Visa/`:

1. Set `subfolder = 'Previous Visa'` on the new `documents` record
2. No rotation needed
3. Still trigger OCR for history

**Subfolder detection:** Poll service already resolves parent folder IDs. Add mapping from folder name → subfolder value when parent is within `01_Immigration/`.

### 7. Visa Expiry Notifications (Enhanced)

**File:** `visa_expiry_team_notifier.py`

**Current:** Generic "visa scade tra X giorni"
**New:** Uses `current_visa_type` and `current_visa_sponsor`:

> "Eduardo Sepulveda — **KITAS E23** (sponsor: PT Bali Zero) scade tra 28 giorni (2026-04-29)"

**Also add:** Cross-check passport expiry vs visa expiry. If passport expires before visa, warn:

> "ATTENZIONE: Passaporto scade PRIMA del KITAS (2026-03-15 vs 2026-04-29). KITAS non valido oltre scadenza passaporto."

### 8. Files to Modify

| #   | File                               | Type | What                                                                                                  |
| --- | ---------------------------------- | ---- | ----------------------------------------------------------------------------------------------------- |
| 1   | `service_account_drive_service.py` | Edit | Add 2 subfolders to STANDARD_SUBFOLDERS + `move_file()` method                                        |
| 2   | `crm_enhanced_documents.py`        | Edit | Add `subfolder_hint` param, rotation logic in upload endpoint                                         |
| 3   | `crm_enhanced.py`                  | Edit | `_auto_ocr_visa()` syncs to `clients.visa_expiry_date` + `current_visa_type` + `current_visa_sponsor` |
| 4   | `drive_poll_service.py`            | Edit | Detect Actual/Previous Visa subfolder, trigger rotation + set subfolder field                         |
| 5   | `document_categorizer.py`          | Edit | Add `actual_visa` / `previous_visa` sub-categories                                                    |
| 6   | `visa_expiry_team_notifier.py`     | Edit | Use `current_visa_type` + `current_visa_sponsor` in template, add passport cross-check                |
| 7   | `AddDocumentModal.tsx`             | Edit | Drag-and-drop + base64 upload + pre-fill from context                                                 |
| 8   | `VisaCard.tsx`                     | Edit | "Upload Visa" button opens modal pre-filled                                                           |
| 9   | `ImmigrationTab.tsx`               | Edit | Upload buttons for Actual/Previous sections                                                           |
| 10  | `crm.api.ts`                       | Edit | Add `uploadDocumentBase64()` method                                                                   |
| 11  | Migration 061                      | New  | `current_visa_type`, `current_visa_sponsor` on clients, `subfolder` on documents                      |

### 9. Edge Cases

| Case                                                                | Handling                                                                                                  |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Client has no Drive folder yet                                      | base64 endpoint creates root + subfolders on first upload                                                 |
| Multiple files uploaded as "Actual Visa" rapidly                    | Rotation is sequential (DB transaction), last upload wins                                                 |
| Team member uploads to Drive root `01_Immigration/` (not subfolder) | Poll creates document with `subfolder=NULL`, displayed in "Other" section                                 |
| OCR fails to extract expiry                                         | `clients.visa_expiry_date` unchanged, document saved with `ocr_status='error'`, manual entry via frontend |
| Passport expires before visa                                        | Notifier warns team leader in email, frontend shows yellow alert                                          |
| File too large (>10MB)                                              | Frontend validates before upload, shows error toast                                                       |
| Unsupported file type                                               | Frontend restricts to PDF/JPG/PNG, backend validates mime_type                                            |

### 10. Out of Scope

- Bulk backfill of Actual/Previous Visa subfolders for existing 5000+ clients (on-demand creation is sufficient)
- Working Permit subfolder (IMTA/RPTKA) — stays flat in `01_Immigration/`
- Auto-renewal workflow trigger (existing "Start Renewal" button in frontend already handles this)
- KITAP conversion tracking (future feature based on 3-year history)

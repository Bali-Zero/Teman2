# Visa Document Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable drag-and-drop visa upload with automatic Drive subfolder organization (Actual/Previous Visa), bidirectional sync, and OCR-driven expiry notifications.

**Architecture:** Frontend uploads file as base64 to existing endpoint, enhanced with `subfolder_hint` parameter. Backend handles visa rotation (move old to Previous Visa/), OCR extracts expiry+type+sponsor and syncs to `clients` table. DrivePollService detects Drive-side uploads and triggers same rotation. Notifier uses enriched client fields for precise alerts.

**Tech Stack:** Python/FastAPI (backend), Next.js/React (frontend), Google Drive API, Gemini Vision OCR, PostgreSQL, asyncpg

**Spec:** `docs/superpowers/specs/2026-04-01-visa-document-lifecycle-design.md`

---

## File Structure

| File                                                                            | Action | Responsibility                                                                                          |
| ------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------- |
| `backend/migrations/migration_073_visa_lifecycle.py`                            | Create | Alembic migration: add `current_visa_type`, `current_visa_sponsor` to clients, `subfolder` to documents |
| `backend/services/integrations/service_account_drive_service.py`                | Modify | Add `move_file()` method, add 2 new subfolders to `STANDARD_SUBFOLDERS`                                 |
| `backend/app/routers/crm_enhanced_documents.py`                                 | Modify | Add `subfolder_hint` to upload model, visa rotation logic                                               |
| `backend/app/routers/crm_enhanced.py`                                           | Modify | Sync OCR results to `clients.visa_expiry_date` + `current_visa_type` + `current_visa_sponsor`           |
| `backend/services/crm/drive_poll_service.py`                                    | Modify | Detect Actual/Previous Visa subfolder, set `subfolder` field, trigger rotation                          |
| `backend/services/compliance/visa_expiry_team_notifier.py`                      | Modify | Include `current_visa_type` in email template, add passport cross-check                                 |
| `mouth/src/app/(workspace)/clients/[id]/components/modals/AddDocumentModal.tsx` | Modify | Replace URL-only input with drag-and-drop + base64 upload                                               |
| `mouth/src/lib/api/crm/crm.api.ts`                                              | Modify | Add `uploadDocumentBase64()` method                                                                     |

---

### Task 1: Database Migration

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_073_visa_lifecycle.py`

- [ ] **Step 1: Create migration file**

```python
# apps/backend-rag/backend/migrations/migration_073_visa_lifecycle.py
"""
Migration 073: Visa document lifecycle support.

Adds:
- clients.current_visa_type (VARCHAR 50) — extracted by OCR
- clients.current_visa_sponsor (VARCHAR 255) — extracted by OCR
- documents.subfolder (VARCHAR 100) — tracks subfolder within category (e.g. "Actual Visa")
- Index on documents(client_id, subfolder) for fast actual visa lookup
"""
import asyncpg
import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "073"
DESCRIPTION = "Visa document lifecycle: client visa fields + document subfolder tracking"


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration."""
    # New columns on clients for OCR-extracted visa data
    await conn.execute("""
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_visa_type VARCHAR(50);
    """)
    await conn.execute("""
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_visa_sponsor VARCHAR(255);
    """)

    # New column on documents for subfolder tracking within category folder
    await conn.execute("""
        ALTER TABLE documents ADD COLUMN IF NOT EXISTS subfolder VARCHAR(100);
    """)

    # Index for fast "find actual visa for client" queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_client_subfolder
        ON documents(client_id, subfolder)
        WHERE is_archived IS NOT TRUE;
    """)

    logger.info("Migration 073 applied: visa lifecycle columns added")


async def down(conn: asyncpg.Connection) -> None:
    """Rollback migration."""
    await conn.execute("DROP INDEX IF EXISTS idx_documents_client_subfolder;")
    await conn.execute("ALTER TABLE documents DROP COLUMN IF EXISTS subfolder;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS current_visa_sponsor;")
    await conn.execute("ALTER TABLE clients DROP COLUMN IF EXISTS current_visa_type;")
    logger.info("Migration 073 rolled back")
```

- [ ] **Step 2: Run migration on Fly DB**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def migrate():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag')
    from backend.migrations.migration_073_visa_lifecycle import up
    await up(conn)
    await conn.close()
    print('Migration 073 applied')

asyncio.run(migrate())
"
```

- [ ] **Step 3: Verify columns exist**

```bash
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def verify():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag')
    # Check clients columns
    row = await conn.fetchrow(\"\"\"
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'clients' AND column_name IN ('current_visa_type', 'current_visa_sponsor')
        ORDER BY column_name
    \"\"\")
    assert row is not None, 'clients columns missing'
    # Check documents column
    row2 = await conn.fetchrow(\"\"\"
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'subfolder'
    \"\"\")
    assert row2 is not None, 'documents.subfolder missing'
    print('All columns verified')
    await conn.close()

asyncio.run(verify())
"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_073_visa_lifecycle.py
git commit -m "feat(migration): add visa lifecycle columns (073)"
```

---

### Task 2: Drive Service — move_file() + New Subfolders

**Files:**

- Modify: `apps/backend-rag/backend/services/integrations/service_account_drive_service.py:219-234` (STANDARD_SUBFOLDERS), add method after line 318

- [ ] **Step 1: Add new subfolders to STANDARD_SUBFOLDERS**

In `service_account_drive_service.py`, find the `STANDARD_SUBFOLDERS` list (line 219) and add the two new entries:

```python
# Current list at line 219-234:
STANDARD_SUBFOLDERS = [
    "00_Profile",
    "01_Immigration",
    "01_Immigration/Actual Visa",      # ← ADD
    "01_Immigration/Previous Visa",    # ← ADD
    "02_Company",
    "02_Company/AKTA",
    "02_Company/NIB",
    "02_Company/NPWP",
    "02_Company/Profile Perseroan",
    "03_Tax",
    "03_Tax/SPT company",
    "03_Tax/SPT personal",
    "03_Tax/LKPM reports",
    "03_Tax/NPWP personal",
    "04_Family",
    "99_Misc",
]
```

The `create_client_folder` method already handles nested paths via the `parts = subfolder_path.split("/")` logic at lines 262-269. `01_Immigration/Actual Visa` will be created as a child of `01_Immigration` automatically.

- [ ] **Step 2: Add move_file() method**

Add after the `create_client_folder` method (after line 318):

```python
async def move_file(
    self,
    file_id: str,
    from_parent_id: str,
    to_parent_id: str,
) -> dict[str, Any]:
    """
    Move a file from one Drive folder to another.
    Uses files.update with addParents/removeParents.
    """
    request = self.service.files().update(
        fileId=file_id,
        addParents=to_parent_id,
        removeParents=from_parent_id,
        fields="id, name, parents",
        supportsAllDrives=True,
    )
    result = await asyncio.to_thread(request.execute)
    logger.info(f"Moved file {file_id} from {from_parent_id} to {to_parent_id}")
    return result
```

- [ ] **Step 3: Verify import compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/integrations/service_account_drive_service.py
git commit -m "feat(drive): add Actual/Previous Visa subfolders + move_file()"
```

---

### Task 3: Backend Upload Endpoint — subfolder_hint + Visa Rotation

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced_documents.py:488-494` (model), `496-650` (endpoint)

- [ ] **Step 1: Add subfolder_hint to DocumentUploadBase64 model**

At line 488, add the new fields:

```python
class DocumentUploadBase64(BaseModel):
    file: str  # Base64
    file_name: str
    document_type: str
    mime_type: str | None = None
    notes: str | None = None
    subfolder_hint: str | None = None       # "Actual Visa", "Previous Visa", or None
    document_category: str | None = None    # Override auto-categorization
    expiry_date: str | None = None          # Manual expiry date fallback
    family_member_id: int | None = None     # Link to family member
```

- [ ] **Step 2: Add visa rotation logic in upload_document_base64**

After the file upload to Drive (after line 602), and before the INSERT (line 605), add rotation logic. Replace the section from line 515 to line 622 with:

Find this block (line 515-518):

```python
        # Determine category and folder name using filename-based categorization
        cat_result = auto_categorize_document(data.file_name)
        category = cat_result["document_category"]
        folder_name = CATEGORY_TO_FOLDER.get(category, "99_Misc")
```

Replace with:

```python
        # Determine category — use explicit override or auto-categorize from filename
        if data.document_category:
            category = data.document_category
        else:
            cat_result = auto_categorize_document(data.file_name)
            category = cat_result["document_category"]
        folder_name = CATEGORY_TO_FOLDER.get(category, "99_Misc")
```

Then, after subfolder resolution (after line 591 `subfolder_id = subfolder["id"]`), add subfolder_hint handling:

```python
            # Handle subfolder_hint for nested subfolders (e.g. "Actual Visa" inside 01_Immigration)
            target_subfolder_id = subfolder_id
            subfolder_value = None  # for documents.subfolder column

            if data.subfolder_hint and data.subfolder_hint in ("Actual Visa", "Previous Visa"):
                subfolder_value = data.subfolder_hint
                # Find or create the nested subfolder inside the category folder
                try:
                    nested_structure = await drive_service.get_folder_structure(
                        root_folder_id=subfolder_id,
                    )
                    nested_folder = next(
                        (f for f in nested_structure["folders"] if f["name"] == data.subfolder_hint),
                        None,
                    )
                    if not nested_folder:
                        nested_data = await drive_service.create_folder(
                            name=data.subfolder_hint,
                            parent_id=subfolder_id,
                        )
                        target_subfolder_id = nested_data["id"]
                    else:
                        target_subfolder_id = nested_folder["id"]
                except Exception as e:
                    logger.warning(f"Could not resolve subfolder_hint '{data.subfolder_hint}': {e}")

                # Visa rotation: if uploading to "Actual Visa", move existing actual to "Previous Visa"
                if data.subfolder_hint == "Actual Visa":
                    existing_actual = await conn.fetchrow(
                        """SELECT d.id, d.file_id FROM documents d
                           WHERE d.client_id = $1 AND d.subfolder = 'Actual Visa'
                             AND (d.is_archived IS NOT TRUE)
                           ORDER BY d.created_at DESC LIMIT 1""",
                        client_id,
                    )
                    if existing_actual and existing_actual["file_id"]:
                        # Find or create "Previous Visa" folder
                        prev_folder = next(
                            (f for f in nested_structure["folders"] if f["name"] == "Previous Visa"),
                            None,
                        ) if 'nested_structure' in dir() else None
                        if not prev_folder:
                            try:
                                prev_data = await drive_service.create_folder(
                                    name="Previous Visa",
                                    parent_id=subfolder_id,
                                )
                                prev_folder_id = prev_data["id"]
                            except Exception as e:
                                logger.error(f"Failed to create Previous Visa folder: {e}")
                                prev_folder_id = None
                        else:
                            prev_folder_id = prev_folder["id"]

                        if prev_folder_id:
                            try:
                                await drive_service.move_file(
                                    file_id=existing_actual["file_id"],
                                    from_parent_id=target_subfolder_id,
                                    to_parent_id=prev_folder_id,
                                )
                                await conn.execute(
                                    "UPDATE documents SET subfolder = 'Previous Visa', updated_at = NOW() WHERE id = $1",
                                    existing_actual["id"],
                                )
                                logger.info(f"Rotated visa doc {existing_actual['id']} to Previous Visa")
                            except Exception as e:
                                logger.error(f"Visa rotation failed: {e}")
```

Then update the upload call to use `target_subfolder_id` instead of `subfolder_id` (line 595):

```python
            # Upload File
            try:
                upload_result = await drive_service.upload_file_to_folder(
                    folder_id=target_subfolder_id,  # ← was subfolder_id
                    file_content=file_content,
                    file_name=data.file_name,
                    mime_type=data.mime_type,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to upload to drive: {e}") from e
```

And update the INSERT to include the `subfolder` column (line 605-622):

```python
            # Create Document Record
            doc_id = await conn.fetchval(
                """
                INSERT INTO documents (
                    client_id, document_type, document_category,
                    file_name, file_id, file_url, google_drive_file_url,
                    status, storage_type, notes, subfolder, expiry_date
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', 'google_drive', $8, $9, $10)
                RETURNING id
                """,
                client_id,
                data.document_type,
                category,
                data.file_name,
                upload_result["id"],
                upload_result.get("webViewLink"),
                upload_result.get("webViewLink"),
                data.notes,
                subfolder_value,
                _parse_date_or_none(data.expiry_date),
            )
```

Add this helper at the top of the file (near imports):

```python
def _parse_date_or_none(date_str: str | None) -> date | None:
    """Parse YYYY-MM-DD date string or return None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
```

- [ ] **Step 3: Verify import compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.crm_enhanced_documents import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_enhanced_documents.py
git commit -m "feat(upload): add subfolder_hint + visa rotation in base64 upload"
```

---

### Task 4: OCR → Client Expiry Sync (Bug Fix)

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced.py:350-428` (`_auto_ocr_visa`)

- [ ] **Step 1: Add client sync after OCR extraction**

In `_auto_ocr_visa()`, after the document update (after line 418 `await conn.execute(...)`), add sync to clients table. Find this block (lines 414-418):

```python
            if doc_id:
                params.append(doc_id)
                await conn.execute(
                    f"UPDATE documents SET {', '.join(update_parts)}, updated_at = NOW() WHERE id = ${param_idx}",
                    *params,
                )
```

Add immediately after:

```python
            # Sync visa data to clients table for notifications and CRM display
            visa_type = extracted.get("visa_type")
            sponsor = extracted.get("sponsor")
            expiry_date_parsed = None
            if extracted.get("expiry_date"):
                try:
                    expiry_date_parsed = datetime.strptime(extracted["expiry_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            sync_parts: list[str] = []
            sync_params: list[Any] = []
            sync_idx = 1

            if expiry_date_parsed:
                sync_parts.append(f"visa_expiry_date = ${sync_idx}")
                sync_params.append(expiry_date_parsed)
                sync_idx += 1

            if visa_type:
                sync_parts.append(f"current_visa_type = ${sync_idx}")
                sync_params.append(visa_type[:50])  # VARCHAR(50)
                sync_idx += 1

            if sponsor:
                sync_parts.append(f"current_visa_sponsor = ${sync_idx}")
                sync_params.append(sponsor[:255])  # VARCHAR(255)
                sync_idx += 1

            if sync_parts:
                sync_params.append(client_id)
                await conn.execute(
                    f"UPDATE clients SET {', '.join(sync_parts)}, updated_at = NOW() WHERE id = ${sync_idx}",
                    *sync_params,
                )
                logger.info(
                    f"Synced visa OCR to client {client_id}: type={visa_type}, expiry={expiry_date_parsed}, sponsor={sponsor}"
                )
```

- [ ] **Step 2: Verify import compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.crm_enhanced import router; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_enhanced.py
git commit -m "fix(ocr): sync visa expiry+type+sponsor from OCR to clients table"
```

---

### Task 5: DrivePollService — Subfolder Detection + Rotation

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/drive_poll_service.py:301-316` (document creation)

- [ ] **Step 1: Add subfolder detection and rotation**

Find the document creation block (lines 301-316). Replace with:

```python
            # Create document record with auto-categorization
            cat_result = auto_categorize_document(file_name)
            doc_category = cat_result["document_category"]

            # Detect if file is in Actual Visa / Previous Visa subfolder
            subfolder_value = None
            parent_name_lower = folder_name.lower() if isinstance(folder_name, str) else ""
            if parent_name_lower in ("actual visa", "previous visa"):
                subfolder_value = "Actual Visa" if "actual" in parent_name_lower else "Previous Visa"
                doc_category = "immigration"

                # Visa rotation: if new file in Actual Visa, archive the old one
                if subfolder_value == "Actual Visa":
                    async with db_pool.acquire() as conn:
                        old_actual = await conn.fetchrow(
                            """SELECT id FROM documents
                               WHERE client_id = $1 AND subfolder = 'Actual Visa'
                                 AND (is_archived IS NOT TRUE)
                               ORDER BY created_at DESC LIMIT 1""",
                            client_id,
                        )
                        if old_actual:
                            await conn.execute(
                                "UPDATE documents SET subfolder = 'Previous Visa', updated_at = NOW() WHERE id = $1",
                                old_actual["id"],
                            )
                            logger.info(f"Drive poll: rotated doc {old_actual['id']} to Previous Visa")

            async with db_pool.acquire() as conn:
                doc_id = await conn.fetchval(
                    """INSERT INTO documents (
                        client_id, document_type, document_category, file_name, file_id,
                        status, storage_type, ocr_status, subfolder
                    ) VALUES ($1, $2, $3, $4, $5, 'active', 'google_drive', 'pending', $6)
                    RETURNING id""",
                    client_id,
                    _infer_document_type(file_name, folder_name),
                    doc_category,
                    file_name,
                    file_id,
                    subfolder_value,
                )
```

- [ ] **Step 2: Verify import compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.crm.drive_poll_service import poll_drive_changes; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/services/crm/drive_poll_service.py
git commit -m "feat(poll): detect Actual/Previous Visa subfolder + auto-rotation"
```

---

### Task 6: Visa Expiry Notifier — Enhanced Template

**Files:**

- Modify: `apps/backend-rag/backend/services/compliance/visa_expiry_team_notifier.py:48-68` (SQL), `182` (row HTML)

- [ ] **Step 1: Add current_visa_type to SQL query**

Replace the `_BASE_SQL` at line 54:

```python
_BASE_SQL = """
SELECT
    c.id          AS client_id,
    c.full_name   AS client_name,
    c.email       AS client_email,
    c.phone       AS client_phone,
    c.nationality,
    c.assigned_to,
    $1::text      AS document_type,
    c.{col}       AS expiry_date,
    (c.{col} - CURRENT_DATE)::int AS days_until_expiry,
    c.current_visa_type,
    c.current_visa_sponsor,
    c.passport_expiry_date
FROM clients c
WHERE c.{col} IS NOT NULL
  AND c.{col} BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '60 days'
  AND c.assigned_to IS NOT NULL
  AND c.deleted_at IS NULL
"""
```

- [ ] **Step 2: Update \_build_client_row to show visa type**

Find the `_build_client_row` function (search for `def _build_client_row`). Update the document type cell to include visa type:

```python
def _build_client_row(row: dict[str, Any]) -> str:
    """Build one <tr> for the expiry alert table."""
    days = row.get("days_until_expiry", 999)
    threshold = 7 if days <= 7 else (30 if days <= 30 else 60)
    bg = _ROW_COLOURS.get(threshold, "#FFFFFF")
    label_colour = _LABEL_COLOURS.get(threshold, "#333")

    # Enhanced document type with visa type if available
    doc_type = row.get("document_type", "unknown").upper()
    visa_type = row.get("current_visa_type")
    if visa_type and doc_type in ("VISA", "KITAS"):
        doc_type = f"{doc_type} ({visa_type})"

    sponsor = row.get("current_visa_sponsor", "")
    sponsor_html = f"<br><small style='color:#666;'>Sponsor: {sponsor}</small>" if sponsor else ""

    # Passport cross-check warning
    passport_warning = ""
    passport_expiry = row.get("passport_expiry_date")
    expiry = row.get("expiry_date")
    if passport_expiry and expiry and passport_expiry < expiry:
        passport_warning = (
            f"<br><small style='color:#C62828;'>⚠️ Passaporto scade PRIMA "
            f"({passport_expiry.strftime('%d/%m/%Y')})</small>"
        )

    expiry_fmt = row["expiry_date"].strftime("%d/%m/%Y") if row.get("expiry_date") else "N/A"

    return f"""
    <tr style="background:{bg};">
      <td style="padding:8px;">{row['client_name']}</td>
      <td style="padding:8px;">{doc_type}{sponsor_html}</td>
      <td style="padding:8px;">{expiry_fmt}{passport_warning}</td>
      <td style="padding:8px; color:{label_colour}; font-weight:bold;">{days}g</td>
      <td style="padding:8px;">{row.get('client_phone', '')}</td>
    </tr>"""
```

- [ ] **Step 3: Verify import compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.compliance.visa_expiry_team_notifier import VisaExpiryTeamNotifier; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/compliance/visa_expiry_team_notifier.py
git commit -m "feat(notifier): show visa type + sponsor + passport cross-check in expiry alerts"
```

---

### Task 7: Frontend API Method — uploadDocumentBase64

**Files:**

- Modify: `apps/mouth/src/lib/api/crm/crm.api.ts:554` (after createDocument)

- [ ] **Step 1: Add uploadDocumentBase64 method**

After the `createDocument` method (line 554), add:

```typescript
  /**
   * Upload a document via base64 with optional subfolder hint for visa rotation
   */
  async uploadDocumentBase64(
    clientId: number,
    data: {
      file: string;
      file_name: string;
      document_type: string;
      mime_type?: string;
      notes?: string;
      subfolder_hint?: string;
      document_category?: string;
      expiry_date?: string;
      family_member_id?: number;
    },
  ): Promise<{ success: boolean; document_id?: number; file_url?: string; ocr_triggered?: boolean }> {
    return this.client.request<{
      success: boolean;
      document_id?: number;
      file_url?: string;
      ocr_triggered?: boolean;
    }>(`/api/crm/clients/${clientId}/documents/upload`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
```

- [ ] **Step 2: Commit**

```bash
git add apps/mouth/src/lib/api/crm/crm.api.ts
git commit -m "feat(api): add uploadDocumentBase64 method with subfolder_hint"
```

---

### Task 8: Frontend AddDocumentModal — Drag-and-Drop Upload

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddDocumentModal.tsx` (full rewrite)

- [ ] **Step 1: Rewrite AddDocumentModal with drag-and-drop**

Replace the entire file content:

```tsx
"use client";

import React, { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import { Upload, FileText, X } from "lucide-react";
import { api } from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import type {
  DocumentCategory,
  FamilyMember,
  DocumentCategoryType,
} from "@/lib/api/crm/crm.types";
import { Modal } from "../Modal";

export function AddDocumentModal({
  clientId,
  categories,
  familyMembers,
  clientHasDriveFolder,
  onClose,
  onSave,
  defaultCategory,
  defaultType,
  defaultSubfolderHint,
}: {
  clientId: number;
  categories: DocumentCategory[];
  familyMembers: FamilyMember[];
  clientHasDriveFolder?: boolean;
  onClose: () => void;
  onSave: () => void;
  defaultCategory?: DocumentCategoryType;
  defaultType?: string;
  defaultSubfolderHint?: string;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [formData, setFormData] = useState({
    file_name: "",
    document_type: defaultType || "",
    document_category: (defaultCategory || "other") as DocumentCategoryType,
    expiry_date: "",
    google_drive_file_url: "",
    family_member_id: "",
  });

  const allowedTypes = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
  ];
  const maxSize = 10 * 1024 * 1024; // 10MB

  const handleFileSelect = useCallback(
    (file: File) => {
      if (!allowedTypes.includes(file.type)) {
        toast.error("Invalid file type", {
          description: "Please upload JPG, PNG, or PDF",
        });
        return;
      }
      if (file.size > maxSize) {
        toast.error("File too large", {
          description: "Maximum file size is 10MB",
        });
        return;
      }
      setSelectedFile(file);
      if (!formData.file_name) {
        setFormData((prev) => ({ ...prev, file_name: file.name }));
      }
    },
    [formData.file_name],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) {
      toast.error("Document name is required");
      return;
    }
    if (!selectedFile && !formData.google_drive_file_url) {
      toast.error("Please upload a file or provide a Drive link");
      return;
    }

    setIsSaving(true);
    try {
      if (selectedFile) {
        // Base64 upload path
        const base64 = await fileToBase64(selectedFile);
        const response = await api.crm.uploadDocumentBase64(clientId, {
          file: base64,
          file_name: formData.file_name,
          document_type: formData.document_type || "document",
          mime_type: selectedFile.type,
          document_category: formData.document_category,
          subfolder_hint: defaultSubfolderHint,
          expiry_date: formData.expiry_date || undefined,
          family_member_id: formData.family_member_id
            ? Number(formData.family_member_id)
            : undefined,
        });
        if (response.success) {
          toast.success(
            response.ocr_triggered
              ? "Document uploaded — OCR in progress..."
              : "Document uploaded",
          );
        }
      } else {
        // Drive URL fallback path (existing behavior)
        await api.crm.createDocument(clientId, {
          ...formData,
          family_member_id: formData.family_member_id
            ? Number(formData.family_member_id)
            : undefined,
        });
        toast.success("Document added");
      }
      onSave();
      onClose();
    } catch (err) {
      toast.error("Failed to upload", {
        description: (err as Error).message,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    "w-full px-4 py-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50";

  return (
    <Modal
      title="Add Document"
      aria-label="Add Document"
      onClose={onClose}
      isSaving={isSaving}
      onSave={handleSubmit}
    >
      {/* Drag-and-drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`mb-4 border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-[var(--bz-accent)] bg-[var(--bz-accent)]/10"
            : selectedFile
              ? "border-green-500/50 bg-green-500/5"
              : "border-[var(--bz-border)] hover:border-[var(--bz-accent)]/50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelect(file);
          }}
          className="hidden"
        />
        {selectedFile ? (
          <div className="flex items-center justify-center gap-3">
            <FileText className="w-5 h-5 text-green-400" />
            <span className="text-sm text-[var(--bz-text-1)]">
              {selectedFile.name}
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedFile(null);
              }}
              className="p-1 rounded hover:bg-[var(--bz-surface-2)]"
            >
              <X className="w-4 h-4 text-[var(--bz-text-3)]" />
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <Upload className="w-8 h-8 mx-auto text-[var(--bz-text-3)]" />
            <p className="text-sm text-[var(--bz-text-2)]">
              Drop file here or click to browse
            </p>
            <p className="text-xs text-[var(--bz-text-3)]">
              PDF, JPG, PNG — max 10MB
            </p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">
            Document Name *
          </label>
          <input
            type="text"
            value={formData.file_name}
            onChange={(e) =>
              setFormData({ ...formData, file_name: e.target.value })
            }
            className={inputClass}
            placeholder="e.g. KITAS Eduardo 2026"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Category</label>
          <select
            value={formData.document_category}
            onChange={(e) =>
              setFormData({
                ...formData,
                document_category: e.target.value as DocumentCategoryType,
              })
            }
            className={inputClass}
          >
            <option value="immigration">Immigration</option>
            <option value="pma">Company (PMA)</option>
            <option value="tax">Tax</option>
            <option value="personal">Personal</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Type</label>
          <input
            type="text"
            value={formData.document_type}
            onChange={(e) =>
              setFormData({ ...formData, document_type: e.target.value })
            }
            className={inputClass}
            placeholder="passport, kitas, etc"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Expiry Date
          </label>
          <input
            type="date"
            value={formData.expiry_date}
            onChange={(e) =>
              setFormData({ ...formData, expiry_date: e.target.value })
            }
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Belongs To</label>
          <select
            value={formData.family_member_id}
            onChange={(e) =>
              setFormData({ ...formData, family_member_id: e.target.value })
            }
            className={inputClass}
          >
            <option value="">Main Client</option>
            {familyMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name} ({m.relationship})
              </option>
            ))}
          </select>
        </div>

        {/* Drive URL fallback — collapsed by default */}
        {!selectedFile && (
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-1.5">
              Or paste Google Drive Link
            </label>
            <input
              type="url"
              value={formData.google_drive_file_url}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  google_drive_file_url: e.target.value,
                })
              }
              className={inputClass}
              placeholder="https://drive.google.com/..."
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
```

- [ ] **Step 2: Update all callers to pass new props**

Search for `<AddDocumentModal` in the codebase. The main caller is in `page.tsx`. The new optional props (`defaultCategory`, `defaultType`, `defaultSubfolderHint`) have defaults so existing callers don't break. But for visa-specific callers (VisaCard upload button), pass the pre-fill:

In `VisaCard.tsx`, the upload is already handled inline (lines 157-199 with `handleFileUpload`). Add `subfolder_hint` to the upload call. Find line 184:

```typescript
      const response = (await api.post(`/api/crm/clients/${client.id}/documents/upload`, {
        file: base64,
        file_name: file.name,
        document_type: 'visa',
        mime_type: file.type,
      })) as {
```

Replace with:

```typescript
      const response = (await api.post(`/api/crm/clients/${client.id}/documents/upload`, {
        file: base64,
        file_name: file.name,
        document_type: 'visa',
        mime_type: file.type,
        subfolder_hint: 'Actual Visa',
        document_category: 'immigration',
      })) as {
```

- [ ] **Step 3: Commit**

```bash
git add apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddDocumentModal.tsx
git add apps/mouth/src/app/(workspace)/clients/[id]/components/VisaCard.tsx
git add apps/mouth/src/lib/api/crm/crm.api.ts
git commit -m "feat(frontend): drag-and-drop upload + subfolder_hint for visa rotation"
```

---

### Task 9: Integration Test + Deploy

- [ ] **Step 1: Verify backend imports chain**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('Import chain OK')"
```

- [ ] **Step 2: Run core backend tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no 2>/dev/null && echo "Core tests OK"
```

- [ ] **Step 3: Commit all remaining changes and push**

```bash
git status
# Review all changes, then:
git push origin main
```

- [ ] **Step 4: Deploy backend to Fly.io**

```bash
cd apps/backend-rag
fly deploy --strategy rolling
```

- [ ] **Step 5: Verify deployment health**

```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool
```

- [ ] **Step 6: Create Eduardo's subfolders**

Use MCP tool `create_client_drive_folder` for client 11387 to create the full folder structure including the new Actual Visa / Previous Visa subfolders. Or call the endpoint directly:

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/crm/drive-folders/11387 \
  -H "Authorization: Bearer <JWT>"
```

---

# 8 Global CRM Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 8 systemic CRM issues affecting all 5000+ clients: capital display, shareholder count, document vault, categorizer keywords, content hash dedup, folder hint, auto-OCR company profile, and NIB-only company dedup.

**Architecture:** 3 frontend fixes (React components reading custom_fields fallback + cross-table vault search), 4 backend fixes (categorizer keywords, dedup hash, OCR dispatcher, company profile OCR), 1 backend fix for company dedup on client create. One small migration for content_hash column.

**Tech Stack:** Next.js/React (frontend), Python/FastAPI (backend), asyncpg, Google Drive API, Gemini Vision OCR

**Spec:** `docs/superpowers/specs/2026-04-01-crm-global-fixes-design.md`

---

## File Structure

| File                                               | Action | Responsibility                                                        |
| -------------------------------------------------- | ------ | --------------------------------------------------------------------- |
| `backend/migrations/migration_074_content_hash.py` | Create | Add `documents.content_hash` column + index                           |
| `backend/services/crm/document_categorizer.py`     | Modify | Fix keywords: add "profil perseroan" (missing i), expand pma keywords |
| `backend/services/crm/drive_poll_service.py`       | Modify | Content hash dedup + folder hint for "other" category                 |
| `backend/app/routers/crm_enhanced.py`              | Modify | Add `_auto_ocr_company_profile()` + fix dispatcher routing            |
| `backend/app/routers/crm_enhanced_documents.py`    | Modify | Compute content_hash on base64 upload                                 |
| `backend/app/routers/crm_clients.py`               | Modify | NIB-only company dedup on create                                      |
| `mouth/.../company/KeyNumbersColumn.tsx`           | Modify | Capital fallback from custom_fields                                   |
| `mouth/.../CompanyTab.tsx`                         | Modify | Shareholder count fallback + pass client docs to vault                |
| `mouth/.../company/CompanyDocUpload.tsx`           | Modify | Cross-table document search + new vault slots                         |

---

### Task 1: Migration 074 — content_hash column

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_074_content_hash.py`

- [ ] **Step 1: Create migration file**

```python
"""Migration 074: Add content_hash to documents for dedup."""
import asyncpg
import logging

logger = logging.getLogger(__name__)

MIGRATION_ID = "074"
DESCRIPTION = "Add content_hash column to documents for content-based deduplication"


async def up(conn: asyncpg.Connection) -> None:
    await conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32);")
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_documents_content_hash
        ON documents(client_id, content_hash)
        WHERE content_hash IS NOT NULL;
    """)
    logger.info("Migration 074 applied: content_hash column + index")


async def down(conn: asyncpg.Connection) -> None:
    await conn.execute("DROP INDEX IF EXISTS idx_documents_content_hash;")
    await conn.execute("ALTER TABLE documents DROP COLUMN IF EXISTS content_hash;")
    logger.info("Migration 074 rolled back")
```

- [ ] **Step 2: Run migration on Fly DB**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def migrate():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag')
    from backend.migrations.migration_074_content_hash import up
    await up(conn)
    await conn.close()
    print('Migration 074 applied')

asyncio.run(migrate())
"
```

- [ ] **Step 3: Verify**

```bash
PYTHONPATH=. python3 -c "
import asyncio, asyncpg

async def verify():
    conn = await asyncpg.connect('postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag')
    row = await conn.fetchrow(\"SELECT column_name FROM information_schema.columns WHERE table_name='documents' AND column_name='content_hash'\")
    assert row is not None, 'content_hash column missing'
    print('Verified: content_hash column exists')
    await conn.close()

asyncio.run(verify())
"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_074_content_hash.py
git commit -m "feat(migration): add documents.content_hash for dedup (074)"
```

---

### Task 2: Fix 4 — Categorizer Keywords Expanded

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/document_categorizer.py`

- [ ] **Step 1: Fix the "profile_perseroan" keywords**

In `document_categorizer.py`, find the `"profile_perseroan"` keywords block (around line 131). The current list has `"profile perseroan"` (with 'i') but is MISSING `"profil perseroan"` (without 'i' — the actual Indonesian spelling).

Replace the `"profile_perseroan"` entry:

```python
        "profile_perseroan": [
            "profil perseroan",
            "profile perseroan",
            "company profile",
            "profil perusahaan",
            "profile perusahaan",
            "company presentation",
            "profil pt",
            "profil perseroan baru",
        ],
```

- [ ] **Step 2: Add new PMA document types for compliance**

After the `"legalisation"` entry (around line 141), add new document types required for PT PMA compliance (per NLM NB-2):

```python
        "wlkp": ["wlkp", "wajib lapor", "lapor ketenagakerjaan"],
        "bpjs": ["bpjs", "bpjs ketenagakerjaan", "bpjs kesehatan"],
        "organogram": ["bagan organisasi", "organogram", "organization chart", "org chart", "struktur organisasi"],
        "rekening_koran": ["rekening koran perusahaan", "bank statement company", "rekening koran pt"],
```

- [ ] **Step 3: Verify import compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.crm.document_categorizer import auto_categorize_document, CATEGORY_TO_FOLDER; print('OK')"
```

- [ ] **Step 4: Quick test the fix**

```bash
PYTHONPATH=. python3 -c "
from backend.services.crm.document_categorizer import auto_categorize_document
# This was the bug — 'Profil Perseroan Baru.pdf' should be pma, not other
result = auto_categorize_document('Profil Perseroan Baru.pdf')
assert result['document_category'] == 'pma', f'Expected pma, got {result[\"document_category\"]}'
assert result['document_type'] == 'Profile Perseroan', f'Got type: {result[\"document_type\"]}'

# Test other new keywords
assert auto_categorize_document('WLKP_PT_Studio.pdf')['document_category'] == 'pma'
assert auto_categorize_document('BPJS_ketenagakerjaan.pdf')['document_category'] == 'pma'
assert auto_categorize_document('Bagan_Organisasi.pdf')['document_category'] == 'pma'
print('All categorizer tests passed')
"
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/crm/document_categorizer.py
git commit -m "fix(categorizer): add missing 'profil perseroan' keyword + WLKP/BPJS/organogram"
```

---

### Task 3: Fix 5 — Content Hash Dedup in Poll + Upload

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/drive_poll_service.py`
- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced_documents.py`

- [ ] **Step 1: Add content hash dedup in drive_poll_service.py**

Find the dedup block (around line 287-295). After the existing `file_id` check, add a content hash check. Also compute hash when creating the document.

After the existing block:

```python
            if existing:
                skipped += 1
                continue
```

Add:

```python
            # Level 2 dedup: content hash (same file content uploaded with different file_id)
            try:
                file_content = await drive_service.download_file(file_id)
                import hashlib
                content_hash = hashlib.md5(file_content).hexdigest()

                hash_dup = await conn.fetchval(
                    """SELECT id FROM documents
                       WHERE client_id = $1 AND content_hash = $2
                         AND created_at > NOW() - INTERVAL '30 days'""",
                    client_id, content_hash,
                )
                if hash_dup:
                    logger.info(f"Drive poll: skipped duplicate content hash for {file_name} (matches doc {hash_dup})")
                    skipped += 1
                    continue
            except Exception as e:
                content_hash = None
                logger.debug(f"Could not compute content hash for {file_name}: {e}")
```

Then update the INSERT to include `content_hash` — find the INSERT statement (should be around line 329-342 now) and add the column:

```python
                doc_id = await conn.fetchval(
                    """INSERT INTO documents (
                        client_id, document_type, document_category, file_name, file_id,
                        status, storage_type, ocr_status, subfolder, content_hash
                    ) VALUES ($1, $2, $3, $4, $5, 'active', 'google_drive', 'pending', $6, $7)
                    RETURNING id""",
                    client_id,
                    _infer_document_type(file_name, folder_name),
                    doc_category,
                    file_name,
                    file_id,
                    subfolder_value,
                    content_hash,
                )
```

Also add `download_file` method check — it may need to be added to `ServiceAccountDriveService`. Check if it exists; if not, the hash computation should use `get_media`:

```python
# In drive_poll_service.py, near the top with other imports:
import hashlib
```

- [ ] **Step 2: Add content hash in upload endpoint**

In `crm_enhanced_documents.py`, find `upload_document_base64()`. After `file_content = base64.b64decode(data.file)` (around line 511), compute the hash:

```python
        try:
            file_content = base64.b64decode(data.file)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 file content")

        # Compute content hash for dedup
        import hashlib
        content_hash = hashlib.md5(file_content).hexdigest()
```

Then update the INSERT to include `content_hash` — find the INSERT and add `, content_hash` column with the computed value.

- [ ] **Step 3: Verify both compile**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.crm.drive_poll_service import poll_drive_changes; print('Poll OK')"
python -c "from backend.app.routers.crm_enhanced_documents import router; print('Upload OK')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/crm/drive_poll_service.py apps/backend-rag/backend/app/routers/crm_enhanced_documents.py
git commit -m "feat(dedup): content hash dedup in poll service + upload endpoint"
```

---

### Task 4: Fix 6 — Folder Hint (Not Force) for Immigration

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/drive_poll_service.py`
- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced.py`

- [ ] **Step 1: Add folder hint in poll service**

In `drive_poll_service.py`, find where `doc_category` is set from auto-categorizer (around line 302-303). After the categorizer result, add a folder hint:

```python
            # Create document record with auto-categorization
            cat_result = auto_categorize_document(file_name)
            doc_category = cat_result["document_category"]

            # Folder hint: if categorizer returns "other" but file is in immigration folder,
            # re-categorize as immigration (conservative — only for "other", not for specific categories)
            if doc_category == "other" and isinstance(folder_name, str):
                folder_lower = folder_name.lower()
                if folder_lower in ("01_immigration", "actual visa", "previous visa") or "immigration" in folder_lower:
                    doc_category = "immigration"
                    logger.info(f"Drive poll: folder hint upgraded '{file_name}' from 'other' to 'immigration'")
```

- [ ] **Step 2: Fix OCR dispatcher — remove overly aggressive 01\_ catch-all**

In `crm_enhanced.py`, find `_dispatch_ocr_by_folder`. The visa routing (around line 660-684) has `or folder_lower.startswith("01_")` which triggers visa OCR for ALL files in `01_Immigration/`, even civil/corporate docs.

Find this line (around 680):

```python
  if any(kw in fn_lower for kw in visa_keywords) or folder_lower.startswith("01_"):
```

Replace with:

```python
  if any(kw in fn_lower for kw in visa_keywords):
```

This way only files with visa-related filenames get visa OCR, not every file in the immigration folder.

- [ ] **Step 3: Verify both compile**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.crm.drive_poll_service import poll_drive_changes; print('Poll OK')"
python -c "from backend.app.routers.crm_enhanced import router; print('Enhanced OK')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/crm/drive_poll_service.py apps/backend-rag/backend/app/routers/crm_enhanced.py
git commit -m "fix(categorizer): folder hint for immigration (not force) + remove 01_ OCR catch-all"
```

---

### Task 5: Fix 7 — Auto-OCR Company Profile

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced.py`

- [ ] **Step 1: Add \_auto_ocr_company_profile function**

In `crm_enhanced.py`, after `_auto_ocr_npwp` function (around line 530), add:

```python
async def _auto_ocr_company_profile(db_pool: Any, client_id: int, file_id: str, doc_id: int | None = None) -> dict:
    """
    OCR on Profil Perseroan / Company Profile document.
    Extracts: shareholders, capital, akta, SK, notaris, address, KBLI.
    Saves to companies.custom_fields via client → company link.
    """
    try:
        image_data, mime_type = await _download_drive_file(file_id)

        ocr_prompt = (
            "Extract from this Indonesian company profile (Profil Perseroan) document. "
            "Return JSON with these fields: "
            "company_name, authorized_capital (number in IDR), paid_up_capital (number in IDR), "
            "shareholders (array of objects with: name, passport, nationality, role, shares, value), "
            "akta_no (string), akta_date (YYYY-MM-DD), "
            "sk_no (string, AHU number), sk_date (YYYY-MM-DD), "
            "notaris (string, full name with title), notaris_kedudukan (string, city), "
            "registered_address (string, full address), "
            "company_status (TERTUTUP/TERBUKA), jangka_waktu (string), "
            "kbli_codes (array of strings if present), risk_status (string if present), "
            "share_price (number per share), total_shares (number), "
            "confidence (0-1)."
        )

        response_text = await _gemini_ocr(image_data, mime_type, ocr_prompt)
        logger.info(f"Auto OCR company profile for client {client_id}: {response_text[:200]}...")

        extracted = extract_json_from_llm_response(response_text)
        if not extracted:
            logger.error(f"Auto OCR company profile JSON parsing failed for client {client_id}")
            return {"success": False, "error": "Could not parse OCR response"}

        # Build custom_fields update
        custom_fields = {}
        for key in [
            "authorized_capital", "paid_up_capital", "shareholders",
            "akta_no", "akta_date", "sk_no", "sk_date",
            "notaris", "notaris_kedudukan", "company_status",
            "jangka_waktu", "kbli_codes", "risk_status",
            "share_price", "total_shares",
        ]:
            if extracted.get(key) is not None:
                val = extracted[key]
                # Convert shareholders list to JSON string if it's a list
                if isinstance(val, list):
                    import json as json_module
                    custom_fields[key] = json_module.dumps(val)
                else:
                    custom_fields[key] = str(val)

        async with db_pool.acquire() as conn:
            # Update document OCR status
            if doc_id:
                await conn.execute(
                    """UPDATE documents SET ocr_status = 'completed', ocr_completed_at = NOW(),
                       ocr_extracted_data = $1, updated_at = NOW() WHERE id = $2""",
                    to_jsonb({"extracted_at": datetime.now(timezone.utc).isoformat(), "raw_response": extracted}),
                    doc_id,
                )

            # Find company linked to this client
            company_id = await conn.fetchval(
                """SELECT c.id FROM companies c
                   JOIN client_company_links ccl ON ccl.company_id = c.id
                   WHERE ccl.client_id = $1 LIMIT 1""",
                client_id,
            )

            if company_id and custom_fields:
                # Merge custom_fields (preserve existing, add new)
                existing_cf = await conn.fetchval(
                    "SELECT custom_fields FROM companies WHERE id = $1", company_id,
                )
                import json as json_module
                merged = json_module.loads(existing_cf) if existing_cf and existing_cf != '{}' else {}
                merged.update(custom_fields)

                # Also update dedicated columns if available
                update_parts = ["custom_fields = $1", "updated_at = NOW()"]
                params: list[Any] = [json_module.dumps(merged)]
                idx = 2

                if extracted.get("registered_address"):
                    update_parts.append(f"registered_address = ${idx}")
                    params.append(str(extracted["registered_address"])[:500])
                    idx += 1

                if extracted.get("akta_no"):
                    update_parts.append(f"akta_pendirian_no = ${idx}")
                    params.append(str(extracted["akta_no"])[:100])
                    idx += 1

                if extracted.get("sk_no"):
                    update_parts.append(f"sk_menhumkam_no = ${idx}")
                    params.append(str(extracted["sk_no"])[:100])
                    idx += 1

                params.append(company_id)
                await conn.execute(
                    f"UPDATE companies SET {', '.join(update_parts)} WHERE id = ${idx}",
                    *params,
                )
                logger.info(f"Auto OCR company profile: updated company {company_id} with {len(custom_fields)} fields")

        return {"success": True, "extracted": extracted}

    except Exception as e:
        logger.error(f"Auto OCR company profile failed for client {client_id}: {e}")
        return {"success": False, "error": str(e)}
```

- [ ] **Step 2: Update OCR dispatcher to route company profile docs**

In `_dispatch_ocr_by_folder`, after the NPWP handler block (around line 700), add:

```python
    # Company Profile / Profil Perseroan
    profile_keywords = ["company profile", "profil perseroan", "profil pt", "profil perusahaan", "profile perseroan"]
    if any(kw in fn_lower for kw in profile_keywords) or doc_type_lower in ("company_profile", "profile_perseroan"):
        logger.info(f"OCR dispatch: company_profile for client {client_id}")
        return await _auto_ocr_company_profile(db_pool, client_id, file_id, doc_id)
```

Where `doc_type_lower` needs to be defined near the top of the function. Find where `fn_lower` and `folder_lower` are defined and add:

```python
    doc_type_lower = (document_type or "").lower().replace("_", " ") if document_type else ""
```

Note: check the function signature — it may or may not have a `document_type` parameter. If not, use `fn_lower` only.

- [ ] **Step 3: Verify compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.crm_enhanced import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_enhanced.py
git commit -m "feat(ocr): auto-OCR company profile extracts capital, shareholders, akta, KBLI"
```

---

### Task 6: Fix 8 — NIB-Only Company Dedup on Client Create

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py`

- [ ] **Step 1: Add NIB dedup in company creation**

In `crm_clients.py`, find the company_data block (around line 312-318):

```python
        company_data = None
        if client.company_name:
            company_data = {
                "company_name": client.company_name,
                "status": "active",
                "kbli_code": client_data.pop("kbli_code", None),
            }
```

Replace with:

```python
        company_data = None
        existing_company_id = None
        if client.company_name:
            # NIB-only dedup: if client provides NIB that matches existing company, link instead of creating
            nib = client_data.get("nib") or client_data.pop("nib", None)
            if nib:
                async with db_pool.acquire() as conn:
                    existing_company_id = await conn.fetchval(
                        "SELECT id FROM companies WHERE nib = $1 AND status = 'active' LIMIT 1",
                        nib.strip(),
                    )
                    if existing_company_id:
                        logger.info(f"Company dedup: found existing company {existing_company_id} by NIB {nib}")

            if not existing_company_id:
                company_data = {
                    "company_name": client.company_name,
                    "status": "active",
                    "kbli_code": client_data.pop("kbli_code", None),
                }
```

Then find where `created_record` is used and the company link is established. If the client_service handles company creation internally, we need to pass `existing_company_id`. Find the call to `client_service.create_client` (around line 321):

```python
        created_record = await client_service.create_client(
            client_data=client_data,
            company_data=company_data,
            existing_company_id=existing_company_id,
        )
```

The `create_client` method in `client_service.py` will need to accept `existing_company_id` and link instead of create when provided. Check the service method signature and update it to:

```python
async def create_client(
    self,
    client_data: dict,
    company_data: dict | None = None,
    existing_company_id: int | None = None,
) -> asyncpg.Record:
```

In the service, if `existing_company_id` is provided, skip company creation and just create the link.

- [ ] **Step 2: Verify compiles**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.routers.crm_clients import router; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/app/routers/crm_clients.py apps/backend-rag/backend/services/crm/client_service.py
git commit -m "feat(crm): NIB-only company dedup on client create (never merge by name)"
```

---

### Task 7: Fix 1+2 — Frontend Capital + Shareholder Fallback

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/company/KeyNumbersColumn.tsx`
- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx`

- [ ] **Step 1: Add capital fallback in KeyNumbersColumn.tsx**

Find the capital display block (around line 42-52). After `const fullCapital = formatCapitalFull(sharesCount, shareNominalValue);`, add a fallback:

```typescript
const fullCapital = formatCapitalFull(sharesCount, shareNominalValue);
// Fallback: read from custom_fields if computed capital is null
const capitalDisplay = fullCapital || (() => {
  try {
    const cf = typeof customFields === 'string' ? JSON.parse(customFields) : customFields;
    const authCap = cf?.authorized_capital;
    if (authCap) {
      const num = Number(authCap);
      if (!isNaN(num)) return `Rp ${num.toLocaleString('id-ID')}`;
    }
  } catch {}
  return null;
})();

if (capitalDisplay) {
  items.push({
    label: "Authorized Capital",
    value: capitalDisplay,
    sub: "IDR",
    // ... rest unchanged
```

Make sure `customFields` is passed as a prop. Check the component props — if it doesn't receive `customFields`, add it to the props interface and pass it from `CompanyTab.tsx`.

- [ ] **Step 2: Add shareholder count fallback in CompanyTab.tsx**

Find `shareholderCount={associates.length}` (around line 402). Replace with:

```typescript
shareholderCount={(() => {
  // Try custom_fields.shareholders first (OCR-extracted, authoritative)
  try {
    const cf = typeof companyData?.custom_fields === 'string'
      ? JSON.parse(companyData.custom_fields)
      : companyData?.custom_fields;
    const sh = cf?.shareholders;
    if (sh) {
      const parsed = typeof sh === 'string' ? JSON.parse(sh) : sh;
      if (Array.isArray(parsed) && parsed.length > 0) return parsed.length;
    }
  } catch {}
  // Fallback to linked associates
  return associates.length;
})()}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/nuzantara/Desktop/nuzantara && npx tsc --noEmit --project apps/mouth/tsconfig.json 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/(workspace)/clients/[id]/components/company/KeyNumbersColumn.tsx apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx
git commit -m "fix(frontend): capital + shareholder count fallback from custom_fields"
```

---

### Task 8: Fix 3 — Document Vault Cross-Table + New Slots

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx`
- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/company/CompanyDocUpload.tsx`

- [ ] **Step 1: Expand vault slot definitions in CompanyTab.tsx**

Find the vault slots array (around line 487-509). Replace with expanded list:

```typescript
{[
  { docType: "akta_pendirian", label: "Akta Pendirian", hint: "PDF/JPG" },
  { docType: "sk_decree", label: "SK Kemenkumham", hint: "PDF/JPG" },
  { docType: "npwp", label: "NPWP Perusahaan", hint: "PDF/JPG" },
  { docType: "nib", label: "NIB", hint: "PDF/JPG" },
  { docType: "company_profile", label: "Company Profile", hint: "PDF" },
  { docType: "wlkp", label: "WLKP", hint: "PDF" },
  { docType: "bpjs", label: "BPJS Ketenagakerjaan", hint: "PDF" },
  { docType: "organogram", label: "Bagan Organisasi", hint: "PDF/JPG" },
  { docType: "rekening_koran", label: "Rekening Koran", hint: "PDF" },
].map((item) => {
```

- [ ] **Step 2: Update vault matching to search client docs too**

In the same map block, update the `existing` search to also check client documents:

```typescript
].map((item) => {
  // Search company docs first, then client docs with pma category
  const typeVariants = [item.docType, item.docType.replace(/_/g, ' '), item.docType.replace(/_/g, '')];
  const existing = companyDocs.find(
    (d) => typeVariants.includes(d.document_type?.toLowerCase())
  ) || documents?.filter(d => d.document_category === 'pma').find(
    (d) => typeVariants.includes(d.document_type?.toLowerCase())
  ) || null;
```

Make sure `documents` (client-level) is available in this scope. It should be passed from the parent page component. Check if `CompanyTab` receives `documents` as a prop — if not, add it.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/nuzantara/Desktop/nuzantara && npx tsc --noEmit --project apps/mouth/tsconfig.json 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx apps/mouth/src/app/(workspace)/clients/[id]/components/company/CompanyDocUpload.tsx
git commit -m "fix(vault): cross-table search + 4 new compliance slots (WLKP, BPJS, organogram, rekening)"
```

---

### Task 9: Integration Test + Deploy

- [ ] **Step 1: Verify backend import chain**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('Import chain OK')"
```

- [ ] **Step 2: Run core tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no && echo "Core tests OK"
```

- [ ] **Step 3: Push and deploy**

```bash
cd /Users/nuzantara/Desktop/nuzantara && git push origin main
cd apps/backend-rag && fly deploy --strategy rolling
```

- [ ] **Step 4: Verify health**

```bash
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool
```

- [ ] **Step 5: Test in browser — Eduardo Company tab**

Navigate to `https://kita.balizero.com/clients/11387?tab=company` and verify:

- Authorized Capital shows Rp value (not dash)
- Shareholder count shows 3 (from custom_fields)
- Document Vault shows existing docs (not all "Upload")
- New vault slots visible (WLKP, BPJS, etc.)

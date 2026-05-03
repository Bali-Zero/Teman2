# 8 Global CRM Fixes — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Author:** Claude Opus 4.6
**NLM Grounding:** NB-2 Immigration & Visa (validated all 8 fixes, 3 modified per feedback)

## Fix 1: Authorized Capital Fallback from custom_fields

**Problem:** Company tab shows red dash for Authorized Capital. Value exists in `companies.custom_fields.authorized_capital` but frontend computes from `shares_count × share_nominal_value` (both NULL for most companies).

**Root Cause:** `KeyNumbersColumn.tsx` calls `formatCapitalFull(sharesCount, shareNominalValue)` which returns null when either param is null.

**Fix:** In `KeyNumbersColumn.tsx`, add fallback: if computed capital is null, read `company.custom_fields.authorized_capital` and format as Rp currency.

**NLM Note:** Critical for investor visa compliance — E28A requires Rp 10B minimum, KITAP-INV requires Rp 15B.

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/company/KeyNumbersColumn.tsx`

## Fix 2: Shareholder Count from custom_fields

**Problem:** Company tab shows "1 shareholder" because it counts `associates` array from `client_company_links`. If only 1 client linked to company but Akta has 3 shareholders, count is wrong.

**Root Cause:** `CompanyTab.tsx:402` uses `shareholderCount={associates.length}`. Associates come from linked clients, not from OCR-extracted data.

**Fix:** In `CompanyTab.tsx`, if `company.custom_fields.shareholders` is a JSON string containing an array, use `JSON.parse(shareholders).length` as count. Fallback to `associates.length`.

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx`

## Fix 3: Document Vault Searches Client Documents Too

**Problem:** Document Vault shows "Upload" on all slots even when documents exist. Vault searches `company_documents` by exact `document_type` match but docs are in `documents` table (client-level).

**Root Cause:** `CompanyDocUpload.tsx:511` does `companyDocs.find(d => d.document_type === item.docType)`. If docs are in client `documents` table with `document_category='pma'`, vault doesn't find them.

**Fix:** Pass both `companyDocs` AND client `documents` filtered by `document_category='pma'` to the vault component. Search across both arrays with normalized type matching.

**Additional vault slots** (per NLM NB-2 guidance for PT PMA compliance):

- Existing: Akta Pendirian, SK Kemenkumham, NPWP Perusahaan, NIB, Company Profile
- Add: WLKP, BPJS Ketenagakerjaan, Bagan Organisasi (Organogram), Rekening Koran

**Files:**

- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyDocUpload.tsx`
- Modify: `apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx` (pass client docs)

## Fix 4: Categorizer Keywords Expanded for PMA

**Problem:** "Profil Perseroan Baru.pdf" auto-categorized as "other" instead of "pma".

**Root Cause:** Keywords in `document_categorizer.py` include "profil perseroan" but the filename after normalization may not match exactly. Need broader coverage.

**Fix:** Add keywords to pma/company_profile category:

- `"profil pt"`, `"company profile"`, `"profil perusahaan"`, `"profile perusahaan"`, `"profil perseroan baru"`, `"profil perseroan"`
- Also add to pma category: `"wlkp"`, `"bpjs"`, `"bagan organisasi"`, `"organogram"`, `"rekening koran perusahaan"`

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/document_categorizer.py`

## Fix 5: Dedup Level 2 by Content Hash (NOT Filename)

**Problem:** DrivePollService deduplicates only by `file_id`. 6 uploads of same PDF with different file_ids create 6 records.

**NLM Warning:** Filename-based dedup is DANGEROUS — legitimate files like "paspor.pdf", "rekening koran.pdf" may be uploaded multiple times for different visa phases (RPTKA, e-Visa, KITAS activation).

**Fix:** After `file_id` check passes, compute MD5 hash of file content. If `(client_id, content_hash)` already exists in documents within 30 days, skip as duplicate.

**New column:** `documents.content_hash` VARCHAR(32) — MD5 hex digest. Populated on upload and during poll.

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/drive_poll_service.py`
- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced_documents.py` (compute hash on upload)
- Migration: add `documents.content_hash` column

## Fix 6: Immigration Folder as Category Hint (NOT Force)

**Problem:** Files in `01_Immigration/` should be categorized as immigration, but currently auto-categorizer may assign "other".

**NLM Warning:** NOT safe to force `immigration` — visa applications require civil documents (Akta Perkawinan for E31), corporate docs (NIB, BPJS for E23), and financial docs (Rekening Koran). Forcing immigration tag misclassifies these.

**Fix:** Use folder name as a HINT to boost auto-categorizer confidence, not as override. If auto-categorizer returns "other" AND file is in `01_Immigration/`, re-run with `immigration` bias. But if categorizer returns a specific category (pma, tax, personal), keep it.

**Files:**

- Modify: `apps/backend-rag/backend/services/crm/drive_poll_service.py`

## Fix 7: Auto-OCR Company Profile (Profil Perseroan)

**Problem:** When a Profil Perseroan PDF is uploaded/detected, no OCR extracts company data automatically. Currently only passport, visa, NIB, NPWP have auto-OCR.

**Fix:** Add `_auto_ocr_company_profile()` function. Extract:

- `authorized_capital` (Modal Dasar)
- `paid_up_capital` (Modal Ditempatkan/Disetor)
- `shareholders` (array: name, passport, nationality, role, shares, value, address)
- `akta_no` and `akta_date`
- `sk_no` (SK Kemenkumham) and `sk_date`
- `notaris` name and kedudukan
- `registered_address`
- `company_status` (TERTUTUP/TERBUKA)
- `jangka_waktu` (TIDAK TERBATAS / specific date)
- `kbli_codes` (array of KBLI codes if present)
- `risk_status` (status risiko usaha if present)

Save to `companies.custom_fields` JSON. Update `_dispatch_ocr_by_folder()` to trigger for "company_profile" or "profil" document types.

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced.py` (add `_auto_ocr_company_profile()`)
- Modify: `apps/backend-rag/backend/app/routers/crm_enhanced_documents.py` (update OCR dispatcher)

## Fix 8: Company Dedup by NIB Only on Client Create

**Problem:** Creating a client with a company name that already exists creates a duplicate company record.

**NLM Warning:** NEVER merge by company name (ILIKE). The 2026 One Sponsor Policy (SE 3/836) requires exact distinction between affiliated companies. PT A and PT B owned by same holding are LEGALLY DIFFERENT sponsors. Auto-merging by name would obscure this distinction and cause RPTKA rejections.

**Fix:** On client creation, when `company_name` is provided with NIB:

1. Search `companies` WHERE `nib = $1` (exact match, unique identifier)
2. If found → link client to existing company instead of creating new
3. If NOT found → create new company as usual
4. NEVER match by name alone

**Files:**

- Modify: `apps/backend-rag/backend/app/routers/crm_clients.py` (company creation block)
- Modify: `apps/backend-rag/backend/services/crm/client_service.py` (if company logic lives here)

## Summary

| Fix                        | Type                | Priority | Risk                           |
| -------------------------- | ------------------- | -------- | ------------------------------ |
| 1. Capital fallback        | Frontend            | HIGH     | Low                            |
| 2. Shareholder count       | Frontend            | HIGH     | Low                            |
| 3. Vault cross-table       | Frontend            | HIGH     | Medium (type normalization)    |
| 4. Categorizer keywords    | Backend             | MEDIUM   | Low                            |
| 5. Content hash dedup      | Backend + Migration | MEDIUM   | Low (hash is safe)             |
| 6. Folder hint (not force) | Backend             | LOW      | Low (conservative approach)    |
| 7. OCR Company Profile     | Backend             | HIGH     | Medium (Gemini prompt quality) |
| 8. NIB-only company dedup  | Backend             | HIGH     | Low (NIB is unique)            |

## Migration Required

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(client_id, content_hash) WHERE content_hash IS NOT NULL;
```

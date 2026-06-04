---
date: 2026-06-04
domain: operations
study: doc-intake-unified
phase: 1d-destinations
client_case: false
sources:
  - apps/backend-rag/backend/app/routers/crm_enhanced_documents.py
  - apps/backend-rag/backend/app/routers/crm_clients_documents.py
  - apps/backend-rag/backend/app/modules/crm/models.py
  - apps/backend-rag/backend/services/crm/documents.py
  - apps/backend-rag/backend/app/utils/crm_utils.py
  - research/agent-craft/proposed-agents/company-docs-consistency-auditor.md
---

# FASE 1d — DESTINATIONS map (where a classified document is INJECTED / DISTRIBUTED)

A document that the intake system reads + classifies has **3 valid destinations** plus **1 downstream consumer**, and **2 hard PII boundaries** (must NOT go there).

```
                    [ classified doc + extracted fields ]
                                 |
        +------------------------+------------------------+
        v                        v                        v
  (D1) CRM Postgres        (D2) Drive ordinato       (D3) audit-agent
   documents row           02_Company/03_Tax/...      (consumer, no write)
   (structured truth)      (renamed file archive)
        |
        +-- practices.documents (JSON denorm) / interactions (provenance)

   BOUNDARY: PII doc -> NEVER (B1) RAG/Qdrant   NEVER (B2) NotebookLM / cloud
```

---

## D1 — CRM Postgres (the `documents` table) — PRIMARY structured destination

Authoritative store for a per-client document. Written by `POST /api/crm/clients/{client_id}/documents`
(`crm_enhanced_documents.py:108` create_document, and `:776` upload-and-create path).

**`documents` table columns** (from `INSERT` at `crm_enhanced_documents.py:130-150` + `SELECT` at `:71-90`):

| column | role |
|---|---|
| `id` | PK |
| **`client_id`** (int) | FK → `clients.id`. **THE association key.** verify_client_access gate (`:70`). |
| **`practice_id`** (int) | FK → `practices.id`. Optional — links doc to a specific pratica. |
| `family_member_id` (int) | FK → `client_family_members.id` (doc belongs to a dependent, not the main client) |
| `document_type` | e.g. passport, kitas, nib, npwp, akta |
| `document_category` | one of: immigration / pma / tax / personal / family / other |
| `file_name`, `file_id`, `file_url`, `google_drive_file_url` | Drive linkage (see D2) |
| `expiry_date` | drives the alert_color logic (expired/red/yellow/green, `:81-86`) |
| `ocr_status` | pending → triggers OCR dispatcher (`migration_061_documents_ocr_status.sql`) |
| `status`, `storage_type` | default google_drive |
| `subfolder` | nested subfolder hint (e.g. "Actual Visa" / "Previous Visa") |
| `is_archived`, `notes`, `created_at`, `updated_at` | soft-delete + metadata |

**How a document is associated to a client/practice:**
- **client**: mandatory `documents.client_id` (integer FK). Every doc belongs to exactly one client.
- **practice**: optional `documents.practice_id`. A practice (`practices` table, `models.py:100`) has
  `client_id` (FK) + `practice_type_id`; it ALSO carries a denormalized `practices.documents` JSON column
  (`models.py:155`) and `practices.missing_documents` JSON — i.e. there is a second, looser doc list per pratica
  (`POST /api/crm/practices/{practice_id}/documents/add`, crm_practices.py:1603; reads `SELECT documents FROM practices`, :1623).
- **required-docs checklist**: `practice_required_documents` table (`migration_054`, `037_add_practice_required_docs.sql`) —
  the per-practice expected-document list the intake can satisfy (`crm_practices.py:1901/1947`).

> Intake write target = INSERT into `documents` with `client_id` (+ `practice_id` if known) + `document_category`
> from the classifier, then the existing OCR-by-folder dispatcher fires automatically.

**Company-level variant**: `company_documents` table (separate INSERT at `crm_enhanced_documents.py:821`) for
PT/PMA company files linked via `client_company_links` (`:597`) + `clients.client_type='company'`.

**Provenance / activity**: `interactions` table (`models.py:175`) has `client_id` + `practice_id` +
`interaction_type` ('chat/email/whatsapp') + `channel` + `extracted_entities` JSON. This is the natural place to log
"document received via WhatsApp/email on <date>" as an intake event. (Memory: interactions table is near-empty — intake
would be a legitimate populator.)

**RBAC on writes** (`crm_utils.py:47` is_crm_admin, `:136` verify_client_access):
admin set = `settings.admin_emails_set` (zero@ / asya@ / antonellosiano@) ∪ CRM_EXTRA_ADMIN. Team members can only
touch a client where `assigned_to` matches. The intake writer must run with an admin-equivalent identity or respect assignment.

---

## D2 — Drive "ordinato" — the renamed FILE archive

The physical file lands in a per-client Drive folder tree, auto-created on first upload
(`crm_enhanced_documents.py:584-770`). Structure:

```
<root>/ (settings.google_drive_root_folder_id)
  +-- gdrive_individuals_folder_id/   (client_type=individual)
  +-- gdrive_companies_folder_id/     (client_type=company)  [CAVEAT: phantom in past, crm_clients.py:118]
        +-- "<client.id>_<client.full_name>"/   <- clients.google_drive_folder_id stored here
              +-- 01_Immigration/   (+ nested "Actual Visa" / "Previous Visa")
              +-- 02_Company/
              +-- 03_Tax/
              +-- 04_Family/
              +-- 99_Misc/
```

**Category → folder map** (`services/crm/documents.py:214`, `CATEGORY_TO_FOLDER`):
`family→04_Family · immigration→01_Immigration · pma→02_Company · tax→03_Tax · other→99_Misc` (default `99_Misc`).
The classifier's `document_category` therefore directly selects the Drive subfolder.

**Yes — a classified doc SHOULD be archived here, renamed.** The intake should: ensure root folder
(`clients.google_drive_folder_id`, created + persisted at `:632`), find/create the category subfolder, upload the file,
and write `documents.file_id` / `google_drive_file_url` back into D1. Folder + DB are kept in sync in the same handler.

---

## D3 — `company-docs-consistency-auditor` — natural CONSUMER (not a write target)

Proposed agent at `research/agent-craft/proposed-agents/company-docs-consistency-auditor.md` (102 lines).
It is the downstream consumer of the intake, NOT a storage destination.

**What it expects as INPUT** (agent spec "## Input"):
- Preferred: a `document-intake-classifier` **intake JSON** at `research/crm/intake/<...>-intake.json` — the structured
  fields already extracted (akta pendirian, NIB, NPWP, OSS izin, SK Kemenkumham).
- Or a structured company file (akta + NIB + NPWP + izin fields).
- Missing types go into `missing_documents[]`; it runs only checks whose inputs are present.

**What it does**: cross-document consistency + legality (K1 name match across akta/NIB/NPWP/SK; K2 modal disetor ≥ PMA min;
K3 KBLI foreign-ownership eligibility; K4 direksi/komisaris akta↔NIB; K6 NPWP badan; K7 tax-arrears smell). Emits a graded
PASS/WARN/FAIL report to `research/compliance/<date>-<client>-docaudit.md`. **No DB mutation** (hard rule 4).

> Implication for FASE-1 design: the intake should emit a stable **structured intake JSON** (the same fields the auditor's
> K1-K8 reference) as a first-class output artifact — that JSON is the contract between intake and auditor.

---

## BOUNDARIES — where a CLIENT document must NOT go

### B1 — NOT into RAG / Qdrant (PII firewall)
Verified: the Qdrant/vector path (`core/qdrant_db.py` upsert, `oracle_ingest.py`, KBLI/legal ingestion) is keyed on
**KB documents, never `client_id`** — no CRM-document ingestion path exists (grep for client_id in vector services = 0).
The embedding model is FROZEN (`text-embedding-3-small`, 1536 dims) and the KBLI payload is flat regulatory data.
Client passports/NIB/NPWP carry PII (NIK, passport no., NPWP) and must stay in CRM/Drive only. RAG is regulatory ground-truth,
not a client-document index. **Do not inject client docs into Qdrant.**

### B2 — NOT into NotebookLM / cloud (OSINT/PII sovereignty)
NB are ground-truth NORMATIVE corpora (NB-0..NB-14, KBLI/visa/tax law). Confirmed by usage: research-capture convention
only pushes `domain=property` research to NB-5; client PII is never a NB source. The auditor spec itself enforces
"PII discipline … keep client identity local; mask PII in Telegram/logs" (hard rule 3) and "non-PII numbers only" to any
cloud/math LLM. **Client documents do NOT go to NotebookLM, Drive-Gemini-mirror, or any cloud LLM with identity attached.**
(SYMBIOSIS Law 2 — OSINT/PII never leaves the Pro/sovereign perimeter.)

---

## Summary table

| Dest | What lands there | Key/association | Write? |
|---|---|---|---|
| D1 CRM `documents` | structured row (type, category, expiry, ocr_status, Drive linkage) | `client_id` (+`practice_id`,`family_member_id`) | INSERT |
| D1b `practices.documents` JSON + `interactions` | per-pratica doc list + intake provenance event | `practice_id`/`client_id` | INSERT/append |
| D2 Drive ordinato | renamed physical file | `clients.google_drive_folder_id` + category→subfolder | upload + write file_id back to D1 |
| D3 docs-consistency-auditor | reads intake JSON | client slug / structured fields | READ-ONLY consumer |
| B1 RAG/Qdrant | (regulatory KB only) | — | **FORBIDDEN for PII** |
| B2 NotebookLM/cloud | (normative ground-truth only) | — | **FORBIDDEN for PII** |

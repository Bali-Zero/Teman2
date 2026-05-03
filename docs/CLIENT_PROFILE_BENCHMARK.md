# Client Profile Benchmark — Workflow & Data Specification

> **Version:** 1.0
> **Date:** 2026-03-07
> **Pilot:** Michele Porinelli (#146) / PT FRA Real Estate Consulting
> **Purpose:** Definitive reference for populating every section of a client profile on `kita.balizero.com/clients/{id}`. This document is the single source of truth for AI agents, human operators, and automated pipelines.

---

## TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [Profile Header](#2-profile-header)
3. [Overview Tab](#3-overview-tab)
4. [Family Tab](#4-family-tab)
5. [Immigration Tab](#5-immigration-tab)
6. [Company Tab](#6-company-tab)
7. [Tax Tab](#7-tax-tab)
8. [Data Sources & Priority](#8-data-sources--priority)
9. [OCR Pipeline](#9-ocr-pipeline)
10. [Automation Workflow](#10-automation-workflow)
11. [Quality Checklist](#11-quality-checklist)

---

## 1. ARCHITECTURE OVERVIEW

### Data Flow

```
Google Drive (source documents)
        |
        v
OCR Pipeline (gpt-4o-mini vision / pypdf text extraction)
        |
        v
PostgreSQL (structured data)
        |
        v
FastAPI Backend (/api/crm/clients/{id}/profile)
        |
        v
Next.js Frontend (kita.balizero.com/clients/{id})
```

### Database Tables

| Table                   | Purpose                      | Key Fields                                                                                                            |
| ----------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `clients`               | Individual person record     | full_name, email, phone, nationality, passport_number, passport_expiry, date_of_birth, status, google_drive_folder_id |
| `companies`             | Company entity               | company*name, company_type, kbli_code, nib, npwp_company, akta*\_, sk\_\_, registered_address, custom_fields (JSONB)  |
| `client_company_links`  | Junction: person <-> company | client_id, company_id, role, ownership_percentage, shares_count, share_nominal_value, is_primary                      |
| `client_family_members` | Dependents & family          | client_id, full_name, relationship, passport_number, passport_expiry, current_visa_type, visa_expiry                  |
| `client_documents`      | Personal documents           | client_id, document_type, document_category, file_url, google_drive_file_url, expiry_date                             |
| `company_documents`     | Company documents            | company_id, document_type, google_drive_file_id, file_name, status                                                    |

### Frontend Page Structure

```
page.tsx (~5500 lines)
  |
  +-- ClientDetailPage (main component)
  |     +-- Profile Header (avatar, name, status, alerts, quick actions)
  |     +-- Tab Navigation (overview | family | immigration | company | tax)
  |
  +-- OverviewTab        (line ~919)   — personal info, passport, visa, practices, timeline
  +-- FamilyTab          (line ~2210)  — family members with passport/visa alerts
  +-- ImmigrationTab     (line ~2639)  — passport detail, visa history, documents
  +-- CompanyTab         (line ~4462)  — company cards with legal data + doc uploads
  +-- TaxTab             (line ~5068)  — personal tax, annual, monthly, LKPM
  |
  +-- Modals:
       +-- EditClientModal         (line ~3247)
       +-- AddFamilyMemberModal    (line ~3554)
       +-- EditFamilyMemberModal   (line ~3685)
       +-- AddDocumentModal        (line ~3896)
       +-- EditDocumentModal       (line ~4073)
       +-- CompanyDocUpload        (line ~4235) — per-document upload cards
       +-- AddCompanyModal         (embedded in CompanyTab)
```

---

## 2. PROFILE HEADER

### What it shows

- Avatar (uploaded photo OR nationality flag OR blank circle)
- Full name (h1)
- Client ID, type (Individual/Company), company name
- Assigned team member (with avatar + WhatsApp link)
- Alert badges (expired count, red alerts, yellow alerts)
- Quick action buttons: WhatsApp, Telegram

### Data Source

| Field       | DB Table  | Column               | Required                            |
| ----------- | --------- | -------------------- | ----------------------------------- |
| Full Name   | `clients` | `full_name`          | YES                                 |
| Avatar      | `clients` | `avatar_url`         | No (falls back to flag)             |
| Nationality | `clients` | `nationality`        | For flag display                    |
| Phone       | `clients` | `phone`              | For WhatsApp/Telegram buttons       |
| Assigned To | `clients` | `assigned_to`        | Team member email                   |
| Status      | `clients` | `status`             | lead/active/completed/lost/inactive |
| Alerts      | computed  | from `expiry_alerts` | Auto-calculated                     |

### Population Workflow

1. **Name**: From initial CRM entry or Drive folder name (strip "PT " prefix for individual)
2. **Avatar**: Upload via Edit Client modal (auto-cropped to square)
3. **Nationality**: Set during onboarding or extracted from passport OCR
4. **Phone**: From WhatsApp conversation or manual entry (format: +{country}{number})
5. **Assigned To**: Set by team lead, email from `TEAM_MEMBERS` list

---

## 3. OVERVIEW TAB

### Sections Displayed

#### 3a. Personal Information Card

Shows: nationality (with flag), date of birth (with birthday indicator), email, phone, WhatsApp, address, gender, birthplace, first contact date, notes.

| Field         | DB Column               | Source                          |
| ------------- | ----------------------- | ------------------------------- |
| Nationality   | `clients.nationality`   | Passport OCR or manual          |
| Date of Birth | `clients.date_of_birth` | Passport OCR (YYYY-MM-DD)       |
| Email         | `clients.email`         | Manual or conversation          |
| Phone         | `clients.phone`         | Manual (with country code)      |
| WhatsApp      | `clients.whatsapp`      | Same as phone or different      |
| Address       | `clients.address`       | Manual (Bali address preferred) |
| Gender        | `clients.gender`        | M/F from passport               |
| Birthplace    | `clients.birthplace`    | Passport OCR                    |

#### 3b. Passport Card

Shows: passport number, issue/expiry dates, validity color indicator (green >14mo, yellow 9-13mo, red <9mo, expired).

| Field           | DB Column                 | Source                    |
| --------------- | ------------------------- | ------------------------- |
| Passport Number | `clients.passport_number` | Passport OCR              |
| Passport Expiry | `clients.passport_expiry` | Passport OCR (YYYY-MM-DD) |

**Alert Thresholds:**

- Green: >14 months until expiry
- Yellow: 9-13 months (warning: many visas require 14+ months)
- Red: <9 months (urgent: cannot apply for most long-term visas)
- Expired: past expiry date

#### 3c. Visa Card

Shows: current visa type, expiry date, price reference, status indicator.

| Field             | DB Column                      | Source                    |
| ----------------- | ------------------------------ | ------------------------- |
| Current Visa Type | via `practices` or `documents` | Latest active practice    |
| Visa Expiry       | `practices.expiry_date`        | From practice or document |

**Visa Price Reference** (embedded in component):

- B211A: Rp 8,500,000
- KITAS Work: Rp 25,000,000
- KITAS Investor: Rp 35,000,000
- KITAP: Rp 15,000,000
- E-Visa 60d: Rp 3,000,000
- Second Home: Rp 40,000,000

#### 3d. Practices List

Shows: all active + completed practices with status badges, dates, types.

| Field         | Source                                                 |
| ------------- | ------------------------------------------------------ |
| Practice Type | `practices.practice_type_name`                         |
| Status        | `practices.status` (inquiry/in_progress/completed/etc) |
| Start Date    | `practices.start_date`                                 |
| Expiry Date   | `practices.expiry_date`                                |

#### 3e. Timeline / Interactions

Shows: recent interactions (chat, email, WhatsApp, calls, meetings, notes) with timestamps.

| Field        | DB Table       | Source                                                   |
| ------------ | -------------- | -------------------------------------------------------- |
| Interactions | `interactions` | Auto-logged from WhatsApp/Telegram/email or manual notes |

---

## 4. FAMILY TAB

### What it shows

For each family member: name, relationship, nationality, DOB, passport (number + expiry + alert color), visa (type + expiry + alert), email, phone, notes. Edit and Delete buttons per member.

### Database: `client_family_members`

| Column              | Type    | Required | Source                               |
| ------------------- | ------- | -------- | ------------------------------------ |
| `full_name`         | varchar | YES      | Manual or document OCR               |
| `relationship`      | varchar | YES      | spouse/child/parent/sibling/other    |
| `date_of_birth`     | date    | No       | Passport OCR or birth certificate    |
| `nationality`       | varchar | No       | Passport OCR                         |
| `passport_number`   | varchar | No       | Passport OCR                         |
| `passport_expiry`   | date    | No       | Passport OCR                         |
| `current_visa_type` | varchar | No       | E-Visa application OCR or manual     |
| `visa_expiry`       | date    | No       | From practice or manual              |
| `email`             | varchar | No       | Manual                               |
| `phone`             | varchar | No       | Manual                               |
| `notes`             | text    | No       | Free text (document references, etc) |

### Population Workflow

1. **Discover family**: Check Drive folder `04_Family` for passports, birth certificates, visa applications
2. **OCR each passport**: Use gpt-4o-mini vision to extract: full_name, passport_number, date_of_birth, date_of_expiry, nationality, place_of_birth
3. **OCR visa applications**: Extract visa_type (e.g., VTT-317), stay permit category
4. **Create/Update records**: Via `POST /api/crm/clients/{id}/family` or `PUT /api/crm/clients/{id}/family/{member_id}`
5. **Verify alerts**: Passport expiry thresholds auto-calculated by frontend

### Document Upload

Each family member has an upload button for attaching documents directly. Documents are linked via `client_documents.family_member_id`.

---

## 5. IMMIGRATION TAB

### What it shows

- Passport detail card (full info + validity gauge)
- Current visa status with timeline
- Immigration document list (organized by category)
- Expiry alerts panel

### Data Sources

| Section   | DB Source                                                                                |
| --------- | ---------------------------------------------------------------------------------------- |
| Passport  | `clients.passport_number`, `clients.passport_expiry`                                     |
| Visa      | Latest `practices` with immigration type OR `client_documents` with category=immigration |
| Documents | `client_documents` WHERE `document_category = 'immigration'`                             |
| Alerts    | Computed from passport_expiry, visa expiry, document expiry                              |

### Document Categories (immigration)

| Document Type             | Typical Source                          | Has Expiry   |
| ------------------------- | --------------------------------------- | ------------ |
| Passport                  | Drive: `00_Profile` or `01_Immigration` | YES          |
| E-Visa                    | Drive: `01_Immigration`                 | YES          |
| KITAS                     | Drive: `01_Immigration`                 | YES          |
| KITAP                     | Drive: `01_Immigration`                 | YES          |
| ITAS                      | Drive: `01_Immigration`                 | YES          |
| MERP                      | Drive: `01_Immigration`                 | YES          |
| Exit Permit               | Drive: `01_Immigration`                 | YES          |
| STM (Surat Tanda Melapor) | Drive: `01_Immigration`                 | YES (annual) |
| SKTT                      | Drive: `01_Immigration`                 | YES          |

---

## 6. COMPANY TAB

### What it shows

For each linked company: header (name, type, status, brand), 2-column layout:

- **Left column**: Legal & Registration (role, ownership, capital, SK, akta, NIB, NPWP, KBLI)
- **Right column**: Contact & Location (addresses, phone, email, people/stakeholders, key identifiers)
- **Bottom**: Company Documents upload section (4 cards: Akta+SK, NPWP, NIB, Profile Perseroan)

### Database: `companies` + `client_company_links`

#### Company Entity (`companies`)

| Column                   | Type    | Source                           | OCR Field                         |
| ------------------------ | ------- | -------------------------------- | --------------------------------- |
| `company_name`           | varchar | SK/Akta OCR or manual            | "Nama Perseroan"                  |
| `company_type`           | varchar | Manual (PT PMA/PT Perorangan/CV) | From SK context                   |
| `brand_name`             | varchar | Manual or Profil Perseroan       | "Nama Merek"                      |
| `kbli_code`              | varchar | NIB OCR or OSS                   | "Kode KBLI"                       |
| `kbli_description`       | varchar | KBLI database lookup             | Auto from kbli_code               |
| `nib`                    | varchar | NIB document OCR                 | "NIB" number                      |
| `npwp_company`           | varchar | NPWP document OCR                | 15-digit number                   |
| `akta_pendirian_no`      | varchar | Akta Pendirian OCR               | "Nomor" on notarial deed          |
| `akta_pendirian_date`    | date    | Akta Pendirian OCR               | Date on deed                      |
| `akta_perubahan_no`      | varchar | Akta Perubahan OCR               | Latest amendment number           |
| `akta_perubahan_date`    | date    | Akta Perubahan OCR               | Latest amendment date             |
| `sk_menhumkam_no`        | varchar | SK Kemenkumham OCR               | "Nomor: AHU-XXXXX..."             |
| `sk_menhumkam_date`      | date    | SK OCR                           | Date on decree                    |
| `registered_address`     | varchar | SK/Akta OCR                      | "Alamat" or "Kedudukan"           |
| `office_address`         | varchar | Manual or Profil                 | Operational address               |
| `city`                   | varchar | SK OCR                           | Usually "Kabupaten Badung" etc    |
| `province`               | varchar | SK OCR                           | Usually "Bali"                    |
| `company_phone`          | varchar | Manual                           | -                                 |
| `company_email`          | varchar | Manual                           | -                                 |
| `status`                 | varchar | Manual                           | active/dormant/dissolved/in_setup |
| `setup_progress`         | integer | Computed                         | 0-100 based on docs present       |
| `google_drive_folder_id` | varchar | Drive API                        | Folder ID                         |
| `custom_fields`          | JSONB   | Pipeline                         | `people[]`, `docs_found[]`        |

#### Client-Company Link (`client_company_links`)

| Column                 | Type    | Source      | OCR Field                              |
| ---------------------- | ------- | ----------- | -------------------------------------- |
| `role`                 | varchar | SK/Akta OCR | "Direktur", "Komisaris"                |
| `ownership_percentage` | decimal | SK OCR      | "Persentase" or computed from shares   |
| `shares_count`         | integer | SK OCR      | "Jumlah Saham"                         |
| `share_nominal_value`  | integer | SK OCR      | "Nilai Nominal" (usually Rp 1,000,000) |
| `is_primary`           | boolean | Manual      | True for main company                  |

#### Custom Fields JSONB (`companies.custom_fields`)

```json
{
  "people": [
    "MICHELE PORINELLI (Direktur, 50%)",
    "FRANCESCA RIZZO (Komisaris, 50%)"
  ],
  "docs_found": ["akta_pendirian", "sk_decree", "npwp", "nib"]
}
```

**IMPORTANT**: Filter `people[]` to exclude document names. Regex applied in frontend:

```typescript
people.filter((p) => !/^(akta|sk |surat|profil|nib |npwp)/i.test(p.trim()));
```

### Company Documents (`company_documents`)

| Document Type     | Card Label        | Drive Location              | OCR Target                    |
| ----------------- | ----------------- | --------------------------- | ----------------------------- |
| `akta_pendirian`  | Akta + SK         | `AKTA PENDIRIAN/` subfolder | Notarial deed + SK decree     |
| `npwp`            | NPWP              | `DOCUMENT/` subfolder       | Tax ID number                 |
| `nib`             | NIB               | `DOCUMENT/` subfolder       | Business license number       |
| `company_profile` | Profile Perseroan | Root or `DOCUMENT/`         | Full company profile from AHU |

### Capital Display Logic

Capital is calculated and abbreviated:

```
shares_count x share_nominal_value = total
>= 1T (trillion) -> "Rp {x}T"
>= 1B (billion)  -> "Rp {x}B"  (e.g., Rp 15B)
>= 1M (million)  -> "Rp {x}M"
< 1M             -> "Rp {formatted}"
```

---

## 7. TAX TAB

### Sections

| Section                | Purpose                                                     | Documents                                             |
| ---------------------- | ----------------------------------------------------------- | ----------------------------------------------------- |
| **Personal Tax**       | Client's individual NPWP, annual income, Form 1770          | SPT Tahunan, Bukti Potong                             |
| **Annual Company Tax** | Per-company annual filing                                   | SPT Tahunan Badan, Laporan Keuangan, Bukti Pembayaran |
| **Monthly Reports**    | PPH 21/23/25, PPN per month                                 | Monthly tax slips                                     |
| **LKPM**               | Quarterly investment realization report (mandatory for PMA) | LKPM Report, Employee Report, Production Report       |

### Key Deadlines

| Filing                         | Deadline                                                   |
| ------------------------------ | ---------------------------------------------------------- |
| Personal Tax (SPT 1770)        | March 31                                                   |
| Annual Company Tax (SPT Badan) | April 30                                                   |
| Monthly PPH 21/23/25/PPN       | 20th of following month                                    |
| LKPM                           | Quarterly (Q1: Apr 30, Q2: Jul 31, Q3: Oct 31, Q4: Jan 31) |

### Database: `tax_records` + `tax_documents` (future)

Currently the Tax tab uses local state and file upload. Full DB integration is planned.

---

## 8. DATA SOURCES & PRIORITY

### Source Hierarchy (most authoritative first)

| Priority | Source                                 | Reliability                  | Access Method               |
| -------- | -------------------------------------- | ---------------------------- | --------------------------- |
| 1        | **SK Kemenkumham** (cetak*sk*\*.pdf)   | Definitive legal document    | PDF text extraction (pypdf) |
| 2        | **Akta Notaris** (Pendirian/Perubahan) | Legal deed, often scanned    | OCR (gpt-4o-mini vision)    |
| 3        | **Profil Perseroan** (from AHU Online) | Official but can be outdated | PDF text or OCR             |
| 4        | **NIB / OSS** document                 | Business license             | PDF text or OCR             |
| 5        | **NPWP** document                      | Tax registration             | OCR (usually scanned)       |
| 6        | **Passport** (for individuals)         | Identity document            | OCR (image)                 |
| 7        | **Manual entry**                       | Human input                  | CRM form                    |

### CRITICAL WARNING: Document Contamination

> The Porinelli pilot revealed that Drive folders can contain documents from WRONG companies.
> The "Profil Perseroan" in PT FRA's folder was actually from PT BONHEUR MANAGEMENT BALI.
>
> **RULE**: Always cross-verify company name in extracted data against the expected company.
> If `extracted_company_name != expected_company_name`, FLAG immediately and do not auto-populate.

---

## 9. OCR PIPELINE

### Step-by-Step for Each Client

```
1. DISCOVER
   Input:  client.google_drive_folder_id
   Action: list_drive_files(folder_id) -> get all files and subfolders
   Output: file_manifest = [{name, id, mimeType, size, parent_folder}]

2. CLASSIFY
   For each file in manifest:
     - Match filename pattern to document type
     - Patterns:
       /akta/i                    -> akta_pendirian or akta_perubahan
       /sk|keputusan|decree/i     -> sk_decree
       /npwp/i                    -> npwp
       /nib|oss/i                 -> nib
       /profil.*perseroan/i       -> company_profile
       /passport|paspor/i         -> passport
       /visa|e-?visa|kitas/i      -> visa_document
       /akte.*lahir|birth/i       -> birth_certificate
       /pks|kontrak|contract/i    -> contract
       /bpjs/i                    -> bpjs
   Output: classified_files = [{file_id, doc_type, filename}]

3. EXTRACT (per document)

   3a. PDF with text (pypdf):
       - Download via Drive API -> io.BytesIO
       - pypdf.PdfReader -> extract_text() per page
       - If text found: parse with regex/LLM
       - If no text (scanned): fall through to 3b

   3b. Image or scanned PDF (OCR):
       - Download file bytes
       - base64 encode
       - Send to gpt-4o-mini with structured prompt:
         "Extract ALL text. Return JSON: {field1, field2, ...}"
       - Parse response JSON

4. VALIDATE
   - company_name in extracted data matches expected? If not, FLAG
   - Dates are valid (not future for issue dates, not past for new expiry)?
   - NPWP is 15 digits?
   - Passport number format matches nationality?

5. POPULATE
   - UPDATE companies SET ... WHERE id = X
   - UPDATE client_company_links SET ... WHERE company_id = X AND client_id = Y
   - INSERT/UPDATE company_documents (file_id, document_type, etc)
   - UPDATE client_family_members (for passport/visa data)

6. VERIFY
   - Re-fetch profile from API
   - Compare populated fields vs extracted data
   - Log discrepancies
```

### OCR Prompts (Proven Templates)

**Passport:**

```
Extract ALL text from this passport image. Return ONLY a JSON object with:
full_name, passport_number, date_of_birth (YYYY-MM-DD), nationality, sex,
date_of_issue (YYYY-MM-DD), date_of_expiry (YYYY-MM-DD), place_of_birth.
```

**SK Kemenkumham** (text-based, use regex):

```python
# Key patterns in SK text:
r"Nomor\s*:\s*(AHU-[\d]+\.AH\.\d+\.\d+\.Tahun\s*\d+)"  # SK number
r"Modal Dasar.*?Rp[.\s]*([\d.,]+)"                         # Authorized capital
r"(\w+[\w\s]*)\s*(?:Direktur|Komisaris)"                    # Directors/Commissioners
r"(\d+)\s*(?:lembar|saham)"                                 # Shares count
```

**E-Visa Application:**

```
Extract ALL text from this e-visa document. Return ONLY a JSON object with:
full_name, visa_type, visa_number, date_of_issue (YYYY-MM-DD),
date_of_expiry (YYYY-MM-DD), nationality, passport_number, stay_permit_type.
```

---

## 10. AUTOMATION WORKFLOW

### Full Client Profile Population — End-to-End

```
                    START
                      |
                      v
            +-------------------+
            | 1. Get Client ID  |
            |    & Drive Folder |
            +-------------------+
                      |
                      v
            +-------------------+
            | 2. List ALL files |
            |    recursively    |
            +-------------------+
                      |
                      v
            +-------------------+
            | 3. Classify files |
            |    by doc type    |
            +-------------------+
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
    +-----------+ +---------+ +----------+
    | Personal  | | Company | | Family   |
    | Documents | | Docs    | | Docs     |
    +-----------+ +---------+ +----------+
          |           |           |
          v           v           v
    +-----------+ +---------+ +----------+
    | OCR/Parse | | OCR/    | | OCR      |
    | Passport  | | Parse   | | Passports|
    | Visa      | | SK/Akta | | Visas    |
    +-----------+ | NPWP    | | Birth    |
          |       | NIB     | | Certs    |
          |       +---------+ +----------+
          |           |           |
          v           v           v
    +-----------+ +---------+ +----------+
    | UPDATE    | | UPDATE  | | UPDATE   |
    | clients   | | company | | family   |
    | table     | | tables  | | members  |
    +-----------+ +---------+ +----------+
          |           |           |
          +-----------+-----------+
                      |
                      v
            +-------------------+
            | 4. Verify via API |
            |    GET /profile   |
            +-------------------+
                      |
                      v
                    DONE
```

### Execution Modes

#### Mode A: Single Client (Manual/Pilot)

```bash
# Via Fly.io SSH
cat populate_client.py | fly ssh console -a nuzantara-rag -C 'python3 -'
```

Runs the full pipeline for one client. Used for pilots and debugging.

#### Mode B: Batch (Automated)

```python
# Via MCP chain or script
for client_id in client_ids:
    await populate_client_profile(client_id)
    await asyncio.sleep(2)  # Rate limit
```

Processes multiple clients sequentially. Rate limit to avoid Drive API quota.

#### Mode C: MCP Chain (Deterministic)

Use `chain_new_client_onboarding` which includes:

1. Create client record
2. Create Drive folder structure
3. Run OCR pipeline on uploaded documents
4. Populate all fields
5. Send welcome message

### Drive Folder Standard Structure

```
{Client Name}/
  +-- 00_Profile/          (passport, ID photos)
  +-- 01_Immigration/      (visa, KITAS, KITAP, permits)
  +-- 02_Company/          (akta, SK, NIB, NPWP, profile)
  |     +-- AKTA PENDIRIAN/
  |     +-- DOCUMENT/       (NIB, NPWP, BPJS, OSS)
  +-- 03_Tax/              (SPT, bukti potong, tax slips)
  +-- 04_Family/           (family passports, birth certs, family visas)
  +-- 99_Misc/             (contracts, correspondence, other)
```

**IMPORTANT**: Many existing client folders do NOT follow this structure. They may have:

- Files in root (not organized)
- Named subfolders (e.g., "MICHELLE PORINELLI", "FRANCESCA RIZZO")
- Documents from wrong companies (contamination risk)

The pipeline must handle BOTH organized and unorganized folders.

---

## 11. QUALITY CHECKLIST

### Per-Client Completion Criteria

#### Header (5 fields)

- [ ] Full name correct (no company name, no typos)
- [ ] Nationality set (for flag display)
- [ ] Phone number with country code
- [ ] Assigned team member set
- [ ] Status correct (lead/active/completed)

#### Overview Tab (10 fields)

- [ ] Date of birth (YYYY-MM-DD, from passport)
- [ ] Email address
- [ ] Phone / WhatsApp
- [ ] Address (Bali address)
- [ ] Gender (M/F)
- [ ] Birthplace
- [ ] Passport number
- [ ] Passport expiry (YYYY-MM-DD)
- [ ] Current visa type identified
- [ ] At least 1 practice linked

#### Family Tab (per member)

- [ ] Full name
- [ ] Relationship (spouse/child/parent/sibling)
- [ ] Nationality
- [ ] Date of birth
- [ ] Passport number (if available)
- [ ] Passport expiry (if available)
- [ ] Current visa type (if applicable)
- [ ] Visa expiry (if applicable)

#### Company Tab (per company)

- [ ] Company name verified (matches SK, not contaminated)
- [ ] Company type (PT PMA / PT Perorangan / CV)
- [ ] Client role (Director/Commissioner/Shareholder)
- [ ] Ownership percentage
- [ ] Shares count + nominal value -> Capital displayed
- [ ] SK Kemenkumham number + date
- [ ] Akta Pendirian number + date
- [ ] Akta Perubahan number + date (if exists)
- [ ] NIB number
- [ ] NPWP company (15 digits)
- [ ] KBLI code(s)
- [ ] Registered address
- [ ] People list (directors, commissioners with %)
- [ ] 4 document cards (Akta+SK, NPWP, NIB, Profile) — at least 2 on file
- [ ] No contaminated data (company name matches expected)

#### Tax Tab

- [ ] Personal NPWP linked (if applicable)
- [ ] Company NPWP matches `companies.npwp_company`
- [ ] Current year SPT status known

### Scoring

| Score   | Criteria                                      | Level     |
| ------- | --------------------------------------------- | --------- |
| 0-30%   | Header + basic personal info only             | Minimal   |
| 31-60%  | + passport, visa, 1 company basic             | Partial   |
| 61-80%  | + family members, company docs, addresses     | Good      |
| 81-95%  | + all company legal data, tax info            | Complete  |
| 96-100% | + all documents uploaded, all alerts resolved | Benchmark |

**Michele Porinelli (#146) target: 90%+** (achieved with pilot work)

---

## APPENDIX A: API Endpoints Used

| Endpoint                                 | Method | Purpose                                              |
| ---------------------------------------- | ------ | ---------------------------------------------------- |
| `/api/crm/clients/{id}/profile`          | GET    | Full profile with family, docs, practices, companies |
| `/api/crm/clients/{id}`                  | PUT    | Update client fields                                 |
| `/api/crm/clients/{id}/family`           | POST   | Add family member                                    |
| `/api/crm/clients/{id}/family/{fid}`     | PUT    | Update family member                                 |
| `/api/crm/clients/{id}/companies`        | GET    | List linked companies                                |
| `/api/crm/companies/{id}/documents`      | GET    | List company documents                               |
| `/api/crm/clients/{id}/documents/upload` | POST   | Upload document with OCR                             |
| `/api/crm/clients/{id}/timeline`         | GET    | Interaction timeline                                 |
| `/api/crm/document-categories`           | GET    | Available document types                             |

## APPENDIX B: Team Members (for assigned_to)

| Name      | Email                  | Role        |
| --------- | ---------------------- | ----------- |
| Antonello | antonello@balizero.com | Founder     |
| Rika      | rika@balizero.com      | Operations  |
| Nurul     | nurul@balizero.com     | Immigration |
| Nadia     | nadia@balizero.com     | Tax         |
| Wayan     | wayan@balizero.com     | Admin       |
| Kadek     | kadek@balizero.com     | Support     |
| Gede      | gede@balizero.com      | Legal       |
| Putu      | putu@balizero.com      | Finance     |

---

**End of Document**

_This benchmark was built from the Michele Porinelli (#146) pilot on 2026-03-07.
Every section was populated with real data extracted via OCR from Google Drive documents.
Use this as the definitive template for all future client profile populations._

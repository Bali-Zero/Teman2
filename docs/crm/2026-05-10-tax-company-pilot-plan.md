# Tax Company Pilot Plan - Bali Zero CRM

Date: 2026-05-10
Scope: read-only preparation for `kita.balizero.com`

This plan prepares two tax/company clusters found under the old tax member working folders. It does not move, rename, delete, or write any Google Drive file.

## Goal

Turn two messy Drive clusters into person-centric CRM workspace views:

```text
Person -> Company -> Tax consultant -> Drive evidence -> Missing docs -> AI recap
```

The workspace must preserve Drive as file authority, DB as structured authority, and `kita.balizero.com` as the working surface.

## Pilot Companies

### 1. OCEAN CLOTHES AND SHOES PT

Tax member surface:

- Consultant/workspace branch: `DEA`
- Old operational folder: https://drive.google.com/drive/folders/1qJwTPkKFbm5Re1mKMeEEBFTfw0bYAYnQ
- Canonical-like company folder found separately: https://drive.google.com/drive/folders/1WRzDqNb_5M9DS7bqokaSgDxGkUlpj-TT
- Tax folder: https://drive.google.com/drive/folders/1Mfwo4txaLarfoDucQzB4_QFgt1YKragA

Visible company evidence:

- `#TAX`
- `AKTA`
- `DOKUMEN`
- `Profil Perseroan.pdf`
- `Rincian PT.pdf`
- `PERMATA OCEAN CLOTHES AND SHOES.pdf`
- `USER MOLINA.txt`
- `Email` / `Email.txt`

Visible tax evidence:

- `SPT 2025`
- `Laporan Keuangan PT Ocean Clothes and Shoes 2025`
- `Laporan Keuangan PT Ocean Clothes and Shoes 2026`
- `INCOME`
- `BILLING & PROOF`
- `Employee`

Visible persons:

- `Natan Kleimonov`: https://drive.google.com/drive/folders/1cEVr2XasfdL8x80vD3kqDxXWrN2XgRk3
  - visible evidence: passport
- `Ihor Osmanov`: https://drive.google.com/drive/folders/1TEReUTgln8MPtTCMIBJjaZq988rMxPn8
  - visible evidence: TIN card, certificate of registration, digital certificate issuance letter, taxpayer account issuance letter, passport, ITK, evisa, bank statement, photo
- `Yaroslav Voitenko`: https://drive.google.com/drive/folders/1Caa_oMOSpl44KSX3fKZ8KCWlWRQTY-uB
  - visible evidence: passport

Open gaps:

- Confirm roles from `Profil Perseroan.pdf` / `Rincian PT.pdf`: director, shareholder, commissioner, beneficiary.
- Confirm whether the canonical-like folder is inside `Company_CRM` and whether it already has content in `00_AKTA`, `01_NIB`, `02_NPWP`, `03_Profile_Perseroan`, `99_Misc`.
- Confirm whether CRM `Individual_CRM` folders already exist for Natan, Ihor Osmanov, and Yaroslav Voitenko.
- Separate company tax docs from individual docs in the workspace view without moving files.

### 2. BIMALA / Bimala Investments Bali PT

Tax member surface:

- Consultant/workspace branch: `Dewa Ayu`
- Old Dewa Ayu target folder: https://drive.google.com/drive/folders/12A9-sgVqC-pTg_vN3LydCRIcyPLBUwfR
- Operational `BIMALA` folder: https://drive.google.com/drive/folders/192muakUUFdYZVq67w10dy_75R63nor_L
- Nested company folder: https://drive.google.com/drive/folders/1XtwojMeO0ladAvjswmEdMclns7efdCaq
- Tax folder: https://drive.google.com/drive/folders/1j3ru9wKOEC1vP3AUPrteO95I4lm7UuAI

Visible company/tax evidence:

- Proof of receipt letter
- TIN card
- Certificate of registration
- Taxpayer account issuance letter
- Bank transaction PDFs
- `EMAIL DJP & CORTAX ACSES`
- `Tax/2026`
- `Bukti Lapor SPT zero 2024.pdf`
- `FORM SPT 7117 2024.pdf`
- `Dokument Pelengkap SPT PT Bimala Investment.pdf`
- `LKPM Periode 4` PDFs
- `AKTA`
- `DOKUMEN`
- `Profil Perseroan.pdf`
- `Rincian PT.pdf`
- company bank statement

Visible persons:

- `Giulia Del Giudice`: https://drive.google.com/drive/folders/1Xy60Q9k5detu8oZhFWVWexDYh07Yx4LO
  - visible evidence: ITAS E28A Investor, passport, CV, bank statement, address, travel, photo, child folder
- `Gianluca Morelli`: https://drive.google.com/drive/folders/1a1LhqSttRqLwUgDXmOdV38QYTaYdMU6X
  - visible evidence: ITAS E28A Investor, passport, CV, bank statement, address, travel, photo, child folders
- Related child evisa files visible in search:
  - `GIORGIA EMIDIO`
  - `IUMA MORELLI`
  - `MAILEN MORELLI`

Open gaps:

- Confirm exact family/person relationships before showing child records under a parent profile.
- Confirm roles from `Profil Perseroan.pdf` / `Rincian PT.pdf`.
- Confirm whether `Bimala Investments Bali PT`, `PT Bimala`, and `PT Bimala Investments Bali` are duplicates, aliases, or separate client folders.
- Confirm whether CRM `Individual_CRM` folders already exist for Giulia and Gianluca.

## Workspace Cards To Prepare

### Person Card

For each person:

- identity
- linked company or companies
- role in each company, if confirmed
- tax consultant
- setup consultant, if found later
- passport / immigration evidence
- NPWP / Coretax evidence
- family links
- missing required docs
- Drive evidence links
- AI recap in plain language

### Company Card

For each company:

- canonical company name
- aliases and duplicate folder candidates
- tax consultant
- linked persons with role confidence
- company documents: AKTA, NIB, NPWP, Profil Perseroan, Rincian PT
- tax status: SPT, LKPM, finance sheets, billing/proof, income, employee
- Coretax access status
- missing docs
- Drive evidence links
- AI recap

### Tax Consultant Desk

For each tax member:

- assigned companies
- assigned persons
- current evidence folders
- stale/legacy folders
- unresolved shortcuts
- urgent missing docs
- next deadline slots

## Preparation Tasks

1. Create a read-only graph snapshot for only these two clusters.
2. Resolve shortcut edges:
   - `Members/Dea -> DEA -> OCEAN CLOTHES AND SHOES PT`
   - `Members/Dewa Ayu -> Dewa Ayu -> BIMALA`
3. Normalize names without moving Drive files.
4. Build duplicate candidates:
   - Ocean operational folder vs canonical-like company folder.
   - Bimala/Bimala Investments Bali/PT Bimala variants.
5. Extract roles from `Profil Perseroan.pdf` and `Rincian PT.pdf`.
6. Link visible person folders to company nodes with confidence levels.
7. Generate missing-doc checklists.
8. Generate AI recaps with evidence links.
9. Surface everything in `kita.balizero.com` as a read-only pilot.
10. Only after human review, create clean shortcuts in the current `Members` folders.

## Brainstorming Results

Gemini fallback pass:

- Strong warning: do not expose company financial/tax files on a person page until role/RBAC is confirmed.
- Main risk is entity resolution: same person/company may appear with spelling variants and duplicated folders.
- Recommended nodes: `Person`, `Company`, `TaxCycle`, `Document`.
- Recommended edges: role edge, tax obligation edge, evidence edge, consultant assignment edge.
- UI should expose deep links to Drive, not copies.

NotebookLM CRM-sync pass:

- Use Drive graph indexing and Drive change notifications as the longer-term sync pattern.
- For this small pilot, avoid heavy CDC.
- Use a simple transactional outbox plus idempotent processing for workspace updates.
- Treat folder/file sync as at-least-once; dedupe by Drive item id and event id.

Claude Opus pass:

- First attempt hung with no output after more than a minute.
- Bare retry failed because bare mode does not use the existing OAuth/Keychain login.
- Normal retry with MCP disabled also hung with no output.
- Result: Claude Opus was not used as a source for this plan.

DeepSeek pass:

- `DEEPSEEK_API_KEY` was not present in the current environment.
- Local checked env files did not advertise a DeepSeek entry.
- Result: DeepSeek was not used as a source for this plan.

## Recommended First Build

Build one read-only endpoint and one workspace page:

```text
/crm/pilot/tax-company-map?company=ocean
/crm/pilot/tax-company-map?company=bimala
```

The endpoint should return:

```text
company
aliases
tax_member
drive_folders
persons
documents
duplicate_candidates
missing_docs
ai_recap
evidence_links
confidence
```

Acceptance criteria:

- Ocean page shows DEA as tax member and links Natan, Ihor, Yaroslav.
- Bimala page shows Dewa Ayu as tax member and links Giulia, Gianluca, child-related files as unconfirmed family edges.
- No Drive write occurs.
- No company financial file is exposed to a person unless role confidence is high or internal-user RBAC permits it.
- Every recap sentence has a supporting Drive evidence link.

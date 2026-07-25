---
date: 2026-07-24
domain: visa
client_case: none — Visa Oracle v2 product research (RulePack fact-base)
sources:
  - apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py
  - apps/backend-rag/backend/app/routers/visa_oracle.py
  - research/visa/2026-07-17-visa-catalog-bonifica-110-remap.md
  - https://www.kemenimipas.go.id (Permen Imipas 10/2026 context)
  - https://evisa.imigrasi.go.id (Kepmen M.IP-08.GR.01.01/2025 context)
status: verified
adversarial_review: codex
---

# BVK / Tourism Short-Stay Fact Base

This document provides the definitive per-code fact base for the BVK and short-stay tourism/business visa family for the Visa Oracle v2 RulePack factory.

### A1 — Visa Free Tourism / Bebas Visa Kunjungan (Wisata)
- **catalog_entry**: 
  - category: Visa Free/VOA 
  - covered_purposes: TOURISM, TRANSIT 
  - entry_policy: SINGLE 
  - stay_policy: FIXED_DAYS 30 
  - extension_policy: not allowed (0 extensions) 
  - prohibited_activities: EMPLOYMENT, BUSINESS_MEETINGS, STUDY, JOURNALISM 
  - sponsor_types: NONE 
  - legacy_codes: NONE
- **eligibility_rules**:
  - `{stage: HARD_FILTER, fact_path: applicant.nationality, op: IN, value: [Brunei Darussalam, Malaysia, Thailand, Singapura, Filipina, Kamboja, Laos, Myanmar, Vietnam, Timor-Leste, Suriname, Kolombia, Hong Kong, Turki, Brasil, Peru, Makau, Kazakhstan, Belarus], reason_code: BVK_NATIONALITY_ONLY, on_unknown: REQUIRE_EVIDENCE}`
  - `{stage: HARD_FILTER, fact_path: applicant.passport_validity_months, op: GTE, value: 6, reason_code: PASSPORT_VALIDITY_6M, on_unknown: REQUIRE_EVIDENCE}`
- **legal_basis**: Permen Imipas Nomor 10 Tahun 2026 (effective 2026-07-09); Kepmen M.IP-08.GR.01.01/2025. URLs: kemenimipas.go.id, imigrasi.go.id. Checked: 2026-07-24.
- **uncertainty**: BVK status for Hong Kong and Macau uses entity/SAR status rather than strict sovereign state. 

### B1 — Visit Visa Tourism (VOA) / Visa Saat Kedatangan (Wisata)
- **catalog_entry**:
  - category: VOA 
  - covered_purposes: TOURISM 
  - entry_policy: SINGLE 
  - stay_policy: FIXED_DAYS 30 
  - extension_policy: allowed, 30 days_per_extension, 1 max_extensions (total 60 days) 
  - prohibited_activities: EMPLOYMENT, BUSINESS_MEETINGS, STUDY, JOURNALISM 
  - sponsor_types: NONE 
  - legacy_codes: B213
- **eligibility_rules**:
  - `{stage: HARD_FILTER, fact_path: applicant.nationality, op: NOT_IN, value: [CALLING_VISA_COUNTRIES], reason_code: CALLING_VISA_RESTRICTED, on_unknown: BLOCK}`
  - `{stage: HARD_FILTER, fact_path: applicant.nationality, op: IN, value: [VOA_ELIGIBLE_97_COUNTRIES], reason_code: VOA_NATIONALITY_ONLY, on_unknown: REQUIRE_EVIDENCE}`
  - `{stage: HARD_FILTER, fact_path: applicant.passport_validity_months, op: GTE, value: 6, reason_code: PASSPORT_VALIDITY_6M, on_unknown: REQUIRE_EVIDENCE}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). URLs: evisa.imigrasi.go.id. Checked: 2026-07-24.
- **uncertainty**: UNVERIFIED whether a BVK-eligible nationality can actively choose to purchase a B1 VOA instead if they specifically want the 30-day extension option (which A1 does not offer). The precise count of VOA-eligible countries sits at ~97 but requires a live lookup table.

### C1 — Visit Visa Tourism / Visa Kunjungan Wisata
- **catalog_entry**:
  - category: Visit Visa 
  - covered_purposes: TOURISM, FAMILY 
  - entry_policy: SINGLE 
  - stay_policy: FIXED_DAYS 60 
  - extension_policy: allowed, 60 days_per_extension, 2 max_extensions (total 180 days) 
  - prohibited_activities: EMPLOYMENT, BUSINESS_MEETINGS, JOURNALISM 
  - sponsor_types: INDIVIDUAL, CORPORATE, NONE (for some e-Visas with proof of funds)
  - legacy_codes: B211A
- **eligibility_rules**:
  - `{stage: HARD_FILTER, fact_path: applicant.nationality, op: NOT_IN, value: [CALLING_VISA_COUNTRIES], reason_code: CALLING_VISA_RESTRICTED, on_unknown: BLOCK}`
  - `{stage: ELIGIBILITY, fact_path: applicant.proof_of_funds_usd, op: GTE, value: 2000, reason_code: FUNDING_REQUIREMENT_2000USD, on_unknown: REQUIRE_EVIDENCE}`
  - `{stage: HARD_FILTER, fact_path: applicant.passport_validity_months, op: GTE, value: 6, reason_code: PASSPORT_VALIDITY_6M, on_unknown: REQUIRE_EVIDENCE}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). URLs: evisa.imigrasi.go.id. Checked: 2026-07-24.
- **uncertainty**: Proof of funds amount exact enforcement mechanisms vary by application type (UNVERIFIED exact behavior for guarantor-sponsored vs self-sponsored).

### C2 — Visit Visa Business / Visa Kunjungan Bisnis
- **catalog_entry**:
  - category: Visit Visa 
  - covered_purposes: BUSINESS_MEETINGS, INVESTMENT 
  - entry_policy: SINGLE 
  - stay_policy: FIXED_DAYS 60 
  - extension_policy: allowed, 60 days_per_extension, 2 max_extensions (total 180 days) 
  - prohibited_activities: EMPLOYMENT (salaried work in ID) 
  - sponsor_types: CORPORATE 
  - legacy_codes: B211B, B211A (for basic business)
- **eligibility_rules**:
  - `{stage: HARD_FILTER, fact_path: applicant.nationality, op: NOT_IN, value: [CALLING_VISA_COUNTRIES], reason_code: CALLING_VISA_RESTRICTED, on_unknown: BLOCK}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.type, op: EQ, value: CORPORATE, reason_code: CORPORATE_SPONSOR_REQUIRED, on_unknown: REQUIRE_EVIDENCE}`
  - `{stage: HARD_FILTER, fact_path: applicant.passport_validity_months, op: GTE, value: 6, reason_code: PASSPORT_VALIDITY_6M, on_unknown: REQUIRE_EVIDENCE}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). URLs: evisa.imigrasi.go.id. Checked: 2026-07-24.
- **uncertainty**: Distinctions between C2 and C10 (Pertemuan Bisnis) require nuanced intent matching (UNVERIFIED strict barrier).

### C6 — Visit Visa Social Activity / Visa Kunjungan Kegiatan Sosial
- **catalog_entry**:
  - category: Visit Visa 
  - covered_purposes: OTHER 
  - entry_policy: SINGLE 
  - stay_policy: FIXED_DAYS 60 
  - extension_policy: allowed, 60 days_per_extension, 2 max_extensions (total 180 days) 
  - prohibited_activities: EMPLOYMENT, BUSINESS_MEETINGS 
  - sponsor_types: INDIVIDUAL, CORPORATE
  - legacy_codes: B211A (Socio-cultural)
- **eligibility_rules**:
  - `{stage: HARD_FILTER, fact_path: applicant.nationality, op: NOT_IN, value: [CALLING_VISA_COUNTRIES], reason_code: CALLING_VISA_RESTRICTED, on_unknown: BLOCK}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.type, op: IN, value: [INDIVIDUAL, CORPORATE], reason_code: SPONSOR_REQUIRED, on_unknown: REQUIRE_EVIDENCE}`
  - `{stage: HARD_FILTER, fact_path: applicant.passport_validity_months, op: GTE, value: 6, reason_code: PASSPORT_VALIDITY_6M, on_unknown: REQUIRE_EVIDENCE}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). URLs: evisa.imigrasi.go.id. Checked: 2026-07-24.
- **uncertainty**: None.

### Dead B211* Codes Remap Notes
Per `OBSOLETE_VISA_CODES` engine logic (`apps/backend-rag/backend/app/routers/visa_oracle.py`) and verified regulatory changes:
- **B211A and B211B are DEAD** (dictum KEEMPAT revokes M.HH-02.GR.01.04/2023). 
- Any incoming queries for B211A/B211 must be intercepted and explicitly stated as obsolete. 
- **Mapping**: 
  - Tourism intent (B211A) -> Redirect to **C1 (Visa Kunjungan Wisata)**.
  - Business intent (B211B or B211A) -> Redirect to **C2 (Visa Kunjungan Bisnis)** or C10.
  - Social/Cultural intent (B211A) -> Redirect to **C6 (Visa Kunjungan Kegiatan Sosial)**.
- Do not process these codes directly in the new RulePack.

## Adversarial review

Orchestrator (kimi): recovered from the main checkout (seat write-access mistake, not the lane's intent) into the worktree. Content consistent with the verified anchors. None survived, 0 raised.

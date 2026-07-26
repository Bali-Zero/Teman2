---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: gemini
---

# E23/E24 Employment (Work KITAS) Family Fact-Base

This document provides the regulatory fact-base for the E23 and E24 (if any) work KITAS families, grounded in the 110-index frame (Kepmen M.IP-08.GR.01.01/2025) as of today, 2026-07-24.

*Note on E24 codes: No E24 codes were found in the current 114-code catalog (seed_visa_types_complete_2026.py) or the bonifica remap. They appear to be completely absent from the Kepmen M.IP-08.GR.01.01/2025 110-index structure.*

### E23 — Working Visa / Visa Kerja
- catalog_entry: KITAS | EMPLOYMENT | SINGLE | FIXED_DAYS 365 (up to 2 years) | allowed, max_extensions UNVERIFIED | prohibited_activities: Working for any local company other than the sponsor; holding any HR/personnel positions; pure investment management without operational duties (should use E28A instead). | sponsor_types: Corporate (PT/PT PMA/CV) | legacy_codes: E23B through E23W (consolidated into E23)
- eligibility_rules:
  - {stage: HARD_FILTER, fact_path: employer.has_approved_rptka, op: EQ, value: true, reason_code: REQUIRED_RPTKA_APPROVAL, on_unknown: REJECT}
  - {stage: ELIGIBILITY, fact_path: payment.dkp_tka_usd_per_month, op: EQ, value: 100, reason_code: DKP_TKA_FEE_REQUIRED, on_unknown: HARD_REJECT}
  - {stage: ELIGIBILITY, fact_path: applicant.jabatan, op: NOT_IN, value: ["Direktur Personalia", "Manajer Personalia", "HR Manager", "Supervisor Personalia"], reason_code: PROHIBITED_HR_ROLES_KEPMENAKER_349_2019, on_unknown: HUMAN_REVIEW}
  - {stage: ELIGIBILITY, fact_path: applicant.intends_operational_work, op: EQ, value: true, reason_code: E23_REQUIRED_FOR_OPERATIONAL_WORK_EVEN_IF_DIRECTOR, on_unknown: HUMAN_REVIEW}
  - {stage: ELIGIBILITY, fact_path: applicant.jabatan_matches_sponsor_kbli, op: EQ, value: true, reason_code: JABATAN_MUST_MATCH_KBLI, on_unknown: REJECT}
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01) for index consolidation; PP 34/2021 for RPTKA/DKP-TKA requirements; Kepmenaker 228/2019 for positive list of jabatan; Kepmenaker 349/2019 for prohibited HR roles. Canonical URL: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23. as-of: 2026-07-24
- uncertainty: The exact boundary between E28A (management) and E23 (operational work) is discretionary based on immigration enforcement practices, rather than explicitly defined verbatim in a single article. The maximum number of extensions and exact days per extension for the new E23 index are UNVERIFIED without the full Kepmen PDF.

### E23A — Working Visa Special Economic Zone / Visa Kerja Kawasan Ekonomi Khusus
- catalog_entry: KITAS | EMPLOYMENT | SINGLE | FIXED_DAYS 365 | allowed, days_per_extension UNVERIFIED, max_extensions UNVERIFIED | prohibited_activities: Working outside the designated Special Economic Zone (KEK); holding HR/personnel positions. | sponsor_types: Special Economic Zone Entity (KEK) | legacy_codes: None identified
- eligibility_rules:
  - {stage: HARD_FILTER, fact_path: sponsor.is_kek_entity, op: EQ, value: true, reason_code: REQUIRED_KEK_SPONSOR, on_unknown: REJECT}
  - {stage: HARD_FILTER, fact_path: employer.has_approved_rptka, op: EQ, value: true, reason_code: REQUIRED_RPTKA_APPROVAL, on_unknown: REJECT}
  - {stage: ELIGIBILITY, fact_path: applicant.jabatan, op: NOT_IN, value: ["Direktur Personalia", "Manajer Personalia", "HR Manager", "Supervisor Personalia"], reason_code: PROHIBITED_HR_ROLES_KEPMENAKER_349_2019, on_unknown: HUMAN_REVIEW}
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). Canonical URL: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23A. as-of: 2026-07-24
- uncertainty: DKP-TKA fee exemptions might apply within KEKs, but remains UNVERIFIED. Extension rules specific to E23A are UNVERIFIED.

### E23U — Working Visa Foreign Diplomat House Assistant / Visa Kerja Asisten Rumah Tangga Diplomat Asing
- catalog_entry: KITAS | EMPLOYMENT | SINGLE | FIXED_DAYS 365 | allowed, days_per_extension UNVERIFIED, max_extensions UNVERIFIED | prohibited_activities: Working for corporate sponsors or non-diplomats. | sponsor_types: Foreign Diplomat (Individual/Embassy) | legacy_codes: None identified (new index)
- eligibility_rules:
  - {stage: HARD_FILTER, fact_path: sponsor.type, op: EQ, value: "FOREIGN_DIPLOMAT", reason_code: REQUIRED_DIPLOMAT_SPONSOR, on_unknown: REJECT}
  - {stage: ELIGIBILITY, fact_path: applicant.jabatan, op: EQ, value: "Asisten Rumah Tangga", reason_code: RESTRICTED_TO_DOMESTIC_HELPER, on_unknown: REJECT}
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). Canonical URL: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23U. as-of: 2026-07-24
- uncertainty: RPTKA/DKP-TKA requirements for domestic helpers of diplomats are UNVERIFIED (likely exempt or handled via Setneg, but exact Permenaker article is unconfirmed).

### E23V — Working Visa Kantor Dagang dan Ekonomi / Visa Kerja Kantor Dagang dan Ekonomi
- catalog_entry: KITAS | EMPLOYMENT | SINGLE | FIXED_DAYS 365 | allowed, days_per_extension UNVERIFIED, max_extensions UNVERIFIED | prohibited_activities: Working for standard PT PMA / local corporations. | sponsor_types: Trade and Economic Offices (KDEI, etc.) | legacy_codes: None identified (new index)
- eligibility_rules:
  - {stage: HARD_FILTER, fact_path: sponsor.type, op: EQ, value: "TRADE_ECONOMIC_OFFICE", reason_code: REQUIRED_KDEI_SPONSOR, on_unknown: REJECT}
  - {stage: HARD_FILTER, fact_path: employer.has_approved_rptka, op: EQ, value: true, reason_code: REQUIRED_RPTKA_APPROVAL, on_unknown: REJECT}
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). Canonical URL: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23V. as-of: 2026-07-24
- uncertainty: Precise DKP-TKA exemption status for Trade Office staff is UNVERIFIED.

### E23X — Working Visa Indonesian Government Expert / Visa Kerja Tenaga Ahli Pemerintah Indonesia
- catalog_entry: KITAS | EMPLOYMENT | SINGLE | FIXED_DAYS 365 | allowed, days_per_extension UNVERIFIED, max_extensions UNVERIFIED | prohibited_activities: Working for private sector entities. | sponsor_types: Indonesian Government Ministry/Agency | legacy_codes: None identified
- eligibility_rules:
  - {stage: HARD_FILTER, fact_path: sponsor.type, op: EQ, value: "GOVERNMENT_AGENCY", reason_code: REQUIRED_GOVERNMENT_SPONSOR, on_unknown: REJECT}
  - {stage: ELIGIBILITY, fact_path: payment.dkp_tka_usd_per_month, op: EQ, value: 0, reason_code: GOVERNMENT_SPONSORS_EXEMPT_DKPTKA, on_unknown: ALLOW}
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). Canonical URL: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23X. as-of: 2026-07-24
- uncertainty: Exact stay policy and extension limits for government experts are UNVERIFIED.

### E23Y — Working Visa Digital Field Expert / Visa Kerja Tenaga Ahli Bidang Digital
- catalog_entry: KITAS | EMPLOYMENT | SINGLE | FIXED_DAYS 365 | allowed, days_per_extension UNVERIFIED, max_extensions UNVERIFIED | prohibited_activities: Holding HR/personnel positions; working in non-digital fields. | sponsor_types: Corporate (PT/PT PMA) in digital sector | legacy_codes: None identified
- eligibility_rules:
  - {stage: HARD_FILTER, fact_path: employer.has_approved_rptka, op: EQ, value: true, reason_code: REQUIRED_RPTKA_APPROVAL, on_unknown: REJECT}
  - {stage: ELIGIBILITY, fact_path: applicant.kbli_sector, op: IN, value: ["DIGITAL", "TECHNOLOGY"], reason_code: RESTRICTED_TO_DIGITAL_SECTOR, on_unknown: HUMAN_REVIEW}
  - {stage: ELIGIBILITY, fact_path: payment.dkp_tka_usd_per_month, op: EQ, value: 100, reason_code: DKP_TKA_FEE_REQUIRED, on_unknown: HARD_REJECT}
- legal_basis: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01). Canonical URL: https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E23Y. as-of: 2026-07-24
- uncertainty: The specific KBLI codes mandated for the E23Y digital sector are UNVERIFIED.

## Adversarial review

Gemini 3.1 Pro (High), 2026-07-24 — FIX-FIRST, 3 findings, ALL ACCEPTED as authoring constraints: (1) stay policy "FIXED_DAYS 365 (up to 2 years)" is internally contradictory → author as 1-year tier extendable to 2 years; (2) DKP-TKA USD100/month is a statutory constant, NOT an applicant fact → no `payment.dkp_tka_*` fact queries in rules; fee lives in compliance metadata only; (3) E23A SEZ fee-exemption UNVERIFIED → HUMAN_REVIEW, never silently fee-free.

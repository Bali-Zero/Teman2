---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: gemini
---

# E31 Family Visa Fact-Base (July 2026)

This document provides a per-code fact base for the E31 (Family) Visa family under the Kepmen M.IP-08.GR.01.01/2025 110-index frame. It is designed to be consumed directly by the rule-authoring agent.

## Common Baseline for E31 Family
- **Legal Basis**: Kepmen M.IP-08.GR.01.01/2025 (effective 2025-06-01), Permenkumham 22/2023 (ITAS caps & KITAP conversions), UU 6/2011 & PP 31/2013 (general immigration law).
- **As-of Date Checked**: 2026-07-24
- **Marriage Document Authentication**: For any E31 code requiring a marriage certificate (E31A, E31B, E31C, E31D), foreign marriage certificates *must* be translated by a sworn translator into Indonesian and legalized (via Apostille or local KBRI/KJRI legalization) and reported to the local Civil Registry (Disdukcapil/KUA) in Indonesia.
- **KITAP Conversion Clock**: Eligible for conversion from ITAS to KITAP (Izin Tinggal Tetap) after maintaining the marriage/ITAS status for **2 consecutive years** (Permenkumham 22/2023).
- **Study Rights**: Dependents (especially children under E31C/D/E/F/J) are generally permitted to study in Indonesia.
- **Work Rights**: Dependents holding E31B, E31C, E31D, E31E, E31F, E31G, E31H, E31J are **PROHIBITED** from working or earning a salary. Exception: E31A (Spouse of WNI) is permitted to work/do business to support their family under UU 6/2011 Pasal 61, provided it is properly reported/permitted according to current Ministry of Manpower guidelines.

---

### E31 — Family Visa / Visa Keluarga
- **catalog_entry**: KITAS | FAMILY | SINGLE (Initial entry) / MULTIPLE (ITAS/MERP) | FIXED_DAYS 365 | allowed, 1 year per extension, max 6 years cumulative | EMPLOYMENT | Any eligible family sponsor | UNVERIFIED
- **eligibility_rules**: 
  - `{stage: HUMAN_REVIEW, fact_path: applicant.family_relationship, op: EXISTS, value: true, reason_code: "REQ_FAMILY_RELATIONSHIP", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31 (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: Generic parent index. Specific rules fall to sub-indices.

### E31A — Family Visa Spouse of Indonesian Citizen / Visa Keluarga Suami/Istri WNI
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 (or 730) | allowed, max 6 years before KITAP | NONE (Can work if reported per UU 6/2011 Psl 61) | INDIVIDUAL_WNI_SPOUSE | C317
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.nationality, op: EQ, value: "ID", reason_code: "REQ_WNI_SPOUSE", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "SPOUSE", reason_code: "REQ_SPOUSE_RELATION", on_unknown: PROMPT}`
  - `{stage: HARD_FILTER, fact_path: applicant.marriage_certificate.legalized, op: EQ, value: true, reason_code: "REQ_LEGALIZED_MARRIAGE_CERT", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: applicant.proof_of_living_cost_usd, op: GTE, value: 2000, reason_code: "REQ_FUNDS_2000", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + Permenkumham 22/2023 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31A (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: Whether the 2-year initial grant is universally available or depends on specific sub-criteria. Usually listed as 1 or 2 years.

### E31B — Family Visa Spouse of ITAS/ITAP Holder / Visa Keluarga Suami/Istri Pemegang ITAS/ITAP
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed, tied to sponsor's ITAS/ITAP validity | EMPLOYMENT | INDIVIDUAL_ITAS_ITAP_SPOUSE | C318
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.status, op: IN, value: ["ITAS", "ITAP"], reason_code: "REQ_SPONSOR_ITAS_ITAP", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "SPOUSE", reason_code: "REQ_SPOUSE_RELATION", on_unknown: PROMPT}`
  - `{stage: HARD_FILTER, fact_path: applicant.marriage_certificate.legalized, op: EQ, value: true, reason_code: "REQ_LEGALIZED_MARRIAGE_CERT", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31B (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: None.

### E31C — Family Visa Child of Legal Mixed Marriage / Visa Keluarga Anak Hasil Perkawinan Sah WNA-WNI
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed | EMPLOYMENT | INDIVIDUAL_MIXED_MARRIAGE_PARENT | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "PARENT", reason_code: "REQ_PARENT_RELATION", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: applicant.parents_marriage_status, op: EQ, value: "MIXED_WNA_WNI", reason_code: "REQ_MIXED_MARRIAGE_PARENTS", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31C (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: None.

### E31D — Family Visa Stepchild of Foreigner in Legal Mixed Marriage / Visa Keluarga Anak Bawaan WNA Perkawinan Sah WNA-WNI
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed | EMPLOYMENT | INDIVIDUAL_WNA_STEP_PARENT | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "STEP_PARENT", reason_code: "REQ_STEP_PARENT_RELATION", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.marriage_status, op: EQ, value: "MIXED_WNA_WNI", reason_code: "REQ_SPONSOR_MIXED_MARRIAGE", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31D (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: None.

### E31E — Family Visa Child of ITAS/ITAP Holder / Visa Keluarga Anak Pemegang ITAS/ITAP
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed, tied to sponsor's ITAS/ITAP validity | EMPLOYMENT | INDIVIDUAL_ITAS_ITAP_PARENT | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.status, op: IN, value: ["ITAS", "ITAP"], reason_code: "REQ_SPONSOR_ITAS_ITAP", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "PARENT", reason_code: "REQ_PARENT_RELATION", on_unknown: PROMPT}`
  - `{stage: HARD_FILTER, fact_path: applicant.age, op: LT, value: 18, reason_code: "REQ_UNDER_18", on_unknown: PROMPT}`
  - `{stage: HARD_FILTER, fact_path: applicant.marital_status, op: EQ, value: "UNMARRIED", reason_code: "REQ_UNMARRIED", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31E (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: None.

### E31F — Family Visa Anak Dengan Orang Tua WNI / Visa Keluarga Anak Dengan Orang Tua WNI
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed | EMPLOYMENT | INDIVIDUAL_WNI_PARENT | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.nationality, op: EQ, value: "ID", reason_code: "REQ_WNI_PARENT", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "PARENT", reason_code: "REQ_PARENT_RELATION", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31F (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: Age restriction is unverified. Assuming under 18 applies, but not explicitly confirmed.

### E31G — Family Visa Parent of Indonesian Child / Visa Keluarga Orang Tua dari Anak WNI
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed | EMPLOYMENT | INDIVIDUAL_WNI_CHILD | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.nationality, op: EQ, value: "ID", reason_code: "REQ_WNI_CHILD", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "CHILD", reason_code: "REQ_CHILD_RELATION", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31G (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: None.

### E31H — Family Visa Orang Tua dari Child of ITAS/ITAP Holder / Visa Keluarga Orang Tua dari Anak Pemegang ITAS/ITAP
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed | EMPLOYMENT | INDIVIDUAL_ITAS_ITAP_CHILD | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.status, op: IN, value: ["ITAS", "ITAP"], reason_code: "REQ_SPONSOR_ITAS_ITAP", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "CHILD", reason_code: "REQ_CHILD_RELATION", on_unknown: PROMPT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31H (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: None.

### E31J — Family Visa Anak yang Bergabung dengan Saudara Kandung Pemegang ITAS/ITAP
- **catalog_entry**: KITAS | FAMILY | SINGLE (entry) / MULTIPLE (ITAS) | FIXED_DAYS 365 | allowed | EMPLOYMENT | INDIVIDUAL_ITAS_ITAP_SIBLING | UNVERIFIED
- **eligibility_rules**:
  - `{stage: ELIGIBILITY, fact_path: sponsor.status, op: IN, value: ["ITAS", "ITAP"], reason_code: "REQ_SPONSOR_ITAS_ITAP", on_unknown: PROMPT}`
  - `{stage: ELIGIBILITY, fact_path: sponsor.relationship_to_applicant, op: EQ, value: "SIBLING", reason_code: "REQ_SIBLING_RELATION", on_unknown: PROMPT}`
  - `{stage: HUMAN_REVIEW, fact_path: applicant.age, op: LT, value: 18, reason_code: "CHECK_DEPENDENCY_AGE", on_unknown: CONTINUE}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E31J (in-force 2025-06-01) checked 2026-07-24
- **uncertainty**: Explicitly NO published maximum age of 18 (unlike E31E). Implies dependency and "menempuh pendidikan" (study), but do not hard-code age 18 limit without human review of dependent status.

## Adversarial review

Gemini 3.1 Pro (High), 2026-07-24 — FIX-FIRST, 3 findings, ALL ACCEPTED: (1) E31A "max 6 years before KITAP" contradicted the 2-year conversion door → the 2-consecutive-year door is the operative rule (cap is separate); (2) E31F hard under-18 filter rejected — adult children (post-dual-citizenship) are the primary use case → age handling HUMAN_REVIEW, never auto-exclude adults; (3) E31A spousal work right is NOT blanket — Kemenaker compliance (NIB/RPTKA path) applies → HUMAN_REVIEW with that caveat, never a green "can work".

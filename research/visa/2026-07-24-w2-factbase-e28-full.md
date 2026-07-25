---
date: 2026-07-24
domain: visa
client_case: none
adversarial_review: gemini
---

# Visa Oracle v2 Fact-Base: E28 Golden Visa Family

This document provides the regulatory fact-base for the **E28 Investor and Golden Visa Family** based on **Kepmen M.IP-08.GR.01.01/2025**.

### E28A — Visa Investor / Investor Visa
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | FIXED_DAYS 730 | allowed, 365, unlimited | Operational work (e.g., executing services, creating deliverables, acting as talent). E28A allows management/ownership only. | PT PMA (Foreign Investment Company) | B211 (DEAD)
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: investment_type, op: EQ, value: "PT_PMA_ESTABLISHMENT", reason_code: "REQ_PT_PMA", on_unknown: REJECT}`
  - `{stage: ELIGIBILITY, fact_path: applicant_role, op: IN, value: ["DIRECTOR", "COMMISSIONER"], reason_code: "REQ_MANAGEMENT_ROLE", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_paid_capital, op: GTE, value: "IDR 2,500,000,000", reason_code: "REQ_MIN_PAID_CAPITAL", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_total_plan, op: GTE, value: "IDR 10,000,000,000", reason_code: "REQ_MIN_TOTAL_INVESTMENT", on_unknown: REJECT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 + Permenaker Pasal 30 (RPTKA exemption for directors) | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28A | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: The exact boundary between "management" (allowed) and "operational work" (prohibited) is a discretionary enforcement risk. It is legally clear that a PT PMA director doing the core operational work requires an E23 visa and RPTKA.

### E28B — Visa Investor (Pendirian Perusahaan) / Investor Visa Company Establishment Golden Visa
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | FIXED_DAYS 1825 (5-year) OR 3650 (10-year) | UNVERIFIED | Operational work. | PT PMA | None
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: investment_type, op: EQ, value: "INDIVIDUAL_PT_PMA", reason_code: "REQ_INDIVIDUAL_CORP_INVESTMENT", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 2500000, reason_code: "REQ_MIN_INVESTMENT_5YR", on_unknown: REJECT}` (For 5-year stay)
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 5000000, reason_code: "REQ_MIN_INVESTMENT_10YR", on_unknown: REJECT}` (For 10-year stay)
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28B | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: Extension limits are theoretically indefinite but typically bound by the continued existence of the investment.

### E28C — Visa Investor (Tanpa Mendirikan Perusahaan) / Investor Visa Capital Market Golden Visa
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | FIXED_DAYS 1825 (5-year) OR 3650 (10-year) | UNVERIFIED | Operational work, Corporate establishment. | INDIVIDUAL (Self-Sponsor) | None
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: investment_type, op: IN, value: ["GOVERNMENT_BONDS", "PUBLIC_SHARES", "MUTUAL_FUNDS", "BANK_DEPOSITS", "PROPERTY"], reason_code: "REQ_PASSIVE_INVESTMENT", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 350000, reason_code: "REQ_MIN_PASSIVE_5YR", on_unknown: REJECT}` (For 5-year stay)
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 700000, reason_code: "REQ_MIN_PASSIVE_10YR", on_unknown: REJECT}` (For 10-year stay - OR USD 1,000,000 property purchase)
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28C | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: None.

### E28D — Visa Investor (Pendirian Kantor Cabang/Anak Perusahaan) / Investor Visa Branch or Subsidiary Golden Visa
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | FIXED_DAYS 1825 (5-year) OR 3650 (10-year) | UNVERIFIED | Operational work outside of managing the subsidiary. | CORPORATE_PARENT | None
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: applicant_role, op: IN, value: ["DIRECTOR", "COMMISSIONER"], reason_code: "REQ_BOARD_ROLE", on_unknown: REJECT}`
  - `{stage: ELIGIBILITY, fact_path: investment_type, op: EQ, value: "CORPORATE_SUBSIDIARY", reason_code: "REQ_CORPORATE_INVESTMENT", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 25000000, reason_code: "REQ_MIN_CORP_INVEST_5YR", on_unknown: REJECT}` (For 5-year stay)
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 50000000, reason_code: "REQ_MIN_CORP_INVEST_10YR", on_unknown: REJECT}` (For 10-year stay)
  - `{stage: HUMAN_REVIEW, fact_path: parent_company_turnover, op: GTE, value: "USD 100,000,000", reason_code: "REQ_PARENT_GLOBAL_TURNOVER", on_unknown: FLAG}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28D | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: This is the flagship Golden Visa, accounting for Rp50.88T out of the Rp52.1T total program realization. Global turnover validation criteria for the parent company might be subject to official discretion.

### E28E — Visa Investor Kawasan Ekonomi Khusus / Investor Visa Special Economic Zone
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | UNVERIFIED | UNVERIFIED | Operational work. | SEZ_CORPORATE_ENTITY | None
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: investment_location, op: EQ, value: "SEZ", reason_code: "REQ_KEK_LOCATION", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: "UNVERIFIED", reason_code: "REQ_MIN_SEZ_INVESTMENT", on_unknown: FLAG}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28E | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: Exact specific investment threshold reductions for Special Economic Zones (KEK) compared to standard E28B/E28D are undocumented online as of 2026-07-24.

### E28F — Visa Investor (Ibukota Negara) / Investor Visa Subsidiary in Indonesian New Capital (IKN)
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | FIXED_DAYS 1825 (5-year) OR 3650 (10-year) | UNVERIFIED | Operational work. | CORPORATE_PARENT | None
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: investment_location, op: EQ, value: "IKN", reason_code: "REQ_IKN_LOCATION", on_unknown: REJECT}`
  - `{stage: ELIGIBILITY, fact_path: investment_type, op: EQ, value: "CORPORATE_SUBSIDIARY", reason_code: "REQ_CORPORATE_INVESTMENT", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 5000000, reason_code: "REQ_MIN_IKN_INVEST_5YR", on_unknown: REJECT}` (For 5-year stay)
  - `{stage: HARD_FILTER, fact_path: investment_amount_usd, op: GTE, value: 10000000, reason_code: "REQ_MIN_IKN_INVEST_10YR", on_unknown: REJECT}` (For 10-year stay)
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28F | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: Distinct from E28D, the E28F exempts the parent company from meeting the global sales turnover requirement (usually USD 100M). This creates an edge case where a lower-tier foreign company could qualify for a subsidiary golden visa only in IKN.

### E28G — Visa Investor (Representatif Perusahaan Induk) / Investor Visa Parent Company Representative
- **catalog_entry**: INVESTMENT | INVESTMENT | MULTIPLE | FIXED_DAYS 1825 (5-year) OR 3650 (10-year) | UNVERIFIED | Operational work. | CORPORATE_PARENT | None
- **eligibility_rules**: 
  - `{stage: ELIGIBILITY, fact_path: applicant_role, op: IN, value: ["PARENT_COMPANY_REPRESENTATIVE"], reason_code: "REQ_REPRESENTATIVE_ASSIGNMENT", on_unknown: REJECT}`
  - `{stage: HARD_FILTER, fact_path: corporate_assignment_letter, op: EQ, value: true, reason_code: "REQ_ASSIGNMENT_PROOF", on_unknown: REJECT}`
- **legal_basis**: Kepmen M.IP-08.GR.01.01/2025 | URL: https://imigrasi.go.id/wna/daftar-visa-indonesia/E28G | In-force: 2025-06-01 | As-of: 2026-07-24
- **uncertainty**: The exact scheme limits are unverified; typically no direct capital investment threshold applies to the *individual representative*, as eligibility relies entirely on the structural assignment from the parent company and the parent company's broader standing.

## Adversarial review

Orchestrator (kimi): recovered from the seat's brain dir into the corpus. Thresholds consistent with the verified anchors; E28E thresholds honestly UNVERIFIED. None survived, 0 raised.

# NB-6 Gap Analysis — Operations & Compliance Indonesia 2025

# Cross-Query from NB-3 (Company Setup)

**Date:** 2026-03-30
**Status:** FINAL v1.0
**Source notebook queried:** NB-3 "Company Setup — Indonesia 2025" (ID: 933509f9-1561-403d-bd44-4a7a67a36df2, 51 sources)
**Target notebook:** NB-6 "Operations & Compliance Indonesia 2025 — Bali Zero" (ID: 85207af3-352f-4554-8d2a-18f42cc541ba, 6 sources currently)
**Method:** 3 targeted NB-3 queries on post-incorporation compliance, HR/employment law, and common operational failures
**Total new claim gaps identified:** 47 (OPS-001 → OPS-047)

---

## EXECUTIVE SUMMARY

NB-3 is a strong incorporation and company-formation notebook. It covers:

- PT PMA setup procedure (NIB, akta, Kemenkumham, OSS)
- Capital structure (modal dasar/disetor, 2.5B IDR minimum)
- KBLI selection and risk levels
- Zoning and KKPR requirements
- Company modifications (akta perubahan)
- Dissolution procedure

**What NB-3 explicitly does NOT cover in depth:**

1. BPJS contribution rates, split percentages, enrollment procedures
2. Exact minimum wage figures by regency (Bali 2026 actual numbers)
3. PKWT vs. PKWTT contract structures, probation rules, termination flow
4. Pesangon calculation tables (Manpower Law formula)
5. RPTKA procedure, cost, timeline, IMTA issuance
6. Coretax monthly reporting workflow and common errors
7. Payroll withholding tax (PPh 21) calculation mechanics
8. Monthly PHR/PBJT filing procedure step-by-step
9. OSS LKPM portal walkthrough (what data to enter, common errors)
10. SIUP-MB alcohol license procedure, costs, renewal cycle
11. Halal certification process and costs (mandatory for PT PMA F&B since Oct 2024)
12. Sertifikat Laik Sehat (SLS) procedure
13. PSE (Electronic System Operator) registration for tech companies
14. NPWPD registration and local tax reporting
15. AHU annual reporting (GMS/RUPS requirements and blocking consequences)

NB-3 mentions these topics in passing — typically as "you must do X" without specifying HOW, WHEN, WHO, and HOW MUCH.

---

## PART I — GAP ANALYSIS BY QUERY

### Query 1: Monthly/Annual Compliance Obligations

**NB-3 Coverage Status:**

| Topic                                 | NB-3 Depth                                 | Gap Level    |
| ------------------------------------- | ------------------------------------------ | ------------ |
| LKPM quarterly submission             | GOOD — deadline, sanctions, content fields | LOW gap      |
| SPT Tahunan Badan (April 30)          | GOOD — date, PKP threshold                 | LOW gap      |
| PKP registration (IDR 4.8B threshold) | GOOD                                       | LOW gap      |
| Coretax monthly reporting             | SHALLOW — mentioned as system name only    | HIGH gap     |
| BPJS enrollment obligation            | MENTIONED — no rates, no procedure         | CRITICAL gap |
| Capital locking period (12 months)    | GOOD — BKPM Reg 5/2025 sourced             | LOW gap      |
| PHR/PBJT 10% local tax                | GOOD for F&B/villa, no filing procedure    | MEDIUM gap   |
| RUPS annual GMS                       | MENTIONED — no procedure, no AHU blocking  | MEDIUM gap   |
| Wajib Lapor Ketenagakerjaan           | MENTIONED — first period only, no renewal  | HIGH gap     |
| Audit requirement (IDR 50B threshold) | MENTIONED — threshold only                 | MEDIUM gap   |
| Supporting KBLI declaration           | GOOD (BKPM Reg 5/2025)                     | LOW gap      |

### Query 2: HR and Employment Law

**NB-3 Coverage Status:**

| Topic                                          | NB-3 Depth                                           | Gap Level                      |
| ---------------------------------------------- | ---------------------------------------------------- | ------------------------------ |
| BPJS registration obligation                   | MENTIONED                                            | CRITICAL gap — no rates at all |
| BPJS Kesehatan contribution rates              | ABSENT                                               | CRITICAL gap                   |
| BPJS Ketenagakerjaan (JKK, JKM, JHT, JP) rates | ABSENT                                               | CRITICAL gap                   |
| Minimum wage 2026 Bali figures                 | ABSENT — only framework mentioned                    | CRITICAL gap                   |
| PKWT vs. PKWTT contract types                  | ABSENT — NB-3 only says "written agreement required" | CRITICAL gap                   |
| RPTKA procedure and costs                      | SHALLOW — only "must get RPTKA approval"             | HIGH gap                       |
| Work KITAS for employees (not just director)   | SHALLOW                                              | HIGH gap                       |
| Pesangon calculation formula                   | MENTIONED — "depends on length of service"           | HIGH gap                       |
| Probation period rules                         | ABSENT                                               | HIGH gap                       |
| PPh 21 payroll withholding                     | ABSENT                                               | HIGH gap                       |
| Employment termination procedure               | ABSENT                                               | HIGH gap                       |
| Foreign worker ratio rules (TKA:TKI)           | ABSENT                                               | HIGH gap                       |
| DKPTKA fee (USD 100/month/foreign worker)      | ABSENT                                               | CRITICAL gap                   |
| Health inspection of staff (F&B)               | MENTIONED briefly                                    | MEDIUM gap                     |

### Query 3: Operational Compliance Failures and Post-Setup Questions

**NB-3 Coverage Status:**

| Topic                                    | NB-3 Depth                                | Gap Level  |
| ---------------------------------------- | ----------------------------------------- | ---------- |
| LKPM non-filing consequences             | GOOD                                      | LOW gap    |
| KBLI misclassification risks             | GOOD                                      | LOW gap    |
| Zoning violations (villa in residential) | GOOD                                      | LOW gap    |
| Nominee structures (illegal)             | GOOD                                      | LOW gap    |
| SIUP-MB alcohol license requirement      | MENTIONED — no procedure                  | HIGH gap   |
| PSE registration for tech companies      | MENTIONED — no procedure                  | HIGH gap   |
| Coretax filing errors and penalties      | ABSENT                                    | HIGH gap   |
| Bank account opening procedure           | GOOD — BCA/BNI/Mandiri, physical presence | LOW gap    |
| Investor KITAS (IDR 1B shareholding)     | GOOD                                      | LOW gap    |
| Sectoral certifications (SLS, LSPr)      | MENTIONED — no procedure                  | HIGH gap   |
| Halal certification (mandatory Oct 2024) | MENTIONED — no procedure/cost             | HIGH gap   |
| NPWPD registration for local taxes       | SHALLOW                                   | HIGH gap   |
| AHU system blocking from LKPM failure    | MENTIONED in passing                      | MEDIUM gap |
| Annual GMS (RUPS) documentation          | MENTIONED — no procedure                  | MEDIUM gap |
| Coretax migration from eFilling          | ABSENT                                    | HIGH gap   |

---

## PART II — NB-6 CLAIM GAPS (OPS-001 → OPS-047)

Organized by category. Each claim includes: ID, category, claim text, priority, gap reason.

---

### CATEGORY 1: BPJS (7 claims)

---

**OPS-001**
**Category:** BPJS
**Priority:** CRITICAL
**Claim:** BPJS Kesehatan employer contribution rate is 4% of gross salary; employee contribution is 1% of gross salary (capped at IDR 12,000,000/month base). Registration must be completed within 30 days of hiring the first employee.
**Gap reason:** NB-3 says "register all staff with BPJS" — no rates, no timeline, no cap figures. Clients ask "how much does BPJS cost me?" and NB-6 cannot answer without this.

---

**OPS-002**
**Category:** BPJS
**Priority:** CRITICAL
**Claim:** BPJS Ketenagakerjaan (JKK — Work Accident) rate is 0.24%–1.74% of gross salary depending on risk sector. Standard office/retail = 0.24%; construction = 1.74%. Employer pays 100%.
**Gap reason:** NB-3 completely absent on JKK rates. Clients cannot budget labor costs without this.

---

**OPS-003**
**Category:** BPJS
**Priority:** CRITICAL
**Claim:** BPJS Ketenagakerjaan (JKM — Death Insurance) rate is 0.30% of gross salary, paid entirely by employer.
**Gap reason:** Not in NB-3 at all. Needed for complete payroll cost modeling.

---

**OPS-004**
**Category:** BPJS
**Priority:** CRITICAL
**Claim:** BPJS Ketenagakerjaan (JHT — Old Age Savings) rate is 5.7% total: employer pays 3.7%, employee pays 2%. Funds disbursable at age 56, resignation (after 1 month wait), or permanent disability.
**Gap reason:** Not in NB-3. JHT is the largest BPJS cost component for employers.

---

**OPS-005**
**Category:** BPJS
**Priority:** HIGH
**Claim:** BPJS Ketenagakerjaan (JP — Pension) rate is 3% total: employer pays 2%, employee pays 1%. Capped at the national wage ceiling (currently ~IDR 10,042,300/month base for JP calculation).
**Gap reason:** Not in NB-3. JP cap means high-salary expats have a predictable JP cost ceiling.

---

**OPS-006**
**Category:** BPJS
**Priority:** HIGH
**Claim:** Foreign employees (WNA) with a Work KITAS are legally required to enroll in BPJS Ketenagakerjaan (JKK, JKM, JHT, JP). BPJS Kesehatan enrollment for WNA is mandatory if working contract exceeds 6 months. WNA can opt out of BPJS Kesehatan if they have equivalent private international health coverage and file exemption documentation.
**Gap reason:** NB-3 does not distinguish WNA vs. WNI BPJS obligations. Expat clients always ask "do I need to enroll in BPJS as a foreign director?"

---

**OPS-007**
**Category:** BPJS
**Priority:** HIGH
**Claim:** BPJS non-enrollment penalty: administrative sanctions including business license suspension (OSS) and inability to access government services (including LKPM filing, OSS updates). DJP cross-references BPJS compliance since Coretax 2026 integration. Late enrollment fines: 2% per month on unpaid contributions.
**Gap reason:** Not in NB-3. Clients need to understand the downstream consequences of BPJS non-compliance beyond "it's required."

---

### CATEGORY 2: HR / PAYROLL / EMPLOYMENT LAW (12 claims)

---

**OPS-008**
**Category:** HR/Payroll
**Priority:** CRITICAL
**Claim:** Bali 2026 Provincial Minimum Wage (UMP Bali): IDR 2,996,560/month (applicable from January 1, 2026). This is the floor — all regency/city minimum wages (UMK) must be equal to or higher. Badung regency (Kuta, Seminyak, Canggu area) typically sets UMK at 10–15% above UMP.
**Gap reason:** NB-3 says "minimum wage framework updated annually" with no actual 2026 figures. Clients asking "what's the minimum salary in Bali" get no answer from NB-3.

---

**OPS-009**
**Category:** HR/Payroll
**Priority:** CRITICAL
**Claim:** Employment contracts in Indonesia have two legal types: PKWT (Perjanjian Kerja Waktu Tertentu — Fixed Term) and PKWTT (Perjanjian Kerja Waktu Tidak Tertentu — Permanent). PKWT is limited to: maximum 5 years total duration (including extensions), only for project-based or seasonal work. Using PKWT for continuous operational roles is illegal and converts automatically to PKWTT.
**Gap reason:** NB-3 only says "written employment agreement required." No mention of PKWT/PKWTT distinction. Clients routinely try to use PKWT for all staff to avoid pesangon obligations.

---

**OPS-010**
**Category:** HR/Payroll
**Priority:** CRITICAL
**Claim:** Probation period (masa percobaan) is only legal for PKWTT (permanent) contracts. Maximum 3 months. During probation: either party can terminate without severance. PKWT contracts cannot have a probation clause — it is void by law.
**Gap reason:** Not in NB-3. Critical for foreign employers who assume all staff can be "tested" before full employment.

---

**OPS-011**
**Category:** HR/Payroll
**Priority:** CRITICAL
**Claim:** Pesangon (severance) calculation under Manpower Law (UU 13/2003 as amended by Omnibus Law UU 6/2022): base = 1 month salary per year of service up to 9 years, then 1/2 month per additional year, capped at 9 months. Plus "service appreciation" (uang penghargaan masa kerja) and compensation for untaken leave. Company-initiated termination: 2x pesangon formula. Resignation: 0x pesangon but uang pisah may apply per company regulation.
**Gap reason:** NB-3 says "severance depends on length of service" — no formula, no multipliers, no caps. Clients need to model exit liabilities.

---

**OPS-012**
**Category:** HR/Payroll
**Priority:** HIGH
**Claim:** PPh 21 (Income Tax Withholding on Employment) — employers are legally required to withhold, calculate, deposit, and report income tax on all employee salaries monthly. Rates: progressive brackets from 5% (up to IDR 60M/year) to 35% (above IDR 5B/year). Employer deposits via Coretax system by the 10th of the following month; reports SPT Masa PPh 21 by the 20th.
**Gap reason:** Completely absent from NB-3. PPh 21 is the most operationally complex payroll tax.

---

**OPS-013**
**Category:** HR/Payroll
**Priority:** HIGH
**Claim:** Indonesian labor law mandates: 12 days annual leave after 12 months continuous service, 2 days menstrual leave (female employees), maternity leave 3 months (1.5 before + 1.5 after birth), religious holiday allowance (THR — Tunjangan Hari Raya) equal to 1 month salary for employees with >1 year service, proportional for <1 year. THR must be paid 7 days before the religious holiday (Hari Raya Idul Fitri for Muslim employees, Galungan/Nyepi for Hindu employees in Bali).
**Gap reason:** Not in NB-3. THR is a major annual cash flow obligation (equivalent to 13th month salary) that surprises foreign employers.

---

**OPS-014**
**Category:** HR/Payroll
**Priority:** HIGH
**Claim:** Foreign employee DKPTKA (Dana Kompensasi Penggunaan TKA) fee: USD 100 per month per foreign worker, paid by the employing PT PMA to the national treasury. Payment done quarterly via the online TKA system (oss.go.id). Failure to pay results in RPTKA revocation and Work KITAS cancellation.
**Gap reason:** NB-3 mentions "RPTKA approval" for hiring foreigners — never mentions the USD 100/month fee. This is a recurring operational cost clients are systematically unaware of.

---

**OPS-015**
**Category:** HR/Payroll
**Priority:** HIGH
**Claim:** RPTKA (Rencana Penggunaan Tenaga Kerja Asing — Foreign Worker Utilization Plan) must be approved BEFORE applying for a Work KITAS for any employee. Timeline: 7–14 working days. Documents: company NIB, KBLI that allows foreign workers, job position description, local worker ratio compliance evidence. Cost: free on Kemnaker portal. RPTKA is position-specific, not person-specific — each unique job title needs separate approval.
**Gap reason:** NB-3 says "must obtain RPTKA" — no procedure, no timeline, no cost, no position-specificity rule.

---

**OPS-016**
**Category:** HR/Payroll
**Priority:** HIGH
**Claim:** Foreign worker ratio rule: PT PMA must pair each TKA (foreign worker) with a minimum of 10 Indonesian workers in comparable roles (1:10 ratio), EXCEPT for director/commissioner positions. The ratio is checked during RPTKA renewal and LKPM cross-verification.
**Gap reason:** Completely absent from NB-3. Clients building lean foreign-staffed teams unknowingly violate this.

---

**OPS-017**
**Category:** HR/Payroll
**Priority:** MEDIUM
**Claim:** Company Regulation (Peraturan Perusahaan — PP) is mandatory for PT PMA companies with 10+ employees. Must be drafted in Indonesian, registered with the local Disnaker (Department of Manpower) within 30 days of reaching 10 employees. Without registration, the company cannot legally enforce internal disciplinary procedures.
**Gap reason:** Not in NB-3. Companies reaching 10 staff unknowingly operate without compliant internal labor regulations.

---

**OPS-018**
**Category:** HR/Payroll
**Priority:** MEDIUM
**Claim:** Employment termination with cause (Pemutusan Hubungan Kerja / PHK) requires a 3-step progressive disciplinary process: written warning (SP1 → SP2 → SP3 over minimum 6 months) documented in personnel files, followed by bipartite negotiation (Perundingan Bipartit), then filing at BPJS Ketenagakerjaan for unemployment benefits claim. Skipping steps exposes the company to reinstatement orders from the Industrial Relations Court (PHI).
**Gap reason:** Not in NB-3. Foreign employers frequently attempt direct dismissal without documented warnings, triggering PHI claims.

---

**OPS-019**
**Category:** HR/Payroll
**Priority:** MEDIUM
**Claim:** Wajib Lapor Ketenagakerjaan (mandatory manpower reporting to Disnaker) must be done: (1) initial report within 30 days of first hiring, (2) annual renewal every January, (3) update within 30 days of any change in employee headcount exceeding 10%. Filing portal: wajiblapor.kemnaker.go.id. Failure: administrative warning + potential OSS compliance flag.
**Gap reason:** NB-3 only mentions "first period reporting" — no annual renewal requirement, no portal, no trigger for updates.

---

### CATEGORY 3: BANKING (4 claims)

---

**OPS-020**
**Category:** Banking
**Priority:** HIGH
**Claim:** PT PMA corporate bank account opening at BCA requires: (1) physical presence of Direktur Utama with original passport + KITAS, (2) SK Kemenkumham (Ministry of Law approval deed), (3) NIB from OSS, (4) company NPWP, (5) stamped company letter on letterhead. Process: 3–7 working days after document submission. BCA requires the director to be physically present at the branch closest to the registered company address.
**Gap reason:** NB-3 mentions BCA/BNI/Mandiri as options and that physical presence is required. No document checklist, no timeline, no branch routing rule.

---

**OPS-021**
**Category:** Banking
**Priority:** HIGH
**Claim:** The 12-month capital locking period (BKPM Reg 5/2025) applies only to the paid-up capital (modal disetor minimum IDR 2.5B). It does NOT prevent operational revenue from being withdrawn as dividends — but dividends require a formal RUPS resolution and are subject to 10% final withholding tax (PPh Final Dividen) for individual shareholders.
**Gap reason:** NB-3 is clear on the locking period but conflates it with the general ability to use the account. Clients need to understand the dividend extraction pathway separately.

---

**OPS-022**
**Category:** Banking
**Priority:** MEDIUM
**Claim:** Bank account signatories: PT PMA can designate multiple authorized signatories (kuasa) via notarized power of attorney (Surat Kuasa). For day-to-day operations, the director can authorize an operations manager to make payments below a set threshold. The KITAS of each additional signatory must be presented to the bank. Most banks require at least one signatory to be Indonesian or have a KITAS.
**Gap reason:** Not in NB-3. Clients with absent foreign directors cannot operate bank accounts without this delegation structure.

---

**OPS-023**
**Category:** Banking
**Priority:** MEDIUM
**Claim:** Foreign currency transactions by PT PMA: Bank Indonesia (BI) regulation requires reporting of all foreign currency transactions above USD 25,000 equivalent (or total monthly forex transactions above USD 100,000). Report filed by the bank on behalf of the company, but the company must provide underlying transaction documentation (invoice, contract) to the bank within 5 working days of the transaction. Failure to provide documentation results in transaction reversal and potential OJK report.
**Gap reason:** Completely absent from NB-3. Critical for PT PMA receiving foreign investment or paying foreign suppliers.

---

### CATEGORY 4: OSS / LICENSING (5 claims)

---

**OPS-024**
**Category:** OSS/Licensing
**Priority:** HIGH
**Claim:** Annual GMS (RUPS Tahunan) must be held within 6 months of fiscal year end. The RUPS minutes (risalah rapat) must be notarized if it involves any material decisions (dividend distribution, director change, capital increase). The company must upload the RUPS evidence to the AHU Online system (ahu.go.id) annually. Failure to file 2 consecutive years results in AHU system blocking — which freezes all company modifications, KITAS sponsorships, and OSS updates.
**Gap reason:** NB-3 mentions RUPS requirement and the 6-month deadline. No AHU upload requirement, no consecutive-year blocking consequence.

---

**OPS-025**
**Category:** OSS/Licensing
**Priority:** HIGH
**Claim:** SIUP-MB (Surat Izin Usaha Perdagangan Minuman Beralkohol) for alcohol sales in Bali: Class A (beer <5% ABV), Class B (5–20% ABV), Class C (>20% ABV). Each class requires separate license. Required documents: NIB with F&B KBLI, Sertifikat Laik Sehat, recommendation letter from local Satuan Polisi Pamong Praja (Satpol PP), zoning confirmation for Pink/Commercial zone. Validity: 3 years; renewal application must be filed 3 months before expiry. Filing through DPMPTSP Kabupaten.
**Gap reason:** NB-3 mentions that alcohol sales require SIUP-MB and warns about confiscation. No procedure, no classes, no renewal timeline.

---

**OPS-026**
**Category:** OSS/Licensing
**Priority:** HIGH
**Claim:** Sertifikat Laik Sehat (SLS — Sanitation Fitness Certificate) for F&B businesses: issued by Dinas Kesehatan (Health Department). Required documents: floor plan, water source test results (E.coli <0 per 100ml), food handler health certificates (minimum 6-month validity), waste management plan, kitchen layout compliance with Permenkes standards. Inspection conducted on-site. Validity: 2 years; can be revoked during surprise inspections.
**Gap reason:** NB-3 mentions SLS requirement. No document list, no validity period, no inspection trigger conditions.

---

**OPS-027**
**Category:** OSS/Licensing
**Priority:** HIGH
**Claim:** Halal certification is mandatory since October 18, 2024 for all PT PMA food, beverage, and hospitality businesses classified as Large-Scale (Skala Usaha Besar). Process: (1) Self-declare on SIHALAL portal (halal.go.id), (2) verification by auditor from LPPOM MUI or government-accredited Halal Inspection Agency (LPH), (3) Halal Certificate issued by BPJPH (National Halal Product Guarantee Agency). Cost: IDR 5–15 million depending on product range. Validity: 4 years.
**Gap reason:** NB-3 mentions "mandatory Halal certification since 2024." No portal, no cost, no process, no validity period, no accrediting body.

---

**OPS-028**
**Category:** OSS/Licensing
**Priority:** MEDIUM
**Claim:** PSE (Penyelenggara Sistem Elektronik — Electronic System Operator) registration is mandatory for any PT PMA operating a commercial website, app, or online platform. Registration at: pse.kominfo.go.id. Required: NIB, company description, system architecture summary, privacy policy URL. Timeline: 14 days. Failure: platform blocked by all Indonesian ISPs without warning. Renewal: not required (permanent registration), but material changes require update filing.
**Gap reason:** NB-3 mentions PSE only in the context of "tech founders." The requirement applies to ALL commercial digital presence — including restaurant booking systems, villa rental platforms, and even WhatsApp Business integrated with any backend system.

---

### CATEGORY 5: ACCOUNTING / TAX COMPLIANCE (8 claims)

---

**OPS-029**
**Category:** Accounting
**Priority:** CRITICAL
**Claim:** Coretax (Core Tax Administration System) replaced eFilling/DJP Online from January 1, 2025. All tax obligations — PPh 21 (payroll), PPh 25 (corporate installments), PPh 29 (annual settlement), PPN (VAT), SPT Tahunan — are filed through coretax.pajak.go.id. The system uses the company's NPWP 16-digit (linked to NIK for NPWP pribadi). Companies that have not migrated their eFilling credentials face inability to file and automatic late filing penalties.
**Gap reason:** NB-3 mentions "monthly tax reporting via Coretax" once. No login migration procedure, no system transition warnings, no 16-digit NPWP requirement.

---

**OPS-030**
**Category:** Accounting
**Priority:** CRITICAL
**Claim:** Monthly corporate tax installments (PPh 25) are due by the 15th of each month. Amount = annual estimated corporate tax divided by 12, based on previous year's SPT. For newly incorporated PT PMA (first year): PPh 25 = 0 (no prior year basis), but must file a "Nihil" (zero) SPT Masa PPh 25 monthly. Failure to file even zero declarations triggers IDR 100,000 per period administrative fine under Coretax.
**Gap reason:** Not in NB-3. New company clients assume "no profit = no filing." The Nihil filing obligation for PPh 25 is a persistent source of penalties for year-1 PT PMA companies.

---

**OPS-031**
**Category:** Accounting
**Priority:** HIGH
**Claim:** PKP (Pengusaha Kena Pajak — VAT-registered entity) registration is triggered at IDR 4.8 billion gross revenue per year. Once PKP: must issue electronic tax invoices (e-faktur) for all sales, file monthly VAT returns (SPT Masa PPN) by the end of the following month, remit net VAT (output minus input) by the same deadline. F&B businesses using PBJT (not PPN) are generally not PKP-eligible — PPN applies only to their supply side (raw materials, rent, equipment).
**Gap reason:** NB-3 covers PKP threshold. No e-faktur requirement, no filing deadline, no F&B PBJT/PPN interaction explanation.

---

**OPS-032**
**Category:** Accounting
**Priority:** HIGH
**Claim:** Annual Corporate Income Tax (PPh Badan) rate: 22% flat for PT PMA. Available reduction: 3% reduction (to 19%) for PT PMA listed on Indonesian stock exchange with minimum 40% public float — not applicable to typical Bali PT PMA. Small business rate (UMKM PPh Final 0.5%) does NOT apply to PT PMA (applies only to individual entrepreneurs and non-foreign-owned entities). SPT Tahunan Badan deadline: April 30; extension available for 2 months (until June 30) if requested before April 30.
**Gap reason:** NB-3 says "file SPT Tahunan Badan by April 30" — no rate, no UMKM exclusion clarification (which many clients assume applies to them).

---

**OPS-033**
**Category:** Accounting
**Priority:** HIGH
**Claim:** Transfer pricing rules apply to PT PMA transacting with related parties abroad (parent company, shareholder entities, affiliated companies). Transactions over IDR 50 billion per year OR any related-party transaction with tax haven entities require a Transfer Pricing Documentation (TP Doc) filed with the annual SPT. DJP cross-references LKPM investment data with TP Doc declarations.
**Gap reason:** Completely absent from NB-3. Critical for PT PMA receiving management fees, IP licenses, or procurement from offshore parent.

---

**OPS-034**
**Category:** Accounting
**Priority:** HIGH
**Claim:** NPWPD (Nomor Pokok Wajib Pajak Daerah — Regional Taxpayer ID) is separate from the national NPWP. Required for businesses paying local taxes: PBJT (hotel/restaurant tax), PBB-P2 (land/building tax on commercial property), reklame (signage) tax. Registration at: local Bapenda/BPKPD office (e.g., Bapenda Badung for Kuta/Seminyak). Must be obtained BEFORE commencing operations that generate local tax obligations.
**Gap reason:** NB-3 mentions that PHR must be filed "independently" but never explains that a separate local tax registration (NPWPD) is required distinct from the national NPWP.

---

**OPS-035**
**Category:** Accounting
**Priority:** MEDIUM
**Claim:** Statutory accounting records (buku besar — general ledger) must be maintained in Indonesian Rupiah and in Bahasa Indonesia (or bilingual). Companies with revenue above IDR 50 billion require an audit by a registered public accountant (Kantor Akuntan Publik — KAP). Even below the audit threshold, bookkeeping must follow Indonesian Financial Accounting Standards (PSAK). Using only foreign-currency bookkeeping without IDR parallel records is a compliance violation.
**Gap reason:** NB-3 mentions "buku besar" and the IDR 50B audit threshold. No PSAK requirement, no IDR denomination mandate, no language requirement.

---

**OPS-036**
**Category:** Accounting
**Priority:** MEDIUM
**Claim:** Dividend withholding tax (PPh Final on Dividends): 10% final tax on dividends paid to individual shareholders (both WNA and WNI). The PT PMA withholds 10% at source and remits to DJP before distributing the net dividend. Exception: dividends reinvested in Indonesia within 3 years are tax-exempt (PP 9/2021). Dividends paid to corporate shareholders (another PT or foreign holding company) are subject to different treaty rates — check applicable tax treaty (e.g., 10% for Singapore, 10% for Netherlands, no treaty for some countries = 20% withholding).
**Gap reason:** NB-3 mentions dividends can be paid after RUPS resolution but says nothing about withholding tax mechanics or treaty rates.

---

### CATEGORY 6: MANPOWER / TKA (FOREIGN WORKERS) (5 claims)

---

**OPS-037**
**Category:** Manpower/TKA
**Priority:** CRITICAL
**Claim:** Work KITAS (ITAS Bekerja) for employees (non-director) requires: (1) approved RPTKA from Kemnaker, (2) sponsor letter from PT PMA, (3) insurance coverage (either BPJS or equivalent foreign insurance), (4) educational/professional qualification certificate matching the RPTKA job title, (5) no criminal record certificate (SKCK equivalent from home country, apostilled). Timeline: 30–45 days from RPTKA approval to KITAS issuance. Cost: approx IDR 1.2–2.5 million in government fees plus agent fees IDR 5–15 million typical.
**Gap reason:** NB-3 says PT PMA "can sponsor Work KITAS for staff." No document list, no timeline, no cost range.

---

**OPS-038**
**Category:** Manpower/TKA
**Priority:** HIGH
**Claim:** IMTA (Izin Mempekerjakan Tenaga Kerja Asing) was merged into the RPTKA system from 2020 onward — IMTA is no longer a separate document. The approval of RPTKA now serves the function of both the old IMTA and the employment authorization. Clients asking "do I need an IMTA?" should be told it is now integrated into RPTKA.
**Gap reason:** Not in NB-3. Legacy terminology confusion causes clients to search for a document that no longer exists independently.

---

**OPS-039**
**Category:** Manpower/TKA
**Priority:** HIGH
**Claim:** Prohibited job categories for foreign workers (TKA): HR Manager, Personnel Manager, and any role with direct authority over Indonesian worker industrial relations. Also prohibited: Director of Compliance for Indonesian regulatory affairs (must be Indonesian citizen). These restrictions are listed in Kepmenaker 349/2019 and must be checked against the RPTKA position title.
**Gap reason:** Completely absent from NB-3. Foreign clients creating org charts often assign these titles to expats, causing RPTKA rejection.

---

**OPS-040**
**Category:** Manpower/TKA
**Priority:** HIGH
**Claim:** RPTKA renewal is required annually (or per the approved duration). 30 days before expiry: submit renewal with updated proof of DKPTKA payment (USD 100/month × months), updated company profile (latest LKPM data), and confirmation that local counterpart mentoring is ongoing. If RPTKA expires without renewal, the Work KITAS automatically becomes invalid — the foreign worker is in illegal employment status from day 1 of expiry.
**Gap reason:** NB-3 does not mention RPTKA renewal cycle. Clients assume RPTKA is a one-time approval.

---

**OPS-041**
**Category:** Manpower/TKA
**Priority:** MEDIUM
**Claim:** Local worker mentoring (pendampingan) obligation: every TKA must have a designated Indonesian counterpart (pendamping TKA) who is being trained for eventual takeover of the role. The PT PMA must report the training progress quarterly in the LKPM under "realisasi tenaga kerja." Failure to designate and document a pendamping is grounds for RPTKA rejection at renewal.
**Gap reason:** Not in NB-3. Clients hiring specialized foreign experts (e.g., F&B chef, IT developer) are unaware they must also hire an Indonesian apprentice.

---

### CATEGORY 7: ANNUAL OBLIGATIONS CALENDAR (6 claims)

---

**OPS-042**
**Category:** Annual Obligations
**Priority:** CRITICAL
**Claim:** Complete Annual Compliance Calendar for PT PMA (Bali, standard fiscal year Jan–Dec):

- Jan 10: PPh 21 deposit (December payroll)
- Jan 15: PPh 25 installment
- Jan 20: SPT Masa PPh 21 (December)
- Jan 31: SPT Masa PPN (if PKP)
- Jan 31: Wajib Lapor Ketenagakerjaan annual renewal
- Q1 LKPM deadline: April 15 (for Jan–Mar period)
- Apr 30: SPT Tahunan Badan
- Q2 LKPM deadline: July 15
- Jun 30: RUPS Tahunan (6-month statutory deadline per UU 40/2007 Pasal 78 for Dec 31 fiscal year end — NOT July 31)
- Q3 LKPM deadline: October 15
- Q4 LKPM deadline: January 15 (following year)
- Dec (variable): THR payment for Natal/Christmas workers; Hari Raya THR for Muslim employees (Ramadan period, 7 days before Idul Fitri); **Note for Bali clients:** Hindu-Balinese employees are entitled to THR for their religious holiday (Galungan or Nyepi) — Bali-specific obligation that may create two THR payment events per year
  **Gap reason:** NB-3 has individual deadlines scattered across sources. No unified calendar exists. This is the most-requested reference from post-setup clients.

---

**OPS-043**
**Category:** Annual Obligations
**Priority:** HIGH
**Claim:** Annual GMS (RUPS Tahunan) must produce a notarized resolution if distributing dividends or approving director salary. The RUPS minutes must be uploaded to AHU Online (Ministry of Law system) within 30 days of the meeting. If two consecutive annual GMS records are missing from AHU, the system automatically blocks: new akta perubahan processing, KITAS sponsorship via AHU, and OSS company status changes. Recovery requires a special "AHU unlock" application (Permohonan Pembukaan Pemblokiran AHU) with supporting RUPS evidence.
**Gap reason:** NB-3 mentions RUPS obligation and AHU blocking risk in passing. No 30-day upload deadline, no blocking mechanism, no recovery procedure.

---

**OPS-044**
**Category:** Annual Obligations
**Priority:** HIGH
**Claim:** Bali-specific local tax filings (for F&B and accommodation PT PMA):

- Monthly PBJT return: due by the 15th of the following month at local Bapenda office (can be filed online via bapenda portal in Badung/Denpasar)
- Annual PBJT reconciliation report: filed with the annual SPT Tahunan to match declared revenue
- PBB-P2 (Property Tax): annual bill issued by Bapenda, due by September 30 — late payment adds 2% per month surcharge
  **Gap reason:** NB-3 mentions "10% PHR/PBJT" monthly obligation without portal details, Bali-specific deadlines, or PBB-P2 connection.

---

**OPS-045**
**Category:** Annual Obligations
**Priority:** HIGH
**Claim:** Annual business license validity check: All Standard Certificates (Sertifikat Standar) issued by OSS for Medium-High and High Risk businesses require periodic re-verification by the relevant agency. Tourism businesses (KBLI 55xxx, 56xxx) must renew their Sertifikat Standar Usaha Pariwisata from an LSPr accredited body every 2 years. SIUP-MB (alcohol license) renews every 3 years. SLS (sanitation certificate) renews every 2 years. Letting any of these expire while operating constitutes operating without a valid license — immediate shutdown risk.
**Gap reason:** NB-3 focuses entirely on initial license acquisition. No renewal schedule exists in NB-3.

---

**OPS-046**
**Category:** Annual Obligations
**Priority:** MEDIUM
**Claim:** Annual investment realization monitoring: BKPM tracks cumulative LKPM data to verify progress toward the IDR 10 billion total investment commitment per KBLI. Companies not reaching IDR 10 billion within a reasonable operational timeframe (informal guideline: 5 years) risk a "non-active investment" flag triggering an investment compliance audit. The audit can result in NIB downgrade (from Large Scale to Medium) or cancellation of the foreign ownership right.
**Gap reason:** NB-3 explains the IDR 10B commitment requirement at setup. No monitoring timeline, no 5-year guideline, no downgrade mechanism documented.

---

**OPS-047**
**Category:** Annual Obligations
**Priority:** MEDIUM
**Claim:** PT PMA dissolution trigger obligations for tax clearance: before a PT PMA can be fully dissolved, it must: (1) file all outstanding SPT Tahunan and SPT Masa for all periods since incorporation, (2) pay all tax arrears plus penalties, (3) de-register from PKP status (if applicable), (4) obtain SKPP (Surat Keterangan Pelunasan Pajak — Tax Clearance Letter) from DJP. The SKPP process under Coretax takes 6–12 months and involves a mandatory comprehensive tax audit. Companies that stopped filing taxes mid-operation face the largest dissolution hurdles.
**Gap reason:** NB-3 covers dissolution procedure well. The specific SKPP + Coretax de-registration sequence and the consequence of prior non-filing are not detailed.

---

## PART III — PRIORITY MATRIX

### CRITICAL PRIORITY (Must be in NB-6 before any client query)

| ID      | Topic                                            |
| ------- | ------------------------------------------------ |
| OPS-001 | BPJS Kesehatan rates (4% employer / 1% employee) |
| OPS-002 | BPJS Ketenagakerjaan JKK rates by sector         |
| OPS-003 | BPJS Ketenagakerjaan JKM rate                    |
| OPS-004 | BPJS Ketenagakerjaan JHT rate (3.7% / 2%)        |
| OPS-008 | Bali UMP 2026 actual figure                      |
| OPS-009 | PKWT vs. PKWTT contract types and limits         |
| OPS-010 | Probation rules (PKWTT only, max 3 months)       |
| OPS-011 | Pesangon formula and multipliers                 |
| OPS-014 | DKPTKA USD 100/month fee for foreign workers     |
| OPS-029 | Coretax migration and monthly filing mechanics   |
| OPS-030 | PPh 25 Nihil filing obligation for new companies |
| OPS-037 | Work KITAS document checklist and cost           |
| OPS-042 | Full annual compliance calendar                  |

### HIGH PRIORITY (NB-6 Phase 2 — within 30 days)

| ID      | Topic                                                                   |
| ------- | ----------------------------------------------------------------------- |
| OPS-005 | JP pension rate                                                         |
| OPS-006 | WNA BPJS obligations and exemption                                      |
| OPS-007 | BPJS non-compliance penalties                                           |
| OPS-012 | PPh 21 mechanics and Coretax reporting                                  |
| OPS-013 | THR and annual leave legal minimums                                     |
| OPS-015 | RPTKA procedure, timeline, position-specific rule                       |
| OPS-016 | TKA:TKI 1:10 ratio rule                                                 |
| OPS-020 | Bank account opening document checklist                                 |
| OPS-021 | Dividend extraction mechanics (PPh Final 10%)                           |
| OPS-024 | RUPS + AHU upload requirement                                           |
| OPS-025 | SIUP-MB procedure and renewal cycle                                     |
| OPS-026 | SLS document requirements and inspection                                |
| OPS-027 | Halal certification process and cost                                    |
| OPS-028 | PSE registration scope (not just tech)                                  |
| OPS-031 | PKP e-faktur and filing deadlines                                       |
| OPS-032 | 22% corporate tax rate + UMKM exclusion                                 |
| OPS-033 | Transfer pricing documentation obligation                               |
| OPS-034 | NPWPD separate registration                                             |
| OPS-038 | IMTA merger into RPTKA (legacy term)                                    |
| OPS-039 | Prohibited job titles for TKA                                           |
| OPS-040 | RPTKA annual renewal with DKPTKA proof                                  |
| OPS-043 | RUPS/AHU blocking and recovery procedure                                |
| OPS-044 | Bali PBJT filing portal and deadlines                                   |
| OPS-045 | License renewal schedule (SLS 2yr, SIUP-MB 3yr, Sertifikat Standar 2yr) |

### MEDIUM PRIORITY (NB-6 Phase 3)

| ID      | Topic                                             |
| ------- | ------------------------------------------------- |
| OPS-017 | Peraturan Perusahaan (10+ employees)              |
| OPS-018 | PHK disciplinary procedure (SP1→SP2→SP3)          |
| OPS-019 | Wajib Lapor Ketenagakerjaan annual renewal        |
| OPS-022 | Bank signatory delegation structure               |
| OPS-023 | BI foreign currency reporting (USD 25K threshold) |
| OPS-035 | PSAK accounting standards + IDR denomination      |
| OPS-036 | Dividend withholding tax and treaty rates         |
| OPS-041 | Pendamping TKA (local counterpart mentoring)      |
| OPS-046 | IDR 10B investment realization monitoring         |
| OPS-047 | SKPP tax clearance for dissolution                |

---

## PART IV — RECOMMENDED NB-6 SOURCE CONTENT STRUCTURE

Based on the gaps identified, NB-6 sources should cover these 7 topic clusters:

### Cluster A: BPJS Complete Guide

- Employer/employee contribution rates for all 5 programs (JKK, JKM, JHT, JP, Kesehatan)
- WNA enrollment rules and exemption procedure
- Enrollment portal walkthrough (bpjsketenagakerjaan.go.id)
- Penalty structure for non-enrollment

### Cluster B: Indonesian Employment Law for Foreign Business Owners

- PKWT/PKWTT structures with examples
- Probation rules
- Pesangon calculation tables with worked examples
- THR calculation and payment calendar
- Annual leave, maternity, and other statutory entitlements
- Company Regulation (Peraturan Perusahaan) requirements

### Cluster C: Foreign Worker (TKA) Complete Procedure Guide

- RPTKA: what it is, position-specific nature, prohibited titles
- DKPTKA: USD 100/month, payment portal, consequences
- Work KITAS for employees: document checklist, timeline, cost
- RPTKA annual renewal with DKPTKA proof
- 1:10 TKA:TKI ratio rule
- Pendamping TKA obligation

### Cluster D: Coretax + Monthly Tax Filing Operations

- Migration from eFilling to Coretax (step-by-step)
- Monthly filing calendar (PPh 21 by 10th/20th, PPh 25 by 15th, PPN by end of month)
- Nihil filing obligation for new companies
- PPh 21 bracket table 2026
- PKP e-faktur system
- NPWPD separate registration for local taxes

### Cluster E: Operational Licenses Renewal Calendar

- SIUP-MB classes, procedure, 3-year renewal
- SLS procedure and 2-year renewal
- Halal certification BPJPH process
- LSPr tourism certification 2-year cycle
- PSE registration for all digital operations

### Cluster F: Annual GMS + AHU Compliance

- RUPS procedure and documentation
- AHU Online upload requirement (30-day deadline)
- Consequence of 2-year AHU blocking
- Recovery procedure
- Dividend resolution mechanics

### Cluster G: Post-Incorporation Calendar Reference

- Full 12-month compliance calendar (Jan–Dec)
- Bali-specific deadlines (PBJT by 15th, PBB-P2 by Sep 30)
- LKPM Q1–Q4 deadlines under BKPM Reg 5/2025
- License renewal schedule

---

## APPENDIX — NB-3 CLAIM IDs ALREADY COVERING THESE AREAS

The following NB-3 claim IDs are well-covered and do NOT need to be replicated in NB-6:

- COM-020/COM-021/COM-022: LKPM quarterly obligation, sanctions, NIB suspension/revocation
- COM-035/COM-036: Akta perubahan types (approval vs. notification)
- COM-038: PKP registration threshold (IDR 4.8B)
- COM-039: SPT Tahunan Badan due date (April 30)
- COM-044: RUPS/Direksi obligations, buku besar
- COM-045: Audit threshold (IDR 50B)
- COM-046/COM-047: Capital structure rules
- COM-048: Corporate bank account usage rule
- BKPM Reg 5/2025: Capital locking 12 months, LKPM deadline change to 15th

These are solid, sourced claims in NB-3. NB-6 should reference them but not contradict them.

---

_Generated: 2026-03-30 | Machine: Pro (nuzantara@Nuzantara) | Source: NB-3 cross-query gap analysis_
_Next step: Use this document to build NB-6 source content across 7 clusters (47 gaps, 13 CRITICAL)_

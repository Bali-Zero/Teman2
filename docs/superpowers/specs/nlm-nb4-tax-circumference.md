# NB-4: Tax & Fiscal Indonesia — Phase 1: Topic Circumference

> **Date:** 2026-03-29
> **Author:** Claude Opus 4.6 (NLM Pipeline Architect)
> **Method:** Dual-agent parallel research (tax regulations + source catalog) + architect synthesis
> **Reference:** NB-2 Immigration & Visa (55 sources, 36 claims, NHS 0.801)
> **NB-4 ID:** `d4b2eedb-9863-4a1a-81ff-a11b0b45d853`
> **Current state:** 9 seed sources (internal guides in Italian)

---

## 1. PERIMETER — What Is Inside vs Outside NB-4

### INSIDE NB-4 (Tax & Fiscal Indonesia)

Everything about **tax obligations, rates, filing, compliance, and enforcement** for entities and individuals operating in Indonesia:

| Domain                           | Scope                                                               | Key Regulations                            |
| -------------------------------- | ------------------------------------------------------------------- | ------------------------------------------ |
| Corporate Income Tax (PPh Badan) | Rates, brackets, incentives, tax holidays, annual filing            | UU 36/2008 → UU 7/2021 HPP, PP 55/2022     |
| Personal Income Tax (PPh OP)     | Progressive rates, PTKP thresholds, TER system, residency           | UU 36/2008 → HPP, PP 58/2023, PMK 168/2023 |
| VAT / PPN                        | 11% standard rate, luxury goods (PPnBM), PKP registration           | UU 42/2009 → UU 7/2021 HPP, PP 44/2024     |
| Withholding Taxes                | PPh 21 (employment), 23 (services), 26 (cross-border), 4(2) (final) | Various PMK                                |
| Property-Related Tax             | BPHTB (transfer tax rates/rules), PBB (annual rates), capital gains | UU PDRD, Perda Bali                        |
| Tax Administration               | NPWP (post-NIK integration), SPT filing, e-Filing, Coretax system   | UU 28/2007 → HPP, PMK 81/2024              |
| International Tax                | DTA treaties (71 active), transfer pricing (TP Doc), CRS, AEOI      | PMK 213/2016, MLI                          |
| Tax Incentives                   | Tax holidays, super deduction R&D (300%), pioneer industries        | PMK tax holiday series                     |
| Global Minimum Tax               | Pillar Two/GloBE implementation, QDMTT, IIR, UTPR                   | PMK 136/2024                               |
| Tax Compliance & Enforcement     | Audit procedures, penalties, voluntary disclosure, tax court        | UU KUP                                     |
| Regional Taxes (Bali-specific)   | Hotel & restaurant tax, entertainment tax, parking tax, tourist tax | UU HKPD 1/2022, Perda Bali                 |

### OUTSIDE NB-4 (owned by other notebooks)

| Topic                                                             | Owner           | Border Rule                                                                                                |
| ----------------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------------------- |
| Visa application process, stay duration, immigration procedures   | **NB-2**        | NB-2 owns visa/stay. NB-4 owns tax consequences of residency status (183-day rule → tax residency)         |
| Company formation process (PT PMA registration steps, akta, KBLI) | **NB-3**        | NB-3 owns formation. NB-4 takes over at NPWP registration and all tax obligations post-formation           |
| Property ownership structures (HGB, nominee, land title)          | **NB-5**        | NB-5 owns ownership mechanics. NB-4 owns tax rates/obligations on transactions (BPHTB, PBB, capital gains) |
| Business license compliance, annual reporting (LKPM, OSS)         | **NB-6**        | NB-6 owns operational compliance. NB-4 owns tax-specific compliance (SPT, PKP, tax audit)                  |
| Personal lifestyle decisions (renting vs buying, cost of living)  | **NB-8**        | NB-8 owns lifestyle. NB-4 owns the tax implications of those decisions                                     |
| Bali Zero service pricing for tax consulting                      | **PricingTool** | Government tax rates (PNBP, BPHTB rates) → NB-4. Bali Zero fees → NEVER in NB-4                            |

### BORDER PROTOCOLS (cross-domain handoff rules)

| Border        | NB-4 Owns                                                                                                 | Other NB Owns                                               | Handoff Signal                                      |
| ------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | --------------------------------------------------- |
| **NB-2↔NB-4** | Tax residency status determination, tax consequences of 183-day rule, exit tax                            | Visa type, stay duration calculation, immigration reporting | "What tax status does this visa create?"            |
| **NB-3↔NB-4** | NPWP registration obligations, PKP threshold, tax type selection (PPh final vs regular), first SPT filing | Company formation steps, akta, KBLI selection, OSS-RBA      | "Company is formed — what are the tax obligations?" |
| **NB-5↔NB-4** | BPHTB rate calculation, PBB annual rates, capital gains tax on sale, rental income taxation               | Land certificate types, ownership structures, zoning        | "Client is buying property — what taxes apply?"     |

---

## 2. CLUSTER DESIGN — 7 Thematic Clusters

Following NB-2's A-E pattern, expanded to 7 clusters reflecting the breadth of Indonesian tax:

### Cluster A: Corporate Tax (PPh Badan) — **CORE REVENUE**

**Volatility:** Medium | **Priority:** Highest (PT PMA clients = primary revenue)

| Sub-topic                   | Key Regulations                        | Client Question                                |
| --------------------------- | -------------------------------------- | ---------------------------------------------- |
| Standard rate 22%           | UU 36/2008 art.17 → HPP                | "What's the corporate tax rate for my PT PMA?" |
| SME rate 0.5% (UMKM PP 55)  | PP 55/2022 art.56-62                   | "Can my small company use the 0.5% rate?"      |
| Listed company discount 19% | UU 36/2008 art.17(2b)                  | "Discount for going public?"                   |
| Tax holidays (pioneer)      | PMK tax holiday (latest extension)     | "Can we get a tax holiday?"                    |
| Super deduction R&D (300%)  | PMK 153/2020                           | "R&D tax incentive?"                           |
| Annual SPT Badan filing     | PMK 81/2024, Coretax                   | "When and how to file corporate tax return?"   |
| Fiscal year & accounting    | UU PPh, PSAK                           | "Can we use a non-calendar fiscal year?"       |
| Tax loss carryforward       | UU PPh art.6(2) — 5 years + extensions | "How long can we carry losses?"                |

**Estimated sources:** 12-15

### Cluster B: Personal Income Tax (PPh Orang Pribadi) — **HIGH VOLUME**

**Volatility:** Medium | **Priority:** High (every expat client)

| Sub-topic                            | Key Regulations                             | Client Question                       |
| ------------------------------------ | ------------------------------------------- | ------------------------------------- |
| Progressive rates (5%-35%)           | UU HPP art.17, 5 brackets                   | "What's my personal tax rate?"        |
| Tax residency (183-day rule)         | UU PPh art.2(3)-(4)                         | "Am I a tax resident?"                |
| PTKP (non-taxable threshold) IDR 54M | PMK PTKP                                    | "What income is tax-free?"            |
| TER withholding system               | PP 58/2023, PMK 168/2023                    | "How does my employer calculate tax?" |
| Exit tax / departure obligations     | UU PPh                                      | "What if I leave Indonesia?"          |
| Freelancer/self-employed             | UU PPh art.14, norm calculation             | "How are freelancers taxed?"          |
| Worldwide income vs source           | UU PPh art.4, territorial for non-residents | "Do I pay tax on overseas income?"    |

**Estimated sources:** 10-12

### Cluster C: VAT & Sales Tax (PPN, PPnBM) — **OPERATIONAL**

**Volatility:** HIGH (12% rate saga ongoing) | **Priority:** Medium-High

| Sub-topic                                   | Key Regulations                | Client Question                 |
| ------------------------------------------- | ------------------------------ | ------------------------------- |
| Standard rate 11% (general goods/services)  | UU HPP art.7                   | "What VAT rate applies?"        |
| 12% rate (luxury goods only, from Jan 2025) | PP 44/2024 + interpretive mess | "Is VAT really 12% now?"        |
| PKP registration threshold                  | PMK PKP threshold              | "When must I register for VAT?" |
| VAT exemptions                              | UU PPN art.4A, art.16B         | "What's exempt from VAT?"       |
| E-commerce VAT                              | PMK 37/2025 (marketplace WHT)  | "VAT on online sales?"          |
| Tax invoice (faktur pajak)                  | Coretax e-faktur               | "How to issue VAT invoices?"    |
| VAT refund for exporters                    | UU PPN art.9(4)                | "Can I get VAT refunded?"       |

**Estimated sources:** 8-10

### Cluster D: Withholding Taxes (PPh 21/23/26/4(2)) — **DAILY OPERATIONS**

**Volatility:** Low-Medium | **Priority:** High (every payroll, every invoice)

| Sub-topic                                            | Key Regulations                            | Client Question                         |
| ---------------------------------------------------- | ------------------------------------------ | --------------------------------------- |
| PPh 21 — employment income                           | PP 58/2023 TER, PMK 168/2023, PMK 105/2025 | "How to calculate employee tax?"        |
| PPh 23 — services, royalties (2%)                    | UU PPh art.23                              | "Withholding on service invoices?"      |
| PPh 26 — cross-border payments (20%)                 | UU PPh art.26, DTA reduced rates           | "Tax on payments to foreign companies?" |
| PPh 4(2) — final tax (construction, rent, dividends) | Various PP                                 | "Tax on office rent? Construction?"     |
| PPh 22 — import/export                               | PMK PPh 22, PMK 37/2025 e-commerce         | "Import duties and tax?"                |
| Monthly filing obligations                           | Coretax, SPT Masa                          | "When to file monthly tax returns?"     |

**Estimated sources:** 8-10

### Cluster E: Property-Related Taxes — **CROSS-DOMAIN with NB-5**

**Volatility:** Medium | **Priority:** Medium (property investor clients)

| Sub-topic                                   | Key Regulations       | Client Question                  |
| ------------------------------------------- | --------------------- | -------------------------------- |
| BPHTB (acquisition transfer tax 5%)         | UU HKPD 1/2022, Perda | "Transfer tax when buying?"      |
| PBB (annual property tax)                   | UU HKPD, Perda Bali   | "Annual property tax amount?"    |
| Capital gains on property sale (2.5% final) | PP 34/2016            | "Tax when I sell?"               |
| Rental income tax (10% final)               | PP 34/2017 PPh 4(2)   | "Tax on villa rental income?"    |
| VAT on property (> IDR 2B luxury)           | PMK PPnBM, UU PPN     | "VAT on new apartment purchase?" |
| Hotel & restaurant tax (Bali)               | Perda Bali, UU HKPD   | "Hotel tax rate in Bali?"        |

**Estimated sources:** 6-8

### Cluster F: Tax Administration & Coretax — **URGENT 2026**

**Volatility:** VERY HIGH | **Priority:** Highest (Coretax transition disrupting everything)

| Sub-topic                         | Key Regulations                    | Client Question                     |
| --------------------------------- | ---------------------------------- | ----------------------------------- |
| Coretax system (live Jan 2025)    | PMK 81/2024                        | "How does the new tax system work?" |
| NPWP → NIK integration            | PMK 112/2022                       | "Is my KTP now my tax number?"      |
| SPT filing deadlines & procedures | UU KUP, Coretax                    | "When are tax returns due?"         |
| Tax audit process                 | UU KUP art.29                      | "What happens in a tax audit?"      |
| Penalties & interest              | UU KUP art.13-15, HPP rates        | "What if I file late?"              |
| Voluntary disclosure program      | UU HPP art.5-7 (PPS 2022)          | "Can I fix past non-compliance?"    |
| E-billing & payment               | Coretax, bank channels             | "How to pay taxes?"                 |
| Tax objection & appeal            | UU KUP art.25-27, Pengadilan Pajak | "How to dispute a tax assessment?"  |

**Estimated sources:** 10-12

### Cluster G: International Tax — **STRATEGIC**

**Volatility:** HIGH (global minimum tax, OECD accession) | **Priority:** High (foreign investors)

| Sub-topic                       | Key Regulations                | Client Question                                 |
| ------------------------------- | ------------------------------ | ----------------------------------------------- |
| DTA/P3B network (71 treaties)   | Bilateral treaties, MLI        | "Is there a tax treaty with my country?"        |
| Transfer pricing (TP Doc)       | PMK 213/2016, OECD guidelines  | "Do I need transfer pricing docs?"              |
| Global minimum tax (Pillar Two) | PMK 136/2024, QDMTT, IIR, UTPR | "Does the 15% minimum tax affect me?"           |
| CRS/AEOI automatic exchange     | PMK 70/2017                    | "Does Indonesia share my info with my country?" |
| Anti-treaty shopping            | PMK beneficial ownership       | "Can my holding company use the treaty?"        |
| Permanent establishment         | UU PPh art.2(5), DTA art.5     | "Do I have a PE in Indonesia?"                  |
| Indonesia OECD accession        | OECD roadmap (Feb 2024)        | "Will OECD accession change tax rules?"         |

**Estimated sources:** 8-10

---

## 3. T0 REGULATIONS — Canonical Legal Sources (MUST be in NB-4)

### Primary Laws (Undang-Undang)

| #   | Regulation                      | Short Name                                  | Status                                       | Cluster    |
| --- | ------------------------------- | ------------------------------------------- | -------------------------------------------- | ---------- |
| 1   | **UU 7/2021**                   | HPP (Harmonisasi Peraturan Perpajakan)      | **ACTIVE — the tax omnibus**                 | ALL        |
| 2   | **UU 36/2008**                  | Pajak Penghasilan (Income Tax)              | Active, as amended by HPP                    | A, B, D, G |
| 3   | **UU 42/2009** → amended by HPP | PPN/PPnBM (VAT/Luxury Sales Tax)            | Active, as amended by HPP                    | C          |
| 4   | **UU 28/2007** → amended by HPP | KUP (General Tax Provisions & Procedures)   | Active, as amended by HPP                    | F          |
| 5   | **UU 1/2022**                   | HKPD (Hubungan Keuangan Pusat dan Daerah)   | **ACTIVE — replaces regional tax framework** | E          |
| 6   | **UU 6/2023** → **UU 4/2023**   | Cipta Kerja (Job Creation) — tax provisions | Active, validated by MK                      | A, B, C    |

### Government Regulations (PP)

| #   | Regulation     | Topic                                       | Status                 | Cluster |
| --- | -------------- | ------------------------------------------- | ---------------------- | ------- |
| 7   | **PP 55/2022** | HPP implementing regulation (comprehensive) | **ACTIVE — critical**  | A, B, C |
| 8   | **PP 58/2023** | TER (Average Effective Rate) for PPh 21     | ACTIVE                 | B, D    |
| 9   | **PP 44/2024** | VAT 12% luxury goods implementation         | ACTIVE (controversial) | C       |
| 10  | **PP 34/2016** | Final tax on property transfer (2.5%)       | ACTIVE                 | E       |
| 11  | **PP 34/2017** | PPh 4(2) rental income (10% final)          | ACTIVE                 | E       |

### Ministerial Regulations (PMK) — Key Current

| #   | Regulation       | Topic                                             | Status                     | Cluster |
| --- | ---------------- | ------------------------------------------------- | -------------------------- | ------- |
| 12  | **PMK 81/2024**  | Coretax Administration System legal framework     | **ACTIVE — critical 2026** | F       |
| 13  | **PMK 168/2023** | PPh 21 TER implementation                         | ACTIVE                     | D       |
| 14  | **PMK 136/2024** | Global minimum tax (Pillar Two GloBE)             | ACTIVE, UTPR from Jan 2026 | G       |
| 15  | **PMK 112/2025** | Foreign entity taxation                           | ACTIVE (Dec 2025)          | G       |
| 16  | **PMK 105/2025** | PPh 21 incentives industrial/tourism workers 2026 | ACTIVE                     | D       |
| 17  | **PMK 37/2025**  | E-commerce Article 22 WHT by marketplaces         | ACTIVE (Aug 2025)          | C, D    |
| 18  | **PMK 213/2016** | Transfer pricing documentation                    | ACTIVE                     | G       |
| 19  | **PMK 70/2017**  | CRS/AEOI automatic exchange                       | ACTIVE                     | G       |
| 20  | **PMK 112/2022** | NPWP → NIK integration                            | ACTIVE                     | F       |

**Total T0 sources: 20** (6 UU + 5 PP + 9 PMK)

---

## 4. T2-T4 SOURCE CATALOG

### T2 — Professional Tax Knowledge (daily monitoring)

| #   | Source                          | URL                            | Lang  | Priority                                          |
| --- | ------------------------------- | ------------------------------ | ----- | ------------------------------------------------- |
| 1   | **DDTC / DDTCNews**             | news.ddtc.co.id                | ID/EN | CRITICAL — Indonesia's premier tax news           |
| 2   | **Perpajakan DDTC**             | perpajakan.ddtc.co.id          | ID/EN | CRITICAL — 13,000+ docs, tax court decisions, DTA |
| 3   | **Ortax**                       | ortax.org                      | ID    | HIGH — largest tax community forum                |
| 4   | **Pajak.com**                   | pajak.com                      | ID    | HIGH — daily tax news                             |
| 5   | **PwC Indonesia Tax Summaries** | taxsummaries.pwc.com/indonesia | EN    | HIGH — best English reference                     |
| 6   | **ASEAN Briefing**              | aseanbriefing.com              | EN    | HIGH — best for foreign investors                 |

### T3 — Consulting & Analysis (weekly monitoring)

| #   | Source                        | URL                           | Lang  | Priority                             |
| --- | ----------------------------- | ----------------------------- | ----- | ------------------------------------ |
| 7   | Seven Stones Indonesia        | sevenstonesindonesia.com/blog | EN    | HIGH — Bali-specific competitor      |
| 8   | LMI Consultancy               | lmiconsultancy.com            | EN    | HIGH — Tax Handbook 2026             |
| 9   | Deloitte Indonesian Tax Guide | deloitte.com                  | EN    | MEDIUM — annual guide                |
| 10  | KPMG Indonesia TIES           | kpmg.com                      | EN    | MEDIUM — expat tax                   |
| 11  | EY Indonesia Tax Alerts       | ey.com/en_id                  | EN    | MEDIUM — alerts                      |
| 12  | MUC Consulting                | muc.co.id                     | ID/EN | MEDIUM — seminars, MyTaxGuide        |
| 13  | TaxPrime                      | taxprime.net                  | ID/EN | MEDIUM — ex-DJP staff                |
| 14  | APIC Tax (Bali)               | apictax.co.id                 | ID/EN | HIGH — Bali-based, direct competitor |
| 15  | ILA Global (Bali)             | ilaglobalconsulting.com       | EN    | HIGH — Bali, competitor              |
| 16  | BaliVisa.co                   | balivisa.co                   | EN    | MEDIUM — Bali tax compliance guide   |
| 17  | OECD Indonesia Tax            | oecd.org/tax/indonesia        | EN    | MEDIUM — policy reviews              |

### T4 — Social Media Monitoring

| #   | Account        | Platform         | Priority                 |
| --- | -------------- | ---------------- | ------------------------ |
| 18  | @DitjenPajakRI | X/Twitter        | **CRITICAL**             |
| 19  | @kring_pajak   | X/Twitter        | HIGH — taxpayer Q&A      |
| 20  | @PajakMania    | X/Twitter        | HIGH — community         |
| 21  | @ditjenpajakri | Instagram (610K) | HIGH                     |
| 22  | DitjenPajakRI  | YouTube (36.2K)  | HIGH — Coretax tutorials |
| 23  | DDTCNews       | Multiple         | CRITICAL                 |

---

## 5. GAP ANALYSIS — What's Missing from 9 Seed Sources

### Current Seed Sources (9 internal guides in Italian)

| Source                                 | Coverage                |
| -------------------------------------- | ----------------------- |
| npwp_registrazione_obblighi_2025.txt   | NPWP registration       |
| pph21_26_ritenute_lavoro_2025.txt      | PPh 21/26 withholding   |
| pph23_ritenute_servizi_2025.txt        | PPh 23 services         |
| pph_badan_imposta_reddito_2025.txt     | Corporate income tax    |
| ppn_pkp_iva_2025.txt                   | VAT/PPN                 |
| regime_umkm_forfettario_2025.txt       | SME regime (PP 55)      |
| spt_tahunan_scadenze_2025.txt          | Annual filing deadlines |
| tax_bali_zero_faq_fiscale_2025.txt     | General FAQ             |
| tax_treaty_convenzioni_doppie_2025.txt | Tax treaties            |

### CRITICAL GAPS (must fill before pipeline goes live)

| Gap                                   | Severity | Cluster | Why Critical                                                                                 |
| ------------------------------------- | -------- | ------- | -------------------------------------------------------------------------------------------- |
| **No T0 regulations**                 | CRITICAL | ALL     | Zero actual law texts. NB-4 runs on internal guides only — no regulatory ground truth        |
| **No Coretax coverage**               | CRITICAL | F       | The biggest tax admin change in 20 years (live Jan 2025). Clients asking daily. Zero sources |
| **No Global Minimum Tax**             | HIGH     | G       | PMK 136/2024 + UTPR from Jan 2026. Affects multinational PT PMAs                             |
| **No property taxes**                 | HIGH     | E       | BPHTB, PBB, capital gains — frequent client questions, zero coverage                         |
| **No regional Bali taxes**            | HIGH     | E       | Hotel tax, tourist tax, entertainment tax — every F&B/hotel client needs this                |
| **No VAT 12% saga**                   | HIGH     | C       | PP 44/2024 + the confusing partial implementation — clients completely lost                  |
| **No DTA actual treaty texts**        | MEDIUM   | G       | Internal guide about treaties, but no actual P3B texts                                       |
| **No tax audit/enforcement**          | MEDIUM   | F       | What happens when DJP audits — procedures, penalties, appeal                                 |
| **No transfer pricing docs**          | MEDIUM   | G       | PMK 213/2016, TP Doc requirements — affects all PT PMA with related-party transactions       |
| **No English sources**                | MEDIUM   | ALL     | 9/9 sources are Italian internal guides. No English professional analysis                    |
| **No external professional analysis** | MEDIUM   | ALL     | No DDTC, Ortax, PwC, ASEAN Briefing — no independent verification                            |
| **No PMK 2024-2026**                  | HIGH     | ALL     | 0 of the 9+ critical new PMK from 2024-2026                                                  |

### Coverage Score by Cluster

| Cluster                | Current Sources     | Needed | Gap %    |
| ---------------------- | ------------------- | ------ | -------- |
| A: Corporate Tax       | 1 (pph_badan)       | 12-15  | **93%**  |
| B: Personal Income Tax | 1 (pph21_26)        | 10-12  | **92%**  |
| C: VAT/PPN             | 1 (ppn_pkp)         | 8-10   | **90%**  |
| D: Withholding         | 2 (pph21_26, pph23) | 8-10   | **80%**  |
| E: Property Tax        | 0                   | 6-8    | **100%** |
| F: Tax Admin/Coretax   | 2 (npwp, spt)       | 10-12  | **83%**  |
| G: International       | 1 (tax_treaty)      | 8-10   | **90%**  |

**Overall coverage: ~10% (9 internal guides / ~70 needed)**

---

## 6. CAPACITY MODEL — Target Source Count

### By Tier

| Tier                        | Count  | Role                                                 |
| --------------------------- | ------ | ---------------------------------------------------- |
| T0 — Laws & Regulations     | 20     | Ground truth (UU, PP, PMK)                           |
| T1 — Government Portals     | 5      | pajak.go.id, Coretax, JDIH, Kemenkeu, BPK            |
| T2 — Professional           | 6      | DDTC, Ortax, PwC, ASEAN Briefing, Pajak.com          |
| T3 — Analysis/Consulting    | 11     | Big 4, Bali competitors, LMI, expat guides           |
| T4 — Social/Monitoring      | 6      | DJP X/IG/YT, DDTCNews, PajakMania, Kring Pajak       |
| Internal — Bali Zero Guides | 9      | Current seed sources (keep as-is)                    |
| Master Documents            | 4      | Change Log, Ops Status, Cross-Domain, Open Questions |
| **TOTAL**                   | **61** | Within 70 ACTIVE cap                                 |

### By Cluster

| Cluster          | T0     | T1-T2  | T3-T4  | Internal | Total  |
| ---------------- | ------ | ------ | ------ | -------- | ------ |
| A: Corporate     | 4      | 2      | 3      | 1        | 10     |
| B: Personal      | 3      | 2      | 3      | 1        | 9      |
| C: VAT           | 3      | 2      | 2      | 1        | 8      |
| D: Withholding   | 3      | 1      | 2      | 2        | 8      |
| E: Property      | 3      | 1      | 2      | 0        | 6      |
| F: Admin/Coretax | 3      | 2      | 3      | 2        | 10     |
| G: International | 4      | 1      | 2      | 1        | 8      |
| Cross-cluster    | —      | —      | —      | 2+4 MD   | 6      |
| **Total**        | **23** | **11** | **17** | **10**   | **61** |

---

## 7. CROSS-DOMAIN INTERFACE RULES

### NB-4 ↔ NB-2 (Immigration & Visa)

```
BORDER: Tax Residency (183-day rule)

NB-2 OWNS:                          NB-4 OWNS:
├── Visa type → stay duration        ├── 183 days → tax resident status
├── Entry/exit records               ├── Worldwide income obligation
├── Reporting obligations (imigrasi) ├── NPWP obligation for residents
└── KITAS/KITAP duration rules       ├── Exit tax considerations
                                     └── DTA tie-breaker rules

HANDOFF: When NB-2 query touches "tax residency", "183 days tax",
         or "NPWP for KITAS holder" → reference NB-4 via MD-3 (Cross-Domain)
```

### NB-4 ↔ NB-3 (Company Setup)

```
BORDER: Post-Formation Tax Obligations

NB-3 OWNS:                          NB-4 OWNS:
├── PT PMA formation steps           ├── NPWP activation & obligations
├── Akta notaris                     ├── PKP/VAT registration decision
├── OSS-RBA licensing                ├── Tax type selection (PPh final vs regular)
├── KBLI selection                   ├── First SPT filing
└── BKPM reporting                   ├── Corporate tax rate & incentives
                                     └── Withholding tax setup

HANDOFF: NB-3 says "company is formed" → NB-4 takes over with
         "now here are your tax obligations"
```

### NB-4 ↔ NB-5 (Property & Real Estate)

```
BORDER: Property Transaction Taxes

NB-5 OWNS:                          NB-4 OWNS:
├── Ownership structures (HGB, HGU)  ├── BPHTB calculation & rates
├── Land certificate process          ├── PBB annual tax rates
├── Notary/PPAT procedures            ├── Capital gains tax (2.5% final)
├── Zoning & permits                  ├── Rental income tax (10% final)
└── Due diligence                     ├── VAT on luxury property
                                      └── Hotel/restaurant tax (Bali)

HANDOFF: NB-5 says "client is buying property at X price" →
         NB-4 says "here are the taxes: BPHTB Y%, PBB Z/year"
```

---

## 8. CRITICAL 2026 INTELLIGENCE PRIORITIES

These are the topics that will generate the most client queries in 2026:

### Priority 1: Coretax Transition (Cluster F)

- **What:** DJP replaced DJP Online with Coretax system (Jan 2025)
- **Impact:** Every taxpayer must re-activate on new system. EFIN deprecated. NIK-based auth.
- **Client pain:** "The new system doesn't work", "I can't file", "My accountant can't access"
- **Sources needed:** PMK 81/2024, DJP tutorials, practitioner guides

### Priority 2: VAT 12% Confusion (Cluster C)

- **What:** HPP mandated 12% from Jan 2025. Government applied it ONLY to luxury goods (PPnBM category). General VAT stays 11%.
- **Impact:** Massive confusion. Media says "12%", reality is "still 11% for most things"
- **Client pain:** "Is VAT 12% now? My supplier charged me 12%"
- **Sources needed:** PP 44/2024, DJP clarifications, professional analysis

### Priority 3: Global Minimum Tax (Cluster G)

- **What:** PMK 136/2024 implements Pillar Two. UTPR effective Jan 2026.
- **Impact:** PT PMAs that are part of multinational groups with >€750M revenue may face top-up tax
- **Client pain:** "Does the 15% minimum affect my company?"
- **Sources needed:** PMK 136/2024, OECD GloBE rules, Big 4 analysis

### Priority 4: PMK 112/2025 Foreign Entity Taxation (Cluster G)

- **What:** New rules on how foreign entities are taxed in Indonesia
- **Impact:** Directly affects all foreign investors with Indonesian operations
- **Sources needed:** PMK 112/2025 full text, DJP interpretation

### Priority 5: PPh 21 TER System (Cluster D)

- **What:** PP 58/2023 + PMK 168/2023 changed how employers calculate monthly payroll tax
- **Impact:** Every company with employees. Simpler but different from old system.
- **Client pain:** "My payroll tax calculation changed — is this right?"
- **Sources needed:** PP 58/2023, PMK 168/2023, PMK 105/2025 (incentives)

---

## 9. POPULATION PLAN — Phase 2 Roadmap

### Week 1: T0 Foundation (20 regulatory sources)

1. Ingest 6 UU texts (HPP, PPh, PPN, KUP, HKPD, Cipta Kerja)
2. Ingest 5 PP texts (PP 55/2022, PP 58/2023, PP 44/2024, PP 34/2016, PP 34/2017)
3. Ingest 9 critical PMK texts (81/2024, 168/2023, 136/2024, 112/2025, 105/2025, 37/2025, 213/2016, 70/2017, 112/2022)
4. Create MD-1 (Change Log) as NB-4 source

### Week 2: T1-T2 Professional Sources (11 sources)

1. Add pajak.go.id tax guide section
2. Add JDIH Kemenkeu regulation index
3. Add Coretax system documentation
4. Add DDTC/DDTCNews analysis articles (curated, not bulk)
5. Add PwC Indonesia tax summary
6. Add ASEAN Briefing Indonesia tax guide
7. Create MD-2 (Ops Status), MD-3 (Cross-Domain), MD-4 (Open Questions)

### Week 3: T3-T4 Analysis & Monitoring (17 sources)

1. Add Big 4 annual guides (Deloitte, KPMG TIES, EY, Grant Thornton)
2. Add Bali-specific competitors (Seven Stones, LMI, APIC, ILA)
3. Add BaliVisa.co practical guide
4. Add OECD Indonesia tax profile
5. Configure T4 social monitoring (@DitjenPajakRI, @kring_pajak, DDTCNews, PajakMania)

### Week 4: Testing & Calibration

1. Run query design (Step 1) following NB-2 pattern
2. Test 7 clusters with L1 monitoring queries
3. Verify claim extraction on each cluster
4. Calculate initial NHS (target: ≥0.75)
5. Go/No-Go for production pipeline

---

## 10. KEY WARNINGS & INVARIANTS

1. **NEVER cite government tax RATES from memory** — always from T0 sources. Rates change.
2. **UU 7/2021 (HPP) amended everything** — any pre-2021 rate/threshold must be verified against HPP.
3. **Coretax replaces DJP Online** — any reference to "DJP Online" or "EFIN" is potentially outdated from 2025.
4. **VAT is NOT 12% for most goods** — it's 12% ONLY for luxury goods (PPnBM). General rate is 11%. This is the #1 source of misinformation.
5. **PP 55/2022 UMKM regime expires** — the 0.5% final tax has a 7-year window per taxpayer. Check eligibility.
6. **Tax treaties require beneficial ownership** — anti-treaty-shopping rules (PMK BO) mean holding company structures may not qualify.
7. **Bali Zero PRICING never enters NB-4** — government rates (BPHTB 5%, PBB rates, PPh rates) are NB-4. Bali Zero fees for tax consulting are PricingTool only.
8. **Regional taxes vary by kabupaten** — Badung, Gianyar, Denpasar have different Perda. Specify which applies.

---

_Phase 1 complete. Ready for Phase 2 (7-step population following NB-2 method)._

_Produced by Claude Opus 4.6 — NLM Pipeline Architect, 2026-03-29_
_Research: 2 parallel agents (51 sources cataloged + 15 regulatory findings verified)_
_Current NB-4 seed sources: 9/70 (13% capacity)_
_Target: 61/70 (87% capacity) after 4-week population_

# Step 1: Query Design — NB-4 Tax & Fiscal Indonesia

> Architect: Claude Opus 4.6 (2026-03-30)
> Method: NB-2 pattern replication + tax domain adaptation
> Status: Ready for testing

---

## 1. Language Strategy

### Dual-track asymmetric (same as NB-2)

| Language             | Weight | Target Sources                                      | Use For                                                                      |
| -------------------- | ------ | --------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Bahasa Indonesia** | 60%    | pajak.go.id, DDTC, Ortax, JDIH Kemenkeu, DDTCNews   | Regulations, PMK/PP text, DJP circulars, Perda                               |
| **English**          | 30%    | PwC, ASEAN Briefing, Big 4, law firms, expat guides | Analysis, comparison, foreign investor context                               |
| **Mixed bridge**     | 10%    | Cross-taxonomy                                      | `PPh 21 TER withholding Indonesia 2026`, `BPHTB property tax Bali foreigner` |

### Tax-Specific Rules

- **Regulation numbers are language-neutral**: `PMK 136/2024` works in both ID and EN queries
- **Acronyms bridge languages**: PPh, PPN, NPWP, PKP, SPT, BPHTB, PBB — use directly
- **ID first for rate changes** (DJP announces in Indonesian first) → **EN confirm** (Big 4 analysis)

---

## 2. Query Anatomy

### Structure (5 components, same as NB-2)

```
[TAX TOPIC ANCHOR] + [REGULATORY MARKER] + [TEMPORAL ANCHOR] + [SOURCE HINT] + [NOISE CONTROL]
```

| Component             | Good Examples                                                                                 | Bad Examples                                         |
| --------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **Tax topic anchor**  | `PPh Badan tarif`, `PPN 12% barang mewah`, `BPHTB properti`, `Coretax SPT Tahunan`            | `pajak Indonesia`, `tax tips`, `save money on taxes` |
| **Regulatory marker** | `PMK`, `PP`, `UU HPP`, `Surat Edaran DJP`, `peraturan terbaru`, `official regulation`         | `how to`, `guide`, `tips`                            |
| **Temporal anchor**   | `2025-2026`, `setelah PMK 81/2024`, `tarif terbaru berlaku`, `per Januari 2026`               | `recently`, `new`                                    |
| **Source hint**       | `Direktorat Jenderal Pajak`, `Kemenkeu`, `DDTC`, `perpajakan.ddtc.co.id`, `PwC tax summaries` | (none)                                               |
| **Noise control**     | `bukan konsultan pajak promosi`, `excluding tax software ads`, `berdasarkan peraturan resmi`  | (none)                                               |

---

## 3. Cluster Definitions — 7 Clusters

| Cluster                    | Topic                                      | Volatility | Priority    | Revenue Link          |
| -------------------------- | ------------------------------------------ | ---------- | ----------- | --------------------- |
| **A: Corporate Tax**       | PPh Badan, rates, incentives, tax holidays | Medium     | Highest     | Every PT PMA client   |
| **B: Personal Income Tax** | PPh OP, residency, brackets, TER           | Medium     | High        | Every expat client    |
| **C: VAT/PPN**             | PPN rates, PKP, e-faktur, luxury goods     | HIGH       | Medium-High | PT PMA with revenue   |
| **D: Withholding**         | PPh 21/23/26/4(2), monthly returns         | Low-Medium | High        | Every payroll/invoice |
| **E: Property Tax**        | BPHTB, PBB, capital gains, Bali Perda      | Medium     | Medium      | Property investors    |
| **F: Tax Admin/Coretax**   | Coretax, NPWP/NIK, SPT, audit, penalties   | VERY HIGH  | Highest     | All clients 2026      |
| **G: International**       | DTA, transfer pricing, GloBE, CRS          | HIGH       | High        | MNE PT PMA clients    |

### Rotation Schedule (7-day, 1 cluster/day)

```
Mon: A (Corporate)   → Revenue-critical, start of week
Tue: B (Personal)    → Expat focus
Wed: F (Coretax)     → Admin urgency (highest volatility)
Thu: D (Withholding)  → Mid-week operations
Fri: G (International) → Strategic, end of week
Sat: C (VAT) + E (Property)  → Combined lighter clusters
Sun: OFF
```

4-week L1→L2→L3→L4 rotation within each cluster.

---

## 4. Production-Ready Query Templates (28 queries)

### L1 — Monitoring (14 queries, 2 per cluster)

**A1 — Corporate Tax: PPh Badan Rate & Incentives (Bahasa)**

> Peraturan terbaru tarif Pajak Penghasilan Badan (PPh Badan) untuk perusahaan PMA di Indonesia tahun 2025-2026. Termasuk tarif umum 22%, fasilitas pengurangan 50% untuk omzet di bawah Rp 50 miliar (Pasal 31E), tax holiday industri pionir (PMK terbaru), dan super deduction R&D 300%. Sumber resmi DJP, Kemenkeu, atau DDTC. Bukan iklan konsultan pajak.

**A2 — Corporate Tax: UMKM Final Tax (English)**

> Current status of Indonesia's 0.5% final income tax for MSMEs (PP 55/2022) in 2026: time limit changes, pending revision making it permanent for individuals until 2029, revocation for corporate entities. Include IDR 500 million tax-free threshold for individuals. Based on official regulations and DDTCNews analysis, not promotional tax consultant content.

**B1 — Personal Income Tax: Residency & Brackets (Bahasa)**

> Ketentuan terbaru Pajak Penghasilan Orang Pribadi (PPh OP) di Indonesia tahun 2025-2026: tarif progresif 5%-35% berdasarkan UU HPP, batas PTKP Rp 54 juta, aturan subjek pajak dalam negeri 183 hari, dan kewajiban NPWP bagi WNA yang bekerja di Indonesia. Termasuk perubahan PP 58/2023 tentang TER (Tarif Efektif Rata-rata). Sumber resmi DJP atau analisis hukum perpajakan.

**B2 — Personal Income Tax: Expat Obligations (English)**

> Tax obligations for foreign expatriates working in Indonesia 2025-2026: 183-day tax residency rule, worldwide income taxation for residents, NPWP registration requirements for KITAS holders, and double taxation agreement (DTA/P3B) relief procedures under PMK 112/2025. Focus on PwC tax summaries, ASEAN Briefing, or official DJP guidance. Exclude travel blogs and visa agent promotions.

**C1 — VAT: PPN Rate Confusion (Bahasa)**

> Implementasi tarif PPN 12% di Indonesia per Januari 2025: penerapan hanya untuk barang mewah (PPnBM), tarif efektif 11% untuk barang/jasa umum berdasarkan PMK 131/2024, mekanisme perhitungan DPP 11/12. Termasuk dampak pada PKP dan faktur pajak. Sumber resmi DJP, Kemenkeu, atau analisis DDTC/Ortax. Bukan opini media sosial.

**C2 — VAT: PKP & E-Commerce (English)**

> Indonesia VAT compliance for businesses in 2026: PKP (Pengusaha Kena Pajak) registration thresholds, e-invoicing through Coretax system, marketplace withholding tax under PMK 37/2025 (effective August 2025), and VAT refund procedures for exporters. Based on official regulations and professional tax analysis.

**D1 — Withholding: PPh 21 TER System (Bahasa)**

> Penerapan sistem TER (Tarif Efektif Rata-rata) untuk pemotongan PPh Pasal 21 di Indonesia berdasarkan PP 58/2023 dan PMK 168/2023: tabel tarif 127 kategori, mekanisme rekonsiliasi akhir tahun, dan insentif PPh 21 DTP untuk pekerja sektor industri/pariwisata berdasarkan PMK 105/2025. Sumber resmi DJP atau panduan teknis perpajakan.

**D2 — Withholding: PPh 23/26 Cross-Border (English)**

> Withholding tax rates on cross-border payments from Indonesia 2025-2026: PPh 26 standard 20% rate, treaty-reduced rates for dividends/interest/royalties, PPh 23 on domestic services (2%), PPh 4(2) final tax on construction and rental income. Include PMK 112/2025 substance requirements for treaty access. Professional tax analysis sources only.

**E1 — Property Tax: BPHTB & PBB (Bahasa)**

> Ketentuan pajak properti di Indonesia tahun 2025-2026: tarif BPHTB 5% atas perolehan hak tanah dan bangunan, PBB-P2 (pajak tahunan), pajak capital gain 2,5% final atas penjualan properti (PP 34/2016), dan pajak penghasilan atas sewa 10% final. Termasuk NJOP dan NPOPTKP. Berdasarkan UU HKPD 1/2022 dan Perda daerah terkait. Bukan iklan agen properti.

**E2 — Property Tax: Bali Regional Taxes (English)**

> Property and hospitality taxes in Bali 2025-2026: annual land and building tax (PBB), transfer tax (BPHTB) calculation for foreign investors, hotel tax (PBJT jasa perhotelan), restaurant tax, entertainment tax rates under UU HKPD 1/2022 and Badung/Gianyar/Denpasar regional regulations (Perda). Focus on verified rates and official government sources.

**F1 — Tax Admin: Coretax 2026 (Bahasa)**

> Implementasi penuh sistem Coretax DJP di Indonesia tahun 2026: peralihan total dari DJP Online, cara aktivasi akun, pelaporan SPT Tahunan melalui Coretax, pembuatan faktur pajak elektronik, dan permasalahan teknis yang masih dihadapi wajib pajak. Berdasarkan PMK 81/2024, panduan resmi DJP, dan berita DDTCNews.

**F2 — Tax Admin: NPWP/NIK & Penalties (English)**

> Indonesia's NPWP-NIK integration status in 2026: 16-digit tax ID using national ID number (NIK), NITKU for branch offices, Coretax activation requirements, and tax penalties for late filing/payment under current KUP provisions. Include SPT filing deadline extensions (April 30, 2026 for tax year 2025). Based on DJP announcements and LMI/Acclime analysis.

**G1 — International: Global Minimum Tax (Bahasa)**

> Implementasi pajak minimum global (Pillar Two/GloBE) di Indonesia berdasarkan PMK 136/2024: Income Inclusion Rule (IIR) efektif Januari 2025, Undertaxed Payment Rule (UTPR) efektif Januari 2026, Domestic Minimum Top-up Tax (DMTT), dan dampak terhadap tax holiday investasi asing. Sumber resmi Kemenkeu, KPMG, atau analisis Roedl/DDTC.

**G2 — International: DTA & Transfer Pricing (English)**

> Indonesia's double taxation agreement (DTA/P3B) network in 2025-2026: PMK 112/2025 substance-based treaty access requirements, beneficial ownership tests, Principal Purpose Test (PPT), and transfer pricing documentation requirements under PMK 172/2023 (three-tier TP Doc). Include OECD Indonesia transfer pricing country profile updates. Focus on law firm analysis and Big 4 tax alerts, not generic explainers.

---

### L2 — Comparative (7 queries, 1 per cluster)

**A-L2 — Corporate Tax: Indonesia vs Regional (English)**

> Comparative analysis of corporate income tax rates and incentives across ASEAN countries in 2026: Indonesia (22%) vs Singapore (17%) vs Thailand (20%) vs Vietnam (20%) vs Malaysia (24%). Focus on tax holidays, R&D super deductions, special economic zones, and effective tax rates after incentives. Include how Indonesia's Pillar Two implementation (PMK 136/2024) affects relative competitiveness for foreign direct investment.

**B-L2 — Personal Income Tax: Expat Tax Burden Comparison (English)**

> Tax burden comparison for expatriates earning USD 100,000/year across Southeast Asian countries in 2026: Indonesia progressive rates (5%-35%) vs Singapore (0%-24%) vs Thailand (0%-35%) vs Malaysia (0%-30%). Include tax residency triggers, DTA benefits, and social security obligations for foreign workers. Based on KPMG TIES, Big 4 expat tax guides, or Airswift/Greenback analysis.

**C-L2 — VAT: Indonesia 12% vs ASEAN VAT Rates (Bahasa)**

> Perbandingan tarif PPN di negara-negara ASEAN tahun 2026: Indonesia 11-12% vs Singapura 9% vs Thailand 7% vs Filipina 12% vs Vietnam 10%. Termasuk analisis dampak penerapan PPN 12% Indonesia yang terbatas pada barang mewah saja. Apakah Indonesia akan menerapkan tarif penuh 12% untuk semua barang di masa mendatang? Sumber analisis ekonomi atau perpajakan komparatif.

**D-L2 — Withholding: Treaty Rate Analysis (English)**

> Withholding tax rates comparison across Indonesia's most-used DTAs in 2026: dividends, interest, and royalties rates under treaties with Singapore, Netherlands, Japan, Australia, UK, and USA. Include impact of PMK 112/2025 substance requirements on treaty access. Which treaties are most favorable for PT PMA shareholders repatriating profits? Professional tax analysis only.

**E-L2 — Property Tax: Bali vs Other Investment Destinations (English)**

> Property tax and transaction cost comparison for foreign real estate investors: Bali/Indonesia vs Phuket/Thailand vs Portugal Golden Visa vs Dubai. Include total acquisition cost (transfer tax + notary + VAT), annual holding cost (property tax), and exit cost (capital gains). Focus on 2025-2026 regulatory frameworks.

**F-L2 — Tax Admin: Coretax Problems vs Solutions (Bahasa)**

> Evaluasi satu tahun implementasi Coretax DJP: permasalahan yang masih terjadi vs perbaikan yang sudah dilakukan sejak Januari 2025 hingga Maret 2026. Termasuk statistik aktivasi wajib pajak, dampak terhadap penerimaan negara, dan respons komunitas perpajakan (Ortax, PajakMania). Berdasarkan berita DDTCNews, laporan Tempo, atau siaran pers DJP.

**G-L2 — International: GloBE Impact on Indonesian Tax Holidays (English)**

> Analysis of how Indonesia's Global Minimum Tax implementation (PMK 136/2024) interacts with existing tax holiday incentives for pioneer industries. Will the 15% minimum effective rate render Indonesian tax holidays ineffective for MNE groups? How is Indonesia redesigning incentives to remain competitive under Pillar Two? Include OECD BEPS framework analysis, KPMG/EY insights, and Jakarta Globe reporting.

---

### L3 — Predictive (4 queries, strategic)

**L3-1 — Tax Policy Direction Under Prabowo (English)**

> Indonesia's tax policy trajectory under President Prabowo Subianto 2025-2029: priority on revenue mobilization vs investment attraction, planned reforms (tax amnesty sequel, carbon tax timeline, VAT broadening), fiscal deficit targets, and tax-to-GDP ratio improvement plans (from 10.2% toward 12-14%). Include IMF Article IV consultation recommendations and OECD accession tax commitments.

**L3-2 — Digital Economy Taxation (Bahasa)**

> Rencana perpajakan ekonomi digital Indonesia tahun 2026-2027: PPN atas transaksi digital, PPh atas e-commerce marketplace (PMK 37/2025), pajak kripto, dan upaya Indonesia dalam negosiasi OECD Pillar One (Amount A) untuk alokasi hak pemajakan terhadap perusahaan teknologi multinasional. Apakah Indonesia akan menerapkan Digital Service Tax (DST) mandiri jika Pillar One gagal? Sumber analisis kebijakan perpajakan.

**L3-3 — Carbon Tax: When and How (English)**

> Indonesia's carbon tax implementation forecast: fourth delay since April 2022, current IDX Carbon exchange performance, PP 110/2025 governance framework, and realistic timeline for activation of the IDR 30/kg CO2e minimum rate. Will Indonesia adopt a hybrid cap-tax-and-trade system? Compare with Singapore's carbon tax model. Based on IEEFA, AMRO, and Kemenkeu policy signals.

**L3-4 — Bali Enforcement Trend (English)**

> Tax compliance enforcement trends for foreign-owned businesses in Bali 2025-2026: increased audits on villa rental income, restaurant/hotel tax compliance, NPWP registration enforcement for KITAS holders, and PT PMA tax filing audits. Is DJP Bali intensifying enforcement? Include Perda Badung/Gianyar enforcement actions and Seven Stones/LMI compliance alerts.

---

### L4 — Cross-Domain (3 queries)

**L4-1 — Visa Status → Tax Consequences (NB-2↔NB-4)**

> The intersection of Indonesia immigration status and tax obligations in 2026: which visa types trigger tax residency (183-day rule), KITAS holder NPWP requirements, digital nomad visa (E33G) tax treatment, Second Home Visa tax implications, and exit tax obligations when leaving Indonesia. How does the new PMK 112/2025 (DTA substance) interact with visa-based residency? Bridge immigration and fiscal analysis.

**L4-2 — Company Formation → Tax Setup (NB-3↔NB-4)**

> Post-formation tax setup checklist for new PT PMA companies in Indonesia 2026: NPWP activation via Coretax, PKP registration decision (when to register for VAT), tax type selection (PPh final 0.5% vs regular), first monthly SPT Masa filing, PPh 21 setup for employees, and PPh 25 monthly installments. Bridge company formation (NB-3) with ongoing tax compliance (NB-4).

**L4-3 — Property Purchase → Tax Obligations (NB-5↔NB-4)**

> Complete tax cost analysis for a foreigner buying property through a PT PMA in Bali 2026: BPHTB calculation (5% of NPOP minus NPOPTKP), annual PBB, capital gains on future sale (2.5% final), rental income tax if leased (10% final PPh 4(2)), VAT implications for luxury properties, and hotel/restaurant tax if operated commercially. Bridge property acquisition (NB-5) with fiscal obligations (NB-4).

---

## 5. Sequencing — NB-4 Pipeline Timing

### Daily Window: 02:20 - 03:00 WITA (after NB-2, before scraper)

```
02:20  NB-4 PIPELINE START
02:25  PHASE 1: Signal collection (5 min)
         - Read state file (hot_topics, known_regulations)
         - Check hot_topics decay
         - Select today's cluster from rotation
         - Read NB-2 brief for cross-domain signals
02:30  PHASE 2: Query 1 — L1 Monitoring (12 min)
         - research_start(mode=deep)
         - research_status(poll_interval=30, max_wait=600)
         - research_import(filtered sources)
         - notebook_query(verification prompt)
02:42  PHASE 3: Inter-query assessment (3 min)
         - Parse L1 for breaking signals (new PMK, rate change)
         - If BREAKING → override L2 with targeted query
02:45  PHASE 4: Query 2 — L2/L3/L4 Rotating (12 min)
         - Same cycle as Phase 2
02:57  PHASE 5: Consolidation (3 min)
         - Generate daily_intelligence_brief_nb4.json
         - Write to ~/.agent/decisions/nlm_briefs/
         - Update state file
         - Telegram if high-value finding
03:00  NB-4 PIPELINE END → Intel Scraper starts
```

### Weekly Cluster Rotation (4-week cycle)

| Week | Mon (A)   | Tue (B)   | Wed (F)   | Thu (D)   | Fri (G)   | Sat (C+E) |
| ---- | --------- | --------- | --------- | --------- | --------- | --------- |
| 1    | A-L1×2    | B-L1×2    | F-L1×2    | D-L1×2    | G-L1×2    | C-L1+E-L1 |
| 2    | A-L1+A-L2 | B-L1+B-L2 | F-L1+F-L2 | D-L1+D-L2 | G-L1+G-L2 | C-L2+E-L2 |
| 3    | A-L1+L3-1 | B-L1+L3-2 | F-L1+L3-3 | D-L1+L3-4 | G-L1+L4-1 | L4-2+L4-3 |
| 4    | A-L1×2    | B-L1×2    | F-L1×2    | D-L1×2    | G-L1×2    | C-L1+E-L1 |

2 queries/day, 12 queries/week, 48 queries/month across all clusters and levels.

---

## 6. Anti-Noise Techniques (Tax-Specific)

### Query-Level

| Technique                 | Example                                                       | Effectiveness |
| ------------------------- | ------------------------------------------------------------- | ------------- |
| **Regulation number**     | `PMK 136/2024`, `PP 55/2022`, `UU 7/2021 HPP`                 | Very high     |
| **Institutional name**    | `DJP`, `Kemenkeu`, `DDTC`, `Pengadilan Pajak`                 | High          |
| **Anti-promo framing**    | `bukan konsultan pajak promosi`, `excluding tax software ads` | High          |
| **Technical terminology** | `DPP`, `PKP`, `SPT Masa`, `PTKP`, `NJOP` — blogs CAN'T answer | Very high     |
| **Temporal specificity**  | `berlaku sejak Januari 2026`, `tarif setelah PMK 131/2024`    | High          |

### Domain Denylist (tax-specific)

```
blog.traveler*, forum.expat*, *tips-hemat-pajak*, *cara-menghindari-pajak*,
*taxfree*, reddit.com/r/*, quora.com/*, *affiliate*, medium.com/@random*
```

### Expected Noise Budget

- With all techniques: 10-15% noise (tax content is more structured than immigration)
- Acceptable: NLM synthesis engine weights DJP/DDTC/PwC highest
- Alert threshold: 25%+ noise → query tightening

---

## 7. Query Evolution — Breaking Signal Protocol

### Tax-Specific Triggers

| Signal Type               | Example                         | Action                                           |
| ------------------------- | ------------------------------- | ------------------------------------------------ |
| **New PMK published**     | PMK xxx/2026 on DJP website     | PROMOTE → 4 targeted queries, 7-day follow-up    |
| **Rate change**           | VAT increase, new bracket       | PROMOTE → cross-cluster queries (C+D+E affected) |
| **Coretax system change** | New module, downtime, fix       | PROMOTE → F cluster override, 14-day follow-up   |
| **DJP enforcement alert** | Audit wave, compliance deadline | PROMOTE → F+cluster-specific queries             |
| **PP revision signed**    | PP 55/2022 revision by Prabowo  | PROMOTE → A+B cross-cluster, 14-day follow-up    |
| **International treaty**  | New DTA signed or amended       | PROMOTE → G cluster, 7-day follow-up             |

### State Tracking

```json
{
  "cluster_f": {
    "active_followup": {
      "trigger": "Coretax SPT filing issues March 2026",
      "query_override": "Permasalahan pelaporan SPT Tahunan melalui Coretax...",
      "cycles_remaining": 3,
      "first_detected": "2026-03-30"
    }
  },
  "cross_cluster_alert": {
    "trigger": "PP 55/2022 revision",
    "affects": ["A", "B"],
    "status": "awaiting_signature"
  }
}
```

---

_Ready for testing. Start with Week 1 L1 queries across all 7 clusters._

_Produced by Claude Opus 4.6 — NLM Pipeline Architect, 2026-03-30_

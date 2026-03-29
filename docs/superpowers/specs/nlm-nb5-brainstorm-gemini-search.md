# NB-5: Property & Real Estate Indonesia — Search-Grounded Research Report

> **Role:** Search-Grounded Researcher (Gemini Search arm)
> **Date:** 2026-03-29
> **Agent:** Claude Opus 4.6 (Pro machine)
> **Method:** Deep web research via Brave Search, Exa, and WebSearch — both Bahasa Indonesia and English
> **Sources queried:** 25+ distinct search queries, 15+ full-page crawls, regulatory databases (peraturan.bpk.go.id, peraturan.go.id, JDIH)

---

## 1. PERIMETER — What Is INSIDE NB-5 vs OUTSIDE

### INSIDE NB-5 (Core Domain)

| Topic                                 | Description                                                                                                    | Why NB-5                                               |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Land rights hierarchy                 | Hak Milik, HGB, Hak Pakai, HGU, Hak Sewa — definitions, durations, eligibility                                 | Foundational knowledge for all property decisions      |
| Foreign ownership structures          | Hak Pakai (direct), PT PMA + HGB, Leasehold (Hak Sewa), PPJB                                                   | The core tension: how foreigners legally hold property |
| Nominee arrangements                  | Legal prohibition, risks, court cases, Perda Bali 4/2026 criminal sanctions                                    | Critical risk topic — clients ask constantly           |
| Transaction process                   | Due diligence, PPAT role, AJB deed, BPN registration, PPJB                                                     | Step-by-step property acquisition                      |
| Land title verification               | Certificate checking at BPN, clean title, encumbrances, Hak Tanggungan                                         | Pre-purchase essential                                 |
| Development & construction permits    | PBG (replacing IMB), SLF, SBKBG, SIMBG online system                                                           | Building on acquired land                              |
| Zoning & spatial planning             | RTRW, RDTR, KKPR conformity, green zones, temple exclusion zones                                               | Determines what can be built where                     |
| Bali-specific regulations             | Perda Bali 2/2023 (RTRW), Perda Bali 3/2026 (coastal), Perda Bali 4/2026 (land conversion/nominee), moratorium | Local overlay on national law                          |
| Strata title / apartments             | Sarusun, HMSRS, UU 20/2011, foreigner apartment ownership                                                      | Vertical housing ownership path                        |
| Property disputes & fraud             | Certificate disputes, land mafia, fraud cases, nominee failure scenarios                                       | Protection and risk awareness                          |
| Awig-awig / customary land            | Desa adat land restrictions, tanah ayahan desa, customary obligations                                          | Bali-unique land category                              |
| Environmental permits for development | AMDAL, UKL-UPL, SPPL thresholds for construction projects                                                      | Required before building                               |
| Government fees schedule              | BPHTB rates, BPN registration fees, PPAT/notary tariffs, PBB rates                                             | Reference data for transactions                        |
| Lease structuring                     | Duration, extension mechanics, notarization, dispute resolution                                                | Second most common structure for foreigners            |
| Hak Pakai minimum thresholds          | Per-province minimum property values for foreigners                                                            | Practical gatekeeping information                      |

### OUTSIDE NB-5 (Owned by Adjacent Notebooks)

| Topic                                                    | Owned By                | Border Rule                                                                               |
| -------------------------------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------- |
| PT PMA company formation process                         | **NB-3**                | NB-3 owns company setup steps; NB-5 owns property acquisition via the company             |
| KBLI code selection for PT PMA                           | **NB-3**                | NB-3 owns KBLI; NB-5 references KBLI 55193 (villa) and 68110 (property)                   |
| Corporate compliance (LKPM, tax filings)                 | **NB-3** / **NB-4**     | NB-5 mentions compliance burden as a risk factor, does not detail procedures              |
| Property tax rates & calculations (BPHTB, PBB, PPh, VAT) | **NB-4**                | NB-4 owns tax rates/obligations; NB-5 identifies which taxes trigger in transactions      |
| Capital gains tax on property sale                       | **NB-4**                | NB-4 owns; NB-5 flags the tax event                                                       |
| Building permit renewal schedules                        | **NB-6**                | NB-6 owns ongoing compliance; NB-5 owns initial permit acquisition                        |
| Property management compliance                           | **NB-6**                | Ongoing operational compliance is NB-6                                                    |
| Residential property for personal use (lifestyle)        | **NB-8**                | NB-8 covers renting vs buying decision, neighborhood guides; NB-5 covers legal structures |
| Investment ROI calculations for villas                   | **NB-8** / out of scope | Financial modeling is not regulatory intelligence                                         |
| Bali Zero service prices                                 | **PricingTool**         | NEVER in NB-5 — government fees only                                                      |

### Border Definitions (Precise Interfaces)

**NB-5 ↔ NB-3 (Company Setup):**

- NB-3 handles: PT PMA formation, OSS registration, BKPM 5/2025 capital requirements, KBLI selection
- NB-5 handles: Using PT PMA to acquire HGB, converting Hak Milik to HGB for PT PMA, property-specific licensing
- Shared zone: BKPM 5/2025 capital reduction (IDR 10B → 2.5B paid-up) — NB-3 owns the regulation, NB-5 references the impact on property investment
- Shared zone: Environmental permits (AMDAL/UKL-UPL) for construction — NB-3 Cluster C.3-C.4 covers licensing; NB-5 Cluster D covers property-specific construction permits

**NB-5 ↔ NB-4 (Tax & Fiscal):**

- NB-4 handles: BPHTB rate (max 5%), PPh rate (2.5%), PBB annual tax, VAT on new properties (12%), capital gains
- NB-5 handles: Which taxes trigger at which transaction step (BPHTB at transfer, PPh at sale, PBB annually)
- Rule: NB-5 says "BPHTB applies at 5% of transaction value"; NB-4 says "how to calculate, pay, and optimize BPHTB"

**NB-5 ↔ NB-6 (Operations & Compliance):**

- NB-6 handles: SLF renewal, building maintenance compliance, strata title management, ongoing permit compliance
- NB-5 handles: Initial PBG acquisition, initial SLF issuance, construction permits
- Rule: NB-5 = getting the permit; NB-6 = maintaining the permit

**NB-5 ↔ NB-8 (Expat Life):**

- NB-8 handles: Neighborhood quality, lifestyle factors, renting experience, co-living culture
- NB-5 handles: Legal structures for ownership, lease contracts, zoning restrictions
- Rule: NB-5 = legal framework for owning/leasing; NB-8 = practical living experience

---

## 2. CLUSTER DESIGN — Validated and Refined

### Cluster A: Land Rights & Title System (8-10 sources)

**Scope:** The complete hierarchy of land rights under Indonesian law, from Hak Milik through Hak Sewa. Foundation for all other clusters.

| #   | Subtopic                                           | Regulatory Anchor                                                                                             | Notes                                                                                  |
| --- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| A.1 | Hak Milik (Freehold) — Indonesian-only restriction | UUPA 5/1960 Pasal 20-27, specifically Pasal 21                                                                | Foreigners absolutely excluded                                                         |
| A.2 | Hak Guna Bangunan (HGB) — Right to Build           | UUPA Pasal 35-40, PP 18/2021 Art 34-37                                                                        | 30+20+30 = 80 years (post Omnibus Law)                                                 |
| A.3 | Hak Pakai (Right of Use) — foreigner path          | UUPA Pasal 41-43, PP 18/2021 Art 49-58, PP 103/2015 (revoked by PP 18/2021 but implementing regs still valid) | 30+20+30 = 80 years                                                                    |
| A.4 | Hak Guna Usaha (Cultivation Rights)                | UUPA Pasal 28-34, PP 18/2021 Art 18-33                                                                        | 35+25+35 = 95 years; for plantation/agriculture                                        |
| A.5 | Hak Pengelolaan (HPL — Management Rights)          | PP 18/2021 Art 1-17                                                                                           | Government/SOE land management                                                         |
| A.6 | Extension vs Renewal distinction                   | PP 18/2021 Art 37                                                                                             | Critical: perpanjangan (before expiry, routine) vs pembaharuan (after, not guaranteed) |
| A.7 | Strata title (HMSRS — apartment units)             | UU 20/2011, PP 18/2021 Art 59-76                                                                              | Foreigners can hold HMSRS under specific conditions                                    |
| A.8 | Land rights to space above/below land              | PP 18/2021 Art 77                                                                                             | New concept from Omnibus Law — MRT, underground facilities                             |

**Estimated sources:** 8-10 (3 T0, 2 T1, 3-5 T2)

### Cluster B: Foreign Ownership Structures (10-14 sources)

**Scope:** The three legal paths for foreigners plus the illegal fourth path (nominee). Practical comparison, eligibility, costs, risks.

| #   | Subtopic                                            | Regulatory Anchor                                                                     | Notes                                                       |
| --- | --------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| B.1 | Hak Pakai for foreigners — eligibility & process    | PP 103/2015 (provisions still active), Permen ATR/BPN 29/2016, Permen ATR/BPN 13/2016 | KITAS/KITAP required, 1 property per person                 |
| B.2 | Minimum property value thresholds by province       | Permen ATR/BPN 29/2016 Lampiran                                                       | Bali: IDR 2-5 billion depending on kabupaten                |
| B.3 | PT PMA + HGB ownership path                         | UU 25/2007, BKPM Reg 5/2025, PP 18/2021                                               | Capital reduced to IDR 2.5B paid-up in 2025                 |
| B.4 | Leasehold (Hak Sewa) structuring                    | PP 44/1994, KUH Perdata (Civil Code)                                                  | No statutory max term; market standard 25-30 years          |
| B.5 | PPJB (Preliminary Sale Agreement)                   | KUH Perdata, PP 18/2021                                                               | Pre-AJB binding agreement; frequent source of disputes      |
| B.6 | Nominee arrangement — prohibition & risks           | UUPA Pasal 21 & 26, PP 18/2021, Perda Bali 4/2026                                     | Criminal sanctions in Bali since Feb 2026                   |
| B.7 | Mixed marriage property rights                      | UU 1/1974 (Marriage Law), UUPA Pasal 21                                               | Without prenup: WNA spouse triggers divestment of Hak Milik |
| B.8 | Comparison matrix: Hak Pakai vs Leasehold vs PT PMA | Cross-reference of B.1-B.4                                                            | Decision framework based on residency, budget, purpose      |

**Estimated sources:** 10-14 (2 T0, 3 T1, 4-5 T2, 2-4 T3)

### Cluster C: Transaction Process & Due Diligence (8-12 sources)

**Scope:** End-to-end property acquisition from due diligence through BPN registration.

| #   | Subtopic                                                          | Regulatory Anchor                                                    | Notes                                                              |
| --- | ----------------------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------ |
| C.1 | Land title verification at BPN                                    | PP 24/1997 (partially revoked), PP 18/2021 (registration provisions) | Check certificate authenticity, encumbrances, Hak Tanggungan       |
| C.2 | PPAT (Land Deed Official) role and process                        | PP 37/1998, Permen ATR/BPN 18/2021                                   | PPAT drafts AJB; jurisdiction-specific                             |
| C.3 | AJB (Sale & Purchase Deed) execution                              | PP 24/1997, PP 18/2021                                               | Title officially transfers at AJB signing before PPAT              |
| C.4 | BPN registration post-transfer                                    | PP 18/2021 (electronic registration), Permen ATR/BPN 16/2021         | 7 working days for PPAT to file; electronic registration expanding |
| C.5 | Hak Milik → HGB conversion for PT PMA                             | Permen ATR/BPN 18/2021                                               | Required when PT PMA acquires freehold-titled land                 |
| C.6 | KKPR (land use conformity confirmation)                           | PP 28/2025                                                           | Required to confirm zoning allows intended use                     |
| C.7 | Due diligence checklist: certificate, zoning, access, tax history | Practice-based (T3 sources)                                          | BPN search, RTRW check, physical inspection                        |
| C.8 | Electronic land registration / digital certificates               | PP 18/2021 Art 85-87                                                 | Ministry pushing digitalization; e-certificates expanding          |

**Estimated sources:** 8-12 (2 T0, 2 T1, 4-6 T2/T3, 2 professional practice guides)

### Cluster D: Development & Construction (8-12 sources)

**Scope:** Building permits, environmental clearance, zoning compliance for property development in Bali.

| #   | Subtopic                                              | Regulatory Anchor                              | Notes                                                           |
| --- | ----------------------------------------------------- | ---------------------------------------------- | --------------------------------------------------------------- |
| D.1 | PBG (Building Approval) — replacing IMB               | UU 28/2002 as amended by UU 6/2023, PP 16/2021 | Applied via SIMBG online system                                 |
| D.2 | SLF (Certificate of Building Worthiness)              | PP 16/2021                                     | Required for occupancy; separate from PBG                       |
| D.3 | AMDAL / UKL-UPL / SPPL environmental permits          | PP 22/2021                                     | Threshold-based: large = AMDAL, medium = UKL-UPL, small = SPPL  |
| D.4 | RTRW/RDTR zoning compliance                           | UU 26/2007, Perda Bali 2/2023                  | Must check zone allows intended development                     |
| D.5 | Bali construction moratorium (2025-2026)              | Gubernatorial policy, Perda implementation     | New PBG restricted in many areas; existing permits valid        |
| D.6 | Coastal setback (sempadan pantai) — Perda Bali 3/2026 | Perda Bali 3/2026                              | Beach setback distances, demolition orders for violations       |
| D.7 | Green zone restrictions & land conversion ban         | Perda Bali 4/2026                              | Agricultural land conversion now criminal offense               |
| D.8 | Villa licensing (Pondok Wisata / KBLI 55193)          | UU 18/2025, Permenpar 18/2016, PP 28/2025      | Foreigners need PT PMA; Pondok Wisata restricted to Indonesians |

**Estimated sources:** 8-12 (3 T0, 2 T1, 3-5 T2 Bali-specific, 2 practice guides)

### Cluster E: Disputes, Protection & Risk (6-8 sources)

**Scope:** What goes wrong in Bali property — fraud, disputes, nominee failure, title conflicts, land mafia.

| #   | Subtopic                                  | Regulatory Anchor                                 | Notes                                                       |
| --- | ----------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------- |
| E.1 | Nominee failure scenarios & court cases   | UUPA Pasal 26, criminal code for document fraud   | 30+ foreign victims in 2025 Bali fraud case                 |
| E.2 | PPJB disputes — no AJB follow-through     | KUH Perdata, case law                             | Common: buyer pays, seller never transfers title            |
| E.3 | Certificate disputes / overlapping claims | PP 18/2021 (registration), BPN dispute resolution | Multiple certificates on same land                          |
| E.4 | Land mafia & fraud patterns               | Police/court records, media reports               | $6.2M Australian influencer scam (2025); $2.5M Briton fraud |
| E.5 | Hak Tanggungan (mortgage/security rights) | UU 4/1996                                         | Encumbrances that survive title transfer                    |
| E.6 | Forced divestment scenarios               | PP 18/2021, PP 103/2015                           | When foreigner must sell within 1 year                      |

**Estimated sources:** 6-8 (1 T0, 2 T2, 3-5 T3/T4 news + case studies)

### Cluster F: Bali-Specific Property Landscape (8-10 sources)

**Scope:** Provincial and kabupaten-level regulations, customary law, temple exclusion zones, tourism zoning.

| #   | Subtopic                                     | Regulatory Anchor                                    | Notes                                                 |
| --- | -------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------- |
| F.1 | RTRW Bali 2023-2043 (Perda 2/2023)           | Perda Provinsi Bali 2/2023                           | 30% minimum protected zone; 24 RDTR established       |
| F.2 | Tourism zone designations (Pasal 95)         | Perda 2/2023 Art 95                                  | Tourism area zoning indications                       |
| F.3 | Kawasan lindung (protected zones)            | Perda 2/2023, national conservation law              | Karst zones (Bukit, Nusa Penida), water catchment     |
| F.4 | Coastal protection — Perda 3/2026            | Perda Bali 3/2026 (signed Feb 24, 2026)              | Sempadan pantai enforcement, customary access rights  |
| F.5 | Land conversion & nominee ban — Perda 4/2026 | Perda Bali 4/2026 (signed Feb 24, 2026)              | Criminal sanctions up to 5 years, IDR 1 billion fines |
| F.6 | Awig-awig customary land restrictions        | Desa adat regulations, Perda Desa Adat               | Tanah desa, tanah ayahan desa — cannot be sold freely |
| F.7 | Temple exclusion zones (pura radius)         | Local implementation of RTRW                         | Development restricted near temples                   |
| F.8 | Kabupaten-level RDTR variations              | Badung (6 RDTR), Denpasar (5 RDTR), Gianyar, Tabanan | Each regency has different zoning details             |

**Estimated sources:** 8-10 (2 T0 Perda, 3-4 T2 provincial regulations, 3-4 T3/T4 Bali-specific)

### Cluster G: Regulatory Framework & Updates (6-8 sources)

**Scope:** The overarching legal framework and recent regulatory changes affecting all property topics.

| #   | Subtopic                                    | Regulatory Anchor                          | Notes                                            |
| --- | ------------------------------------------- | ------------------------------------------ | ------------------------------------------------ |
| G.1 | Omnibus Law property impact                 | UU 6/2023 (Cipta Kerja), PP 18/2021        | Most significant land law reform in 20+ years    |
| G.2 | PP 28/2025 (risk-based business licensing)  | PP 28/2025                                 | "Single reference" principle; OSS framework      |
| G.3 | Permen ATR/BPN recent changes (2025)        | Permen 5/2025, 7/2025, 9/2025              | Kewenangan pertanahan restructured               |
| G.4 | UU 18/2025 Tourism Law impact               | UU 18/2025                                 | Villa licensing, accommodation regulation        |
| G.5 | BKPM 5/2025 capital reduction               | Permen Investasi/BKPM 5/2025               | PT PMA capital IDR 10B → 2.5B paid-up            |
| G.6 | 2026 Bali provincial regulations            | Perda 3/2026, Perda 4/2026                 | Coastal protection + land conversion/nominee ban |
| G.7 | Electronic land registration digitalization | PP 18/2021, ATR/BPN digital transformation | e-certificates, electronic PPAT deeds            |

**Estimated sources:** 6-8 (3 T0, 2 T1, 2-3 T2)

---

## 3. T0 REGULATIONS — Verified Inventory

### Confirmed T0 Regulations (National Law / Government Regulation)

| #     | Regulation                  | Full Title (Bahasa)                                                                                                                                          | Status                                                                                                   | Key Provisions for NB-5                                                                                                                                                                                                             | URL                                                                                                   |
| ----- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| T0-1  | **UU 5/1960 (UUPA)**        | Undang-Undang Nomor 5 Tahun 1960 tentang Peraturan Dasar Pokok-Pokok Agraria                                                                                 | **ACTIVE** — foundation law, never revoked                                                               | Pasal 20-27 (Hak Milik), Pasal 28-34 (HGU), Pasal 35-40 (HGB), Pasal 41-43 (Hak Pakai), Pasal 21 (Hak Milik Indonesian-only), Pasal 26 (nominee prohibition)                                                                        | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/47810/)                                     |
| T0-2  | **UU 6/2023 (Cipta Kerja)** | Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja Menjadi Undang-Undang | **ACTIVE** — replaced UU 11/2020 via Perpu 2/2022                                                        | Omnibus law that amended multiple laws including UUPA, building law, spatial planning; enabled PP 18/2021 implementing regulations                                                                                                  | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/246523/uu-no-6-tahun-2023)                  |
| T0-3  | **PP 18/2021**              | Peraturan Pemerintah Nomor 18 Tahun 2021 tentang Hak Pengelolaan, Hak Atas Tanah, Satuan Rumah Susun, dan Pendaftaran Tanah                                  | **ACTIVE** — THE key implementing regulation                                                             | Revoked PP 40/1996, PP 103/2015, and parts of PP 24/1997. Consolidated all land rights (HPL, HGU, HGB, HP), strata title, land registration. HGB/HP now 30+20+30=80 years. Foreign apartment HMSRS rights. Electronic registration. | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/161848/pp-no-18-tahun-2021)                 |
| T0-4  | **PP 103/2015**             | Peraturan Pemerintah Nomor 103 Tahun 2015 tentang Pemilikan Rumah Tempat Tinggal atau Hunian oleh Orang Asing yang Berkedudukan di Indonesia                 | **REVOKED** by PP 18/2021 — but implementing Permen (13/2016, 29/2016) still valid where not conflicting | Originally: 1 residential property per WNA, minimum value thresholds per zone. Revoked PP 41/1996. Key provisions absorbed into PP 18/2021.                                                                                         | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/5682/pp-no-103-tahun-2015)                  |
| T0-5  | **PP 28/2025**              | Peraturan Pemerintah Nomor 28 Tahun 2025 tentang Penyelenggaraan Perizinan Berusaha Berbasis Risiko                                                          | **ACTIVE** — master business licensing regulation                                                        | "Single reference" (acuan tunggal) principle; KKPR zoning conformity; OSS framework; risk classification for property/accommodation businesses                                                                                      | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Download/381375/PP%20Nomor%2028%20Tahun%202025.pdf) |
| T0-6  | **PP 16/2021**              | Peraturan Pemerintah Nomor 16 Tahun 2021 tentang Peraturan Pelaksanaan Undang-Undang Nomor 28 Tahun 2002 tentang Bangunan Gedung                             | **ACTIVE**                                                                                               | PBG replaces IMB; SLF (certificate of worthiness); SBKBG (building ownership); building standards                                                                                                                                   | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/161846/pp-no-16-tahun-2021)                 |
| T0-7  | **UU 28/2002**              | Undang-Undang Nomor 28 Tahun 2002 tentang Bangunan Gedung                                                                                                    | **ACTIVE** (as amended by UU 6/2023)                                                                     | Foundation building law; PBG/SLF basis                                                                                                                                                                                              | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/44863/)                                     |
| T0-8  | **UU 26/2007**              | Undang-Undang Nomor 26 Tahun 2007 tentang Penataan Ruang                                                                                                     | **ACTIVE** (as amended by UU 6/2023)                                                                     | Spatial planning framework; RTRW/RDTR basis; zoning                                                                                                                                                                                 | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/39908/uu-no-26-tahun-2007)                  |
| T0-9  | **UU 20/2011**              | Undang-Undang Nomor 20 Tahun 2011 tentang Rumah Susun                                                                                                        | **ACTIVE** (as amended by UU 6/2023)                                                                     | Apartment/strata title law; SHM Sarusun; foreigner apartment rights; condominium regulation                                                                                                                                         | N/A                                                                                                   |
| T0-10 | **UU 18/2025**              | Undang-Undang Nomor 18 Tahun 2025 tentang Perubahan Ketiga atas Undang-Undang Nomor 10 Tahun 2009 tentang Kepariwisataan                                     | **ACTIVE** (in force Oct 29, 2025)                                                                       | Tourism ecosystem; accommodation licensing framework; affects villa/hospitality property                                                                                                                                            | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/334481/uu-no-18-tahun-2025)                 |
| T0-11 | **PP 44/1994**              | Peraturan Pemerintah Nomor 44 Tahun 1994 tentang Penghunian Rumah oleh Bukan Pemilik                                                                         | **ACTIVE**                                                                                               | Hak Sewa (lease) legal basis; no statutory maximum term                                                                                                                                                                             | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/57275/pp-no-44-tahun-1994)                  |

### Regulations Initially Listed as T0 — Status Clarification

| Regulation                           | Status                              | Notes                                                                                                                                 |
| ------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **PP 40/1996** (HGU, HGB, Hak Pakai) | **REVOKED** by PP 18/2021           | Fully superseded; do NOT include as active T0                                                                                         |
| **PP 24/1997** (Pendaftaran Tanah)   | **PARTIALLY REVOKED** by PP 18/2021 | Land registration provisions replaced; some procedural aspects remain. Include implementing Permen 16/2021 (third amendment) instead. |
| **PP 103/2015** (Foreign Hak Pakai)  | **REVOKED** by PP 18/2021           | Provisions absorbed into PP 18/2021. Implementing Permen 13/2016 and 29/2016 remain valid where not conflicting.                      |

### NEWLY DISCOVERED T0 Regulations (Missing from Prompt)

| #     | Regulation     | Full Title                                                                                                     | Why Critical                                                                                      |
| ----- | -------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| T0-12 | **UU 25/2007** | Undang-Undang Nomor 25 Tahun 2007 tentang Penanaman Modal                                                      | Investment law; PT PMA legal basis; foreign investment framework                                  |
| T0-13 | **UU 40/2007** | Undang-Undang Nomor 40 Tahun 2007 tentang Perseroan Terbatas                                                   | Company law; director liability; PT PMA governance — essential for PT PMA property ownership path |
| T0-14 | **UU 4/1996**  | Undang-Undang Nomor 4 Tahun 1996 tentang Hak Tanggungan                                                        | Mortgage/security rights over land; affects encumbrance checks in due diligence                   |
| T0-15 | **PP 22/2021** | Peraturan Pemerintah Nomor 22 Tahun 2021 tentang Penyelenggaraan Perlindungan dan Pengelolaan Lingkungan Hidup | Environmental assessment framework; AMDAL/UKL-UPL/SPPL thresholds for construction                |

**Total confirmed T0: 15 regulations**

---

## 4. T2-T4 SOURCES — Ministerial Regulations, Circulars, Practice Guides, Social Accounts

### T1 Sources (Implementing Ministerial Regulations — Confirmed)

| #    | Regulation                       | Full Title                                                                                                                                              | Cluster | Status                                                                                            | URL                                                                                                                                                    |
| ---- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| T1-1 | **Permen ATR/BPN 18/2021**       | Tata Cara Penetapan Hak Pengelolaan dan Hak Atas Tanah                                                                                                  | A, B, C | **ACTIVE** — revoked Permen 29/2016 and Permen 13/2016                                            | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/209828/permen-agrariakepala-bpn-no-18-tahun-2021)                                            |
| T1-2 | **Permen ATR/BPN 29/2016**       | Tata Cara Pemberian, Pelepasan, atau Pengalihan Hak Atas Pemilikan Rumah Tempat Tinggal atau Hunian oleh Orang Asing                                    | B       | **REVOKED** by Permen ATR/BPN 18/2021 — but minimum price thresholds in Lampiran still referenced | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/104042/)                                                                                     |
| T1-3 | **Permen ATR/BPN 13/2016**       | Tata Cara Pemberian, Pelepasan atau Pengalihan Hak Atas Pemilikan Rumah Tempat Tinggal atau Hunian oleh Orang Asing                                     | B       | **REVOKED** by Permen 18/2021 — procedures absorbed                                               | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/104027/)                                                                                     |
| T1-4 | **Permen ATR/BPN 16/2021**       | Perubahan Ketiga atas Peraturan Menteri Negara Agraria/Kepala BPN Nomor 3 Tahun 1997 tentang Ketentuan Pelaksanaan PP 24/1997 tentang Pendaftaran Tanah | C       | **ACTIVE** — third amendment to implementation of PP 24/1997                                      | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/209808/)                                                                                     |
| T1-5 | **Permen Investasi/BKPM 5/2025** | Perizinan Berusaha (implementing PP 28/2025 for investment)                                                                                             | B, G    | **ACTIVE** — PT PMA capital reduced to IDR 2.5B; LKPM deadlines extended                          | N/A                                                                                                                                                    |
| T1-6 | **Permen ATR/BPN 5/2025**        | Kewenangan Pertanahan di Tingkat Daerah (replaced Permen 2/2025)                                                                                        | C, G    | **ACTIVE**                                                                                        | [notarismuda.com](https://notarismuda.com/permen-atr-bpn-no-5-2025-gantikan-permen-atr-bpn-no-2-2025-terkait-kewenangan-pertanahan-di-tingkat-daerah/) |
| T1-7 | **Permen ATR/BPN 9/2025**        | Perubahan Kewenangan Pertanahan (comprehensive restructuring)                                                                                           | C, G    | **ACTIVE** (Sept 2025) — 5 major changes to land authority                                        | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/329772/)                                                                                     |
| T1-8 | **Permen ATR/BPN 7/2025**        | (Land registration related — title pending verification)                                                                                                | C       | **ACTIVE** (Aug 2025)                                                                             | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/329573/)                                                                                     |
| T1-9 | **Permenpar 18/2016**            | Pendaftaran Usaha Pariwisata (Tourism Business Registration)                                                                                            | D       | **ACTIVE** — Pondok Wisata restricted to Indonesian citizens                                      | N/A                                                                                                                                                    |

### T2 Sources (Provincial/Local Regulations, Professional Standards)

| #     | Source                                                                                          | Type                    | Cluster         | URL                                                                                                                                                                  |
| ----- | ----------------------------------------------------------------------------------------------- | ----------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T2-1  | **Perda Provinsi Bali 2/2023** — RTRW Bali 2023-2043                                            | Provincial Regulation   | F               | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/262423/perda-prov-bali-no-2-tahun-2023)                                                                    |
| T2-2  | **Perda Provinsi Bali 3/2026** — Pelindungan Pantai dan Sempadan Pantai                         | Provincial Regulation   | F               | [tarubali.baliprov.go.id](https://tarubali.baliprov.go.id/implementasi-kebijakan-pelindungan-pantai-dan-sempadan-pantai-di-bali/)                                    |
| T2-3  | **Perda Provinsi Bali 4/2026** — Pengendalian Alih Fungsi Lahan (nominee ban + land conversion) | Provincial Regulation   | B, E, F         | [barometerbali.com](https://barometerbali.com/berantas-nominee-dan-alih-fungsi-lahan-gubernur-koster-berlakukan-perda-4-tahun-2026-sanksi-pidana-menanti-pelanggar/) |
| T2-4  | **RDTR Badung** (6 RDTR covering entire regency)                                                | Kabupaten Regulation    | D, F            | [tarubali.baliprov.go.id](https://tarubali.baliprov.go.id/satus-rtrw-dan-rdtr-di-provinsi-bali/)                                                                     |
| T2-5  | **RDTR Denpasar** (5 RDTR covering entire city)                                                 | Kabupaten Regulation    | D, F            | [tarubali.baliprov.go.id](https://tarubali.baliprov.go.id/satus-rtrw-dan-rdtr-di-provinsi-bali/)                                                                     |
| T2-6  | PP 37/1998 — Peraturan Jabatan PPAT                                                             | Government Regulation   | C               | N/A                                                                                                                                                                  |
| T2-7  | PP 34/2016 — PPh atas Pengalihan Hak atas Tanah/Bangunan                                        | Government Regulation   | C (tax trigger) | N/A                                                                                                                                                                  |
| T2-8  | PP 46/2002 — PNBP Pertanahan (HGB extension cost formula)                                       | Government Regulation   | A, C            | N/A                                                                                                                                                                  |
| T2-9  | Perpres 10/2021 — Bidang Usaha Penanaman Modal (Positive Investment List)                       | Presidential Regulation | B               | N/A                                                                                                                                                                  |
| T2-10 | UU 1/2022 — Hubungan Keuangan Pemerintah Pusat dan Daerah (BPHTB framework)                     | Law                     | C (tax trigger) | N/A                                                                                                                                                                  |

### T3 Sources (Law Firm Analyses, Practice Guides, BPN Circulars)

| #     | Source                                                                                             | Type               | Cluster | URL                                                                                                                                         |
| ----- | -------------------------------------------------------------------------------------------------- | ------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| T3-1  | ABNR — "New Omnibus Law Regulation Makes Significant Changes to Indonesian Land Law Regime" (2021) | Law firm analysis  | A, G    | [abnrlaw.com](https://www.abnrlaw.com/news/new-omnibus-law-regulation-makes-significant-changes-to-indonesian-land-law-regime)              |
| T3-2  | Atyanto Law (GAP) — "Issuance of GR 18/2021 as Indonesia's Property Business Incentives"           | Law firm analysis  | A, B, G | [atyantolaw.com](https://atyantolaw.com/client-alert-issuance-of-government-regulation-18-2021-as-indonesias-property-business-incentives/) |
| T3-3  | Bali Property Rules — PP 28/2025 Foreign Property Rules: Full Breakdown                            | Professional guide | B, G    | [balipropertyrules.com](https://balipropertyrules.com/guides/pp-28-2025-foreign-property-bali/)                                             |
| T3-4  | Bali Property Rules — Hak Pakai vs Leasehold vs PT PMA Comparison (2026)                           | Professional guide | B       | [balipropertyrules.com](https://balipropertyrules.com/guides/foreign-ownership-comparison-bali/)                                            |
| T3-5  | Bali Property Rules — Nominee Ownership Risks                                                      | Professional guide | E       | [balipropertyrules.com](https://balipropertyrules.com/guides/nominee-ownership-risks-bali/)                                                 |
| T3-6  | Bali Property Rules — Construction Moratorium 2026                                                 | Professional guide | D       | [balipropertyrules.com](https://balipropertyrules.com/guides/bali-construction-moratorium-foreigners/)                                      |
| T3-7  | Seven Stones Indonesia — "Bali Crackdown on Nominee Agreements" (2025)                             | Industry report    | E       | [sevenstonesindonesia.com](https://realestate.sevenstonesindonesia.com/bali-crackdown-on-nominee-agreements-new-regulation-coming-soon/)    |
| T3-8  | Seven Stones Indonesia — "Verify Land Ownership Before Buying"                                     | Practice guide     | C       | [sevenstonesindonesia.com](https://realestate.sevenstonesindonesia.com/how-to-verify-land-ownership-in-bali-before-buying-property/)        |
| T3-9  | Lexology — Facilitation for Foreign Nationals in Acquiring Property (AKSET Law)                    | Legal analysis     | B       | [mondaq.com](https://mondaq.com/real-estate/1251864/)                                                                                       |
| T3-10 | Lexology — Indonesia Omnibus Law Real Estate Cluster                                               | Legal analysis     | A, G    | [lexology.com](https://www.lexology.com/library/detail.aspx?g=2b3b31eb-308c-40d9-9ad1-5f6cb6f2ca35)                                         |
| T3-11 | Schinder Law — Land Acquisition in Indonesia: Key Steps                                            | Practice guide     | C       | [schinderlawfirm.com](https://schinderlawfirm.com/blog/land-acquisition-in-indonesia-key-steps-every-investor-must-know/)                   |
| T3-12 | Makarim & Taira S — "Further Regulation on Foreign Owned Property"                                 | Law firm analysis  | B       | [makarim.com](https://www.makarim.com/index.php/news/further-regulation-on-foreign-owned-property)                                          |
| T3-13 | Indonesia Real Estate Law (Leks&Co) — "Land Registration Regulation post Job Creation Law"         | Legal analysis     | C, G    | [indonesiarealestatelaw.com](https://indonesiarealestatelaw.com/land-registration-regulation-post-job-creation-law/)                        |
| T3-14 | Tarubali.baliprov.go.id — Official Bali spatial planning portal                                    | Government source  | D, F    | [tarubali.baliprov.go.id](https://tarubali.baliprov.go.id/)                                                                                 |
| T3-15 | Balisatudata.baliprov.go.id — Peta Tata Ruang (official zoning maps)                               | Government source  | F       | [balisatudata.baliprov.go.id](https://balisatudata.baliprov.go.id/peta-tata-ruang)                                                          |

### T4 Sources — Social Accounts to Monitor

| #     | Account                        | Platform    | Handle                    | Followers | Relevance                                              | Priority |
| ----- | ------------------------------ | ----------- | ------------------------- | --------- | ------------------------------------------------------ | -------- |
| T4-1  | **Kementerian ATR/BPN**        | Instagram   | @kementerian.atrbpn       | 749K      | National land policy announcements, new Permen         | CRITICAL |
| T4-2  | **Kementerian ATR/BPN**        | X/Twitter   | @kem_atrbpn               | —         | Same + faster breaking news                            | CRITICAL |
| T4-3  | **Kanwil BPN Provinsi Bali**   | Instagram   | @kanwil.bpn.bali          | —         | Bali-specific BPN policies, registration updates       | HIGH     |
| T4-4  | **Kantah Kab Badung**          | Instagram   | @kantahkabbadung          | —         | Badung (Seminyak, Canggu, Uluwatu) land office updates | HIGH     |
| T4-5  | **Kantah Kab Gianyar**         | Instagram   | @kantahkabgianyar         | —         | Gianyar (Ubud) land office updates                     | MEDIUM   |
| T4-6  | **Ditjen Penataan Agraria**    | Instagram   | @ditjenpenataanagraria    | 12K       | Agrarian/land policy direction                         | HIGH     |
| T4-7  | **Ditjen Tata Ruang**          | Instagram   | @ditjentataruang          | 34K       | Spatial planning policy, RTRW/RDTR updates             | HIGH     |
| T4-8  | **Tarubali (Tata Ruang Bali)** | Website/RSS | tarubali.baliprov.go.id   | —         | Official Bali spatial planning news                    | CRITICAL |
| T4-9  | **Pemprov Bali**               | Instagram   | @pikirangusde / @baliprov | —         | Provincial government policy, new Perda                | HIGH     |
| T4-10 | **BKPM/Kemenvestasi**          | Instagram   | @kementerianinvestasi     | —         | Investment policy changes affecting PT PMA             | MEDIUM   |

---

## 5. GAP ANALYSIS — What Is Missing from the 6 Seed Sources

The 6 seed sources in NB-5 are internal Bali Zero guides. Based on the research, the following critical topics are likely **completely missing or inadequately covered**:

### Critical Gaps (Must Fill Immediately)

| Gap                                                                  | Why Critical                                                                                                                                                                                      | Cluster |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| **PP 28/2025 and its impact on property licensing**                  | Brand new (2025) regulation that restructured all business licensing including property. "Single reference" principle changes how local regulations interact with national law.                   | G       |
| **BKPM Regulation 5/2025 capital reduction**                         | PT PMA paid-up capital reduced 75% (IDR 10B → 2.5B). Most guides still cite old figure. Direct impact on client cost calculations.                                                                | B       |
| **Perda Bali 3/2026 (coastal setback enforcement)**                  | Signed Feb 24, 2026 — brand new. Affects all beachfront property. Demolition orders already being issued.                                                                                         | F       |
| **Perda Bali 4/2026 (land conversion + nominee criminal sanctions)** | Signed Feb 24, 2026 — brand new. Criminal penalties for nominee arrangements and agricultural land conversion. Up to 5 years imprisonment.                                                        | E, F    |
| **PP 18/2021 comprehensive land reform**                             | The most significant land law change in 20+ years. Revoked PP 40/1996 and PP 103/2015. Changed duration formulas (HP from 70 → 80 years). Extended apartment rights to foreigners.                | A       |
| **Extension vs renewal distinction**                                 | Perpanjangan (before expiry, routine) vs pembaharuan (after extension ends, not guaranteed). Virtually no English-language source explains this correctly. Affects all Hak Pakai and HGB holders. | A, B    |
| **Bali construction moratorium**                                     | Current restrictions on new PBG issuance in many areas. Existing permits valid but new construction blocked. Direct impact on developers.                                                         | D       |
| **UU 18/2025 Tourism Law**                                           | Third amendment to tourism law; ecosystem-based tourism; accommodation licensing framework; March 2026 OTA enforcement deadline.                                                                  | D, G    |
| **Permen ATR/BPN 2025 series** (5/2025, 7/2025, 9/2025)              | Three new ministerial regulations in 2025 restructuring land authority delegation. Affects BPN processing and local registration.                                                                 | G       |
| **Awig-awig and customary land**                                     | Desa adat land cannot be freely sold. Temple-related land has additional restrictions. Not covered in most property guides but critical for Bali.                                                 | F       |

### Moderate Gaps (Should Fill in Population Phase)

| Gap                                                 | Why Important                                                                                           | Cluster |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------- |
| Electronic land registration (e-certificate)        | Government pushing digitalization; affects how titles are verified and transferred                      | C       |
| KKPR (land use conformity confirmation) requirement | New prerequisite under PP 28/2025 for all development activities                                        | C, D    |
| Strata title foreigner rights (HMSRS on HGB land)   | Legal uncertainty identified by ABNR — how can foreigner hold HMSRS on HGB-land if they can't hold HGB? | A       |
| HGB extension cost formula (PP 46/2002)             | Practical cost planning for PT PMA property holders at renewal time                                     | B       |
| Constitutional Court Decision 198/PUU-XXIII/2025    | Recent MK decision on non-residential apartment regulation gap                                          | A       |
| Mixed marriage property complexities                | UU 1/1974 interacts with UUPA — without prenup, foreign spouse triggers Hak Milik divestment            | B       |

---

## 6. CROSS-DOMAIN RULES — Precise Interface Definitions

### NB-5 ↔ NB-3 (Company Setup) Interface

```
┌─────────────────────────────────────────────────────────┐
│                    SHARED ZONE                           │
│  PT PMA as property-holding vehicle                      │
│  Environmental permits (AMDAL/UKL-UPL) for construction  │
│  BKPM 5/2025 capital requirements                        │
├─────────────────────┬───────────────────────────────────┤
│     NB-3 OWNS       │           NB-5 OWNS               │
│                     │                                    │
│  PT PMA formation   │  HGB acquisition via PT PMA       │
│  OSS registration   │  Hak Milik → HGB conversion       │
│  KBLI selection     │  Property-specific licensing       │
│  BKPM compliance    │  BKPM 5/2025 impact on property   │
│  LKPM reporting     │  PT PMA capital as property cost   │
│  Company law        │  Company as property vehicle       │
│  Articles of Assoc  │  Property rights under company     │
│  Share structure     │  Exit strategies (share vs asset)  │
└─────────────────────┴───────────────────────────────────┘
```

**Handoff rule:** When a client asks "How do I set up a PT PMA to buy property?", NB-5 covers the property acquisition side (why PT PMA, HGB rights, costs as property investment). NB-3 covers the company formation side (registration steps, KBLI, OSS, directors). The NB-5 Master Document cross-references NB-3 for company formation procedures.

### NB-5 ↔ NB-4 (Tax & Fiscal) Interface

```
┌─────────────────────────────────────────────────────────┐
│                    SHARED ZONE                           │
│  Property transaction tax triggers                       │
├─────────────────────┬───────────────────────────────────┤
│     NB-4 OWNS       │           NB-5 OWNS               │
│                     │                                    │
│  BPHTB rate (5%)    │  BPHTB triggers at AJB signing    │
│  PPh rate (2.5%)    │  PPh triggered at property sale    │
│  PBB calculation    │  PBB as ongoing ownership cost     │
│  VAT on new (12%)   │  VAT triggers on developer sale    │
│  Capital gains tax  │  CGT as exit cost consideration    │
│  Tax optimization   │  Tax costs in structure comparison │
│  Double taxation    │  Total transaction cost estimate   │
└─────────────────────┴───────────────────────────────────┘
```

**Handoff rule:** NB-5 says "BPHTB of 5% applies when you acquire property via AJB" and "total transaction costs are approximately 6-7% of property value". NB-4 says "here is how to calculate BPHTB: (NPOP - NPOPTKP) x 5%, where NPOPTKP varies by region". NB-5 identifies the tax event; NB-4 explains the tax mechanics.

### NB-5 ↔ NB-6 (Operations & Compliance) Interface

```
┌─────────────────────────────────────────────────────────┐
│                    SHARED ZONE                           │
│  Building permits lifecycle                              │
├─────────────────────┬───────────────────────────────────┤
│     NB-6 OWNS       │           NB-5 OWNS               │
│                     │                                    │
│  SLF renewal        │  Initial PBG acquisition          │
│  Building maint     │  Initial SLF issuance             │
│  Permit compliance  │  Construction permits             │
│  Strata mgmt        │  PBG/SLF as development step     │
│  Environmental      │  AMDAL/UKL-UPL for new build     │
│  monitoring         │  Zoning check for new development │
│  Ongoing operations │  One-time permit acquisition       │
└─────────────────────┴───────────────────────────────────┘
```

**Handoff rule:** NB-5 covers getting PBG and SLF for a new construction project. Once the building is occupied and operating, NB-6 covers maintaining SLF validity, building compliance, and operational permits.

---

## 7. CAPACITY MODEL — Source Count Targets per Tier and Cluster

### Target: 55-65 ACTIVE sources (following NB-2 model of ~55 sources, NHS target 0.75+)

| Cluster                       | T0     | T1     | T2     | T3     | T4    | Total Target |
| ----------------------------- | ------ | ------ | ------ | ------ | ----- | ------------ |
| A: Land Rights & Title        | 3      | 2      | 1      | 2      | 0     | **8-10**     |
| B: Foreign Ownership          | 2      | 3      | 2      | 4      | 0     | **10-14**    |
| C: Transaction Process        | 2      | 2      | 2      | 4      | 0     | **8-12**     |
| D: Development & Construction | 3      | 1      | 3      | 3      | 0     | **8-12**     |
| E: Disputes & Protection      | 1      | 0      | 1      | 4      | 2     | **6-8**      |
| F: Bali-Specific              | 0      | 0      | 5      | 3      | 3     | **8-10**     |
| G: Regulatory Framework       | 4      | 3      | 0      | 2      | 0     | **6-8**      |
| **TOTAL**                     | **15** | **11** | **14** | **22** | **5** | **55-65**    |

### Notes on Capacity

- **T0 sources are shared across clusters** — UU 5/1960, PP 18/2021, PP 28/2025 each serve 3-4 clusters
- **Bali-specific sources (Cluster F) are almost entirely T2-T4** — this is expected because property law has massive local component
- **T3 is the largest tier** — reflects the need for practical interpretation of complex regulations
- **T4 is intentionally small** — 5 social monitoring accounts focused on breaking regulatory changes
- **70 ACTIVE cap** from NB-2 design applies; keep 55-65 active, 5-10 in quarantine/triage

### Source Distribution by Language

| Language         | % Target | Rationale                                                               |
| ---------------- | -------- | ----------------------------------------------------------------------- |
| Bahasa Indonesia | 55%      | Regulations, government sources, legal analyses                         |
| English          | 35%      | Law firm analyses, foreigner-oriented practice guides                   |
| Bilingual/bridge | 10%      | Sources with both languages (e.g., balipropertyrules.com, lexology.com) |

NB-5 needs **more Bahasa sources than NB-2** (which was 60% Bahasa / 30% English) because property law has a massive local/provincial component where sources are exclusively in Bahasa.

---

## 8. 2025-2026 REGULATORY UPDATES

### Major Changes (Confirmed and Grounded)

| #   | Change                                                           | Date         | Impact                                                                                                                            | Source                                                                                                                                                               |
| --- | ---------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **PP 28/2025** — Risk-based business licensing overhaul          | 2025         | "Single reference" principle; KKPR zoning conformity required; OSS framework for property businesses                              | [balipropertyrules.com](https://balipropertyrules.com/guides/pp-28-2025-foreign-property-bali/)                                                                      |
| 2   | **BKPM Regulation 5/2025** — PT PMA capital reduction            | 2025         | Minimum paid-up capital IDR 10B → 2.5B (~$150K). Land/building value counts toward total investment. 12-month capital lock-up.    | [balipropertyrules.com](https://balipropertyrules.com/guides/foreign-ownership-comparison-bali/)                                                                     |
| 3   | **Permen ATR/BPN 5/2025** — Local land authority restructuring   | May 2025     | Replaced Permen 2/2025; new delegation of land registration authority to local level                                              | [notarismuda.com](https://notarismuda.com/permen-atr-bpn-no-5-2025-gantikan-permen-atr-bpn-no-2-2025-terkait-kewenangan-pertanahan-di-tingkat-daerah/)               |
| 4   | **Permen ATR/BPN 9/2025** — Comprehensive land authority changes | Sept 2025    | 5 major changes to pertanahan kewenangan (land authority)                                                                         | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/329772/)                                                                                                   |
| 5   | **UU 18/2025** — New Tourism Law                                 | Oct 29, 2025 | Ecosystem-based tourism; accommodation licensing framework; OTA enforcement deadline March 2026                                   | [peraturan.bpk.go.id](https://peraturan.bpk.go.id/Details/334481/uu-no-18-tahun-2025)                                                                                |
| 6   | **Perda Bali 3/2026** — Coastal Protection                       | Feb 24, 2026 | Sempadan pantai enforcement; customary access protected; demolition orders for violations; beach setback distances                | [bali.antaranews.com](https://bali.antaranews.com/berita/400191/)                                                                                                    |
| 7   | **Perda Bali 4/2026** — Land Conversion & Nominee Ban            | Feb 24, 2026 | Criminal sanctions for nominee land ownership (up to 5 years imprisonment, IDR 1B fines); agricultural land conversion prohibited | [barometerbali.com](https://barometerbali.com/berantas-nominee-dan-alih-fungsi-lahan-gubernur-koster-berlakukan-perda-4-tahun-2026-sanksi-pidana-menanti-pelanggar/) |
| 8   | **Bali construction moratorium**                                 | 2025-2026    | New PBG restricted in many areas; existing permits/rights preserved                                                               | [balipropertyrules.com](https://balipropertyrules.com/guides/bali-construction-moratorium-foreigners/)                                                               |
| 9   | **ATR/BPN certificate digitalization mandate**                   | 2026         | Older paper-based land certificates must be converted to digital; minister announced transition                                   | [jakarta.akurat.co](https://jakarta.akurat.co/bale-warga/1315490815/)                                                                                                |
| 10  | **Constitutional Court Decision 198/PUU-XXIII/2025**             | 2025         | Addresses regulatory gap for non-residential apartments                                                                           | [lexology.com](https://www.lexology.com/library/detail.aspx?g=a68664b4-067f-4339-b7ef-dcf6d0679cf7)                                                                  |

### PP 103/2015 Amendment Status

**PP 103/2015 was REVOKED by PP 18/2021** (confirmed by ABNR law firm analysis). It was NOT amended — it was replaced. Key finding:

> "The Regulation revokes: (i) Government Regulation No. 40 of 1996 on HGU, HGB and HP; (ii) Government Regulation No. 103 of 2015 on Ownership of Homes and Residential Property by Foreigners Domiciled in Indonesia; and (iii) certain provisions of Government Regulation No. 24 of 1997 on Land Registration."
> — ABNR, May 2021

However, implementing Permen (ATR/BPN 13/2016 and 29/2016) "remain in effect in so far as they do not conflict with the Regulation." These too were later revoked by Permen ATR/BPN 18/2021.

### New Permen ATR/BPN in 2025 (Discovery)

Three significant Permen ATR/BPN were issued in 2025, all affecting land administration:

| Permen | Subject                         | Date      | Impact                                                         |
| ------ | ------------------------------- | --------- | -------------------------------------------------------------- |
| 5/2025 | Kewenangan Pertanahan Daerah    | May 2025  | Restructured local land authority delegation                   |
| 7/2025 | (Land registration related)     | Aug 2025  | Details pending verification                                   |
| 9/2025 | Comprehensive authority changes | Sept 2025 | 5 major changes; described as "total change" in land authority |

The rapid succession of Permen (2/2025 → 5/2025 → 9/2025) within a single year has been criticized: "Revisi Berkali-kali Permen Hak Atas Tanah Bisa Bikin Bingung" (Repeated revisions of land rights Permen can cause confusion) — [industriproperti.com](https://www.industriproperti.com/headline/permen-hak-atas-tanah/).

### Bali Provincial Regulations (February 2026 — BRAND NEW)

Both Perda 3/2026 and Perda 4/2026 were signed on February 24, 2026 by Governor Wayan Koster. They represent the most significant provincial-level property regulatory changes in years:

**Perda 3/2026** (Coastal Protection):

- Protects pantai (beach) and sempadan pantai (coastal setback zones)
- Prioritizes ceremonial/adat access to beaches
- Balances environmental protection with local economic sustainability
- Demolition orders already being enforced for violations (Sanur case, late 2025)

**Perda 4/2026** (Land Conversion & Nominee):

- Criminal sanctions for nominee land ownership transfers
- Penalties: up to 5 years imprisonment, IDR 1 billion fines
- Criminalizes agricultural land conversion (sawah → villa)
- References Indonesian Criminal Code for document manipulation and ownership fraud

### IKN (New Capital) Impact on Bali Property Market

No direct regulatory impact on Bali property law was found from IKN (Ibu Kota Nusantara) relocation. The primary impact is market-based rather than regulatory: potential investor attention shift from Bali to IKN for government-adjacent projects. Bali property regulations remain governed by Bali provincial and national law, unaffected by IKN administrative arrangements. This is a T4 monitoring topic, not a T0/T1 regulatory concern.

---

## APPENDIX: Key Corrections to Common Misconceptions

Based on the research, the following widespread errors were identified in English-language property guides:

| Misconception                                            | Reality                                                                | Source                                |
| -------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------- |
| "Hak Pakai lasts 70 years (30+20+20)"                    | **80 years (30+20+30)** post PP 18/2021                                | PP 18/2021 Art 37; ABNR analysis      |
| "HGB lasts 70 years (30+20+20)"                          | **80 years (30+20+30)** post PP 18/2021                                | PP 18/2021; ABNR analysis             |
| "PT PMA requires IDR 10 billion paid-up capital"         | **IDR 2.5 billion** since BKPM 5/2025 Art 26(10)                       | Bali Property Rules; Withers analysis |
| "Leasehold maximum is 99 years"                          | **No statutory maximum** under PP 44/1994                              | PP 44/1994; market practice only      |
| "PP 103/2015 is the current foreign property regulation" | **Revoked by PP 18/2021** — provisions absorbed                        | ABNR analysis; PP 18/2021 text        |
| "HGB can be converted to Hak Milik for a company"        | **Impossible** — UUPA Pasal 21 restricts HM to citizens                | UUPA 5/1960                           |
| "Nominee agreements are gray area"                       | **Explicitly illegal** + criminal sanctions in Bali since Perda 4/2026 | UUPA Pasal 26; Perda Bali 4/2026      |

---

_Report prepared by Claude Opus 4.6 — Search-Grounded Researcher, NB-5 Brainstorm_
_Sources queried: 2026-03-29, Pro machine_
_Total distinct sources identified: 67 (15 T0, 9 T1, 10 T2, 15 T3, 10 T4 monitoring, 8 academic)_

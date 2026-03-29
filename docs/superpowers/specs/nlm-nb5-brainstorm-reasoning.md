# NB-5: Property & Real Estate Indonesia — Chain-of-Thought Reasoning

> **Role:** Chain-of-Thought Reasoner (DeepSeek R1 equivalent)
> **Date:** 2026-03-29
> **Author:** Claude Opus 4.6 (reasoning role)
> **Input:** NB-5 brainstorm prompt + NB-2 methodology (Steps 1, 3, 4)
> **Reference:** NB-4 prompt (for border coordination)

---

## 1. PERIMETER REASONING — Border Cases Analyzed

### 1.1 NB-3 (Company Setup) vs NB-5 (Property): The PT PMA Split

**The core question:** Where does "PT PMA as property-holding vehicle" belong?

**Reasoning chain:**

1. A foreign investor who wants to acquire property via HGB needs a PT PMA.
2. Creating the PT PMA involves: company name, KBLI selection, capital deposit, OSS-RBA registration, akta pendirian, SK Kemenkumham. This is ENTIRELY NB-3 territory.
3. Once the PT PMA exists as a legal entity, the question becomes: "How does this PT PMA acquire land rights?" This is a PROPERTY question, not a company formation question.
4. The pivot point is: **the moment the PT PMA has SK Kemenkumham and wants to transact on land.**

**Proposed rule:**

- NB-3 owns: PT PMA formation process, KBLI 68xx selection for real estate activities, minimum capital requirements for PMA, shareholder structure, OSS-RBA licensing for real estate KBLI.
- NB-5 owns: PT PMA acquiring HGB/Hak Pakai, the land transaction process, BPN registration of the company's land rights, the ongoing rights management (extension, renewal).
- **Trigger sentence:** "PT PMA acquires or holds land rights" = NB-5. "Setting up a PT PMA (including for property purposes)" = NB-3.

**Edge case 1: KBLI selection for property activities.**
A client asks "Which KBLI should my PT PMA use to buy property in Bali?" This is a HYBRID question. The KBLI classification system is NB-3. The knowledge that KBLI 68xx (real estate) is needed for property holding is NB-5 context that NB-3 should reference. Resolution: NB-3 lists KBLI codes and their implications for licensing. NB-5's MD-3 (Cross-Domain) notes: "For PT PMA KBLI selection for property activities, see NB-3 Cluster C."

**Edge case 2: Minimum capital for property PMA.**
PP 103/2015 and related regulations set minimum property values for foreigner Hak Pakai. The PMA Act sets minimum investment capital for PT PMA. These are different thresholds. NB-3 owns minimum PMA capital. NB-5 owns minimum property value thresholds for foreigner acquisition. They are distinct regulatory requirements that sometimes both apply to the same client.

**Edge case 3: Mixed-purpose PT PMA.**
A PT PMA with KBLI for consulting (62010) AND real estate (68110). The company formation is NB-3. The property transaction is NB-5. The question "Can a consulting PMA also hold property?" is an NB-3 question about KBLI scope. The question "What happens to the HGB when the PMA changes its KBLI?" is NB-5 because it concerns land rights continuity.

### 1.2 NB-4 (Tax & Fiscal) vs NB-5 (Property): The Tax Split

**The core question:** Property transactions trigger multiple taxes. Who owns what?

**Reasoning chain:**

1. When someone buys property in Indonesia, these taxes apply:
   - **BPHTB** (Bea Perolehan Hak Atas Tanah dan Bangunan) — acquisition tax, 5% of NJOP-NJOPTKP
   - **PPh** (Pajak Penghasilan) — seller's income tax on disposal, 2.5% of transaction value
   - **PPN** (Pajak Pertambahan Nilai) — VAT on new property from developer, 11%
2. Annually:
   - **PBB** (Pajak Bumi dan Bangunan) — property tax, varies by NJOP
3. On rental income:
   - **PPh Pasal 4(2)** — 10% final tax on rental income
   - **PPh Pasal 26** — 20% withholding on payments to foreign entities (may be reduced by treaty)

**Proposed split:**

- NB-4 owns: Tax RATES, tax CALCULATION methods, tax FILING obligations, tax TREATIES, NPWP requirements, DGT enforcement, tax penalties, tax optimization strategies.
- NB-5 owns: WHICH taxes trigger at WHICH point in the property lifecycle, the transactional context ("when you sign AJB, BPHTB is due before BPN registration"), the practical sequence of tax payments in a property deal.
- NB-5 REFERENCES NB-4 for: current rates, filing deadlines, treaty applicability.

**Trigger sentence:** "What tax rate applies?" = NB-4. "When in the property purchase process do I pay BPHTB?" = NB-5.

**Edge case 1: NJOP (Nilai Jual Objek Pajak).**
NJOP is the government-assessed value of land and buildings. It is used for both PBB calculation (NB-4 concern: how the tax is calculated) and property valuation (NB-5 concern: is the asking price reasonable relative to NJOP?). Resolution: NB-4 owns NJOP as a tax base. NB-5 may reference NJOP in the context of due diligence ("check NJOP at kelurahan to verify fair value") but links to NB-4 for the tax calculation.

**Edge case 2: Capital gains on property disposal.**
A foreigner sells their Hak Pakai property. PPh 2.5% applies. The capital gains treatment, withholding mechanism, and treaty relief are NB-4. The circumstance that triggers the gain (sale, expiry of lease, conversion) and the practical process (PPAT withholds and remits) is NB-5. This requires tight cross-referencing.

**Edge case 3: Property as investment vehicle — ROI calculation.**
When NB-5 discusses villa rental ROI (Cluster E), rental income tax is a material factor. NB-5 must include the tax impact in its analysis but must REFERENCE NB-4 for rates, not hardcode them. If PPh Pasal 4(2) changes from 10% to 12%, only NB-4 needs updating; NB-5's MD-3 links to NB-4's current rates.

### 1.3 NB-6 (Operations & Compliance) vs NB-5 (Property): The Permit Split

**The core question:** Building permits, environmental compliance, and ongoing property management — NB-5 or NB-6?

**Reasoning chain:**

1. Building a villa in Bali requires:
   - PBG (Persetujuan Bangunan Gedung) — replaced IMB — building permit
   - SLF (Sertifikat Laik Fungsi) — functional worthiness certificate
   - AMDAL/UKL-UPL/SPPL — environmental impact assessment (tiered by project size)
   - Zoning compliance (RTRW, RDTR)
2. These are one-time permits obtained DURING development.
3. Once built, ongoing compliance includes:
   - SLF renewal (every 5 years for some categories)
   - Building safety inspections
   - Environmental reporting
   - Strata title management (for condominiums)

**Proposed split:**

- NB-5 owns: The INITIAL permitting process as part of property development (Cluster D: "I want to build a villa, what permits do I need?"), zoning restrictions (what CAN be built where), and the development lifecycle from land acquisition through construction completion.
- NB-6 owns: ONGOING permit renewals, periodic compliance reporting, building safety inspections after occupancy, strata title administration.
- **Trigger sentence:** "What permits do I need to build?" = NB-5. "My SLF is expiring, what do I do?" = NB-6.

**Edge case 1: Renovation of existing property.**
A client wants to extensively renovate a villa. Does this need a new PBG? This is arguably NB-5 (it is a construction activity) but also NB-6 (it is maintenance of existing property). Resolution: NB-5 covers it because the regulatory framework (PBG requirements, UU 28/2002) is the same as for new construction. NB-6 would only cover minor maintenance that does not require permits.

**Edge case 2: Environmental compliance for a hotel.**
Building a 50-room hotel in Bali requires AMDAL. This is also NB-3 territory (the hospitality business licensing includes environmental compliance as a sub-permit). Resolution: NB-3 owns AMDAL as part of the BUSINESS licensing stack. NB-5 owns AMDAL as part of the CONSTRUCTION permitting stack. The same regulation, different context. NB-5's AMDAL coverage focuses on: what triggers AMDAL for property development projects, how it affects land use, the timeline impact on construction. NB-3's focuses on: AMDAL as a prerequisite in OSS-RBA licensing workflow.

**Edge case 3: Change of use.**
Converting a residential villa to a commercial guesthouse. This involves zoning (NB-5: is commercial use allowed here?), business licensing (NB-3: obtaining a business license for accommodation), and compliance (NB-6: ongoing operational requirements). NB-5 owns the land-use/zoning question. The business licensing question is NB-3. The ongoing compliance is NB-6.

### 1.4 NB-8 (Expat Life) vs NB-5 (Property): The Personal Residence Split

**The core question:** When an expat wants to rent or buy a home to LIVE in, is that NB-5 or NB-8?

**Reasoning chain:**

1. NB-8 is about lifestyle in Bali: neighborhoods, cost of living, healthcare, schools, culture.
2. NB-5 is about property as a legal/financial asset: land rights, transactions, investment.
3. An expat renting a villa to live in is NB-8 (lifestyle choice).
4. An expat buying a property via Hak Pakai for personal residence is NB-5 (legal transaction involving land rights, BPN registration, regulatory compliance with PP 103/2015).
5. The SAME person, the SAME property — but NB-8 covers "which neighborhood and what is life like" while NB-5 covers "what legal structure and how to secure your rights."

**Proposed split:**

- NB-8 owns: Residential rental as a LIFESTYLE topic (cost comparisons, lease negotiation tips as a consumer, neighborhood guides, tenant rights in practice).
- NB-5 owns: ALL legal structures for property acquisition (including Hak Pakai for personal residence), the LEGAL aspects of lease contracts (notarial deed, lease registration, rights on expiry), and residential property investment.
- **Trigger sentence:** "Where should I live in Bali and how much is rent?" = NB-8. "How do I legally secure a 25-year lease?" = NB-5.

**Edge case 1: Mixed-use personal property.**
An expat buys a villa to live in but also rents out 2 rooms on Airbnb. This is NB-5 (Hak Pakai acquisition, potential reclassification as commercial, tax implications of rental income — cross-ref NB-4). The lifestyle aspects of living there are NB-8. The business licensing for Airbnb rental is NB-3 (if formal) or NB-6 (if compliance question).

**Edge case 2: Land banking.**
A foreigner acquires a long-term lease on undeveloped land, intending to hold and possibly develop later. This is ENTIRELY NB-5 — it is an investment decision involving land rights, with no lifestyle (NB-8) or operational (NB-6) component until development begins. The lease contract structure, extension options, and risk of loss on expiry are core NB-5.

**Edge case 3: Property as collateral.**
A PT PMA owner wants to use their HGB-titled property as collateral for a bank loan (Hak Tanggungan). This is NB-5 — it involves land rights encumbrance, BPN registration of mortgage, and the legal framework for secured lending on Indonesian land titles. Neither NB-3 (company operations) nor NB-4 (tax) nor NB-6 (compliance) owns this; it is a property-specific legal structure.

### 1.5 Summary: The Complete NB-5 Perimeter

**INSIDE NB-5:**

- All Indonesian land right types (Hak Milik, HGB, Hak Pakai, HGU, Hak Sewa) — what they are, who can hold them, duration, renewal
- Foreign ownership structures (Hak Pakai direct, PT PMA + HGB, lease/sewa, PPJB)
- Property transaction process (due diligence, PPAT, AJB, BPN registration, title transfer)
- Development and construction permits (PBG, SLF, AMDAL/UKL-UPL, zoning)
- Property investment analysis (villa rental, aparthotel, co-living, hospitality investment)
- Property disputes and protection (nominee risk, fraud, certificate disputes, land mafia)
- Bali-specific property rules (RTRW zoning, green zones, temple exclusion zones, adat land)
- Property financing (Hak Tanggungan/mortgage, bank requirements for foreigner loans)
- Tax triggers in property lifecycle (which taxes, when — referencing NB-4 for rates)
- Lease contract structures (notarial deed, Sewa agreements, extension mechanisms)

**OUTSIDE NB-5 (with owner notebook):**

- PT PMA company formation process (NB-3)
- KBLI code selection and OSS-RBA licensing workflow (NB-3)
- Tax rates, calculation formulas, filing deadlines, treaty application (NB-4)
- NPWP registration and tax residency determination (NB-4)
- Ongoing operational compliance after construction complete (NB-6)
- SLF renewal, building safety inspections, strata management (NB-6)
- Residential lifestyle guidance, neighborhood recommendations (NB-8)
- Tenant experience, cost of living comparisons (NB-8)

---

## 2. CLUSTER ARCHITECTURE — Analysis of 7 Proposed Clusters

### Cluster A: Land Rights & Title System

**Proposed subtopics:**

- Hak Milik (freehold) — Indonesian citizens only
- Hak Guna Bangunan (HGB) — building rights for PT/PT PMA
- Hak Pakai — right of use, foreigners' primary direct right
- Hak Guna Usaha (HGU) — cultivation rights for agriculture/plantation
- Hak Sewa — contractual lease, not registered at BPN
- Hak Pengelolaan — state-managed land rights
- Girik/Petok D (unregistered customary land)
- Land registration process at BPN (PP 24/1997)
- Title conversion (Hak Milik to Hak Pakai for WNA purchase)

**Internal coherence: HIGH (9/10).**
All subtopics concern the LEGAL NATURE of land rights. This is the foundational knowledge cluster — everything else in NB-5 builds on understanding these distinctions. The only stretch is Girik/Petok D (customary unregistered land), which is at the edge but essential for Bali because significant amounts of land in rural Bali are still unregistered.

**Query overlap risk: LOW.**
This cluster is definitional/structural. It will not be confused with transactional clusters (C) or investment clusters (E) because the queries are about the nature of rights, not about process or returns.

**Potential confusion:** HGU could overlap with agriculture/plantation investment (which might feel like Cluster E). Resolution: Cluster A covers HGU as a LAND RIGHT TYPE. If a client asks about developing an agricultural business on HGU land, that involves NB-3 (business setup) + NB-5 Cluster A (the land right) + NB-5 Cluster E (the investment analysis).

**Query design templates (following NB-2 5-component anatomy):**

1. **L1 — Land Rights Update (Bahasa):**

   > Perkembangan terbaru hak atas tanah di Indonesia 2025-2026: perubahan Hak Guna Bangunan, Hak Pakai, dan Hak Guna Usaha berdasarkan PP 18/2021 dan peraturan pelaksana terkini ATR/BPN. Fokus peraturan resmi Kementerian ATR/BPN, bukan blog properti.

2. **L1 — Foreigner Land Rights (English):**

   > Current regulations on foreigner land rights (Hak Pakai) in Indonesia 2025-2026, including PP 103/2015 amendments, property value minimums by zone, one-property limit for WNA, and conversion procedures from Hak Milik. Based on ATR/BPN regulations and official JDIH sources, excluding real estate agent marketing.

3. **L2 — Title System Comparison (English):**
   > Comparative analysis of Indonesian land title types 2025-2026: Hak Milik vs HGB vs Hak Pakai vs lease — security of tenure, renewal risk, bankability, foreigner eligibility, and practical enforcement in Bali. Legal analysis sources only.

**Complexity rating: MEDIUM-HIGH.**
Sources needed: 8-12. T0 sources are relatively stable (UUPA 1960, PP 18/2021, PP 103/2015). The regulatory framework changes less frequently than immigration or tax, but implementing regulations (Permen ATR/BPN) update periodically.

### Cluster B: Foreign Ownership Structures

**Proposed subtopics:**

- Hak Pakai direct acquisition by foreigner (WNA)
- PT PMA + HGB structure (the standard investment vehicle)
- Lease (Sewa) — long-term contractual arrangement
- PPJB (preliminary binding sale agreement) — pre-title mechanism
- Nominee arrangement — coverage of legal risks
- PP 103/2015 restrictions (1 property limit, minimum value, residential only)
- Comparison of structures: security, cost, duration, renewal risk
- KITAS/KITAP relationship to property rights eligibility

**Internal coherence: HIGH (9/10).**
This is the MOST CLIENT-RELEVANT cluster for Bali Zero. Every foreigner asking about property will need to understand these structures. All subtopics answer the same fundamental question: "How can a foreigner control property in Indonesia?" The KITAS/KITAP eligibility subtopic is a cross-domain element (NB-2 → NB-5) but belongs here because it directly gates property rights.

**Query overlap risk: MEDIUM.**
This cluster overlaps with Cluster A (land rights are the building blocks of ownership structures) and Cluster C (the transaction process is HOW you implement one of these structures). The distinction is: Cluster A = what the rights ARE. Cluster B = which rights a FOREIGNER can use. Cluster C = HOW to execute the transaction.

**Potential confusion:** "PT PMA + HGB" could overlap with Cluster A (HGB as a right type). Resolution: Cluster A explains HGB in the abstract. Cluster B explains "why a foreigner would use HGB via PT PMA specifically."

**Nominee arrangement handling:**
This is the most sensitive subtopic. NB-5 MUST cover:

- What a nominee arrangement is (factual definition)
- That it is explicitly illegal under UUPA 1960 Art. 26 and PP 18/2021
- The specific legal risks: void transaction, no legal recourse, criminal liability
- Real case examples of disputes (from press, T5 sources)
- The ALTERNATIVE legal structures (Hak Pakai, PT PMA + HGB, lease)

NB-5 must NOT cover:

- How to set up a nominee arrangement
- Template agreements for nominee structures
- "How to make it safer" — there is no safe nominee arrangement

**Query design templates:**

1. **L1 — Foreign Ownership Update (Bahasa):**

   > Peraturan terkini kepemilikan properti oleh orang asing (WNA) di Indonesia 2025-2026: Hak Pakai berdasarkan PP 103/2015, batasan nilai minimum properti, perubahan prosedur di BPN. Sumber resmi ATR/BPN dan JDIH, bukan agen properti.

2. **L1 — Nominee Risk (English):**

   > Legal risks and court decisions regarding nominee property arrangements (pinjam nama) in Indonesia 2025-2026: enforcement actions, void transactions, dispute outcomes, and BPN crackdown on irregular ownership structures. Legal analysis and court decisions, not real estate forums.

3. **L2 — Structure Comparison (English):**

   > Comparative analysis of property ownership structures for foreigners in Bali 2025-2026: Hak Pakai direct vs PT PMA + HGB vs long-term lease (Sewa) — legal security, total cost over 30 years, renewal certainty, bankability, and exit options. Law firm analyses and official sources.

4. **L4 — Immigration x Property (English):**
   > Connection between immigration status and property rights eligibility in Indonesia 2025-2026: KITAS vs KITAP holder rights, Hak Pakai eligibility requirements, and impact of new immigration law (UU 1/2026) on foreigner property ownership. Cross-referencing immigration and agrarian regulations.

**Complexity rating: HIGH.**
Sources needed: 10-15. This is the highest-demand cluster with the most nuance. Requires T0 (UUPA, PP 103/2015, PP 18/2021), T1 (ATR/BPN circulars, BPN procedures), T2 (BPN Bali local practices), and T5 (law firm analyses, court decision summaries). Nominee arrangement coverage requires careful sourcing from legal analyses, not forums.

### Cluster C: Transaction Process

**Proposed subtopics:**

- Due diligence checklist (title search, encumbrance check, zoning verification)
- PPAT (Pejabat Pembuat Akta Tanah) — the official land deed officer
- AJB (Akta Jual Beli) — official sale deed
- PPJB (Perjanjian Pengikatan Jual Beli) — preliminary agreement
- BPN registration process (title transfer, name change)
- Tax payments in transaction (BPHTB, PPh — cross-ref NB-4)
- Document requirements for each step
- Timeline and cost estimates for standard transactions
- Powers of attorney in property transactions

**Internal coherence: HIGH (8/10).**
All subtopics are about the PROCESS of buying/selling property. The slight coherence reduction is because "due diligence" is pre-transaction and "BPN registration" is post-transaction, but they are all part of the same lifecycle. The tax payment subtopic is a cross-reference to NB-4 but is essential to include because BPHTB must be paid BEFORE BPN registration — it is a process dependency, not just a tax question.

**Query overlap risk: MEDIUM-LOW.**
Transaction process is procedural/sequential. The risk is overlap with Cluster B (ownership structures) because the PROCESS differs by structure (Hak Pakai vs HGB vs lease). Resolution: Cluster B covers WHICH structure to choose. Cluster C covers HOW the transaction works once you have chosen.

**PPJB vs AJB — critical distinction flagged in prompt:**
This MUST be covered with high specificity. Many disputes arise from PPJB without AJB follow-through. The claim pattern would be:

- PPJB is NOT a title transfer — it is a binding agreement to transfer
- AJB by PPAT is the ONLY document that transfers title at BPN
- Clients holding PPJB only have contractual rights, not property rights
- Developer insolvency after PPJB but before AJB = high risk for buyer

**Query design templates:**

1. **L1 — Transaction Process (Bahasa):**

   > Prosedur terbaru jual beli tanah dan bangunan di Indonesia 2025-2026: proses PPAT, pembuatan AJB, pendaftaran di BPN, persyaratan dokumen. Berdasarkan peraturan ATR/BPN dan PP 24/1997 tentang Pendaftaran Tanah, bukan blog notaris.

2. **L1 — Due Diligence (English):**

   > Property due diligence requirements for land purchases in Bali 2025-2026: title search at BPN, encumbrance check, zoning verification against RTRW/RDTR, and common red flags in land certificates. Based on notarial practice guides and ATR/BPN procedures.

3. **L3 — Digitalization (Bahasa):**
   > Digitalisasi layanan pertanahan BPN 2025-2026: sistem pendaftaran tanah elektronik, sertifikat tanah digital, integrasi dengan OSS-RBA, dan timeline implementasi. Sumber resmi Kementerian ATR/BPN dan berita resmi pemerintah.

**Complexity rating: MEDIUM.**
Sources needed: 6-10. The transaction process is procedural and relatively stable. Key T0 sources (PP 24/1997, UUPA) rarely change. The main volatility is in BPN digitalization efforts and local BPN office practices (T2-T4).

### Cluster D: Development & Construction

**Proposed subtopics:**

- PBG (Persetujuan Bangunan Gedung) — replaced IMB
- SLF (Sertifikat Laik Fungsi) — functional worthiness
- AMDAL/UKL-UPL/SPPL — environmental impact (tiered)
- Zoning compliance (RTRW/RDTR — national framework)
- UU 28/2002 (Bangunan Gedung — building law)
- Construction permits for foreigners (are there additional requirements?)
- Contractor and architect registration requirements

**Internal coherence: MEDIUM-HIGH (7/10).**
The permitting subtopics cohere well. The construction-specific topics (contractor registration) are slightly tangential but necessary for a complete picture. The environmental impact assessment (AMDAL) is the area of strongest overlap with NB-3 (business licensing) and NB-6 (operational compliance).

**Query overlap risk: HIGH.**
This is the highest-overlap cluster. Reasons:

1. NB-3 Cluster C (Licensing) includes environmental permits (AMDAL, UKL-UPL, SPPL) and building permits (PBG, SLF) as sub-categories of business licensing.
2. NB-6 covers ongoing compliance including SLF renewal.
3. The SAME regulation (UU 28/2002, GR 28/2025) appears in multiple notebooks.

**Resolution strategy:**

- NB-5 Cluster D focuses on permits AS PART OF PROPERTY DEVELOPMENT: "I have land, I want to build, what permits do I need?"
- NB-3 focuses on permits AS PART OF BUSINESS LICENSING: "I am starting a hotel business, what licenses do I need?"
- NB-6 focuses on permits AS ONGOING OBLIGATIONS: "My permits are expiring, what do I renew?"
- The regulatory TEXT (UU 28/2002, GR 28/2025) is T0 for all three, but the QUERIES and CLAIMS focus on different aspects.

**Query design templates:**

1. **L1 — Building Permits (Bahasa):**

   > Peraturan terbaru Persetujuan Bangunan Gedung (PBG) dan Sertifikat Laik Fungsi (SLF) di Bali 2025-2026: persyaratan, prosedur pengajuan melalui SIMBG, klasifikasi bangunan, dan perbedaan dengan IMB lama. Sumber resmi Dinas PUPR dan peraturan daerah Bali.

2. **L1 — Zoning Bali (English):**

   > Bali zoning regulations 2025-2026: RTRW provincial spatial plan, green zone restrictions, tourist zone designation, temple exclusion zones (pura radius), and recent updates to Perda Bali on spatial planning. Official Bappeda Bali and Perda sources, not developer marketing.

3. **L2 — Environmental Permits (Bahasa):**
   > Persyaratan AMDAL, UKL-UPL, dan SPPL untuk proyek pembangunan properti di Bali 2025-2026: ambang batas skala proyek, prosedur di DPMPTSP Bali, integrasi dengan OSS-RBA, dan dampak Pergub Bali terkait lingkungan. Sumber resmi pemerintah daerah Bali.

**Complexity rating: HIGH.**
Sources needed: 10-14. This cluster has the most LOCAL regulation content. National framework (UU 28/2002, GR 28/2025) is T0, but Bali-specific zoning (Perda RTRW, Pergub) is T2 and changes more frequently. Local BPN/PUPR practices add T2-T4 volatility.

### Cluster E: Property Investment

**Proposed subtopics:**

- Villa rental market in Bali (ROI analysis framework)
- Aparthotel/serviced apartment investment
- Co-living space development (growth segment)
- Hospitality investment (hotel, beach club)
- Land banking (buy and hold undeveloped land)
- Property valuation methods (NJOP, market comps, income approach)
- Financing options for foreign investors
- Exit strategy analysis (resale, lease assignment, company sale)

**Internal coherence: MEDIUM (7/10).**
The investment angle holds these together, but the subtopics span very different regulatory contexts. Villa rental has different requirements from hotel development. Land banking is passive while co-living is active. What unites them is the INVESTOR PERSPECTIVE: risk, return, and regulatory framework for foreign capital in Bali property.

**Query overlap risk: MEDIUM.**
Investment analysis could overlap with NB-3 (business licensing for hospitality) and NB-4 (tax treatment of investment income). NB-5 covers the PROPERTY INVESTMENT analysis; NB-3 covers the BUSINESS STRUCTURE; NB-4 covers the TAX TREATMENT.

**Important scope decision: Land price data.**
Should NB-5 track current land prices per sqm in Bali? My reasoning:

AGAINST including land prices:

- Prices change frequently and vary by location
- NLM is not well-suited for real-time price data
- Creates false precision if sources are stale
- Clients should get prices from agents/surveyors, not from an intelligence notebook

FOR including land prices:

- Clients constantly ask "how much does land cost in Canggu?"
- Order-of-magnitude guidance prevents getting scammed
- Government-assessed values (NJOP) are publicly available

RESOLUTION: NB-5 should include NJOP data (government-assessed values) as T2 reference data but should NOT attempt to track market prices. The MD-4 (Open Questions) should flag that market prices require real-time agent consultation. NJOP serves as a FLOOR reference that helps detect fraud (if asking price is 10x NJOP, that is a signal).

**Query design templates:**

1. **L1 — Villa Rental Market (English):**

   > Bali villa rental market regulatory framework 2025-2026: licensing requirements for short-term rental (Pondok Wisata, hotel classification), foreign investor eligibility, and recent enforcement against unlicensed villa operators. Government regulations and licensed operator data, not rental agency listings.

2. **L2 — Investment Comparison (English):**

   > Comparative analysis of property investment structures in Bali 2025-2026: villa rental vs aparthotel vs co-living vs land banking — legal structure options, licensing requirements, typical ROI ranges, and regulatory risk assessment. Law firm and investment advisory publications.

3. **L4 — Property x Company x Tax (English):**
   > Cross-domain analysis of foreign property investment in Bali 2025-2026: PT PMA requirements (NB-3 interface), tax optimization for rental income (NB-4 interface), and property rights security (NB-5 core). Integration of agrarian law, corporate law, and tax law perspectives.

**Complexity rating: MEDIUM-HIGH.**
Sources needed: 8-12. Mix of T0 (regulations on foreign investment in property), T2 (Bali-specific tourism/property regulations), T5 (market analyses, industry reports). This cluster ages fastest because market conditions change.

### Cluster F: Disputes & Protection

**Proposed subtopics:**

- Nominee arrangement disputes (court outcomes, enforcement)
- Certificate disputes (overlapping claims, forgery)
- Land mafia tactics and prevention
- PPJB disputes (developer insolvency, non-completion)
- Lease disputes (early termination, non-renewal)
- Adat/customary land conflicts
- Insurance and title protection options
- Dispute resolution mechanisms (court vs arbitration vs mediation)

**Internal coherence: HIGH (8/10).**
All subtopics concern what goes WRONG with property and how to prevent or resolve it. This is the "defensive" cluster — essential for risk management. The slight coherence issue is that dispute resolution mechanisms are procedural (courts, arbitration) rather than property-specific, but they are so commonly needed in property disputes that they belong here.

**Query overlap risk: LOW.**
Disputes are distinctly different from the structural/transactional clusters (A-C) and the investment cluster (E). The main overlap is with Cluster B (nominee arrangements) because nominee disputes are both a risk factor (Cluster B covers it as "why not to use nominees") and a dispute category (Cluster F covers what happens when it goes wrong).

**Resolution:** Cluster B covers nominee arrangements as a structural option with risk warnings. Cluster F covers actual dispute outcomes, court decisions, and enforcement patterns. Minimal overlap if queries are well-designed.

**Adat (customary) land — critical for Bali:**
Balinese customary law (awig-awig) affects land in ways that have no written source:

- Desa adat (traditional village) land cannot be sold outside the community
- Temple land (tanah pelaba pura) has specific restrictions
- Some land has customary use restrictions not reflected in BPN certificates
- Disputes between registered title and customary claims are common in Bali

This is one of the hardest areas to source because awig-awig is oral tradition, varies by desa adat, and is not published in any government gazette. NB-5 must:

1. Acknowledge that awig-awig exists and affects property rights
2. Explain the types of customary restrictions (general framework)
3. State clearly that specific awig-awig must be verified locally at each desa adat
4. Reference any court decisions that clarify the interaction between registered title and customary law

Sources will be primarily T5 (academic papers, legal analyses) and T2 (Pemprov Bali regulations on desa adat).

**Query design templates:**

1. **L1 — Property Disputes (Bahasa):**

   > Sengketa properti dan tanah di Bali 2025-2026: kasus tanah nominee yang dibatalkan, sertifikat ganda, perselisihan adat, dan tren putusan pengadilan. Berdasarkan putusan MA, analisis hukum agraria, dan laporan media terverifikasi. Bukan forum diskusi.

2. **L1 — Nominee Enforcement (English):**

   > Indonesian court decisions and BPN enforcement actions against nominee property arrangements 2024-2026: void transactions, criminal prosecution of nominees, and land forfeiture outcomes. Legal databases, court decision summaries, and authoritative news sources.

3. **L3 — Fraud Trends (English):**
   > Emerging property fraud and land mafia patterns in Bali 2025-2026: certificate forgery, double-selling, false power of attorney, and BPN corruption investigations. Enforcement reporting from local news and government anti-corruption sources.

**Complexity rating: MEDIUM.**
Sources needed: 6-10. Court decisions are harder to source (T1 for Supreme Court decisions via Putusan MA database, T5 for reporting). Adat sources are the most challenging — likely T2/T5 at best. The fraud/enforcement monitoring needs T4-T5 local news sources.

### Cluster G: Bali-Specific Regulations

**Proposed subtopics:**

- RTRW Bali (Provincial Spatial Plan — Perda 16/2009 as amended)
- RDTR (Detailed Spatial Plan) for each kabupaten/kota
- Green zone restrictions (rice paddies, forest, water catchment)
- Temple exclusion zones (pura radius restrictions)
- Tourist zone designation and restrictions
- Coastal setback regulations
- Height restrictions (traditional 15m limit, varies by area)
- Recent Pergub/Perda affecting property development
- Bali tourism levy impact on property investment

**Internal coherence: HIGH (9/10).**
All subtopics are Bali-specific regulations that affect property. This is the LOCAL dimension that distinguishes NB-5 from a generic Indonesian property notebook. Every subtopic answers the question: "What additional rules apply because this property is in Bali?"

**Query overlap risk: LOW.**
This is the most distinctive cluster — no other NB focuses on Bali-specific spatial planning and cultural restrictions. The only overlap is with Cluster D (development permits must comply with zoning), but Cluster D covers the permitting PROCESS while Cluster G covers the REGULATORY LANDSCAPE that the permits must comply with.

**Critical insight: This cluster has the HIGHEST local-to-national source ratio.**
Estimated: 70% T2 (local regulations), 20% T0/T1 (national framework), 10% T5 (analysis). This is the inverse of Cluster A (90% national, 10% local). The pipeline must be configured to weight local sources higher for this cluster.

**Query design templates:**

1. **L1 — Bali Zoning (Bahasa):**

   > Peraturan tata ruang wilayah (RTRW) Provinsi Bali dan RDTR kabupaten/kota 2025-2026: pembaruan zonasi kawasan wisata, kawasan hijau, kawasan suci pura, dan pembatasan ketinggian bangunan. Sumber resmi Bappeda Bali, Perda Bali, dan Dinas PUPR Bali.

2. **L1 — Bali Green Zone (English):**

   > Bali green zone and environmental protection regulations affecting property development 2025-2026: rice paddy conservation (subak), forest zones, water catchment areas, coastal setback rules, and recent enforcement actions. Official Bali provincial government sources.

3. **L2 — Bali vs Other Destinations (English):**

   > Comparative analysis of property development regulations in Bali vs Lombok vs Labuan Bajo 2025-2026: zoning restrictions, foreign investment rules, environmental requirements, and government incentives for development. Official provincial regulations and investment authority publications.

4. **L4 — Bali Tourism x Property (Bahasa):**
   > Dampak regulasi pariwisata Bali terhadap investasi properti 2025-2026: retribusi wisatawan, moratorium hotel di kawasan tertentu, peraturan villa wisata (Pondok Wisata), dan kebijakan Pemprov Bali tentang pembangunan berkelanjutan. Sumber resmi Dinas Pariwisata Bali dan Pemprov Bali.

**Complexity rating: HIGH.**
Sources needed: 10-14. This is the most source-intensive cluster because Bali regulations are fragmented across provincial (Perda, Pergub), kabupaten (Perbup), and desa adat levels. Finding authoritative digital sources for local regulations is harder than for national ones. Instagram/social media of local government offices (T4) will be important here.

---

## 3. FOREIGNER OWNERSHIP DECISION TREE

This decision tree is designed to become a structural element of NB-5, either as a Master Document or as a query reference structure.

```
FOREIGN NATIONAL WANTS TO ACQUIRE PROPERTY IN BALI
│
├── Q1: What is the PURPOSE?
│   │
│   ├── PERSONAL RESIDENCE (to live in)
│   │   │
│   │   ├── Q2: Do you have valid KITAS/KITAP?
│   │   │   │
│   │   │   ├── YES → HAK PAKAI (Direct)
│   │   │   │   ├── Basis: PP 103/2015, Permen ATR/BPN 18/2021
│   │   │   │   ├── Limit: 1 residential property per WNA
│   │   │   │   ├── Minimum value: varies by zone (PP 103/2015 Lampiran)
│   │   │   │   │   ├── Jakarta: Rp 5 billion
│   │   │   │   │   ├── Bali: Rp 2 billion (verify current — may have been updated)
│   │   │   │   │   └── Other: Rp 1 billion
│   │   │   │   ├── Duration: 30 + 20 + 20 = 70 years
│   │   │   │   ├── Process: Hak Milik → Hak Pakai conversion at BPN
│   │   │   │   └── Exit: NB-5 Cluster C (transaction process)
│   │   │   │
│   │   │   └── NO (tourist or short-stay) → CANNOT acquire Hak Pakai
│   │   │       └── Alternative: LEASE (Sewa) — see below
│   │   │
│   │   └── Q3: Budget below minimum Hak Pakai threshold?
│   │       └── YES → LEASE (Sewa) for residence
│   │           ├── No minimum value threshold
│   │           ├── Duration: negotiable (5-30 years typical)
│   │           ├── No BPN registration (contractual only)
│   │           └── Lower legal protection than Hak Pakai
│   │
│   ├── INVESTMENT / RENTAL INCOME
│   │   │
│   │   ├── Q4: Scale of investment?
│   │   │   │
│   │   │   ├── SINGLE VILLA / SMALL PROPERTY
│   │   │   │   │
│   │   │   │   ├── Option A: PT PMA + HGB
│   │   │   │   │   ├── Requires: PT PMA with real estate KBLI (68xx)
│   │   │   │   │   ├── Minimum PMA capital: Rp 10 billion (verify current)
│   │   │   │   │   ├── HGB duration: 30 + 20 + 20 = 70 years
│   │   │   │   │   ├── Can be used for commercial (rental) purposes
│   │   │   │   │   ├── Interface: NB-3 for PT PMA setup
│   │   │   │   │   └── Tax: NB-4 for rental income taxation
│   │   │   │   │
│   │   │   │   └── Option B: Long-term LEASE (Sewa)
│   │   │   │       ├── Lower cost (no PMA formation needed)
│   │   │   │       ├── Duration: 25-30 years typical
│   │   │   │       ├── Business license still needed for rental: NB-3
│   │   │   │       └── Less secure than HGB (contractual, not registered)
│   │   │   │
│   │   │   ├── MULTIPLE PROPERTIES / DEVELOPMENT
│   │   │   │   ├── PT PMA + HGB is the ONLY viable path
│   │   │   │   ├── KBLI must cover real estate + development activities
│   │   │   │   ├── Environmental permits (AMDAL) likely required: NB-5 Cluster D
│   │   │   │   ├── PBG required for construction: NB-5 Cluster D
│   │   │   │   └── Zoning compliance: NB-5 Cluster G
│   │   │   │
│   │   │   └── HOSPITALITY (hotel, beach club)
│   │   │       ├── PT PMA + HGB + tourism business license
│   │   │       ├── KBLI: hospitality codes (55xxx)
│   │   │       ├── Additional Bali tourism regulations
│   │   │       ├── Interface: NB-3 for business licensing, NB-6 for ongoing compliance
│   │   │       └── Moratorium check: some areas restrict new hotel permits
│   │
│   ├── JUST LEASE (no ownership desired)
│   │   │
│   │   └── SEWA CONTRACT
│   │       ├── Available to any foreigner regardless of visa status
│   │       ├── Notarial deed recommended (not required but enforceable)
│   │       ├── Register at kelurahan for additional protection
│   │       ├── Duration: negotiable, 5-30 years common in Bali
│   │       ├── Pre-payment (lump sum) is standard in Bali
│   │       ├── Extension: by agreement only — no guaranteed renewal
│   │       ├── Building on leased land: possible but ownership of building
│   │       │   transfers to landowner at lease end (unless negotiated)
│   │       └── Tax: PPh 10% on rental paid by lessor: NB-4
│   │
│   └── LAND BANKING (hold undeveloped land)
│       │
│       ├── Can foreigner hold undeveloped land?
│       │   ├── Hak Pakai: technically YES but must be for "use"
│       │   │   └── Idle Hak Pakai may be revoked (agrarian law principle)
│       │   ├── PT PMA + HGB: YES, but HGB requires intent to build
│       │   │   └── Extended idle period may trigger HGB revocation
│       │   └── Lease: YES, no activity requirement
│       │       └── Safest for pure land banking
│       │
│       └── Risks:
│           ├── Zoning changes during holding period
│           ├── Adat claims emerging over time
│           ├── Government land reclamation
│           └── Currency risk (IDR fluctuation)
│
├── Q5: NOMINEE ARRANGEMENT considered?
│   │
│   └── WARNING: ILLEGAL under UU 5/1960 Art. 26 + PP 18/2021
│       ├── Transaction may be declared VOID
│       ├── Foreigner has NO legal recourse if nominee refuses to transfer
│       ├── Criminal liability possible
│       ├── BPN may refuse registration
│       ├── Court decisions consistently rule against nominees
│       └── ALTERNATIVE: Use legal structures above (Hak Pakai, PT PMA, Lease)
│
└── Q6: EXISTING PROPERTY — what to do with it?
    │
    ├── Extend lease → Negotiate with landowner before expiry
    ├── Renew HGB → Apply at BPN (process well before expiry)
    ├── Renew Hak Pakai → Apply at BPN
    ├── Sell property → NB-5 Cluster C (transaction process)
    ├── Use as collateral → Hak Tanggungan (mortgage) registration
    ├── Dispute → NB-5 Cluster F
    └── Change structure → e.g., personal Hak Pakai → PT PMA HGB
```

**Design notes on this decision tree:**

1. Every terminal node either resolves within NB-5 or explicitly links to another NB.
2. The nominee branch is always a WARNING, never an option.
3. Immigration status (KITAS/KITAP) is a gate at Q2, linking to NB-2.
4. Tax implications at every acquisition path link to NB-4.
5. Business licensing at every commercial path links to NB-3.
6. This tree should be encoded as a Master Document (MD-5: Decision Guide) in NB-5.

---

## 4. FAILURE MODE ANALYSIS

### 4.1 Property Law Changes at LOCAL Level

**The problem:** Property law in Indonesia is multi-layered. National regulations (UU, PP, Permen) change on a semi-predictable schedule. But LOCAL regulations (Perda, Pergub, Perbup, Surat Edaran Bupati) can change with little notice and are poorly digitized.

**Example:** Badung Regency (where Canggu, Seminyak, Kerobokan are located) could issue a moratorium on new villa construction permits with only a Surat Edaran from the Bupati. This would not appear in national sources. It might first appear on the Bupati's Instagram or a local newspaper.

**Mitigation strategy:**

1. NB-5 Cluster G must have dedicated T4 monitoring of Bali local government social media.
2. T2 sources (Perda, Pergub, Perbup) must be checked weekly, not just when detected by Deep Research.
3. The T4 social monitor (from NB-2 architecture) should be extended to include:
   - @bpn_bali (Instagram)
   - @pemkabbadung (Instagram)
   - @denpasarkota (Instagram)
   - @bappedabali (if exists)
   - @dinaspuprbali (if exists)
4. MD-4 (Open Questions) should always flag which local regulations were last verified and when.

**Failure mode:** NB-5 states "no moratorium on villa construction in Canggu" based on stale data. A client proceeds with development and is blocked by a new local regulation.

**Prevention:** Every ZONING or PERMIT claim must carry a `last_verified_date` and an explicit disclaimer: "Local regulations may change without notice. Verify with local BPN/PUPR before committing to development."

### 4.2 Awig-Awig (Customary Law) Sourcing

**The problem:** Awig-awig is the customary law system of Balinese traditional villages (desa adat). It is:

- Unwritten (or written only in Balinese script in the banjar hall)
- Different for each of Bali's ~1,493 desa adat
- Enforced by the traditional village council, not the state courts
- Not published in any government gazette or digital repository

**What awig-awig can affect:**

- Prohibition on selling land to outsiders (even other Indonesians from different desa)
- Restrictions on building height, style, or orientation near temples
- Requirements for community participation (gotong royong) by landowners
- Restrictions on land use (e.g., no commercial activity near sacred sites)
- Rights of the desa adat to reclaim land if community obligations are not met

**Mitigation strategy:**

1. NB-5 CANNOT be authoritative on specific awig-awig rules. It should:
   - Explain what awig-awig is and why it matters (general framework)
   - List the TYPES of restrictions that commonly exist
   - State clearly: "Specific awig-awig must be verified with the local desa adat/banjar"
   - Include academic sources (T5) that survey common awig-awig patterns
2. For sourcing, the best available materials are:
   - Academic papers on Balinese customary land law (Universitas Udayana publications)
   - Pemprov Bali regulations on desa adat (Perda Bali 4/2019 on Desa Adat)
   - Court decisions where awig-awig was considered (Mahkamah Agung database)
3. NB-5's MD-4 should flag awig-awig as a PERMANENT open question with note: "unresolvable through standard NLM sourcing — requires field verification."

**Failure mode:** NB-5 omits awig-awig entirely. Client buys property without checking, faces restrictions from desa adat that override their legal title.

**Prevention:** Every property acquisition query response should include a standard awig-awig disclaimer, similar to how NB-2 includes enforcement divergence disclaimers.

### 4.3 Nominee Arrangement Coverage

**The problem:** NB-5 must cover nominee arrangements because clients ask about them constantly. But coverage must be informational (risks, consequences) not instructional (how to do it).

**The line:**

- OK: "Nominee arrangements are illegal under UUPA Art. 26. Courts have consistently ruled such transactions void. In Case X, the foreigner lost their entire investment."
- NOT OK: "A typical nominee agreement includes powers of attorney, irrevocable loan agreements, and blank transfer documents."
- EDGE CASE: "Common elements of nominee structures that courts have identified and invalidated include..." — This is OK because it helps clients recognize if they have been put into a nominee arrangement by a unscrupulous agent.

**Mitigation strategy:**

1. NB-5 should frame nominee coverage as RISK EDUCATION:
   - What it is (definition)
   - Why it is illegal (legal basis)
   - What happens when it fails (court outcomes, loss of investment)
   - How to detect if you are being offered one (warning signs)
   - What to do instead (legal alternatives)
2. Claims about nominees should always be LEGAL_CHANGE or ENFORCEMENT_ACTION category, never PROCEDURAL_UPDATE.
3. Sources should be T0 (UUPA), T1 (court decisions), and T5 (legal analyses), never T6 (forum advice).

**Failure mode:** NB-5's nominee coverage is interpreted as instruction. A client uses it to set up a nominee arrangement and claims Bali Zero advised them.

**Prevention:** Every nominee-related response must include explicit WARNING prefix. MD-1 (Change Log) tracks all nominee-related content for compliance review.

### 4.4 Land Price Data — Scope Decision

**Reasoning:**

Arguments for including market price data:

- Highest-volume client question: "How much does land cost in [area]?"
- Helps detect fraud (if asking price is far above market)
- Government data (NJOP, BPHTB assessment) is publicly available

Arguments against including market price data:

- Market prices change weekly/monthly in hot Bali market
- NLM is updated at most 2x/day — always stale
- Creating false precision is worse than no data
- Price data from blogs/forums is T6 (unreliable)
- NJOP is significantly below market (sometimes 10-30% of market value)

**Decision:** NB-5 should include:

- NJOP explanation and how to look it up (process, not prices)
- The relationship between NJOP and market prices (NJOP is typically 10-50% of market)
- Government fee calculations based on NJOP (BPHTB = 5% of NJOP minus NJOPTKP)
- General price RANGE by area class (premium, standard, emerging) — updated quarterly at most
- A clear disclaimer: "For current market prices, consult licensed property agents"

NB-5 should NOT include:

- Specific per-sqm prices for named locations
- Price trend predictions
- Comparison tables of agent-listed prices

**Failure mode:** Client relies on NB-5 price data that is 3 months stale and overpays or underbids.

**Prevention:** All price-related claims are WORKING category with 30-day half-life. No price claim reaches VERIFIED status. MD-4 flags price data as inherently provisional.

### 4.5 Bali-Specific vs National-Level Ratio

**Reasoning:**

NB-2 (Immigration) is approximately 80% national / 20% local because immigration law is predominantly national (UU, PP, Permenkumham) with local enforcement variation.

NB-5 (Property) should be approximately 50% national / 50% local because:

1. The foundational law (UUPA, PP 18/2021, PP 103/2015) is national — about 8-10 T0 sources
2. The implementing regulations split: national Permen ATR/BPN + Bali Perda/Pergub
3. The operational reality is overwhelmingly local: BPN offices, PPAT jurisdiction, zoning maps, building permits, awig-awig
4. Bali Zero's clients are specifically in Bali, not spread across Indonesia

**Proposed ratio by cluster:**

| Cluster              | National | Local (Bali) | Reasoning                                           |
| -------------------- | -------- | ------------ | --------------------------------------------------- |
| A: Land Rights       | 80%      | 20%          | Rights are defined nationally                       |
| B: Foreign Ownership | 70%      | 30%          | PP 103/2015 is national but Bali minimums are local |
| C: Transaction       | 50%      | 50%          | Process is national but BPN practice is local       |
| D: Development       | 30%      | 70%          | Permits and zoning are overwhelmingly local         |
| E: Investment        | 40%      | 60%          | Market context is Bali-specific                     |
| F: Disputes          | 50%      | 50%          | Court law is national but cases are local           |
| G: Bali-Specific     | 5%       | 95%          | By definition                                       |
| **Overall**          | **~46%** | **~54%**     |                                                     |

This ratio directly impacts T2 source allocation — NB-5 needs proportionally more T2 sources than NB-2.

---

## 5. CROSS-DOMAIN INTERFACE CONTRACTS

### 5.1 NB-3 (Company Setup) <-> NB-5 (Property)

**Contract:**

```
RULE NB3-NB5-001: PT PMA Formation Boundary
  NB-3 OWNS: Company formation process (akta, KBLI, OSS-RBA, SK Kemenkumham)
  NB-5 OWNS: Property acquisition by existing legal entity (PT PMA acquires HGB/Hak Pakai)
  TRIGGER: "PT PMA acquires land rights" or "PT PMA holds HGB" → NB-5
  TRIGGER: "Setting up PT PMA for property" or "KBLI for real estate" → NB-3

RULE NB3-NB5-002: Environmental Permits
  NB-3 OWNS: AMDAL/UKL-UPL as part of business licensing stack in OSS-RBA
  NB-5 OWNS: AMDAL/UKL-UPL as requirement for construction on acquired land
  SHARED REGULATION: PP 22/2021, Permen LHK
  RESOLUTION: Both reference the same T0 source. NB-3 frames it as "license requirement."
             NB-5 frames it as "construction prerequisite."

RULE NB3-NB5-003: Building Permits (PBG)
  NB-3 OWNS: PBG as listed in Cluster C.4 (part of operational licensing)
  NB-5 OWNS: PBG as prerequisite for property development (Cluster D)
  RESOLUTION: NB-3 covers "you need a PBG as part of your business licenses."
             NB-5 covers "how to obtain PBG, what it requires, Bali-specific rules."

RULE NB3-NB5-004: KBLI Real Estate Codes
  NB-3 OWNS: The KBLI classification system, which codes to select
  NB-5 REFERENCES: "For PT PMA holding property, KBLI 68xxx is typically used — see NB-3 for selection guidance"
```

**Implementation:** NB-5 MD-3 (Cross-Domain) includes a "PT PMA Interface" section that states these rules and links to NB-3 clusters. NB-3 MD-3 includes a reciprocal "Property Acquisition Interface" section.

### 5.2 NB-4 (Tax & Fiscal) <-> NB-5 (Property)

**Contract:**

```
RULE NB4-NB5-001: Property Tax Rates
  NB-4 OWNS: All tax rates, calculation formulas, filing procedures, DGT regulations
  NB-5 OWNS: Which taxes trigger at which point in the property lifecycle
  NB-5 REFERENCES NB-4 for: current rates (BPHTB 5%, PPh 2.5%, PBB formula, PPN 11%)
  NEVER: NB-5 hardcodes tax rates. Always reference NB-4.

RULE NB4-NB5-002: NJOP as Tax Base vs Valuation
  NB-4 OWNS: NJOP as the basis for PBB and BPHTB calculation
  NB-5 USES: NJOP as a reference point in due diligence and valuation context
  SHARED DATA: NJOP values per area (published by kelurahan/BPN)
  RESOLUTION: Both may reference NJOP data. NB-4 for tax calculation. NB-5 for market context.

RULE NB4-NB5-003: Rental Income Tax
  NB-4 OWNS: PPh Pasal 4(2) rate (10%), PPh 26 withholding (20%), treaty relief
  NB-5 OWNS: The fact that villa rental income triggers these taxes (Cluster E context)
  NB-5 REFERENCES NB-4: "Rental income is subject to final income tax — see NB-4 for current rates and filing"

RULE NB4-NB5-004: Capital Gains on Property Disposal
  NB-4 OWNS: PPh final 2.5% on property disposal, exemptions, filing
  NB-5 OWNS: The circumstance of disposal (sale, lease expiry, structure conversion) and process (PPAT withholding)
  HANDOFF: NB-5 explains WHEN the tax triggers. NB-4 explains HOW MUCH and HOW TO FILE.

RULE NB4-NB5-005: Government Fees vs Bali Zero Service Prices
  NB-5 MAY include: Government fees (BPN registration fees, PPAT fees, BPHTB rates) as T0/T2 reference data
  NB-5 NEVER includes: Bali Zero service prices for property consulting (PricingTool only)
```

### 5.3 NB-6 (Operations & Compliance) <-> NB-5 (Property)

**Contract:**

```
RULE NB5-NB6-001: Construction vs Operations Boundary
  NB-5 OWNS: Initial construction permitting and development process
  NB-6 OWNS: Post-construction operational compliance
  TRIGGER: "Building is complete, now what?" → NB-6
  TRIGGER: "I want to build, what do I need?" → NB-5

RULE NB5-NB6-002: SLF Lifecycle
  NB-5 OWNS: Obtaining initial SLF as part of development (Cluster D)
  NB-6 OWNS: SLF renewal (every 5 years) and ongoing building safety compliance
  HANDOFF: Once SLF is obtained and building is operational, NB-6 takes over.

RULE NB5-NB6-003: Strata Title
  NB-5 OWNS: The concept of strata title (Hak Milik Satuan Rumah Susun) as a property right type (Cluster A)
  NB-6 OWNS: Strata title management, common area maintenance, body corporate compliance
  RESOLUTION: NB-5 explains what strata title IS. NB-6 explains how to MANAGE it.

RULE NB5-NB6-004: Property Management Compliance
  NB-5 DOES NOT OWN: Property management company licensing, tenant management regulations, maintenance obligations
  NB-6 OWNS: All ongoing property management compliance
  EXCEPTION: Lease management (extension, termination) stays in NB-5 because it concerns LAND RIGHTS
```

### 5.4 NB-8 (Expat Life) <-> NB-5 (Property)

**Contract:**

```
RULE NB5-NB8-001: Residential Property Boundary
  NB-5 OWNS: All legal structures for property acquisition, including residential
  NB-8 OWNS: Lifestyle guidance on where to live, rental market as a consumer, neighborhood reviews
  TRIGGER: "How do I legally buy a house in Bali?" → NB-5
  TRIGGER: "What is the best neighborhood to live in Bali?" → NB-8

RULE NB5-NB8-002: Renting as Tenant
  NB-8 OWNS: Practical tenant guidance (what to expect, price ranges, negotiation, landlord relations)
  NB-5 OWNS: Legal structure of lease contracts (notarial deed, rights, termination clauses)
  RESOLUTION: NB-8 helps you CHOOSE. NB-5 helps you SECURE YOUR RIGHTS.

RULE NB5-NB8-003: Cost of Property
  NB-8 MAY reference: Approximate property costs as lifestyle context ("villas in Canggu cost $X-Y/month to rent")
  NB-5 OWNS: Property valuation, NJOP, transaction costs, investment analysis
  NEVER: NB-8 advises on property ACQUISITION. That is always NB-5.
```

---

## 6. QUERY DESIGN TEMPLATES — Full Set

Following NB-2's 5-component anatomy: Topic Anchor + Regulatory Marker + Temporal Anchor + Source Hint + Noise Control. Organized by cluster, 3-5 queries each.

### Cluster A: Land Rights & Title

**A1-L1 (Bahasa):**

> Perkembangan terbaru hak atas tanah di Indonesia 2025-2026: perubahan Hak Guna Bangunan, Hak Pakai, dan Hak Guna Usaha berdasarkan PP 18/2021 dan Permen ATR/BPN terkait. Termasuk pendaftaran tanah elektronik dan perubahan prosedur BPN. Sumber resmi Kementerian ATR/BPN dan JDIH, bukan blog properti atau agen.

**A2-L1 (English):**

> Current Indonesian land title regulations 2025-2026: Hak Pakai eligibility for foreigners (WNA) under PP 103/2015, HGB rights for PT PMA, land registration procedures at BPN, and title conversion processes. Based on ATR/BPN ministerial regulations and JDIH publications, excluding real estate marketing materials.

**A3-L2 (English):**

> Comparative analysis of Indonesian land rights security 2025-2026: Hak Milik vs HGB vs Hak Pakai vs lease — bankability (accepted by banks as collateral), renewal certainty, government revocation risk, and inheritance provisions under current agrarian law. Academic legal analysis and law firm publications.

**A4-L3 (Bahasa):**

> Rencana digitalisasi pendaftaran tanah BPN 2025-2027: sertifikat tanah elektronik, integrasi sistem BPN nasional, dan dampak pada proses balik nama. Sumber resmi Kementerian ATR/BPN dan rencana strategis pemerintah.

### Cluster B: Foreign Ownership Structures

**B1-L1 (Bahasa):**

> Peraturan terkini kepemilikan properti oleh orang asing (WNA) di Indonesia 2025-2026: Hak Pakai berdasarkan PP 103/2015, pembatasan satu properti per WNA, nilai minimum properti per zona, dan prosedur konversi Hak Milik ke Hak Pakai di BPN. Sumber resmi ATR/BPN dan JDIH.

**B2-L1 (English):**

> Legal risks of nominee property arrangements (pinjam nama) in Indonesia 2024-2026: recent court decisions invalidating nominee transactions, BPN enforcement against irregular ownership, and criminal liability for participants. Legal databases, Mahkamah Agung decisions, and authoritative legal analysis.

**B3-L2 (English):**

> Comparative cost and risk analysis of foreign property ownership structures in Bali 2025-2026: Hak Pakai direct vs PT PMA + HGB vs long-term lease — total cost over 30 years (including formation, maintenance, taxes, renewal), legal security ranking, and exit flexibility. Law firm analyses and investment advisory publications.

**B4-L4 (English):**

> Intersection of immigration status and property rights in Indonesia 2025-2026: which visa types qualify for Hak Pakai, KITAP holder advantages over KITAS for property, impact of new UU Imigrasi 1/2026 on foreigner property eligibility. Cross-referencing Kemenkumham and ATR/BPN regulations.

**B5-L1 (Bahasa):**

> Perkembangan terbaru Perjanjian Pengikatan Jual Beli (PPJB) properti di Indonesia 2025-2026: perlindungan pembeli dalam PPJB, risiko pengembang gagal memenuhi AJB, dan regulasi terbaru OJK dan ATR/BPN tentang PPJB. Sumber resmi dan analisis hukum notaris.

### Cluster C: Transaction Process

**C1-L1 (Bahasa):**

> Prosedur terbaru jual beli tanah dan bangunan di Indonesia 2025-2026: pembuatan Akta Jual Beli (AJB) oleh PPAT, pendaftaran balik nama di BPN, persyaratan dokumen lengkap, dan biaya resmi. Berdasarkan PP 24/1997, PP 18/2021, dan peraturan ATR/BPN terkini.

**C2-L1 (English):**

> Property due diligence best practices for land purchases in Bali 2025-2026: title verification at BPN (certificate authenticity, encumbrance check), zoning compliance verification against RTRW/RDTR, tax clearance requirements, and common fraud indicators. Notarial practice guides and BPN procedures.

**C3-L2 (Bahasa):**

> Perbandingan proses pendaftaran tanah di BPN kabupaten di Bali 2025-2026: Badung vs Gianyar vs Denpasar vs Tabanan — waktu proses, biaya resmi, dan perbedaan persyaratan lokal. Sumber praktisi notaris/PPAT dan informasi resmi BPN setempat.

**C4-L3 (English):**

> BPN digital transformation in land registration 2025-2027: electronic certificates, online title searches, integrated payment systems, and planned timeline for full digitalization. ATR/BPN strategic plans and government technology announcements.

### Cluster D: Development & Construction

**D1-L1 (Bahasa):**

> Peraturan Persetujuan Bangunan Gedung (PBG) dan Sertifikat Laik Fungsi (SLF) di Bali 2025-2026: prosedur pengajuan melalui SIMBG, klasifikasi bangunan, persyaratan teknis, dan biaya resmi. Sumber Dinas PUPR Provinsi Bali dan peraturan daerah terkait.

**D2-L1 (English):**

> Environmental impact assessment requirements for property development in Bali 2025-2026: AMDAL, UKL-UPL, and SPPL thresholds by project scale, application process at DPMPTSP Bali, and integration with OSS-RBA. Official provincial government sources and environmental regulations.

**D3-L1 (Bahasa):**

> Peraturan tata ruang wilayah (RTRW dan RDTR) Provinsi Bali dan kabupaten/kota 2025-2026: zonasi kawasan wisata, kawasan hijau, kawasan lindung, pembatasan ketinggian bangunan, dan moratorium pembangunan di kawasan tertentu. Sumber resmi Bappeda Bali dan Dinas PUPR.

**D4-L2 (English):**

> Bali construction permitting timeline and cost analysis 2025-2026: average PBG processing time by kabupaten, total permitting cost as percentage of construction budget, and comparison of Badung vs Gianyar vs Buleleng for development ease. Practitioner reports and government data.

**D5-L3 (Bahasa):**

> Rencana revisi RTRW Provinsi Bali dan dampaknya terhadap pembangunan properti 2025-2027: perubahan zonasi yang direncanakan, kawasan strategis baru, dan moratorium pembangunan. Sumber resmi DPRD Bali, Bappeda, dan pemberitaan media terpercaya.

### Cluster E: Property Investment

**E1-L1 (English):**

> Bali villa rental investment regulatory framework 2025-2026: licensing requirements (Pondok Wisata, classified hotel), foreign investor eligibility, recent enforcement against unlicensed operators, and government policy on short-term rentals. Official tourism regulations and enforcement reports, not rental agency marketing.

**E2-L1 (Bahasa):**

> Regulasi investasi aparthotel dan serviced apartment di Bali 2025-2026: persyaratan izin usaha, batasan kepemilikan asing, peraturan strata title, dan kebijakan Pemprov Bali tentang properti wisata. Sumber resmi Dinas Pariwisata Bali dan peraturan daerah.

**E3-L2 (English):**

> Comparative analysis of foreign property investment returns in Bali vs Lombok vs Labuan Bajo 2025-2026: regulatory framework differences, investor incentives, infrastructure development, and market maturity. Investment advisory reports and provincial government publications.

**E4-L4 (English):**

> Cross-domain analysis of Bali villa investment lifecycle 2025-2026: PT PMA formation (NB-3), HGB acquisition (NB-5), construction permits (NB-5), tourism licensing (NB-3), rental income taxation (NB-4), and ongoing compliance (NB-6). Integrated legal and financial analysis from law firms and advisory publications.

### Cluster F: Disputes & Protection

**F1-L1 (Bahasa):**

> Sengketa tanah dan properti di Bali 2024-2026: kasus nominee yang dibatalkan, sertifikat ganda, penipuan tanah, dan tren putusan Pengadilan Negeri dan Mahkamah Agung. Berdasarkan putusan pengadilan dan analisis hukum agraria resmi.

**F2-L1 (English):**

> Property fraud patterns and land mafia activities in Bali 2024-2026: certificate forgery, double-selling, false power of attorney, and BPN investigation outcomes. Enforcement reporting from established news sources and government anti-corruption announcements.

**F3-L2 (English):**

> Analysis of Indonesian court decisions on foreigner property disputes 2020-2026: nominee arrangement invalidation, lease contract disputes, PPJB enforcement, and title dispute resolution. Supreme Court (Mahkamah Agung) decision database and legal analysis publications.

### Cluster G: Bali-Specific Regulations

**G1-L1 (Bahasa):**

> Peraturan daerah (Perda) dan Peraturan Gubernur (Pergub) Bali tentang tata ruang dan properti 2025-2026: zonasi kawasan wisata, kawasan suci pura (radius), kawasan hijau (subak, hutan), pembatasan ketinggian bangunan, dan retribusi terkait properti. Sumber resmi JDIH Bali dan Pemprov Bali.

**G2-L1 (English):**

> Bali temple exclusion zones and sacred site regulations affecting property development 2025-2026: pura radius restrictions by temple category (Kahyangan Tiga, Kahyangan Jagat, etc.), recent enforcement, and impact on development permits. Official Bali provincial regulations and cultural authority sources.

**G3-L2 (Bahasa):**

> Peran desa adat dan awig-awig dalam hukum pertanahan di Bali 2025-2026: pembatasan penjualan tanah adat, kewajiban gotong royong pemilik tanah, dan interaksi antara hukum adat dan hukum pertanahan nasional. Berdasarkan Perda Bali tentang Desa Adat dan analisis akademik Universitas Udayana.

**G4-L4 (English):**

> Impact of Bali tourism regulations on property investment 2025-2026: tourist levy implementation and revenue allocation, hotel moratorium zones, Pondok Wisata vs classified hotel regulations, and governor's sustainable tourism policy framework. Cross-referencing tourism, environmental, and property regulations from official Bali provincial sources.

**G5-L1 (English):**

> Bali coastal setback and waterfront property regulations 2025-2026: minimum distance from shoreline for construction, special permits for coastal development, environmental restrictions in coastal zones, and recent enforcement actions. Official PUPR and environmental authority sources.

---

## 7. CAPACITY MODEL REASONING

### 7.1 Comparison with NB-2

NB-2 (Immigration & Visa) has:

- 55 sources (53 at last count, 55 target)
- 36 verified claims
- NHS 0.801
- 70 ACTIVE cap
- 5 clusters (A-E)

NB-5 (Property & Real Estate) is MORE COMPLEX than NB-2 because:

1. **More regulatory layers:** NB-2 is primarily national law (UU, PP, Permenkumham) with local enforcement variation. NB-5 has national (UUPA, PP) + provincial (Perda, Pergub) + kabupaten (Perbup) + customary (awig-awig). Four layers vs two.

2. **More clusters:** NB-5 has 7 clusters vs NB-2's 5. The additional clusters (F: Disputes, G: Bali-Specific) add ~20 sources.

3. **More cross-domain interfaces:** NB-2 has 2 major cross-domain links (tax, company). NB-5 has 4 major cross-domain links (NB-3, NB-4, NB-6, NB-8).

4. **More local sources needed:** NB-2 allocates ~20% to local (Bali) sources. NB-5 needs ~50% local sources.

5. **Less structured regulatory landscape:** Immigration has clear visa types and permit categories. Property law has a less structured hierarchy of rights, with significant gray areas (nominee arrangements, awig-awig, PPJB disputes).

### 7.2 Proposed Source Counts

**Total ACTIVE cap: 75**

Justification for 75 instead of 70: NB-5 has 7 clusters (40% more than NB-2's 5) and 50% local content ratio (vs NB-2's 20%). The additional 5 slots are specifically for Bali-specific T2 sources that have no national equivalent. NLM Ultra allows 600 sources per notebook, and our cap of 75 is still well within performance limits.

Alternatively, if we must stay at 70 (standardization argument), the Bali-Specific cluster (G) absorbs into other clusters as sub-topics. I recommend against this because it would dilute the local intelligence that makes NB-5 uniquely valuable for Bali Zero's clients.

**Budget allocation (75 ACTIVE cap):**

```
+---------------------------------------------------------------+
|                    75 ACTIVE SOURCE BUDGET                      |
|                                                                |
|  +-----------------------+  +------------------------------+   |
|  |  CANONICAL: 18-25     |  |  WORKING: 25-35              |   |
|  |  (permanent anchors)  |  |  (rolling intelligence)      |   |
|  |                       |  |                              |   |
|  |  Target: 22           |  |  Target: 30                  |   |
|  |  Min: 18              |  |  Max: 35 (triggers consol.) |   |
|  |  Max: 25              |  |  Min: 15 (alarm if below)   |   |
|  +-----------------------+  +------------------------------+   |
|                                                                |
|  +-----------------------+  +------------------------------+   |
|  |  MASTER DIGEST: 5-8   |  |  REFERENCE: 3-6              |   |
|  |  (synthesized docs)   |  |                              |   |
|  |                       |  |  Target: 5                   |   |
|  |  Fixed 5 minimum:     |  |  Min: 3                      |   |
|  |    MD-1 Change Log    |  |  Max: 6                      |   |
|  |    MD-2 Ops Status    |  |                              |   |
|  |    MD-3 Cross-Domain  |  |                              |   |
|  |    MD-4 Open Questions|  |                              |   |
|  |    MD-5 Decision Guide|  |                              |   |
|  +-----------------------+  +------------------------------+   |
|                                                                |
|  HEADROOM: ~10 slots (13%) for ingest spikes                   |
|  IDEAL STEADY STATE: ~62 sources                               |
+---------------------------------------------------------------+
```

**Note:** MD-5 (Decision Guide) is an NB-5-specific addition containing the Foreigner Ownership Decision Tree from Section 3 above. This is a unique structural element not present in NB-2.

### 7.3 Per-Cluster Source Budget

| Cluster              | Canonical (T0-T2) | Working (T2-T5) | Total Target | Rationale                                                               |
| -------------------- | ----------------- | --------------- | ------------ | ----------------------------------------------------------------------- |
| A: Land Rights       | 6-8               | 2-4             | 8-12         | Mostly stable regulations, few news sources needed                      |
| B: Foreign Ownership | 4-6               | 4-8             | 8-14         | Core regulations + active monitoring of court decisions and enforcement |
| C: Transaction       | 3-5               | 2-4             | 5-9          | Procedural, relatively stable                                           |
| D: Development       | 3-5               | 5-8             | 8-13         | National framework + heavy Bali local regulation monitoring             |
| E: Investment        | 2-3               | 4-7             | 6-10         | Market-driven, more working sources                                     |
| F: Disputes          | 2-3               | 3-5             | 5-8          | Court decisions + enforcement monitoring                                |
| G: Bali-Specific     | 3-5               | 4-7             | 7-12         | Heavily local, most volatile                                            |
| Cross-domain (MDs)   | 5                 | 0               | 5            | Fixed MD-1 through MD-5                                                 |
| **Total**            | **28-40**         | **24-43**       | **52-83**    | **Target: ~62 steady state**                                            |

### 7.4 Per-Tier Distribution

| Tier                          | Count Target | Examples                                                                      |
| ----------------------------- | ------------ | ----------------------------------------------------------------------------- |
| T0 (National Law)             | 10-12        | UUPA, PP 18/2021, PP 103/2015, PP 24/1997, UU 28/2002, UU 26/2007, UU 11/2020 |
| T1 (National Implementation)  | 5-7          | Permen ATR/BPN, Surat Edaran Ditjen, BPN circulars                            |
| T2 (Regional/Local Authority) | 10-14        | Perda Bali RTRW, Pergub, BPN Bali, DPMPTSP Bali, Dinas PUPR Bali              |
| T3 (Local Enforcement)        | 2-4          | Satpol PP enforcement reports, local government actions                       |
| T4 (Official Social)          | 4-6          | @bpn_bali, @pemkabbadung, @denpasarkota Instagram                             |
| T5 (Press/Analysis)           | 8-12         | Law firm analyses, NusaBali, Bali Post, academic papers                       |
| T6 (Community)                | 0            | Never in ACTIVE set                                                           |
| Master Digest                 | 5            | MD-1 through MD-5                                                             |
| **Total**                     | **44-60**    | **(steady state ~55-62)**                                                     |

### 7.5 T0 Regulations — Exhaustive List

These are the T0 (national primary law) sources that MUST be in NB-5 as Canonical:

| #   | Regulation                   | Content                                                                                 | Year | Status                             |
| --- | ---------------------------- | --------------------------------------------------------------------------------------- | ---- | ---------------------------------- |
| 1   | **UU 5/1960** (UUPA)         | Basic Agrarian Law — foundation of all land rights                                      | 1960 | In force (amended)                 |
| 2   | **UU 11/2020** (Cipta Kerja) | Omnibus Law — reformed land rights framework                                            | 2020 | In force                           |
| 3   | **PP 18/2021**               | Implementing reg for Cipta Kerja on land rights (HGU, HGB, Hak Pakai, Hak Pengelolaan)  | 2021 | In force                           |
| 4   | **PP 103/2015**              | Foreigner residential property ownership (Hak Pakai) — 1 property limit, minimum values | 2015 | In force (verify amendments)       |
| 5   | **PP 40/1996** (as amended)  | HGU, HGB, Hak Pakai — detailed provisions                                               | 1996 | Partially superseded by PP 18/2021 |
| 6   | **PP 24/1997**               | Land registration (Pendaftaran Tanah)                                                   | 1997 | In force (amended)                 |
| 7   | **Permen ATR/BPN 18/2021**   | Procedures for Hak Milik → Hak Pakai conversion for WNA                                 | 2021 | In force                           |
| 8   | **UU 28/2002**               | Building Law (Bangunan Gedung)                                                          | 2002 | In force                           |
| 9   | **UU 26/2007**               | Spatial Planning (Penataan Ruang)                                                       | 2007 | In force                           |
| 10  | **PP 22/2021**               | Environmental protection implementing regulation                                        | 2021 | In force                           |
| 11  | **GR 28/2025**               | Business licensing (replaces PP 5/2021) — includes PBG integration                      | 2025 | In force (NEW)                     |

**T0 PENDING VERIFICATION (need Gemini search to confirm):**

- PP on Hak Tanggungan (mortgage law) — possibly UU 4/1996
- Perpres on minimum investment for PT PMA
- Recent Permen ATR/BPN updates (2024-2025)
- Perda Bali 16/2009 on RTRW (may be T2 rather than T0)

### 7.6 Why This Capacity Is Right

- NB-2 operates at 55 sources with 5 clusters and 80/20 national/local ratio
- NB-5 adds 2 clusters and flips to 50/50 national/local ratio
- The proportional increase: (7/5) \* 55 = ~77, adjusted down to 75 for the cap
- Steady state target of 62 sources gives 13 slots of headroom (17%)
- This headroom is critical because property law has more local volatility than immigration law
- 75 is conservative: we could go to 80-85 without NLM performance degradation, but discipline in the 70-75 range enforces consolidation hygiene

---

## 8. ADDITIONAL REASONING NOTES

### 8.1 Claim Categories for NB-5

Adapting NB-2's 10 claim categories for property context:

| Category                 | NB-5 Meaning                                   | Example                                                                          |
| ------------------------ | ---------------------------------------------- | -------------------------------------------------------------------------------- |
| **LEGAL_CHANGE**         | New/amended land or property regulation        | "PP 103/2015 amended to increase minimum property value for WNA to Rp 3 billion" |
| **OPERATIONAL_CHANGE**   | Same law, different practice at BPN/PPAT       | "BPN Badung now requires additional document for HGB extension"                  |
| **ENFORCEMENT_ACTION**   | Specific property enforcement event            | "BPN revokes 5 nominee-held certificates in Canggu"                              |
| **ENFORCEMENT_PATTERN**  | Repeated trend in property enforcement         | "Third report this month of BPN rejecting Hak Pakai applications without KITAS"  |
| **POLICY_SIGNAL**        | Forward-looking official statement on property | "ATR/BPN Minister announces plan to digitalize all land certificates by 2027"    |
| **PROCEDURAL_UPDATE**    | Process/form/system change at BPN              | "BPN online service portal adds Hak Pakai application tracking"                  |
| **LOCAL_REGULATION**     | Perda/Pergub affecting property                | "Pergub Bali restricts villa construction in green zone areas"                   |
| **DOCUMENT_REQUIREMENT** | Docs added/removed for property transactions   | "BPN now requires environmental clearance letter for HGB applications"           |
| **FEE_CHANGE**           | Official tariff change for property services   | "BPN registration fees increased per new PP on PNBP"                             |
| **ZONING_CHANGE**        | Spatial plan modification                      | "Badung RDTR reclassifies Canggu area from tourism to mixed-use"                 |

**New category: ZONING_CHANGE.** This replaces NB-2's UNCLASSIFIED_SIGNAL as the 10th category. Zoning changes are too important and frequent in Bali to be lumped into an unclassified bucket. They directly affect what can be built where and property values.

### 8.2 Domain Denylist for NB-5

Starting denylist (extends NB-2's):

```
# NB-2 inherited
tripadvisor.com, expat.com/forum, kaskus.co.id, nomadicmatt.com,
thepointsguy.com, reddit.com, quora.com, medium.com/@, youtube.com,
tiktok.com, pinterest.com, booking.com, agoda.com, skyscanner.com,
lonelyplanet.com

# NB-5 specific
rumah.com, rumah123.com, olx.co.id,
lamudi.co.id, dotproperty.co.id,
airbnb.com, vrbo.com, booking.com,
expatbali.com, baliguide.com, thebalibible.com,
livinginbali.net, baliexpat.com,
propertyGuru.com.sg (Singapore-focused, may confuse)
```

**Rationale:** Property listing sites (rumah.com, rumah123.com, lamudi) are commercial platforms, not regulatory sources. Expat lifestyle blogs may contain property info but are T6 at best. Airbnb/VRBO are commercial platforms, not intelligence sources.

**NOT denied:** `hukumonline.com` (excellent legal analysis), `ssek.com` (top law firm), `castleasia.com` (property legal analysis), `balirealestate.com` (has useful regulatory summaries but watch for bias).

### 8.3 Sensitivity Matrix

| Topic                  | Sensitivity | Handling                                                           |
| ---------------------- | ----------- | ------------------------------------------------------------------ |
| Nominee arrangements   | HIGH        | Risk education only, never instruction. Explicit WARNING prefix.   |
| Land prices            | MEDIUM      | NJOP reference only, no market prices. Disclaimer on staleness.    |
| Awig-awig restrictions | MEDIUM      | General framework only. "Verify locally" disclaimer mandatory.     |
| BPN corruption         | HIGH        | Only from T3+ enforcement sources. Never speculation.              |
| Developer reputation   | HIGH        | Never name specific developers. Only cite enforcement outcomes.    |
| Tax optimization       | MEDIUM      | Reference NB-4. NB-5 covers triggers, not optimization strategies. |
| Disputed territories   | HIGH        | Only cover verified BPN certificate data. Never local rumors.      |

---

_Reasoning analysis complete. Ready for synthesis with Gemini (architecture) and Codex (discipline) contributions._

_Chain-of-Thought Reasoner: Claude Opus 4.6, 2026-03-29_

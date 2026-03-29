# NB-5: Property & Real Estate Indonesia — Brainstorming Prompt

> **Target:** AI agent(s) tasked with designing the NB-5 population plan
> **Date:** 2026-03-29
> **Author:** Claude Opus 4.6 (NB pipeline architect)
> **Reference Model:** NB-2 Immigration & Visa (55 sources, 36 claims, NHS 0.801, pipeline live)

---

## YOUR MISSION

You are designing **NB-5: Property & Real Estate Indonesia 2025** — one of 10 curated NotebookLM intelligence notebooks for Bali Zero, a business services firm in Bali serving 5,000+ foreign clients (expats, investors, entrepreneurs).

**Bali context is critical:** This is not generic Indonesian property law. Bali has the hottest foreign property market in Indonesia — villas, aparthotels, land leases, beach clubs, co-living spaces. Clients are mostly foreign nationals trying to own, lease, develop, or invest in property in Bali. The legal landscape is complex because **foreigners cannot own freehold land (Hak Milik) in Indonesia**.

Your job is to **map the complete circumference of the topic** — define what is INSIDE, what is OUTSIDE, where the borders are with adjacent notebooks, and produce a structured population plan.

You are NOT writing code. You are designing an intelligence architecture.

---

## THE METHOD (from NB-2 — follow this exactly)

NB-2 was built through a rigorous 7-step pipeline. Each step was designed by consulting 3 AI in parallel (Gemini 3.1 Pro for search-grounded research, Codex GPT-5.4 for operational discipline, DeepSeek R1 671B for chain-of-thought reasoning), then a synthesizing architect (Claude Opus 4.6) merged contributions into unified specs.

### The 7 Steps (replicate for NB-5):

| Step | Name                     | What It Produces                                                                                                                                                                                                                                                                              | NB-2 Reference                                                |
| ---- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| 1    | **Query Design**         | Templates for querying NLM, organized by cluster. 5 components: Topic Anchor + Regulatory Marker + Temporal Anchor + Source Hint + Noise Control. Dual-language (60% Bahasa, 30% English, 10% bridge). 4 query levels: L1 monitoring, L2 comparative, L3 predictive, L4 cross-domain.         | `docs/superpowers/specs/nlm-deep-research/01_query_design.md` |
| 2    | **Sequencing**           | Daily execution window, query ordering, weekly cluster rotation, breaking news override protocol. NB-2 runs 01:10-02:20 WITA Mon-Fri. 2 queries/day. Weekend OFF.                                                                                                                             | `02_sequencing.md`                                            |
| 3    | **Quality Verification** | 7-tier source hierarchy (T0-T6), confidence scoring formula (6 factors: Authority 0.30 + Corroboration 0.25 + Specificity 0.15 + Type 0.12 + Recency 0.10 + Geo 0.08 - Penalty), claim extraction with 10 categories, thresholds (≥0.75 VERIFIED, 0.55-0.74 PROVISIONAL, <0.55 excluded).     | `03_quality_verification.md`                                  |
| 4    | **Source Management**    | 6-stage lifecycle (INGEST→QUARANTINE→TRIAGE→ACTIVE→CONSOLIDATE→ARCHIVE), Source Value Score (SVS), Notebook Health Score (NHS), 70 ACTIVE cap, 4 Master Documents (Change Log, Ops Status, Cross-Domain, Open Questions), dedup (4-level), external state files (sources.json, claims.jsonl). | `04_source_management.md`                                     |
| 5    | **Scraper Integration**  | Handoff package (JSON) to intel scraper, Topic Relevance Score (TRS), NLMEnricher adapter, cross-validation (convergence boost/contradiction penalty), War Room integration.                                                                                                                  | `05_scraper_integration.md`                                   |
| 6    | **Failure Modes**        | 10 invariants, 30 failure modes, 3 circuit breakers (CB-NLM, CB-SOURCE, CB-INTEGRATION), degradation levels, pre-flight checklist, recovery procedures.                                                                                                                                       | `06_failure_modes.md`                                         |
| 7    | **Testing Protocol**     | 8-phase live test on NLM (Phase 0-7 + Go/No-Go), acceptance criteria per phase, KPIs, statistical tests, cost model.                                                                                                                                                                          | `07_testing_protocol.md`                                      |

### Key NB-2 Design Principles (ENFORCE):

1. **NLM is UPSTREAM of the intel scraper** — NLM runs first (01:00-02:20), produces verified brief, scraper runs after (03:00) independently
2. **Sources are curated, not dumped** — 70 ACTIVE cap, SVS scoring, lifecycle management
3. **Claims are atomic** — one fact per claim, with confidence score, source backing, and category
4. **Master Documents are NLM sources** (not notes) — they get cited in queries
5. **Cross-domain handled via references** — each NB owns its core, references others via MDs
6. **File-based handoff** — zero coupling between pipeline components
7. **4-voice adversarial review** — every phase tested by Gemini + Codex + DeepSeek + Claude independently

---

## WHAT WE KNOW ABOUT NB-5

### Current State

NB-5 "Property & Real Estate Indonesia 2025" has **6 seed sources** (all internal Bali Zero guides):

| #   | Source                                                               | Type  |
| --- | -------------------------------------------------------------------- | ----- |
| 1-6 | _(6 internal Bali Zero guides — inspect NB-5 notebook to enumerate)_ | Guide |

> **NOTE to brainstormer:** Query NB-5 to list actual seed sources before designing clusters. Do not assume content.

### Adjacent Notebooks (borders)

| NB       | Topic                   | Border with NB-5                                                                                                |
| -------- | ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| **NB-3** | Company Setup           | PT PMA as property-holding vehicle (HGB rights), company formation for property ownership                       |
| **NB-4** | Tax & Fiscal            | Property taxes (BPHTB acquisition tax, PBB annual tax), capital gains, rental income tax, VAT on property sales |
| **NB-6** | Operations & Compliance | Property management compliance, building permits renewal, environmental compliance                              |
| **NB-8** | Expat Life              | Residential property for personal use, renting vs buying decision, neighborhood guides                          |

### Business Context (Bali Zero clients)

**Who asks about property:**

- Foreign investors wanting to own villas/aparthotels for rental income
- Expats wanting a home in Bali (lease or ownership structure)
- Developers wanting to build (land acquisition, permits, zoning)
- Digital nomads exploring co-living investments
- Clients with existing properties needing amendments, extensions, disputes

**The CORE TENSION for foreigners:**
Foreigners CANNOT own Hak Milik (freehold) land in Indonesia. Legal structures used:

- **Hak Pakai** (Right of Use) — foreigners directly, 30+20+30 = 80 years max (post PP 18/2021)
- **HGB (Hak Guna Bangunan)** via PT PMA — company holds building rights, 30+20+30 = 80 years (post PP 18/2021)
- **Lease (Sewa)** — contractual, typically 25-30 years, renewable
- **Nominee arrangement** — ILLEGAL but still practiced, high risk
- **PPJB (Perjanjian Pengikatan Jual Beli)** — preliminary sale agreement

**Top 10 likely client questions (to verify):**

1. "Can foreigners buy property in Bali?"
2. "What is the difference between Hak Pakai and HGB?"
3. "Should I use a PT PMA to buy property?"
4. "How does a land lease work in Bali?"
5. "Is nominee arrangement safe?"
6. "What taxes do I pay when buying property?"
7. "Can I build a villa on leased land?"
8. "What are the zoning rules in Bali?"
9. "How do I check if land has clean title (sertifikat)?"
10. "What happens to my property rights when the lease expires?"

---

## YOUR DELIVERABLES

### Phase 1: Topic Circumference (this brainstorm)

Produce a structured analysis covering:

1. **PERIMETER** — What is INSIDE NB-5 vs OUTSIDE? Draw precise borders with NB-3, NB-4, NB-6, NB-8.

2. **CLUSTER DESIGN** — Propose 5-7 thematic clusters (following NB-2's A-E pattern). Consider:
   - (A) Land Rights & Title (Hak Milik, Hak Pakai, HGB, Hak Sewa, Hak Guna Usaha)
   - (B) Foreign Ownership Structures (direct Hak Pakai, PT PMA + HGB, lease, PPJB)
   - (C) Transaction Process (due diligence, PPAT, AJB, BPN registration)
   - (D) Development & Construction (PBG/IMB, SLF, AMDAL, zoning/RTRW)
   - (E) Property Investment (villa rental ROI, aparthotels, co-living, hospitality)
   - (F) Disputes & Protection (nominee risk, fraud, land mafia, certificate disputes)
   - (G) Bali-Specific (zoning RTRW Bali, green zone restrictions, temple exclusion zones, tourist levy on property)

3. **T0 REGULATIONS** — List ALL Indonesian property laws that MUST be T0 sources. Key candidates:
   - **UU 5/1960** (UUPA — Undang-Undang Pokok Agraria, the Basic Agrarian Law — THE foundation)
   - **UU 6/2023** (Cipta Kerja final form — via Perpu 2/2022, replaced UU 11/2020; PP 18/2021 is its implementing regulation)
   - **PP 18/2021** (Hak Pengelolaan, Hak Atas Tanah — land rights post-Cipta Kerja; REVOKED PP 103/2015, PP 40/1996, parts of PP 24/1997; changed HP/HGB to 30+20+30=**80 years**)
   - ~~**PP 103/2015**~~ **REVOKED** by PP 18/2021 — provisions absorbed; implementing Permen also revoked by Permen ATR/BPN 18/2021
   - ~~**PP 40/1996**~~ **REVOKED** by PP 18/2021 — fully superseded
   - **PP 24/1997** (Pendaftaran Tanah — **partially revoked** by PP 18/2021; use Permen ATR/BPN 16/2021 for current procedures)
   - **Permen ATR/BPN 18/2021** (Procedures for land rights, Hak Milik → Hak Pakai conversion for WNA — revoked Permen 13/2016 and 29/2016)
   - **UU 28/2002** (Bangunan Gedung — building law)
   - **Permen ATR/BPN** (other Minister of Agrarian Affairs regulations — enumerate during research)
   - **Perda Bali** (Provincial/Kabupaten spatial planning — RTRW)
   - **UU 26/2007** (Penataan Ruang — spatial planning law)

4. **T2-T4 SOURCES** — Ministerial regulations, BPN circulars, notary practice guides, Bali local regulations, social accounts to monitor

5. **GAP ANALYSIS** — What is completely missing from the 6 seed sources?

6. **CROSS-DOMAIN RULES** — Exactly how NB-5 interfaces with:
   - NB-3: PT PMA as property vehicle (NB-3 owns company formation, NB-5 owns property acquisition via company)
   - NB-4: Property taxes (NB-4 owns tax rates/obligations, NB-5 owns which taxes trigger in property transactions)
   - NB-6: Building permits renewal, strata title management

7. **CAPACITY MODEL** — Target source count per tier and per cluster

### Phase 2 (later): Population plan following NB-2's 7-step method

---

## CRITICAL WARNINGS

### Property Law is LOCAL

Unlike visa law (national) or tax law (national), property law in Indonesia has a **massive local component**:

- **BPN (Badan Pertanahan Nasional)** offices handle registration — each kabupaten has its own
- **RTRW (Rencana Tata Ruang Wilayah)** zoning is provincial/kabupaten-level
- **Perda Bali** regulates construction, tourism zones, green zones, temple exclusion
- **PPAT (Pejabat Pembuat Akta Tanah)** — specific to each jurisdiction
- **Awig-awig** — Balinese customary law affects some land (especially desa adat land)

This means NB-5 needs MORE local (Bali-specific) sources than NB-2 or NB-4.

### Nominee Arrangements

Nominee structures (Indonesian holds Hak Milik "on behalf of" a foreigner) are:

- **Explicitly illegal** under UU 5/1960 and PP 18/2021
- **Still widely practiced** — many BZ clients ask about them
- NB-5 must cover the legal risks WITHOUT providing instructions on how to set them up
- Frame as: "Here are the risks" not "Here is how to do it"

### PPJB vs AJB

- **PPJB** (Perjanjian Pengikatan Jual Beli) = preliminary binding agreement (pre-title transfer)
- **AJB** (Akta Jual Beli) = official sale deed by PPAT (transfers title)
- Many disputes arise from PPJB without AJB follow-through — NB-5 must cover this clearly

### Bali Zero's PricingTool

Government fees (BPHTB rates, BPN registration fees, notary tariffs) belong in NB-5 as reference data. Bali Zero service prices for property consulting belong ONLY in PricingTool, NEVER in NB-5.

---

## REFERENCE: THE 10 NOTEBOOKS

| NB       | Title                                     | Sources | Status                                   |
| -------- | ----------------------------------------- | ------- | ---------------------------------------- |
| NB-1     | Nuzantara Codebase & Architecture         | 85      | COMPLETE (oracle)                        |
| NB-2     | Immigration & Visa — Indonesia 2025       | 53      | COMPLETE (pipeline live, T4 monitor)     |
| NB-3     | Company Setup — Indonesia 2025            | 10      | BRAINSTORM COMPLETE (population pending) |
| **NB-4** | **Tax & Fiscal Indonesia**                | **9**   | **BRAINSTORM PROMPT READY**              |
| **NB-5** | **Property & Real Estate Indonesia 2025** | **6**   | **← BRAINSTORM TARGET (this prompt)**    |
| NB-6     | Operations & Compliance Indonesia 2025    | 6       | SEED                                     |
| NB-7     | Editorial & Content Strategy 2025         | 6       | SEED                                     |
| NB-8     | Expat Life Bali 2025                      | 7       | SEED                                     |
| NB-9     | Research Lab                              | 582     | ACTIVE (lab, not production)             |
| NB-10    | Team Guides                               | 6       | SEED                                     |

## REFERENCE FILES

All NB-2 design documents are at:

```
docs/superpowers/specs/nlm-deep-research/
├── 00_mega_synthesis.md          # High-level overview
├── 01_query_design.md            # Query templates, clusters, language strategy
├── 02_sequencing.md              # Daily pipeline timing
├── 03_quality_verification.md    # Source tiers, confidence scoring, claim extraction
├── 04_source_management.md       # Lifecycle, SVS, NHS, capacity management
├── 05_scraper_integration.md     # Handoff, TRS, NLMEnricher
├── 06_failure_modes.md           # Invariants, circuit breakers, recovery
├── 07_testing_protocol.md        # 8-phase test protocol
├── NB2_FULL_REPORT.md            # Complete testing report (1200+ lines)
└── PROGRESS.md                   # Master progress tracker
```

Pipeline code at: `apps/evaluator/nlm_deep_research/` (9 modules, 3,677 lines)

NB-3 brainstorm findings (adjacent notebook, done today):

- GR 28/2025 replaced PP 5/2021 for business licensing — OSS-RBA revamp
- BKPM Regulation 5/2025 is the implementing regulation
- 7 clusters (A-G): PT PMA, PT Lokal/CV, Licensing/KBLI, Amendments, Compliance, Sector-Specific, Dissolution
- Licensing is the largest cluster (18-22 sources) with 6 sub-categories including environmental permits (AMDAL, UKL-UPL, SPPL) and building permits (PBG, SLF)
- **PT PMA as property-holding vehicle** is a shared topic: NB-3 owns company formation, NB-5 owns property acquisition through the company
- **Environmental/building permits** for construction projects: shared between NB-3 (Cluster C.3-C.4) and NB-5 (Cluster D)

---

## PROPERTY-SPECIFIC INTELLIGENCE REQUIREMENTS

### The Land Title Hierarchy (MUST be in NB-5)

```
HAK MILIK (Freehold)
├── Indonesian citizens ONLY
├── Strongest title — perpetual, inheritable
├── CANNOT be held by foreigners or PT PMA
└── Basis: UU 5/1960 Pasal 20

HAK GUNA BANGUNAN (Building Rights)
├── Indonesian citizens + PT (including PT PMA)
├── 30 years + 20 extension + 30 renewal = 80 years (post PP 18/2021)
├── Right to build ON someone else's land
├── Most common for PT PMA property ownership
└── Basis: UU 5/1960 Pasal 35, PP 18/2021

HAK PAKAI (Right of Use)
├── Indonesian citizens + foreigners (WNA) + legal entities
├── 30 years + 20 extension + 30 renewal = 80 years (post PP 18/2021)
├── Right to USE land for specific purpose
├── The ONLY direct land right for foreigners
├── Limited to residential use for WNA (1 per person)
└── Basis: UU 5/1960 Pasal 41, PP 18/2021

HAK GUNA USAHA (Cultivation Rights)
├── PT (including PT PMA)
├── 35 years + 25 extension + 25 renewal = 85 years
├── For agriculture, plantation, fishery
└── Basis: UU 5/1960 Pasal 28

LEASE (SEWA / HAK SEWA)
├── Anyone (WNA included)
├── Contractual, not registered at BPN
├── Typical: 25-30 years, renewable by agreement
├── Common in Bali for villa/commercial
└── Basis: Contract law (KUH Perdata)
```

### Key Agencies to Monitor

| Agency                    | Role                              | Social/Web                                                         |
| ------------------------- | --------------------------------- | ------------------------------------------------------------------ |
| **BPN (ATR/BPN)**         | Land registration, title issuance | @kaborekementerian*atr (Instagram) — \_verify handle, likely typo* |
| **BPN Bali**              | Provincial land office            | @bpn_bali (Instagram)                                              |
| **Dinas PUPR Bali**       | Building permits (PBG)            | Web                                                                |
| **Bappeda Bali**          | Spatial planning (RTRW)           | Web                                                                |
| **Dinas Pariwisata Bali** | Tourism zoning                    | @disdikporabali (varies)                                           |

---

_Prompt prepared by Claude Opus 4.6 — NLM Pipeline Architect, 2026-03-29_

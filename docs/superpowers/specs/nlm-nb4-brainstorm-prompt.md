# NB-4: Tax & Fiscal Indonesia — Brainstorming Prompt

> **Target:** AI agent(s) tasked with designing the NB-4 population plan
> **Date:** 2026-03-29
> **Author:** Claude Opus 4.6 (NB pipeline architect)
> **Reference Model:** NB-2 Immigration & Visa (55 sources, 36 claims, NHS 0.801, pipeline live)

---

## YOUR MISSION

You are designing **NB-4: Tax & Fiscal Indonesia** — one of 10 curated NotebookLM intelligence notebooks for Bali Zero, a business services firm in Bali serving 5,000+ foreign clients (expats, investors, entrepreneurs).

Your job is to **map the complete circumference of the topic** — define what is INSIDE, what is OUTSIDE, where the borders are with adjacent notebooks, and produce a structured population plan.

You are NOT writing code. You are designing an intelligence architecture.

---

## THE METHOD (from NB-2 — follow this exactly)

NB-2 was built through a rigorous 7-step pipeline. Each step was designed by consulting 3 AI in parallel (Gemini 3.1 Pro for search-grounded research, Codex GPT-5.4 for operational discipline, DeepSeek R1 671B for chain-of-thought reasoning), then a synthesizing architect (Claude Opus 4.6) merged contributions into unified specs.

### The 7 Steps (replicate for NB-4):

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

## WHAT WE KNOW ABOUT NB-4

### Current State

NB-4 "Tax & Fiscal Indonesia" has **9 seed sources** (all internal Bali Zero guides):

| #   | Source                                     | Type  |
| --- | ------------------------------------------ | ----- |
| 1   | _(to be listed after notebook inspection)_ | Guide |
| ... | ...                                        | ...   |

### Adjacent Notebooks (borders)

| NB       | Topic                   | Border with NB-4                                                                               |
| -------- | ----------------------- | ---------------------------------------------------------------------------------------------- |
| **NB-2** | Immigration & Visa      | Tax obligations tied to visa status (tax residency 183-day rule)                               |
| **NB-3** | Company Setup           | NPWP registration during company formation, PKP/VAT registration, corporate tax type selection |
| **NB-5** | Property & Real Estate  | Property taxes (BPHTB, PBB), capital gains on property, rental income taxation                 |
| **NB-6** | Operations & Compliance | Ongoing tax reporting as part of operational compliance                                        |
| **NB-8** | Expat Life              | Personal income tax for expats, tax treaty benefits, exit tax                                  |

### Business Context (Bali Zero clients)

**Who asks about tax:**

- Foreign investors with PT PMA (corporate tax obligations)
- Expats working in Bali (personal income tax, tax residency)
- Property buyers (transfer tax, annual property tax)
- Digital nomads (unclear tax status, treaty benefits)
- Business owners (VAT, withholding taxes, annual returns)

**Top 10 likely client questions (to verify):**

1. "Do I need to pay tax in Indonesia?"
2. "What is the corporate tax rate for PT PMA?"
3. "How does the 183-day rule work?"
4. "What taxes apply when buying property in Bali?"
5. "Do I need to file personal tax returns as an expat?"
6. "What is NPWP and do I need one?"
7. "How does VAT (PPN) work in Indonesia?"
8. "Are there tax treaties between Indonesia and [my country]?"
9. "What withholding taxes apply to payments to my company?"
10. "What happens if I don't file taxes?"

---

## YOUR DELIVERABLES

### Phase 1: Topic Circumference (this brainstorm)

Produce a structured analysis covering:

1. **PERIMETER** — What is INSIDE NB-4 vs OUTSIDE? Draw precise borders with NB-2, NB-3, NB-5, NB-6, NB-8.

2. **CLUSTER DESIGN** — Propose 5-7 thematic clusters (following NB-2's A-E pattern). Consider:
   - (A) Corporate Tax (PPh Badan)
   - (B) Personal Income Tax (PPh Orang Pribadi)
   - (C) VAT & Sales Tax (PPN, PPnBM)
   - (D) Withholding Taxes (PPh 21, 23, 26, 4(2))
   - (E) Property-Related Taxes (BPHTB, PBB, capital gains)
   - (F) Tax Administration (NPWP, SPT, e-Filing, tax audit)
   - (G) International Tax (treaties, transfer pricing, CRS)

3. **T0 REGULATIONS** — List ALL Indonesian tax laws that MUST be T0 sources. Key candidates:
   - UU 36/2008 (Pajak Penghasilan — Income Tax, as amended by Cipta Kerja & HPP)
   - UU 42/2009 → UU 7/2021 HPP (PPN/VAT)
   - UU 7/2021 (Harmonisasi Peraturan Perpajakan — HPP, the tax omnibus)
   - UU 28/2007 → UU 7/2021 (KUP — General Tax Provisions)
   - PP-level implementing regulations
   - PMK (Peraturan Menteri Keuangan) — ministerial finance regulations

4. **T2-T4 SOURCES** — Ministerial regulations, DJP circulars, social accounts to monitor

5. **GAP ANALYSIS** — What is completely missing from the 9 seed sources?

6. **CROSS-DOMAIN RULES** — Exactly how NB-4 interfaces with NB-3 (company), NB-5 (property), NB-2 (visa/residency)

7. **CAPACITY MODEL** — Target source count per tier and per cluster

### Phase 2 (later): Population plan following NB-2's 7-step method

---

## CRITICAL WARNINGS

- **NEVER guess Indonesian tax rates or thresholds** — they change frequently. Always cite source.
- **UU 7/2021 (HPP)** amended multiple earlier tax laws — verify which provisions are current.
- **PP 55/2022** (implementing HPP) is a critical regulation — check if further updated.
- **Tax residency** (183-day rule) creates a border between NB-2 (visa) and NB-4 (tax). Rule: NB-2 owns visa/stay duration, NB-4 owns tax consequences of residency status.
- **NPWP registration** creates a border between NB-3 (company setup) and NB-4 (tax). Rule: NB-3 owns the registration step during company formation, NB-4 owns what happens after (filing, rates, obligations).
- **Bali Zero's PricingTool** — government tax rates (PNBP, BPHTB rates) belong in NB-4 as reference. Bali Zero service prices for tax consulting belong ONLY in PricingTool, NEVER in NB-4.

---

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

- GR 28/2025 replaced PP 5/2021 for business licensing
- BKPM Regulation 5/2025 is the implementing regulation
- 7 clusters (A-G): PT PMA, PT Lokal/CV, Licensing/KBLI, Amendments, Compliance, Sector-Specific, Dissolution
- Licensing is the largest cluster (18-22 sources) with 6 sub-categories
- Perpres 14/2024 updated the Positive Investment List
- BPS 7/2025 updated the KBLI catalog

---

_Prompt prepared by Claude Opus 4.6 — NLM Pipeline Architect, 2026-03-29_

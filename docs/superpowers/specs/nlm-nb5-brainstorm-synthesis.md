# NB-5: Property & Real Estate Indonesia — Mega Synthesis

> **Author:** Claude Opus 4.6 (NLM Pipeline Architect — synthesizing role)
> **Date:** 2026-03-29
> **Inputs:** 3 parallel brainstorm reports:
>
> - `nlm-nb5-brainstorm-gemini-search.md` (515 lines, 67 sources identified)
> - `nlm-nb5-brainstorm-reasoning.md` (~650 lines, decision tree + 25 query templates)
> - `nlm-nb5-brainstorm-ops.md` (~600 lines, pipeline integration + risk register)
>   **Status:** BRAINSTORM COMPLETE — ready for Phase 2 (Population Plan)

---

## 0. CRITICAL DISCOVERY: PP 103/2015 IS REVOKED

**All 3 agents converged on this:** PP 103/2015 was **REVOKED** by PP 18/2021, not amended. The brainstorm prompt listed it as a T0 candidate — it must be demoted to T0-HISTORICAL (referenced but not current law).

Key implications:

- Hak Pakai and HGB durations changed from **70 years (30+20+20)** to **80 years (30+20+30)** under PP 18/2021
- PP 40/1996 also REVOKED by PP 18/2021
- Implementing Permen (13/2016, 29/2016) also REVOKED by Permen ATR/BPN 18/2021
- UU 11/2020 was itself superseded by **UU 6/2023** (Cipta Kerja final form via Perpu 2/2022)

**The brainstorm prompt's T0 list needs correction.** See §2 below.

---

## 1. CONSENSUS: PERIMETER

All 3 reports converge on identical borders. No contradictions.

### INSIDE NB-5 (15 topics)

| #   | Topic                                                                     | Key Regulations                     |
| --- | ------------------------------------------------------------------------- | ----------------------------------- |
| 1   | Land rights hierarchy (Hak Milik, HGB, Hak Pakai, HGU, Hak Sewa, HPL)     | UU 5/1960, PP 18/2021               |
| 2   | Foreign ownership structures (Hak Pakai direct, PT PMA+HGB, Lease, PPJB)  | PP 18/2021, UU 25/2007              |
| 3   | Nominee arrangements — risks and illegality                               | UU 5/1960 Art.26, Perda Bali 4/2026 |
| 4   | Transaction process (due diligence → PPAT → AJB → BPN)                    | PP 24/1997, Permen ATR/BPN 18/2021  |
| 5   | Title verification and encumbrances                                       | PP 18/2021, UU 4/1996               |
| 6   | Development permits (PBG, SLF, SBKBG)                                     | UU 28/2002, PP 16/2021              |
| 7   | Zoning and spatial planning (RTRW, RDTR, KKPR)                            | UU 26/2007, Perda Bali 2/2023       |
| 8   | Environmental permits for construction (AMDAL, UKL-UPL, SPPL)             | PP 22/2021                          |
| 9   | Bali-specific: Perda 3/2026 coastal, Perda 4/2026 land conversion/nominee | Provincial law                      |
| 10  | Strata title / apartments (HMSRS)                                         | UU 20/2011, PP 18/2021              |
| 11  | Disputes, fraud, land mafia                                               | Case law, enforcement data          |
| 12  | Awig-awig customary land (framework only, not catalog)                    | Perda Bali 4/2019 (Desa Adat)       |
| 13  | Government fee schedule (BPHTB rates, BPN fees, notary tariffs)           | Reference data                      |
| 14  | Lease structuring (Sewa contracts)                                        | PP 44/1994, KUH Perdata             |
| 15  | Property as collateral (Hak Tanggungan)                                   | UU 4/1996                           |

### OUTSIDE NB-5

| Topic                                              | Owner            | Border Rule                                                   |
| -------------------------------------------------- | ---------------- | ------------------------------------------------------------- |
| PT PMA formation process                           | **NB-3**         | NB-3 = company setup; NB-5 = property acquisition via company |
| KBLI selection and OSS-RBA licensing               | **NB-3**         | NB-5 references KBLI 68110/55193 but NB-3 owns                |
| Tax rates, calculations, filing                    | **NB-4**         | NB-5 identifies tax triggers; NB-4 owns mechanics             |
| Ongoing operational compliance (post-construction) | **NB-6**         | NB-5 = getting permit; NB-6 = maintaining permit              |
| Residential lifestyle, neighborhoods               | **NB-8**         | NB-5 = legal structure; NB-8 = living experience              |
| Bali Zero service prices                           | **PricingTool**  | NEVER in NB-5                                                 |
| Market property prices                             | **OUT OF SCOPE** | NB-5 tracks NJOP only, not market prices                      |

### Cross-Domain Interface Contracts (14 rules from Reasoning)

**NB-3 ↔ NB-5 (4 rules):**

1. "PT PMA acquires or holds land rights" = NB-5. "Setting up a PT PMA" = NB-3.
2. KBLI 68xx for property: NB-3 lists codes, NB-5 explains why they're needed for property.
3. Minimum PMA capital: NB-3. Minimum property value for WNA: NB-5.
4. Environmental permits for construction: NB-5 (as development step). For business licensing: NB-3.

**NB-4 ↔ NB-5 (5 rules):**

1. "What tax rate?" = NB-4. "When in the purchase do I pay?" = NB-5.
2. NJOP as tax base: NB-4. NJOP as due diligence reference: NB-5.
3. Capital gains circumstance: NB-5. Capital gains calculation: NB-4.
4. Tax costs in ownership structure comparison: NB-5 (references NB-4 rates).
5. NB-5 NEVER hardcodes tax rates — always references NB-4.

**NB-6 ↔ NB-5 (3 rules):**

1. Initial PBG/SLF acquisition = NB-5. SLF renewal = NB-6.
2. Renovation requiring PBG = NB-5 (same regulatory framework as new construction).
3. Change of use (residential → commercial): zoning question = NB-5; operational compliance = NB-6.

**NB-8 ↔ NB-5 (2 rules):**

1. "Where should I live and how much is rent?" = NB-8. "How to legally secure a 25-year lease?" = NB-5.
2. Mixed-use (live + Airbnb): legal structure = NB-5, lifestyle = NB-8, business license = NB-3.

---

## 2. CONSENSUS: T0 REGULATIONS (15 confirmed)

Search confirmed 15 T0 regulations. **3 from the original prompt are REVOKED:**

### Active T0 (15)

| #   | Regulation     | Title                          | Status                        | Key for NB-5                                                                        |
| --- | -------------- | ------------------------------ | ----------------------------- | ----------------------------------------------------------------------------------- |
| 1   | **UU 5/1960**  | UUPA (Basic Agrarian Law)      | ACTIVE (foundation)           | Pasal 20-43 (all land rights), Art.21 (WNA exclusion), Art.26 (nominee prohibition) |
| 2   | **UU 6/2023**  | Cipta Kerja (Omnibus — final)  | ACTIVE                        | Replaced UU 11/2020; enabled PP 18/2021 implementing regulations                    |
| 3   | **PP 18/2021** | Land Rights + Registration     | ACTIVE (THE key regulation)   | HGB/HP 30+20+30=80yr; revoked PP 40/1996, PP 103/2015; foreign apartment rights     |
| 4   | **PP 28/2025** | Risk-Based Business Licensing  | ACTIVE                        | KKPR zoning conformity; OSS for property businesses                                 |
| 5   | **PP 16/2021** | Building Law Implementation    | ACTIVE                        | PBG replaces IMB; SLF; SBKBG                                                        |
| 6   | **PP 22/2021** | Environmental Protection       | ACTIVE                        | AMDAL/UKL-UPL/SPPL thresholds                                                       |
| 7   | **PP 44/1994** | House Occupation (Lease)       | ACTIVE                        | Hak Sewa legal basis; no statutory max term                                         |
| 8   | **UU 28/2002** | Building Law                   | ACTIVE (amended by UU 6/2023) | PBG/SLF foundation                                                                  |
| 9   | **UU 26/2007** | Spatial Planning               | ACTIVE (amended by UU 6/2023) | RTRW/RDTR framework                                                                 |
| 10  | **UU 20/2011** | Apartment/Strata Title         | ACTIVE (amended by UU 6/2023) | HMSRS; foreigner apartment rights                                                   |
| 11  | **UU 18/2025** | Tourism Law (3rd amendment)    | ACTIVE (Oct 2025)             | Villa licensing, accommodation regulation                                           |
| 12  | **UU 25/2007** | Investment Law                 | ACTIVE                        | PT PMA legal basis; foreign investment framework                                    |
| 13  | **UU 40/2007** | Company Law                    | ACTIVE                        | PT PMA governance, director liability                                               |
| 14  | **UU 4/1996**  | Hak Tanggungan (Mortgage)      | ACTIVE                        | Encumbrances, collateral rights over land                                           |
| 15  | **UU 1/2022**  | Central-Local Fiscal Relations | ACTIVE                        | BPHTB framework (property acquisition tax)                                          |

### REVOKED (do NOT include as active — reference as historical context only)

| Regulation                        | Revoked By                 | Note                                                       |
| --------------------------------- | -------------------------- | ---------------------------------------------------------- |
| PP 103/2015 (Foreign Hak Pakai)   | PP 18/2021                 | Provisions absorbed                                        |
| PP 40/1996 (HGU, HGB, Hak Pakai)  | PP 18/2021                 | Fully superseded                                           |
| PP 24/1997 (Land Registration)    | PP 18/2021 (partial)       | Some procedural aspects remain; use Permen 16/2021 instead |
| UU 11/2020 (Original Cipta Kerja) | UU 6/2023 via Perpu 2/2022 | Use UU 6/2023 as T0, not UU 11/2020                        |

---

## 3. CONSENSUS: 7 CLUSTERS (validated)

All 3 agents validated the 7-cluster architecture. Reasoning rated coherence 7-9/10 across clusters.

| Cluster | Name                           | Sources Target | Coherence | Overlap Risk         | Key Distinguisher                       |
| ------- | ------------------------------ | -------------- | --------- | -------------------- | --------------------------------------- |
| **A**   | Land Rights & Title            | 8-10           | 9/10      | LOW                  | Definitional — what rights ARE          |
| **B**   | Foreign Ownership Structures   | 10-14          | 9/10      | MEDIUM               | Which rights FOREIGNERS can use         |
| **C**   | Transaction Process            | 8-12           | 8/10      | MEDIUM-LOW           | HOW to execute a transaction            |
| **D**   | Development & Construction     | 8-12           | 7/10      | **HIGH** (NB-3/NB-6) | Permits as part of PROPERTY development |
| **E**   | Disputes & Protection          | 6-8            | 8/10      | LOW                  | What goes WRONG                         |
| **F**   | Bali-Specific                  | 8-10           | 9/10      | LOW                  | LOCAL regulations overlay               |
| **G**   | Regulatory Framework & Updates | 6-8            | N/A       | LOW                  | Meta-cluster for changes                |

### Cluster D Overlap Mitigation (flagged by Reasoning)

Cluster D has the highest overlap risk with NB-3 and NB-6. Resolution:

- **NB-5 Cluster D** = permits as PROPERTY DEVELOPMENT step ("I have land, what permits to build?")
- **NB-3 Cluster C** = permits as BUSINESS LICENSING step ("I'm starting a hotel, what licenses?")
- **NB-6** = permits as ONGOING OBLIGATION ("My SLF is expiring, what to renew?")
- Same regulation text (UU 28/2002, PP 28/2025), different QUERY CONTEXT and CLAIM FOCUS.

---

## 4. FOREIGNER OWNERSHIP DECISION TREE (from Reasoning)

Key structural element — should become **MD-5: Decision Guide** in NB-5.

```
FOREIGN NATIONAL → PURPOSE?
├── PERSONAL RESIDENCE
│   ├── Has KITAS/KITAP? → HAK PAKAI (direct, 1 property, min value threshold)
│   └── No KITAS? → LEASE only (no ownership possible)
├── INVESTMENT/RENTAL
│   ├── Single villa → PT PMA+HGB or Long-term Lease
│   ├── Multiple/development → PT PMA+HGB only
│   └── Hospitality → PT PMA+HGB + tourism license → NB-3
├── JUST LEASE → Sewa contract (any foreigner, no visa requirement)
├── LAND BANKING → Lease safest (Hak Pakai/HGB have "use" requirement)
├── NOMINEE? → ⚠️ ILLEGAL (UU 5/1960 Art.26 + Perda Bali 4/2026 = criminal)
└── EXISTING PROPERTY → extend/renew/sell/collateral/dispute
```

Every terminal node resolves within NB-5 or links to NB-2/3/4/6.

---

## 5. PIPELINE INTEGRATION (from Ops)

### Schedule

| Day | 01:00 Slot | 02:25 Slot | Notes         |
| --- | ---------- | ---------- | ------------- |
| Mon | NB-2       | NB-3       | Fresh week    |
| Tue | NB-2       | **NB-5**   |               |
| Wed | NB-2       | NB-4       |               |
| Thu | NB-2       | **NB-5**   | NB-2 runs L3  |
| Fri | NB-2       | NB-3       | Consolidation |

**NB-5: 2 days/week, 4 queries/week, ~17 queries/month.**

Rationale: Property law changes slower than immigration. UU 5/1960 is from 1960. Changes come from implementing regulations quarterly, not weekly.

### Phasing

- **Phase 1 (now):** NB-5 does NOT run. Only NB-2 live.
- **Phase 2 (~Month 2):** NB-3 + NB-4 join pipeline.
- **Phase 3 (~Month 3+):** NB-5 joins at 02:25 Tue/Thu.

### Scraper Handoff

Separate file: `latest_nb5.json` (avoids timing conflict — NB-5 may finish at 03:10, after scraper starts at 03:00). Scraper reads NB-2 handoff at 03:00; NB-5 handoff available next day. ~10 lines of code change in `nlm_enricher.py`.

---

## 6. SOURCE MANAGEMENT (Ops + Search merged)

### Capacity: 70 ACTIVE cap (same as NB-2)

| Category          | Budget  | Composition                                                                                                   |
| ----------------- | ------- | ------------------------------------------------------------------------------------------------------------- |
| Canonical (T0-T2) | 22      | 12 T0 + 5 T1 + 5 T2                                                                                           |
| Working (T3-T5)   | 25      | Bali-specific 10-15, national 8-12, analysis 3-5                                                              |
| Master Digests    | 5-6     | MD-1 Change Log, MD-2 Ops Status, MD-3 Cross-Domain, MD-4 Open Questions, MD-5 Decision Guide, MD-6 Awig-awig |
| Reference         | 4-6     | Title hierarchy, fee schedule, zoning summary, ownership matrix                                               |
| Headroom          | ~8      | For ingest spikes                                                                                             |
| **Steady state**  | **~62** |                                                                                                               |

### SVS Weight Adaptations

| Factor         | NB-2 | NB-5     | Why                                                  |
| -------------- | ---- | -------- | ---------------------------------------------------- |
| Tier Authority | 0.25 | **0.30** | Property is more regulation-dependent                |
| Uniqueness     | 0.15 | **0.20** | More source overlap (everyone writes about nominees) |
| Freshness      | 0.20 | **0.15** | Property regs change less often                      |
| Claims         | 0.25 | 0.20     | Fewer sources but denser per regulation              |
| Citations      | 0.15 | 0.15     | Same                                                 |

**New: Geo Bonus** (+0.10 for Bali-specific sources within existing 0.15 BONUS cap).

### Language Distribution

| Language         | NB-2 | NB-5                                      |
| ---------------- | ---- | ----------------------------------------- |
| Bahasa Indonesia | 60%  | **70%** (local regs exist ONLY in Bahasa) |
| English          | 30%  | 20%                                       |
| Bridge           | 10%  | 10%                                       |

---

## 7. T4 SOCIAL MONITOR (Ops + Search merged)

### 10 Accounts (from Search), Frequency from Ops

| #   | Account                        | Platform  | Priority | Frequency |
| --- | ------------------------------ | --------- | -------- | --------- |
| 1   | @kementerian.atrbpn            | Instagram | CRITICAL | 12h       |
| 2   | @kem_atrbpn                    | X/Twitter | CRITICAL | 12h       |
| 3   | @kanwil.bpn.bali               | Instagram | HIGH     | 12h       |
| 4   | @kantahkabbadung               | Instagram | HIGH     | 12h       |
| 5   | @ditjenpenataanagraria         | Instagram | HIGH     | 12h       |
| 6   | @ditjentataruang               | Instagram | HIGH     | 12h       |
| 7   | tarubali.baliprov.go.id        | Web       | CRITICAL | 12h       |
| 8   | hukumonline.com/tag/pertanahan | RSS/Web   | HIGH     | 12h       |
| 9   | peraturan.bpk.go.id            | Web       | HIGH     | daily     |
| 10  | jdih.baliprov.go.id            | Web       | MEDIUM   | daily     |
| 11  | Kementerian ATR/BPN            | YouTube   | HIGH     | daily     |
| 12  | Ditjen SPPR ATR/BPN            | YouTube   | HIGH     | daily     |

**YouTube channels** (official ministry video — policy announcements, regulation explanations, sosialisasi):

- `youtube.com/c/KementerianATRBPN` — National land agency official channel
- `youtube.com/@DitjenSPPRATRBPN` — Directorate General for Spatial Planning & Land Affairs

SVS threshold: 0.35 (same as NB-2). Fetch: every 12h (not 6h — property posts less frequently). YouTube: daily check (video transcripts via T4 pipeline).

---

## 8. FAILURE MODES (4 NB-5-specific + NB-2 inherited)

| CB           | Trigger                       | Threshold                              | Open Duration      | Mitigation                                       |
| ------------ | ----------------------------- | -------------------------------------- | ------------------ | ------------------------------------------------ |
| **CB-LOCAL** | Local reg sources unavailable | 5 consecutive zero-result queries      | 72h → 7d           | Pre-upload Perda as text; JDIH BPK mirror        |
| **CB-AWIG**  | N/A (known permanent gap)     | N/A                                    | Permanent          | Framework coverage + "verify locally" disclaimer |
| **CB-PRICE** | N/A (scope exclusion)         | N/A                                    | N/A                | Track NJOP only; market prices = out of scope    |
| **CB-BPN**   | BPN website down              | 5 failures to import from \*.bpn.go.id | Standard CB-SOURCE | Text-uploaded T0 are BPN-independent             |

**Nominee content guardrail:** Hard-coded — all nominee claims MUST include `dispute_risk` category and reference UU 5/1960 illegality. Go/No-Go test verifies no setup instructions.

---

## 9. TESTING PROTOCOL (8-phase, adapted from NB-2)

### 5 Test Queries

| Query                                                | Expected                           | Pass Criteria                       |
| ---------------------------------------------------- | ---------------------------------- | ----------------------------------- |
| "Hak Pakai untuk WNA berdasarkan PP 18/2021"         | Cites PP 18/2021, 30+20+30 formula | Confidence ≥0.60, T0 cited          |
| "Prosedur pendaftaran tanah di BPN untuk HGB PT PMA" | BPN registration, PPAT, AJB        | Mentions PPAT and AJB               |
| "What are the risks of nominee arrangements?"        | Warns illegality, UU 5/1960        | Does NOT provide setup instructions |
| "Zonasi RTRW Bali kawasan pariwisata"                | Tourism zones, green zones         | Mentions RTRW restrictions          |
| "Perbedaan Hak Pakai dan HGB"                        | Accurate comparison                | 2+ T0 sources cited                 |

### 10 Claim Categories

LEGAL_FRAMEWORK · OWNERSHIP_STRUCTURE · REGISTRATION_PROCESS · ZONING_REGULATION · TAX_TRIGGER · PRICE_THRESHOLD · CONSTRUCTION_PERMIT · DISPUTE_RISK · COMPLIANCE_DEADLINE · ENFORCEMENT_ACTION

### Go/No-Go Criteria (9)

| Criterion                         | Threshold             | Blocking |
| --------------------------------- | --------------------- | -------- |
| Pre-flight (Phase 0)              | 12/12                 | YES      |
| ACTIVE sources (Phase 1)          | ≥15                   | YES      |
| Query confidence median (Phase 2) | ≥0.55                 | YES      |
| Claims extracted (Phase 3)        | ≥15                   | YES      |
| ILM on consolidation (Phase 4)    | <0.10                 | YES      |
| Cross-domain refs (Phase 5)       | ≥2                    | NO       |
| Nominee query safety (Phase 2)    | No setup instructions | YES      |
| Pipeline dry run (Phase 7)        | 5/5 days              | YES      |
| Handoff JSON validates            | Valid schema          | YES      |

---

## 10. COST MODEL

| Item                                         | Cost                   |
| -------------------------------------------- | ---------------------- |
| Monthly incremental (NLM subscription share) | ~$2/month              |
| One-time setup                               | ~11 hours Claude Code  |
| Claim extraction                             | $0 (local Qwen 3.5:9b) |
| T4 monitoring infra                          | $0 (existing)          |

---

## 11. RISK REGISTER (Top 5)

| #   | Risk                                | L    | I    | Mitigation                                                    |
| --- | ----------------------------------- | ---- | ---- | ------------------------------------------------------------- |
| 1   | Perda Bali text unavailable online  | HIGH | HIGH | Pre-upload as text; Hukumonline proxy; BZ legal team scanning |
| 2   | BPN website unreliable              | HIGH | MED  | Text-uploaded T0; JDIH BPK mirror; CB-SOURCE                  |
| 3   | Nominee content liability           | MED  | HIGH | Hard-coded guardrail; Go/No-Go test; risk-only framing        |
| 4   | Scheduling conflicts with NB-3/NB-4 | MED  | MED  | 2 days/week flexible; can start 1 day/week                    |
| 5   | Awig-awig false confidence gap      | LOW  | HIGH | Permanent MD-4 flag; standing disclaimer; "verify locally"    |

---

## 12. KEY CORRECTIONS TO COMMON MISCONCEPTIONS (from Search)

| Misconception                                        | Reality                                                  | Source               |
| ---------------------------------------------------- | -------------------------------------------------------- | -------------------- |
| "Hak Pakai lasts 70 years (30+20+20)"                | **80 years (30+20+30)** post PP 18/2021                  | ABNR analysis        |
| "HGB lasts 70 years"                                 | **80 years (30+20+30)**                                  | PP 18/2021           |
| "PT PMA requires IDR 10B paid-up"                    | **IDR 2.5B** since BKPM 5/2025                           | Bali Property Rules  |
| "Leasehold max is 99 years"                          | **No statutory maximum** (PP 44/1994)                    | Market practice only |
| "PP 103/2015 is current foreign property regulation" | **REVOKED by PP 18/2021**                                | ABNR analysis        |
| "Nominee agreements are gray area"                   | **Explicitly illegal** + criminal in Bali (Perda 4/2026) | UU 5/1960 + Perda    |

---

## 13. DIVERGENCES BETWEEN AGENTS (resolved)

| Topic              | Search               | Reasoning                           | Ops                 | Resolution                                                                     |
| ------------------ | -------------------- | ----------------------------------- | ------------------- | ------------------------------------------------------------------------------ |
| ACTIVE cap         | 55-65                | 75                                  | 70                  | **70** (NB-2 standard; NLM constraint is signal, not API limit)                |
| HP/HGB duration    | 80yr (30+20+30)      | 70yr (30+20+20)                     | N/A                 | **80yr** — Search is correct, citing PP 18/2021 Art.37 and ABNR                |
| Cluster count      | 7 (A-G)              | 7 (A-G, renamed F→Disputes, G→Bali) | 7                   | **7 as proposed** — Search naming is better (E=Disputes, F=Bali, G=Regulatory) |
| T4 fetch frequency | 6h                   | N/A                                 | 12h                 | **12h** — Ops rationale is sound (property posts weekly, not daily)            |
| Land prices        | NJOP only, no market | NJOP yes, market no                 | No market prices    | **Consensus: NJOP reference only, no market prices**                           |
| Awig-awig          | Framework only       | Framework + disclaimer              | Known permanent gap | **Consensus: framework + disclaimer + MD-4 permanent flag**                    |

### Duration Correction (IMPORTANT)

Reasoning's decision tree shows 70-year durations in several places. **This must be corrected to 80 years** per PP 18/2021 before the decision tree is used as MD-5. Search's grounded finding (ABNR law firm confirmation) takes precedence.

---

## 14. 2025-2026 REGULATORY LANDSCAPE (from Search)

### Top 10 Changes

| #   | Change                                                | Date                          | Impact                                          |
| --- | ----------------------------------------------------- | ----------------------------- | ----------------------------------------------- |
| 1   | PP 28/2025 (Business licensing overhaul)              | 2025                          | KKPR zoning conformity required                 |
| 2   | BKPM 5/2025 (PT PMA capital IDR 10B→2.5B)             | 2025                          | 75% reduction in property investment barrier    |
| 3   | Permen ATR/BPN 5/2025, 7/2025, 9/2025                 | May-Sep 2025                  | Land authority restructured 3x in one year      |
| 4   | UU 18/2025 (Tourism Law)                              | Oct 2025                      | Villa licensing, OTA enforcement                |
| 5   | **Perda Bali 3/2026** (Coastal protection)            | Feb 24, 2026                  | Sempadan pantai; demolition orders              |
| 6   | **Perda Bali 4/2026** (Land conversion + nominee ban) | Feb 24, 2026                  | **Criminal sanctions: 5yr prison, IDR 1B fine** |
| 7   | Bali construction moratorium                          | 2025-2026                     | New PBG restricted in many areas                |
| 8   | ATR/BPN certificate digitalization                    | 2026                          | Paper→digital certificate conversion mandated   |
| 9   | Constitutional Court 198/PUU-XXIII/2025               | 2025                          | Non-residential apartment gap                   |
| 10  | PP 18/2021 consolidated land reform                   | 2021 (still most significant) | Revoked 3 major PPs; extended durations         |

---

## 15. NEXT STEPS: Phase 2 Population Plan

The brainstorm is complete. To proceed to population:

### Immediate (before pipeline)

1. **Correct brainstorm prompt** — Update PP 103/2015 status, UU 11/2020→6/2023, duration 70→80yr
2. **Inspect NB-5 notebook** — List actual 6 seed sources via NLM API
3. **Upload 12 T0 regulations** as text sources to NB-5 (BPN-independent)
4. **Create T4 config** — `t4_nb5_config.json` with 10 accounts

### Phase 2 Design (following NB-2 7-step method)

| Step                    | Status                               | Blocking   |
| ----------------------- | ------------------------------------ | ---------- |
| 1. Query Design         | 25 templates DONE (Reasoning)        | NO — ready |
| 2. Sequencing           | Schedule DONE (Ops)                  | NO — ready |
| 3. Quality Verification | Claim categories DONE, SVS adapted   | NO — ready |
| 4. Source Management    | Lifecycle + capacity DONE            | NO — ready |
| 5. Scraper Integration  | Handoff design DONE (~10 LOC change) | NO — ready |
| 6. Failure Modes        | 4 CB defined, nominee guardrail DONE | NO — ready |
| 7. Testing Protocol     | 8-phase adapted, Go/No-Go DONE       | NO — ready |

### Dependency

NB-5 pipeline activation is gated on:

- NB-3 population complete (Phase 2)
- NB-4 brainstorm dispatched and synthesized (prompt exists, not yet dispatched)
- Pro OpenClaw cron slot at 02:25 Tue/Thu configured

---

_Synthesis by Claude Opus 4.6 — NLM Pipeline Architect, 2026-03-29_
_3 agents × ~500 lines each = ~1,500 lines input → 400 lines synthesis_
_Token investment: ~367K tokens across 3 agents (search 152K + reasoning 98K + ops 118K)_

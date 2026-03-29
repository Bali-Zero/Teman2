# NB-5: Property & Real Estate — Operational Discipline Review

> **Role:** Operational Discipline Reviewer
> **Date:** 2026-03-29
> **Author:** Claude Opus 4.6 (1M context)
> **Input:** NB-5 brainstorm prompt + NB-2 pipeline specs (Steps 2, 4, 5, 6, 7)
> **Question:** Can NB-5 actually be built, operated, and maintained within existing infrastructure?

---

## 1. PIPELINE INTEGRATION — Scheduling NB-5 in the Nightly Window

### 1.1 Current Nightly Timeline (WITA)

```
01:00-02:20   NB-2 Immigration (LIVE, Mon-Fri, 2 queries/day)
02:20-03:00   Buffer
03:00-03:30   Intel Scraper (Pro, OpenClaw)
04:30-05:00   NB-1 Code Refresh
05:00         KB Ingest (Air cron)
```

### 1.2 Pending Notebooks (Queue)

| NB   | Status                                  | Est. Window | Priority    |
| ---- | --------------------------------------- | ----------- | ----------- |
| NB-3 | Brainstorm complete, population pending | 50-70 min   | HIGH (next) |
| NB-4 | Brainstorm prompt ready                 | 50-70 min   | HIGH        |
| NB-5 | Brainstorm target (this document)       | 50-70 min   | MEDIUM      |

### 1.3 Sequencing Conflict Analysis

**Problem:** NB-2 occupies 01:00-02:20. Each additional notebook needs ~70 min (signal collection + 2 queries + consolidation + handoff). The 01:00-03:00 window before the scraper is exactly 120 min — enough for NB-2 alone with buffer, but NOT for NB-2 + another notebook sequentially.

**OpenClaw cron capacity constraints:**

- Pro runs the NLM pipeline via OpenClaw/launchd at 01:10 WITA
- Each NLM `research_start(mode=deep)` takes 15-20 min per query
- NLM API does not document explicit rate limits, but concurrent requests to the same notebook are not supported
- Different notebooks CAN be queried in parallel (separate NLM API sessions)

### 1.4 Proposed Schedule — Staggered Multi-Notebook

**Phase 1 (Now → NB-3 population complete):** NB-5 does NOT run. Only NB-2 in production.

**Phase 2 (NB-3 + NB-4 live, ~Month 2):** Two-notebook nightly run.

**Phase 3 (NB-5 joins, ~Month 3+):** Three-notebook nightly run.

```
PHASE 3 SCHEDULE (Mon-Fri):

01:00  NB-2 START (immigration — highest priority, most dynamic)
01:10  NB-2 Query 1 (L1 monitoring)
01:30  NB-2 Query 2 (L2 comparative)
01:55  NB-2 Consolidation + Handoff
02:20  NB-2 COMPLETE

02:25  NB-5 START (property — lower velocity than immigration)
02:30  NB-5 Query 1 (L1 monitoring)
02:50  NB-5 Query 2 (L2 comparative, OR skip if budget pressure)
03:10  NB-5 Consolidation + Handoff
03:25  NB-5 COMPLETE

03:00  INTEL SCRAPER starts (note: overlap with NB-5 tail)
       Scraper reads NB-2 handoff immediately (latest.json written at 02:10)
       NB-5 handoff written at 03:10 — scraper must re-check or read on next cycle
```

**Where do NB-3/NB-4 go?** Alternate days:

| Day     | 01:00 Slot | 02:25 Slot      | Notes                 |
| ------- | ---------- | --------------- | --------------------- |
| **Mon** | NB-2       | NB-3 (Company)  | Fresh week start      |
| **Tue** | NB-2       | NB-5 (Property) |                       |
| **Wed** | NB-2       | NB-4 (Tax)      |                       |
| **Thu** | NB-2       | NB-5 (Property) | NB-2 runs L3 this day |
| **Fri** | NB-2       | NB-3 (Company)  | Both do consolidation |

**NB-5 runs 2 days/week (Tue, Thu).** This yields:

- 2 days x 2 queries = 4 queries/week
- 4 queries x 4.3 weeks = ~17 queries/month

**Rationale for 2 days/week:** Property regulation changes less frequently than immigration. Indonesian property law (UU 5/1960 as foundation) is stable. Changes come from implementing regulations (PP, Permen ATR/BPN) which change quarterly, not weekly. Government gazette (JDIH) publishes property-related regulations far less often than immigration ones.

### 1.5 Scraper Handoff Overlap

The intel scraper starts at 03:00, but NB-5 may not finish until 03:25. Solutions:

**Option A (recommended):** NB-5 writes its handoff to a separate file:

```
~/.agent/decisions/nlm_to_scraper/
├── latest.json           # NB-2 (written 02:10, used by scraper at 03:00)
├── latest_nb5.json       # NB-5 (written 03:10, used by scraper NEXT day)
└── _metadata.json
```

The scraper reads `latest.json` (NB-2) at 03:00 as today. NB-5's handoff is available for manual use or next day's scraper context. This preserves NB-2's UPSTREAM architecture and avoids making the scraper wait.

**Option B:** Push NB-5 to start at 02:40, accept 1 query/day instead of 2, finish by 03:00. Simpler but less intelligence per run.

**Decision: Option A.** Two handoff files, scraper already has NLMEnricher with triple error boundary. Adding a second file is ~5 lines of code in `load_nlm_handoff()`.

### 1.6 Weekly Budget (Hard Cap)

NB-2 weekly cap: 40 queries/week (currently uses 10-15).

NB-5 proposal: **20 queries/week** (4 queries/day x 2 days/week = 8, plus 12 reserve for breaking news, Friday consolidation, afternoon follow-ups).

Combined weekly NLM API load across all notebooks:

```
NB-2: 10-15 queries/week (live, measured)
NB-3: 4-8 queries/week (projected, 2 days)
NB-4: 4-8 queries/week (projected, 2 days)
NB-5: 4-8 queries/week (projected, 2 days)
---
Total: 22-39 queries/week (within NLM Ultra tier capacity)
```

---

## 2. SOURCE MANAGEMENT PLAN — Adapting NB-2's 6-Stage Lifecycle

### 2.1 Lifecycle (No Changes Needed)

The 6-stage lifecycle (INGEST -> QUARANTINE -> TRIAGE -> ACTIVE -> CONSOLIDATE -> ARCHIVE) applies directly to NB-5. The state machine is domain-agnostic.

### 2.2 SVS Weighting Adaptations

NB-2's SVS formula uses these weights:

| Factor           | NB-2 Weight | NB-5 Proposed | Rationale                                                                                                             |
| ---------------- | ----------- | ------------- | --------------------------------------------------------------------------------------------------------------------- |
| Tier Authority   | 0.25        | **0.30**      | Property law is MORE regulation-dependent. T0 sources matter more.                                                    |
| Claims Extracted | 0.25        | 0.20          | Property claims tend to be denser per source (fewer sources, more substance per regulation).                          |
| Freshness        | 0.20        | **0.15**      | Property regulations change less often. A 90-day old Permen ATR/BPN is still highly relevant.                         |
| Citations        | 0.15        | 0.15          | Unchanged.                                                                                                            |
| Uniqueness       | 0.15        | **0.20**      | Property sources have MORE overlap (everyone writes about nominee risk). Uniqueness matters more for differentiation. |

### 2.3 Geo Factor (Bali-Specific Scoring)

**Key difference from NB-2:** Property law has a massive local component (RTRW, Perda, BPN kabupaten, awig-awig). NB-2 immigration law is 90% national. NB-5 property law is perhaps 60% national, 40% local/Bali.

**Proposal: Add Geo Bonus to SVS** (within the existing 0.15 BONUS cap):

| Condition                                                     | Bonus |
| ------------------------------------------------------------- | ----- |
| Source is Bali-specific regulation (Perda, Pergub, RTRW Bali) | +0.10 |
| Source covers Bali BPN office practices                       | +0.05 |
| Source is generic national without Bali context               | +0.00 |

This biases retention toward Bali-specific sources, which are harder to find and more relevant to clients.

### 2.4 Language Distribution

NB-2 targets 60% Bahasa, 30% English, 10% bridge queries.

NB-5 adjustment:

- **70% Bahasa** for queries — local regulations (Perda, RTRW) exist ONLY in Bahasa
- **20% English** — for expat-oriented analysis and comparison articles
- **10% bridge** — mixed queries for BPN procedures

Source language distribution in ACTIVE set:

- T0-T2 (regulations): ~95% Bahasa (primary text of law)
- T3-T4 (enforcement/social): ~70% Bahasa
- T5 (press): ~50/50 (expat media in English)

### 2.5 ACTIVE Cap

**NB-2 cap: 70.** NB-5 proposed: **70 (same).**

Rationale: NLM Ultra allows 600 sources per notebook. The 70 cap is about signal-to-noise, not NLM limits. Property has slightly fewer active regulations than immigration, but the local component (Perda, zoning, BPN circulars) compensates. 70 is appropriate.

### 2.6 Budget Allocation (70 ACTIVE)

```
+----------------------------------------------------------------+
|                    70 ACTIVE SOURCE BUDGET (NB-5)               |
|                                                                 |
|  +-----------------------+  +------------------------------+    |
|  |  CANONICAL: 18-25     |  |  WORKING: 20-30              |    |
|  |  (regulations, laws)  |  |  (news, analysis, social)    |    |
|  |                       |  |                              |    |
|  |  Target: 22           |  |  Target: 25                  |    |
|  |  T0: 8-12 (core laws) |  |  Bali-specific: 10-15       |    |
|  |  T1: 5-8 (Permen)     |  |  National property: 8-12    |    |
|  |  T2: 3-5 (Perda Bali) |  |  Expat analysis: 3-5        |    |
|  +-----------------------+  +------------------------------+    |
|                                                                 |
|  +-----------------------+  +------------------------------+    |
|  |  MASTER DIGEST: 4-6   |  |  REFERENCE: 4-6              |    |
|  |  (synthesized docs)   |  |  (standing tables, guides)   |    |
|  |                       |  |                              |    |
|  |  MD-1 Change Log      |  |  Land title hierarchy        |    |
|  |  MD-2 Ops Status      |  |  BPHTB/PBB rate table        |    |
|  |  MD-3 Cross-Domain    |  |  Bali zoning summary         |    |
|  |  MD-4 Open Questions  |  |  Foreign ownership matrix    |    |
|  |  MD-5 Price Rules *   |  |                              |    |
|  +-----------------------+  +------------------------------+    |
|                                                                 |
|  HEADROOM: ~8 slots (11%) for ingest spikes                    |
|  IDEAL STEADY STATE: ~62 sources                               |
+----------------------------------------------------------------+

* MD-5 Price Rules: Government fee schedule (BPHTB rates, BPN tariffs).
  Bali Zero service prices NEVER in NB-5 — PricingTool only.
```

### 2.7 Staleness Half-Lives (Property-Adapted)

| Source Type          | NB-2 Half-Life | NB-5 Half-Life | Rationale                                                                |
| -------------------- | -------------- | -------------- | ------------------------------------------------------------------------ |
| LAW_IN_FORCE         | Infinite       | Infinite       | Same — active laws never decay                                           |
| LAW_SUPERSEDED       | 30 days        | **60 days**    | Property laws get superseded less often; old law context valuable longer |
| REGULATION_CIRCULAR  | 90 days        | **120 days**   | BPN circulars remain relevant longer than immigration circulars          |
| OFFICIAL_PORTAL      | 60 days        | 60 days        | Same                                                                     |
| OFFICIAL_SOCIAL      | 30 days        | 30 days        | Same                                                                     |
| NEWS_ARTICLE         | 15 days        | **20 days**    | Property news decays slightly slower (fewer updates per week)            |
| ANALYSIS_REPORT      | 120 days       | **180 days**   | Property analysis (e.g., zoning study) stays relevant much longer        |
| MASTER_DIGEST        | 180 days       | 180 days       | Same                                                                     |
| **PRICE_DATA** (new) | N/A            | **30 days**    | Land/property price data is volatile; short half-life if tracked at all  |
| **PERDA_BALI** (new) | N/A            | **180 days**   | Local regulations change infrequently                                    |

---

## 3. SCRAPER INTEGRATION — NB-5 Handoff

### 3.1 Handoff Architecture

NB-5 follows the identical handoff pattern as NB-2:

- Output file: `~/.agent/decisions/nlm_to_scraper/latest_nb5.json`
- Same JSON schema (`schema_version: "1.0"`, same field names)
- `notebook_id: "nb5_property"`

The NLMEnricher adapter in the scraper (`scripts/nlm_enricher.py`) needs a minor extension:

```python
# Current: reads latest.json (NB-2 only)
# Proposed: reads latest.json + latest_nb5.json, merges findings

def _load_all_handoffs(self) -> list[dict]:
    handoffs = []
    for filename in ["latest.json", "latest_nb5.json"]:
        path = HANDOFF_DIR / filename
        data = self._load_single_handoff(path)
        if data:
            handoffs.append(data)
    return handoffs
```

**Invasion budget:** ~10 lines changed in existing scraper code. Consistent with NB-2's "minimal invasion" principle.

### 3.2 TRS Adaptation for Property

The Topic Relevance Score formula stays the same (0.25 confidence + 0.25 novelty + 0.20 client_impact + 0.15 editorial + 0.15 source_tier + BONUS).

**Property-specific TRS sub-scores:**

- `F_client_impact` for property: segments = unique (property_type, ownership_structure) pairs
  - property_type: villa, land, aparthotel, commercial, agricultural
  - ownership_structure: hak_pakai, hgb_via_pma, lease, nominee

- `F_editorial_value` for property: conditions become:
  - has_deadline (e.g., Hak Pakai extension deadline)
  - has_cross_domain (touches NB-3 company or NB-4 tax)
  - affects_active_clients (existing property holders)
  - has_actionable_rec (concrete next step for client)

### 3.3 NLMEnricher Metadata for NB-5

Additional `nlm_*` fields specific to NB-5:

| Field                     | Type   | Purpose                                                  |
| ------------------------- | ------ | -------------------------------------------------------- |
| `nlm_property_type`       | string | villa / land / commercial / agricultural                 |
| `nlm_ownership_structure` | string | hak_pakai / hgb / lease / nominee / mixed                |
| `nlm_bali_specific`       | bool   | True if finding is Bali-local (not just national)        |
| `nlm_regulation_ref`      | string | Specific regulation number (e.g., "PP 18/2021 Pasal 12") |

These are additive-only (NLMEnricher contract: never modifies existing fields).

---

## 4. FAILURE MODES SPECIFIC TO NB-5

### 4.1 CB-LOCAL: Circuit Breaker for Local Regulation Sources

**Problem:** Perda Bali (provincial regulations) are significantly harder to find online than national regulations. The JDIH Bali database is less complete than JDIH Kemenkumham. Many Perda are only in physical gazette.

**Circuit Breaker Design:**

```
CB-LOCAL (Local Regulation Source)
├── CLOSED: Normal operation, local sources responding
├── Threshold: 5 consecutive queries with 0 local sources found
├── OPEN: Skip Bali-specific queries, fall back to national-only monitoring
│   Duration: 72h
├── HALF_OPEN: Try 1 Bali-specific query
│   Success: Reset to CLOSED
│   Failure: Back to OPEN, extend to 7 days
└── Cascade: If open >14 days → flag MD-3 (Cross-Domain) as STALE for Bali
```

**Mitigation:** Seed NB-5 with known Perda Bali texts as T0/T2 sources (uploaded as text, not URLs). This makes NB-5 resilient to Bali JDIH downtime.

### 4.2 CB-AWIG: Handling Awig-Awig (Unwritten Customary Law)

**Problem:** Awig-awig (Balinese customary village law) affects property in desa adat areas. It is:

- NOT codified in any official database
- Varies per desa adat (1,488 desa adat in Bali)
- NOT enforceable through national courts (enforced by banjar/desa adat)
- Sometimes conflicts with national zoning

**Source Strategy:**

| Approach                        | Feasibility | Action                                                          |
| ------------------------------- | ----------- | --------------------------------------------------------------- |
| Government digitization project | LOW         | Monitor DPRD Bali for any codification effort                   |
| Academic research (journals)    | MEDIUM      | Add 2-3 academic papers on awig-awig and property as T4-T5      |
| Practitioner guides             | HIGH        | Add INI (notary association) guidelines on awig-awig            |
| BZ internal knowledge           | HIGH        | Create MD-6 "Awig-Awig Property Impact" from BZ team experience |

**NB-5 position on awig-awig:** Track the PRINCIPLE that awig-awig exists and affects property transactions (especially in desa adat areas), but do NOT attempt to catalog individual desa rules. Always recommend: "Consult local PPAT and banjar before purchasing land in desa adat areas."

**No circuit breaker needed** — awig-awig is a known gap, not a failure. NB-5 acknowledges the gap explicitly in MD-4 (Open Questions).

### 4.3 CB-PRICE: Land/Property Price Data

**Problem:** Land and property price data in Bali is:

- Extremely volatile (can change 20-30% in a year)
- Not officially published (no government price index for Bali)
- Often unreliable (asking prices vs transaction prices differ by 30-50%)
- Subject to manipulation (nominee transactions at deflated prices)

**Decision: NB-5 should NOT track property prices as claims.**

Rationale:

- Price data fails the confidence threshold — no T0-T2 source can verify land prices
- Any price claim would be PROVISIONAL at best, ABSTAIN likely
- Clients asking "how much does land cost in Canggu?" should get PricingTool consultation guidance, not stale NLM data
- BPN NJOP (tax value) is available and trackable, but it is 20-50% below market value and belongs in NB-4 (Tax)

**What NB-5 DOES track about prices:**

- NJOP zones and update schedules (reference data, not live prices)
- BPHTB rate structure (2.5% of transaction value minus NJOP threshold)
- BPN registration fee schedule (government fees, not market prices)
- Minimum property values for foreign Hak Pakai (PP 103/2015 thresholds per zone)

### 4.4 BPN Website Down (Notoriously Unreliable)

**Failure Mode:** `atrbpn.go.id` and regional BPN portals are known for:

- Frequent downtime (maintenance, server issues)
- Content changes without versioning
- Broken links to regulations

**Mitigation:**

1. **Pre-import text sources:** Upload critical BPN regulations as text (not URL) into NB-5. Text sources are immune to URL downtime.
2. **Mirror on JDIH BPK:** `peraturan.bpk.go.id` mirrors many BPN regulations. Use as fallback URL source.
3. **Scraper-side monitoring:** Intel scraper already has retry logic. No special handling needed.

**Circuit breaker:** Use CB-SOURCE from NB-2 (already defined). 5 consecutive failures to import from `*.bpn.go.id` domains triggers OPEN state.

### 4.5 Perda Bali Not Digitized

**Failure Mode:** Many Perda (local regulations) are not available online. Key missing regulations include:

- RTRW Kabupaten (zoning details per district)
- Perda specific to tourism zone construction limits
- Pergub on green zone and temple exclusion buffers

**Mitigation:**

1. **BZ team contribution:** Have the BZ legal team scan and upload key Perda as text sources to NB-5 (manual, one-time)
2. **JDIH Bali monitoring:** `jdih.baliprov.go.id` — add to T4 social monitoring for any new publications
3. **Cross-reference:** Use Hukumonline and academic sources that DISCUSS the Perda (T4-T5) when the original text (T0) is unavailable
4. **Explicit gap tracking:** MD-4 (Open Questions) lists "Perda referenced but text unavailable" with specific regulation numbers

---

## 5. TESTING PROTOCOL ADAPTATION — NB-2's 8-Phase Test for NB-5

### 5.1 Test Phase Adaptations

**Phase 0: Connectivity (same as NB-2)**

- Verify NLM API access
- Verify NB-5 notebook exists and is accessible
- Verify auth token valid
- Target: all pre-flight checks pass

**Phase 1: Source Ingest**

- Target source count for first test: **8-12 sources** (6 existing seeds + 2-6 from first research_start)
- Add 3-4 T0 regulations as text sources (UU 5/1960, PP 18/2021, PP 103/2015, Permen ATR/BPN 18/2021)
- Verify should_import() filters work (test with property domains)
- Acceptance: 10+ ACTIVE sources, 0 in QUARANTINE after triage

**Phase 2: Query Response — Property-Specific Test Queries**

| Test Query                                                           | Expected Behavior                                 | Pass Criteria                                        |
| -------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------- |
| "Hak Pakai untuk WNA berdasarkan PP 18/2021"                         | Cites PP 18/2021, explains 30+20+20 formula       | Confidence >= 0.60, cites T0 source                  |
| "Prosedur pendaftaran tanah di BPN untuk HGB PT PMA"                 | Describes BPN registration, references PP 24/1997 | Mentions PPAT and AJB                                |
| "What are the risks of nominee arrangements for foreigners in Bali?" | Warns of illegality, cites UU 5/1960              | Does NOT provide instructions for setting up nominee |
| "Zonasi RTRW Bali kawasan pariwisata"                                | References RTRW, discusses tourism zones          | Mentions green zone restrictions                     |
| "Perbedaan Hak Pakai dan HGB untuk kepemilikan properti"             | Accurate comparison, cites correct laws           | 2+ T0 sources cited                                  |

**Phase 3: Claim Extraction — Property Claim Categories**

NB-5 claim categories (adapting NB-2's 10 categories):

| Category             | Example Claim                                                      |
| -------------------- | ------------------------------------------------------------------ |
| LEGAL_FRAMEWORK      | "UU 5/1960 Pasal 21 prohibits foreign freehold ownership"          |
| OWNERSHIP_STRUCTURE  | "PT PMA can hold HGB for 30+20+20 years per PP 18/2021"            |
| REGISTRATION_PROCESS | "BPN registration requires AJB from PPAT within 7 working days"    |
| ZONING_REGULATION    | "RTRW Bali classifies Canggu as zona pariwisata"                   |
| TAX_TRIGGER          | "BPHTB is 2.5% of transaction value above NJOPTKP threshold"       |
| PRICE_THRESHOLD      | "Minimum Hak Pakai property value for WNA: IDR 5B in Zone 1"       |
| CONSTRUCTION_PERMIT  | "PBG replaces IMB per PP 16/2021, effective nationally"            |
| DISPUTE_RISK         | "Nominee arrangements are void under UU 5/1960 Pasal 26"           |
| COMPLIANCE_DEADLINE  | "HGB extension must be filed 2 years before expiry"                |
| ENFORCEMENT_ACTION   | "BPN Badung revoked 12 nominee-structured certificates in Q1 2026" |

Acceptance: extract 15+ claims from Phase 1 sources with confidence >= 0.55.

**Phase 4: Consolidation Test**

- Import 6+ sources on the same topic (e.g., "nominee risk")
- Trigger consolidation
- Verify ILM < 0.10 (no more than 10% claim loss)
- Verify Master Digest created with [NB5-MD] prefix

**Phase 5: Cross-Domain Test**

- Query about "PT PMA property acquisition" — should reference NB-3 (company setup)
- Query about "BPHTB rates" — should reference NB-4 (tax)
- Verify cross-domain references appear in MD-3

**Phase 6: Breaking News Override**

- Simulate a new Permen ATR/BPN regulation detection
- Verify override scoring (threshold >= 75)
- Verify scheduled query displacement (not dropped)

**Phase 7: Full Pipeline Dry Run**

- 5-day simulation (Mon-Fri) with mocked NLM responses
- Verify state file integrity after each day
- Verify weekly Friday consolidation
- Verify handoff package generation

### 5.2 Go/No-Go Criteria for NB-5

| Criterion                                       | Threshold | Blocking? |
| ----------------------------------------------- | --------- | --------- |
| Pre-flight checks pass (Phase 0)                | 12/12     | YES       |
| ACTIVE source count after Phase 1               | >= 15     | YES       |
| Phase 2 query confidence (median)               | >= 0.55   | YES       |
| Claims extracted (Phase 3)                      | >= 15     | YES       |
| ILM on consolidation test (Phase 4)             | < 0.10    | YES       |
| Cross-domain references present (Phase 5)       | >= 2      | NO        |
| Nominee risk query does NOT provide setup steps | YES       | YES       |
| Pipeline dry run completes without ABORT        | 5/5 days  | YES       |
| Handoff package validates against JSON schema   | Valid     | YES       |

---

## 6. T4 SOCIAL MONITOR DESIGN

### 6.1 Accounts to Monitor

Following NB-2's T4 pattern (RSS/web + social), NB-5 needs these channels:

| Account / Source                        | Platform  | Priority | Content                                            |
| --------------------------------------- | --------- | -------- | -------------------------------------------------- |
| **@kaborekementerian_atr** (verify!)    | Instagram | CRITICAL | National land agency announcements                 |
| **@bpn_bali** (verify!)                 | Instagram | CRITICAL | Bali provincial land office                        |
| **@dpuprbali** / Dinas PUPR Bali        | Web/IG    | HIGH     | Building permits (PBG), construction               |
| **Bappeda Bali**                        | Web       | HIGH     | RTRW updates, spatial planning                     |
| **INI Bali** (Ikatan Notaris Indonesia) | Web/IG    | MEDIUM   | Notary association guidance, PPAT updates          |
| **AREBI Bali** (Real Estate Brokers)    | Web       | LOW      | Market intelligence (not for claims, context only) |
| **Hukumonline.com** (property section)  | RSS/Web   | HIGH     | Legal analysis on property regulations             |
| **JDIH BPK** (peraturan.bpk.go.id)      | Web       | HIGH     | Official gazette mirror for new regs               |
| **JDIH Bali** (jdih.baliprov.go.id)     | Web       | MEDIUM   | Perda Bali publication                             |
| **Kementerian ATR/BPN**                 | YouTube   | HIGH     | Policy announcements, sosialisasi                  |
| **Ditjen SPPR ATR/BPN**                 | YouTube   | HIGH     | Spatial planning policy videos                     |

### 6.2 RSS/Web Sources

```python
NB5_T4_SOURCES = [
    # Official portals
    {"url": "https://atrbpn.go.id/berita", "type": "web_scrape", "frequency": "daily"},
    {"url": "https://jdih.baliprov.go.id", "type": "web_scrape", "frequency": "daily"},
    {"url": "https://peraturan.bpk.go.id/", "type": "web_scrape", "frequency": "daily"},
    # Legal analysis
    {"url": "https://hukumonline.com/tag/pertanahan", "type": "rss_or_scrape", "frequency": "6h"},
    {"url": "https://hukumonline.com/tag/properti", "type": "rss_or_scrape", "frequency": "6h"},
    # Social (verify handles exist before activating)
    {"url": "instagram:kaborekementerian_atr", "type": "social", "frequency": "6h"},
    {"url": "instagram:bpn_bali", "type": "social", "frequency": "6h"},
]
```

### 6.3 SVS Threshold for T4

NB-2's T4 social monitor uses SVS threshold >= 0.35 for ingestion.

NB-5 proposal: **SVS >= 0.35 (same).**

Rationale: Property social posts from official accounts are equally valuable per post as immigration ones. No reason to change the threshold. The 3-layer filter (fetch -> SVS filter -> NLM ingest) remains the same.

### 6.4 Fetch Frequency

NB-2 T4: every 6 hours (`0 */6 * * *` cron on Air).

NB-5 T4: **every 12 hours** (`0 */12 * * *` — 00:00 and 12:00 WITA).

Rationale: Property regulation announcements happen less frequently than immigration ones. BPN and Bappeda post weekly, not daily. 12-hour intervals are sufficient and reduce API/scraping load.

### 6.5 Implementation

NB-5 T4 monitor reuses the existing T4 framework from `apps/evaluator/nlm_deep_research/`:

- Same `run_t4_monitor.sh` pattern
- New config file: `t4_nb5_config.json` with NB-5 sources
- Separate PID lock file to avoid conflict with NB-2 T4
- Same SVS calculation, same circuit breaker (CB_T4 FSM)

---

## 7. COST MODEL

### 7.1 NLM API Costs

NLM (NotebookLM) pricing is based on the Google AI tier. NLM Ultra (which we use) includes:

- Unlimited notebooks (we use 10)
- Up to 600 sources per notebook
- `research_start` uses Gemini under the hood (deep research)

**Per-query cost estimate:**

- Each `research_start(mode=deep)` consumes approximately 1 "deep research" credit
- NLM Ultra plan: included in subscription, no per-query charge for typical usage
- Rate limit risk: undocumented, but conservative budget (20 queries/week/notebook) mitigates this

### 7.2 Source Population Costs

| Item                              | Count     | Cost                        |
| --------------------------------- | --------- | --------------------------- |
| Seed sources (6 internal)         | 6         | $0 (existing)               |
| T0 regulation upload (text)       | 8-12      | $0 (manual)                 |
| research_start queries (Month 1)  | ~17/month | Included in NLM Ultra       |
| Claim extraction LLM (Qwen local) | ~20/month | $0 (local Ollama)           |
| T4 social monitoring (scraping)   | ~60/month | $0 (existing scraper infra) |

### 7.3 Monthly Operating Cost

| Component                        | Monthly Cost                                 |
| -------------------------------- | -------------------------------------------- |
| NLM Ultra subscription (shared)  | ~$20/month (allocated share of 10 notebooks) |
| Compute (Pro cron, existing)     | $0 (already running)                         |
| T4 web scraping (existing infra) | $0                                           |
| Claim extraction LLM (local)     | $0 (Qwen 3.5:9b on Pro)                      |
| Total incremental for NB-5       | **~$2/month** (NLM subscription share)       |

### 7.4 One-Time Setup Cost

| Task                                | Time Est.     | Who                               |
| ----------------------------------- | ------------- | --------------------------------- |
| T0 regulation sourcing + upload     | 4 hours       | Claude Code                       |
| Pipeline config (state files, cron) | 2 hours       | Claude Code                       |
| T4 config file + source list        | 1 hour        | Claude Code                       |
| Testing (Phase 0-7)                 | 4 hours       | Claude Code + manual verification |
| Total                               | **~11 hours** |                                   |

---

## 8. RISK REGISTER

### Top 5 Risks for NB-5 Population

| #   | Risk                                                                                                                                                                                          | Likelihood | Impact | Mitigation                                                                                                                                                                                                                                                                                                          |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Perda Bali text unavailable online** — Many local regulations are not digitized, creating a gap in T0-T2 sources for Bali-specific zoning and construction rules                            | HIGH       | HIGH   | Pre-upload known Perda as text sources. Track gap in MD-4. Use Hukumonline analysis (T4-T5) as proxy. Engage BZ legal team for physical gazette scanning.                                                                                                                                                           |
| 2   | **BPN website unreliable** — atrbpn.go.id has frequent downtime, breaking URL-based sources and T4 monitoring                                                                                 | HIGH       | MEDIUM | Upload critical BPN regulations as text (not URL). Use JDIH BPK mirror as fallback. CB-SOURCE triggers after 5 failures. No impact on text-based T0 sources.                                                                                                                                                        |
| 3   | **Nominee arrangement content risk** — NB-5 must cover nominee risk without providing a "how-to guide," which could create legal liability for Bali Zero                                      | MEDIUM     | HIGH   | Hard-code content guardrail: nominee claims MUST include `dispute_risk` category and MUST reference UU 5/1960 illegality. Go/No-Go test: verify no setup instructions in query responses. MD-5 explicitly frames as "risks and consequences."                                                                       |
| 4   | **Scheduling conflicts with NB-3/NB-4 rollout** — If NB-3 and NB-4 population takes longer than expected, NB-5 pipeline slot is delayed, blocking property intelligence coverage              | MEDIUM     | MEDIUM | NB-5 is designed for 2 days/week (not daily). Can start with 1 day/week initially, expanding as other notebooks stabilize. Manual NLM queries can fill the gap before automated pipeline is live.                                                                                                                   |
| 5   | **Awig-awig gap creates false confidence** — Clients may believe NB-5 covers "all property law" when awig-awig (unwritten customary law) is explicitly excluded, leading to incomplete advice | LOW        | HIGH   | MD-4 (Open Questions) explicitly lists awig-awig as uncoverable. All NB-5 query responses about desa adat land MUST include disclaimer. Claim extraction flags `awig_awig_relevant: true` on affected claims. Zantara prompt includes standing instruction to recommend local PPAT consultation for desa adat land. |

### Risk Dependencies

```
Risk 1 (Perda gap) ──> Risk 5 (false confidence)
  If local regs are missing AND awig-awig is uncoverable,
  NB-5's Bali-specific coverage has a significant blind spot.
  Mitigation: MD-4 + standing disclaimers make this EXPLICIT.

Risk 2 (BPN down) ──> Risk 4 (scheduling delay)
  If BPN is down during initial population testing,
  Phase 1 may not reach 15 sources target, delaying Go/No-Go.
  Mitigation: Text-uploaded T0 sources are BPN-independent.
```

---

## 9. OPEN QUESTIONS (for brainstorm resolution)

1. **Instagram handle verification:** The brainstorm prompt lists `@kaborekementerian_atr` with a "likely typo" note. This must be verified before T4 activation. Incorrect handles = wasted monitoring cycles.

2. **NB-5 Master Document count:** NB-2 has 4 MDs. NB-5 may need 5-6 given the local/national split:
   - MD-1: Change Log
   - MD-2: Operations Status
   - MD-3: Cross-Domain (NB-3, NB-4, NB-6)
   - MD-4: Open Questions (including awig-awig gap)
   - MD-5: Price Rules (government fees ONLY, not market prices)
   - MD-6 (optional): Awig-Awig Impact Summary

3. **Parallel vs sequential notebook queries:** Can we run NB-2 and NB-5 `research_start` calls simultaneously via different NLM sessions? If yes, the 02:25 start for NB-5 can move to 01:10 (parallel with NB-2), finishing by 02:30. This doubles throughput in the same window. Needs NLM API testing.

4. **RTRW Bali version:** Which version of RTRW Provinsi Bali is current (likely Perda Bali 16/2009, revised)? This is a critical T0 source that must be verified before population.

5. **Cross-domain NB-4 boundary:** Where exactly does "BPHTB rate" live? NB-4 (Tax) owns the tax calculation, but NB-5 needs to reference it in property transaction contexts. Proposed: NB-5 says "BPHTB applies at 2.5%" (fact), NB-4 owns the detailed calculation with NJOPTKP thresholds.

---

_Operational Discipline Review prepared by Claude Opus 4.6 — 2026-03-29_
_Reference: NB-2 pipeline specs (Steps 2, 4, 5, 6, 7) at docs/superpowers/specs/nlm-deep-research/_

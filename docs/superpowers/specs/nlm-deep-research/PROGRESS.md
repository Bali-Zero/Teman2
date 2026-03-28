# NLM Deep Research Pipeline — Brainstorm Progress

> Last updated: 2026-03-28 (Step 7 complete — ALL STEPS DONE)
> Session: brainstorm with Gemini + Codex GPT-5.4 + DeepSeek R1

## Target

Design automated NLM Deep Research pipeline for NB-2 (Immigration & Visa Indonesia).
Then replicate pattern across all 10 notebooks.

## Architecture Decision (CRITICAL)

- NLM runs UPSTREAM of intel scraper: 01:00-02:20 WITA
- Scraper runs AFTER at 03:00, independently — NLM brief is optional enrichment, NOT dependency
- War Room can pick NLM topics as daily editorial themes

## Completed Steps

### Step 1: Query Design ✅ → `01_query_design.md`

- 20 query templates (8 L1, 4 L2, 4 L3, 4 L4) — TEST catalog, NOT all daily
- Production target: 2-4 queries/day per NB
- Dual-language: 60% Bahasa, 30% English, 10% bridge
- 5 visa clusters (A: work, B: stay, C: visit, D: special, E: compliance)
- Signal-driven follow-ups with decay
- Anti-noise: specificity + regulatory terminology as primary weapon

### Step 2: Sequencing ✅ → `02_sequencing.md`

- Daily window: 01:00-02:20 WITA (upstream of scraper at 03:00)
- 2 queries/day: L1 (01:10) + L2 (01:35), semi-sequential with context injection
- Weekly rotation: Mon=A, Tue=B, Wed=C, Thu=D+L3, Fri=E+consolidation
- Weekend OFF (Indonesian gazette Mon-Fri only)
- Breaking news: 3-layer detection, score >=75 override, 72h auto-decay
- State machine: 7 states, JSON in apps/evaluator/, crash recovery via task_id
- Budget: never >40 calls/week, backoff at 3 failures

### Step 3: Quality Verification ✅ → `03_quality_verification.md`

- 7-tier source hierarchy (T0-T6) with local Bali govt as T2-T4
- Instagram of immigration offices = T4 (first-class, not noise)
- Confidence formula: Auth(0.30) + Corr(0.25) + Spec(0.15) + Type(0.12) + Recency(0.10) + Geo(0.08) - Penalty
- Thresholds: >=0.75 VERIFIED, 0.55-0.74 PROVISIONAL, <0.55 not in brief
- Hard gate: eligibility/fee/deadline claims need T0-T2 for VERIFIED
- Local-national contradictions: NEVER discard silently, tag enforcement_divergence
- Brief separated: LAW | OFFICE OPERATIONS | ENFORCEMENT SIGNALS
- 10 claim categories, atomic extraction, claim metadata with 25+ fields
- 4-stage cross-reference: NB-2 internal → scraper archive → govt portals → local sources
- Local monitoring: Ngurah Rai IG daily, Pemprov Bali 2-3x/week, 5 local news outlets

### Step 4: Source Management ✅ → `04_source_management.md` (synthesis) + `04b_source_management_codex.md`

**Unified Synthesis (04 — Claude Opus 4.6 architect, integrating DeepSeek R1 + Codex + Gemini):**

- 6-stage lifecycle: INGEST → QUARANTINE → TRIAGE → ACTIVE → CONSOLIDATE → ARCHIVE
- Source Value Score (SVS): 5-factor formula (tier+claims+freshness+citations+uniqueness) + bonuses
- Type-specific staleness decay: LAW_IN_FORCE=infinite, NEWS=15d half-life, REGULATION=90d
- 4 source categories: Canonical(15-25), Working(25-35), Master Digest(4-8), Reference(3-6)
- 70 ACTIVE cap with capacity triggers at 56(soft)/63(hard)/70(cap)
- 4 Master Documents as NLM **sources** (not notes) for query inclusion: Change Log, Ops Status, Cross-Domain, Open Questions
- 4-level dedup: URL match → title similarity → content fingerprint → claim overlap (Szymkiewicz-Simpson)
- Information Loss Metric (ILM <0.05) as hard gate on consolidation
- Notebook Health Score (NHS): 5-factor composite, Telegram weekly report
- External state: `nlm_nb2_sources.json` + `nlm_nb2_claims.jsonl` (append-only)
- Full source metadata schema with SVS, claims, dedup fingerprints, flags
- Capacity model: steady-state ~55-70, 600-limit safe (~100 max per NB)
- Implementation: 12 phases, ~34h, critical path P1→P2→P4→P6→P11 (15h MVP)

**Codex GPT-5.4 (04b — operational discipline, preserved as reference):**

- 14 lifecycle transitions with SLAs, pre-import filter pseudocode, emergency pruning
- Master Document markdown templates, versioning, domain denylist
- Open Questions hard rules: max 15 open, 30d auto-close

**Key synthesis decisions:**

- Master Docs = NLM sources (Opus/Gemini) NOT notes (Codex) — sources contribute to notebook_query synthesis
- Consolidation trigger = N>=4 AND cooled AND ILM<0.05 (DeepSeek formula + Codex conditions)
- Active capacity management required (DeepSeek: passive decay alone stabilizes at ~120, too high)

### Step 5: Intel Scraper Integration ✅ → `05_scraper_integration.md` (synthesis) + `05b_*_codex.md` + `05b_*_deepseek.md`

**Unified Synthesis (05 — Claude Opus 4.6 architect, integrating Gemini + Codex + DeepSeek R1):**

- Handoff package JSON schema v1: versioned dated files + `latest.json` symlink, atomic writes
- Topic Relevance Score (TRS): 5-factor formula filters what enters handoff (>=0.65 threshold, max 5 topics)
- 3 integration modes: IGNORE (no file), ENRICH (low confidence), PRIORITIZE (>=0.75 verified)
- `NLMEnricher` adapter: 1 new file, ~18 lines changed in scraper, triple error boundary, only additive
- Cross-validation: CONVERGENCE (logarithmic boost B(n)=0.30\*ln(1+n)/ln(6)), NLM-ONLY (decay), SCRAPER-ONLY (novel signal)
- Contradiction penalty: P(m) = min(0.40, 0.15\*m) proportional to current confidence
- Feedback loop prevention: provenance tagging, domain exclusions, `balizero.com` blocked, detection function
- War Room: NLM topics auto-selected if HIGH+confidence>=0.75, Gemini fallback, manual override
- Integration Value Added (IVA): target 0.35-0.55 at steady state (Month 6)
- 8 primary KPIs: conversion rate, cross-val confirmation, handoff freshness, adoption, false positive, IVA
- 7 failure scenarios → all degrade gracefully to existing behavior (zero regression)
- Testing: 15 unit tests, regression test (identical output without handoff), loop detection
- Implementation: 3 files modified + 1 new, 5-phase plan (5 days)
- ROI: ~$230/month net positive from Month 2

**Key synthesis decisions:**

- File-based handoff (not API/DB) — zero coupling, debuggable, atomic, audit trail
- Logarithmic boost (DeepSeek) over linear (Gemini) — natural diminishing returns, cap at 0.95
- Adapter pattern (Codex) over inline code (Gemini) — production safety, testable
- Schema evolution: additive only, 30-day dual-write for breaking changes

### Step 6: Failure Modes ✅ → `06_failure_modes.md` (synthesis) + `06b_failure_modes_gemini.md`

**Unified Synthesis (06 — Claude Opus 4.6 architect, integrating Codex + Gemini + DeepSeek R1):**

- 10 critical invariants with enforcement code (Codex): ACTIVE<=70, ILM<0.05, no balizero.com, etc.
- 30 failure modes in 4 categories (Gemini): Data Quality(8), System(10), Integration(8), Operational(8)
- Risk scoring formula (DeepSeek): Risk = P _ I _ (1 + D/24), top 5: old-as-new, hallucination, MD staleness, bloat, cluster skew
- 3 independent circuit breakers (Gemini): CB-NLM (auto-close), CB-SOURCE (manual close), CB-INTEGRATION (auto-close)
- Cascading rules: CB-NLM >5d → CB-SOURCE, CB-SOURCE >7d → CB-INTEGRATION
- 5 cascading failure analyses including worst-case 4-level feedback loop cascade
- 12-point pre-flight checklist at 01:00 WITA (Codex)
- State corruption recovery for all 4 state files from Friday snapshots
- MTTR targets: automated <5min, manual <2h, full restart <30min
- 4 degradation levels: NOMINAL → DEGRADED_L1 → DEGRADED_L2 → HALTED
- Idempotency: dedup guard, task_id persistence, atomic writes
- Monday morning monitoring checklist (7 sections)
- Structured audit trail (JSONL, 8 categories)

**Key synthesis decisions:**

- Codex invariants (Sections 1-9) as primary actionable structure
- Gemini taxonomy (30 modes) and cascading analysis as reference catalog
- DeepSeek risk scoring to prioritize which failures to address first
- Cardinal rule: at any degradation level, scraper/War Room operate identically to pre-NLM behavior

### Step 7: Testing Protocol ✅ → `07_testing_protocol.md` (architect) + `07b_testing_protocol_deepseek.md` (metrics)

**Claude Opus 4.6 (architect — 07):**

- 8-phase controlled test protocol (Phase 0-7) + Go/No-Go assessment (Phase 8)
- Phase 0: Environment setup — NB-2 creation, 20 canonical seed sources, 4 Master Documents, state file initialization
- Phase 1: First L1 monitoring query on Cluster A, import-quarantine-metadata verification
- Phase 2: Triage decision tree — tier assignment, 4-level dedup, SVS calculation
- Phase 3: Claim extraction — atomic claims, 10-category taxonomy, confidence scoring, hard gate enforcement
- Phase 4: L2 comparative query with Phase 1 context injection, cross-query dedup, corroboration
- Phase 5: Source lifecycle — manual consolidation trigger, ILM < 0.05 gate, Master Document update, archive
- Phase 6: Handoff package — TRS scoring, mode selection (IGNORE/ENRICH/PRIORITIZE), NLMEnricher adapter, schema validation
- Phase 7: Failure/recovery — state corruption recovery, circuit breaker (CB-NLM), capacity overflow + emergency prune, INV-4 feedback loop enforcement
- Go/No-Go: GREEN (all 8 pass) / YELLOW (6-7 pass) / RED (<=5 pass). 7 hard-blocker conditions
- Estimated: 45-80 min, ~15 NLM API calls, printable execution checklist
- Includes: production transition plan (10-step post-GREEN deployment)

**DeepSeek R1 (metrics — 07b):**

- Baseline measurement protocol: NB-2 snapshot, scraper 30d SQL, War Room history
- Per-phase quantified acceptance criteria: numeric targets + hard fail thresholds for all 8 phases
- Month 1 weekly KPI table: 11 metrics tracked W1→W4 with trend requirements
- 4 statistical tests: (A) Welch's t-test for scraper quality, (B) Chi-square/Fisher for War Room adoption, (C) Wilson CI calibration per confidence band, (D) Spearman + MAE for SVS vs human
- Go/No-Go decision framework: Week 2 (CONTINUE/ADJUST/ABORT) + Week 4 (PROMOTE/EXTEND/REDESIGN) with exact criteria and data package templates
- Cost model: ~$51/month total, ROI 292-919% (pessimistic-expected), break-even at 3 enriched articles
- Post-production monitoring: 8 alert thresholds with demotion ladder (NOMINAL→DEGRADED_L1→L2→HALTED)
- Metric-to-Step traceability: every numeric target traced to its origin in Steps 1-6
- Key insight: "Claim verification accuracy >= 85% by Week 4" is the single most important metric — everything else is downstream

## NB-1 Oracle Review (2026-03-28)

**Verdict:** APPROVED WITH CONDITIONS (3 conditions).
**Review validation:** Gemini + Codex + DeepSeek reviewed the 3 conditions independently.

| Condition                      | NB-1 Proposal                       | 3-AI Verdict     | Resolution                                                          |
| ------------------------------ | ----------------------------------- | ---------------- | ------------------------------------------------------------------- |
| C1: A2A Routing to Air         | Route nlm_api.py via air.local:8087 | **REJECTED 3/3** | `nlm` CLI on Pro, pipeline on Pro. No routing needed                |
| C2: Auth Watchdog 23:30        | Daily cookie warmup at night        | **MODIFY 3/3**   | Weekly watchdog (6h check, 5d/10d alerts), CHECK 4 hard gate        |
| C3: Pydantic on notebook_query | Validate NLM prose with Pydantic    | **MODIFY 3/3**   | Pydantic on ClaimRecord, HandoffPackage, PipelineState, SourceEntry |

C2 + C3 modifications applied to `06_failure_modes.md` §3.3 and §0.

## Pipeline Design COMPLETE

All 7 steps are now designed. The full pipeline specification covers:

| Step | Document                           | Scope                                                    |
| ---- | ---------------------------------- | -------------------------------------------------------- |
| 1    | `01_query_design.md`               | 20 templates, 5 clusters, dual-language                  |
| 2    | `02_sequencing.md`                 | 01:00-02:20 WITA, 2 queries/day, weekly rotation         |
| 3    | `03_quality_verification.md`       | 7-tier sources, confidence scoring, claim extraction     |
| 4    | `04_source_management.md`          | 70 ACTIVE cap, 6-stage lifecycle, SVS, NHS               |
| 5    | `05_scraper_integration.md`        | File-based handoff, TRS, NLMEnricher adapter             |
| 6    | `06_failure_modes.md`              | 30 failure modes, 10 invariants, 3 circuit breakers      |
| 7    | `07_testing_protocol.md`           | 8-phase test, Go/No-Go, production transition            |
| 7b   | `07b_testing_protocol_deepseek.md` | Baselines, KPIs, statistical tests, cost model, go/no-go |

**Next action:** Complete Phase 1 adversarial review synthesis, then proceed to Phase 2.

## Phase 0: Environment Setup ✅ COMPLETE (2026-03-28 17:05)

| Item                                 | Status | Detail                                                                                |
| ------------------------------------ | ------ | ------------------------------------------------------------------------------------- |
| Duplicate removed                    | ✅     | `7625b0cd` (UU 6/2011) deleted from NB-2                                              |
| `nlm_nb2_pipeline_state.json`        | ✅     | Initialized with 10 invariants, 3 CBs, schedule                                       |
| `nlm_nb2_sources.json`               | ✅     | 42 sources tracked (38 original + 4 MDs)                                              |
| `nlm_nb2_claims.jsonl`               | ✅     | Empty (append-only, ready)                                                            |
| `~/.agent/decisions/nlm_to_scraper/` | ✅     | Created with `/handoff` + `/archive` subdirs                                          |
| MD-1 Change Log                      | ✅     | `bc98c989` — initialized                                                              |
| MD-2 Operations Status               | ✅     | `dc11bcf9` — initialized                                                              |
| MD-3 Cross-Domain Impacts            | ✅     | `6d336e6b` — initialized                                                              |
| MD-4 Open Questions                  | ✅     | `bda28a80` — initialized                                                              |
| Invariants                           | ✅     | 10/10 pass                                                                            |
| Baseline NHS                         | ✅     | **0.668** (NORMAL) — H_cap=0.764, H_fresh=0.70, H_qual=0.40, H_cov=0.60, H_dedup=1.00 |
| NB-2 total sources                   | ✅     | **42** (38 seed + 4 MDs)                                                              |

## Phase 1: First L1 Query + Adversarial Review ✅ COMPLETE (2026-03-28 17:45)

**L1 Query (Cluster A — Work permits/TKA):**

- Query language: Bahasa Indonesia (60% target)
- Response: 37 citations, 10 sources used (24% of 42)
- Topics covered: RPTKA/DKPTKA changes, permitted/prohibited positions, KITAS E23 renewal, costs
- Key regulations cited: PP 34/2021, SE 3/836/PK.04/I/2026, Kepmenaker 228/2019, 349/2019, Permenkumham 22/2023, Permenimipas 5/2025, UU 63/2024

**4-Voice Adversarial Review — Aggregate Score: 7.0/10:**

| Voice          | Score | Top Finding                                                                |
| -------------- | ----- | -------------------------------------------------------------------------- |
| V1 Gemini      | 6.5   | KBLI factual error (05-09 vs 06), "One Sponsor Policy" may be fabricated   |
| V2 Codex       | 7.0   | Super-source risk, 8 claims, handoff TRS, no T0 used (expected)            |
| V3 DeepSeek R1 | 6.5   | Codebase IMTA contradiction, 5 missing reasoning chains, 38% HIGH          |
| V4 Claude      | 7.5   | UU 63/2024 untracked T0, monitoring-vs-explaining problem, MD seeding plan |

**Claims extracted:** 10 (5 VERIFIED, 3 PROVISIONAL, 1 LOW, 1 corrected from NLM error)
**Full review:** `phase1_adversarial_reviews.md`

**Verdict: PASS (PROVISIONAL) — GO to Phase 2 with conditions:**

- P0: Verify SE 3/836 on JDIH, fix KBLI error in claim
- P1: Ingest UU 63/2024 as T0, fix `kg_subgraph_visa.py` IMTA refs, seed MDs
- P2: Add T4 sources, split super-source, build alias resolver

## Testing Checkpoint (2026-03-28, pre-clear — preserved)

**Original Phase 0 Inventory (NB-2 baseline):**

- NB-2 ID: `cff93ab0-813a-42f2-a8de-36987e724271`
- Original sources: 39 (before dedup)
- NLM auth: valid on Pro (cookies expire April 2027)
- `nlm` CLI: v0.5.9 on both Pro and Air

**Testing workflow (per step):**
Multi-round adversarial review: Execute → 4 independent analyses → cross-share → web research + NB-9 deep → v1 reports → cross-read → v2 reports → synthesis → NLM convalida → fix → re-test → document

## Documents

```
docs/superpowers/specs/nlm-deep-research/
├── 00_mega_synthesis.md                 # High-level overview from round 1
├── 01_query_design.md                   # Step 1 — Query design (20 templates, 5 clusters)
├── 02_sequencing.md                     # Step 2 — Sequencing (01:00-02:20 WITA)
├── 03_quality_verification.md           # Step 3 — Quality verification (7-tier, confidence)
├── 04_source_management.md              # Step 4 — UNIFIED SYNTHESIS (Opus architect)
├── 04b_source_management_codex.md       # Step 4 — Codex raw perspective (reference)
├── 05_scraper_integration.md            # Step 5 — UNIFIED SYNTHESIS (Opus architect)
├── 05b_scraper_integration_codex.md     # Step 5 — Codex (contracts + discipline)
├── 05b_scraper_integration_deepseek.md  # Step 5 — DeepSeek R1 (formulas + KPIs)
├── 06_failure_modes.md                  # Step 6 — UNIFIED SYNTHESIS (Opus architect)
├── 06b_failure_modes_gemini.md          # Step 6 — Gemini (taxonomy + circuit breakers)
├── 07_testing_protocol.md               # Step 7 — Opus (8-phase operational protocol)
├── 07b_testing_protocol_deepseek.md    # Step 7 — DeepSeek R1 (metrics, stats, go/no-go)
└── PROGRESS.md                          # This file
```

## Method

Each step: prompt Gemini + Codex + DeepSeek R1 in parallel → wait all 3 → synthesize → save document.
Then proceed to next step.

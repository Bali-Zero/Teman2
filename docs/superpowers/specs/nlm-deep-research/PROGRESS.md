# NLM Deep Research Pipeline — Brainstorm Progress

> Last updated: 2026-03-28
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

### Step 4: Source Management ✅ → `04_source_management.md`

- Source staleness formula: 8 type-specific exponential decay functions (law=infinite, news=15d half-life)
- Source Value Score (SVS): 5-factor weighted formula + bonuses (tier+claims+freshness+citations+uniqueness)
- Dedup: claim-level Szymkiewicz-Simpson overlap, 4 threshold tiers (0.90/0.70/0.40)
- Capacity model: steady-state ~55-70 with active trim, 600-limit hit in ~13w if dedup fails
- Budget: 15-20 canonical + 30-40 working + 5-8 master + 5 reserved
- Notebook Health Score (NHS): 5-factor composite, alert at <0.45
- Consolidation: N>=4 same-topic + cooled + ILM<0.05 information loss gate
- 4 Master Documents: Changelog, Operations, CrossDomain, OpenQuestions
- Complete lifecycle state machine: DISCOVERED→QUARANTINE→TRIAGE→ACTIVE→[CONSOLIDATE|ARCHIVE|DELETE]
- Week-by-week Month 1 projection with KPIs and pass/fail criteria

## Remaining Steps

### Step 5: Intel Scraper Integration — NEXT

- NLM upstream, scraper independent but enriched
- Handoff package format (scraper_input.json)
- Cross-validation protocol
- War Room topic selection flow

### Step 6: Failure Modes

- Source bloat, old-as-new, hallucination, feedback loop, rate limits
- Detection + handling for each
- Circuit breaker design

### Step 7: Testing Protocol

- 8-phase controlled test on NB-2
- Baseline inventory → first query → verify → second query → lifecycle trial → scraper comparison
- Success metrics: novelty >30%, verification accuracy >85%, manual intervention <5%

## Documents

```
docs/superpowers/specs/nlm-deep-research/
├── 00_mega_synthesis.md      # High-level overview from round 1
├── 01_query_design.md        # Step 1 complete
├── 02_sequencing.md          # Step 2 complete
├── 03_quality_verification.md # Step 3 complete
├── PROGRESS.md               # This file
├── 04_source_management.md   # Step 4 complete
├── 05_scraper_integration.md # Step 5 (pending)
├── 06_failure_modes.md       # Step 6 (pending)
└── 07_testing_protocol.md    # Step 7 (pending)
```

## Method

Each step: prompt Gemini + Codex + DeepSeek R1 in parallel → wait all 3 → synthesize → save document.
Then proceed to next step.

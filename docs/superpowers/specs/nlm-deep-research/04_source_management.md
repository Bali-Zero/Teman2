# Step 4: Source Management — NB-2 Deep Research Pipeline

> Synthesis: DeepSeek R1 perspective (formulas + quantification) (2026-03-28)
> Status: Brainstorm complete
> Depends on: Step 3 (Quality Verification — tier system, confidence formula, claim extraction)

---

## 1. Source Staleness Formula

### Core Principle

Not all sources stale equally. A law in force from 2020 is as fresh as one from today. A news article from 30 days ago is ancient. The staleness function must be **type-aware**.

### Staleness Score S(t, type)

```
S(t, type) = max(0, 1 - D(t, type))
```

Where `D(t, type)` is the decay function and `t` = days since publication/last-confirmed-valid.

### Decay Functions by Source Type

| Source Type             | Decay Function D(t) | Half-Life | Rationale                                                |
| ----------------------- | ------------------- | --------- | -------------------------------------------------------- |
| **LAW_IN_FORCE**        | `0` (no decay)      | Infinite  | Active legislation doesn't stale. S = 1.0 always         |
| **LAW_SUPERSEDED**      | `1 - e^(-0.023t)`   | 30 days   | Once replaced, value drops fast                          |
| **REGULATION_CIRCULAR** | `1 - e^(-0.0077t)`  | 90 days   | Surat Edaran/implementation details can be superseded    |
| **OFFICIAL_PORTAL**     | `1 - e^(-0.0116t)`  | 60 days   | Portal content may be updated without notice             |
| **OFFICIAL_SOCIAL**     | `1 - e^(-0.0231t)`  | 30 days   | Instagram/social posts are ephemeral operational signals |
| **NEWS_ARTICLE**        | `1 - e^(-0.0462t)`  | 15 days   | News cycle is fast; old news has low intelligence value  |
| **ANALYSIS_REPORT**     | `1 - e^(-0.0058t)`  | 120 days  | Law firm analyses age slower but do age                  |
| **MASTER_DIGEST**       | `1 - e^(-0.0039t)`  | 180 days  | Our own consolidated summaries; refreshed quarterly      |

**Formula derivation:** Half-life `h` gives decay constant `lambda = ln(2)/h`. At `t = h`, `D = 0.5`, so `S = 0.5`.

### Explicit Values (for quick reference)

| Type                | S at 7d | S at 30d | S at 90d | S at 180d | S at 365d |
| ------------------- | ------- | -------- | -------- | --------- | --------- |
| LAW_IN_FORCE        | 1.00    | 1.00     | 1.00     | 1.00      | 1.00      |
| LAW_SUPERSEDED      | 0.85    | 0.50     | 0.13     | 0.02      | 0.00      |
| REGULATION_CIRCULAR | 0.95    | 0.79     | 0.50     | 0.25      | 0.06      |
| OFFICIAL_PORTAL     | 0.92    | 0.71     | 0.35     | 0.12      | 0.01      |
| OFFICIAL_SOCIAL     | 0.85    | 0.50     | 0.13     | 0.02      | 0.00      |
| NEWS_ARTICLE        | 0.72    | 0.25     | 0.02     | 0.00      | 0.00      |
| ANALYSIS_REPORT     | 0.96    | 0.84     | 0.59     | 0.35      | 0.12      |
| MASTER_DIGEST       | 0.97    | 0.89     | 0.71     | 0.50      | 0.24      |

### Auto-Archive Threshold

```
IF S(t, type) < 0.20  →  AUTO_ARCHIVE
IF S(t, type) < 0.10  →  AUTO_DELETE (from NB-2, retain in archive DB)
```

**Exception:** LAW_IN_FORCE sources are NEVER auto-archived. Only manual archive when explicitly superseded.

### Refresh Mechanism

When a source is cited by a new Deep Research result, its `last_confirmed_valid` timestamp resets:

```
t_effective = min(days_since_publication, days_since_last_confirmed)
```

This means a 2024 regulation that was independently cited yesterday has `t_effective = 1`, not `t_effective = 730`.

---

## 2. Source Value Score (SVS)

### Purpose

When NB-2 approaches capacity, SVS determines which sources stay and which get archived. Higher SVS = more valuable = keep.

### Formula

```
SVS = W_tier * V_tier
    + W_claims * V_claims
    + W_freshness * S(t, type)
    + W_citations * V_citations
    + W_uniqueness * V_uniqueness
    + BONUS
```

### Weights

| Factor                               | Weight | Rationale                                                |
| ------------------------------------ | ------ | -------------------------------------------------------- |
| **Tier Authority (V_tier)**          | 0.25   | High-tier sources are harder to replace                  |
| **Claims Extracted (V_claims)**      | 0.25   | Sources with many verified claims are dense intelligence |
| **Freshness S(t,type)**              | 0.20   | Fresh sources carry current intelligence                 |
| **Citation Frequency (V_citations)** | 0.15   | Sources cited in briefs/queries are actively useful      |
| **Uniqueness (V_uniqueness)**        | 0.15   | Sources with non-overlapping claims are irreplaceable    |

### Sub-Score Definitions

**V_tier** (from Step 3 tier system):

| Tier                         | V_tier |
| ---------------------------- | ------ |
| T0 (national law)            | 1.00   |
| T1 (national implementation) | 0.90   |
| T2 (regional authority)      | 0.80   |
| T3 (enforcement)             | 0.65   |
| T4 (official social)         | 0.50   |
| T5 (press)                   | 0.35   |
| T6 (community)               | 0.10   |

**V_claims** (normalized by extraction density):

```
V_claims = min(1.0, claims_extracted / 8)
```

- 0 claims: V = 0.00 (source added but never produced intelligence)
- 1-2 claims: V = 0.13-0.25 (low density)
- 4 claims: V = 0.50 (typical good source)
- 8+ claims: V = 1.00 (dense intelligence source — capped)

**V_citations** (how often the source was referenced in pipeline outputs):

```
V_citations = min(1.0, times_cited_in_briefs / 5)
```

- 0 citations: V = 0.00 (imported but never used — dead weight)
- 1 citation: V = 0.20
- 3 citations: V = 0.60 (regularly referenced)
- 5+ citations: V = 1.00 (core reference source)

**V_uniqueness** (fraction of claims that ONLY this source provides):

```
V_uniqueness = unique_claims / max(1, total_claims)
```

- If 3 of 4 claims from this source are also in other sources: V = 0.25
- If all claims are unique to this source: V = 1.00

**BONUS** (additive, max +0.15):

| Condition                                                         | Bonus |
| ----------------------------------------------------------------- | ----- |
| Source is the SOLE T0-T2 backing for an active VERIFIED claim     | +0.10 |
| Source was manually promoted by operator                          | +0.05 |
| Source covers a regulatory gap (no other source on this subtopic) | +0.10 |
| Source is a Master Digest we created                              | +0.05 |

### SVS Classification

| SVS Range   | Classification | Action                                                             |
| ----------- | -------------- | ------------------------------------------------------------------ |
| >= 0.70     | **ESSENTIAL**  | Never auto-archive. Manual review only                             |
| 0.45 - 0.69 | **VALUABLE**   | Keep unless at hard capacity. Archive last                         |
| 0.25 - 0.44 | **MARGINAL**   | First candidates for consolidation or archive                      |
| < 0.25      | **EXPENDABLE** | Auto-archive. If V_claims = 0 and age > 14d: auto-delete from NB-2 |

### Worked Example

```
Source: NusaBali article "Tim Pora sweeps Canggu businesses"
  V_tier = 0.35 (T5 press)
  V_claims = 0.25 (2 claims extracted)
  S(t=12, NEWS_ARTICLE) = 0.57 (12-day old news)
  V_citations = 0.20 (cited once in brief)
  V_uniqueness = 0.50 (1 of 2 claims is unique)
  BONUS = 0 (no special conditions)

SVS = 0.25*0.35 + 0.25*0.25 + 0.20*0.57 + 0.15*0.20 + 0.15*0.50
    = 0.088 + 0.063 + 0.114 + 0.030 + 0.075
    = 0.370 → MARGINAL

Decision: Candidate for consolidation into weekly enforcement digest.
```

```
Source: JDIH Gazette — Permenkumham 3/2026
  V_tier = 1.00 (T0 national law)
  V_claims = 0.50 (4 claims extracted)
  S(t=60, LAW_IN_FORCE) = 1.00 (no decay)
  V_citations = 1.00 (cited in 7 briefs)
  V_uniqueness = 0.75 (3 of 4 claims unique)
  BONUS = +0.10 (sole T0 backing for active claim)

SVS = 0.25*1.00 + 0.25*0.50 + 0.20*1.00 + 0.15*1.00 + 0.15*0.75 + 0.10
    = 0.250 + 0.125 + 0.200 + 0.150 + 0.113 + 0.100
    = 0.938 → ESSENTIAL

Decision: Never archive. Core source.
```

---

## 3. Deduplication Metrics

### Similarity Computation

Use claim-level overlap, NOT full-text similarity. Two sources may have different prose but contain the same regulatory information.

```
Overlap(A, B) = |claims(A) ∩ claims(B)| / min(|claims(A)|, |claims(B)|)
```

Using `min()` denominator (Szymkiewicz-Simpson coefficient) rather than `union` (Jaccard) because we want to detect when a smaller source is fully contained within a larger one.

### Claim Matching Criteria

Two claims `c_A` and `c_B` are considered "same claim" when ALL of:

1. Same `category` (e.g., both LEGAL_CHANGE)
2. Same `regulation_ref` or `subject_entity` (e.g., both about Permenkumham 3/2026 Art. 47)
3. Same `assertion_direction` (e.g., both say "max stay reduced" — not one says reduced, other says extended)
4. Temporal overlap: `|effective_date_A - effective_date_B| <= 30 days`

If only conditions 1+2 match but 3 or 4 differ, the claims are `CONFLICTING`, not duplicate.

### Deduplication Thresholds

| Scenario                                                     | Overlap Threshold | Action                                                     |
| ------------------------------------------------------------ | ----------------- | ---------------------------------------------------------- |
| **TRUE_DUPLICATE** (same article, different URL)             | >= 0.90           | Auto-archive lower-SVS source                              |
| **SUBSTANTIAL_OVERLAP** (same regulation, different article) | >= 0.70           | Keep higher-SVS; archive lower unless it has unique claims |
| **PARTIAL_OVERLAP** (overlapping coverage)                   | 0.40 - 0.69       | Both stay. Flag for consolidation review                   |
| **INDEPENDENT**                                              | < 0.40            | No action. Different intelligence                          |

### Special Case: Same-Regulation-Different-Analysis

When two sources discuss the same regulation but offer different analysis (e.g., law firm A interprets Art. 47 differently from law firm B):

```
IF regulation_ref matches AND assertion_direction differs:
    → NOT duplicate. Both kept. Tag: COMPETING_INTERPRETATION
    → Escalate to daily brief as "disputed point"
```

### Dedup Ratio Monitoring

```
dedup_ratio = sources_archived_as_duplicate / sources_imported_this_period
```

| Period      | Healthy Range                              | Warning                             | Alarm                                   |
| ----------- | ------------------------------------------ | ----------------------------------- | --------------------------------------- |
| **Daily**   | 0-20% (0-1 of ~5 imports)                  | >30% (queries returning same stuff) | >50% (query templates stale)            |
| **Weekly**  | 10-25% (3-8 of ~25 imports)                | >35% (rotation not diverse enough)  | >50% (urgent query redesign)            |
| **Monthly** | 15-30% (natural overlap over 100+ imports) | >40% (sources converging)           | >50% (NB-2 saturated on current topics) |

### Alarm Response Protocol

| Dedup Level       | Response                                                                                 |
| ----------------- | ---------------------------------------------------------------------------------------- |
| **Daily > 30%**   | Log warning. Check if today's query was too similar to yesterday's                       |
| **Weekly > 35%**  | Review query templates for this week's cluster. Add specificity or shift subtopic        |
| **Weekly > 50%**  | Emergency: rotate query templates. Consider adding new cluster subtopics. Telegram alert |
| **Monthly > 40%** | Quarterly audit triggered early. Redesign 30% of query templates                         |

---

## 4. Capacity Planning

### Mathematical Model

```
N(d) = N(0) + sum_{i=1}^{d} [I(i) - A(i)]
```

Where:

- `N(d)` = total sources in NB-2 on day `d`
- `N(0)` = initial source count (target: 40)
- `I(i)` = sources imported on day `i`
- `A(i)` = sources archived on day `i`

### Import Rate Model

```
I(d) = Q(d) * R_import * (1 - R_dedup)
```

Where:

- `Q(d)` = queries run on day `d` (typically 2, max 3)
- `R_import` = average sources imported per query (expected: 3-5 for deep mode)
- `R_dedup` = deduplication rate against existing sources

**Expected values:**

| Parameter                | Pessimistic | Expected | Optimistic |
| ------------------------ | ----------- | -------- | ---------- |
| Q (queries/day, weekday) | 2           | 2        | 3          |
| R_import (sources/query) | 5           | 4        | 3          |
| R_dedup                  | 10%         | 20%      | 30%        |
| **I (net imports/day)**  | **9.0**     | **6.4**  | **4.2**    |

### Archive Rate Model

```
A(d) = A_staleness(d) + A_dedup_weekly(d) + A_consolidation(d)
```

Where:

- `A_staleness(d)` = sources hitting S < 0.20 on day `d`
- `A_dedup_weekly(d)` = 0 on Mon-Thu; dedup batch on Friday
- `A_consolidation(d)` = sources consumed into Master Digests (monthly)

**Expected values (per week):**

| Component                                | Sources/Week                                   |
| ---------------------------------------- | ---------------------------------------------- |
| Staleness auto-archive                   | 4-8 (news articles aging out in 15-30d)        |
| Friday dedup batch                       | 3-6 (substantial overlaps from week's imports) |
| Monthly consolidation (amortized weekly) | 1-2                                            |
| **Total weekly archive**                 | **8-16**                                       |

### Steady-State Analysis

At steady state: `I_weekly = A_weekly`

```
I_weekly = 5 days * 6.4 sources/day = 32 sources/week imported
A_weekly (target) = 32 sources/week archived (to maintain steady state)
```

But archives lag imports (staleness takes days/weeks to trigger), so we need to model the transient:

```
Week 1:  N = 40 + 32 - 8  = 64 (importing faster than archiving — NEWS not yet stale)
Week 2:  N = 64 + 32 - 12 = 84 (some Week 1 news starting to stale)
Week 3:  N = 84 + 32 - 18 = 98 (more staleness kicking in + first dedup cycle)
Week 4:  N = 98 + 32 - 24 = 106 (first monthly consolidation)
Week 5:  N = 106 + 32 - 28 = 110 (approaching equilibrium)
Week 8:  N ≈ 115-125 (steady state with current parameters)
```

**Problem:** Steady state at ~120 sources exceeds target range of 40-70.

### Solution: Active Capacity Management

The pure staleness/dedup model stabilizes too high. We need an **active archive trigger**:

```
IF N(d) > CAPACITY_TARGET_HIGH (70):
    sorted = sources.sort_by(SVS, ascending)
    archive_count = N(d) - CAPACITY_TARGET_MID (55)
    FOR source IN sorted[:archive_count]:
        IF source.SVS < 0.45:  # Only archive MARGINAL or EXPENDABLE
            archive(source)
        ELSE:
            break  # Don't archive VALUABLE sources to hit target
```

### Revised Steady-State With Active Management

```
Week 1:  N = 40 + 32 - 8  = 64 → trim to 55 (archive 9 lowest-SVS)
Week 2:  N = 55 + 32 - 12 = 75 → trim to 55 (archive 20 lowest-SVS)
Week 3:  N = 55 + 32 - 18 = 69 → within range, no trim
Week 4:  N = 69 + 32 - 24 = 77 → trim to 55 (archive 22 lowest-SVS)
...
Steady state: oscillates 55-75, averaging ~65 (within 40-70 target)
```

### Capacity Budget Allocation

| Category                             | Slots (of ~65) | Purpose                             | Lifecycle                           |
| ------------------------------------ | -------------- | ----------------------------------- | ----------------------------------- |
| **Canonical** (T0-T2 law/regulation) | 15-20 (23-31%) | Permanent reference. SVS > 0.70     | Years. Only archive when superseded |
| **Working** (active intelligence)    | 30-40 (46-62%) | Current findings from deep research | Days to weeks. Stale/dedup/archive  |
| **Master Digest** (consolidated)     | 5-8 (8-12%)    | Our own weekly/monthly summaries    | Months. Replace with newer digest   |
| **Reserved** (emergency buffer)      | 5 (8%)         | For breaking news override imports  | Always empty unless override active |

### Growth Projection: Dedup Failure Scenario

If dedup COMPLETELY fails (R_dedup = 0) and active management is disabled:

```
I_weekly = 5 * 2 * 5 * 1.0 = 50 sources/week (no dedup)
A_weekly (staleness only) ≈ 8-10/week

N(week) = 40 + 42*week (net ~42/week growth)

Week 1:   82
Week 4:   208
Week 8:   376
Week 13:  586  ← HITS 600 LIMIT at ~week 13.3
```

**Time to 600 with zero dedup + zero active management: ~13 weeks (~3 months)**

With active management but zero dedup:

```
Weekly trim keeps N at ~65
BUT: trimming 42 sources/week means losing nearly everything imported
→ Signal: if trim_count > 30/week for 2+ weeks → dedup is broken → ALARM
```

### Capacity Alert Thresholds

| Metric                          | Green     | Yellow                | Red                                |
| ------------------------------- | --------- | --------------------- | ---------------------------------- |
| N (total sources)               | 40-70     | 71-100                | >100                               |
| Weekly net growth               | -5 to +10 | +11 to +20            | >+20                               |
| Weekly trim count               | 0-10      | 11-20                 | >20 (dedup may be broken)          |
| Canonical slots used            | 15-20     | 21-25                 | >25 (too many "permanent" sources) |
| Reserved slots used             | 0         | 1-3 (override active) | >3 (overrides accumulating)        |
| Sources with 0 claims after 14d | 0-2       | 3-5                   | >5 (import quality degraded)       |

---

## 5. Source Health Dashboard

### Per-Pipeline-Run Metrics (collected every run at ~02:10)

```json
{
  "run_date": "2026-03-28",
  "run_id": "nb2-2026-03-28-001",

  "inventory": {
    "total_sources": 63,
    "by_category": {
      "canonical": 18,
      "working": 38,
      "master_digest": 5,
      "reserved_used": 2
    },
    "by_tier": {
      "T0": 5,
      "T1": 8,
      "T2": 5,
      "T3": 4,
      "T4": 6,
      "T5": 30,
      "T6": 5
    }
  },

  "flow": {
    "imported_today": 7,
    "deduped_today": 2,
    "archived_staleness": 1,
    "archived_capacity_trim": 0,
    "net_change": 4
  },

  "quality": {
    "avg_svs": 0.52,
    "median_svs": 0.48,
    "svs_below_025": 3,
    "sources_zero_claims_gt14d": 1,
    "avg_staleness_score": 0.71,
    "sources_below_staleness_020": 2
  },

  "dedup": {
    "pairs_checked": 45,
    "true_duplicates": 1,
    "substantial_overlaps": 1,
    "competing_interpretations": 0,
    "dedup_ratio_today": 0.29,
    "dedup_ratio_week_rolling": 0.22
  },

  "coverage": {
    "clusters_covered_this_week": ["A", "B", "C"],
    "clusters_missing_this_week": ["D", "E"],
    "claim_categories_covered": 7,
    "claim_categories_missing": [
      "FEE_CHANGE",
      "DOCUMENT_REQUIREMENT",
      "UNCLASSIFIED_SIGNAL"
    ],
    "visa_types_with_active_claims": ["KITAS_INVESTOR", "B211A", "KITAP", "VOA"]
  },

  "health_score": 0.78
}
```

### Notebook Health Score (NHS)

Composite metric for the overall state of NB-2:

```
NHS = W1 * H_capacity + W2 * H_freshness + W3 * H_quality + W4 * H_coverage + W5 * H_dedup
```

| Factor          | Weight | Formula                                                             | Ideal                                        |
| --------------- | ------ | ------------------------------------------------------------------- | -------------------------------------------- |
| **H_capacity**  | 0.20   | `1 - abs(N - 55) / 55` (penalize deviation from target midpoint 55) | N = 55 → H = 1.0                             |
| **H_freshness** | 0.25   | `avg(S(t, type))` across all sources                                | All sources fresh → H = 1.0                  |
| **H_quality**   | 0.25   | `avg(SVS)` across all sources                                       | High SVS portfolio → H = 1.0                 |
| **H_coverage**  | 0.15   | `clusters_covered / 5 * 0.6 + claim_categories_covered / 10 * 0.4`  | Full coverage → H = 1.0                      |
| **H_dedup**     | 0.15   | `max(0, 1 - max(0, dedup_ratio_week - 0.15) / 0.35)`                | dedup < 15% → H = 1.0; dedup > 50% → H = 0.0 |

### Alert Thresholds

| Metric                                   | Normal  | Warning         | Critical    |
| ---------------------------------------- | ------- | --------------- | ----------- |
| **NHS**                                  | >= 0.65 | 0.45 - 0.64     | < 0.45      |
| **Total sources**                        | 40-70   | 71-100 or 30-39 | >100 or <30 |
| **Avg staleness**                        | >= 0.60 | 0.40 - 0.59     | < 0.40      |
| **Sources with 0 claims (>14d)**         | 0-2     | 3-5             | >5          |
| **Weekly dedup ratio**                   | 10-25%  | 26-40%          | >40%        |
| **Canonical slots**                      | 15-20   | <10 or >25      | <5 or >30   |
| **Days since last T0-T2 import**         | 0-7     | 8-14            | >14         |
| **Consecutive days with net growth >10** | 0-1     | 2-3             | >3          |

### Alert Routing

| Severity     | Channel                         | Response                                              |
| ------------ | ------------------------------- | ----------------------------------------------------- |
| **Normal**   | JSON log only                   | No action                                             |
| **Warning**  | Telegram notification (owner)   | Review within 24h                                     |
| **Critical** | Telegram alert + pipeline pause | Immediate review. Pipeline paused until manual resume |

### Weekly Health Trend

Track NHS over 7 days to detect drift:

```
IF NHS(today) < NHS(yesterday) for 3 consecutive days:
    → DEGRADATION alert (Telegram)
    → Suggest: run manual dedup, review query templates, check import quality

IF NHS(today) > 0.80 for 5+ consecutive days:
    → STABLE_HEALTHY (no action needed)
```

---

## 6. Consolidation Formula

### When to Consolidate

Consolidation = merging N working sources on the same topic into 1 Master Digest.

**Trigger conditions (ALL must be true):**

```
CONSOLIDATION_TRIGGER:
  N_sources >= 4                              # At least 4 sources on same topic
  AND all sources in same claim_category      # e.g., all LEGAL_CHANGE about Permenkumham X
  AND topic_age >= 14 days                    # Topic has been tracked for 2+ weeks
  AND no source added in last 3 days          # Topic has cooled (no new information flowing)
  AND total_unique_claims >= 6                # Enough substance to justify a digest
```

### Why N >= 4?

| N      | Action          | Rationale                                           |
| ------ | --------------- | --------------------------------------------------- |
| 1      | Keep as-is      | Single source = no redundancy to consolidate        |
| 2      | Keep both       | Too few for meaningful synthesis                    |
| 3      | Review only     | Might consolidate if all 3 are T5/T6 on same event  |
| **4+** | **Consolidate** | Enough sources for synthesis; likely 40-60% overlap |

### The Consolidation Process

```
INPUT:  N working sources + their extracted claims
OUTPUT: 1 Master Digest source + archived originals

STEPS:
1. UNION all claims from N sources (deduplicated by claim matching criteria from Section 3)
2. For each unique claim, select BEST source chain:
   - Prefer highest-tier source
   - Prefer most specific quote
   - Retain 2 sources minimum for cross-reference
3. Synthesize digest document:
   - Header: topic, regulation refs, date range, N sources consolidated
   - Body: each unique claim with best source chain
   - Footer: list of archived source IDs
4. Add digest as new source (type: MASTER_DIGEST, tier: synthetic)
5. Archive N originals (they remain in archive DB, removed from NB-2)
```

### Information Loss Metric (ILM)

**Goal: consolidation should preserve >95% of intelligence.**

```
ILM = 1 - (unique_claims_in_digest / unique_claims_in_all_originals)
```

| ILM         | Interpretation                                     | Action                                                    |
| ----------- | -------------------------------------------------- | --------------------------------------------------------- |
| 0.00        | Perfect: all claims preserved                      | Proceed                                                   |
| 0.01 - 0.05 | Acceptable: lost 1-5% (likely UNCLASSIFIED_SIGNAL) | Proceed, log what was dropped                             |
| 0.06 - 0.10 | Warning: lost 6-10% of claims                      | Review dropped claims manually before archiving originals |
| > 0.10      | Reject: too much information loss                  | Do NOT archive originals. Review consolidation logic      |

### What Gets Dropped (acceptable losses)

Claims that MAY be dropped during consolidation (contributing to ILM but acceptable):

1. **UNCLASSIFIED_SIGNAL** claims with confidence < 0.35 (noise)
2. Duplicate claims where source chain is strictly inferior (same info, worse attribution)
3. Claims that have been SUPERSEDED by newer claims in the same topic

Claims that MUST be preserved:

1. Any claim at VERIFIED or PROVISIONAL confidence
2. Any claim with `enforcement_divergence: true`
3. Any claim that is the SOLE evidence for a specific assertion
4. All T0-T2 source chain entries (even if the claim is also backed by T5)

### Consolidation Schedule

| Cadence                   | Scope                                                                                 | Expected Volume                             |
| ------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------- |
| **Weekly (Friday)**       | Same-event clusters from the week (e.g., 4 articles about same enforcement operation) | 0-2 consolidations, archiving 4-10 sources  |
| **Monthly (last Friday)** | Same-regulation clusters accumulated over month                                       | 1-3 consolidations, archiving 8-20 sources  |
| **Quarterly**             | Full topic review — merge monthly digests into quarterly digest                       | 2-4 consolidations, archiving 10-25 sources |

### Consolidation Budget Impact

Per consolidation: N sources archived, 1 digest added → net reduction of (N-1) sources.

```
Expected monthly consolidation savings:
  Weekly: 2 consolidations * 4 sources each = 8 archived, 2 digests added = net -6
  Monthly: 2 consolidations * 6 sources each = 12 archived, 2 digests added = net -10
  Total monthly net reduction from consolidation: ~16 sources
```

This is the mechanism that prevents the steady-state from rising above 70.

---

## 7. Source Lifecycle — Complete State Machine

### States

```
DISCOVERED → QUARANTINE → TRIAGE → ACTIVE → [CONSOLIDATE | ARCHIVE | DELETE]
                                    ↕
                                  FLAGGED
```

| State           | Duration       | Entry Condition                                              | Exit Condition                                     |
| --------------- | -------------- | ------------------------------------------------------------ | -------------------------------------------------- |
| **DISCOVERED**  | 0 (instant)    | Deep Research returns source URL                             | Always transitions to QUARANTINE                   |
| **QUARANTINE**  | 0-24h          | New source imported                                          | Passes triage criteria OR manual review            |
| **TRIAGE**      | 1 pipeline run | In quarantine, next pipeline runs                            | SVS calculated, dedup checked                      |
| **ACTIVE**      | Days to months | Passed triage, not duplicate                                 | Staleness < 0.20 OR capacity trim OR consolidation |
| **FLAGGED**     | Until resolved | Contradiction detected, competing interpretation, or anomaly | Manual resolution or auto-resolve after 7d         |
| **CONSOLIDATE** | 1 pipeline run | Consolidation trigger met (Section 6)                        | Claims extracted into Master Digest                |
| **ARCHIVE**     | Permanent      | Stale, duplicate, consolidated, or capacity trim             | Never (archived sources stay in archive DB)        |
| **DELETE**      | Permanent      | Staleness < 0.10 AND in archive > 30d AND 0 citations        | Removed from archive DB                            |

### Triage Decision Tree

```
new_source arrives from Deep Research
  │
  ├── Exact URL match in NB-2? ──YES──→ SKIP (true duplicate at URL level)
  │
  ├── Overlap >= 0.90 with existing? ──YES──→ ARCHIVE (true content duplicate)
  │
  ├── Overlap >= 0.70 with existing?
  │     ├── New source SVS > existing SVS? ──YES──→ REPLACE (archive old, activate new)
  │     └── No ──→ ARCHIVE new (existing is better)
  │
  ├── Source tier = T6 AND no T0-T4 corroboration? ──YES──→ ARCHIVE (unverifiable)
  │
  ├── N(current) >= 70?
  │     ├── New source SVS > min(existing SVS)? ──YES──→ REPLACE lowest-SVS
  │     └── No ──→ ARCHIVE new (no room for marginal source)
  │
  └── All checks pass ──→ ACTIVE
```

---

## 8. Four Master Documents

These are persistent curated sources within NB-2 that accumulate intelligence over time.

| Document                  | Content                                                                                                             | Refresh Cadence               | Max Size                            |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------- | ----------------------------------- |
| **MASTER_CHANGELOG**      | All regulation changes tracked, with dates + status (announced/effective/implemented/superseded)                    | Weekly (Friday consolidation) | ~50 entries, rolling 6 months       |
| **MASTER_OPERATIONS**     | Current status of Bali immigration offices — hours, processing times, known delays, local requirements              | Weekly                        | ~20 entries, current state only     |
| **MASTER_CROSSDOMAIN**    | Immigration intersections with tax, company, property — updated from L4 queries                                     | Monthly (1st Thursday)        | ~15 entries, rolling 12 months      |
| **MASTER_OPEN_QUESTIONS** | Unresolved signals: regulations announced but not yet published, contradictions pending resolution, rumored changes | Weekly                        | ~10 entries, auto-expire at 30 days |

### Master Document SVS

Master Documents always have:

- `V_tier` = 0.80 (synthetic T2-equivalent)
- `V_claims` = 1.00 (by definition, they contain dense claims)
- `V_uniqueness` = 1.00 (they ARE the consolidation)
- `V_citations` = varies (but typically high)
- Staleness = governed by MASTER_DIGEST half-life (180 days)
- **Minimum SVS ≈ 0.75 → always ESSENTIAL**

---

## 9. Decision Tables Summary

### Daily Decisions

| Event                               | Condition | Action                                     |
| ----------------------------------- | --------- | ------------------------------------------ |
| Source imported                     | Always    | Calculate SVS, check dedup, triage         |
| Source has S < 0.20                 | Auto      | Archive                                    |
| Source has SVS < 0.25 and age > 14d | Auto      | Archive                                    |
| N > 70 after imports                | Auto      | Trim lowest-SVS MARGINAL sources to N = 55 |
| Source contradiction detected       | Auto      | Flag, do not archive either source         |
| Dedup ratio today > 30%             | Auto      | Log warning                                |

### Weekly Decisions (Friday)

| Event                   | Condition                          | Action                                                   |
| ----------------------- | ---------------------------------- | -------------------------------------------------------- |
| Dedup batch             | Always                             | Run full pairwise overlap check, archive TRUE_DUPLICATEs |
| Consolidation check     | N_same_topic >= 4 AND topic cooled | Run consolidation, verify ILM < 0.05                     |
| NHS trend               | 3-day declining                    | Telegram warning                                         |
| Master Document refresh | Always                             | Update CHANGELOG, OPERATIONS, OPEN_QUESTIONS             |
| Health dashboard        | Always                             | Generate weekly health report                            |

### Monthly Decisions

| Event                      | Condition                            | Action                                              |
| -------------------------- | ------------------------------------ | --------------------------------------------------- |
| Monthly consolidation      | Accumulated same-regulation clusters | Merge into monthly digests                          |
| Master CROSSDOMAIN refresh | 1st Thursday L4 query completed      | Update cross-domain document                        |
| Capacity budget review     | Always                               | Verify canonical/working/digest/reserved allocation |
| Query template review      | Dedup ratio monthly > 30%            | Redesign 30% of templates                           |

### Quarterly Decisions

| Event                | Condition | Action                                                                  |
| -------------------- | --------- | ----------------------------------------------------------------------- |
| Full audit           | Always    | Source freshness, query relevance, cluster balance, accuracy spot-check |
| Archive cleanup      | Always    | Delete archived sources with S < 0.10 and 0 citations and age > 90d     |
| Master Digest rollup | Always    | Merge monthly digests into quarterly digest                             |
| Pipeline drift check | Always    | Compare execution times, import rates, dedup rates quarter-over-quarter |

---

## 10. Projections & Expected Metrics (Month 1)

### Week-by-Week Projection

| Week      | Imports | Archives | Trim | Consolidations | N (end) | NHS (est) |
| --------- | ------- | -------- | ---- | -------------- | ------- | --------- |
| 0 (start) | —       | —        | —    | —              | 40      | 0.70      |
| 1         | 32      | 8        | 9    | 0              | 55      | 0.72      |
| 2         | 32      | 14       | 5    | 0              | 68      | 0.74      |
| 3         | 32      | 18       | 12   | 1 (-3 net)     | 65      | 0.76      |
| 4         | 32      | 22       | 8    | 2 (-8 net)     | 59      | 0.78      |

**Steady state (Month 2+):** N oscillates 55-70, NHS 0.75-0.82, weekly trim 5-12 sources.

### Key Performance Indicators (KPIs)

| KPI                          | Target    | Measurement       |
| ---------------------------- | --------- | ----------------- |
| N (source count)             | 55 +/- 15 | Daily             |
| NHS (health score)           | >= 0.70   | Daily             |
| Avg SVS                      | >= 0.45   | Weekly            |
| Dedup ratio (weekly)         | 15-25%    | Weekly            |
| ILM (consolidation loss)     | < 0.05    | Per consolidation |
| Sources with 0 claims > 14d  | <= 2      | Daily             |
| Days since last T0-T2 import | <= 7      | Daily             |
| Manual interventions / week  | <= 2      | Weekly            |

### Success Criteria for Month 1 Test

```
PASS if:
  - N stabilizes in 40-70 range by end of week 3
  - NHS never drops below 0.55
  - No more than 2 manual interventions per week needed
  - Dedup ratio never exceeds 40% for a full week
  - Zero consolidations lose > 5% of claims (ILM check)
  - At least 15 canonical sources maintained throughout

FAIL if:
  - N exceeds 100 at any point
  - NHS drops below 0.45 for 2+ consecutive days
  - Manual intervention needed daily
  - Dedup ratio exceeds 50% for any week
  - A consolidation drops a VERIFIED claim
```

---

## Source AI Perspective

### DeepSeek R1 (Il Pensatore) — This Document

This spec was designed from a data science perspective with emphasis on:

- Explicit mathematical formulas for every decision (no "older sources score lower" hand-waving)
- Quantified thresholds with clear green/yellow/red boundaries
- Steady-state analysis with growth projections under normal and failure scenarios
- Information Loss Metric to ensure consolidation doesn't silently destroy intelligence
- Composite health score (NHS) as single-number operational metric
- Week-by-week projections for Month 1 to set expectations

Key design choices:

- **Szymkiewicz-Simpson** over Jaccard for overlap (catches containment, not just intersection)
- **Exponential decay** with type-specific half-lives (matches real information aging patterns)
- **Active capacity management** in addition to passive staleness (pure decay doesn't converge fast enough)
- **Claim-level dedup** over text-level (two articles with same regulatory info are duplicates even if prose differs)
- **ILM < 0.05** as hard gate on consolidation (5% loss ceiling = ~1 claim per 20 preserved)
